"""Neural ZAR player: GRU policy trained with PPO across parallel game copies.

Curriculum: boards sit on whatever resume_stage their progress file says
(L1 first -> CONTINUE chain escalates on wins). Battle-phase RL with the full
SP-deck action space; planning (money mortars) stays scripted.

Obs (18): log1p civ/zomb/converting/corpses/police, money/1000, t/300, frac,
zombie trend, civ slope, charges para/heli-spawned/gas/ac130,
hot-spot blob x/y/density (combat centroid from screenshot), prev unit/cell.
Actions (49): 0 wait | unit u in {para(1), heli(2), gas(3), AC130(4)} x 12
grid cells (4x3 over the play island, client PHYSICAL px).

Usage:
  python nn_play.py play  --pids A,B,C [--eps 2] [--rounds 6] [--random]
  python nn_play.py greedy --pid A
"""
import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.set_num_threads(2)

ROOT = r'D:\zar-scratch'
MODEL = os.path.join(ROOT, 'sessions', 'nn_policy.pt')
HIST = os.path.join(ROOT, 'analysis', 'nn_hist.jsonl')
NOBS, NA, HID = 19, 49, 128
UNITS = [('1', 'para', 1), ('2', 'heli', 1), ('3', 'gas', 1), ('4', 'ac130', 3)]
XS = [500, 767, 1033, 1300]
YS = [260, 500, 740]
CELLS = [(x, y) for y in YS for x in XS]          # 12 cells


def cell_of(i):
    return CELLS[i % 12]


class PolicyNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(NOBS, HID, 1, batch_first=True)
        self.pol = nn.Linear(HID, NA)
        self.val = nn.Linear(HID, 1)

    def forward(self, x, h=None):
        out, h = self.gru(x, h)
        return self.pol(out), self.val(out).squeeze(-1), h


def make_obs(st, o, frac, trend, slope, blob, prev):
    g = lambda v: math.log1p(max(v or 0, 0))
    ch = st['charges']
    return [g(o['civ']), g(o['zomb']), g(o['converting']), g(o['corpses']),
            g(o['police']), (o['money'] or 0) / 1000.0, min(st['t'] / 300.0, 2),
            frac, max(-3, min(3, trend / 1000.0)), max(-1, min(1, slope)),
            float(ch['para']), float(st['heli_up']), float(ch['gas']),
            ch['ac130'] / 3.0,
            -1 if blob is None else blob[0] / 1920.0,
            -1 if blob is None else blob[1] / 1200.0,
            -1.0 if blob is None else min(blob[2] / 4000.0, 1.0),
            float(prev[0]), float(prev[1])]


