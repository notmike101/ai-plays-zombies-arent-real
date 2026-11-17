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
    """START single SPACE; VERIFY phase='playing' via DUMP (memory counters
    lie on lost screens). SPACE again only while a dialog/pause blocks."""
    env.vi.key_press(0x20, sc=57)
    time.sleep(3.0)
    for _ in range(6):
        d = env.dump()
        if d:
            ph = d['where'].get('phase')
            if ph == 'playing':
                if d['clock'].get('paused') == 'true':
                    env.vi.key_press(0x20, sc=57)   # stray pause
                return d
            if ph == 'planning':
                env.vi.key_press(0x20, sc=57)      # ready_short warning YES
                time.sleep(2.5)
                continue
        else:
            env.vi.key_press(0x20, sc=57)          # dialog blocks: YES
        time.sleep(2.0)
    return None


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
    counts = dump.get('counts', {})
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
        old = torch.load(path)
    except FileNotFoundError:
        return
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


def run_episode(args):
    pid, sd, eps_rand, tag = args
    from env_zar import ZAREnv
    observer = None
    try:
        env = ZAREnv(pid)
        cell_of = lambda c: cell_of_px(c, env.cw, env.ch)
        o = env.to_planning()          # R-loop to planning ONLY (net readies)
        kit = {0: 1}                   # Police lvl1 (1 SP — cheapest pick;
        env.set_loadout(kit)           # the econ echo verifies the buy)
        bind_keys = load_bind_keys(env)
        env.vi.key_press(0x74, sc=0x3F)  # 8x battle speed (harness, not strat)
        st = {'t': 0.0, 'planning': True, 'spend_frac': 0.0, 'frz': 0,
              'deck': [], 'sim': 0.0, 'mult': 8.0, 'last_dump': 0.0}
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
        wprev = None        # watchdog-only obs snapshot, distinct from prev_o
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
            blobs, tot = (None, 0)
            if o['zomb']:
                blobs, tot = env.crowd_topk()
                if not blobs and st['planning']:
                    hs = env.hot_spot()
                    blobs = [(hs[0], hs[1], 2000)] if hs else []
            mu, mc = masks_for(st)
            nblobs = [(bx / max(env.cw, 1), by / max(env.ch, 1), n)
                      for bx, by, n in (blobs or [])]
            f = make_obs(st, o, frac, trend, slope, nblobs, prev_u, prev_c,
                         succ)
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
                d = ready_once(env)
                st['planning'] = False
                st['deck'] = build_deck(d, bind_keys)
                print(f"DECK {pid}: " + (', '.join(
                    f"{s['name']}x{int(s['charges'])}@{s['key']}u{int(s['unlock'])}"
                    for s in st['deck']) or 'EMPTY'), flush=True)
                t0 = time.time()
                step_at = time.time()
                prev_o = env.obs()
                prev_t = time.time()
                wprev = None       # phase boundary: never inherit a streak
                rews.append(-0.05)
                trail.append((round(st['t'], 1), (prev_o.get('civ') or 0),
                              prev_o.get('zomb'), prev_o.get('money'), u, c))
                step += 1
                continue
            if st['planning'] and u in U_HOTKEY:
                vk, sc = U_HOTKEY[u]
                cx, cy = cell_of(c)
                env._arm(vk, sc)
                # Polled-path placement: the engine reads DLL-hooked
                # cursor/buttons; PostMessage clicks place NOTHING in-world;
                # >=3-step >=6px strokes only (verified by HUD receipts).
                env.vi.drag(int(cx), int(cy), int(cx) + 8, int(cy) + 6,
                            steps=4)
                time.sleep(0.3)
                did = True
            elif st['planning'] and u == 10:
                x1, y1 = cell_of(c)
                x2, y2 = cell_of(zone_span(c))
                env._arm(0x42, 48)
                for px, py in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
                    env.vi.drag(int(px), int(py), int(px) + 7, int(py) + 5,
                                steps=3)
                    time.sleep(0.12)
                env.vi.key_press(0x0D, sc=28)  # CLOSE loop: ENTER or no zone
                time.sleep(0.8)
                did = True        # fee charges on close; receipt gates bonus
            elif not st['planning'] and u in U2ABILITY:
                s = next((x for x in st['deck']
                          if x['name'] == U2ABILITY[u]), None)
                if s and s['key'] and slot_castable(st, s):
                    was_alive = s['alive']
                    cx, cy = cell_of(c)
                    env.cast(s['key'], cx, cy)
                    if not (s['name'] == 'Heli' and was_alive):
                        s['charges'] -= 1.0
                        if s['arrival'] > 0:
                            s['pending'] = True
                            s['ready_t'] = st['sim'] + s['arrival']
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
            if not st['planning']:
                st['sim'] += dt * st['mult']
                for s in st['deck']:
                    if s['pending'] and st['sim'] >= s['ready_t']:
                        s['pending'] = False
                        if s['name'] == 'Heli':
                            s['alive'] = True   # optimistic; dump verifies
                if time.time() - st['last_dump'] > 20:
                    st['last_dump'] = time.time()
                    refresh_battle_state(st, env.dump())
            if did and u in U2ABILITY:
                # it17 winning lever shaping: a cast placed INS the
                # detected horde outearns a blind cast (heli redeploys).
                fx, fy = cell_of(c)                      # compare in client
                fx /= max(env.cw, 1)                     # fractions: blobs
                fy /= max(env.ch, 1)                     # are normalized
                near = any(abs(fx - bx) < 0.09 and abs(fy - by) < 0.10
                           for bx, by, _n in nblobs)
                r += 0.15 if near else 0.02
            trail.append((round(st['t'], 1), o.get('civ'), o.get('zomb'),
                          o.get('money'), u, c))
            if did:
                r -= 0.01
                if st['planning'] and u not in (0, 1) and succ == 1.0:
                    r += 0.12    # receipt: money really fell = placed for real
            r = max(r, -0.25)     # floor: evacuation waves are saves, not spiral
            rews.append(r)
            if o['zomb'] > 0:
                fought = True
            prev_o = dict(o)
            prev_t = time.time()
            step += 1
            # ---------------- termination ----------------
            if st['planning']:
                if step >= PLAN_STEPS:
                    d = ready_once(env)
                    st['planning'] = False
                    st['deck'] = build_deck(d, bind_keys)
                    t0 = time.time()
                    print(f"DECK {pid}: " + (', '.join(
                        f"{s['name']}x{int(s['charges'])}@{s['key']}u{int(s['unlock'])}"
                        for s in st['deck']) or 'EMPTY'), flush=True)
                    step_at = time.time()
                    prev_o = env.obs()
                    prev_t = time.time()
                    wprev = None   # phase boundary: never inherit a streak
                time.sleep(0.2)
                continue
            bt = time.time() - t0
            # Pause watchdog: compare against the PREVIOUS battle sample
            # via a dedicated snapshot — prev_o is re-snapshotted above
            # every iteration (the cc8ef9f check compared o with itself and
            # false-fired every second battle iteration). LIMITATION:
            # stationary (civ, zomb) can also mean a dialog/menu is open
            # (counters freeze; SPACE = dialog YES there), and a genuine
            # no-contact lull; counter data alone still cannot PROVE the
            # game is paused — this only guarantees the streak now means
            # "no progress between DISTINCT battle samples".
            wp = (o['civ'], o['zomb'])
            if (o['zomb'] or 0) > 0 and wprev is not None and wp == wprev:
                st['frz'] += 1
                if st['frz'] >= 2:     # pause wedge: unpause
                    print(f'UNPAUSE pid {pid} t {st["t"]:.0f}', flush=True)
                    env.vi.key_press(0x20, sc=57)
                    st['frz'] = 0
            else:
                st['frz'] = 0
            wprev = wp
            if o['zomb'] == 0 and bt > 25 and fought:
                win = True
                break
            if fought and (frac <= 0.02 and bt > 60 or
                           (o['civ'] or 0) == 0 and bt > 6):
                break
            if bt > BATTLE_T:
                break
            time.sleep(max(STEP_S - (time.time() - step_at), 0.3))
        battle_dur = st['t']
        sp = q_saved(pid, battle_dur)
        eff = max(frac, sp or 0.0)
        R_final = (3.0 if win else 0.0) + 5.0 * eff ** 1.5
        if win:
            # USER DIRECTIVE 2026-11-16: STAY ON LEVEL 1 until told otherwise.
            # Replay THIS level (R = dialog, 2nd R = YES): keeps placements +
            # budget, banks the badge, and the pinned-adaptive loop hardens
            # each good win via outbreak head starts. (ENTER would advance.)
            env.vi.key_press(0x52, sc=19)
            time.sleep(2.5)
            env.vi.key_press(0x52, sc=19)
            time.sleep(6)
        rews[-1] += R_final
        return dict(level=tag, pid=pid, win=bool(win), frac=float(frac),
                    civ0=int(civ0), t=st['t'], obs=obs, us=us, cs=cs,
                    ulps=ulps, clps=clps, trail=trail, rews=rews,
                    masks=mus, R=float(sum(rews)))
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
    if Observer is not None:
        validate_labels(NOBS, INPUT_LABELS)  # AGENTS.md contract: mismatch
        # means make_obs changed without labels -> refuse to launch training
    if a.mode == 'greedy':
        net = PolicyNet2()
        load_pretrained(net, MODEL)
        ep = run_episode((int(a.pid), net.state_dict(), False, 'eval'))
        print('GREEDY', {k: ep[k] for k in
                         ('win', 'frac', 't', 'R') if k in ep}, flush=True)
        return
    pids = [int(p) for p in a.pids.split(',')]
    net = PolicyNet2()
    if os.path.exists(MODEL):
        load_pretrained(net, MODEL)
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
                if len(tr.get('obs', [])) < 2:
                    print('SKIP short traj', tr['pid'], 'win', tr['win'],
                          'frac', tr['frac'], 't', round(tr.get('t', 0), 1),
                          flush=True)
                    continue
                with open(HIST, 'a') as fh:
                    fh.write(json.dumps({k: tr[k] for k in
                                         ('level', 'pid', 'win', 'frac', 't',
                                          'R', 'civ0') if k in tr}) + '\n')
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
