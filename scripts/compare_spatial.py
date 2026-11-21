"""Guarded fresh-board PPO comparison. Production weights are read-only."""
import argparse
import hashlib
import json
import math
import os
import time
import uuid
from collections import Counter
from copy import deepcopy
from functools import partial
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import torch
import numpy as np
import psutil
from torch import nn

import local_agent as operator
import nn_play2 as trainer
import zar_boot
from env_zar import ZAREnvError
from nn_report import records
from experiment_signal import summarize_signal
from shelter_reward import DURATION_CAP, DURATION_MAX_INTERVAL


class SpatialPolicy(trainer.PolicyNet2):
    """One shared five-channel cell scorer per tool."""
    def __init__(self):
        super().__init__()
        del self.hc
        self.cell = nn.Linear(5, trainer.NU, bias=False)
        self.first = trainer.INPUT_LABELS.index('Grid civilians cell 1 (log1p count)')

    def forward(self, x, h=None):
        out, h = self.gru(x, h)
        cells = x[..., self.first:self.first + 5*trainer.NC].unflatten(-1, (5, trainer.NC))
        scores = self.cell(cells.transpose(-1, -2)).transpose(-1, -2).flatten(-2)
        return self.hu(out), scores, self.val(out).squeeze(-1), h


BREACH_COSTS = {'breach_baseline': trainer.BREACH_COST,
                'breach_stronger': 3 * trainer.BREACH_COST}
READY_CREDITS = {'coverage_baseline': 0., 'coverage_credit': .30}
ZONE_TEMPERATURES = {'zone_baseline': 1., 'zone_exploration': 1.5}
PLANNING_TEMPERATURES = {'planning_baseline': 1., 'planning_exploration': 1.35}
BATTLE_TEMPERATURES = {'battle_baseline': 1., 'battle_exploration': 1.5}
BATTLE_BOUNDARY_BY_ARM = {'boundary_control': False, 'boundary_filtered': True}
TARGET_SETTLE = {'target_baseline': False, 'target_settle': True}
READY_DELAY_COSTS = {'ready_delay_baseline': 0., 'ready_delay_cost': .002}
PLANNING_ENTROPY_BONUSES = {'entropy_baseline': 0., 'planning_entropy': .045}
DEFENSE_COSTS = {'defense_baseline': trainer.BREACH_COST,
                 'defense_stronger': 3 * trainer.BREACH_COST}
READY_SHORTFALL_COSTS = {'shortfall_baseline': 0., 'shortfall_penalty': .15}
SHELTER_DURATION_RATES = {'duration_baseline': 0., 'duration_credit': .01}
SHELTER_INPUT_BY_ARM = {'shelter_grid': False, 'shelter_exact': True}
SHELTER_GEOMETRY_BY_ARM = {'geometry_control': False, 'geometry_visible': True}
OPENING_TIMING_BY_ARM = {'opening_control': False, 'opening_visible': True}
CAPACITY_BY_ARM = {'recurrent_standard': trainer.HID, 'recurrent_wide': 192}
PREPARATION_CREDIT_BY_ARM = {'preparation_control': False, 'preparation_credit': True}


def widen_recurrence(source, optimizer):
    before, after = source.gru.hidden_size, CAPACITY_BY_ARM['recurrent_wide']
    if before != trainer.HID or source.gru.input_size != trainer.NOBS:
        raise ValueError('Recurrent expansion requires the original hidden and input widths')
    net = trainer.PolicyNet2(hidden_size=after)
    previous = source.state_dict()
    expanded = net.state_dict()

    def copy_weights(name, src, dst):
        if name.startswith('gru.'):
            for gate in range(3):
                old = slice(gate * before, (gate + 1) * before)
                new = slice(gate * after, gate * after + before)
                if name == 'gru.weight_hh_l0':
                    dst[new, :before] = src[old]
                    dst[new, before:] = 0.
                else:
                    dst[new] = src[old]
        elif name.endswith('.weight'):
            dst[:, :before] = src
            dst[:, before:] = 0.
        else:
            dst.copy_(src)
        return dst

    for name, value in expanded.items():
        copy_weights(name, previous[name], value)
    net.load_state_dict(expanded)
    optimizer = deepcopy(optimizer)
    groups = optimizer['param_groups']
    if len(groups) != 1 or len(groups[0]['params']) != len(previous):
        raise ValueError('Unexpected Adam parameter order for recurrent expansion')
    for name, parameter in zip(previous, groups[0]['params']):
        moments = optimizer['state'].get(parameter, {})
        for field, value in moments.items():
            if field in ('exp_avg', 'exp_avg_sq', 'max_exp_avg_sq'):
                if value.shape != previous[name].shape:
                    raise ValueError(f'Unexpected Adam shape for {name}')
                moments[field] = copy_weights(name, value, value.new_zeros(expanded[name].shape))
    return net, optimizer


def extend_private_model(source, optimizer, *, geometry=False, opening_timing=False):
    """Preserve the original GRU and Adam values when adding zero input columns."""
    net = trainer.PolicyNet2(shelter_occupancy=not (geometry or opening_timing),
                             shelter_geometry=geometry, opening_timing=opening_timing)
    added = net.gru.input_size - source.gru.input_size
    weights = source.state_dict()
    key = 'gru.weight_ih_l0'
    original_shape = weights[key].shape
    weights[key] = nn.functional.pad(weights[key], (0, added))
    net.load_state_dict(weights)
    optimizer = deepcopy(optimizer)
    groups = optimizer['param_groups']
    if len(groups) != 1 or len(groups[0]['params']) != len(weights):
        raise ValueError('Unexpected optimizer parameters for shelter input extension')
    first = groups[0]['params'][list(weights).index(key)]
    for name, value in optimizer['state'].get(first, {}).items():
        if name in ('exp_avg', 'exp_avg_sq', 'max_exp_avg_sq'):
            if value.shape != original_shape:
                raise ValueError('Unexpected Adam input moment width')
            optimizer['state'][first][name] = nn.functional.pad(value, (0, added))
    return net, optimizer