def run_episode(args):
    pid, sd, eps_rand, level_tag = args
    from env_zar import ZAREnv
    try:
        env = ZAREnv(pid)
        env.ready()                      # R-loops to PLANNING then SPACE
        m = env.obs()['money'] or 0
        if m >= 2900:                   # fresh board (any level): mortars
            env.auto_garrison(budget_frac=0.25)
        env.vi.key_press(0x74, sc=0x3F)  # F5 = 8x
        o0 = env.obs()
        civ0 = o0['civ'] or 1
        st = {'t': 0.0, 'charges': {'para': 1, 'gas': 1, 'ac130': 3},
              'heli_up': 0.0}
        net = None
        if not eps_rand:
            net = PolicyNet()
            net.load_state_dict(sd)
            net.eval()
        h = None
        obs, acts, logps, rews, masks = [], [], [], [], []
        prev_o, prev_f = o0, 1.0
        trend, slope = 0.0, 0.0
        prev = (0.0, 0.0)
        last = time.time()
        t0 = time.time()
        win = False
        fought = o0['zomb'] > 0
        while True:
            t = time.time() - t0
            st['t'] = t
            o = env.poll()
            dt = max(time.time() - last, 1e-6)
            last = time.time()
            trend = 0.7 * trend + 0.3 * ((o['zomb'] or 0) -
                                         (prev_o['zomb'] or 0)) / dt
            slope = ((o['civ'] or 0) - (prev_o['civ'] or 0)) / \
                max(dt * max(civ0, 1), 1e-6)
            prev_o, prev_f = o, o['civ'] / civ0 if o['civ'] else 0
            frac = (o['civ'] or 0) / civ0
            blob = env.hot_spot() if o['zomb'] else None
            f = make_obs(st, o, frac, trend, slope,
                         (blob[0], blob[1], 2000) if blob else None, prev)
            mask = np.ones(NA, dtype=np.float32)
            for u in range(4):
                avail = (st['heli_up'] if UNITS[u][1] == 'heli'
                         else st['charges'][UNITS[u][1]])
                if avail <= 0:
                    mask[1 + u * 12:1 + (u + 1) * 12] = 0
            obs.append(f)
            masks.append(mask)
            x = torch.tensor([f], dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                if net is None:
                    legal = np.flatnonzero(mask > 0)
                    a = int(np.random.choice(legal))
                    lp = float(np.log(1.0 / max(len(legal), 1)))
                else:
                    logits, v, h = net(x, h)
                    logits = logits.squeeze(0).clone()
                    logits.masked_fill_(torch.tensor(mask == 0), -1e9)
                    dist = torch.distributions.Categorical(logits=logits)
                    a = int(dist.sample())
                    lp = float(dist.log_prob(torch.tensor(a)))
                    h = h.detach()
            acts.append(a)
            logps.append(lp)
            if 'f_hist' not in st:
                st['f_hist'] = [1.0]
            r = 8.0 * (frac - st['f_hist'][-1]) - (0.02 if a else 0.0)
            st['f_hist'].append(frac)
            rews.append(r)
            # execute
            if a:
                u = (a - 1) // 12
                key, name, _ = UNITS[u]
                cx, cy = cell_of(a - 1)
                if name == 'heli':
                    env.cast(key, cx, cy)
                    st['heli_up'] = 1.0
                    st['charges']['heli'] = 0
                else:
                    if st['charges'][name] > 0:
                        env.cast(key, cx, cy)
                        st['charges'][name] -= 1
                prev = (u + 1, (a - 1) % 12 + 1)
            else:
                prev = (0.0, 0.0)
            if o['zomb'] > 0:
                fought = True
            if o['zomb'] == 0 and t > 25 and fought:
                win = True
                break
            if frac <= 0.02 and fought:
                break
            if t > 560:
                break
            time.sleep(max(2.5 - (time.time() - t0 - t), 0.3))
        R_final = (3.0 if win else 0.0) + 5.0 * frac ** 1.5
        if rews:
            rews[-1] += R_final
        if not win and frac < 0.05:
            try:
                from harness import grab
                grab(env.hwnd).save(r'D:\zar-scratch\analysis\epfail_%d.png'
                                    % pid)
            except Exception:
                pass
        # win screen: log + try CONTINUE (ENTER) to climb the curriculum
        if win:
            from harness import grab
            try:
                grab(env.hwnd).save(os.path.join(
                    ROOT, 'analysis', f'win_{pid}.png'))
            except Exception:
                pass
            env.vi.key_press(0x0D, sc=28)
            time.sleep(6)
        return dict(level=level_tag, pid=pid, win=bool(win), frac=float(frac),
                    t=t, obs=obs, acts=acts, logps=logps, rews=rews,
                    masks=masks, R=float(sum(rews)))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return dict(level=level_tag, pid=pid, err=str(e))


def gae(rews, vals, lam=0.95, gamma=0.99):
    T = len(rews)
    adv = [0.0] * T
    lastg = 0.0
    for i in reversed(range(T)):
        nv = vals[i + 1] if i + 1 < T else 0.0
        delta = rews[i] + gamma * nv - vals[i]
        lastg = delta + gamma * lam * lastg
        adv[i] = lastg
    rets = [0.0] * T
    run = 0.0
    for i in reversed(range(T)):
        run = rews[i] + gamma * run
        rets[i] = run
    return adv, rets


def ppo_update(net, trajs, epochs=4, clip=0.2, c1=0.5, ent=0.01):
    opt = torch.optim.Adam(net.parameters(), lr=3e-4)
    X = [np.array(t['obs'], dtype=np.float32) for t in trajs]
    A_ = [np.array(t['acts']) for t in trajs]
    LP = [np.array(t['logps'], dtype=np.float32) for t in trajs]
    RW = [np.array(t['rews'], dtype=np.float32) for t in trajs]
    with torch.no_grad():
        VALS = []
        for x in X:
            xt = torch.tensor(x).unsqueeze(0)
            _, v, _ = net(xt)
            VALS.append(v.squeeze(0).numpy())
    ADVS, RETS = [], []
    for x, rw, v in zip(X, RW, VALS):
        a, r = gae(list(rw), list(v) + [0.0])
        ADVS.append(np.array(a, dtype=np.float32))
        RETS.append(np.array(r, dtype=np.float32))
    alladv = np.concatenate(ADVS)
    mu, sd = alladv.mean(), alladv.std() + 1e-8
    for _ in range(epochs):
        order = np.random.permutation(len(X))
        tot = 0.0
        for k in order:
            x = torch.tensor(X[k]).unsqueeze(0)
            lp_old = torch.tensor(LP[k])
            logits, v, _ = net(x)
            logits = logits.squeeze(0)
            dist = torch.distributions.Categorical(logits=logits)
            lp = dist.log_prob(torch.tensor(A_[k]))
            ratio = torch.exp(lp - lp_old)
            adv = torch.tensor((ADVS[k] - mu) / sd)
            pg = -torch.min(ratio * adv,
                            torch.clamp(ratio, 1 - clip, 1 + clip) * adv).mean()
            vf = ((v.squeeze(0) - torch.tensor(RETS[k])) ** 2).mean()
            loss = pg + c1 * vf - ent * dist.entropy().mean()
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 0.5)
            opt.step()
            tot += float(loss)
        print('ppo batch loss', round(tot / max(len(X), 1), 3), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['play', 'greedy', 'train'])
    ap.add_argument('--pids', default='')
    ap.add_argument('--pid', default='')
    ap.add_argument('--eps', type=int, default=2)
    ap.add_argument('--rounds', type=int, default=6)
    ap.add_argument('--random', action='store_true')
    a = ap.parse_args()
    if a.mode == 'greedy':
        net = PolicyNet()
        net.load_state_dict(torch.load(MODEL))
        ep = run_episode((int(a.pid), net.state_dict(), False, 'eval'))
        print('GREEDY', {k: ep[k] for k in
                         ('win', 'frac', 't', 'R') if k in ep}, flush=True)
        return
    pids = [int(p) for p in a.pids.split(',')]
    net = PolicyNet()
    if os.path.exists(MODEL):
        try:
            net.load_state_dict(torch.load(MODEL))
        except RuntimeError:
            print('stale ckpt shape: restarting fresh', flush=True)
    sd = net.state_dict()
    with mp.Pool(len(pids)) as pool:
        for rnd in range(a.rounds):
            jobs = [(p, {k: v.clone() for k, v in sd.items()},
                     a.random, f'r{rnd}') for p in pids for _ in range(a.eps)]
            trajs = pool.map(run_episode, jobs)
            good, wins, fracs = [], 0, []
            for tr in trajs:
                if 'err' in tr:
                    print('ERR', tr['pid'], tr['err'][:120], flush=True)
                    continue
                with open(HIST, 'a') as fh:
                    fh.write(json.dumps({k: tr[k] for k in
                                         ('level', 'pid', 'win', 'frac', 't',
                                          'R')}) + '\n')
                good.append(tr)
                wins += tr['win']
                fracs.append(tr['frac'])
                print('ep pid', tr['pid'], 'win', tr['win'],
                      'frac', round(tr['frac'], 3), 'R', round(tr['R'], 2),
                      flush=True)
            if not a.random and good:
                ppo_update(net, good)
                sd = net.state_dict()
                torch.save(sd, MODEL)
            if good:
                print(f'round {rnd}: wins {wins}/{len(good)} '
                      f'meanfrac {np.mean(fracs):.3f}', flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
