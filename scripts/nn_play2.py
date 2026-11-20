"""ZAR recurrent PPO: the model chooses loadout, planning geometry and battle actions.

Schema 4: native mechanics observations and 48 cells conditioned on the tool.
Reward = -new infections / initial population + 5 * terminal saved fraction - .02 per outside target.
Timeouts bootstrap; they never earn a terminal save reward. R carries the board.
"""
import argparse
from bisect import bisect_left
import hashlib
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Optional read-only visualizer; all telemetry stays under visualizer/.
sys.path.append(ROOT)
try:
    from visualizer.observer import Observer
    from visualizer.labels import INPUT_LABELS, validate as validate_labels
except ImportError:
    Observer = None
from scripts.mechanic_contract import EXTRA_TOOLS, EXTRA_LABELS, extra_cell_label
from policy_mechanics import Mechanics, PLACEMENTS, SPEED_TICKS, embedded_defenses, extra_masks, preparation_counts, preparation_fingerprint
MODEL = os.path.join(ROOT, 'sessions', 'nn_policy4.pt')
HIST = os.path.join(ROOT, 'analysis', 'nn_hist4.jsonl')
NOBS, HID = 332+len(EXTRA_LABELS), 128
PLANNING_INDEX = INPUT_LABELS.index('Planning phase')
BATTLE_GAMMA, BATTLE_LAMBDA = .99, .95
SAVED_REWARD_SCALE = 5.
RETRY_CIVILIAN_FRACTION = .10
MISSILE_CIVILIAN_COST = 1.
OUTSIDE_PLAYAREA_COST = .02
SPECIAL_ACTIVATION_CREDIT = .01
MAX_CREDITED_SPECIALS = 3
NU, NC = 72+len(EXTRA_TOOLS), 48
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
            15: (0x5A, 44), 16: (0x47, 34), 17: (0x51, 16), 18: (0x45, 18)}


# BATTLE DECK: purchased levels and actual saved roster determine hotkeys.
ABILITY_U = {'Police': 33, 'Bomber': 20, 'Heli': 11, 'Stungas': 21,
             'Firebomb': 22, 'CallArms': 12, 'APC': 23, 'Demolition': 24,
             'Rally': 13, 'SeekDestroy': 19, 'Bus': 25, 'Missile': 26,
             'Medevac': 14, 'Dozer': 27, 'Cluster': 28, 'Tank': 29,
             'AC130': 30, 'Cure': 31, 'Nuke': 32}
DECK_ORDER = ['Police', 'Bomber', 'Heli', 'Stungas', 'Firebomb', 'CallArms',
              'APC', 'Demolition', 'Rally', 'SeekDestroy', 'Bus', 'Missile',
              'Medevac', 'Dozer', 'Cluster', 'Tank', 'AC130', 'Cure', 'Nuke']
U2ABILITY = {v: k for k, v in ABILITY_U.items()}
BUY_TOOLS = slice(34, 34 + len(DECK_ORDER))
TOOLS += [f'buy_{n}' for n in DECK_ORDER] + [f'refund_{n}' for n in DECK_ORDER]
CELL_LABELS = [f'{tool}: cell {c+1}' for tool in TOOLS for c in range(NC)]
TOOLS += EXTRA_TOOLS
CELL_LABELS += [extra_cell_label(tool,c) for tool in EXTRA_TOOLS for c in range(NC)]
PLANNING_U = list(range(11)) + [15, 16, 17, 18]
BATTLE_GEOMETRY = {12, 20, 22, 24, 27, 28, 30, 33}
from spatial import XF, YF, inside_polygon
from shelter_reward import Shelter, CREDIT as SHELTER_CREDIT, BREACH_COST
WORLD_CELLS = np.repeat(YF < .70, len(XF))  # The last grid row overlaps the 1920x1200 HUD.
# resizes itself after tiling (probe: client 1920x1200 despite SetWindowPos),
# so cell coords are always computed from the LIVE client size.


PLAN_STEPS = 60            # harness bound on planning phase (cap, not strategy)
BATTLE_T = 560.0
STEP_S = 0.1               # Bounded10 Hz decisions; action receipts can take longer.

