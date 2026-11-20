"""Guarded fresh-board PPO comparison. Production weights are read-only."""
import argparse
import json
import math
import os
import time
import uuid
from collections import Counter
from copy import deepcopy
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


def episode(job):
    copy, arm, weights, seed, tag = job
    try:
        env = zar_boot.boot(operator.owned_copy(copy), discard_dump_states=True)
    except ZAREnvError as exc:
        return {'err': str(exc)}
    try:
        policy = SpatialPolicy if arm == 'shared' else trainer.PolicyNet2
        options = dict(start_kind='fresh', seed=seed, missile_credit=arm!='unshaped')
        if arm in ('standard', 'balanced'):
            options.update(fixed_speed='speed_1', fixed_clock=True)
        return trainer.run_episode((env.pid, weights, False, tag, options), policy_factory=policy,
                                   telemetry=False)
    finally:
        zar_boot.stop(env)


def collect_pairs(pool, jobs, directory):
    results = list(pool.map(episode, jobs))
    for start in range(0, len(jobs), 2):
        pair = slice(start, start + 2)
        errors = [r['err'] for r in results[pair] if 'err' in r]
        transient = ('Timed out waiting for UI frames', 'Stale native HUD frame',
                     'No consistent HUD observer frame', 'failed at injection: argument 1: OverflowError')
        if errors and all(any(reason in error for reason in transient) for error in errors):
            with (directory/'interface-retries.jsonl').open('a') as f:
                f.write(json.dumps(dict(pair=[job[4] for job in jobs[pair]], errors=errors))+'\n')
            results[pair] = list(pool.map(episode, jobs[pair]))
    return results