def episode(job, *, observe=False, audit_signal=False, separate_policy_cpus=False):
    copy, arm, weights, seed, tag, *phase = job
    battle_study = arm in BATTLE_TEMPERATURES
    boundary_study = arm in BATTLE_BOUNDARY_BY_ARM
    capacity_study = arm in CAPACITY_BY_ARM
    preparation_credit_study = arm in PREPARATION_CREDIT_BY_ARM
    target_study = arm in TARGET_SETTLE
    ready_study = arm in READY_DELAY_COSTS
    duration_study = arm in SHELTER_DURATION_RATES
    opening_study = arm in OPENING_TIMING_BY_ARM
    geometry_study = arm in SHELTER_GEOMETRY_BY_ARM
    input_study = arm in SHELTER_INPUT_BY_ARM or geometry_study
    planning_study = (arm in PLANNING_TEMPERATURES or arm in PLANNING_ENTROPY_BONUSES
                      or battle_study or target_study or ready_study)
    try:
        copy_dir = operator.owned_copy(copy)
        env = None
        if (arm in BREACH_COSTS or arm in READY_CREDITS or arm in ZONE_TEMPERATURES
                or planning_study or arm in DEFENSE_COSTS or arm in READY_SHORTFALL_COSTS
                or duration_study or input_study or boundary_study or opening_study or capacity_study
                or preparation_credit_study):
            try:
                env = zar_boot.boot(copy_dir, welcome_wait=15, discard_dump_states=True)
            except ZAREnvError as exc:
                print(f'{copy} fast boot failed: {exc}. Retrying with standard warmup.', flush=True)
        if env is None:
            env = zar_boot.boot(copy_dir, discard_dump_states=True)
    except ZAREnvError as exc:
        return {'err': str(exc)}
    inherited_cpus = None
    try:
        policy = SpatialPolicy if arm == 'shared' else trainer.PolicyNet2
        options = dict(start_kind='fresh', seed=seed, missile_credit=arm!='unshaped')
        if observe:
            options['observer_interval'] = 1.
        if target_study:
            options['settle_cast_target'] = TARGET_SETTLE[arm]
        if ready_study:
            options['ready_delay_cost'] = READY_DELAY_COSTS[arm]
        if battle_study or target_study or ready_study or audit_signal:
            options['experiment_signal'] = ('ready_delay' if ready_study else
                                            'target_settle' if target_study else
                                            'battle_tools' if battle_study else
                                            'planning_tools' if arm in PLANNING_TEMPERATURES else
                                            'zone_cells' if arm in ZONE_TEMPERATURES else
                                            'planning_entropy' if arm in PLANNING_ENTROPY_BONUSES else
                                            'spatial_cells' if arm in ('dense', 'shared') else 'receipts')
        if arm in ('standard', 'balanced'):
            options.update(fixed_speed='speed_1', fixed_clock=True)
        if arm in BREACH_COSTS:
            options.update(fixed_speed='speed_2', fixed_clock=True, occupied_breach_cost=BREACH_COSTS[arm])
        if arm in READY_CREDITS:
            options.update(fixed_speed='speed_2', fixed_clock=True, ready_coverage_credit=READY_CREDITS[arm])
        if arm in ZONE_TEMPERATURES:
            options.update(fixed_speed='speed_2', fixed_clock=True, ready_coverage_credit=.30)
            if phase == [True] and ZONE_TEMPERATURES[arm] != 1.:
                options['zone_temperature'] = ZONE_TEMPERATURES[arm]
        if planning_study:
            options.update(fixed_speed='speed_2', fixed_clock=True, ready_coverage_credit=.30)
            temperature = PLANNING_TEMPERATURES.get(arm, PLANNING_TEMPERATURES['planning_exploration'])
            if phase == [True] and temperature != 1.:
                options['planning_tool_temperature'] = temperature
            if battle_study and phase == [True]:
                options['battle_tool_temperature'] = BATTLE_TEMPERATURES[arm]
        if arm in ZONE_TEMPERATURES or planning_study:
            options['planning_zone_audit'] = True
        if arm in DEFENSE_COSTS or arm in READY_SHORTFALL_COSTS:
            options.update(fixed_speed='speed_2', fixed_clock=True, ready_coverage_credit=.30,
                           planning_zone_audit=True)
            if arm in DEFENSE_COSTS:
                options['occupied_breach_cost'] = DEFENSE_COSTS[arm]
            else:
                options['ready_shortfall_cost'] = READY_SHORTFALL_COSTS[arm]
            if phase == [True]:
                options['planning_tool_temperature'] = PLANNING_TEMPERATURES['planning_exploration']
        if duration_study:
            options.update(fixed_speed='speed_1', fixed_clock=True, ready_coverage_credit=.30,
                           planning_zone_audit=True, experiment_signal='receipts',
                           shelter_duration_rate=SHELTER_DURATION_RATES[arm])
            if phase == [True]:
                options['planning_tool_temperature'] = PLANNING_TEMPERATURES['planning_exploration']
        if boundary_study or capacity_study or preparation_credit_study:
            options.update(fixed_speed='speed_1', fixed_clock=True, ready_coverage_credit=.30,
                           planning_zone_audit=True, experiment_signal='receipts',
                           battle_boundary_filter=BATTLE_BOUNDARY_BY_ARM.get(arm, True))
            if capacity_study:
                policy = partial(trainer.PolicyNet2, hidden_size=CAPACITY_BY_ARM[arm])
                options['experiment_signal'] = 'recurrent_capacity'
            if preparation_credit_study:
                options['experiment_signal'] = 'preparation_credit'
            if phase == [True]:
                options['planning_tool_temperature'] = PLANNING_TEMPERATURES['planning_exploration']
        if opening_study:
            policy = partial(trainer.PolicyNet2, opening_timing=True)
            options.update(fixed_speed='speed_1', fixed_clock=True, ready_coverage_credit=.30,
                           planning_zone_audit=True, experiment_signal='receipts',
                           battle_boundary_filter=True, opening_timing_input=OPENING_TIMING_BY_ARM[arm])
            if phase == [True]:
                options['planning_tool_temperature'] = PLANNING_TEMPERATURES['planning_exploration']
        if input_study:
            policy = partial(trainer.PolicyNet2, shelter_occupancy=not geometry_study,
                             shelter_geometry=geometry_study)
            options.update(fixed_speed='speed_1', fixed_clock=True, ready_coverage_credit=.30,
                           planning_zone_audit=True, experiment_signal='receipts')
            if geometry_study:
                options['shelter_geometry_input'] = SHELTER_GEOMETRY_BY_ARM[arm]
            else:
                options['shelter_occupancy_input'] = SHELTER_INPUT_BY_ARM[arm]
            if phase == [True]:
                options['planning_tool_temperature'] = PLANNING_TEMPERATURES['planning_exploration']
        if separate_policy_cpus:
            worker = psutil.Process()
            inherited_cpus = worker.cpu_affinity()
            game = psutil.Process(env.pid)
            if len(inherited_cpus) < 4 or game.cpu_affinity() != inherited_cpus:
                raise RuntimeError('Cannot split the inherited game and worker CPU allowance')
            game.cpu_affinity(inherited_cpus[:-2])
            worker.cpu_affinity(inherited_cpus[-2:])
        return trainer.run_episode((env.pid, weights, False, tag, options), policy_factory=policy,
                                   telemetry=observe)
    finally:
        try:
            zar_boot.stop(env)
        finally:
            if inherited_cpus is not None:
                worker.cpu_affinity(inherited_cpus)