def cell_of_px(c, cw, ch):
    return (int(XF[c % 8] * cw), int(YF[c // 8] * ch))


class PolicyNet2(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(NOBS, HID, 1, batch_first=True)
        self.hu = nn.Linear(HID, NU)
        self.hc = nn.Linear(HID, NU * NC)
        self.val = nn.Linear(HID, 1)

    def forward(self, x, h=None):
        out, h = self.gru(x, h)
        return self.hu(out), self.hc(out), self.val(out).squeeze(-1), h


def slot_castable_frac(st, s):
    """Live stock fraction; an autonomous helicopter grants no extra cast."""
    return min(s['charges'], s['max_charges']) / max(s['max_charges'], 1.0)



def make_obs(st, o, frac, trend, slope, blobs, prev_u, prev_c, succ):
    g = lambda v: math.log1p(max(v or 0, 0))
    money = o['money'] or 0.0
    deck = st.get('deck') or []
    slots = [slot_castable_frac(st, s) for s in deck[:4]]
    slots += [0.0] * (4 - len(slots))
    base = [g(o['civ']), g(o['zomb']), g(o['converting']), g(o['corpses']),
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
    grid = np.asarray(st.get('grid', np.zeros((5, NC))))
    base.extend(np.log1p(grid[:4]).flatten().tolist())
    base.extend(grid[4].tolist())
    for name in DECK_ORDER:
        slot = next((s for s in deck if s['name'] == name), None)
        base.extend([st.get('loadout', {}).get(name, 0) / 10.,
                     slot_castable_frac(st, slot) if slot else 0.,
                     max(0., slot.get('ready_t', st['sim'])-st['sim']) / 60. if slot else 0.])
    anchor = st.get('anchor')
    base.extend([st.get('sp', 0) / 10., anchor[0]/72 if anchor else -1.,
                 anchor[1]/NC if anchor else -1.])
    base.extend(st.get('mechanics_features', [0.]*len(EXTRA_LABELS)))
    return base


def slot_castable(st, s):
    """Battle mask rule: sim clock past unlock, not awaiting arrival, and
    a charge remaining (existing aircraft act autonomously)."""
    if not s.get('key'):return False
    t = st['sim']
    if t + 0.5 < s['unlock']:
        return False
    if s['pending'] and t < s['ready_t']:
        return False
    return s['charges'] > 0


def base_masks(st):
    mu = np.zeros(NU, dtype=np.float32)
    mc = np.ones(NC, dtype=np.float32)
    if st.get('dialog'):
        mu[72:] = extra_masks(st).any(axis=1)
        return mu, mc
    if st.get('anchor'):
        u, c = st['anchor']
        mu[u] = 1
        mu[TOOLS.index('cancel_tool')] = 1
        mc[c] = 0
        if u == 10:
            mc[np.arange(NC)//8 == c//8] = 0
            mc[np.arange(NC)%8 == c%8] = 0
        return mu, mc
    if st.get('gesture_anchor'):
        mu[72:] = extra_masks(st).any(axis=1)
        return mu, mc
    if st['planning']:
        for u in PLANNING_U:
            mu[u] = 1
        if 'ready_legal' in st:
            mu[1] = st['ready_legal'] and not len(st['native']['selection']['polygon'])
        if 'planning_roster' in st:
            for u,name in PLACEMENTS.items():
                if u < 72:mu[u] = name in st['planning_roster']
        if 'build_targets' in st and not any(p is not None and WORLD_CELLS[i]
                                             for i, p in enumerate(st['build_targets'])):
            mu[[2, 3, 5, 8, 9]] = 0
        for i, name in enumerate(DECK_ORDER):
            level = st.get('loadout', {}).get(name, 0)
            cost = st.get('costs', {}).get(name)
            room = level > 0 or sum(v > 0 for v in st.get('loadout', {}).values()) < 7
            if cost is not None and cost > 0 and cost <= st.get('sp', 0) and room and name in st.get('unlocked', []):
                mu[34+i] = 1
            if level > 0:
                mu[53+i] = 1
    else:
        mu[0] = 1
        for s in (st.get('deck') or []):
            u = ABILITY_U.get(s['name'])
            if u is not None and slot_castable(st, s):
                mu[u] = 1
    for u,targets in st.get('battle_targets',{}).items():
        if not any(p is not None and st.get('world_cells',WORLD_CELLS)[i] for i,p in enumerate(targets)):mu[u]=0
    if st['planning']:
        for tool, _ in st.get('picker_blocked', ()):
            if tool < 72:
                mu[tool] = 0
    mu[72:] = extra_masks(st).any(axis=1)
    return mu, mc


BUILDING_PLACEMENTS = {tool for tool, name in PLACEMENTS.items() if name in (
    'Garrison', 'Sniper', 'Mortar', 'Nest', 'GasMortar', 'FireMortar',
    'Railgun', 'Howitzer', 'MLRS',
)}


SNAPPED_PLANNING_TOOLS = BUILDING_PLACEMENTS | {9}
PLANNING_SPATIAL_TOOLS = set(PLANNING_U[2:]) | set(PLACEMENTS)


def blocked_placement_cells(st, retries, decision):
    if not st['planning'] or not retries:
        return {}
    blocked = {}
    view = tuple(st['native']['camera'])
    for (tool, cell), (deadline, camera, target) in retries.items():
        if decision < deadline and view == camera and st['build_targets'][cell] == target:
            blocked.setdefault(tool, set()).add(cell)
    return blocked


def planning_geometry_masks(st, width, height):
    boundary = st.get('playarea_boundary')
    if not st['planning'] or boundary is None or st.get('dialog') or st.get('gesture_anchor'):
        return {}
    indices = np.arange(NC)
    rows, cols = np.divmod(indices, 8)
    cells = [cell_of_px(cell, width, height) for cell in indices]
    inside = inside_polygon(cells, boundary) & st.get('world_cells', WORLD_CELLS)
    if st.get('anchor'):
        tool, anchor = st['anchor']
        candidates = inside & inside[anchor] & (indices != anchor)
        if tool == 10:
            candidates &= ((rows != rows[anchor]) & (cols != cols[anchor])
                           & inside[rows[anchor] * 8 + cols] & inside[rows * 8 + cols[anchor]])
        return {tool: candidates}
    corners = inside[rows[:, None] * 8 + cols[None, :]]
    rectangles = (inside[:, None] & inside[None, :] & corners & corners.T
                  & (rows[:, None] != rows[None, :]) & (cols[:, None] != cols[None, :]))
    segments = inside & (inside.sum() >= 2)
    targets = st.get('build_targets', ())
    snapped = np.zeros(NC, dtype=bool)
    valid = [i for i, target in enumerate(targets) if target is not None]
    if valid:
        snapped[valid] = inside_polygon([targets[i] for i in valid], boundary)
    snapped &= st.get('world_cells', WORLD_CELLS)
    masks = {tool: snapped if tool in SNAPPED_PLANNING_TOOLS else inside
             for tool in PLANNING_SPATIAL_TOOLS}
    masks.update({10: rectangles.any(axis=1), 15: segments, 17: segments, 18: segments})
    return masks

def battle_geometry_masks(st, width, height):
    boundary = st.get('playarea_boundary')
    if st['planning'] or boundary is None or st.get('dialog'):
        return {}
    if st.get('anchor'):
        tool, anchor = st['anchor']
        if tool not in BATTLE_GEOMETRY:
            return {}
        origin = battle_point(st, tool, anchor, width, height)
        endpoints = [cell_of_px(i, width, height) for i in range(NC)]
        return {tool: inside_polygon(endpoints, boundary) & inside_polygon([origin], boundary)[0]}

    world_points = [(round(XF[i % 8] * width), round(YF[i // 8] * height)) for i in range(NC)]
    pointer_cells = inside_polygon(world_points, boundary)
    if st.get('gesture_anchor'):
        name, anchor = st['gesture_anchor']
        if name in ('drag_world', 'shift_drag_world'):
            return {TOOLS.index(name): pointer_cells & pointer_cells[anchor]}
        return {}
    masks = {TOOLS.index(name): pointer_cells
             for name in ('click_world', 'right_click_world', 'drag_world', 'shift_drag_world')}
    cast_cells = None
    for slot in st.get('deck', ()):
        tool = ABILITY_U.get(slot['name'])
        if tool is None or not slot_castable(st, slot):
            continue
        if tool in st.get('battle_targets', {}):
            points = [battle_point(st, tool, i, width, height) for i in range(NC)]
            masks[tool] = inside_polygon(points, boundary)
        else:
            if cast_cells is None:
                cast_cells = inside_polygon([cell_of_px(i, width, height) for i in range(NC)], boundary)
            masks[tool] = cast_cells
    return masks


def masks_for(st):
    tools, cells = base_masks(st)
    blocked_tools = (st.get('outside_retries', {}).keys()
                     | st.get('placement_blocked', {}).keys() | st.get('geometry_cells', {}).keys())
    for tool in blocked_tools:
        if tools[tool] and not cell_mask(st,tool,cells).any():
            tools[tool]=0
    return tools,cells


def cell_mask(st, u, mc):
    result = base_cell_mask(st,u,mc)
    for cell in st.get('outside_retries', {}).get(u, ()):
        result[cell] = 0
    for cell in st.get('placement_blocked', {}).get(u, ()):
        result[cell] = 0
    exact_geometry = st.get('geometry_cells', {}).get(u)
    if exact_geometry is not None:
        result *= exact_geometry
    return result


def base_cell_mask(st, u, mc):
    if u >= 72:
        if TOOLS[u]=='cancel_tool' and st.get('anchor'):
            return np.eye(1,NC,dtype=np.float32)[0]
        return extra_masks(st)[u-72].copy()
    mc = mc.copy()
    mc *= st.get('world_cells',WORLD_CELLS)
    if u in (0, 1) or u >= 34:
        mc[:] = 0
        mc[0] = 1
    elif not st['planning'] and u in st.get('battle_targets',{}) and not st.get('anchor'):
        mc *= [p is not None for p in st['battle_targets'][u]]
    elif st['planning'] and u in (2, 3, 5, 8, 9) and 'build_targets' in st:
        mc *= [p is not None for p in st['build_targets']]
    return mc


def battle_point(st, tool, cell, width, height):
    target=st.get('battle_targets',{}).get(tool,[None]*NC)[cell]
    return target if target is not None else cell_of_px(cell,width,height)


def outside_playarea(st, tool, cell, width, height):
    boundary = st.get('playarea_boundary')
    if boundary is None:
        return False
    name = TOOLS[tool]
    center = cell_of_px(cell, width, height)
    points = []
    if st['planning'] and tool in PLANNING_SPATIAL_TOOLS:
        if tool in SNAPPED_PLANNING_TOOLS:
            points = [st['build_targets'][cell]]
        else:
            points = [center]
        if st.get('anchor') and tool in (10, 15, 17, 18):
            x1, y1 = cell_of_px(st['anchor'][1], width, height)
            x2, y2 = center
            points.append((x1, y1))
            if tool == 10:
                points.extend(((x1, y2), (x2, y1)))
    elif not st['planning'] and tool in U2ABILITY:
        if st.get('anchor') and tool in BATTLE_GEOMETRY:
            points = [battle_point(st, tool, st['anchor'][1], width, height), center]
        else:
            points = [battle_point(st, tool, cell, width, height)]
    elif name in ('click_world', 'right_click_world', 'drag_world', 'shift_drag_world',
                  'zone_begin', 'zone_corner', 'drag_corner', 'drag_edge',
                  'move_selection', 'reaim_selection'):
        points = [(round(XF[cell%8]*width), round(YF[cell//8]*height))]
        if name in ('drag_world', 'shift_drag_world') and st.get('gesture_anchor'):
            start = st['gesture_anchor'][1]
            points.append((round(XF[start%8]*width), round(YF[start//8]*height)))
    return bool(points) and (any(point is None for point in points) or
                             not inside_polygon(points,boundary).all())


def update_outside_retries(st, width, height):
    retries = {}
    for tool,cells in st.get('outside_retries',{}).items():
        invalid = {cell for cell in cells if outside_playarea(st,tool,cell,width,height)}
        if invalid:
            retries[tool] = invalid
    st['outside_retries'] = retries


def select_policy_cell(distribution, greedy, generator=None):
    if generator is not None:
        return int(torch.multinomial(distribution.probs, 1, generator=generator))
    return int(distribution.probs.argmax() if greedy else distribution.sample())


def loadout_distribution(logits, legal_tools):
    legal_buys = torch.zeros_like(logits, dtype=torch.bool)
    legal_buys[BUY_TOOLS] = torch.as_tensor(legal_tools[BUY_TOOLS], dtype=torch.bool)
    ranked = logits.masked_fill(~legal_buys, -torch.inf).softmax(dim=0)
    return exploration_distribution(ranked, legal_buys, 0.5)


def exploration_distribution(ranked, legal, fraction):
    uniform = legal / legal.sum()
    return torch.distributions.Categorical(probs=(1. - fraction) * ranked + fraction * uniform)


def cell_distribution(logits, tool, mask):
    logits = logits.reshape(-1, NU, NC)
    tools = torch.as_tensor(tool, dtype=torch.long).reshape(-1)
    selected = logits[torch.arange(len(tools)), tools]
    selected = selected.masked_fill(torch.as_tensor(mask) == 0, -1e9)
    return torch.distributions.Categorical(logits=selected.squeeze(0) if len(tools) == 1 else selected)


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


def _rule(counts, name, suffix, *, default=0.0):
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
    return default


def opening_loadout_options(st):
    offers = {}
    for name, cost in st['costs'].items():
        if name not in st['unlocked'] or not 0 < cost <= st['sp']:
            continue
        unlock = _rule(st['rules'], name, '_unlock_seconds', default=math.nan)
        arrival = _rule(st['rules'], name, '_arrival_seconds', default=math.nan)
        if (math.isfinite(unlock) and unlock >= 0
                and math.isfinite(arrival) and arrival >= 0):
            offers[name] = {'cost': cost, 'first_effect': unlock + arrival}
    return offers


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
            'flight': _rule(counts, name, '_flight_seconds') if name=='Missile' else 0.,
            'pending': False, 'ready_t': 0.0, 'alive': False,
            'key': keys[i] if i < len(keys) else None}


def build_deck(dump, keys, roster=None, perks=()):
    """Purchased levels plus actual seven-slot roster; config supplies rules only."""
    if not dump:
        return []
    econ = dump.get('economy', {})
    counts = {**dump.get('config', {}), **dump.get('params', {}), **dump.get('counts', {})}
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
    for i, name in enumerate(roster if roster is not None else DECK_ORDER):
        if name in bought and name in ABILITY_U:
            deck.append(_slot(name, bought[name], pl, counts, keys,
                              i if roster is not None else len(deck)))
    if any(p['name']=='Quick_Deploy' for p in perks):
        cut=float(counts['perk_unlock_cut_percent'])
        if not math.isfinite(cut) or not 0<=cut<=100:raise ValueError('Invalid Quick Deploy reduction')
        for slot in deck:slot['unlock'] *= 1-cut/100
    return deck


def refresh_battle_state(st, dump):
    """Only live clock and helicopter counts; config charges are not live stock."""
    if not dump:
        return
    clock = dump.get('clock', {})
    st['sim'] = float(clock.get('sim_time', st['sim']))
    st['mult'] = float(clock.get('speed_mult', st['mult']))
    for slot in st.get('deck', []):
        if slot['name'] == 'Heli':
            slot['alive'] = int(dump.get('counts', {}).get('helicopters', 0)) > 0
            if slot['alive']:
                slot['pending'] = False


def checkpoint_schema():
    return dict(version=4, inputs=INPUT_LABELS, tools=TOOLS, cells=CELL_LABELS)


def learning_config(*, legacy=False):
    config = dict(revision=1 if legacy else 9, infection_cost=1.,
                  terminal_saved_scale=SAVED_REWARD_SCALE,
                  planning_gamma=1., planning_lambda=1.,
                  battle_gamma=BATTLE_GAMMA, battle_lambda=BATTLE_LAMBDA)
    if not legacy:
        config['battle_discount_reference_sim_seconds'] = STEP_S
        config['planning_target'] = 'undiscounted_episode_return'
        config['outside_playarea_cost'] = OUTSIDE_PLAYAREA_COST
        config['block_rejected_targets_until_legal'] = True
        config['shelter_credit'] = SHELTER_CREDIT
        config['occupied_breach_cost'] = BREACH_COST
        config['missile_civilian_cost'] = MISSILE_CIVILIAN_COST
        config['special_activation_credit'] = SPECIAL_ACTIVATION_CREDIT
        config['max_credited_specials'] = MAX_CREDITED_SPECIALS
    return config


def load_pretrained(net, path):
    data = torch.load(path, weights_only=True)
    if data.get('schema') != checkpoint_schema():
        raise ValueError('Incompatible checkpoint schema: explicitly migrate v3 with migrate_policy.py')
    net.load_state_dict(data['policy'])


def record_population_pressure(actions, obs, initial, sim):
    if obs['zomb'] > 0 and obs['civ'] <= obs['zomb']:
        actions.setdefault('first_outnumbered_sim', sim)
    if obs['civ'] <= RETRY_CIVILIAN_FRACTION * initial:
        actions.setdefault('first_live_at_retry_floor_sim', sim)


def transition_reward(before, after, civ0):
    # Infections are losses; evacuation is not. No per-sample clipping.
    return -max(after['infections'] - before['infections'], 0) / civ0


def charge_missile_civilian_loss(footer, step_ends, rewards, civ0):
    """Put each verified civilian loss on the step that crosses its native impact time."""
    if not footer or footer.get('combat_events_truncated') is not False:
        return None
    if any(not math.isfinite(t) for t in step_ends) or any(
            a > b for a, b in zip(step_ends, step_ends[1:])):
        return None
    impacts = {}
    for event in footer.get('combat_events', ()):
        if event.get('ev') != 'bomb' or event.get('what') != 'cruise_missile':
            continue
        seq, sim = event.get('seq'), event.get('sim')
        kills = (event.get('killed') or {}).get('civilians')
        if (type(seq) is not int or not isinstance(sim, (int, float)) or not math.isfinite(sim)
                or sim < 0 or type(kills) is not int or not 0 <= kills <= civ0):
            return None
        if seq in impacts and impacts[seq] != (sim, kills):
            return None
        impacts[seq] = sim, kills
    assigned = 0
    for sim, kills in impacts.values():
        step = bisect_left(step_ends, sim)
        if step < len(rewards):
            rewards[step] -= MISSILE_CIVILIAN_COST * kills / civ0
            assigned += kills
    return dict(confirmed=sum(kills for _, kills in impacts.values()), assigned=assigned)


def apply_loadout_action(env, st, name, delta):
    from game_controls import PickerNavigationError

    try:
        levels = env.change_loadout(name, delta)
    except PickerNavigationError:
        if env.loadout_levels() != st['loadout']:
            raise
        return False
    st['loadout'] = levels
    st['sp'] -= delta*st['costs'][name]
    return True


def planning_limit_reached(steps, limit, modal_open):
    # Give the policy one decision to handle a dialog raised by the last action.
    return steps >= limit + int(bool(modal_open))


def battle_timeout(state,now,battle_start,paused_since,options):
    if state['phase']=='playing' and state['paused']:
        if paused_since is None:paused_since=now
        if now-paused_since>=options.get('paused_seconds',float('inf')):
            return 'continuous_pause',paused_since
    else:paused_since=None
    if battle_start is not None and now-battle_start>=options.get('battle_seconds',BATTLE_T):
        return 'battle_clock',paused_since
    return None,paused_since


def run_episode(args, *, policy_factory=None, telemetry=True):
    pid, sd, eps_rand, tag, *extra = args
    options = extra[0] if extra else {}
    if 'seed' in options:
        torch.manual_seed(options['seed'])
        np.random.seed(options['seed'] % (2**32))
    zone_rng = None
    if options.get('sample_zone_geometry'):
        zone_rng = torch.Generator().manual_seed(options['seed'])
    loadout_rng = (torch.Generator().manual_seed(options['seed'] ^ 0x6C6F6164)
                   if options.get('sample_loadout') else None)
    garrison_rng = (torch.Generator().manual_seed(options['seed'] ^ 0x67617272)
                    if options.get('sample_garrison_sites') else None)
    cast_target_mode = options.get('cast_target_mode')
    cast_target_rng = (torch.Generator().manual_seed(options['seed'] ^ 0x687A90D5)
                       if cast_target_mode == 'sample' else None)
    from env_zar import ZAREnv, ZAREnvError
    env = observer = None
    u = c = None
    state = {}
    logging = False
    try:
        env = ZAREnv(pid)
        env.validate_build()
        mechanics = Mechanics(env)
        env.discard_dump_states = True
        allow_progression = options.get('allow_progression', False)
        if not allow_progression and env.game_state()['phase'] == 'won':
            raise ZAREnvError('Won board requires explicit campaign progression or a fresh L1 start')
        env.to_planning()
        initial = env.dump()
        if not initial or initial.get('where', {}).get('phase') != 'planning':
            raise ZAREnvError(f'No confirmed initial planning dump; state={env.game_state()}, '
                                  f'modal={env.scalar(0x667868, "<B")}, '
                                  f'menu={env.scalar(0x666870, "<B")}')
        stage_text = initial['where'].get('stage')
        if not allow_progression and stage_text and not stage_text.startswith('0 '):
            raise ZAREnvError(f'Expected L1 in default training mode, got {stage_text}')
        header = env.start_log()
        logging = True
        session = header['session']
        board_id = hashlib.sha256(json.dumps({
            'session': {k: session.get(k) for k in ('campaign', 'scenario', 'map', 'money', 'loadout')},
            'plan': [line for line in initial.get('_text', '').splitlines() if line.startswith('board ')]},
            sort_keys=True).encode()).hexdigest()[:16]
        keys = load_bind_keys(env)
        fixed_speed = options.get('fixed_speed')
        speed_action = fixed_speed or 'speed_1'
        mechanics.controls.key_action(speed_action)
        o = env.obs()
        civ0 = max(o['civ'], 1)
        m0 = o['money']
        st = dict(t=0., planning=True, spend_frac=0., deck=[], sim=0., mult=8., shelter=Shelter(civ0))
        config = initial.get('config', {})
        st['rules']={**config,**initial.get('params',{})}
        st.update(loadout=env.loadout_levels(), sp=session.get('sp_unspent', 0),
                  unlocked=env.unlocked_abilities(),
                  costs={name: _rule({k.removeprefix('loadout_'): v for k, v in config.items()}, name, '_cost')
                         for name in DECK_ORDER})
        opening_loadout = (opening_loadout_options(dict(st, rules={**st['rules'], **initial.get('counts', {})}))
                           if options.get('placement_feedback') else {})
        ready_loadout = {}
        ready_paint_mode = ready_paint_tiles = ready_embedded_defenses = ready_preparation = None
        plan = initial
        net = None if eps_rand else (policy_factory or PolicyNet2)().eval()
        if net is not None:
            net.load_state_dict(sd)
            if options.get('stage_model'):
                path=stage_model_path(options['stage_model'],session.get('scenario'))
                if session['scenario']>1 and os.path.isfile(path):load_pretrained(net,path)
            if Observer is not None and telemetry:
                observer = Observer(net, pid, tag, interval=options.get('observer_interval', .2), labels={
                    'input': INPUT_LABELS, 'hu': TOOLS, 'hc': CELL_LABELS})
        rows = {k: [] for k in ('obs', 'us', 'cs', 'ulps', 'clps', 'rews', 'masks', 'trail', 'sim_elapsed')}
        h = None
        prev_u = prev_c = succ = trend = slope = 0.
        start = time.monotonic()
        battle_start = None
        paused_since = timeout_reason = None
        end = None
        nbuy = 0
        battle_actions = dict(decisions=0, cast_available=0, cast_sampled=0, stock_decreased=0)
        if cast_target_mode:
            battle_actions['cast_target_non_argmax'] = 0
        if options.get('audit_cast_targets'):
            battle_actions['alternate_target_audit'] = dict(compared=0, different_argmax=0)
        if options.get('audit_cast_tools'):
            battle_actions['alternate_tool_audit'] = dict(compared=0, distance_sum=0.)
        legal_casts = {}
        selected_casts = {}
        selected_placements = {}
        shadow = dict(frames=[], casts=[]) if options.get('capture_shadow') else None
        if shadow is not None:
            import psutil
            from shadow_transitions import TransitionCapture, combat_context
            capture = TransitionCapture()
            shadow.update(schema=2, pid=pid, created=psutil.Process(pid).create_time(),
                          viewport=[env.cw, env.ch], policy=policy_id(net) if net is not None else 'random',
                          campaign=session.get('campaign'), scenario=session.get('scenario'),
                          map=session.get('map'), board=board_id, tools=TOOLS)
        outside_actions = 0
        outside_targets = {}
        special_activations = {}
        picker_rejections = {}
        picker_retry_at = {}
        placement_retry_at = {}
        placement_feedback = options.get('placement_feedback', False)
        paid_buildings = {}
        unconfirmed_buildings = {}
        building_receipts = []
        plan_limit = options.get('plan_steps', PLAN_STEPS)
        def episode_state():
            observed = env.game_state()
            if battle_start is None and observed['phase'] != 'planning':
                action = TOOLS[u] if u is not None else 'initial observation'
                raise ZAREnvError(f"Game entered {observed['phase']} without model READY after {action}")
            return observed

        state = episode_state()
        next_rest=0.
        next_retry_check = 0.
        excursion=False
        while end is None:
            if state['phase'] in ('won', 'lost'):
                end = state['phase']
                break
            st['planning'] = state['phase'] == 'planning'
            st['t'] = time.monotonic() - (battle_start or start)
            st['sim'], st['mult'] = state['sim'], state['mult']
            if not st['planning']:
                stock = env.battle_stock()
                for slot in st['deck']:
                    slot['charges'] = stock[slot['name']]
                if st.get('anchor'):
                    slot = next(s for s in st['deck'] if ABILITY_U[s['name']] == st['anchor'][0])
                    if not slot_castable(st, slot):
                        st.pop('anchor')
            frac = o['civ'] / civ0
            st['picker_blocked'] = [pair for pair, retry_at in picker_retry_at.items()
                                    if len(rows['obs']) < retry_at]
            if (time.monotonic()>=next_rest and not st.get('anchor') and not st.get('gesture_anchor')
                    and not st.get('corridor_armed') and not st.get('dialog')):
                fitted=mechanics.controls.rest_view()
                if not st['planning']:
                    battle_actions['view_checks']=battle_actions.get('view_checks',0)+1
                    battle_actions['view_fits']=battle_actions.get('view_fits',0)+int(fitted)
                excursion=False
                next_rest=time.monotonic()+2.
                after_view=episode_state()
                if after_view['phase']!=state['phase']:
                    state=after_view
                    o=env.obs()
                    continue
            mechanics.refresh(st)
            if not st['planning'] and rows['rews']:
                rows['rews'][-1] += st['shelter'].observe(st.get('native'),st['sim'])
            blobs = []
            f = make_obs(st, o, frac, trend, slope, blobs, prev_u, prev_c, succ)
            update_outside_retries(st,env.cw,env.ch)
            st['placement_blocked'] = blocked_placement_cells(st, placement_retry_at, len(rows['obs']))
            if placement_feedback:
                geometry = planning_geometry_masks if st['planning'] else battle_geometry_masks
                st['geometry_cells'] = geometry(st, env.cw, env.ch)
            mu, mc = masks_for(st)
            base_cells = mc
            greedy = options.get('greedy') and (st['planning'] or not options.get('sample_battle'))
            if fixed_speed:
                for name in SPEED_TICKS:
                    mu[TOOLS.index(name)] = 0
                if state['phase'] == 'playing' and state['mult'] != SPEED_TICKS[fixed_speed]:
                    raise ZAREnvError(f'Expected {fixed_speed}, observed native speed {state["mult"]}')
            if options.get('fixed_clock'):
                mu[TOOLS.index('pause_toggle')] = 0
            x = torch.tensor([[f]], dtype=torch.float32)
            with torch.no_grad():
                if net is None:
                    u = int(np.random.choice(np.flatnonzero(mu)))
                    mc = cell_mask(st, u, mc)
                    c = int(np.random.choice(np.flatnonzero(mc)))
                    ulp, clp = -math.log(mu.sum()), -math.log(mc.sum())
                else:
                    if (getattr(net,'cast_timing',None) is not None or getattr(net,'missile_reserve',0.)
                            or getattr(net,'missile_followup',0.) or getattr(net,'firebomb_line_targeting',False)):
                        net.set_cast_targets(st, mu, mc, env.cw, env.ch)
                    if st['planning'] and getattr(net, 'garrison_coverage_weight', 0.):
                        net.set_garrison_coverage(st, mu, mc, env.cw, env.ch)
                    if st['planning'] and getattr(net, 'zone_population_weight', 0.):
                        net.set_zone_population(st, mu, mc, env.cw, env.ch)
                    if getattr(net,'special_probe',0.):
                        net.set_special_probe(st,env.cw,env.ch)
                    lu, lc, _, h = net(x, h)
                    du = torch.distributions.Categorical(logits=lu.flatten().masked_fill(torch.tensor(mu == 0), -1e9))
                    u = int(du.probs.argmax() if greedy else du.sample())
                    if (loadout_rng is not None and greedy and st['planning']
                            and BUY_TOOLS.start <= u < BUY_TOOLS.stop
                            and mu[BUY_TOOLS].sum() > 1):
                        du = loadout_distribution(lu.flatten(), mu)
                        u = int(torch.multinomial(du.probs, 1, generator=loadout_rng))
                    if not st['planning']:
                        if options.get('collect_cast_tool_gradients'):
                            net.record_cast_tool_gradient(u, du.probs)
                        if options.get('audit_cast_tools'):
                            audit = battle_actions['alternate_tool_audit']
                            audit['compared'] += 1
                            audit['distance_sum'] += net.alternate_tool_distance(du)
                    mc = cell_mask(st, u, mc)
                    dc = cell_distribution(lc, u, mc)
                    cell_rng = zone_rng if st['planning'] and TOOLS[u] == 'zone_rect' else None
                    if (garrison_rng is not None and greedy and st['planning']
                            and TOOLS[u] == 'garrison' and mc.sum() > 1):
                        dc = exploration_distribution(dc.probs, torch.as_tensor(mc, dtype=torch.bool), 0.25)
                        cell_rng = garrison_rng
                    if cast_target_mode and not st['planning'] and u in U2ABILITY:
                        c = select_policy_cell(dc, cast_target_mode == 'greedy', cast_target_rng)
                        battle_actions['cast_target_non_argmax'] += int(c != int(dc.probs.argmax()))
                        if options.get('collect_cast_gradients'):
                            net.record_cast_gradient(u, c, dc.probs)
                    else:
                        c = select_policy_cell(dc, greedy, cell_rng)
                    if options.get('audit_cast_targets') and not st['planning'] and u in U2ABILITY:
                        audit = battle_actions['alternate_target_audit']
                        audit['compared'] += 1
                        audit['different_argmax'] += int(net.alternate_cast_argmax(u, dc, mc) != int(dc.probs.argmax()))
                    ulp, clp = float(du.log_prob(torch.tensor(u))), float(dc.log_prob(torch.tensor(c)))
                    if observer:
                        cp = torch.zeros(NU, NC)
                        cp[u] = dc.probs
                        observer.publish(probabilities={'hu': du.probs, 'hc': cp.flatten()},
                                         selected={'hu': u, 'hc': u*NC+c},
                                         phase='planning' if st['planning'] else 'battle')
            for k, v in dict(obs=f, us=u, cs=c, ulps=ulp, clps=clp, masks=(mu, mc)).items():
                rows[k].append(v)
            if not st['planning']:
                battle_actions['decisions'] += 1
                available_casts = [TOOLS[tool] for tool in U2ABILITY if mu[tool]]
                battle_actions['cast_available'] += int(bool(available_casts))
                battle_actions['cast_sampled'] += int(u in U2ABILITY)
                for name in available_casts:
                    legal_casts[name] = legal_casts.get(name, 0) + 1
                if u in U2ABILITY:
                    selected_casts[TOOLS[u]] = selected_casts.get(TOOLS[u], 0) + 1
                if shadow is not None and not capture.truncated and state['phase'] == 'playing':
                    capture.observe(
                        dict(sim=state['sim'], tick=int(st['native']['tick']), speed=state['mult'],
                             paused=state['paused'], camera=list(st['native']['camera']),
                             counts={k:o[k] for k in ('civ','zomb','converting','infections')},
                             grid=st['grid'].tolist(), anchor=st.get('anchor'),
                             context=combat_context(st['native'], env.cw, env.ch),
                             stock={slot['name']:[slot['charges'],slot['ready_t'],slot['pending']]
                                    for slot in st['deck']}),
                        dict(tool=TOOLS[u], cell=c, legal_tools=np.flatnonzero(mu).tolist(),
                             legal_cells=np.flatnonzero(mc).tolist(),
                             legal_cast_cells={TOOLS[tool]:np.flatnonzero(cell_mask(st,tool,base_cells)).tolist()
                                               for tool in U2ABILITY if mu[tool]}))
                    capture.receipt('not_applicable' if u == 0 else 'unknown')
                if shadow is not None and state['phase'] == 'playing' and not state['paused']:
                    frames = shadow['frames']
                    if len(frames) < 2048 and (not frames or state['sim'] >= frames[-1]['sim'] + .25):
                        frames.append(dict(sim=state['sim'], camera=list(st['native']['camera']),
                                           grid=st['grid'][:4].tolist(), civilians=o['civ'], zombies=o['zomb'],
                                           legal_casts=available_casts,
                                           selected=TOOLS[u], cell=c))
            elif u in PLACEMENTS:
                name = PLACEMENTS[u]
                selected_placements[name] = selected_placements.get(name, 0) + 1
            before = o
            previous_state = state
            action_started = time.monotonic()
            picker_rejected = False
            special_credit = 0.
            outside = outside_playarea(st, u, c, env.cw, env.ch)
            if outside:
                if shadow is not None and state['phase'] == 'playing':
                    capture.receipt('rejected', reason='outside_playarea')
                outside_actions += 1
                st['outside_retries'].setdefault(u,set()).add(c)
                target = f'{TOOLS[u]}/{c+1}'
                outside_targets[target] = outside_targets.get(target,0)+1
            elif u in PLACEMENTS:
                cx,cy=cell_of_px(c,env.cw,env.ch)
                if u in BUILDING_PLACEMENTS:
                    cx,cy=map(int,st['build_targets'][c])
                mechanics.controls.place(PLACEMENTS[u],(cx,cy))
            elif u >= 72:
                receipt = mechanics.execute(st,TOOLS[u],c)
                picker_rejected = receipt is False
                if isinstance(receipt,tuple) and TOOLS[u].startswith('panel_building_'):
                    building,ability=receipt
                    if building not in special_activations:
                        special_activations[building] = ability
                        if len(special_activations)<=MAX_CREDITED_SPECIALS:
                            special_credit = SPECIAL_ACTIVATION_CREDIT
            elif st['planning']:
                if u == 1:
                    if placement_feedback:
                        ready_paint_mode = bool(env.scalar(0x665160, '<B'))
                        paint = st['native']['paint']['kind']
                        ready_paint_tiles = dict(spikes=int(np.count_nonzero(paint == 1)),
                                                 oil=int(np.count_nonzero(paint == 2)))
                        ready_embedded_defenses = embedded_defenses(st['native'])
                        ready_preparation = preparation_counts(st['native'])
                        ready_preparation['layout_id'] = preparation_fingerprint(st['native'])
                    state = ready_once(env)
                    battle_start = time.monotonic()
                    d = dict(initial)
                    d['economy'] = {f'loadout {name}': str(level) for name, level in
                                    env.loadout_levels().items() if level > 0}
                    st['deck'] = build_deck(d, keys, env.roster(), st['perks'])
                    stock = env.battle_stock()
                    for slot in st['deck']:
                        slot['charges'] = slot['max_charges'] = stock[slot['name']]
                    if placement_feedback:
                        ready_loadout = {slot['name']: slot['unlock'] + slot['arrival'] for slot in st['deck']
                                         if slot['key'] and slot['charges'] > 0
                                         and math.isfinite(slot['unlock'] + slot['arrival'])}
                elif 34 <= u < 72:
                    name = DECK_ORDER[(u-34) % 19]
                    delta = 1 if u < 53 else -1
                    picker_rejected = not apply_loadout_action(env, st, name, delta)
                elif u in (10, 15, 17, 18):
                    if not st.get('anchor'):
                        st['anchor'] = (u, c)
                    else:
                        x1, y1 = cell_of_px(st.pop('anchor')[1], env.cw, env.ch)
                        x2, y2 = cell_of_px(c, env.cw, env.ch)
                        if u == 10:
                            mechanics.controls.zone_rectangle((x1, y1), (x2, y2))
                        else:
                            env._arm(*U_HOTKEY[u])
                            mechanics.controls.drag_handles((x1,y1),(x2,y2))
                            if u == 15:
                                env.vi.click(x2, y2)
                            mechanics.controls.frames()
                elif u in U_HOTKEY:
                    env._arm(*U_HOTKEY[u])
                    cx, cy = cell_of_px(c, env.cw, env.ch)
                    if u in (2, 3, 5, 8, 9):
                        cx, cy = map(int, st['build_targets'][c])
                    env.vi.move_to(cx, cy)
                    env.vi.click()
                    mechanics.controls.frames()
            elif u in U2ABILITY:
                slot = next(s for s in st['deck'] if s['name'] == U2ABILITY[u])
                if u in BATTLE_GEOMETRY and not st.get('anchor'):
                    st['anchor'] = (u, c)
                    if shadow is not None:
                        capture.receipt('gesture_started')
                else:
                    before_stock = env.battle_stock()[slot['name']]
                    if u in BATTLE_GEOMETRY:
                        import ctypes
                        vk = ord(slot['key'].upper())
                        env._arm(vk, ctypes.windll.user32.MapVirtualKeyW(vk, 0))
                        start_xy = battle_point(st,u,st.pop('anchor')[1],env.cw,env.ch)
                        end_xy = cell_of_px(c, env.cw, env.ch)
                        points = (start_xy, end_xy)
                        if u == 27:
                            env.vi.click(*start_xy)
                            time.sleep(.15)
                            env.vi.click(*end_xy)
                        else:
                            env.vi.drag(*start_xy, *end_xy)
                        mechanics.controls.frames()
                    else:
                        points = (battle_point(st,u,c,env.cw,env.ch),)
                        env.cast(slot['key'], *points[0])
                    slot['charges'] = env.battle_stock()[slot['name']]
                    if shadow is not None:
                        pixels = [[float(x), float(y)] for x, y in points]
                        capture.receipt('attempted', before=before_stock, after=slot['charges'], pixels=pixels)
                    # The stock receipt, not a sent keypress, proves a resource was spent.
                    if slot['charges'] < before_stock:
                        battle_actions['stock_decreased'] += 1
                        slot['last_cast_t'] = episode_state()['sim']
                        if shadow is not None:
                            capture.receipt('confirmed', before=before_stock, after=slot['charges'],
                                            sim=slot['last_cast_t'], pixels=pixels)
                        if shadow is not None and len(shadow['casts']) < 512:
                            shadow['casts'].append(dict(tool=TOOLS[u], cell=c,
                                                       sim=slot['last_cast_t'], spent=before_stock-slot['charges']))
                        slot['ready_t'] = slot['last_cast_t'] + slot['arrival']
                        slot['pending'] = slot['arrival'] > 0
                    if slot['name'] == 'Heli':
                        slot['alive'] = bool(np.any(mechanics.reader.snapshot()['helicopters']['alive']))
            if not excursion and TOOLS[u].startswith(('pan_','zoom_')):
                excursion=True
                next_rest=time.monotonic()+2.
            if picker_rejected:
                picker_rejections[TOOLS[u]] = picker_rejections.get(TOOLS[u], 0) + 1
                # Try other actions before reopening a picker that just rejected this choice.
                picker_retry_at[u, c] = len(rows['obs']) + 5
            # Observe after this action; outcomes belong to this transition.
            time.sleep(max(0., (.1 if st['planning'] else STEP_S) - (time.monotonic()-action_started)))
            o = env.obs()
            state = episode_state()
            if any(o[k] is None for k in ('money', 'civ', 'zomb', 'infections')):
                raise ZAREnvError('Incomplete observation')
            dt = max(state['sim'] - previous_state['sim'], .001)
            trend = (o['zomb'] - before['zomb']) / dt
            slope = (o['civ'] - before['civ']) / (dt*civ0)
            succ = float(st['planning'] and o['money'] < before['money'] - .01)
            if st['planning'] and u in BUILDING_PLACEMENTS and not outside:
                counts = paid_buildings if succ else unconfirmed_buildings
                unit = PLACEMENTS[u]
                counts[unit] = counts.get(unit, 0) + 1
                if placement_feedback:
                    camera = tuple(float(v) for v in st['native']['camera'])
                    target = st['build_targets'][c]
                    building_receipts.append(dict(decision=len(rows['obs'])-1, tool=TOOLS[u], cell=c,
                                                  target=target, camera=camera, paid=bool(succ),
                                                  existing_shelters=len(st['native'].get('zones', ())),
                                                  spend=round(before['money']-o['money'], 2)))
                    if not succ:
                        placement_retry_at[u, c] = (len(rows['obs']) + 5, camera, target)
            nbuy += int(succ)
            st['spend_frac'] = max(0., (m0-o['money']) / max(m0, 1))
            prev_u, prev_c = float(u), float(c)
            rows['rews'].append(transition_reward(before, o, civ0) - OUTSIDE_PLAYAREA_COST * outside + special_credit)
            rows['sim_elapsed'].append(max(0., state['sim'] - previous_state['sim']))
            rows['trail'].append((state['sim'], o['civ'], o['zomb'], o['money'], u, c))
            for slot in st['deck']:
                if slot['pending'] and state['sim'] >= slot['ready_t']:
                    slot['pending'] = False
            now = time.monotonic()
            timeout_reason,paused_since=battle_timeout(state,now,battle_start,paused_since,options)
            official_retry_saved = None
            playing = state['phase'] == 'playing'
            live_at_floor = o['civ'] <= RETRY_CIVILIAN_FRACTION * civ0
            infection_exhausted = o['infections'] >= (1. - RETRY_CIVILIAN_FRACTION) * civ0
            if playing:
                record_population_pressure(battle_actions, o, civ0, state['sim'])
            if playing and live_at_floor and not infection_exhausted and now >= next_retry_check:
                next_retry_check = now + 1.
                official_retry_saved = env.logged_saved_fraction(state['sim'])
            if state['phase'] in ('won', 'lost'):
                end = state['phase']
            elif (playing and live_at_floor and (infection_exhausted or
                  (official_retry_saved is not None and official_retry_saved <= RETRY_CIVILIAN_FRACTION))):
                end = 'aborted'
                if official_retry_saved is not None:
                    battle_actions['retry_snapshot_saved_frac'] = official_retry_saved
            elif timeout_reason:
                end = 'timeout'
            elif (state['phase'] == 'planning' and len(rows['obs']) >= plan_limit
                  and planning_limit_reached(len(rows['obs']), plan_limit, env.scalar(0x667868, '<B'))):
                end = 'timeout'
                timeout_reason='planning_decisions'
        footer = env.stop_log(capture_events=True)
        logging = False
        battle_actions['logged_deployments']=footer.get('deployments') if footer else None
        battle_actions['logged_kills'] = (footer.get('stats') or {}).get('kills') if footer else None
        if options.get('collect_cast_gradients'):
            battle_actions['cast_target_gradients'] = net.cast_gradients.tolist()
        if options.get('collect_cast_tool_gradients'):
            battle_actions['cast_tool_gradients'] = net.cast_tool_gradients.tolist()
        if placement_feedback and footer:
            events = footer.get('combat_events') or ()
            battle_actions['firebomb_lines'] = [
                dict(sim=event.get('sim'), start=(event.get('from') or {}).get('world'),
                     end=(event.get('to') or {}).get('world'))
                for event in events
                if event.get('ev') == 'deploy' and event.get('what') == 'fire_bomb']
            battle_actions['firebomb_impacts'] = sum(
                event.get('ev') == 'bomb' and event.get('what') == 'fire_bomb' for event in events)
        battle_actions['deploy_sim_seconds']=footer.get('deploy_sim_seconds') if footer else None
        saved = None
        if footer and footer.get('phase') == state['phase']:
            pct = footer.get('stats', {}).get('saved_pct')
            if pct is not None and math.isfinite(pct) and 0 <= pct <= 100:
                saved = pct / 100.
        bootstrap = 0.
        if end == 'timeout' and net is not None:
            st['planning'] = state['phase'] == 'planning'
            st['t'] = time.monotonic()-(battle_start or start)
            mechanics.refresh(st)
            st['sim'] = state['sim']
            f = make_obs(st, o, o['civ']/civ0, trend, slope, [], prev_u, prev_c, succ)
            with torch.no_grad():
                _, _, value, _ = net(torch.tensor([[f]], dtype=torch.float32), h)
                bootstrap = float(value.item())
        planning_blockers = None
        if end == 'timeout' and state['phase'] == 'planning':
            try:
                planning_blockers = env.geometry_blockers()
            except ZAREnvError:
                planning_blockers = ["geometry_unavailable"]
            if len(st.get('native', {}).get('selection', {}).get('polygon', ())):
                planning_blockers.append('unfinished_polygon')
            if st.get('dialog'):
                planning_blockers.append('modal_dialog')
            if st.get('anchor') or st.get('gesture_anchor'):
                planning_blockers.append('unfinished_gesture')
        outside_reward = -OUTSIDE_PLAYAREA_COST * outside_actions
        shelter = st['shelter']
        special_reward = SPECIAL_ACTIVATION_CREDIT * min(len(special_activations),MAX_CREDITED_SPECIALS)
        rewards = dict(infections=sum(rows['rews'])-outside_reward-shelter.presence_credit-shelter.breach_penalty-special_reward,
                       special_activation=special_reward,
                       outside_playarea=outside_reward, shelter=shelter.presence_credit,
                       occupied_breach=shelter.breach_penalty,
                       terminal=outcome_reward(saved, end))
        missile_rewards = rows['rews'] if options.get('missile_credit', True) else [0.] * len(rows['rews'])
        missile_losses = charge_missile_civilian_loss(
            footer, [step[0] for step in rows['trail']], missile_rewards, civ0)
        battle_actions['missile_civilian_losses'] = missile_losses
        battle_actions.update(legal_cast_tools=legal_casts, selected_cast_tools=selected_casts,
                              severe_failure=severe_outcome(saved, end))
        rewards['missile_civilian_loss'] = (-MISSILE_CIVILIAN_COST * missile_losses['assigned'] / civ0
                                            if missile_losses is not None and missile_rewards is rows['rews'] else 0.)
        if rows['rews']:
            rows['rews'][-1] += rewards['terminal']
        advance = end == 'won' and saved is not None and saved >= .35
        if end in ('aborted', 'lost') or end == 'won' and not advance:
            env.retry()
        if options.get('record_layout'):
            rows['layout_text']='\n'.join(line for line in initial['_text'].splitlines() if line.startswith('board '))
        if shadow is not None:
            rows['shadow'] = dict(shadow, session=header['wall'], native_footer=footer is not None,
                                  outbreak=footer.get('outbreak') if footer else None,
                                  native_combat_events=footer['combat_events'] if footer else None,
                                  native_combat_events_truncated=footer['combat_events_truncated'] if footer else None,
                                  states=capture.states, transitions=capture.transitions,
                                  tail=capture.pending,
                                  truncated=capture.truncated or len(shadow['casts']) >= 512)
        return dict(rows, level=tag, pid=pid, win=end == 'won', advance=advance, end=end,
                    saved_frac=saved if end != 'timeout' else None,
                    observed_saved_frac=saved, timeout_phase=state['phase'] if end == 'timeout' else None,
                    timeout_reason=timeout_reason if end=='timeout' else None,
                    planning_blockers=planning_blockers, picker_rejections=picker_rejections,
                    outbreak=footer.get('outbreak') if footer else None,
                    ready_stats=footer.get('ready_stats') if footer else None,
                    opening_loadout=opening_loadout, ready_loadout=ready_loadout,
                    ready_paint_mode=ready_paint_mode, ready_paint_tiles=ready_paint_tiles,
                    ready_embedded_defenses=ready_embedded_defenses, ready_preparation=ready_preparation,
                    special_activations=special_activations,
                    reward_components=rewards, outside_playarea_actions=outside_actions,
                    outside_targets=outside_targets, battle_actions=battle_actions,
                    selected_placements=selected_placements,
                    paid_buildings=paid_buildings, unconfirmed_buildings=unconfirmed_buildings,
                    building_receipts=building_receipts,
                    shelter=dict(credited_civilians=len(shelter.credited),exposed_civilians=len(shelter.exposed),
                                 breach_exposures=shelter.breach_exposures,
                                 occupied_breaches=shelter.occupied_breaches,
                                 first_occupied_breach=shelter.first_occupied_breach),
                    frac=o['civ']/civ0, bootstrap=bootstrap,
                    civ0=civ0, t=time.monotonic()-start, sim=state['sim'],
                    battle_started=battle_start,
                    R=sum(rows['rews']), nbuy=nbuy, ndeck=len(st['deck']),
                    spend=m0-o['money'], board=session, board_id=board_id,
                    scenario=session.get('scenario'), campaign=session.get('campaign'),
                    start_kind=options.get('start_kind', 'unknown'), seed=options.get('seed'),
                    log_started=header['wall'])
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return dict(level=tag, pid=pid, err=str(exc), last_tool=u, last_cell=c,
                    phase=state.get('phase'), seed=options.get('seed'),
                    start_kind=options.get('start_kind', 'unknown'))
    finally:
        try:
            if logging:
                env.stop_log()
        finally:
            if observer is not None:
                observer.close()
            if env is not None:
                env.close()


def gae(rews, vals, lam=BATTLE_LAMBDA, gamma=BATTLE_GAMMA, bootstrap=0.0,
        planning=None, sim_elapsed=None):
    planning = [False]*len(rews) if planning is None else planning
    elapsed = [STEP_S]*len(rews) if sim_elapsed is None else sim_elapsed
    if not len(rews) == len(vals) == len(planning) == len(elapsed):
        raise ValueError('Rewards, values, phases and elapsed times must have equal lengths')
    if any(not math.isfinite(dt) or dt < 0 for dt in elapsed):
        raise ValueError('Invalid elapsed simulation time')
    adv, last = [], 0.0
    next_value = bootstrap
    episode_return = bootstrap
    for r, v, is_planning, dt in zip(rews[::-1], vals[::-1], planning[::-1], elapsed[::-1]):
        episode_return += r
        if is_planning:
            last = episode_return - v
        else:
            # Paused battle actions consume no simulated time.
            time_steps = dt / STEP_S
            discount, trace = gamma**time_steps, lam**time_steps
            delta = r + discount * next_value - v
            last = delta + discount * trace * last
        adv.append(last)
        next_value = v
    adv = list(reversed(adv))
    rets = [a + v for a, v in zip(adv, vals)]
    return adv, rets


def severe_outcome(saved_frac, end):
    if saved_frac is None or end not in ('won', 'lost', 'aborted'):
        return None
    return saved_frac < RETRY_CIVILIAN_FRACTION


def outcome_reward(saved_frac, end):
    if saved_frac is None or end == 'timeout':
        return 0.0
    return SAVED_REWARD_SCALE * saved_frac


def valid_trajectory(tr):
    if 'err' in tr:
        return False
    if tr.get('end') == 'timeout':
        return isinstance(tr.get('bootstrap'), (int, float)) and math.isfinite(tr['bootstrap'])
    saved = tr.get('saved_frac')
    return (tr.get('end') in ('won', 'lost', 'aborted') and
            isinstance(saved, (int, float)) and math.isfinite(saved) and 0 <= saved <= 1)


def phase_loss_weights(planning):
    """Give planning and battle equal loss mass when both phases are present."""
    count = planning.count_nonzero().item()
    total = planning.numel()
    if count in (0, total):
        return torch.ones_like(planning, dtype=torch.float32)
    return torch.where(planning, total/(2*count), total/(2*(total-count)))


def ppo_update(net, trajs, opt, epochs=4, clip=0.2, c1=0.5, ent=0.015, *, balance_phases=False):
    seqs = []
    for t in trajs:
        X = torch.tensor(np.array(t['obs'], dtype=np.float32)).unsqueeze(0)
        U = torch.tensor(t['us'])
        C = torch.tensor(t['cs'])
        ULP = torch.tensor(t['ulps'], dtype=torch.float32)
        CLP = torch.tensor(t['clps'], dtype=torch.float32)
        MU = torch.tensor(np.array([m[0] for m in t['masks']],
                                   dtype=np.float32))
        MC = torch.tensor(np.array([m[1] for m in t['masks']], dtype=np.float32))
        RW = np.array(t['rews'], dtype=np.float32)
        with torch.no_grad():
            _, _, v, _ = net(X)
        vals = v.squeeze(0).numpy()
        adv, ret = gae(list(RW), list(vals), bootstrap=t.get('bootstrap', 0.0),
                       planning=X[0, :, PLANNING_INDEX].bool().tolist(), sim_elapsed=t['sim_elapsed'])
        seqs.append((X, U, C, ULP, CLP, MU,
                     torch.tensor(adv, dtype=torch.float32),
                            torch.tensor(ret, dtype=torch.float32), MC,
                     phase_loss_weights(X[0,:,PLANNING_INDEX].bool()) if balance_phases else 1.))
    alladv = np.concatenate([s[6].numpy() for s in seqs])
    mu_a, sd_a = alladv.mean(), alladv.std() + 1e-8
    diagnostics = []
    for epoch in range(epochs):
        order = np.random.permutation(len(seqs))
        tot = 0.0
        for k in order:
            X, U, C, ULP, CLP, MU, ADV, RET, MC, W = seqs[k]
            lu, lc, v, _ = net(X)
            du = torch.distributions.Categorical(
                logits=lu.squeeze(0).masked_fill_(MU == 0, -1e9))
            dc = cell_distribution(lc, U, MC)
            lp = du.log_prob(U) + dc.log_prob(C)
            ratio = torch.exp(lp - (ULP + CLP))
            adv = (ADV - mu_a) / sd_a
            pg = -(W * torch.min(ratio * adv,
                                 torch.clamp(ratio, 1 - clip, 1 + clip) * adv)).mean()
            vf = (W * (v.squeeze(0) - RET) ** 2).mean()
            loss = pg + c1 * vf - ent * (W * (du.entropy() + dc.entropy())).mean()
            if not torch.isfinite(loss):
                raise ValueError('Non-finite PPO loss; checkpoint not saved')
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 0.5, error_if_nonfinite=True)
            opt.step()
            tot += loss.detach().item()
            with torch.no_grad():
                variance = RET.var(unbiased=False)
                diagnostics.append(dict(epoch=epoch, loss=float(loss),
                    approx_kl=float(((ratio-1)-(lp-(ULP+CLP))).mean()),
                    clip_fraction=float(((ratio-1).abs() > clip).float().mean()),
                    entropy=float((du.entropy()+dc.entropy()).mean()),
                    explained_variance=float(1-(RET-v.squeeze(0)).var(unbiased=False)/variance)
                        if variance > 1e-8 else None))
        print('ppo2 batch loss', round(tot / max(len(seqs), 1), 3), flush=True)
    summary = {key: float(np.mean([d[key] for d in diagnostics if d[key] is not None]))
               if any(d[key] is not None for d in diagnostics) else None
               for key in ('loss', 'approx_kl', 'clip_fraction', 'entropy', 'explained_variance')}
    print('ppo diagnostics', json.dumps(summary), flush=True)
    return summary


def episode_batches(pids, sd, random, tag, eps, options=None):
    if not pids or len(set(pids)) != len(pids) or eps < 1:
        raise ValueError('Provide unique game PIDs and at least one episode')
    options = options or {}
    return [[(p, sd, random, f'{tag}/ep{i}', dict(options,
               seed=options.get('seed', 0)+j*eps+i,
               start_kind=options.get('starts', {}).get(p, 'unknown')))
             for i in range(eps)] for j, p in enumerate(pids)]


def run_batch(jobs):
    results = []
    for job in jobs:
        if results:
            job = (*job[:4], dict(job[4], start_kind='next_level' if results[-1].get('advance') else 'carry'))
        result = run_episode(job)
        results.append(result)
        board = result.get('board', {})
        if 'err' in result or result.get('advance') and (
                not job[4].get('allow_progression') or board.get('scenario') == board.get('scenario_count')):
            break
    return results


def training_enabled(mode, random):
    return mode == 'train' and not random


def save_checkpoint(net, opt, path, run_id):
    path = os.fspath(path)
    tmp = path + '.tmp'
    torch.save({'policy': net.state_dict(), 'optimizer': opt.state_dict(),
                'run_id': run_id, 'schema': checkpoint_schema(), 'learning': learning_config()}, tmp)
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


def stage_model_path(base, stage):
    if type(stage) is not int or not 1<=stage<=5:raise ValueError('Invalid Boston stage')
    stem,ext=os.path.splitext(base)
    return os.fspath(base) if stage==1 else f'{stem}.L{stage}{ext}'


def policy_id(net):
    digest = hashlib.sha256()
    for p in net.parameters():
        digest.update(p.detach().cpu().numpy().tobytes())
    return digest.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['play', 'greedy', 'train'])
    ap.add_argument('--pids', default='')
    ap.add_argument('--pid', default='')
    ap.add_argument('--eps', type=int, default=2)
    ap.add_argument('--rounds', type=int, default=6)
    ap.add_argument('--random', action='store_true')
    ap.add_argument('--allow-progression', action='store_true', help='Explicitly allow Boston L2–L5')
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--history', default=HIST)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--fresh-pids', default='', help='Only freshly booted boards, supplied by train_run')
    ap.add_argument('--plan-steps', type=int, default=PLAN_STEPS)
    ap.add_argument('--battle-seconds', type=float, default=BATTLE_T)
    a = ap.parse_args()
    validate_labels(NOBS, INPUT_LABELS)
    if a.mode != 'train' and not a.random and not os.path.exists(a.model):
        ap.error('Evaluation requires an existing schema-4 checkpoint or --random')
    if a.mode == 'greedy':
        a.pids, a.eps, a.rounds = a.pid, 1, 1
        if a.random:
            ap.error('greedy requires a policy checkpoint')
    if a.rounds < 1 or a.plan_steps < 1 or a.battle_seconds <= 0:
        ap.error('Rounds and rollout bounds must be positive')
    pids = [int(p) for p in a.pids.split(',') if p]
    episode_batches(pids, {}, a.random, '', a.eps)
    fresh = {int(p) for p in a.fresh_pids.split(',') if p}
    if not fresh.issubset(pids):
        ap.error('--fresh-pids must be among --pids')
    starts = {p: 'fresh' if p in fresh else 'unknown' for p in pids}
    torch.manual_seed(a.seed)
    net = PolicyNet2()
    opt = torch.optim.Adam(net.parameters(), lr=3e-4) if training_enabled(a.mode, a.random) else None
    if not a.random:
        load_checkpoint(net, opt, a.model)
    run_id = uuid.uuid4().hex[:12]
    stage_models={1:(net,opt)}
    sd = net.state_dict()
    copy_count = len(pids)
    with mp.Pool(copy_count) as pool:
        for rnd in range(a.rounds):
            options = dict(seed=a.seed+rnd*copy_count*a.eps, starts=starts,
                           greedy=a.mode == 'greedy', plan_steps=a.plan_steps,
                           battle_seconds=a.battle_seconds,stage_model=os.path.abspath(a.model),
                           allow_progression=a.allow_progression)
            jobs = episode_batches(pids, sd, a.random, f'{run_id}/r{rnd}', a.eps, options)
            trajs = [tr for batch in pool.map(run_batch, jobs) for tr in batch]
            good = {}
            checkpoint_id = 'random' if a.random else policy_id(net)
            with open(a.history, 'a', encoding='utf-8') as fh:
                for tr in trajs:
                    row = {k: v for k,v in tr.items() if k not in
                           ('obs', 'us', 'cs', 'ulps', 'clps', 'rews', 'masks', 'trail', 'sim_elapsed', 'board')}
                    stage=tr.get('scenario')
                    if not a.random and type(stage) is int and stage>1 and stage not in stage_models:
                        # Workers used frozen L1 weights if this stage had no specialist yet.
                        specialist=PolicyNet2()
                        specialist.load_state_dict(sd)
                        optimizer=torch.optim.Adam(specialist.parameters(),lr=3e-4) if opt is not None else None
                        load_checkpoint(specialist,optimizer,stage_model_path(a.model,stage))
                        stage_models[stage]=(specialist,optimizer)
                    row.update(kind='episode', run_id=run_id, round=rnd, mode=a.mode,
                               checkpoint_id=policy_id(stage_models[stage][0]) if stage in stage_models and not a.random else checkpoint_id, schema=4, learning=learning_config())
                    fh.write(json.dumps(row) + '\n')
                    starts[tr['pid']] = 'next_level' if tr.get('advance') else 'carry'
                    if not a.allow_progression and tr.get('advance'):
                        pids.remove(tr['pid'])
                    if 'err' in tr:
                        print('ERR', tr['pid'], tr['err'][:120], flush=True)
                        continue
                    if opt is not None and tr.get('obs') and valid_trajectory(tr):
                        good.setdefault(stage,[]).append(tr)
                    print('ep pid', tr['pid'], 'end', tr['end'],
                          'saved', tr['saved_frac'], 'R', round(tr['R'], 2), flush=True)
                for stage,episodes in good.items():
                    model,optimizer=stage_models[stage]
                    diagnostics = ppo_update(model, episodes, optimizer)
                    save_checkpoint(model, optimizer, stage_model_path(a.model,stage), run_id)

                    fh.write(json.dumps(dict(kind='update', run_id=run_id, round=rnd,
                                             scenario=stage, checkpoint_id=policy_id(model), learning=learning_config(),
                                             **diagnostics))+'\n')
            if any('err' in tr for tr in trajs):
                raise RuntimeError('Worker failed; stopped this run after preserving error history')
            if not pids:
                print('All copies met the L1 target; ending run', flush=True)
                break
            if a.allow_progression and any(tr.get('advance') and tr.get('board', {}).get('scenario') ==
                   tr.get('board', {}).get('scenario_count') for tr in trajs):
                print('Campaign completed; ending run for review', flush=True)
                break
    print('done', flush=True)


if __name__ == '__main__':
    main()
