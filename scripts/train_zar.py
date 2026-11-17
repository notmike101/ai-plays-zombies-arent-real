"""GRU policy for ZAREnv: behavior cloning from expert episodes, then PPO.

Obs (10 floats): log1p civ/zomb/conv/corp/police, money/1000, t/300, charges/3,
frac civ, zombie trend/1000 (EMA of deltas).
Actions (13): 0 wait; 1-6 cure at cursor grid (client px 300/740/1180 x 200/520);
7-12 cluster bomb same grid (battle-bar keys 4 and 3).

Usage:
  python train_zar.py expert <pid>   # scripted expert episode -> bc_episodes.jsonl
  python train_zar.py bc             # behavior cloning -> gru_policy.pt
  python train_zar.py ppo <N> <pid>  # N REINFORCE-with-baseline episodes
"""
import json
import math
import os
import sys
import time

import torch
import torch.nn as nn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_zar import ZAREnv

GRID = [(300, 200), (740, 200), (1180, 200), (300, 520), (740, 520), (1180, 520)]
NO, ND = 10, 13
DATA = r'D:\zar-scratch\sessions\bc_episodes.jsonl'
MODEL = r'D:\zar-scratch\sessions\gru_policy.pt'


def feats(o, civ0, t, charges, trend):
    g = lambda v: math.log1p(max(v or 0, 0))
    return [g(o['civ']), g(o['zomb']), g(o['converting']), g(o['corpses']), g(o['police']),
            (o['money'] or 0) / 1000.0, min(t / 300.0, 2.0), charges / 3.0,
            (o['civ'] or 0) / max(civ0, 1), max(-3.0, min(3.0, trend / 1000.0))]


class PolicyNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(NO, 96, 1, batch_first=True)
        self.pol = nn.Linear(96, ND)
        self.val = nn.Linear(96, 1)

    def forward(self, x, h=None):
        out, h = self.gru(x, h)
        last = out[:, -1]
        return self.pol(last), self.val(last).squeeze(-1), h


def decide(o, t, st, policy_fn, rows, civ0):
    now = time.time()
    dt = max(now - st['last'], 0.001)
    dz = ((o['zomb'] or 0) - st['prev_z']) / dt
    st['trend'] = 0.7 * st['trend'] + 0.3 * dz
    st['prev_z'] = o['zomb'] or 0
    st['last'] = now
    f = feats(o, civ0, t, st['charges'], st['trend'])
    a = policy_fn(f, st)
    rows.append(dict(obs=f, action=a))
    if 1 <= a <= 6 and st['charges'] > 0:
        st['charges'] -= 1
        x, y = GRID[a - 1]
        return ('cast', '4', x, y)
    if 7 <= a <= 12:
        x, y = GRID[a - 7]
        return ('cast', '3', x, y)
    return None


def run_episode(pid, policy_fn, max_s=600, charges=3):
    env = ZAREnv(pid)
    env.ready()
    t0 = time.time()
    while (env.obs()['zomb'] or 0) == 0 and time.time() - t0 < 25:
        time.sleep(2)
    o0 = env.obs()
    if (o0['zomb'] or 0) == 0:
        raise RuntimeError('battle did not start')
    civ0 = o0['civ']
    st = {'charges': charges, 'prev_z': o0['zomb'], 'trend': 0.0, 'last': time.time()}
    rows = []
    r = env.battle(lambda o, t: decide(o, t, st, policy_fn, rows, civ0),
                   max_s=max_s, stop_frac=0.04)
    return r, rows


def expert_fn(f, st):
    zomb = math.expm1(f[1])
    t = f[6] * 300
    if st['charges'] > 0 and t > 46 and zomb > 4000:
        a = 1 + getattr(expert_fn, 'i', 0) % 3
        expert_fn.i = a
        return a
    return 0


def cmd_expert(pid):
    expert_fn.i = 0
    r, rows = run_episode(pid, expert_fn)
    with open(DATA, 'a') as fh:
        for row in rows:
            fh.write(json.dumps(row) + '\n')
    print('EPISODE', r, 'rows', len(rows), flush=True)


def cmd_bc(epochs=80):
    rows = [json.loads(l) for l in open(DATA)]
    X = torch.tensor([r['obs'] for r in rows], dtype=torch.float32)
    A = torch.tensor([r['action'] for r in rows], dtype=torch.long)
    net = PolicyNet()
    opt = torch.optim.Adam(net.parameters(), lr=3e-3)
    lossf = nn.CrossEntropyLoss()
    for ep in range(epochs):
        perm = torch.randperm(len(X))
        tot = 0.0
        for i in range(0, len(X), 64):
            idx = perm[i:i + 64]
            p, v, _ = net(X[idx].unsqueeze(1))
            loss = lossf(p, A[idx])
            opt.zero_grad(); loss.backward(); opt.step()
            tot += loss.item() * len(idx)
        if ep % 10 == 0:
            print('ep', ep, 'loss', round(tot / len(X), 4), flush=True)
    torch.save(net.state_dict(), MODEL)
    print('saved', MODEL, flush=True)


def cmd_ppo(n_ep, pid):
    net = PolicyNet()
    if os.path.exists(MODEL):
        net.load_state_dict(torch.load(MODEL))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    for ep in range(n_ep):
        trace = []

        def pol(f, st):
            with torch.no_grad():
                x = torch.tensor([f], dtype=torch.float32).unsqueeze(1)
                p, v, _ = net(x)
                dist = torch.distributions.Categorical(logits=p)
                a = dist.sample()
            trace.append((f, a.item(), v.item()))
            return a.item()

        r, rows = run_episode(pid, pol)
        R = r['frac'] * 10 - 0.05 * sum(1 for _, a, _ in trace if a > 0)
        opt.zero_grad()
        loss = torch.tensor(0.0)
        for f, a, v in trace:
            x = torch.tensor([f], dtype=torch.float32).unsqueeze(1)
            p, vv, _ = net(x)
            dist = torch.distributions.Categorical(logits=p)
            loss = loss - dist.log_prob(torch.tensor([a])) * (R - vv) \
                + 0.5 * (vv - torch.tensor(R)) ** 2
        loss.backward(); opt.step()
        torch.save(net.state_dict(), MODEL)
        print('PPO ep', ep, r, 'R', round(R, 3), flush=True)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'expert':
        cmd_expert(int(sys.argv[2]))
    elif cmd == 'bc':
        cmd_bc()
    elif cmd == 'ppo':
        cmd_ppo(int(sys.argv[2]), int(sys.argv[3]))