def collect_pairs(pool, jobs, directory, *, observe=False, separate_policy_cpus=False, policy_ids=None):
    worker = partial(episode, observe=observe, audit_signal=True)
    if separate_policy_cpus:
        worker = partial(worker, separate_policy_cpus=True)
    def collect(attempt_jobs, attempt):
        identities = [dict(copy=job[0], arm=job[1], policy_seed=job[3], episode=job[4],
                           policy_id=(policy_ids or {}).get(job[1]), attempt=attempt, phase='train' if len(job) > 5 and job[5] else 'evaluation')
                      for job in attempt_jobs]
        with (directory/'attempts.jsonl').open('a', encoding='utf-8') as journal:
            for identity in identities:
                journal.write(json.dumps(dict(identity, status='scheduled'))+'\n')
            journal.flush()
            os.fsync(journal.fileno())
            rows = [None] * len(attempt_jobs)
            futures = {pool.submit(worker, job): index for index, job in enumerate(attempt_jobs)}
            for future in as_completed(futures):
                index = futures[future]
                identity = identities[index]
                try:
                    row = future.result()
                except Exception as error:
                    row = {'err': f'{type(error).__name__}: {error}'}
                journal.write(json.dumps(dict(identity, status='finished', err=row.get('err'),
                                              end=row.get('end'), saved_frac=row.get('saved_frac'),
                                              log_started=row.get('log_started'), win=row.get('win'),
                                              start_kind=row.get('start_kind'),
                                              outbreak_seed=(row.get('outbreak') or {}).get('seed')))+'\n')
                journal.flush()
                os.fsync(journal.fileno())
                rows[index] = row
        return rows

    results = collect(jobs, 0)
    transient = ('Timed out waiting for UI frames', 'Stale native HUD frame',
                 'No consistent HUD observer frame', 'Native map changed during read',
                 'failed at injection: argument 1: OverflowError', 'Timed out waiting for picker closed')
    for start in range(0, len(jobs), 2):
        pair = slice(start, start + 2)
        errors = [r['err'] for r in results[pair] if 'err' in r]
        if errors and all(any(reason in error for reason in transient) for error in errors):
            attempts = [
                dict(copy=job[0], arm=job[1], seed=job[3], tag=job[4],
                     end=row.get('end'), saved_frac=row.get('saved_frac'), err=row.get('err'),
                     log_started=row.get('log_started'),
                     outbreak_seed=(row.get('outbreak') or {}).get('seed'))
                for job, row in zip(jobs[pair], results[pair], strict=True)
            ]
            with (directory/'interface-retries.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(dict(pair=[job[4] for job in jobs[pair]], errors=errors,
                                        original_attempts=attempts))+'\n')
            replacements = collect(jobs[pair], 1)
            prior = [entry['outbreak_seed'] for entry in attempts if type(entry['outbreak_seed']) is int]
            results[pair] = [dict(row, prior_attempt_seeds=prior) for row in replacements] if prior else replacements
    return results


def phase_loss_ledger(observations, *, balanced):
    planning = torch.tensor([bool(obs[trainer.PLANNING_INDEX]) for obs in observations], dtype=torch.bool)
    count = int(planning.sum())
    total = planning.numel()
    if not total:
        share = None
    elif balanced:
        weights = trainer.phase_loss_weights(planning)
        share = float(weights[planning].sum() / weights.sum())
    else:
        share = count / total
    return dict(planning=count, battle=total-count, planning_loss_weight_share=share)


def committed_signal_rows(rows, next_round, copies):
    """Use only training rounds recorded by a completed paired checkpoint."""
    by_round = {}
    for row in rows:
        if row['phase'] == 'train' and row['round'] < next_round and not row.get('err'):
            by_round.setdefault(row['round'], []).append(row)
    return [
        {key: row.get(key) for key in ('round', 'arm', 'phase', 'outbreak_seed', 'start_kind', 'experiment_signal')}
        for batch in by_round.values() if len(batch) == len(copies)
        and {row.get('copy') for row in batch} == set(copies)
        for row in batch
    ]


def previous_outbreak_seeds(analysis):
    """Exclude known Boston L1 outbreaks before launching the experiment."""
    seeds = set()
    for run in analysis.glob('coverage-*'):
        paired = run/'results.jsonl'
        if paired.is_file():
            seeds.update(seed for row in records(paired)
                         if type(seed := row.get('outbreak_seed')) is int)
        attempts = run/'attempts.jsonl'
        if attempts.is_file():
            seeds.update(seed for row in records(attempts) if type(seed := row.get('outbreak_seed')) is int)
        retries = run/'interface-retries.jsonl'
        if retries.is_file():
            seeds.update(seed for row in records(retries) for attempt in row.get('original_attempts', ())
                         if type(seed := attempt.get('outbreak_seed')) is int)
        for name in ('trials.jsonl', 'holdout.jsonl', 'extra-trials.jsonl',
                     'forecast-comparison.jsonl', 'speed-comparison.jsonl'):
            journal = run/name
            if journal.is_file():
                seeds.update(seed for row in records(journal) for level in row.get('levels', ())
                             if level.get('stage') == 1
                             and type(seed := (level.get('outbreak') or {}).get('seed')) is int)
    return seeds


