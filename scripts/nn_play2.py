"""ZAR PPO v2: the NET owns planning AND battle (buys, placement, deployment).

Single GRU policy with factorized heads: U (tool/unit, 14) x C (map cell, 12).
Phases: PLANNING (money spent via tool hotkey + cell click; READY is the
model's decision) then BATTLE (SP deck casts; heli reposition unlimited after
first heli cast). Rewards: 8*dfrac/civ + dense kill term - action costs +
terminal 3*win + 5*frac^1.5. Boards persist: R-loop returns to planning,
placements + leftover budget carry (game rule).

Usage: nn_play2.py train|play --pids a,b,c --eps N --rounds M [--random]
       nn_play2.py greedy --pid P
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
# Optional read-only visualizer; all telemetry stays under visualizer/.
sys.path.append(ROOT)
try:
    from visualizer.observer import Observer
    from visualizer.labels import INPUT_LABELS
except ImportError:
    Observer = None
MODEL = os.path.join(ROOT, 'sessions', 'nn_policy2.pt')
HIST = os.path.join(ROOT, 'analysis', 'nn_hist2.jsonl')
NOBS, HID = 22, 128
NU, NC = 15, 12
TOOLS = ['wait', 'ready', 'napalm', 'mortar', 'sniper', 'turret', 'mine',
         'c4', 'gas_mortar', 'upgrade_unit', 'zone_rect', 'para', 'heli',
         'gas_bomb', 'ac130', 'wall']
# planning DEPLOY/BUILD hotkeys VERIFIED from HUD bottom bar 2026-11-17:
# 1 Napalm $100 | 2 Mortar $79 | 3 Sniper $50 | 4 Turret $90 | 5 Mine $15
# 6 C4 $500 | T Gas Mortar $90 | B Safe Zone (click wall start/end) |
# F Upgrade Unit | G Gate | Z Wall | Q Corridor | E Hold
U_HOTKEY = {2: (0x31, 2), 3: (0x32, 3), 4: (0x33, 4), 5: (0x34, 5),
            6: (0x35, 6), 7: (0x36, 7), 8: (0x54, 20), 9: (0x46, 33),
            14: (0x5A, 44)}
BATTLE_U = {11: ('1', 'para', 1), 12: ('2', 'heli', 1), 13: ('3', 'gas', 1),
            14: ('4', 'ac130', 3)}
PLANNING_U = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
BATTLE_U_ALLOWED = [0, 11, 12, 13, 14]
XS = [500, 767, 1033, 1300]
YS = [260, 500, 740]
CELLS = [(x, y) for y in YS for x in XS]
PLAN_STEPS = 60            # harness bound on planning phase (cap, not strategy)
BATTLE_T = 560.0
STEP_S = 2.5               # battle step period (seconds of game attention)


def cell_of(i):
    return CELLS[i % 12]


class PolicyNet2(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(NOBS, HID, 1, batch_first=True)
        self.hu = nn.Linear(HID, NU)
        self.hc = nn.Linear(HID, NC)
        self.val = nn.Linear(HID, 1)

    def forward(self, x, h=None):
        out, h = self.gru(x, h)
        return self.hu(out), self.hc(out), self.val(out).squeeze(-1), h


def make_obs(st, o, frac, trend, slope, blob, prev_u, prev_c, succ):
    g = lambda v: math.log1p(max(v or 0, 0))
    ch = st['charges']
    money = o['money'] or 0.0
    return [g(o['civ']), g(o['zomb']), g(o['converting']), g(o['corpses']),
            g(o['police']), money / 1000.0, min(st['t'] / 300.0, 2),
            frac, max(-3, min(3, trend / 1000.0)), max(-1, min(1, slope)),
            float(ch['para']), float(st['heli_up']), float(ch['gas']),
            ch['ac130'] / 3.0,
            -1 if blob is None else blob[0] / 1920.0,
            -1 if blob is None else blob[1] / 1200.0,
            -1.0 if blob is None else min(blob[2] / 4000.0, 1.0),
            float(prev_u), float(prev_c), float(succ),
            1.0 if st['planning'] else 0.0,
            min(st['spend_frac'], 1.0)]


def masks_for(st):
    mu = np.zeros(NU, dtype=np.float32)
    if st['planning']:
        for u in PLANNING_U:
            mu[u] = 1
    else:
        mu[0] = 1
        for u in (11, 12, 13, 14):
            key, name, _ = BATTLE_U[u]
            avail = st['heli_up'] if name == 'heli' else st['charges'][name]
            if avail > 0:
                mu[u] = 1
    return mu, np.ones(NC, dtype=np.float32)


def ready_once(env):
    """START single SPACE; 2nd SPACE only if a confirm dialog actually
    blocks (double-SPACE pauses the battle = wedge). Verify tick."""
    env.vi.key_press(0x20, sc=57)
    time.sleep(3.0)
    zo = env.obs()
    if (zo['zomb'] or 0) == 0:
        env.vi.key_press(0x20, sc=57)
        time.sleep(3.0)
    for _ in range(4):
        zo = env.obs()
        if (zo['zomb'] or 0) > 0:
            break
        time.sleep(2.0)

def run_episode(args):
    pid, sd, eps_rand, tag = args
    from env_zar import ZAREnv
    observer = None
    try:
        env = ZAREnv(pid)
        o = env.to_planning()          # R-loop to planning ONLY (net readies)
        env.vi.key_press(0x74, sc=0x3F)  # 8x battle speed (harness, not strat)
        st = {'t': 0.0, 'charges': {'para': 1, 'gas': 1, 'ac130': 3},
              'heli_up': 0.0, 'planning': True, 'spend_frac': 0.0}
        m0 = o['money'] or 0.0
        civ0 = max(o['civ'] or 1, 1)
        net = None
        if not eps_rand:
            net = PolicyNet2()
            net.load_state_dict(sd)
            net.eval()
            if Observer is not None:
                observer = Observer(net, pid, tag, labels={
                    'input': INPUT_LABELS if NOBS == len(INPUT_LABELS) else [],
                    'hu': TOOLS[:NU],
                    'hc': [f'Cell {i + 1}' for i in range(NC)],
                })
        h = None
        obs, us, cs, ulps, clps, rews, mus, trail = [], [], [], [], [], [], [], []
        prev_o = dict(o)
        prev_t = time.time()
        prev_u, prev_c, succ = 0.0, 0.0, 0.0
        trend, slope = 0.0, 0.0
        win = False
        fought = False
        frac = 1.0
        step = 0
        step_at = time.time()
        t0 = time.time()
        while True:
            st['t'] = time.time() - t0
            dt = max(time.time() - prev_t, 1e-6)
            o = env.obs()
            if st['planning'] and o.get('money') is None:
                return dict(level=tag, pid=pid, err='menu state mid-planning')
            trend = 0.7 * trend + 0.3 * ((o['zomb'] or 0) -
                                         (prev_o['zomb'] or 0)) / dt
            slope = ((o['civ'] or 0) - (prev_o['civ'] or 0)) / \
                max(dt * civ0, 1e-6)
            frac = (o['civ'] or 0) / civ0
            kills = max((prev_o['zomb'] or 0) - (o['zomb'] or 0), 0)
            blob = None
            if o['zomb'] and not st['planning']:
                hs = env.hot_spot()
                blob = (hs[0], hs[1], 2000) if hs else None
            mu, mc = masks_for(st)
            f = make_obs(st, o, frac, trend, slope, blob, prev_u, prev_c, succ)
            obs.append(f)
            mus.append((mu, mc))
            x = torch.tensor([f], dtype=torch.float32).unsqueeze(0)
            with torch.no_grad():
                if net is None:
                    u = int(np.random.choice(np.flatnonzero(mu > 0)))
                    c = int(np.random.choice(NC))
                    ulp = float(np.log(1.0 / max(mu.sum(), 1e-9)))
                    clp = float(math.log(1.0 / NC))
                else:
                    lu, lc, v, h = net(x, h)
                    lu = lu.squeeze(0).masked_fill_(
                        torch.tensor(mu == 0), -1e9)
                    du = torch.distributions.Categorical(logits=lu)
                    dc = torch.distributions.Categorical(logits=lc.squeeze(0))
                    u = int(du.sample())
                    c = int(dc.sample())
                    ulp = float(du.log_prob(torch.tensor(u)))
                    clp = float(dc.log_prob(torch.tensor(c)))
                    h = h.detach()
                    if observer is not None:
                        observer.publish(
                            probabilities={'hu': du.probs, 'hc': dc.probs},
                            selected={'hu': u, 'hc': c},
                            phase='planning' if st['planning'] else 'battle')
            us.append(u)
            cs.append(c)
            ulps.append(ulp)
            clps.append(clp)
            # ---------------- execute ----------------
            r = 0.0
            m_before = o['money']
            did = False
            if u == 1 and st['planning']:
                ready_once(env)
                st['planning'] = False
                t0 = time.time()
                step_at = time.time()
                prev_o = env.obs()
                prev_t = time.time()
                rews.append(-0.05)
                trail.append((round(st['t'], 1), (prev_o.get('civ') or 0),
                              prev_o.get('zomb'), prev_o.get('money'), u, c))
                step += 1
                continue
            if st['planning'] and u in U_HOTKEY:
                vk, sc = U_HOTKEY[u]
                cx, cy = cell_of(c)
                env._arm(vk, sc)
                env.vi.move_to(cx, cy)
                time.sleep(0.12)
                env.vi.click()
                time.sleep(0.25)
                did = True
            elif st['planning'] and u == 10:
                x1, y1 = cell_of(c)
                x2, y2 = cell_of((c + 4) % 12)
                env._arm(0x42, 48)
                for px, py in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
                    env.vi.move_to(px, py)
                    time.sleep(0.12)
                    env.vi.click()
                    time.sleep(0.18)
                did = True
            elif not st['planning'] and u in BATTLE_U:
                key, name, _ = BATTLE_U[u]
                cx, cy = cell_of(c)
                if name == 'heli':
                    env.cast(key, cx, cy)
                    st['heli_up'] = 1.0
                elif st['charges'][name] > 0:
                    env.cast(key, cx, cy)
                    st['charges'][name] -= 1
                did = True
            m_after = env.obs()['money'] if did and st['planning'] else None
            if m_after is not None and m_before is not None:
                succ = 1.0 if m_after < m_before - 0.5 else 0.0
            if m_after is not None and m0:
                st['spend_frac'] = max(0.0, (m0 - m_after) / m0)
            prev_u, prev_c = float(u), float(c)
            if not st['planning']:
                r = 8.0 * ((o['civ'] or 0) - (prev_o['civ'] or 0)) / civ0
                r += min(kills, 20000) * 2e-6
            trail.append((round(st['t'], 1), o.get('civ'), o.get('zomb'),
                          o.get('money'), u, c))
            if did:
                r -= 0.01
                if st['planning'] and u not in (0, 1):
                    r += 0.12    # shapes board-building: money fell = bought
            rews.append(r)
            if o['zomb'] > 0:
                fought = True
            prev_o = dict(o)
            prev_t = time.time()
            step += 1
            # ---------------- termination ----------------
            if st['planning']:
                if step >= PLAN_STEPS:
                    ready_once(env)
                    st['planning'] = False
                    t0 = time.time()
                    step_at = time.time()
                    prev_o = env.obs()
                    prev_t = time.time()
                time.sleep(0.2)
                continue
            bt = time.time() - t0
            if (o['civ'], o['zomb']) == (prev_o['civ'], prev_o['zomb']) \
                    and (o['zomb'] or 0) > 0:
                st['frz'] = st.get('frz', 0) + 1
                if st['frz'] >= 2:     # pause wedge: unpause
                    env.vi.key_press(0x20, sc=57)
                    st['frz'] = 0
            else:
                st['frz'] = 0
            if o['zomb'] == 0 and bt > 25 and fought:
                win = True
                break
            if frac <= 0.02 and fought and bt > 60:
                break
            if bt > BATTLE_T:
                break
            time.sleep(max(STEP_S - (time.time() - step_at), 0.3))
            step_at = time.time()
        R_final = (3.0 if win else 0.0) + 5.0 * frac ** 1.5
        if win:
            env.vi.key_press(0x0D, sc=28)   # CONTINUE chain on win screen
            time.sleep(6)
        rews[-1] += R_final
        return dict(level=tag, pid=pid, win=bool(win), frac=float(frac),
                    t=st['t'], obs=obs, us=us, cs=cs, ulps=ulps, clps=clps,
                    trail=trail, rews=rews, masks=mus, R=float(sum(rews)))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return dict(level=tag, pid=pid, err=str(e))
    finally:
        if observer is not None:
            observer.close()


def gae(rews, vals, lam=0.95, gamma=0.99):
    adv, last = [], 0.0
    for r, v in zip(rews[::-1], vals[::-1]):
        last = r + gamma * last - v
        adv.append(last)
    adv = list(reversed(adv))
    rets = [a + v for a, v in zip(adv, vals)]
    return adv, rets


def ppo_update(net, trajs, epochs=4, clip=0.2, c1=0.5, ent=0.015):
    opt = torch.optim.Adam(net.parameters(), lr=3e-4)
    seqs = []
    for t in trajs:
        X = torch.tensor(np.array(t['obs'], dtype=np.float32)).unsqueeze(0)
        U = torch.tensor(t['us'])
        C = torch.tensor(t['cs'])
        ULP = torch.tensor(t['ulps'], dtype=torch.float32)
        CLP = torch.tensor(t['clps'], dtype=torch.float32)
        MU = torch.tensor(np.array([m[0] for m in t['masks']],
                                   dtype=np.float32))
        RW = np.array(t['rews'], dtype=np.float32)
        with torch.no_grad():
            _, _, v, _ = net(X)
        vals = v.squeeze(0).numpy()
        adv, ret = gae(list(RW), list(vals))
        seqs.append((X, U, C, ULP, CLP, MU,
                     torch.tensor(adv, dtype=torch.float32),
                     torch.tensor(ret, dtype=torch.float32)))
    alladv = np.concatenate([s[6].numpy() for s in seqs])
    mu_a, sd_a = alladv.mean(), alladv.std() + 1e-8
    for _ in range(epochs):
        order = np.random.permutation(len(seqs))
        tot = 0.0
        for k in order:
            X, U, C, ULP, CLP, MU, ADV, RET = seqs[k]
            lu, lc, v, _ = net(X)
            du = torch.distributions.Categorical(
                logits=lu.squeeze(0).masked_fill_(MU == 0, -1e9))
            dc = torch.distributions.Categorical(logits=lc.squeeze(0))
            lp = du.log_prob(U) + dc.log_prob(C)
            ratio = torch.exp(lp - (ULP + CLP))
            adv = (ADV - mu_a) / sd_a
            pg = -torch.min(ratio * adv,
                            torch.clamp(ratio, 1 - clip, 1 + clip) * adv).mean()
            vf = ((v.squeeze(0) - RET) ** 2).mean()
            loss = pg + c1 * vf - ent * (du.entropy() + dc.entropy()).mean()
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 0.5)
            opt.step()
            tot += loss.detach().item()
        print('ppo2 batch loss', round(tot / max(len(seqs), 1), 3), flush=True)


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
        net = PolicyNet2()
        net.load_state_dict(torch.load(MODEL))
        ep = run_episode((int(a.pid), net.state_dict(), False, 'eval'))
        print('GREEDY', {k: ep[k] for k in
                         ('win', 'frac', 't', 'R') if k in ep}, flush=True)
        return
    pids = [int(p) for p in a.pids.split(',')]
    net = PolicyNet2()
    if os.path.exists(MODEL):
        try:
            net.load_state_dict(torch.load(MODEL))
        except RuntimeError:
            print('stale ckpt: fresh init', flush=True)
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
