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
from concurrent.futures import ProcessPoolExecutor
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
PLANNING_ENTROPY_BONUSES = {'entropy_baseline': 0., 'planning_entropy': .045}
DEFENSE_COSTS = {'defense_baseline': trainer.BREACH_COST,
                 'defense_stronger': 3 * trainer.BREACH_COST}
READY_SHORTFALL_COSTS = {'shortfall_baseline': 0., 'shortfall_penalty': .15}


def episode(job, *, observe=False, audit_signal=False):
    copy, arm, weights, seed, tag, *phase = job
    battle_study = arm in BATTLE_TEMPERATURES
    planning_study = arm in PLANNING_TEMPERATURES or arm in PLANNING_ENTROPY_BONUSES or battle_study
    try:
        copy_dir = operator.owned_copy(copy)
        env = None
        if (arm in BREACH_COSTS or arm in READY_CREDITS or arm in ZONE_TEMPERATURES
                or planning_study or arm in DEFENSE_COSTS or arm in READY_SHORTFALL_COSTS):
            try:
                env = zar_boot.boot(copy_dir, welcome_wait=15, discard_dump_states=True)
            except ZAREnvError as exc:
                print(f'{copy} fast boot failed: {exc}. Retrying with standard warmup.', flush=True)
        if env is None:
            env = zar_boot.boot(copy_dir, discard_dump_states=True)
    except ZAREnvError as exc:
        return {'err': str(exc)}
    try:
        policy = SpatialPolicy if arm == 'shared' else trainer.PolicyNet2
        options = dict(start_kind='fresh', seed=seed, missile_credit=arm!='unshaped')
        if observe:
            options['observer_interval'] = 1.
        if battle_study or audit_signal:
            options['experiment_signal'] = ('battle_tools' if battle_study else
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
        return trainer.run_episode((env.pid, weights, False, tag, options), policy_factory=policy,
                                   telemetry=observe)
    finally:
        zar_boot.stop(env)


def collect_pairs(pool, jobs, directory, *, observe=False):
    worker = partial(episode, observe=observe, audit_signal=True)
    results = list(pool.map(worker, jobs))
    transient = ('Timed out waiting for UI frames', 'Stale native HUD frame',
                 'No consistent HUD observer frame', 'Native map changed during read',
                 'failed at injection: argument 1: OverflowError', 'Timed out waiting for picker closed')
    for start in range(0, len(jobs), 2):
        pair = slice(start, start + 2)
        errors = [r['err'] for r in results[pair] if 'err' in r]
        if errors and all(any(reason in error for reason in transient) for error in errors):
            with (directory/'interface-retries.jsonl').open('a') as f:
                f.write(json.dumps(dict(pair=[job[4] for job in jobs[pair]], errors=errors))+'\n')
            results[pair] = list(pool.map(worker, jobs[pair]))
    return results


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
            and type(seed := row.get('outbreak_seed')) is int}