def training_outbreak_seeds(rows):
    return {seed for row in rows if row.get('phase') == 'train'
            for seed in (row.get('outbreak_seed'), *row.get('prior_attempt_seeds', ())) if type(seed) is int}


def physical_attempts(journal):
    """Reconstruct native attempt order from durable scheduling and completion rows."""
    attempts = {}
    for row in records(journal):
        key = row['episode'], row['attempt']
        if row['status'] == 'scheduled':
            if key in attempts:
                raise ValueError(f'Duplicate scheduled attempt {key}')
        elif key not in attempts or attempts[key]['status'] != 'scheduled':
            raise ValueError(f'Completion without one pending attempt {key}')
        attempts[key] = row
    return list(attempts.values())


def heldout_consistency(rows, policy_id, *, discovery_seeds=()):
    """Measure three chronological blocks of fresh complete results for one frozen policy."""
    cohort = [r for r in rows if r['phase']=='evaluation' and r['policy_id']==policy_id][:30]
    training_seeds = training_outbreak_seeds(rows).union(discovery_seeds)
    seen = set(training_seeds)
    means, scores = [], []
    qualifying = incomplete = discovery_overlap = complete = 0
    for start in range(0, len(cohort), 10):
        block = []
        for row in cohort[start:start+10]:
            seen.update(row.get('prior_attempt_seeds', ()))
            outbreak = row.get('outbreak_seed')
            score = row.get('saved_frac')
            discovery_overlap += type(outbreak) is int and outbreak in training_seeds
            valid = (not row.get('err') and row.get('start_kind')=='fresh' and type(outbreak) is int and outbreak not in seen
                     and row.get('end') in ('won', 'lost') and isinstance(score, (int, float))
                     and math.isfinite(score) and 0 <= score <= 1)
            if type(outbreak) is int:
                seen.add(outbreak)
            if valid:
                block.append(score)
                scores.append(score)
                complete += 1
                qualifying += bool(row.get('win') and score >= .35)
            else:
                incomplete += 1
        if len(block)==10:
            means.append(math.fsum(block)/10)
    return dict(attempts=len(cohort), complete=complete, incomplete=incomplete, qualifying=qualifying, block_means=means,
                minimum=min(scores, default=None), mean=math.fsum(scores)/len(scores) if scores else None,
                discovery_overlap=discovery_overlap, passed=len(means)==3 and min(means)>=.35)


