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
import re
import shutil
import time
import uuid

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
    from visualizer.labels import INPUT_LABELS, validate as validate_labels
except ImportError:
    Observer = None
MODEL = os.path.join(ROOT, 'sessions', 'nn_policy2.pt')
HIST = os.path.join(ROOT, 'analysis', 'nn_hist2.jsonl')
NOBS, HID = 32, 128
NU, NC = 34, 48
TOOLS = ['wait', 'ready', 'garrison', 'mortar', 'napalm', 'turret', 'mine',
         'c4', 'gas_mortar', 'upgrade_unit', 'zone_rect', 'heli', 'cta',
         'rally', 'medevac', 'wall', 'gate', 'corridor', 'hold', 'seek',
         'bomber', 'stungas', 'firebomb', 'apc', 'demolition', 'bus',
         'missile', 'dozer', 'cluster', 'tank', 'ac130', 'cure', 'nuke',
         'police_drop']
# planning DEPLOY/BUILD hotkeys READ OFF HUD screenshot probe 2026-11-16r:
# [1] Garrison $18-270 | [2] Mortar $75 | [3] Napalm $100 | [4] Turret $90 |
# [5] Mine Field $15 | [6] C4 $500 | [T] Gas Mortar $90 | [Q] Corridor
# $0.40/len | [E] Hold $0.80/rad | [B] Safe Zone | [Z] Wall | [F] Upgrade
# Unit | [G] Gate | [Tab] LOADOUT (SP picks) | [Space] READY
U_HOTKEY = {2: (0x31, 2), 3: (0x32, 3), 4: (0x33, 4), 5: (0x34, 5),
            6: (0x35, 6), 7: (0x36, 7), 8: (0x54, 20), 9: (0x46, 33),
            15: (0x5A, 44), 16: (0x47, 46), 17: (0x51, 16), 18: (0x45, 18)}


# BATTLE DECK (2026-11-17, replaces the pinned-BATTLE_U keybind contract):
# per-board deck TRUTH comes from the F6 dump: [economy] echoes
# 'loadout <Name> = lvl' (what SP actually bought), [counts] echoes the
# balance rules (*_unlock_seconds, *_arrival_seconds,
# ability_charges_per_level = [.Heli = 1, ...]). Bar slots bind to
# bind_slot1..7 (settings.ini) in battle_order.txt order (DECK_ORDER).
# Old stale binding = silent no-op key press; now bindings are READ, never
# assumed. charges = level x per_level (it17 kit verified: cta2 rally3
# medevac4 seek1).
ABILITY_U = {'Police': 33, 'Bomber': 20, 'Heli': 11, 'Stungas': 21,
             'Firebomb': 22, 'CallArms': 12, 'APC': 23, 'Demolition': 24,
             'Rally': 13, 'SeekDestroy': 19, 'Bus': 25, 'Missile': 26,
             'Medevac': 14, 'Dozer': 27, 'Cluster': 28, 'Tank': 29,
             'AC130': 30, 'Cure': 31, 'Nuke': 32}
DECK_ORDER = ['Police', 'Bomber', 'Heli', 'Stungas', 'Firebomb', 'CallArms',
              'APC', 'Demolition', 'Rally', 'SeekDestroy', 'Bus', 'Missile',
              'Medevac', 'Dozer', 'Cluster', 'Tank', 'AC130', 'Cure', 'Nuke']
U2ABILITY = {v: k for k, v in ABILITY_U.items()}
PLANNING_U = list(range(11)) + [15, 16, 17, 18]
XF = [0.11 + 0.77 * i / 7 for i in range(8)]   # grid as FRACTIONS of the
YF = [0.16 + 0.44 * j / 5 for j in range(6)]   # client window: the game
# resizes itself after tiling (probe: client 1920x1200 despite SetWindowPos),
# so cell coords are always computed from the LIVE client size.


def zone_span(c):
    """Zone rect = cell c to one row down + three cols right (~3x2 cells)."""
    r, col = divmod(c, 8)
    return ((r + 1) % 6) * 8 + (col + 3) % 8
PLAN_STEPS = 60            # harness bound on planning phase (cap, not strategy)
BATTLE_T = 560.0
STEP_S = 0.7               # battle step; at 8x ~5.6 s game-time; act() floor
# now ~0.55 s (shorter input sleeps), matching real-time play cadence