def heldout_consistency(rows, policy_id):
    """Measure three chronological blocks of fresh complete results for one frozen policy."""
    cohort = [r for r in rows if r['phase']=='evaluation' and r['policy_id']==policy_id][:30]
    seen = set()
    means = []
    qualifying = incomplete = 0
    for start in range(0, len(cohort), 10):
        block = []
        for row in cohort[start:start+10]:
            outbreak = row.get('outbreak_seed')
            score = row.get('saved_frac')
            valid = (row.get('start_kind')=='fresh' and type(outbreak) is int and outbreak not in seen
                     and row.get('end') in ('won', 'lost') and isinstance(score, (int, float))
                     and math.isfinite(score) and 0 <= score <= 1)
            if type(outbreak) is int:
                seen.add(outbreak)
            if valid:
                block.append(score)
                qualifying += bool(row.get('win') and score >= .35)
            else:
                incomplete += 1
        if len(block)==10:
            means.append(math.fsum(block)/10)
    return dict(attempts=len(cohort), incomplete=incomplete, qualifying=qualifying, block_means=means,
                passed=len(means)==3 and min(means)>=.35)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copies', nargs='+', required=True)
    parser.add_argument('--seed', type=int, default=81251)
    parser.add_argument('--train-rounds', type=int, default=1)
    parser.add_argument('--eval-rounds', type=int, default=2)
    parser.add_argument('--resume', type=Path, help='Resume both arms from a paired training snapshot')
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument('--compare-missile-credit', action='store_true',
                        help='Train two private copies of the same policy with and without the civilian-impact reward')
    comparison.add_argument('--compare-phase-balance', action='store_true',
                            help='Compare existing PPO loss with equal planning and battle loss mass')
    args = parser.parse_args()
    copies = args.copies
    if args.train_rounds < 1 or args.eval_rounds < 2 or args.eval_rounds % 2:
        parser.error('Use positive training rounds and an even number of evaluation rounds')
    if len(copies) not in (2, 4, 6, 8) or len(set(copies)) != len(copies):
        parser.error('Use two to eight distinct copies in pairs')
    with operator.training_lock(operator.LOCK):
        ancestors = [p.pid for p in psutil.Process().parents()]
        for copy in copies:
            operator.require_idle(operator.inventory(), copy, os.getpid(), ancestor_pids=ancestors)
            check = operator.preflight(copy)
            if not check['ok']:
                raise RuntimeError(check['errors'])
        operator.limit_resources(len(copies))
        torch.manual_seed(args.seed)
        baseline = trainer.PolicyNet2()
        trainer.load_pretrained(baseline, trainer.MODEL)
        if args.compare_missile_credit or args.compare_phase_balance:
            labels = ('standard', 'balanced') if args.compare_phase_balance else ('unshaped', 'missile_credit')
            models = {labels[0]: baseline, labels[1]: deepcopy(baseline)}
        else:
            candidate = SpatialPolicy()
            for name in ('gru', 'hu', 'val'):
                getattr(candidate, name).load_state_dict(getattr(baseline, name).state_dict())
            models = {'dense': baseline, 'shared': candidate}
        optimizers = {arm: torch.optim.Adam(net.parameters(), lr=3e-4) for arm, net in models.items()}
        if args.compare_missile_credit or args.compare_phase_balance:
            checkpoint = torch.load(trainer.MODEL, weights_only=True)
            for opt in optimizers.values():
                opt.load_state_dict(deepcopy(checkpoint['optimizer']))
        config = dict(seed=args.seed, copies=copies, train_rounds=args.train_rounds,
                      eval_rounds=args.eval_rounds, schema=trainer.checkpoint_schema(),
                      learning=trainer.learning_config())
        if args.compare_missile_credit:
            config['comparison'] = 'missile_civilian_credit'
        if args.compare_phase_balance:
            config['comparison'] = 'phase_balance'
            config['fixed_speed'] = 'speed_1'
        first_round = 0
        source = trainer.policy_id(baseline)
        if args.resume:
            snapshot = torch.load(args.resume, weights_only=True)
            if snapshot['config'] != config or not 0 < snapshot['next_round'] <= args.train_rounds:
                parser.error('Trial configuration differs from the paired snapshot')
            first_round, source = snapshot['next_round'], snapshot['source']
            for arm, net in models.items():
                net.load_state_dict(snapshot['weights'][arm])
                optimizers[arm].load_state_dict(snapshot['optimizers'][arm])
        experiment = 'phase-balance' if args.compare_phase_balance else (
            'missile-credit' if args.compare_missile_credit else 'spatial')
        tag = 'coverage-' + experiment + '-' + uuid.uuid4().hex[:10]
        directory = Path(operator.ROOT, 'analysis', tag)
        directory.mkdir()
        summaries = []
        print(directory, 'source policy', source, 'starting round', first_round, flush=True)
        with ProcessPoolExecutor(len(copies)) as pool:
            for rnd in range(first_round, args.train_rounds + args.eval_rounds):
                training = rnd < args.train_rounds
                jobs = []
                for i, copy in enumerate(copies):
                    arm = tuple(models)[(i+rnd)%2]
                    jobs.append((copy, arm, models[arm].state_dict(), args.seed+rnd*100+i//2,
                                 f'{tag}/{rnd}/{arm}/{copy}'))
                start = time.monotonic()
                results = collect_pairs(pool, jobs, directory)
                batch_seconds = time.monotonic() - start
                policies = {arm: trainer.policy_id(net) for arm, net in models.items()}
                for job, row in zip(jobs, results):
                    summary = {k: row.get(k) for k in ('end','saved_frac','win','advance','sim','t','err','board_id','timeout_phase','log_started')}
                    summary.update(copy=job[0], arm=job[1], seed=job[3], round=rnd,
                                   phase='train' if training else 'evaluation',
                                   policy_id=policies[job[1]], start_kind=row.get('start_kind'),
                                   outbreak_seed=(row.get('outbreak') or {}).get('seed'),
                                   decisions=len(row.get('obs', [])), batch_seconds=batch_seconds)
                    summary['battle_actions'] = dict(Counter(
                        trainer.TOOLS[u] for u, obs in zip(row.get('us', []), row.get('obs', []))
                        if not obs[trainer.PLANNING_INDEX]))
                    if args.compare_missile_credit or args.compare_phase_balance:
                        summary['missile_civilian_losses'] = row.get('battle_actions', {}).get('missile_civilian_losses')
                        summary['missile_civilian_reward'] = row.get('reward_components', {}).get('missile_civilian_loss')
                        summary['legal_cast_tools'] = row.get('battle_actions', {}).get('legal_cast_tools', {})
                        summary['confirmed_spends'] = row.get('battle_actions', {}).get('stock_decreased')
                        summary['planning_placements_selected'] = row.get('selected_placements', {})
                    with (directory/'results.jsonl').open('a') as f:
                        f.write(json.dumps(summary)+'\n')
                    summaries.append(summary)
                    print(summary, flush=True)
                if any(not trainer.valid_trajectory(row) for row in results):
                    raise RuntimeError('Invalid trajectory; see trial results')
                if training:
                    for arm, net in models.items():
                        np.random.seed(args.seed + rnd)
                        trainer.ppo_update(net, [row for job,row in zip(jobs,results) if job[1]==arm],
                                           optimizers[arm], balance_phases=arm=='balanced')
                        torch.save(net.state_dict(), directory/(arm+'.pt'))
                    temp = directory/'paired.tmp'
                    torch.save(dict(next_round=rnd+1, source=source, config=config,
                                    weights={a:n.state_dict() for a,n in models.items()},
                                    optimizers={a:o.state_dict() for a,o in optimizers.items()}), temp)
                    temp.replace(directory/'paired.pt')
        results = {arm: heldout_consistency([row for row in summaries if row['arm']==arm],
                                           trainer.policy_id(net))
                   for arm, net in models.items()}
        (directory/'consistency.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