def load_warm_start(path, arm):
    with path.open('rb') as stream:
        fingerprint = hashlib.file_digest(stream, 'sha256').hexdigest()
        stream.seek(0)
        snapshot = torch.load(stream, weights_only=True, map_location='cpu')
    if snapshot['config']['schema'] != trainer.checkpoint_schema():
        raise ValueError('Warm-start checkpoint schema differs from the trainer')
    if arm not in snapshot['weights'] or arm not in snapshot['optimizers']:
        raise ValueError(f'Warm-start checkpoint has no weights and optimizer for {arm}')
    seeds = set(snapshot.get('discovery_seeds', ()))
    with path.with_name('results.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            outbreak = json.loads(line).get('outbreak_seed')
            if type(outbreak) is int:
                seeds.add(outbreak)
    return (snapshot['weights'][arm], snapshot['optimizers'][arm], seeds,
            {'arm': arm, 'sha256': fingerprint})


def retain_natural_win(directory, arm, net, optimizer, config, discovery_seeds, rows, best):
    """Keep the exact pre-update actor for the best native win in each private arm."""
    winner = max((row for row in rows if row['arm'] == arm and row['end'] == 'won'
                  and row['win'] is True and row.get('start_kind') == 'fresh'
                  and type(row.get('outbreak_seed')) is int and row.get('saved_frac') is not None),
                 key=lambda row: row['saved_frac'], default=None)
    if winner is None or winner['saved_frac'] <= best:
        return best
    policy = trainer.policy_id(net)
    if policy != winner['policy_id']:
        raise ValueError('Natural win must be saved with its exact actor')
    path = directory / f'{arm}-best-natural.pt'
    temporary = path.with_suffix('.tmp')
    torch.save(dict(config=config, discovery_seeds=sorted(discovery_seeds),
                    weights={arm: net.state_dict()}, optimizers={arm: optimizer.state_dict()},
                    actor_round=winner['round'], policy_id=policy,
                    outcome={key: winner.get(key) for key in ('outbreak_seed', 'saved_frac', 'board_id', 'log_started')}),
               temporary)
    temporary.replace(path)
    return winner['saved_frac']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copies', nargs='+', required=True)
    parser.add_argument('--seed', type=int, default=81251)
    parser.add_argument('--train-rounds', type=int, default=1, help='Use zero to evaluate an exact warm-start actor without updates')
    parser.add_argument('--eval-rounds', type=int, default=2)
    parser.add_argument('--eval-copies', nargs='+', help='Separate owned copies for frozen evaluation')
    source_args = parser.add_mutually_exclusive_group()
    source_args.add_argument('--resume', type=Path, help='Resume both arms from a paired training snapshot')
    source_args.add_argument('--warm-start', nargs=2, metavar=('SNAPSHOT', 'ARM'),
                             help='Start both arms from one private PPO snapshot with its optimizer')
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument('--compare-missile-credit', action='store_true',
                        help='Train two private copies of the same policy with and without the civilian-impact reward')
    comparison.add_argument('--compare-phase-balance', action='store_true',
                            help='Compare existing PPO loss with equal planning and battle loss mass')
    comparison.add_argument('--compare-breach-cost', action='store_true',
                            help='Compare current and triple occupied shelter exposure costs in private PPO')
    comparison.add_argument('--compare-ready-coverage', action='store_true',
                            help='Compare private PPO with and without credit for civilians sheltered at READY')
    comparison.add_argument('--compare-zone-exploration', action='store_true',
                            help='Broaden model-selected safe-zone cells during private training only')
    comparison.add_argument('--compare-planning-exploration', action='store_true',
                            help='Broaden legal tool sampling during private preparation training')
    comparison.add_argument('--compare-ready-delay', action='store_true',
                            help='Compare a small training cost for deferring a legal READY choice')
    comparison.add_argument('--compare-target-settle', action='store_true',
                            help='Wait one UI frame at the model-selected single-click building target before clicking')
    comparison.add_argument('--compare-battle-exploration', action='store_true',
                            help='Broaden legal tool probabilities only when battle abilities can be used')
    comparison.add_argument('--compare-planning-entropy', action='store_true',
                            help='Compare extra planning-tool entropy during PPO at equal rollout temperature')
    comparison.add_argument('--compare-shelter-defense', action='store_true',
                            help='Compare breach costs with broader planning exploration in both training arms')
    comparison.add_argument('--compare-ready-shortfall', action='store_true',
                            help='Compare a capped penalty for low verified civilian shelter coverage at READY')
    comparison.add_argument('--compare-shelter-duration', action='store_true',
                            help='Compare bounded credit for civilians spending time in intact shelters')
    comparison.add_argument('--compare-shelter-input', action='store_true',
                            help='Compare a private policy input for exact civilian shelter occupancy')
    comparison.add_argument('--compare-battle-boundary', action='store_true',
                            help='Compare filtering known out-of-bounds battle targets before sampling')
    comparison.add_argument('--compare-shelter-geometry', action='store_true',
                            help='Compare a private planning input for projected shelter rectangle coverage')
    comparison.add_argument('--compare-opening-timing', action='store_true',
                            help='Compare a private planning input for projected ability timing')
    comparison.add_argument('--compare-recurrent-capacity', action='store_true',
                            help='Compare 128 and warm-expanded 192 recurrent units with identical inputs')
    comparison.add_argument('--compare-preparation-credit', action='store_true',
                            help='Compare native-save preparation targets with shaped episode returns')
    parser.add_argument('--audit-phase-gradients', action='store_true',
                        help='Measure planning and battle gradient alignment on one episode per arm and round')
    parser.add_argument('--observe', action='store_true',
                        help='Publish read-only Observatory decisions at up to 1 Hz per worker')
    parser.add_argument('--separate-policy-cpus', action='store_true',
                        help='Use the last two CPUs of the existing allowance for policy workers')
    args = parser.parse_args()
    copies = args.copies
    if args.train_rounds < 0 or args.eval_rounds < 2 or args.eval_rounds % 2:
        parser.error('Use nonnegative training rounds and an even number of evaluation rounds')
    if args.train_rounds == 0 and not (args.warm_start and args.compare_battle_boundary):
        parser.error('Frozen-only evaluation requires --warm-start and --compare-battle-boundary')
    if len(copies) not in (2, 4, 6, 8) or len(set(copies)) != len(copies):
        parser.error('Use two to eight distinct copies in pairs')
    evaluation_copies = args.eval_copies or copies
    if args.eval_copies and (len(evaluation_copies) not in (2,4,6,8)
            or len(set(evaluation_copies)) != len(evaluation_copies)
            or set(evaluation_copies).intersection(copies)):
        parser.error('Evaluation copies must be distinct, paired and disjoint from training')
    planning_study = (args.compare_planning_exploration or args.compare_planning_entropy
                      or args.compare_battle_exploration or args.compare_target_settle or args.compare_ready_delay)
    coverage_study = (args.compare_ready_coverage or args.compare_zone_exploration
                      or planning_study or args.compare_shelter_defense
                      or args.compare_ready_shortfall or args.compare_shelter_duration
                      or args.compare_shelter_input or args.compare_shelter_geometry
                      or args.compare_battle_boundary or args.compare_opening_timing or args.compare_recurrent_capacity
                      or args.compare_preparation_credit)
    shelter_study = args.compare_breach_cost or coverage_study
    paired_weights = args.compare_missile_credit or args.compare_phase_balance or shelter_study
    if args.warm_start and not paired_weights:
        parser.error('Warm starting requires a comparison with the same network in both arms')
    workers = max(len(copies), len(evaluation_copies))
    with operator.training_lock(operator.LOCK):
        ancestors = [p.pid for p in psutil.Process().parents()]
        for copy in dict.fromkeys(copies + evaluation_copies):
            operator.require_idle(operator.inventory(), copy, os.getpid(), ancestor_pids=ancestors)
            check = operator.preflight(copy)
            if not check['ok']:
                raise RuntimeError(check['errors'])
        operator.limit_resources(workers)
        torch.manual_seed(args.seed)
        baseline = trainer.PolicyNet2()
        discovery_seeds = previous_outbreak_seeds(Path(operator.ROOT, 'analysis'))
        warm_source = None
        if args.warm_start:
            path, arm = args.warm_start
            weights, adam, warm_seeds, warm_source = load_warm_start(Path(path), arm)
            discovery_seeds.update(warm_seeds)
            baseline.load_state_dict(weights)
        else:
            trainer.load_pretrained(baseline, trainer.MODEL)
        if paired_weights and warm_source is None:
            adam = torch.load(trainer.MODEL, weights_only=True)['optimizer']
        if args.compare_shelter_input or args.compare_shelter_geometry or args.compare_opening_timing:
            baseline, adam = extend_private_model(baseline, adam, geometry=args.compare_shelter_geometry,
                                                  opening_timing=args.compare_opening_timing)
        if paired_weights:
            labels = (tuple(PREPARATION_CREDIT_BY_ARM) if args.compare_preparation_credit else
                      tuple(CAPACITY_BY_ARM) if args.compare_recurrent_capacity else
                      tuple(OPENING_TIMING_BY_ARM) if args.compare_opening_timing else
                      tuple(BATTLE_BOUNDARY_BY_ARM) if args.compare_battle_boundary else
                      tuple(SHELTER_GEOMETRY_BY_ARM) if args.compare_shelter_geometry else
                      tuple(SHELTER_INPUT_BY_ARM) if args.compare_shelter_input else
                      tuple(SHELTER_DURATION_RATES) if args.compare_shelter_duration else
                      tuple(READY_SHORTFALL_COSTS) if args.compare_ready_shortfall else
                      tuple(DEFENSE_COSTS) if args.compare_shelter_defense else
                      tuple(READY_DELAY_COSTS) if args.compare_ready_delay else
                      tuple(TARGET_SETTLE) if args.compare_target_settle else
                      tuple(BATTLE_TEMPERATURES) if args.compare_battle_exploration else
                      tuple(PLANNING_ENTROPY_BONUSES) if args.compare_planning_entropy else
                      tuple(PLANNING_TEMPERATURES) if args.compare_planning_exploration else
                      tuple(ZONE_TEMPERATURES) if args.compare_zone_exploration else
                      tuple(READY_CREDITS) if args.compare_ready_coverage else
                      tuple(BREACH_COSTS) if args.compare_breach_cost else
                      ('standard', 'balanced') if args.compare_phase_balance else ('unshaped', 'missile_credit'))
            models = {labels[0]: baseline, labels[1]: deepcopy(baseline)}
        else:
            candidate = SpatialPolicy()
            for name in ('gru', 'hu', 'val'):
                getattr(candidate, name).load_state_dict(getattr(baseline, name).state_dict())
            models = {'dense': baseline, 'shared': candidate}
        optimizers = {arm: torch.optim.Adam(net.parameters(), lr=3e-4) for arm, net in models.items()}
        if paired_weights:
            for opt in optimizers.values():
                opt.load_state_dict(deepcopy(adam))
        if args.compare_recurrent_capacity:
            arm = 'recurrent_wide'
            models[arm], expanded_adam = widen_recurrence(baseline, adam)
            optimizers[arm] = torch.optim.Adam(models[arm].parameters())
            optimizers[arm].load_state_dict(expanded_adam)
        config = dict(seed=args.seed, copies=copies, train_rounds=args.train_rounds,
                      eval_rounds=args.eval_rounds, schema=trainer.checkpoint_schema(
                          shelter_occupancy=args.compare_shelter_input, shelter_geometry=args.compare_shelter_geometry,
                          opening_timing=args.compare_opening_timing),
                      learning=trainer.learning_config())
        rollout_options = {'observe': args.observe}
        if args.separate_policy_cpus:
            rollout_options['separate_policy_cpus'] = True
            config['separate_policy_cpus'] = True
        if args.compare_missile_credit:
            config['comparison'] = 'missile_civilian_credit'
        if args.compare_phase_balance:
            config['comparison'] = 'phase_balance'
            config['fixed_speed'] = 'speed_1'
        if args.eval_copies:
            config['eval_copies'] = evaluation_copies
        if args.compare_breach_cost:
            config.update(comparison='occupied_breach_cost', fixed_speed='speed_2',
                          occupied_breach_cost_by_arm=BREACH_COSTS)
        if args.compare_ready_coverage:
            config.update(comparison='ready_coverage', fixed_speed='speed_2',
                          ready_coverage_credit_by_arm=READY_CREDITS)
        if args.compare_zone_exploration:
            config.update(comparison='zone_exploration', fixed_speed='speed_2',
                          ready_coverage_credit=.30, training_zone_temperature_by_arm=ZONE_TEMPERATURES)
        if args.compare_planning_exploration:
            config.update(comparison='planning_exploration', fixed_speed='speed_2',
                          ready_coverage_credit=.30, training_tool_temperature_by_arm=PLANNING_TEMPERATURES)
        if args.compare_ready_delay:
            config.update(comparison='ready_delay', fixed_speed='speed_2', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          ready_delay_cost_by_arm=READY_DELAY_COSTS)
        if args.compare_target_settle:
            config.update(comparison='target_settle', fixed_speed='speed_2', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          settle_cast_target_by_arm=TARGET_SETTLE)
        if args.compare_battle_exploration:
            config.update(comparison='battle_exploration', fixed_speed='speed_2', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          training_battle_temperature_by_arm=BATTLE_TEMPERATURES)
        if args.compare_planning_entropy:
            config.update(comparison='planning_entropy', fixed_speed='speed_2', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          planning_tool_entropy_bonus_by_arm=PLANNING_ENTROPY_BONUSES)
        if args.compare_shelter_defense:
            config.update(comparison='shelter_defense', fixed_speed='speed_2', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          occupied_breach_cost_by_arm=DEFENSE_COSTS)
        if args.compare_ready_shortfall:
            config.update(comparison='ready_shortfall', fixed_speed='speed_2', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          ready_shortfall_cost_by_arm=READY_SHORTFALL_COSTS,
                          ready_shortfall_target=trainer.READY_COVERAGE_SHORTFALL_TARGET)
        if args.compare_shelter_duration:
            config.update(comparison='shelter_duration', fixed_speed='speed_1', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          shelter_duration_rate_by_arm=SHELTER_DURATION_RATES,
                          shelter_duration_cap=DURATION_CAP, shelter_duration_max_interval=DURATION_MAX_INTERVAL)
        if args.compare_shelter_input:
            config.update(comparison='shelter_input', fixed_speed='speed_1', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          shelter_input_by_arm=SHELTER_INPUT_BY_ARM)
        if args.compare_shelter_geometry:
            config.update(comparison='shelter_geometry', fixed_speed='speed_1', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          shelter_geometry_by_arm=SHELTER_GEOMETRY_BY_ARM)
        if args.compare_battle_boundary:
            config.update(comparison='battle_boundary', fixed_speed='speed_1', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          battle_boundary_by_arm=BATTLE_BOUNDARY_BY_ARM)
        if args.compare_opening_timing:
            config.update(comparison='opening_timing', fixed_speed='speed_1', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          battle_boundary_filter=True, opening_timing_by_arm=OPENING_TIMING_BY_ARM)
        if args.compare_recurrent_capacity:
            config.update(comparison='recurrent_capacity', fixed_speed='speed_1', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          battle_boundary_filter=True, recurrent_width_by_arm=CAPACITY_BY_ARM)
        if args.compare_preparation_credit:
            config.update(comparison='preparation_credit', fixed_speed='speed_1', ready_coverage_credit=.30,
                          training_tool_temperature=PLANNING_TEMPERATURES['planning_exploration'],
                          battle_boundary_filter=True, preparation_credit_by_arm=PREPARATION_CREDIT_BY_ARM,
                          planning_timeout_training_return=trainer.PLANNING_TIMEOUT_RETURN)
        first_round = 0
        prior_signal_rows = []
        source = trainer.policy_id(baseline)
        if warm_source is not None:
            config['warm_source'] = warm_source
        if args.resume:
            snapshot = torch.load(args.resume, weights_only=True)
            if 'warm_source' in snapshot['config']:
                config['warm_source'] = snapshot['config']['warm_source']
            if snapshot['config'] != config or not 0 < snapshot['next_round'] <= args.train_rounds:
                parser.error('Trial configuration differs from the paired snapshot')
            first_round, source = snapshot['next_round'], snapshot['source']
            discovery_seeds.update(snapshot.get('discovery_seeds', ()))
            previous_results = args.resume.with_name('results.jsonl')
            previous_rows = list(records(previous_results)) if previous_results.is_file() else []
            discovery_seeds.update(training_outbreak_seeds(previous_rows))
            prior_signal_rows = snapshot.get('signal_training_rows')
            if prior_signal_rows is None:
                prior_signal_rows = committed_signal_rows(previous_rows, first_round, copies)
            for arm, net in models.items():
                net.load_state_dict(snapshot['weights'][arm])
                optimizers[arm].load_state_dict(snapshot['optimizers'][arm])
        experiment = ('preparation-credit' if args.compare_preparation_credit else
                      'recurrent-capacity' if args.compare_recurrent_capacity else
                      'opening-timing' if args.compare_opening_timing else
                      'battle-boundary' if args.compare_battle_boundary else
                      'shelter-geometry' if args.compare_shelter_geometry else
                      'shelter-input' if args.compare_shelter_input else
                      'shelter-duration' if args.compare_shelter_duration else
                      'ready-shortfall' if args.compare_ready_shortfall else
                      'shelter-defense' if args.compare_shelter_defense else
                      'ready-delay' if args.compare_ready_delay else
                      'target-settle' if args.compare_target_settle else
                      'battle-exploration' if args.compare_battle_exploration else
                      'planning-entropy' if args.compare_planning_entropy else
                      'planning-exploration' if args.compare_planning_exploration else
                      'zone-exploration' if args.compare_zone_exploration else
                      'ready-coverage' if args.compare_ready_coverage else
                      'breach-cost' if args.compare_breach_cost else
                      'phase-balance' if args.compare_phase_balance else
                      'missile-credit' if args.compare_missile_credit else 'spatial')
        tag = 'coverage-' + experiment + '-' + uuid.uuid4().hex[:10]
        directory = Path(operator.ROOT, 'analysis', tag)
        directory.mkdir()
        if not args.train_rounds:
            manifest = dict(config=config, actors={arm: trainer.policy_id(net) for arm, net in models.items()},
                            discovery_seeds=sorted(discovery_seeds))
            (directory/'frozen-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        summaries = []
        best_natural = dict.fromkeys(models, -1.)
        def report_signal():
            journal = directory/'attempts.jsonl'
            native = physical_attempts(journal) if journal.is_file() else []
            evaluation = {}
            for arm, net in models.items():
                actor = trainer.policy_id(net)
                attempts = [row for row in native if row['arm'] == arm and row['phase'] == 'evaluation'
                            and row['policy_id'] == actor]
                result = heldout_consistency(attempts, actor, discovery_seeds=discovery_seeds)
                result['scheduled_native_attempts'] = len(attempts)
                result['finished_native_attempts'] = sum(row['status'] == 'finished' for row in attempts)
                evaluation[arm] = result
            rows = [*prior_signal_rows, *summaries]
            earliest = min((row['round'] for row in rows if row['phase'] == 'train'), default=first_round)
            report = summarize_signal(rows, config, models, evaluation, start_round=earliest)
            temporary = directory/'signal-coverage.tmp'
            temporary.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            temporary.replace(directory/'signal-coverage.json')
            print('experiment signal', report['advisory'], flush=True)
            return evaluation

        print(directory, 'source policy', source, 'starting round', first_round, flush=True)
        with ProcessPoolExecutor(workers) as pool:
            for rnd in range(first_round, args.train_rounds + args.eval_rounds):
                training = rnd < args.train_rounds
                round_copies = copies if training else evaluation_copies
                operator.require_resource_headroom(len(round_copies))
                jobs = []
                for i, copy in enumerate(round_copies):
                    arm = tuple(models)[(i+rnd)%2]
                    jobs.append((copy, arm, models[arm].state_dict(), args.seed+rnd*100+i//2,
                                 f'{tag}/{rnd}/{arm}/{copy}', training))
                start = time.monotonic()
                policies = {arm: trainer.policy_id(net) for arm, net in models.items()}
                try:
                    results = collect_pairs(pool, jobs, directory, policy_ids=policies, **rollout_options)
                except (Exception, KeyboardInterrupt):
                    report_signal()
                    raise
                batch_seconds = time.monotonic() - start
                for job, row in zip(jobs, results):
                    summary = {k: row.get(k) for k in ('end','saved_frac','win','advance','sim','t','err','board_id','timeout_phase','log_started')}
                    summary.update(copy=job[0], arm=job[1], seed=job[3], round=rnd,
                                   phase='train' if training else 'evaluation',
                                   policy_id=policies[job[1]], start_kind=row.get('start_kind'),
                                   outbreak_seed=(row.get('outbreak') or {}).get('seed'),
                                   decisions=len(row.get('obs', [])), batch_seconds=batch_seconds,
                                   experiment_signal=row.get('experiment_signal'), ready_choices=row.get('ready_choices'))
                    if row.get('prior_attempt_seeds'):
                        summary['prior_attempt_seeds'] = row['prior_attempt_seeds']
                    summary['battle_actions'] = dict(Counter(
                        trainer.TOOLS[u] for u, obs in zip(row.get('us', []), row.get('obs', []))
                        if not obs[trainer.PLANNING_INDEX]))
                    if training:
                        summary['phase_loss'] = phase_loss_ledger(row.get('obs', ()), balanced=job[1]=='balanced')
                    if args.compare_missile_credit or args.compare_phase_balance or shelter_study:
                        summary['missile_civilian_losses'] = row.get('battle_actions', {}).get('missile_civilian_losses')
                        summary['missile_civilian_reward'] = row.get('reward_components', {}).get('missile_civilian_loss')
                        summary['legal_cast_tools'] = row.get('battle_actions', {}).get('legal_cast_tools', {})
                        summary['confirmed_spends'] = row.get('battle_actions', {}).get('stock_decreased')
                        summary['cast_receipts'] = row.get('battle_actions', {}).get('cast_receipts')
                        summary['planning_placements_selected'] = row.get('selected_placements', {})
                    if shelter_study or args.compare_phase_balance:
                        summary['planning_actions'] = dict(Counter(
                            trainer.TOOLS[u] for u, obs in zip(row.get('us', []), row.get('obs', []))
                            if obs[trainer.PLANNING_INDEX]))
                        summary['planning_blockers'] = row.get('planning_blockers')
                        summary['shelter'] = row.get('shelter')
                        outbreak = row.get('outbreak') or {}
                        summary['safe_zones_at_ready'] = outbreak.get('safe_zones')
                        summary['sheltered_pct_at_ready'] = outbreak.get('civilians_inside_pct')
                        summary['planning_buildings_paid'] = row.get('paid_buildings', {})
                        summary['ready_stats'] = row.get('ready_stats')
                        battle = row.get('battle_actions', {})
                        for key in ('severe_failure', 'first_outnumbered_sim', 'first_live_at_retry_floor_sim'):
                            summary[key] = battle.get(key)
                        summary['logged_deployments'] = battle.get('logged_deployments')
                        summary['deploy_sim_seconds'] = battle.get('deploy_sim_seconds')
                        summary['zombie_kill_timing'] = battle.get('zombie_kill_timing')
                        summary['occupied_breach_reward'] = row.get('reward_components', {}).get('occupied_breach')
                        summary['occupied_breach_cost'] = (
                            DEFENSE_COSTS.get(job[1], BREACH_COSTS.get(job[1], trainer.BREACH_COST)))
                        if coverage_study:
                            summary['ready_coverage_reward'] = row.get('reward_components', {}).get('ready_coverage')
                    if (args.compare_zone_exploration or planning_study
                            or args.compare_shelter_defense or args.compare_ready_shortfall
                            or args.compare_shelter_duration or args.compare_shelter_input
                            or args.compare_shelter_geometry or args.compare_battle_boundary or args.compare_opening_timing
                            or args.compare_recurrent_capacity or args.compare_preparation_credit):
                        summary['planning_zone_receipts'] = row.get('planning_zone_receipts')
                        summary['shelter_dispatch'] = row.get('shelter_dispatch')
                        for key in ('ready_embedded_defenses', 'ready_preparation', 'ready_loadout',
                                    'first_legal_cast_sim', 'timeout_preparation'):
                            summary[key] = row.get(key)
                    if args.compare_opening_timing:
                        summary['opening_ready_preview'] = row.get('opening_ready_preview')
                    if (args.compare_shelter_geometry or args.compare_battle_boundary
                            or args.compare_opening_timing or args.compare_recurrent_capacity):
                        summary['outside_playarea_targets'] = row.get('outside_targets')
                    if args.compare_zone_exploration:
                        summary['tempered_zone_decisions'] = sum(
                            temp > 1. for temp in row.get('cell_temperatures', ()))
                    if args.compare_ready_shortfall:
                        summary['ready_shortfall_reward'] = row.get('reward_components', {}).get('ready_shortfall')
                    if planning_study or args.compare_shelter_defense or args.compare_ready_shortfall or args.compare_shelter_duration:
                        summary['tempered_planning_decisions'] = sum(
                            temp > 1. and obs[trainer.PLANNING_INDEX] > 0
                            for temp, obs in zip(row.get('tool_temperatures', ()), row.get('obs', ())))
                    with (directory/'results.jsonl').open('a') as f:
                        f.write(json.dumps(summary)+'\n')
                    summaries.append(summary)
                    print(summary, flush=True)
                if any(not trainer.valid_trajectory(row) for row in results):
                    report_signal()
                    raise RuntimeError('Invalid trajectory; see trial results')
                if training:
                    discovery_seeds.update(training_outbreak_seeds(summaries[-len(jobs):]))
                    for arm, net in models.items():
                        np.random.seed(args.seed + rnd)
                        best_natural[arm] = retain_natural_win(
                            directory, arm, net, optimizers[arm], config, discovery_seeds,
                            summaries[-len(round_copies):], best_natural[arm])
                        update = trainer.ppo_update(net, [row for job,row in zip(jobs,results) if job[1]==arm],
                                           optimizers[arm], balance_phases=arm=='balanced',
                                           planning_tool_entropy_bonus=PLANNING_ENTROPY_BONUSES.get(arm, 0.),
                                           audit_phases=args.audit_phase_gradients,
                                           preparation_credit=PREPARATION_CREDIT_BY_ARM.get(arm, False))
                        if args.audit_phase_gradients:
                            with (directory/'phase-gradients.jsonl').open('a') as experiment:
                                experiment.write(json.dumps(dict(round=rnd, arm=arm, source_policy=policies[arm],
                                                                 audit=update['phase_gradients']))+'\n')
                        torch.save(net.state_dict(), directory/(arm+'.pt'))
                    temp = directory/'paired.tmp'
                    torch.save(dict(next_round=rnd+1, source=source, config=config,
                                    discovery_seeds=sorted(discovery_seeds),
                                    signal_training_rows=[*prior_signal_rows, *committed_signal_rows(summaries, rnd+1, copies)],
                                    weights={a:n.state_dict() for a,n in models.items()},
                                    optimizers={a:o.state_dict() for a,o in optimizers.items()}), temp)
                    temp.replace(directory/'paired.pt')
                    report_signal()
                    if (directory/'stop-after-round').is_file():
                        print(f'Paused after atomic checkpoint at next_round={rnd + 1}', flush=True)
                        return
        results = report_signal()
        (directory/'consistency.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