def cell_of_px(c, cw, ch):
    return (int(XF[c % 8] * cw), int(YF[c // 8] * ch))


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


def slot_castable_frac(st, s):
    """Deck-slot availability for obs: fraction of max charges still
    castable; a flying heli counts as one free re-aim."""
    add = 1.0 if (s['name'] == 'Heli' and s['alive']) else 0.0
    return min(s['charges'] + add, s['max_charges']) / \
        max(s['max_charges'], 1.0)


def make_obs(st, o, frac, trend, slope, blobs, prev_u, prev_c, succ):
    g = lambda v: math.log1p(max(v or 0, 0))
    money = o['money'] or 0.0
    deck = st.get('deck') or []
    slots = [slot_castable_frac(st, s) for s in deck[:4]]
    slots += [0.0] * (4 - len(slots))
    return [g(o['civ']), g(o['zomb']), g(o['converting']), g(o['corpses']),
            g(o['police']), money / 1000.0, min(st['t'] / 300.0, 2),
            frac, max(-3, min(3, trend / 1000.0)), max(-1, min(1, slope)),
            slots[0], slots[1], slots[2], slots[3],
            *[v / s for bv in (blobs or [])[:4]
              for v, s in ((bv[0], 1.0), (bv[1], 1.0), (bv[2], 6000.0))],
            *([-1.0] * (12 - 3 * min(len(blobs or []), 4))),
            min(len(blobs or []) / 4.0, 1.0),
            float(prev_u), float(prev_c), float(succ),
            1.0 if st['planning'] else 0.0,
            min(st['spend_frac'], 1.0)]


def slot_castable(st, s):
    """Battle mask rule: sim clock past unlock, not awaiting arrival, and
    either charges left or (Heli) one already flying = free re-aim."""
    t = st['sim']
    if t + 0.5 < s['unlock']:
        return False
    if s['pending'] and t < s['ready_t']:
        return False
    if s['charges'] > 0:
        return True
    return s['name'] == 'Heli' and s['alive']


def masks_for(st):
    mu = np.zeros(NU, dtype=np.float32)
    if st['planning']:
        for u in PLANNING_U:
            mu[u] = 1
    else:
        mu[0] = 1
        for s in (st.get('deck') or []):
            u = ABILITY_U.get(s['name'])
            if u is not None and slot_castable(st, s):
                mu[u] = 1
    return mu, np.ones(NC, dtype=np.float32)


def ready_once(env):
    """One READY and at most one warning confirmation; never assume success."""
    from env_zar import ZAREnvError
    env.vi.key_press(0x20, sc=57)
    for i in range(12):
        time.sleep(.1)
        state = env.game_state()
        if state['phase'] in ('playing', 'won', 'lost'):
            return state
        if i == 5 and state['phase'] == 'planning':
            env.vi.key_press(0x20, sc=57)
    raise ZAREnvError('READY did not enter battle')


_CPL_RE = re.compile(r'\.([A-Za-z]+)\s*=\s*([\d.]+)')


def _rule(counts, name, suffix):
    """Look up '<key><suffix>' in the dumped rules echo trying the naming
    variants (SeekDestroy -> seek_destroy_*, AC130 -> ac130_*)."""
    snake = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    for k in (snake, name.lower(), snake.replace('_', '')):
        v = counts.get(k + suffix)
        if v is not None:
            try:
                return float(v)
            except ValueError:
                pass
    return 0.0


def load_bind_keys(env):
    """Battle bar keys READ from this copy's settings.ini (bind_slot1..7:
    '_1' -> '1', 'T' -> 'T'); never assumed (keybind contract)."""
    with open(os.path.join(env.copy_dir(), 'steam_cloud', 'settings.ini'),
              encoding='utf-8', errors='ignore') as fh:
        txt = fh.read()
    keys = []
    for i in range(1, 8):
        m = re.search(r'^bind_slot%d\s*=\s*(\S+)' % i, txt, re.M)
        if m:
            keys.append(m.group(1)[-1])
    return keys


def _slot(name, lvl, pl, counts, keys, i):
    mx = max(1.0, lvl * float(pl.get(name, 1.0)))
    return {'name': name, 'lvl': lvl, 'max_charges': mx, 'charges': mx,
            'unlock': _rule(counts, name, '_unlock_seconds'),
            'arrival': _rule(counts, name, '_arrival_seconds'),
            'pending': False, 'ready_t': 0.0, 'alive': False,
            'key': keys[i] if i < len(keys) else None}


def build_deck(dump, keys):
    """Deck = what SP actually BOUGHT: only the [economy] 'loadout <Name> =
    lvl' echo proves a purchase. The kit file (resume_loadout) is NOT truth:
    kit probe 2026-11-17 on an SP-starved L1 board consumed the file and
    bought ZERO (economy echo empty), while ability_charges shows unowned
    defaults (.Police = 1) — either would fabricate casts. Charges + timing
    from the [counts] rules echo; bar keys bind in deck (battle_order)
    order; refresh_battle_state re-syncs charges from the live dump."""
    if not dump:
        return []
    econ = dump.get('economy', {})
    counts = {**dump.get('params', {}), **dump.get('counts', {})}
    pl = dict(_CPL_RE.findall(counts.get('ability_charges_per_level', '')))
    bought = {}
    for k, v in econ.items():
        if k.startswith('loadout '):
            try:
                lv = int(float(v))
            except ValueError:
                continue
            if lv > 0:
                bought[k[len('loadout '):].strip()] = lv
    deck = []
    for name in DECK_ORDER:
        if name in bought and name in ABILITY_U:
            deck.append(_slot(name, bought[name], pl, counts, keys,
                              len(deck)))
    return deck


_AB_RE = re.compile(r'\.([A-Za-z0-9]+)\s*=\s*([\d.]+)')


def refresh_battle_state(st, dump):
    """Re-sync sim clock, charges, cooldowns + heli liveness from a periodic
    battle dump: [counts] 'ability_charges'/'ability_cooldown' bracket lines
    are the GAME'S OWN deck truth (drift-corrects the sim);
    counts.helicopters is the only heli truth (the optimistic post-arrival
    'alive' gets cleared here once the aircraft left)."""
    if not dump:
        return
    cl = dump.get('clock', {})
    try:
        st['sim'] = float(cl.get('sim_time', st['sim']))
        st['mult'] = float(cl.get('speed_mult', st['mult']) or 1)
    except (TypeError, ValueError):
        pass
    counts = dump.get('counts', {})
    ch = dict(_AB_RE.findall(counts.get('ability_charges', '')))
    cd = dict(_AB_RE.findall(counts.get('ability_cooldown', '')))
    try:
        heli_n = int(float(counts.get('helicopters', 0)))
    except (TypeError, ValueError):
        heli_n = 0
    for s in st.get('deck') or []:
        if s['name'] in ch:
            s['charges'] = min(float(ch[s['name']]), s['max_charges'])
        if s['name'] != 'Heli' and float(cd.get(s['name'], 0)) > 0:
            # game-side cooldown: exact until-time (heli ignores it: a
            # flying heli is RE-AIMED free, it17-verified)
            s['ready_t'] = (st['sim'] + float(cd[s['name']])
                            if not s['pending'] else s['ready_t'])
            s['pending'] = True
        if s['name'] == 'Heli':
            s['alive'] = heli_n > 0
            if heli_n > 0:
                s['pending'] = False

def q_saved(pid, dur):
    """Game's own saved_pct from its battle telemetry (queue.jsonl); the
    BADGE metric counts evacuation + in-zone, which the live 'civ' memory
    field misses (zones evacuate -> alive falls). Only losers queue rows;
    match by duration. None = row absent (win or lag)."""
    try:
        import psutil
        d = psutil.Process(pid).exe().split('\\')[3]
        p = rf'{ROOT}\game-copies\{d}\cache\usage\queue.jsonl'
        with open(p, encoding='utf-8', errors='ignore') as fh:
            *_, last = fh
        row = json.loads(last)
        if abs(row.get('battle_s', -99) - dur) < 15:
            return float(row.get('saved_pct', 0.0)) / 100.0
    except Exception:
        pass
    return None


def load_pretrained(net, path):
    """Warm start: map an older narrower-obs checkpoint column-wise onto the
    current input width (old columns keep trained weights)."""
    try:
        old = torch.load(path, weights_only=True)
    except FileNotFoundError:
        return
    old = old.get('policy', old)
    new = net.state_dict()
    for key in tuple(old):
        o = old[key]
        if not key.startswith(('gru.', 'hu.', 'hc.', 'val.')):
            continue
        if o.shape != new[key].shape and all(
                n >= g for n, g in zip(new[key].shape, o.shape)):
            w = new[key].clone()
            w[tuple(slice(0, g) for g in o.shape)] = o
            old[key] = w
    net.load_state_dict(old)


def transition_reward(before, after, civ0):
    # Infections are losses; evacuation is not. No per-sample clipping.
    return -max(after['infections'] - before['infections'], 0) / civ0


def run_episode(args):
    pid, sd, eps_rand, tag, *extra = args
    options = extra[0] if extra else {}
    from env_zar import ZAREnv, ZAREnvError
    env = observer = None
    logging = False
    try:
        env = ZAREnv(pid)
        env.validate_build()
        env.to_planning()
        initial = env.dump()
        if not initial or initial.get('where', {}).get('phase') != 'planning':
            raise ZAREnvError('No confirmed initial planning dump')
        header = env.start_log()
        logging = True
        session = header['session']
        keys = load_bind_keys(env)
        env.vi.key_press(0x74, sc=63)
        o = env.obs()
        civ0 = max(o['civ'], 1)
        m0 = o['money']
        st = dict(t=0., planning=True, spend_frac=0., deck=[], sim=0., mult=8.)
        net = None if eps_rand else PolicyNet2().eval()
        if net is not None:
            net.load_state_dict(sd)
            if Observer is not None:
                observer = Observer(net, pid, tag, labels={
                    'input': INPUT_LABELS, 'hu': TOOLS, 'hc': [f'Cell {i+1}' for i in range(NC)]})
        rows = {k: [] for k in ('obs', 'us', 'cs', 'ulps', 'clps', 'rews', 'masks', 'trail')}
        h = None
        prev_u = prev_c = succ = trend = slope = 0.
        start = time.monotonic()
        battle_start = None
        end = None
        nbuy = 0
        state = env.game_state()
        while end is None:
            if state['phase'] in ('won', 'lost'):
                end = state['phase']
                break
            st['planning'] = state['phase'] == 'planning'
            st['t'] = time.monotonic() - (battle_start or start)
            st['sim'], st['mult'] = state['sim'], state['mult']
            if state['paused']:
                env.vi.key_press(0x20, sc=57)
                time.sleep(.1)
                state = env.game_state()
                if state['paused']:
                    raise ZAREnvError('Confirmed pause did not clear')
            frac = o['civ'] / civ0
            # Spatial input is supplied by a validated native reader in milestone 3.
            blobs = []
            f = make_obs(st, o, frac, trend, slope, blobs, prev_u, prev_c, succ)
            mu, mc = masks_for(st)
            x = torch.tensor([[f]], dtype=torch.float32)
            with torch.no_grad():
                if net is None:
                    u = int(np.random.choice(np.flatnonzero(mu)))
                    c = int(np.random.choice(np.flatnonzero(mc)))
                    ulp, clp = -math.log(mu.sum()), -math.log(mc.sum())
                else:
                    lu, lc, _, h = net(x, h)
                    du = torch.distributions.Categorical(logits=lu.flatten().masked_fill(torch.tensor(mu == 0), -1e9))
                    dc = torch.distributions.Categorical(logits=lc.flatten())
                    u = int(du.probs.argmax() if options.get('greedy') else du.sample())
                    c = int(dc.probs.argmax() if options.get('greedy') else dc.sample())
                    ulp, clp = float(du.log_prob(torch.tensor(u))), float(dc.log_prob(torch.tensor(c)))
                    if observer:
                        observer.publish(probabilities={'hu': du.probs, 'hc': dc.probs},
                                         selected={'hu': u, 'hc': c},
                                         phase='planning' if st['planning'] else 'battle')
            for k, v in dict(obs=f, us=u, cs=c, ulps=ulp, clps=clp, masks=(mu, mc)).items():
                rows[k].append(v)
            before = o
            previous_state = state
            action_started = time.monotonic()
            if st['planning']:
                if u == 1 or len(rows['obs']) >= options.get('plan_steps', PLAN_STEPS):
                    state = ready_once(env)
                    battle_start = time.monotonic()
                    d = dict(initial)
                    d['economy'] = {f'loadout {name}': str(level) for name, level in
                                    zip(DECK_ORDER, env.loadout_levels()) if level > 0}
                    st['deck'] = build_deck(d, keys)
                elif u in U_HOTKEY:
                    env._arm(*U_HOTKEY[u])
                    cx, cy = cell_of_px(c, env.cw, env.ch)
                    env.vi.click(cx, cy)
                    time.sleep(.2)
                elif u == 10:
                    x1, y1 = cell_of_px(c, env.cw, env.ch)
                    x2, y2 = cell_of_px(zone_span(c), env.cw, env.ch)
                    env._arm(0x42, 48)
                    for px, py in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
                        env.vi.click(px, py)
                    env.vi.key_press(0x0D, sc=28)
                    time.sleep(.2)
            elif u in U2ABILITY:
                slot = next(s for s in st['deck'] if s['name'] == U2ABILITY[u])
                env.cast(slot['key'], *cell_of_px(c, env.cw, env.ch))
                if not (slot['name'] == 'Heli' and slot['alive']):
                    slot['charges'] = max(slot['charges'] - 1, 0)
                    slot['ready_t'] = state['sim'] + slot['arrival']
                    slot['pending'] = slot['arrival'] > 0
            # Observe after this action; outcomes belong to this transition.
            time.sleep(max(0., (.1 if st['planning'] else STEP_S) - (time.monotonic()-action_started)))
            o = env.obs()
            state = env.game_state()
            if any(o[k] is None for k in ('money', 'civ', 'zomb', 'infections')):
                raise ZAREnvError('Incomplete observation')
            dt = max(state['sim'] - previous_state['sim'], .001)
            trend = (o['zomb'] - before['zomb']) / dt
            slope = (o['civ'] - before['civ']) / (dt*civ0)
            succ = float(st['planning'] and o['money'] < before['money'] - .01)
            nbuy += int(succ)
            st['spend_frac'] = max(0., (m0-o['money']) / max(m0, 1))
            prev_u, prev_c = float(u), float(c)
            rows['rews'].append(transition_reward(before, o, civ0))
            rows['trail'].append((state['sim'], o['civ'], o['zomb'], o['money'], u, c))
            for slot in st['deck']:
                if slot['pending'] and state['sim'] >= slot['ready_t']:
                    slot['pending'] = False
            if state['phase'] in ('won', 'lost'):
                end = state['phase']
            elif state['phase'] == 'playing' and o['civ'] <= .1*civ0:
                end = 'aborted'
            elif battle_start is not None and time.monotonic()-battle_start >= options.get('battle_seconds', BATTLE_T):
                end = 'timeout'
        footer = env.stop_log()
        logging = False
        saved = None
        if footer and footer.get('phase') == state['phase']:
            pct = footer.get('stats', {}).get('saved_pct')
            if pct is not None and math.isfinite(pct) and 0 <= pct <= 100:
                saved = pct / 100.
        bootstrap = 0.
        if end == 'timeout' and net is not None:
            st['planning'] = False
            st['t'] = time.monotonic()-battle_start
            f = make_obs(st, o, o['civ']/civ0, trend, slope, [], prev_u, prev_c, succ)
            with torch.no_grad():
                _, _, value, _ = net(torch.tensor([[f]], dtype=torch.float32), h)
                bootstrap = float(value.item())
        if rows['rews']:
            rows['rews'][-1] += outcome_reward(saved, end)
        if end in ('aborted', 'won', 'lost'):
            env.retry()
        return dict(rows, level=tag, pid=pid, win=end == 'won', end=end,
                    saved_frac=saved, frac=o['civ']/civ0, bootstrap=bootstrap,
                    civ0=civ0, t=time.monotonic()-start, sim=state['sim'],
                    R=sum(rows['rews']), nbuy=nbuy, ndeck=len(st['deck']),
                    spend=m0-o['money'], board=session, log_started=header['wall'])
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return dict(level=tag, pid=pid, err=str(exc))
    finally:
        try:
            if logging:
                env.stop_log()
        finally:
            if observer is not None:
                observer.close()
            if env is not None:
                env.close()


def gae(rews, vals, lam=0.95, gamma=0.99, bootstrap=0.0):
    adv, last = [], 0.0
    next_value = bootstrap
    for r, v in zip(rews[::-1], vals[::-1]):
        delta = r + gamma * next_value - v
        last = delta + gamma * lam * last
        adv.append(last)
        next_value = v
    adv = list(reversed(adv))
    rets = [a + v for a, v in zip(adv, vals)]
    return adv, rets


def outcome_reward(saved_frac, end):
    if saved_frac is None or end == 'timeout':
        return 0.0
    return 5.0 * saved_frac


def valid_trajectory(tr):
    return ('err' not in tr and (tr.get('saved_frac') is not None or
            tr.get('end') == 'timeout' and 'bootstrap' in tr))


def ppo_update(net, trajs, opt, epochs=4, clip=0.2, c1=0.5, ent=0.015):
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
        adv, ret = gae(list(RW), list(vals), bootstrap=t.get('bootstrap', 0.0))
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


def episode_batches(pids, sd, random, tag, eps):
    if not pids or len(set(pids)) != len(pids) or eps < 1:
        raise ValueError('Provide unique game PIDs and at least one episode')
    return [[(p, sd, random, f'{tag}/ep{i}') for i in range(eps)] for p in pids]


def run_batch(jobs):
    return [run_episode(job) for job in jobs]


def training_enabled(mode, random):
    return mode == 'train' and not random


def save_checkpoint(net, opt, path, run_id):
    path = os.fspath(path)
    tmp = path + '.tmp'
    torch.save({'policy': net.state_dict(), 'optimizer': opt.state_dict(),
                'run_id': run_id, 'schema': 1}, tmp)
    if os.path.exists(path):
        shutil.copy2(path, path + '.previous')
    os.replace(tmp, path)


def load_checkpoint(net, opt, path):
    if not os.path.exists(path):
        return
    load_pretrained(net, path)
    data = torch.load(path, weights_only=True)
    if opt is not None and 'optimizer' in data:
        opt.load_state_dict(data['optimizer'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['play', 'greedy', 'train'])
    ap.add_argument('--pids', default='')
    ap.add_argument('--pid', default='')
    ap.add_argument('--eps', type=int, default=2)
    ap.add_argument('--rounds', type=int, default=6)
    ap.add_argument('--random', action='store_true')
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--history', default=HIST)
    a = ap.parse_args()
    if Observer is not None:
        validate_labels(NOBS, INPUT_LABELS)  # AGENTS.md contract: mismatch
        # means make_obs changed without labels -> refuse to launch training
    if a.mode == 'greedy':
        net = PolicyNet2()
        load_checkpoint(net, None, a.model)
        ep = run_episode((int(a.pid), net.state_dict(), False, 'eval'))
        print('GREEDY', {k: ep[k] for k in
                         ('win', 'frac', 't', 'R') if k in ep}, flush=True)
        return
    pids = [int(p) for p in a.pids.split(',') if p]
    episode_batches(pids, {}, a.random, '', a.eps)
    net = PolicyNet2()
    opt = torch.optim.Adam(net.parameters(), lr=3e-4)
    load_checkpoint(net, opt if a.mode == 'train' else None, a.model)
    run_id = uuid.uuid4().hex[:12]
    sd = net.state_dict()
    with mp.Pool(len(pids)) as pool:
        for rnd in range(a.rounds):
            jobs = episode_batches(pids, sd, a.random, f'{run_id}/r{rnd}', a.eps)
            trajs = [tr for batch in pool.map(run_batch, jobs) for tr in batch]
            good, wins, fracs = [], 0, []
            for tr in trajs:
                if 'err' in tr:
                    print('ERR', tr['pid'], tr['err'][:120], flush=True)
                    continue
                if len(tr.get('obs', [])) < 2:
                    print('SKIP short traj', tr['pid'], 'win', tr['win'],
                          'frac', tr['frac'], 't', round(tr.get('t', 0), 1),
                          flush=True)
                    continue
                with open(a.history, 'a') as fh:
                    fh.write(json.dumps({k: tr[k] for k in
                                        ('level', 'pid', 'win', 'frac', 'saved_frac', 'end', 't',
                                         'R', 'civ0', 'nbuy', 'ndeck', 'spend', 'log_started') if k in tr}) + '\n')
                if valid_trajectory(tr):
                    good.append(tr)
                wins += tr['win']
                fracs.append(tr['frac'])
                print('ep pid', tr['pid'], 'win', tr['win'],
                      'frac', round(tr['frac'], 3), 'R', round(tr['R'], 2),
                      flush=True)
            if training_enabled(a.mode, a.random) and good:
                ppo_update(net, good, opt)
                sd = net.state_dict()
                save_checkpoint(net, opt, a.model, run_id)
            if good:
                print(f'round {rnd}: wins {wins}/{len(good)} '
                      f'meanfrac {np.mean(fracs):.3f}', flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
