"""Training session launcher: boot owned copies to planning, run nn_play2,
clean up every game it owned. Screenshot-free; failures still clean up.

Usage: python -B scripts/train_run.py --copies inst1 inst2 --eps 2 --rounds 14 \
           [--random] [--log analysis/nn2_run_x.log]
Boards are fresh L1 (zar_boot stage1). To train on already-planning pids use
--pids directly (then this script does NOT own/clean them).
"""
import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zar_boot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--copies', nargs='*', default=[])
    ap.add_argument('--pids', default='')
    ap.add_argument('--eps', type=int, default=2)
    ap.add_argument('--rounds', type=int, default=6)
    ap.add_argument('--random', action='store_true')
    ap.add_argument('--mode', choices=['train', 'play'], default='train')
    ap.add_argument('--start', choices=['fresh', 'continue'], default='fresh')
    ap.add_argument('--model', default=os.path.join(ROOT, 'sessions', 'nn_policy4.pt'))
    ap.add_argument('--history', default=os.path.join(ROOT, 'analysis', 'nn_hist4.jsonl'))
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--plan-steps', type=int, default=60)
    ap.add_argument('--battle-seconds', type=float, default=560.)
    ap.add_argument('--log', default='')
    a = ap.parse_args()
    if not a.copies and not a.pids:
        ap.error('give --copies and/or --pids')

    envs, owns = [], []
    rc = 1
    try:
        if a.copies:
            with ThreadPoolExecutor(max_workers=len(a.copies)) as pool:
                futs = {pool.submit(zar_boot.boot,
                                    zar_boot.COPIES / c, ('campaign', 'stage1' if a.start == 'fresh' else 'continue')): c for c in a.copies}
                for fut in as_completed(futs):
                    c = futs[fut]
                    try:
                        envs.append(fut.result())
                        print(f'PASS boot {c} pid={envs[-1].pid}', flush=True)
                    except Exception as e:
                        print(f'FAIL boot {c}: {e}', flush=True)
            if not envs:
                print('no boards booted; aborting', flush=True)
                return 2
            time.sleep(2)
            for env in envs:                       # planning barrier
                if env.phase_now() != 'planning':
                    print(f'FAIL barrier pid {env.pid} not planning', flush=True)
                    return 2
            owns += [env.pid for env in envs]
        pids = [str(p) for p in owns] + [p for p in a.pids.split(',') if p]
        cmd = [sys.executable, '-B',
               os.path.join(ROOT, 'scripts', 'nn_play2.py'), a.mode,
               '--pids', ','.join(pids), '--eps', str(a.eps),
               '--rounds', str(a.rounds), '--model', a.model, '--history', a.history,
               '--seed', str(a.seed), '--plan-steps', str(a.plan_steps),
               '--battle-seconds', str(a.battle_seconds)]
        if owns and a.start == 'fresh':
            cmd += ['--fresh-pids', ','.join(map(str, owns))]
        if a.random:
            cmd.append('--random')
        log = a.log or os.path.join(ROOT, 'analysis',
                                    time.strftime('nn3_run_%Y%m%d-%H%M%S.log'))
        print('RUN', ' '.join(cmd), '->', log, flush=True)
        t0 = time.time()
        with open(log, 'w') as fh:
            fh.write('# ' + ' '.join(cmd) + '\n')
            fh.flush()
            rc = subprocess.call(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                 cwd=os.path.join(ROOT, 'scripts'))
        print(f'trainer rc={rc} in {time.time()-t0:.0f}s; log {log}', flush=True)
    finally:
        for env in envs:
            try:
                zar_boot.stop(env)
                print(f'stopped pid {env.pid}', flush=True)
            except Exception as e:
                print(f'FAIL stop pid {env.pid}: {e}', flush=True)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