def heldout_consistency(rows, policy_id, *, discovery_seeds=()):
    """Measure three chronological blocks of fresh complete results for one frozen policy."""
    cohort = [r for r in rows if r['phase']=='evaluation' and r['policy_id']==policy_id][:30]
    training_seeds = training_outbreak_seeds(rows).union(discovery_seeds)
    seen = set(training_seeds)
    means = []
    qualifying = incomplete = discovery_overlap = complete = 0
    for start in range(0, len(cohort), 10):
        block = []
        for row in cohort[start:start+10]:
            outbreak = row.get('outbreak_seed')
            score = row.get('saved_frac')
            discovery_overlap += type(outbreak) is int and outbreak in training_seeds
            valid = (row.get('start_kind')=='fresh' and type(outbreak) is int and outbreak not in seen
                     and row.get('end') in ('won', 'lost') and isinstance(score, (int, float))
                     and math.isfinite(score) and 0 <= score <= 1)
            if type(outbreak) is int:
                seen.add(outbreak)
            if valid:
                block.append(score)
                complete += 1
                qualifying += bool(row.get('win') and score >= .35)
            else:
                incomplete += 1
        if len(block)==10:
            means.append(math.fsum(block)/10)
    return dict(attempts=len(cohort), complete=complete, incomplete=incomplete, qualifying=qualifying, block_means=means,
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
    seeds = set(snapshot['discovery_seeds'])
    with path.with_name('results.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            outbreak = json.loads(line).get('outbreak_seed')
            if type(outbreak) is int:
                seeds.add(outbreak)
    return (snapshot['weights'][arm], snapshot['optimizers'][arm], seeds,
            {'arm': arm, 'sha256': fingerprint})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copies', nargs='+', required=True)
    parser.add_argument('--seed', type=int, default=81251)
    parser.add_argument('--train-rounds', type=int, default=1)
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
    comparison.add_argument('--compare-battle-exploration', action='store_true',
                            help='Broaden legal tool probabilities only when battle abilities can be used')
    comparison.add_argument('--compare-planning-entropy', action='store_true',
                            help='Compare extra planning-tool entropy during PPO at equal rollout temperature')
    comparison.add_argument('--compare-shelter-defense', action='store_true',
                            help='Compare breach costs with broader planning exploration in both training arms')
    comparison.add_argument('--compare-ready-shortfall', action='store_true',
                            help='Compare a capped penalty for low verified civilian shelter coverage at READY')
    parser.add_argument('--observe', action='store_true',
                        help='Publish read-only Observatory decisions at up to 1 Hz per worker')
    args = parser.parse_args()
    copies = args.copies
    if args.train_rounds < 1 or args.eval_rounds < 2 or args.eval_rounds % 2:
        parser.error('Use positive training rounds and an even number of evaluation rounds')
    if len(copies) not in (2, 4, 6, 8) or len(set(copies)) != len(copies):
        parser.error('Use two to eight distinct copies in pairs')
    evaluation_copies = args.eval_copies or copies
    if args.eval_copies and (len(evaluation_copies) not in (2,4,6,8)
            or len(set(evaluation_copies)) != len(evaluation_copies)
            or set(evaluation_copies).intersection(copies)):
        parser.error('Evaluation copies must be distinct, paired and disjoint from training')
    planning_study = (args.compare_planning_exploration or args.compare_planning_entropy
                      or args.compare_battle_exploration)
    coverage_study = (args.compare_ready_coverage or args.compare_zone_exploration
                      or planning_study or args.compare_shelter_defense
                      or args.compare_ready_shortfall)
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
        if paired_weights:
            labels = (tuple(READY_SHORTFALL_COSTS) if args.compare_ready_shortfall else
                      tuple(DEFENSE_COSTS) if args.compare_shelter_defense else
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
            if warm_source is None:
                adam = torch.load(trainer.MODEL, weights_only=True)['optimizer']
            for opt in optimizers.values():
                opt.load_state_dict(deepcopy(adam))
        config = dict(seed=args.seed, copies=copies, train_rounds=args.train_rounds,
                      eval_rounds=args.eval_rounds, schema=trainer.checkpoint_schema(),
                      learning=trainer.learning_config())
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
        experiment = ('ready-shortfall' if args.compare_ready_shortfall else
                      'shelter-defense' if args.compare_shelter_defense else
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
        summaries = []
        def report_signal():
            evaluation = {arm: heldout_consistency(
                [row for row in summaries if row['arm'] == arm], trainer.policy_id(net),
                discovery_seeds=discovery_seeds) for arm, net in models.items()}
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
                results = collect_pairs(pool, jobs, directory, observe=args.observe)
                batch_seconds = time.monotonic() - start
                policies = {arm: trainer.policy_id(net) for arm, net in models.items()}
                for job, row in zip(jobs, results):
                    summary = {k: row.get(k) for k in ('end','saved_frac','win','advance','sim','t','err','board_id','timeout_phase','log_started')}
                    summary.update(copy=job[0], arm=job[1], seed=job[3], round=rnd,
                                   phase='train' if training else 'evaluation',
                                   policy_id=policies[job[1]], start_kind=row.get('start_kind'),
                                   outbreak_seed=(row.get('outbreak') or {}).get('seed'),
                                   decisions=len(row.get('obs', [])), batch_seconds=batch_seconds,
                                   experiment_signal=row.get('experiment_signal'))
                    summary['battle_actions'] = dict(Counter(
                        trainer.TOOLS[u] for u, obs in zip(row.get('us', []), row.get('obs', []))
                        if not obs[trainer.PLANNING_INDEX]))
                    if args.compare_missile_credit or args.compare_phase_balance or shelter_study:
                        summary['missile_civilian_losses'] = row.get('battle_actions', {}).get('missile_civilian_losses')
                        summary['missile_civilian_reward'] = row.get('reward_components', {}).get('missile_civilian_loss')
                        summary['legal_cast_tools'] = row.get('battle_actions', {}).get('legal_cast_tools', {})
                        summary['confirmed_spends'] = row.get('battle_actions', {}).get('stock_decreased')
                        summary['cast_receipts'] = row.get('battle_actions', {}).get('cast_receipts')
                        summary['planning_placements_selected'] = row.get('selected_placements', {})
                    if shelter_study:
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
                            or args.compare_shelter_defense or args.compare_ready_shortfall):
                        summary['planning_zone_receipts'] = row.get('planning_zone_receipts')
                        for key in ('ready_embedded_defenses', 'ready_preparation', 'ready_loadout',
                                    'first_legal_cast_sim'):
                            summary[key] = row.get(key)
                    if args.compare_zone_exploration:
                        summary['tempered_zone_decisions'] = sum(
                            temp > 1. for temp in row.get('cell_temperatures', ()))
                    if args.compare_ready_shortfall:
                        summary['ready_shortfall_reward'] = row.get('reward_components', {}).get('ready_shortfall')
                    if planning_study or args.compare_shelter_defense or args.compare_ready_shortfall:
                        summary['tempered_planning_decisions'] = sum(
                            temp > 1. and obs[trainer.PLANNING_INDEX] > 0
                            for temp, obs in zip(row.get('tool_temperatures', ()), row.get('obs', ())))
                    with (directory/'results.jsonl').open('a') as f:
                        f.write(json.dumps(summary)+'\n')
                    summaries.append(summary)
                    print(summary, flush=True)
                if any(not trainer.valid_trajectory(row) for row in results):
                    raise RuntimeError('Invalid trajectory; see trial results')
                if training:
                    discovery_seeds.update(training_outbreak_seeds(summaries[-len(jobs):]))
                    for arm, net in models.items():
                        np.random.seed(args.seed + rnd)
                        trainer.ppo_update(net, [row for job,row in zip(jobs,results) if job[1]==arm],
                                           optimizers[arm], balance_phases=arm=='balanced',
                                           planning_tool_entropy_bonus=PLANNING_ENTROPY_BONUSES.get(arm, 0.))
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
