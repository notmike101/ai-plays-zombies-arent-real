"""Parallel strategy search for ZAR (multiprocessing over game instances).

Genome: 3 battle-bar casts (t, x, y, kind; kind<0.5=Para else AC130), t in
[18,80], plus 6 planning genes: mine field x,y,len (re-dragged every
planning phase; mines are consumed per battle), turret x,y (persists across
retries, paid once), fortify level 0..4 (F-clicks on the south wall segment,
persists). Fitness = civilian frac at t=score_t. CEM over genomes; episodes
per generation are sharded across instances (parallel across pids,
sequential within one pid). After a lost battle the instance returns to
planning via R (retry) inside run_episode.

Usage:
  python parallel_ga.py test --pids 13676,36276
  python parallel_ga.py run  --pids 13676,36276 --gens 4 --pop 6
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np

ROOT = r'D:\zar-scratch'
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

G_LO = np.array([18.0, 500.0, 250.0, 0.0] * 4 + [200.0, 255.0, 40.0,
               200.0, 255.0, 0.0], dtype=np.float32)
G_HI = np.array([80.0, 1300.0, 700.0, 1.0] * 4 + [1200.0, 760.0, 200.0,
               1200.0, 760.0, 4.0], dtype=np.float32)
G0 = np.array([46.5, 742, 415, 0.0, 48.0, 784, 468, 0.0, 49.5, 815, 416,
               0.0, 60.0, 800, 430, 0.5, 740, 560, 120, 905, 340, 0],
              dtype=np.float32)
NF = 22


def policy_from_genome(g):
    casts = []
    keys = ['1', '3', '2', '4', '4']   # para heli gas ac130 ac130
    for i in range(4):
        t, x, y, k = g[4 * i:4 * i + 4]
        key = keys[min(int(k * 5.0), 4)]
        casts.append((float(t), key, int(x), int(y)))
    casts.sort()
    fired = [False] * 4

    def policy(o, t):
        for j, (ct, key, x, y) in enumerate(casts):
            if not fired[j] and t >= ct:
                fired[j] = True
                return ('cast', key, x, y)
        return None
    return policy


def run_episode(args):
    pid, genome, log_tag, *rest = args
    score_t = float(rest[0]) if rest else 10000.0
    import time as _t
    from env_zar import ZAREnv
    try:
        env = ZAREnv(pid)
        g = np.asarray(genome, dtype=np.float32)
        mx, my, mlen = float(g[16]), float(g[17]), float(g[18])
        m_before = env.obs()['money']
        if m_before >= 4200:   # fresh board: mortar barrage on glowing bldgs
            env.auto_garrison(budget_frac=0.25)   # persists on retry
            m_before = env.obs()['money']
        env.mine_field(int(mx), int(my), int(mlen))
        m_mine = env.obs()['money']
        env.turret(int(g[19]), int(g[20]))
        m_tur = env.obs()['money']
        _TAGS = [(663, 258), (594, 287), (663, 336), (938, 368)]
        for _k in range(int(g[21] + 0.5)):
            env.upgrade(*_TAGS[_k % len(_TAGS)])
        m_fort = env.obs()['money']
        env.ready()
        env.vi.key_press(0x74, sc=0x3F)   # F5 = 8x game speed (dev button)
        pol = policy_from_genome(g)
        r = env.battle(pol, max_s=420, stop_frac=0.02, score_t=score_t,
                        auto_heli=3.5)
        r['money'] = [m_before, m_mine, m_tur, m_fort]
        r['plan'] = list(map(float, g[16:22]))
        # let the battle run out to a lose screen so R resets cleanly
        t_end = _t.time() + 240
        while _t.time() < t_end:
            o = env.obs()
            if (o['civ'] or 0) < 5000 and o['zomb'] > 0:
                break
            if o['zomb'] == 0:
                break
            _t.sleep(4)
        o = env.obs()
        if o['zomb'] > 0 and (o['civ'] or 0) < 5000:
            o2 = o
            for _y in range(4):   # R -> dialog -> R(YES); wait for PLANNING
                env.vi.key_press(0x52, sc=19, hold=0.25)
                _t.sleep(4.0)
                o2 = env.obs()
                if o2['zomb'] == 0 and (o2['civ'] or 0) > 90000:
                    break
            # re-lay the mine field on the fresh board (mines were consumed)
            if o2['zomb'] == 0 and (o2['civ'] or 0) > 90000:
                try:
                    env.mine_field(int(mx), int(my), int(mlen))
                except Exception:
                    pass
        with open(os.path.join(ROOT, 'analysis', f'ga_{log_tag}.json'), 'w') as fh:
            json.dump({'pid': pid, 'genome': list(map(float, genome)),
                       'result': r}, fh)
        if r.get('frac') is None or r.get('invalid'):
            return -1.0
        fit = (0.55 * r['frac'] + 0.30 * r['alive_int']
               + 0.06 * min(r['kills'] / 250000.0, 1.0)
               + 0.05 * min((r['police_pk'] or 0) / 3000.0, 1.0)
               + 0.04 * r['spend_frac'])
        return float(fit)
    except Exception as e:
        print(f'[w{pid}] ERR {e}', flush=True)
        return -1.0


def _seq(chunk):
    return [run_episode(j) for j in chunk]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['test', 'run', 'val'])
    ap.add_argument('--pids', required=True)
    ap.add_argument('--score_t', type=float, default=60.0)
    ap.add_argument('--gens', type=int, default=4)
    ap.add_argument('--pop', type=int, default=6)
    a = ap.parse_args()
    pids = [int(p) for p in a.pids.split(',')]

    if a.mode == 'test':
        jobs = [(p, G0, f'test{p}', 60.0) for p in pids]
        with mp.Pool(len(pids)) as pool:
            print('fracs', pool.map(run_episode, jobs), flush=True)
        return

    if a.mode == 'val':
        _d = json.load(open(os.path.join(ROOT, 'analysis', 'ga_hist.json')))
        bg = np.array(_d['best_genome'], dtype=np.float32)
        jobs = [(p, bg, f'val{p}', a.score_t) for p in pids]
        with mp.Pool(len(pids)) as pool:
            print('fracs', pool.map(run_episode, jobs), flush=True)
        return

    rng = np.random.default_rng(7)
    mu = G0.copy()
    bf = os.path.join(ROOT, 'analysis', 'ga_hist.json')
    if os.path.exists(bf):
        try:
            _d = json.load(open(bf))
            if _d.get('best_fit', 0) > 0:
                _bg = np.array(_d['best_genome'], dtype=np.float32)
                mu = (np.concatenate([_bg, G0[len(_bg):NF]])

                      if len(_bg) < NF else _bg)
                print(f"seeded from saved best {_d['best_fit']:.3f}", flush=True)
        except Exception:
            pass
    sigma = (G_HI - G_LO) * 0.18
    hist = []
    best = (0.0, mu.copy())
    for gen in range(a.gens):
        cands = np.clip(rng.normal(mu, sigma, size=(a.pop, NF)), G_LO, G_HI)
        per = [[] for _ in pids]
        for i in range(a.pop):
            per[i % len(pids)].append((pids[i % len(pids)], cands[i], f'g{gen}e{i}'))
        with mp.Pool(len([c for c in per if c])) as pool:
            shards = pool.starmap(_seq, [(c,) for c in per if c])
        results = [results for shard in zip(*shards) for results in shard]
        # NOTE: zip(*shards) interleaves; fits map back to cand index by round-robin
        order_fit = []
        for i in range(a.pop):
            p_i = i % len(pids)
            k = i // len(pids)
            order_fit.append(shards[p_i][k])
        for c, f in zip(cands, order_fit):
            hist.append({'gen': gen, 'genome': list(map(float, c)), 'fit': f})
            if f > best[0]:
                best = (f, c.copy())
        good = [i for i, f in enumerate(order_fit) if f >= 0]
        if len(good) >= 3:
            top = sorted(good, key=lambda i: -order_fit[i])[:max(2, a.pop // 3)]
            elites = cands[top]
            mu = elites.mean(0)
            sigma = np.maximum(elites.std(0), (G_HI - G_LO) * 0.04)
        with open(os.path.join(ROOT, 'analysis', 'ga_hist.json'), 'w') as fh:
            json.dump({'hist': hist, 'best_fit': best[0],
                       'best_genome': list(map(float, best[1]))}, fh)
        print(f'gen {gen}: fits {[round(f, 3) for f in order_fit]} best {best[0]:.3f} '
              f'mu {np.round(mu, 1).tolist()}', flush=True)


if __name__ == '__main__':
    main()
