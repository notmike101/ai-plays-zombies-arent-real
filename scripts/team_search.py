"""Population search over planning sequences and battle targeting on real game copies."""
import argparse
import campaign_fitness as fitness
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
from itertools import chain, combinations
import json
import math
import os
from pathlib import Path
from time import monotonic
import uuid

import numpy as np
import psutil
import torch

import local_agent as operator
import nn_play2 as tr
from game_controls import Controls
from nn_report import records
from shelter_reward import garrison_perimeter_gain, garrison_reach
from spatial import grid_bins, project
import zar_boot


def matching(prefix):
    return [i for i, name in enumerate(tr.TOOLS) if name.startswith(prefix)]


# A proposal samples a family, a preferred member and spatial parameters.
# These groups balance the proposal distribution across differently sized menus.
FAMILIES = [sorted(tr.PLACEMENTS), [10, 15, 16, 17, 18, 9],
            matching('buy_'), matching('equip_'), matching('perk_'), list(range(tr.NU))]
PLACEMENT_MODES = tuple(tr.TOOLS.index(name) for name in ('place_click', 'place_paint'))
CASTS = sorted(tr.U2ABILITY)
MISSILE = tr.ABILITY_U['Missile']
GARRISON = tr.TOOLS.index('garrison')
ZONE_RECT = tr.TOOLS.index('zone_rect')
FAST_SPEED = tr.TOOLS.index('speed_4')
MISSILE_ROW = CASTS.index(MISSILE)
FIREBOMB = tr.ABILITY_U['Firebomb']
POLICE = tr.ABILITY_U['Police']
FIREBOMB_ROW = CASTS.index(FIREBOMB)
SELECT_BUILDING = tr.TOOLS.index('select_building')
BUILDING_SPECIALS = {name.removeprefix('panel_'):i for i,name in enumerate(tr.TOOLS)
                     if name.startswith('panel_building_') and name.rsplit('_',1)[1].isdigit()}
GRID_START = tr.INPUT_LABELS.index('Grid civilians cell 1 (log1p count)')
PAN = [tr.TOOLS.index('pan_'+name) for name in ('up','left','down','right')]
PAUSE = tr.TOOLS.index('pause_toggle')
PAUSED = tr.INPUT_LABELS.index('Simulation paused (0/1)')
READY_LEGAL = tr.INPUT_LABELS.index('READY land and budget legal (0/1)')
GEOMETRY_ANCHOR = tr.INPUT_LABELS.index('Geometry anchor cell (/ 48; -1 absent)')
GESTURE_ANCHOR = tr.INPUT_LABELS.index('Gesture anchor cell (/ 48; -1 absent)')
MODAL_DIALOG = tr.INPUT_LABELS.index('Modal dialog open (0/1)')
REPAIRS=[tr.TOOLS.index(name) for name in ('undo','refund_selection','cancel_tool','zone_back')]


def gene(rng):
    family = int(rng.integers(len(FAMILIES)))
    return dict(family=family, tool=int(rng.choice(FAMILIES[family])),
                duration=int(rng.integers(2, 8)), x=int(rng.integers(8)),
                y=int(rng.integers(5)), dx=int(rng.integers(-2, 3)),
                dy=int(rng.integers(-2, 3)), weights=rng.normal(0, 1, 5).tolist())


def random_team(rng):
    return dict(plan=[gene(rng) for _ in range(int(rng.integers(2, 7)))],
                battle=rng.normal(0, 1, (len(CASTS), 5)).tolist(),
                cast_bias=rng.uniform(-1, 7, len(CASTS)).tolist(),
                idle_bias=float(rng.uniform(-1, 3)),
                camera_pause=rng.normal(0,2,6).tolist(),blocked_tool=int(rng.choice(REPAIRS)))


def placement_mode_candidate(parent, rng, tool):
    plan = parent['plan']
    index = next((i for i, step in enumerate(plan)
                  if step['family'] == 0 or step['tool'] in tr.PLACEMENTS), None)
    if index is None or sum(step['duration'] for step in plan) >= tr.PLAN_STEPS:
        return None
    if any(step['tool'] in PLACEMENT_MODES for step in plan):
        return None
    child = deepcopy(parent)
    preference = dict(gene(rng), family=len(FAMILIES)-1, tool=tool, duration=1)
    child['plan'].insert(index, preference)
    return child


def loadout_candidate(parent,rng):
    candidate=deepcopy(parent)
    pick=gene(rng)
    pick.update(family=2,tool=int(rng.choice(FAMILIES[2])),duration=1)
    candidate['plan'].insert(0,pick)
    if 'blocked_tool' not in candidate:candidate['blocked_tool']=int(rng.choice(REPAIRS))
    return candidate


def early_loadout_candidate(trial, rng, *, ability=None):
    team = trial.get('team')
    if not team or team.get('layout') or trial.get('arm') or fitness.l1_outbreak_seed(trial) is None:
        return None
    first = trial['levels'][0]
    saved = first.get('saved')
    opening = first.get('opening_loadout') or {}
    ready = first.get('ready_loadout') or {}
    if not isinstance(saved, (int, float)) or not 0 <= saved < .35 or not ready:
        return None
    earliest = min(ready.values())
    purchases = {tr.TOOLS[g['tool']][4:] for g in team['plan'] if g['tool'] in FAMILIES[2]}
    remaining_sp = first.get('ready_loadout_sp')
    breach = (first.get('shelter') or {}).get('first_occupied_breach')
    observed_budget = (type(remaining_sp) in (int, float) and math.isfinite(remaining_sp)
                       and remaining_sp >= 0)
    observed_breach = type(breach) in (int, float) and math.isfinite(breach) and breach > earliest
    alternatives = []
    breach_alternatives = []
    for i, step in enumerate(team['plan']):
        if step['tool'] not in FAMILIES[2]:
            continue
        name = tr.TOOLS[step['tool']][4:]
        if name not in opening or ready.get(name) != earliest:
            continue
        cost = opening[name]['cost']
        for choice, offer in opening.items():
            if ability is not None and choice != ability:
                continue
            if choice in purchases or choice in ready or choice not in tr.ABILITY_U:
                continue
            proposal = (i, tr.TOOLS.index('buy_' + choice))
            if offer['cost'] <= cost and offer['first_effect'] < earliest:
                alternatives.append(proposal)
            elif (observed_budget and observed_breach and step['duration'] == 1
                  and offer['cost'] <= cost + remaining_sp and offer['first_effect'] < breach):
                breach_alternatives.append(proposal)
    alternatives = alternatives or breach_alternatives
    if not alternatives:
        return None
    index, tool = alternatives[int(rng.integers(len(alternatives)))]
    child = deepcopy(team)
    child['plan'][index]['tool'] = tool
    return child


def missile_trial_reference(trial):
    team = trial.get('team')
    if not team or team.get('layout') or any(team.get('later_layouts', {}).values()):
        return None
    if trial.get('arm') or fitness.l1_outbreak_seed(trial) is None:
        return None
    level = trial['levels'][0]
    saved = level.get('saved')
    deployments = (level.get('battle_actions') or {}).get('logged_deployments') or ()
    if (level.get('end') not in ('won', 'lost', 'aborted') or type(saved) not in (int, float)
            or not 0 <= saved <= 1 or 'Missile' not in (level.get('ready_loadout') or {})
            or deployments.count('cruise_missile') < 2):
        return None
    return saved, trial


def fit_garrison_coverage(parent, trials, discovery_exclusions=()):
    """Fit one placement preference on discovery costs and native outcomes."""
    seen = set(discovery_exclusions)
    samples = []
    for trial in trials:
        if trial.get('phase') != 'discovery' or trial.get('team_id') != team_id(parent) or trial.get('error'):
            continue
        levels = trial.get('levels', ())
        if len(levels) != 1:
            continue
        level, = levels
        seed = fitness.l1_outbreak_seed(trial)
        if (type(seed) is not int or seed in seen or level.get('start_kind') != 'fresh'
                or level.get('end') not in ('aborted', 'won', 'lost')):
            continue
        seen.add(seed)
        shelter = level.get('shelter') or {}
        covered, exposures = shelter.get('credited_civilians'), shelter.get('exposed_civilians')
        actions = level.get('battle_actions') or {}
        gradient, score = actions.get('garrison_placement_gradient'), level.get('saved')
        if (type(covered) is not int or covered <= 0 or type(exposures) is not int
                or not 0 <= exposures <= covered or not actions.get('garrison_gradient_choices')
                or type(gradient) not in (int, float) or not math.isfinite(gradient)
                or type(score) not in (int, float) or not 0 <= score <= 1):
            continue
        exposure = exposures / covered
        samples.append(dict(seed=seed, saved=score, exposure=exposure, gradient=gradient,
                            objective=score - .35 * exposure))
    weight = parent['garrison_coverage']
    report = dict(samples=samples, input_weight=weight, fitted_weight=None)
    if len(samples) < 4:
        return None, report
    scores = np.array([sample['objective'] for sample in samples])
    centered = scores - scores.mean()
    gradients = np.array([sample['gradient'] for sample in samples])
    norm = np.linalg.norm(centered) * np.linalg.norm(gradients)
    if norm <= 1e-8:
        return None, report
    # Normalize the update and limit one discovery step to two logit-weight units.
    direction = float(centered @ gradients / norm)
    updated = float(np.clip(weight + 2. * direction, .01, 16.))
    if abs(updated - weight) < 1e-3:
        return None, report
    report['fitted_weight'] = updated
    return dict(deepcopy(parent), garrison_coverage=updated), report


def defense_placement_candidate(parent, rng):
    if len(parent['plan']) > 62:
        return None
    child = deepcopy(parent)
    step = gene(rng)
    step.update(family=0, tool=int(rng.choice(FAMILIES[0])), duration=2)
    unit = tr.PLACEMENTS[step['tool']]
    equip = dict(step, family=3, tool=tr.TOOLS.index('equip_' + unit), duration=1)
    index = int(rng.integers(len(child['plan']) + 1))
    child['plan'][index:index] = [equip, step]
    child['keep_plan_through_gestures'] = True
    return child


def has_defense_evidence(trial):
    team = trial.get('team')
    if not team or team.get('layout') or trial.get('arm') or fitness.l1_outbreak_seed(trial) is None:
        return False
    level = trial['levels'][0]
    ready = level.get('ready_stats') or {}
    saved = level.get('saved')
    return (isinstance(saved, (int, float)) and 0 <= saved <= 1
            and any(v > 0 for v in (level.get('paid_buildings') or {}).values())
            and any((ready.get(unit) or 0) > 0 for unit in ('garrisons', 'snipers', 'mortars', 'turrets')))


def speed_probe(trial):
    if not has_defense_evidence(trial):
        return None
    parent = trial['team']
    level = trial['levels'][0]
    actions = level.get('battle_actions') or {}
    if (parent.get('speed4_penalty') or not level.get('ready_paint_mode')
            or not level.get('ready_loadout') or not actions.get('cast_available')
            or actions.get('stock_decreased') != 0 or level['saved'] >= .35
            or not any(tool == FAST_SPEED for tool, _ in level.get('actions', ()))):
        return None
    return dict(deepcopy(parent), speed4_penalty=3.)


def battle_sampling_candidate(parent):
    candidate = deepcopy(parent)
    if candidate.get('sample_battle'):
        candidate.pop('sample_battle')
        candidate.pop('cast_target_mode', None)
    else:
        candidate['sample_battle'] = True
    return candidate


def planning_scale_candidate(parent, rng):
    return dict(deepcopy(parent), planning_logit_scale=float(rng.uniform(.35, .7)))


def planning_scale_neighbors(parent, evidence):
    scale = parent.get('planning_logit_scale')
    samples = evidence.get(fitness.prefix_id(parent, 1), {})
    if scale is None or not any(seed.startswith('seed/') and len(row) >= 4
                                and row[3] and row[1] >= .20 for seed, row in samples.items()):
        return []
    neighbors = []
    for value in (max(.2, scale - .10), min(1., scale + .10)):
        if value == scale:
            continue
        child = dict(deepcopy(parent), planning_logit_scale=value)
        if fitness.prefix_id(child, 1) not in evidence:
            neighbors.append(child)
    return neighbors


def defense_duration_candidate(trial, rng):
    parent = trial['team']
    remaining = tr.PLAN_STEPS - sum(step['duration'] for step in parent['plan'])
    paid = trial['levels'][0]['paid_buildings']
    eligible = [i for i, step in enumerate(parent['plan'])
                if paid.get(tr.PLACEMENTS.get(step['tool']), 0) > 0 and step['duration'] < tr.PLAN_STEPS]
    if remaining <= 0 or not eligible:
        return None
    child = deepcopy(parent)
    step = child['plan'][int(rng.choice(eligible))]
    step['duration'] += min(int(rng.integers(2, 6)), remaining, tr.PLAN_STEPS - step['duration'])
    return child


def defense_spacing_candidate(trial, rng):
    if not trial or not has_defense_evidence(trial):
        return None
    level = trial['levels'][0]
    if (level['ready_stats'].get('garrisons') or 0) < 4 or level['paid_buildings'].get('Garrison', 0) < 2:
        return None
    parent = trial['team']
    candidates = [i for i, gene in enumerate(parent['plan'])
                  if tr.PLACEMENTS.get(gene['tool']) == 'Garrison']
    if not candidates:
        return None
    child = deepcopy(parent)
    weights = child['plan'][int(rng.choice(candidates))]['weights']
    weights[2] -= float(rng.uniform(1., 2.5))
    return child


def defense_coverage_candidate(trial, rng):
    if not trial or not has_defense_evidence(trial):
        return None
    level = trial['levels'][0]
    if not level['outbreak'].get('safe_zones') or not level['paid_buildings'].get('Garrison'):
        return None
    return dict(deepcopy(trial['team']), garrison_coverage=float(rng.uniform(7., 12.)))


def shelter_order_candidate(parent):
    if not parent.get('garrison_coverage'):
        return None
    plan = parent['plan']
    placement = next((i for i, gene in enumerate(plan)
                      if gene['family'] == 0 or gene['tool'] in tr.PLACEMENTS), None)
    rectangle = next((i for i, gene in enumerate(plan) if gene['tool'] == 10), None)
    if placement is None or rectangle is None or rectangle <= placement:
        return None
    child = deepcopy(parent)
    child['plan'].insert(placement, child['plan'].pop(rectangle))
    return child


def best_defense_trial(defenders, evidence):
    return max(defenders.values(), key=lambda trial: fitness.l1_proposal_rank(evidence, trial['team']),
               default=None)


def nearby_plan_candidate(parent, rng):
    spatial_genes = [i for i, step in enumerate(parent['plan'])
                     if step['family'] in (0, 1) or step['tool'] in FAMILIES[0] + FAMILIES[1]]
    if not spatial_genes:
        return None
    child = deepcopy(parent)
    step = child['plan'][int(rng.choice(spatial_genes))]
    x, y = step['x'], step['y']
    adjacent = [(a, b) for a, b in ((x-1, y), (x+1, y), (x, y-1), (x, y+1))
                if 0 <= a < 8 and 0 <= b < 5]
    step['x'], step['y'] = adjacent[int(rng.integers(len(adjacent)))]
    return child


def l1_candidate(parent,rng):
    if not parent.get('refuge'):return offspring(parent,parent,rng)
    # Isolate the change in initial protection from changes in battle behavior.
    child=deepcopy(parent)
    scale=child['refuge']['scale']
    choices=[v for v in (.8,1.,1.15,1.3,1.45) if abs(v-scale)>.05]
    child['refuge']['scale']=float(rng.choice(choices))
    return child


def pause_variant(trial, rng):
    team = trial.get('team')
    levels = trial.get('levels', [])
    if not team or team.get('layout') or any(team.get('later_layouts', {}).values()) or not levels:
        return None
    level = levels[0]
    if (level.get('timeout_reason') != 'continuous_pause'
            or not level.get('battle_actions', {}).get('stock_decreased')):
        return None
    child = deepcopy(team)
    bias = np.asarray(child.get('camera_pause', [0.] * 6), dtype=float)
    bias[4:] += rng.normal(0, 2, 2)
    child['camera_pause'] = bias.tolist()
    return child


def cast_candidate(trial,rng):
    levels=trial.get('levels',[])
    if not levels or not trial.get('team'):return None
    first=levels[0]
    if first.get('start_kind')!='fresh' or first['stage']!=1:return None
    actions=first.get('battle_actions',{})
    if actions.get('cast_available',0)<10:
        return None
    if actions.get('cast_sampled'):
        deployments = actions.get('logged_deployments') or []
        times = actions.get('deploy_sim_seconds') or []
        saved = first.get('saved')
        # Only native deployment receipts can establish a burst of casts.
        if (not isinstance(saved, (int, float)) or not 0 <= saved < .35
                or actions.get('stock_decreased', 0) < 3
                or len(deployments) < 3 or len(set(deployments[:3])) != 1
                or len(times) < 3 or not all(isinstance(t, (int, float)) for t in times[:3])
                or not 0 <= times[0] <= times[1] <= times[2] <= times[0] + 3):
            return None
    child=deepcopy(trial['team'])
    child['cast_timing']=[float(rng.uniform(.5,7.)),float(rng.uniform(.5,6.))]
    return child


def vary_layout(layout,rng):
    if not layout:return
    index=int(rng.integers(len(layout)))
    move=rng.choice(('reorder','translate','duplicate','remove','prioritize','thin','scale_zone'))
    if move=='scale_zone':
        zones=[item for item in layout if item['kind']=='zone']
        if zones:
            item=zones[int(rng.integers(len(zones)))]
            points=np.asarray(item['points'])
            center=points.mean(axis=0)
            item['points']=(center+(points-center)*rng.uniform(.75,1.4)).tolist()
            item.pop('observed_cost',None)
    elif move=='reorder':
        layout.insert(int(rng.integers(len(layout))),layout.pop(index))
    elif move=='prioritize':
        kind=layout[index]['kind']
        layout.sort(key=lambda item:item['kind']!=kind)
    elif move=='thin':
        kind=layout[index]['kind']
        positions=[i for i,item in enumerate(layout) if item['kind']==kind]
        if len(positions)>1:
            count=int(rng.integers(1,len(positions)))
            for i in sorted(rng.choice(positions,count,replace=False),reverse=True):layout.pop(i)
    elif move=='remove':
        if len(layout)>1:layout.pop(index)
    else:
        item=deepcopy(layout[index])
        span=np.ptp(np.concatenate([a['points'] for a in layout]),axis=0)
        offset=rng.normal(size=2)*np.maximum(1.,span*.025)
        item['points']=(np.asarray(item['points'])+offset).tolist()
        item.pop('observed_cost',None)
        if move=='translate':layout[index]=item
        else:layout.insert(index+1,item)


def available_placement_neighbors(parent, rosters, rng, *, buildings_only=False):
    equipped = [set(roster) for roster in rosters]
    common = set.intersection(*equipped)
    present = set.union(*equipped)
    preferred = {step['tool'] for step in parent['plan']}
    alternatives = [tool for tool, name in tr.PLACEMENTS.items()
                    if name in common and tool not in preferred
                    and (not buildings_only or tool in tr.BUILDING_PLACEMENTS)]
    slot = next((i for i, step in enumerate(parent['plan'])
                 if step['tool'] in tr.PLACEMENTS and tr.PLACEMENTS[step['tool']] not in present),
                None)
    if slot is None or len(alternatives) < 2:
        return []
    children = []
    for tool in rng.choice(alternatives, size=2, replace=False):
        child = deepcopy(parent)
        child['plan'][slot]['tool'] = int(tool)
        children.append(child)
    return children


def preparation_variants(parent, roster, usage, rng):
    plan = parent['plan']
    placements = [i for i, step in enumerate(plan)
                  if step['family'] == 0 and step['tool'] in tr.PLACEMENTS and step['tool'] != GARRISON]
    placements.sort(key=lambda i: tr.PLACEMENTS[plan[i]['tool']] in roster)
    shelter = next((i for i, step in enumerate(plan) if step['tool'] == ZONE_RECT), None)
    if not placements or shelter is None:
        return
    supports = [tr.TOOLS.index(name) for name in ('wall', 'gate', 'corridor', 'hold')]
    unit_slot = placements[0]
    if len(placements) > 1:
        support_slot = placements[1]
    else:
        existing = [i for i, step in enumerate(plan) if step['tool'] in supports]
        if not existing:
            return
        support_slot = min(existing, key=lambda i: plan[i]['duration'])
    units = [tool for tool, name in tr.PLACEMENTS.items()
             if name in roster and tool != GARRISON]
    combinations = [(unit, support, after) for unit in units for support in supports
                    for after in (False, True)]
    ordered = rng.permutation(len(combinations))
    for index in sorted(ordered, key=lambda i: (usage[combinations[i]],
                        usage[combinations[i][0]], usage[combinations[i][1]])):
        unit, support, after = combinations[index]
        unit_step = dict(plan[unit_slot], tool=unit)
        support_step = dict(plan[support_slot], family=1, tool=support)
        changed = []
        for i, step in enumerate(plan):
            if i == min(unit_slot, shelter) and not after:
                changed.append(unit_step)
            if i not in (unit_slot, support_slot):
                changed.append(step)
            if i == shelter:
                if after:
                    changed.append(unit_step)
                changed.append(support_step)
        if changed != plan:
            yield dict(parent, plan=changed), (unit, support, after)


def live_cast_update(parent, trials, *, learn_tools=False):
    key = 'cast_bias' if learn_tools else 'battle'
    gradient_key = 'cast_tool_gradients' if learn_tools else 'cast_target_gradients'
    shape = (len(CASTS),) if learn_tools else (len(CASTS), 5)
    samples = {}
    for trial in sorted(trials, key=lambda trial: trial['copy']):
        seed = fitness.l1_outbreak_seed(trial)
        if seed is None or seed in samples or trial.get('error'):
            continue
        level = trial['levels'][0]
        saved = level.get('saved')
        if level['end'] not in ('won', 'lost', 'aborted') or not isinstance(saved, (int, float)) or not 0 <= saved <= 1:
            continue
        gradient = np.asarray(level['battle_actions'].get(gradient_key))
        if gradient.shape == shape and gradient.dtype.kind in 'fiu' and np.isfinite(gradient).all():
            samples[seed] = (saved, gradient)
    report = dict(scored_seeds=sorted(samples), step_norm=0., learned_field=key)
    if len(samples) < 2:
        return parent, report
    scores, gradients = zip(*samples.values())
    centered = np.asarray(scores) - np.mean(scores)
    gradient = np.tensordot(centered, np.asarray(gradients), axes=1) / (len(samples)-1)
    update = .5 * gradient / max(1., np.linalg.norm(gradient))
    report['step_norm'] = float(np.linalg.norm(update))
    child = dict(parent, **{key: (np.asarray(parent[key]) + update).tolist()})
    return (child if report['step_norm'] else parent), report


def target_comparison_fits(parent, trials, copy_folds, evaluation_mode, *, learn_tools=False):
    reports = {}
    folds = set(copy_folds.values())
    for fold in sorted(folds):
        batch = [trial for trial in trials
                 if len(folds) == 1 or copy_folds[trial['copy']] != fold]
        candidate, fit = live_cast_update(parent, batch, learn_tools=learn_tools)
        reference, challenger = (dict(team, cast_target_mode=evaluation_mode)
                                 for team in (parent, candidate))
        fit.update(parent=team_id(parent), reference=team_id(reference),
                   candidate=team_id(challenger), evaluation_mode=evaluation_mode,
                   exposed_seeds=sorted({seed for trial in batch
                                         if (seed := fitness.l1_outbreak_seed(trial)) is not None}),
                   fit_copies=sorted(trial['copy'] for trial in batch),
                   comparison_copies=[copy for copy, group in copy_folds.items() if group == fold],
                   team=challenger)
        reports[fold] = ((reference, challenger), fit)
    return reports


def battle_neighbors(parent, rng, target=None):
    keys = ('battle', 'cast_bias') if target is None else ('battle',)
    weights = {key: np.asarray(parent[key]) for key in keys}
    offsets = {key: rng.normal(0., .35, weights[key].shape) for key in keys}
    if target is not None:
        offsets['battle'][np.arange(len(CASTS)) != target] = 0.
    return tuple(dict(deepcopy(parent),
                      **{key: (weights[key] + sign * offsets[key]).tolist() for key in keys})
                 for sign in (-1, 1))


def offspring(parent, donor, rng, stage=1):
    child = deepcopy(parent)
    if stage>1:
        layout=child.get('later_layouts',{}).get(str(stage),[])
        vary_layout(layout,rng)
        params=child.setdefault('stage_battle',{}).setdefault(str(stage),{})
        params['blocked_tool']=int(rng.choice(REPAIRS))
        for key in ('battle','cast_bias','camera_pause'):
            base=np.asarray(params.get(key,child.get(key,np.zeros(6))))
            params[key]=(base+rng.normal(0,.35,base.shape)).tolist()
        return child
    i = int(rng.integers(max(1,len(child['plan']))))
    replacement = deepcopy(donor['plan'][int(rng.integers(len(donor['plan'])))]) if donor['plan'] and rng.random()<.5 else gene(rng)
    if child['plan']:child['plan'][i]=replacement
    elif rng.random()<.5:child['plan'].append(replacement)
    if len(child['plan']) < 7 and rng.random()<.35:
        child['plan'].insert(i, gene(rng))
    if len(child['plan']) > 1 and rng.random()<.25:
        child['plan'].pop(i)
    for key in ('battle','cast_bias'):
        base = np.asarray((donor if rng.random()<.5 else parent)[key])
        child[key] = (base + rng.normal(0,.35,base.shape)).tolist()
    child['camera_pause']=(np.asarray(child.get('camera_pause',np.zeros(6)))+rng.normal(0,2,6)).tolist()
    child['blocked_tool']=int(rng.choice(REPAIRS))
    layout=child.get('layout')
    if layout:vary_layout(layout,rng)
    if 'refuge' in child:
        for key,lo,hi in [('scale',.65,1.5),('aspect',.4,2.5),('defense_weight',.01,.5)]:
            child['refuge'][key]=float(np.clip(child['refuge'][key]*np.exp(rng.normal(0,.2)),lo,hi))
    return child


def shelter_cast_pair(defenders, evidence, rng):
    ordered = sorted(defenders.values(),
                     key=lambda trial: fitness.l1_proposal_rank(evidence, trial['team']),
                     reverse=True)
    for trial in ordered:
        level = trial['levels'][0]
        if (not level.get('ready_paint_mode') or trial['team'].get('shelter_defense')
                or not (level.get('battle_actions') or {}).get('cast_sampled')
                or not (level.get('shelter') or {}).get('exposed_civilians')):
            continue
        reference = cast_candidate(trial, rng)
        if reference is not None:
            return reference, dict(deepcopy(reference), shelter_defense=float(rng.uniform(1.5, 4.5)))
    return None


def zone_population_scores(native, legal, anchor_cell, width, height, lookahead):
    """Shared float32 corner scoring for safe-zone population coverage.

    An anchored decision scores the exact (anchor, cell) rectangles; an
    unanchored decision credits each corner, only when lookahead is
    enabled, with the best gain of any complete legal pair through it.
    Returns (scores, civilians) with float32 scores; production scoring and
    probe replay share this function so counterfactual candidates match
    bit-for-bit.
    """
    scores = np.zeros(tr.NC, dtype=np.float32)
    units = native['units']
    civilians = units['pos'][units['kind'] == 0]
    if not len(civilians):
        return scores, 0
    points = project(civilians, native['camera'], width, height)
    sheltered = np.zeros(len(civilians), dtype=bool)
    for zone in native['zones']:
        if len(zone) >= 3:
            sheltered |= tr.inside_polygon(civilians, zone)
    eligible = points[~sheltered]
    if anchor_cell is not None:
        pairs = ((anchor_cell, end) for end in legal)
    elif lookahead:
        legal_corners = set(legal)
        pairs = ((a, b) for a, b in combinations(legal, 2)
                 if a // 8 != b // 8 and a % 8 != b % 8
                 and a // 8 * 8 + b % 8 in legal_corners
                 and b // 8 * 8 + a % 8 in legal_corners)
    else:
        return scores, len(civilians)
    for first, second in pairs:
        start = tr.cell_of_px(first, width, height)
        end = tr.cell_of_px(second, width, height)
        low, high = np.minimum(start, end), np.maximum(start, end)
        inside = ((eligible >= low) & (eligible <= high)).all(axis=1)
        gain = np.count_nonzero(inside) / len(civilians)
        scores[second] = max(scores[second], gain)
        if anchor_cell is None:
            scores[first] = max(scores[first], gain)
    return scores, len(civilians)


class TeamPolicy(tr.PolicyNet2):
    def __init__(self, team, forecast=None, *, collect_cast_gradients=False,
                 collect_cast_tool_gradients=False, alternate_team=None):
        super().__init__()
        self.team = team
        self.steps = [(g, t) for g in team['plan'] for t in range(g['duration'])]
        self.index = 0
        self.coords = torch.arange(tr.NC)
        self.battle = torch.tensor(team['battle'])
        self.cast_gradients = torch.zeros_like(self.battle) if collect_cast_gradients else None
        self.bias = torch.tensor(team['cast_bias'])
        self.cast_tool_gradients = torch.zeros_like(self.bias) if collect_cast_tool_gradients else None
        self.cast_weight_delta = self.cast_bias_delta = None
        if alternate_team is not None:
            if alternate_team['battle'] != team['battle']:
                self.cast_weight_delta = torch.tensor(alternate_team['battle']) - self.battle
            if alternate_team['cast_bias'] != team['cast_bias']:
                self.cast_bias_delta = torch.tensor(alternate_team['cast_bias']) - self.bias
        self.cast_timing = team.get('cast_timing')
        self.opening_cast_bias = team.get('opening_cast_bias', 0.)
        self.opening_cast_bonus = 0.
        self.line_casts = {tool for tool, flag in ((FIREBOMB, 'firebomb_line_targeting'),
                                                   (POLICE, 'police_line_targeting')) if team.get(flag)}
        self.cast_line = None
        self.garrison_coverage_weight = team.get('garrison_coverage', 0.)
        self.garrison_building_range = team.get('garrison_building_range', False)
        self.garrison_early_coverage = team.get('garrison_early_coverage', False)
        self.garrison_coverage_cells = torch.zeros(tr.NC)
        self.garrison_placement_gradient = 0.
        self.garrison_gradient_choices = 0
        self.zone_population_weight = team.get('zone_population', 0.)
        self.zone_anchor_lookahead = team.get('zone_anchor_lookahead', False)
        self.zone_probe = None
        self.zone_population_cells = torch.zeros(tr.NC)
        self.shelter_defense = team.get('shelter_defense',0.)
        self.missile_reserve = team.get('missile_reserve',0.)
        self.missile_followup = team.get('missile_followup',0.)
        self.missile_footprint = team.get('missile_footprint',False)
        self.missile_local = None
        self.missile_wall_risk = None
        self.missile_in_flight = False
        self.missile_charges = 0.
        self.occupied_shelter = False
        self.special_probe = team.get('special_probe',0.)
        self.special_steps = 0
        self.inspected_buildings = set()
        self.special_tools = []
        self.special_cells = []
        self.shelter_perimeter = torch.zeros(tr.NC)
        self.cast_targets = torch.zeros((len(CASTS),tr.NC),dtype=torch.bool)
        self.camera_pause=torch.tensor(team.get('camera_pause',[0.]*6))
        self.predict = None if forecast is None else forecast.forward
        self.campaign_team_id=team_id(team)
        self.campaign_forecast_id=None
        self.campaign_forecast_parameters=0
        if forecast is not None:
            digest=hashlib.sha256()
            for parameter in forecast.parameters():
                digest.update(parameter.detach().cpu().numpy().tobytes())
                self.campaign_forecast_parameters+=parameter.numel()
            self.campaign_forecast_id=digest.hexdigest()[:16]

    def cast_cell_features(self, tool):
        if tool == MISSILE and self.missile_local is not None:
            return torch.cat((self.missile_local, self.cast_grid[2:]))
        if self.cast_line is not None and tool == self.cast_line[0]:
            return self.cast_grid[:, self.cast_line[1]].mean(dim=2)
        return self.cast_grid

    def record_garrison_gradient(self, cell, ranked, sampled):
        # The sampled distribution mixes the actor with 25% legal uniform exploration.
        features = self.garrison_coverage_cells
        responsibility = .75 * ranked[cell] / sampled[cell]
        self.garrison_placement_gradient += float(responsibility * (features[cell] - features @ ranked))
        self.garrison_gradient_choices += 1

    def record_cast_gradient(self, tool, cell, probabilities):
        row = CASTS.index(tool)
        features = self.cast_cell_features(tool)
        self.cast_gradients[row] += features[:, cell] - features @ probabilities

    def record_cast_tool_gradient(self, tool, probabilities):
        self.cast_tool_gradients -= probabilities[CASTS]
        if tool in CASTS:
            self.cast_tool_gradients[CASTS.index(tool)] += 1.

    def alternate_tool_distance(self, distribution):
        logits = distribution.logits.clone()
        logits[CASTS] += self.cast_bias_delta
        return float(.5 * (logits.softmax(dim=0) - distribution.probs).abs().sum())

    def alternate_cast_argmax(self, tool, distribution, legal):
        delta = self.cast_weight_delta[CASTS.index(tool)] @ self.cast_cell_features(tool)
        scores = (distribution.logits + delta).masked_fill(torch.as_tensor(legal) == 0, -torch.inf)
        return int(scores.argmax())

    def set_cast_targets(self, st, tools, cells, width, height):
        self.cast_targets.zero_()
        self.shelter_perimeter.zero_()
        self.missile_in_flight = False
        self.occupied_shelter = False
        self.missile_charges = 0.
        self.cast_line = None
        self.missile_local = None
        self.missile_wall_risk = None
        self.opening_cast_bonus = 0.
        if st['planning'] or st.get('dialog'):
            return
        if self.opening_cast_bias and not st.get('first_cast_confirmed'):
            self.opening_cast_bonus = self.opening_cast_bias * max(0., 1. - st['sim'] / 30.)
        if anchor := st.get('anchor'):
            tool, cell = anchor
            if tool in self.line_casts and tools[tool]:
                start = np.asarray(tr.battle_point(st, tool, cell, width, height))
                ends = np.asarray([tr.cell_of_px(cell, width, height) for cell in range(tr.NC)])
                points = start + (ends[:, None, :] - start) * np.linspace(0., 1., 9)[None, :, None]
                bins = grid_bins(points.reshape(-1, 2), width, height).reshape(tr.NC, 9)
                self.cast_line = (tool, torch.from_numpy(bins))
            return
        boundary = st.get('playarea_boundary')
        if boundary is None:
            return
        centers = [tr.cell_of_px(cell,width,height) for cell in range(tr.NC)]
        inside = tr.inside_polygon(centers,boundary)
        if (self.shelter_defense or self.missile_reserve) and st.get('shelter') and st.get('native'):
            self.occupied_shelter = bool(st['shelter'].protected)
            camera = st['native']['camera']
            world = (np.asarray(centers)-[width/2,height/2])/[camera[2],-camera[2]]+camera[:2]
            self.shelter_perimeter = torch.from_numpy(st['shelter'].perimeter(world))
        for row,tool in enumerate(CASTS):
            if not tools[tool]:
                continue
            eligible = tr.cell_mask(st,tool,cells).astype(bool)
            if tool in st.get('battle_targets',{}):
                points = [tr.battle_point(st,tool,cell,width,height) for cell in range(tr.NC)]
                eligible &= tr.inside_polygon(points,boundary)
            else:
                eligible &= inside
            self.cast_targets[row] = torch.from_numpy(eligible)
        if self.missile_footprint and self.cast_targets[MISSILE_ROW].any() and st.get('native'):
            legal = self.cast_targets[MISSILE_ROW].numpy()
            pixels = [tr.battle_point(st, MISSILE, int(cell), width, height) for cell in np.flatnonzero(legal)]
            context = tr.missile_target_context(st, pixels, width, height)
            if context is not None:
                _, counts, risk = context
                self.missile_local = torch.zeros(2, tr.NC)
                self.missile_local[:, legal] = torch.from_numpy(np.log1p(counts.astype(np.float32)))
                if risk is not None:
                    self.missile_wall_risk = torch.zeros(tr.NC, dtype=torch.bool)
                    self.missile_wall_risk[legal] = torch.from_numpy(risk)
        if (self.missile_followup or self.missile_reserve) and self.cast_targets[MISSILE_ROW].any():
            missile = next((slot for slot in st.get('deck',[]) if slot['name']=='Missile'),None)
            if missile:
                self.missile_in_flight = st['sim'] < missile.get('last_cast_t',-np.inf)+missile.get('flight',0.)
                if self.occupied_shelter:
                    self.missile_charges = missile['charges']

    def set_garrison_coverage(self, st, tools, cells, width, height):
        self.garrison_coverage_cells.zero_()
        native = st.get('native')
        if not tools[GARRISON] or not native or not native['zones'] or not st.get('build_targets'):
            return
        rules = st.get('rules', {})
        radius = tr._rule(rules, 'Garrison', '_range_max', default=-1.)
        if not np.isfinite(radius) or radius < 0 or (not self.garrison_building_range and radius == 0):
            return
        legal = np.flatnonzero(tr.cell_mask(st, GARRISON, cells))
        targets = np.array([st['build_targets'][i] for i in legal], dtype=float).reshape(-1, 2)
        camera = native['camera']
        world = (targets - [width / 2, height / 2]) / [camera[2], -camera[2]] + camera[:2]
        units = native['units']
        defenders = units['pos'][units['kind'] == 6]
        existing_radius = radius
        if self.garrison_building_range:
            base = tr._rule(rules, 'Garrison', '_range_base', default=-1.)
            per_metre = tr._rule(rules, 'Garrison', '_range_per_meter', default=-1.)
            if not (np.isfinite(base) and np.isfinite(per_metre) and base >= 0. and per_metre >= 0.):
                return
            buildings = native['buildings']
            native_radius = garrison_reach(buildings['area'], base, per_metre, radius)
            matches = (defenders[:, None] == buildings['center']).all(axis=-1)
            existing_radius = np.max(np.where(matches, native_radius, 0.), axis=1, initial=0.)
            radius = garrison_reach(np.asarray(st['build_areas'])[legal], base, per_metre, radius)
        if self.garrison_early_coverage:
            delay = tr._rule(rules, 'SafeZone', '_outside_first_shot_seconds')
            if np.isfinite(delay) and delay > 0.:
                civilians = units['pos'][units['kind'] == 0]
                occupied = [zone for zone in native['zones'] if len(zone) >= 3
                            and tr.inside_polygon(civilians, zone).any()]
                inside_defenders = np.zeros(len(defenders), dtype=bool)
                inside_targets = np.zeros(len(world), dtype=bool)
                for zone in occupied:
                    inside_defenders |= tr.inside_polygon(defenders, zone)
                    inside_targets |= tr.inside_polygon(world, zone)
                defenders, existing_radius = defenders[inside_defenders], existing_radius[inside_defenders]
                radius = np.where(inside_targets, radius, 0.)
        gain = garrison_perimeter_gain(native['zones'], defenders, world, radius, existing_radius)
        self.garrison_coverage_cells[legal] = torch.from_numpy(gain)

    def set_zone_population(self, st, tools, cells, width, height):
        self.zone_population_cells.zero_()
        anchor = st.get('anchor')
        native = st.get('native')
        if not tools[ZONE_RECT] or not native:
            return
        if (anchor and anchor[0] != ZONE_RECT) or (not anchor and not self.zone_anchor_lookahead):
            return
        legal = np.flatnonzero(tr.cell_mask(st, ZONE_RECT, cells))
        scores, _ = zone_population_scores(
            native, legal, None if anchor is None else anchor[1], width, height,
            self.zone_anchor_lookahead)
        self.zone_population_cells.copy_(torch.from_numpy(scores))

    def zone_lookahead_counterfactual(self, st, width, height):
        """Lookahead candidate logits on the same native snapshot the probed
        forward just scored, replaying the production float32 operation
        order (zone bias, then plan grid term, then distance) from the
        stashed pre-bias logits. Pure scoring: no forward pass, no plan
        index mutation, no RNG.
        """
        probe = self.zone_probe
        legal = np.flatnonzero(np.asarray(probe['legal_cells']))
        scores, _ = zone_population_scores(st['native'], legal, None, width, height, True)
        logits = probe['pre_zone_logits'] + self.zone_population_weight * torch.from_numpy(scores)
        if 'plan_grid' in probe:
            logits = logits + probe['plan_grid'] - probe['plan_distance']
        return scores, logits

    def set_special_probe(self, st, width, height):
        self.special_tools = []
        self.special_cells = []
        if (not st['planning'] or not st.get('native') or self.special_steps>=6
                or self.index<len(self.steps) or st.get('anchor') or st.get('gesture_anchor')):
            return
        native = st['native']
        if not native['zones']:
            return
        self.special_steps += 1
        selected = native['selection']['building']
        if selected>=0:
            self.inspected_buildings.add(selected)
        self.special_tools = [BUILDING_SPECIALS[key] for key in st['hud']['actions'] if key in BUILDING_SPECIALS]
        if not self.special_tools:
            buildings = native['buildings']
            viable = np.flatnonzero((buildings['class']>0)&(buildings['destroyed']==0)&(buildings['ability']==0))
            viable = [i for i in viable if i not in self.inspected_buildings]
            if viable and native['zones']:
                points = project(buildings['center'][viable],native['camera'],width,height).astype(int)
                candidates = {tuple(point):i for point,i in zip(points,viable)}
                for cell,point in enumerate(st['targets']['building']):
                    index = candidates.get(point)
                    if index is None:
                        continue
                    left,bottom,right,top = buildings['rect'][index]
                    corners = [(left,bottom),(left,top),(right,bottom),(right,top)]
                    if any(tr.inside_polygon(corners,zone).all() for zone in native['zones']):
                        self.special_cells.append(cell)

    def forward(self, x, h=None):
        tools, cells, value, h = super().forward(x, h)
        grid = x[0,0,GRID_START:GRID_START+5*tr.NC].reshape(5,tr.NC)
        cells = cells.reshape(tr.NU,tr.NC)
        if x[0,0,tr.PLANNING_INDEX]:
            probe = self.zone_probe
            if probe is not None:
                probe['pre_zone_logits'] = cells[ZONE_RECT].clone()
            if self.garrison_coverage_weight:
                cells[GARRISON] += self.garrison_coverage_weight * self.garrison_coverage_cells
            if self.zone_population_weight:
                cells[ZONE_RECT] += self.zone_population_weight * self.zone_population_cells
            if self.index < len(self.steps):
                g, t = self.steps[self.index]
                scale = self.team.get('planning_logit_scale')
                if scale is not None:
                    tools = tools * scale
                tools[..., FAMILIES[g['family']]] += 5
                tools[..., g['tool']] += 7
                px, py = (g['x']+t*g['dx'])%8, (g['y']+t*g['dy'])%5
                distance = (self.coords%8-px).abs()+(self.coords//8-py).abs()
                plan = torch.tensor(g['weights']) @ grid
                if probe is not None:
                    probe.update(plan_grid=plan, plan_distance=distance)
                cells = cells + plan - distance
                if not self.team.get('keep_plan_through_gestures') or (
                    x[0,0,GEOMETRY_ANCHOR] < 0 and x[0,0,GESTURE_ANCHOR] < 0
                    and not x[0,0,MODAL_DIALOG]
                ):
                    self.index += 1
            else:
                tools[...,tr.TOOLS.index('ready')] += 15
                if self.special_tools:
                    tools[...,self.special_tools] += self.special_probe
                elif self.special_cells:
                    tools[...,SELECT_BUILDING] += self.special_probe
                    cells[SELECT_BUILDING,self.special_cells] += self.special_probe
                if 'blocked_tool' in self.team and not x[0,0,READY_LEGAL]:
                    tools[...,self.team['blocked_tool']]+=12
        else:
            if self.team.get('speed4_penalty'):
                tools[..., FAST_SPEED] -= self.team['speed4_penalty']
            tools[...,PAN]+=self.camera_pause[:4]
            tools[...,PAUSE]+=self.camera_pause[4+int(x[0,0,PAUSED].item()!=0)]
            if self.predict is not None:
                future=self.predict(grid[:3].reshape(1,3,6,8)).clamp_min(0).reshape(2,tr.NC)
                grid=torch.cat((future,grid[2:]))
            tools[..., CASTS] += self.bias + self.opening_cast_bonus
            if self.cast_timing is not None:
                gain, threshold = self.cast_timing
                demand = grid[1] - .75*grid[0] - threshold
                defense = self.shelter_defense*self.shelter_perimeter*(grid[1]/3).tanh()
                demand = demand+defense
                if self.shelter_defense:
                    cells[CASTS] += defense*self.cast_targets
                best = demand.expand_as(self.cast_targets).masked_fill(~self.cast_targets,-torch.inf).amax(dim=-1)
                tools[...,CASTS] += gain*torch.where(self.cast_targets.any(dim=-1), best.tanh(), 0.)
            if self.missile_in_flight:
                tools[...,MISSILE] -= self.missile_followup
            if self.missile_charges>0:
                pressure = self.shelter_perimeter*(grid[1]/3).tanh()
                legal_pressure = pressure*self.cast_targets[MISSILE_ROW]
                tools[...,MISSILE] -= self.missile_reserve*(1.-legal_pressure.max())/self.missile_charges
                cells[MISSILE] += self.missile_reserve*legal_pressure
            tools[...,tr.TOOLS.index('wait')] += self.team['idle_bias']
            if self.cast_gradients is not None or self.cast_weight_delta is not None:
                self.cast_grid = grid
            scores = self.battle @ grid
            if self.missile_local is not None:
                scores[MISSILE_ROW] += self.battle[MISSILE_ROW, :2] @ (self.missile_local - grid[:2])
            if self.missile_wall_risk is not None:
                scores[MISSILE_ROW] -= 2. * self.missile_wall_risk
            if self.cast_line is not None:
                tool, bins = self.cast_line
                row = CASTS.index(tool)
                segments = grid[:, bins].mean(dim=2)
                scores[row] = self.battle[row] @ segments
            cells[CASTS] += scores
        return tools, cells.reshape(1,1,-1), value, h


def score(row, *, goal_margin=False):
    # Retain official outcomes first. Failed boards get a search gradient from
    # simulated survival time. A paused wall-clock minute adds zero area.
    floor = .35 if goal_margin else 0.
    last = area = 0.
    for sim, civ, *_ in row['trail']:
        stop = min(120., max(last, sim))
        area += (stop-last) * max(0., min(1., civ / row['civ0']) - floor)
        last = stop
    return [int(bool(row['advance'])), int(bool(row['win'])),
            float(row['saved_frac'] or 0.) if row['win'] else 0., area / (120. * (1. - floor))]


def rollout(job, retries=0, start_stage=1, *, training=False, observe=False, observer_interval=.2,
            practice_retry=False, allow_progression=False, capture_shadow=False, fixed_speed=None,
            fast_boot=False, click_start=False, goal_margin=False, collect_cast_gradients=False,
            collect_cast_tool_gradients=False, alternate_team=None, collect_garrison_gradient=False,
            zone_lookahead_probe=False):
    timing = {'started': monotonic()}
    if start_stage>1 and not allow_progression:
        raise ValueError('Later-stage starts require explicit campaign progression')
    copy, weights, team, seed, *forecast_path = job
    forecast=None
    if forecast_path:
        from crowd_forecast import CrowdForecast
        forecast=CrowdForecast().eval()
        forecast.load_state_dict(torch.load(forecast_path[0],weights_only=True))
    destination=('campaign','continue' if start_stage>1 else 'stage1')
    env=None
    levels=[]
    result=dict(copy=copy,seed=seed,levels=levels,timing=timing)
    stage,attempt=start_stage,0
    try:
        copy_dir = operator.owned_copy(copy)
        boot_options = {'discard_dump_states': True}
        if click_start:
            boot_options['click_start'] = True
        if fast_boot:
            try:
                env = zar_boot.boot(copy_dir, destination, welcome_wait=15, **boot_options)
            except zar_boot.ZAREnvError as error:
                print(f'{copy} fast boot failed: {error}. Retrying with standard warmup.', flush=True)
            timing['fast_boot'] = env is not None
        if env is None:
            env = zar_boot.boot(copy_dir, destination, **boot_options)
        if click_start:
            result['initial_paint_mode'] = False  # Native state was verified by boot.
            result['initial_planning_roster'] = Controls(env).planning_roster()
        timing['board_ready'] = monotonic()
        layout_receipts=[]
        while stage <= 5:
            layout = (team or {}).get('layout',[]) if stage==1 else (team or {}).get('later_layouts',{}).get(str(stage),[])
            receipts=[]
            refuge=None
            relocation=None
            if layout or start_stage>1:
                env.to_planning()
                board=env.dump()
                if not board or not board['where']['stage'].startswith(f'{stage-1} '):
                    raise RuntimeError(f'Expected live Boston stage {stage}')
            if layout:
                from layout_memory import apply_layout, remaining_layout, BUILDINGS
                from native_state import VEC
                origin=np.array([env.scalar(r,'<f') for r in (0x665358,0x66535c)])
                boundary=env.array(0x6652e0,VEC,limit=10000)+origin
                if stage==1 and team.get('refuge'):
                    from layout_memory import fit_refuge
                    points=env.array(0x650280,VEC)
                    kinds=env.array(0x6502d0,'u1')
                    if len(points)!=len(kinds):raise RuntimeError('Inconsistent planning population')
                    layout,refuge=fit_refuge(layout,points[kinds==0]+origin,boundary,team['refuge'])
                if stage==1 and attempt==0 and team.get('garrison_relocation') is not None:
                    from layout_memory import relocate_garrison
                    points=env.array(0x658d98,VEC)+origin
                    layout,relocation=relocate_garrison(layout,points,team['garrison_relocation'])
                occupied=[unit for kind,unit in BUILDINGS.items() if f'board {kind} = ' in board['_text']]
                receipts=apply_layout(env,remaining_layout(layout,board),occupied,boundary=boundary)
                if stage==1 and attempt==0:layout_receipts=receipts
            active={**team,**team.get('stage_battle',{}).get(str(stage),{})} if team else None
            start_kind='carry' if attempt else ('fresh' if stage==1 else
                                                'continue' if stage==start_stage else 'next_level')
            options=dict(start_kind=start_kind,seed=seed,record_layout=bool(layout),greedy=True,
                         allow_progression=allow_progression, observer_interval=observer_interval,
                         paused_seconds=45,
                         placement_feedback=not allow_progression and not layout,
                         sample_battle=bool((active or {}).get('sample_battle')),
                         cast_target_mode=(active or {}).get('cast_target_mode'),
                         sample_loadout=bool((active or {}).get('sample_loadout')),
                         sample_garrison_sites=bool((active or {}).get('sample_garrison_sites')),
                         sample_zone_geometry=bool((active or {}).get('sample_zone_geometry')))
            if collect_garrison_gradient:options['collect_garrison_gradient']=True
            if capture_shadow:options['capture_shadow']=True
            if fixed_speed:options['fixed_speed']=fixed_speed
            if collect_cast_gradients:options['collect_cast_gradients']=True
            if collect_cast_tool_gradients:options['collect_cast_tool_gradients']=True
            if zone_lookahead_probe:options['zone_lookahead_probe']=True
            if alternate_team is not None:
                options['audit_cast_targets'] = alternate_team['battle'] != active['battle']
                options['audit_cast_tools'] = alternate_team['cast_bias'] != active['cast_bias']
            episode_started = monotonic()
            row = tr.run_episode((env.pid,weights,False,f'search/{seed}/L{stage}/a{attempt}',options),
                                 policy_factory=(lambda:TeamPolicy(active,forecast,
                                     collect_cast_gradients=collect_cast_gradients,
                                     collect_cast_tool_gradients=collect_cast_tool_gradients,
                                     alternate_team=alternate_team)) if active else None,
                                 telemetry=observe)
            episode_finished = monotonic()
            if not tr.valid_trajectory(row):
                result.update(failed_stage=stage,failed_attempt=attempt,error=row.get('err','invalid trajectory'))
                tool = row.get('last_tool')
                if isinstance(tool, int) and 0 <= tool < len(tr.TOOLS):
                    result['failed_action'] = dict(tool=tr.TOOLS[tool], cell=row.get('last_cell'),
                                                   phase=row.get('phase'))
                break
            levels.append(dict(stage=row['scenario'],end=row['end'],saved=row['saved_frac'],
                               win=row['win'],advance=row['advance'],campaign=row['campaign'],
                               attempt=attempt,start_kind=start_kind,
                               timing=dict(started=episode_started, battle_started=row.get('battle_started'),
                                           finished=episode_finished),
                               refuge=refuge,garrison_relocation=relocation,
                               outbreak=row.get('outbreak'),
                               ready_stats=row.get('ready_stats'),
                               ready_paint_mode=row.get('ready_paint_mode'),
                               ready_paint_tiles=row.get('ready_paint_tiles'),
                               ready_embedded_defenses=row.get('ready_embedded_defenses'),
                               ready_preparation=row.get('ready_preparation'),
                               ready_zones=row.get('ready_zones'),
                               opening_loadout=row.get('opening_loadout', {}),
                               ready_loadout=row.get('ready_loadout', {}),
                               ready_loadout_sp=row.get('ready_loadout_sp'),
                               timeout_reason=row.get('timeout_reason'),planning_blockers=row.get('planning_blockers'),
                               unmatched_layout=remaining_layout(layout,{'_text':row['layout_text']}) if layout else [],
                               layout_receipts=receipts,battle_actions=row['battle_actions'],
                               selected_placements=row.get('selected_placements',{}),
                               paid_buildings=row.get('paid_buildings',{}),
                               unconfirmed_buildings=row.get('unconfirmed_buildings',{}),
                               building_receipts=row.get('building_receipts',[]),
                               outside_playarea_actions=row.get('outside_playarea_actions',0)+
                                   sum(r.get('result')=='outside_playarea' for r in receipts),
                               playarea_cost=tr.OUTSIDE_PLAYAREA_COST/tr.SAVED_REWARD_SCALE,
                               outside_targets=row.get('outside_targets',{}),
                               reward_components=row.get('reward_components',{}),
                               shelter=row.get('shelter',{}),
                               special_activations=row.get('special_activations',{}),
                               special_objective=row.get('reward_components',{}).get('special_activation',0.)/tr.SAVED_REWARD_SCALE,
                               shelter_objective=sum(row.get('reward_components',{}).get(k,0.)
                                   for k in ('shelter','occupied_breach'))/tr.SAVED_REWARD_SCALE,
                               score=score(row, goal_margin=goal_margin),sim=row['sim'],board=row['board_id'],
                               actions=list(zip(row['us'],row['cs'])),log_started=row['log_started']))
            if capture_shadow and 'shadow' in row:
                levels[-1]['shadow'] = dict(row['shadow'], copy=copy,
                                             team=team_id(active) if active else None)
            if row['advance']:
                if not allow_progression or row['scenario']==row['board'].get('scenario_count'):break
                stage+=1
                attempt=0
            elif allow_progression and (stage>1 or (practice_retry and training and row['win'])) and attempt<retries and row['end'] in ('aborted','lost','won'):
                attempt+=1
            else:
                break
        result['layout_receipts']=layout_receipts
    except (RuntimeError,OSError,ValueError) as exc:
        result.update(failed_stage=stage,failed_attempt=attempt,error=str(exc))
    finally:
        if env is not None:
            try:zar_boot.stop(env)
            except psutil.TimeoutExpired as exc:
                result['cleanup_error']=str(exc)
                print('game exit unconfirmed',copy,env.pid,exc,flush=True)
        timing['finished'] = monotonic()
    return result


def team_id(team):
    return hashlib.sha256(json.dumps(team,sort_keys=True).encode()).hexdigest()[:16]


def checkpoint_team(record,base):
    """Only reviewed strategy fields may enter a public model bundle."""
    from layout_memory import BUILDINGS
    team=record['team']
    def fields(obj,required=(),optional=()):
        if not isinstance(obj,dict) or not set(required)<=obj.keys()<=set(required)|set(optional):
            raise ValueError('Unexpected campaign strategy fields')
    def numeric(value,shape):
        a=np.asarray(value)
        if a.shape!=shape or a.dtype.kind not in 'fiu' or not np.isfinite(a).all():
            raise ValueError('Invalid campaign strategy numbers')
    def battle(obj):
        for k,shape in [('battle',(len(CASTS),5)),('cast_bias',(len(CASTS),)),('camera_pause',(6,))]:
            if k in obj:numeric(obj[k],shape)
        if 'cast_timing' in obj:
            numeric(obj['cast_timing'],(2,))
            gain,threshold=obj['cast_timing']
            if not (0<=gain<=8 and 0<=threshold<=8):
                raise ValueError('Invalid campaign cast timing')
        if 'missile_followup' in obj:
            numeric(obj['missile_followup'],())
            if not 0<=obj['missile_followup']<=16:
                raise ValueError('Invalid missile follow-up weight')
        if 'missile_reserve' in obj:
            numeric(obj['missile_reserve'],())
            if not 0<=obj['missile_reserve']<=8:
                raise ValueError('Invalid missile reserve weight')
        if 'shelter_defense' in obj:
            numeric(obj['shelter_defense'],())
            if not 0<=obj['shelter_defense']<=8:
                raise ValueError('Invalid shelter defense weight')
        if 'special_probe' in obj:
            numeric(obj['special_probe'],())
            if not 0<=obj['special_probe']<=24:
                raise ValueError('Invalid special-building probe weight')
        if 'blocked_tool' in obj and (type(obj['blocked_tool'])!=int or obj['blocked_tool'] not in REPAIRS):
            raise ValueError('Invalid campaign recovery action')
    fields(team,('plan','battle','cast_bias','idle_bias'),('layout','later_layouts','stage_battle','camera_pause','blocked_tool','refuge','cast_timing','shelter_defense','special_probe','missile_reserve','garrison_relocation','missile_followup','missile_footprint','keep_plan_through_gestures','planning_logit_scale','sample_battle','cast_target_mode','sample_loadout','sample_garrison_sites','opening_cast_bias','sample_zone_geometry','firebomb_line_targeting','police_line_targeting','garrison_coverage','garrison_building_range','garrison_early_coverage','zone_population','zone_anchor_lookahead','speed4_penalty'))
    if 'opening_cast_bias' in team:
        weight = team['opening_cast_bias']
        if type(weight) not in (int, float) or not 0 < weight <= 4.:
            raise ValueError('Invalid opening cast bias')
    for flag in ('firebomb_line_targeting', 'police_line_targeting', 'missile_footprint'):
        if flag in team and team[flag] is not True:
            raise ValueError(f'Invalid {flag} flag')
    if 'keep_plan_through_gestures' in team and team['keep_plan_through_gestures'] is not True:
        raise ValueError('Invalid gesture planning flag')
    if 'sample_battle' in team and team['sample_battle'] is not True:
        raise ValueError('Invalid battle sampling flag')
    if 'cast_target_mode' in team and (
            team['cast_target_mode'] not in ('sample', 'greedy') or not team.get('sample_battle')):
        raise ValueError('Cast target mode requires sampled battle tools')
    for flag in ('sample_loadout', 'sample_garrison_sites'):
        if flag in team and team[flag] is not True:
            raise ValueError(f'Invalid sampling flag: {flag}')
    if 'sample_zone_geometry' in team and team['sample_zone_geometry'] is not True:
        raise ValueError('Invalid safe-zone geometry sampling flag')
    if 'garrison_coverage' in team:
        weight = team['garrison_coverage']
        if type(weight) not in (int, float) or not 0 <= weight <= 16:
            raise ValueError('Invalid Garrison coverage weight')
    if 'garrison_building_range' in team and (
            team['garrison_building_range'] is not True or not team.get('garrison_coverage')):
        raise ValueError('Building-specific Garrison range requires coverage')
    if 'garrison_early_coverage' in team and (
            team['garrison_early_coverage'] is not True or not team.get('garrison_building_range')):
        raise ValueError('Early Garrison coverage requires building-specific range')
    if 'zone_population' in team:
        weight = team['zone_population']
        if type(weight) not in (int, float) or not 0 <= weight <= 16:
            raise ValueError('Invalid safe-zone population weight')
    if 'zone_anchor_lookahead' in team and (
            team['zone_anchor_lookahead'] is not True or not team.get('zone_population')):
        raise ValueError('Safe-zone anchor lookahead requires population coverage')
    if 'speed4_penalty' in team:
        value = team['speed4_penalty']
        if type(value) not in (int, float) or not 0 < value <= 12:
            raise ValueError('Invalid maximum battle speed preference')
    if 'planning_logit_scale' in team:
        scale = team['planning_logit_scale']
        if type(scale) not in (int, float) or not .2 <= scale <= 1.:
            raise ValueError('Invalid planning logit scale')
    battle(team)
    numeric(team['idle_bias'],())
    if not isinstance(team['plan'],list) or len(team['plan'])>64:raise ValueError('Invalid campaign plan')
    for g in team['plan']:
        fields(g,('family','tool','duration','x','y','dx','dy','weights'))
        for k,low,high in [('family',0,len(FAMILIES)-1),('tool',0,tr.NU-1),('duration',1,60),
                           ('x',0,7),('y',0,4),('dx',-7,7),('dy',-5,5)]:
            if type(g[k])!=int or not low<=g[k]<=high:raise ValueError('Invalid campaign planning gene')
        numeric(g['weights'],(5,))
    for k in ('later_layouts','stage_battle'):fields(team.get(k,{}),optional=('2','3','4','5'))
    for override in team.get('stage_battle',{}).values():
        fields(override,optional=('battle','cast_bias','camera_pause','blocked_tool','cast_timing','shelter_defense','missile_reserve','missile_followup'))
        battle(override)
    if 'garrison_relocation' in team:
        numeric(team['garrison_relocation'],(2,))
        if any(type(value) is not int or not 0<=value<128 for value in team['garrison_relocation']):
            raise ValueError('Invalid garrison relocation')
    if 'refuge' in team:
        fields(team['refuge'],('scale','aspect','defense_weight'))
        for value in team['refuge'].values():numeric(value,())
        if min(team['refuge']['scale'],team['refuge']['aspect'])<=0:raise ValueError('Invalid refuge geometry')
    for layout in [team.get('layout',[]),*team.get('later_layouts',{}).values()]:
        if not isinstance(layout,list) or len(layout)>4096:raise ValueError('Invalid campaign layout')
        for a in layout:
            fields(a,('kind','points'),('observed_cost',))
            kind=a['kind']
            if kind not in (*BUILDINGS,'gate','zone','wall','hold','corridor'):raise ValueError('Unknown placement')
            n=len(a['points'])
            if not (3<=n<=128 if kind=='zone' else n==(2 if kind in ('wall','hold','corridor') else 1)):
                raise ValueError('Invalid placement geometry')
            numeric(a['points'],(n,2))
            if 'observed_cost' in a:
                numeric(a['observed_cost'],())
                if a['observed_cost']<0:raise ValueError('Invalid placement cost')
    if record['base']!=base or record['team_id']!=team_id(team):raise ValueError('Campaign policy identity mismatch')
    return dict(base=base,team_id=record['team_id'],team=team)


def restore_team(net,directory):
    if (directory/'champion.json').is_file():
        record=json.loads((directory/'champion.json').read_text())
        net.load_state_dict(torch.load(directory/'base.pt',weights_only=True))
    else:
        from checkpoints import verify_bundle
        record=verify_bundle(directory).get('campaign_team')
        if not record:raise ValueError('This checkpoint bundle has no campaign team')
        tr.load_pretrained(net,directory/'nn_policy4.pt')
    return checkpoint_team(record,tr.policy_id(net))['team']


def restore_layout_free_proposal(net, directory):
    record = json.loads((directory/'provisional.json').read_text())
    net.load_state_dict(torch.load(directory/'base.pt', weights_only=True))
    team = checkpoint_team(record, tr.policy_id(net))['team']
    if team.get('layout') or any(team.get('later_layouts', {}).values()):
        raise ValueError('Layout-free continuation cannot use layout replay')
    return team


def restore_fitted_pair(directory, base):
    fit = json.loads((directory/'target-fit.json').read_text())
    if 'folds' in fit:
        selected = json.loads((directory/'provisional.json').read_text())['team_id']
        fit = next((report for report in fit['folds'] if report['candidate'] == selected), None)
        if fit is None:
            raise ValueError('Cross-fit retest requires a selected learned challenger')
    candidate = checkpoint_team(dict(base=base, team_id=fit['candidate'], team=fit['team']), base)['team']
    reference = None
    fit_outbreaks = set(fit.get('exposed_seeds', fit['scored_seeds']))
    fit_copies = fit.get('fit_copies')
    for trial in records(directory/'trials.jsonl'):
        if trial.get('generation') == 0 and (fit_copies is None or trial['copy'] in fit_copies):
            seed = fitness.l1_outbreak_seed(trial)
            if seed is not None:
                fit_outbreaks.add(seed)
        if trial.get('team_id') == fit['reference']:
            reference = checkpoint_team(dict(base=base, team_id=fit['reference'], team=trial['team']), base)['team']
    field = fit.get('learned_field', 'battle')
    if field not in ('battle', 'cast_bias') or reference is None or candidate == reference:
        raise ValueError('Expected distinct saved reference and challenger policies')
    if dict(candidate, **{field: reference[field]}) != reference:
        raise ValueError('Expected a saved reference and challenger that differ only in the learned weights')
    return (reference, candidate), fit_outbreaks


def save_frozen_base(directory, weights, continuation):
    target = directory / 'base.pt'
    if continuation is not None:
        source = (continuation / 'base.pt').resolve()
        if source.parent.parent == directory.parent.resolve() and source.parent.name.startswith('coverage-team-'):
            # Completed search bases are immutable. Keep the resume path without another data copy.
            try:
                os.link(source, target)
            except OSError:
                pass
            else:
                return
    torch.save(weights, target)


def holdout_assignments(copies, weights, challenger, incumbent, seed, wave):
    jobs = []
    arms = {}
    for index,copy in enumerate(copies):
        candidate = (index+wave)%2==0
        team = challenger if candidate else incumbent
        jobs.append((copy,weights,team,seed+wave*len(copies)+index//2))
        arms[copy] = ('extra' if index>=2*(len(copies)//2) else
                      'candidate' if candidate else 'incumbent' if incumbent else 'gru')
    return jobs,arms


def shadow_variants(champion):
    timing = deepcopy(champion)
    targeting = deepcopy(champion)
    timing['cast_bias'][MISSILE_ROW] -= 3.
    targeting['battle'][MISSILE_ROW][0] -= 2.
    return {'control': champion, 'timing': timing, 'civilian_avoidance': targeting}


def completed_rollouts(pool,jobs,starts=None,retries=0,training=False, *, allow_progression=False,
                       capture_shadow=False, speeds=None, fast_boot=False, click_start=False, goal_margin=False,
                       collect_cast_gradients=False, collect_cast_tool_gradients=False, alternate_teams=None,
                       collect_garrison_gradient=False, zone_lookahead_probe=False):
    if jobs:
        operator.require_resource_headroom(len(jobs))
    if starts is None:starts=[1]*len(jobs)
    primary = next((job for job in jobs if job[2]), jobs[0] if jobs else None)
    practice_copy=next((j[0] for j,stage in zip(jobs,starts) if training and j[2] and stage==1),None)
    futures={pool.submit(rollout,job,retries,stage,training=training,observe=True,
                         observer_interval=.2 if training and job is primary else 1.,
                         practice_retry=job[0]==practice_copy,allow_progression=allow_progression,
                         capture_shadow=capture_shadow, fast_boot=fast_boot, click_start=click_start,
                         goal_margin=goal_margin, collect_cast_gradients=collect_cast_gradients,
                         collect_cast_tool_gradients=collect_cast_tool_gradients,
                         collect_garrison_gradient=collect_garrison_gradient,
                         zone_lookahead_probe=zone_lookahead_probe,
                         alternate_team=(alternate_teams or {}).get(job[0]),
                         fixed_speed=speeds[job[0]] if speeds else None):(job,stage)
             for job,stage in zip(jobs,starts,strict=True)}
    for future in as_completed(futures):
        job,stage=futures[future]
        try:result=future.result()
        except Exception as exc:result=dict(copy=job[0],seed=job[3],levels=[],error=str(exc),failed_stage=stage)
        yield job,stage,result


def budget_candidate(team,levels,prices=None):
    if not team:return None
    if prices is None:prices={}
    layouts={'1':team.get('layout',[]),**team.get('later_layouts',{})}
    def key(stage,action):
        points = [[float(x),float(y)] for x,y in action['points']]
        return json.dumps([stage,action['kind'],points],separators=(',',':'))
    for stage in levels:
        for receipt in stage.get('layout_receipts',[]):
            if receipt.get('after',0)>=0 or receipt['before']<=0:continue
            number=str(stage['stage'])
            layout=layouts.get(number,[])
            matches=[a for a in layout if a['kind']==receipt['kind'] and
                     ('world_points' not in receipt or a['points']==receipt['world_points'])]
            if len(matches)==1:
                where=key(number,matches[0])
                prices[where]=min(prices.get(where,float('inf')),receipt['before']-receipt['after'])
    changes=[(stage,i,prices[key(stage,a)]) for stage,layout in layouts.items() for i,a in enumerate(layout)
             if key(stage,a) in prices and a.get('observed_cost')!=prices[key(stage,a)]]
    if not changes:return None
    child=deepcopy(team)
    for stage,i,price in changes:
        layout=child['layout'] if stage=='1' else child['later_layouts'][stage]
        layout[i]=dict(layout[i],observed_cost=price)
    return child


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copies',nargs='+',required=True)
    parser.add_argument('--qualified-holdout-only', action='store_true',
                        help='Defer reserved evaluation until a discovery policy qualifies')
    parser.add_argument('--holdout-copies', nargs='+',
                        help='Reserve separate owned copies for the final frozen evaluation')
    neighbors = parser.add_mutually_exclusive_group()
    neighbors.add_argument('--placement-neighbors', action='store_true',
                           help='Compare two equipped placement preferences in the same plan slot')
    neighbors.add_argument('--prep-diversity', action='store_true',
                           help='Explore equipped units with barriers and evacuation plans on fresh boards')
    neighbors.add_argument('--defense-neighbors', action='store_true',
                           help='Compare two equipped building-unit preferences against the same model')
    neighbors.add_argument('--garrison-site-sampling', action='store_true',
                           help='Compare greedy and exploratory choices among legal Garrison sites')
    neighbors.add_argument('--loadout-neighbors', choices=tr.DECK_ORDER,
                           help='Compare one evidenced ability purchase preference on fresh boards')
    neighbors.add_argument('--loadout-sampling', action='store_true',
                           help='Compare greedy and exploratory choices among legal purchases')
    neighbors.add_argument('--battle-neighbors', nargs='?', const='all',
                           choices=('all', 'firebomb', 'firebomb-line', 'police-line', 'missile-followup', 'missile-footprint', 'cast-sampling', 'early-first-cast', 'learn-targets', 'learn-cast-tools', 'retest-fit'),
                           help='Compare battle targeting or learn cast weights from real scores')
    parser.add_argument('--goal-margin', action='store_true',
                        help='Rank unsuccessful discovery battles by survival above the 35 percent target')
    parser.add_argument('--click-start', action='store_true',
                        help='Use verified click placement at the start of fresh L1 trials')
    parser.add_argument('--fast-boot', action='store_true',
                        help='Use a shorter warmup on layout-free discovery boards')
    parser.add_argument('--generations',type=int,default=10)
    parser.add_argument('--allow-progression',action='store_true',help='Explicitly allow Boston L2–L5')
    parser.add_argument('--seed',type=int,default=92851)
    parser.add_argument('--stage-retries','--later-retries',dest='later_retries',type=int,default=2,
                        help='Training retries on later stages and below-target first-stage wins')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--seed-from',type=Path,help='Start with a previous search champion and its frozen GRU')
    source.add_argument('--continue-layout-free', type=Path,
                        help='Keep a previous layout-free proposal in training without promoting it')
    parser.add_argument('--demonstration',type=Path,help='Seed candidates from a local Boston progress file')
    parser.add_argument('--compare-forecast',type=Path,help='Evaluate the same saved champion with and without its CNN forecast')
    parser.add_argument('--compare-shadow',action='store_true',
                        help='Capture fixed-plan missile preference comparisons without promotion')
    parser.add_argument('--compare-speed',action='store_true',help='Compare fixed stock 1x and 2x on fresh L1 boards')
    parser.add_argument('--capture-shadow',action='store_true',help='Record bounded crowd frames and confirmed stock spends for offline analysis')
    args=parser.parse_args()
    battle_target = FIREBOMB_ROW if args.battle_neighbors == 'firebomb' else None
    line_flag = {'firebomb-line': 'firebomb_line_targeting',
                 'police-line': 'police_line_targeting'}.get(args.battle_neighbors)
    learn_tools = args.battle_neighbors == 'learn-cast-tools'
    learn_targets = args.battle_neighbors in ('learn-targets', 'learn-cast-tools')
    retest_fit = args.battle_neighbors == 'retest-fit'
    planning_sampling = ('sample_loadout' if args.loadout_sampling else
                         'sample_garrison_sites' if args.garrison_site_sampling else None)
    paired_policy = planning_sampling or args.loadout_neighbors or args.defense_neighbors or args.battle_neighbors in (
        'firebomb-line', 'police-line', 'missile-followup', 'missile-footprint', 'cast-sampling', 'early-first-cast', 'retest-fit')
    repeat_pair = args.placement_neighbors or battle_target is not None or paired_policy or learn_targets
    copies=args.copies
    cross_fit = learn_targets and args.generations == 3
    target_folds = {copy: i//2 if cross_fit else 0 for i, copy in enumerate(copies)}
    minimum_copies = 2 if retest_fit else 4
    if not minimum_copies <= len(copies) <= 8 or len(set(copies))!=len(copies) or args.generations<1 or args.later_retries<0:
        parser.error(f'Use {minimum_copies}–8 distinct owned copies and positive generations')
    holdout_copies = args.holdout_copies or copies
    if args.holdout_copies:
        if (len(holdout_copies) not in (2, 4, 6, 8)
                or len(set(holdout_copies)) != len(holdout_copies)
                or set(copies).intersection(holdout_copies)):
            parser.error('Use 2–8 distinct, paired holdout copies disjoint from training')
        if args.compare_forecast or args.compare_speed or args.compare_shadow:
            parser.error('Reserved holdout copies are for the final campaign evaluation')
    worker_count = max(len(copies), len(holdout_copies))
    paired_copy_counts = (2, 4) if retest_fit else (4,)
    if (args.battle_neighbors or args.placement_neighbors or paired_policy) and (
            not args.click_start or len(copies) not in paired_copy_counts):
        parser.error('Paired exploration requires the controlled fresh L1 start and a supported copy count')
    if repeat_pair and args.generations != 2 and not cross_fit:
        parser.error('Use two paired waves, or three for cast learning on separate copy pairs')
    if args.goal_margin and not args.click_start:
        parser.error('Goal-margin ranking requires the controlled fresh L1 start')
    if args.prep_diversity and (not args.click_start or not args.holdout_copies):
        parser.error('Preparation exploration requires the controlled L1 start and separate reserve copies')
    if args.click_start and not args.continue_layout_free:
        parser.error('Click-mode baseline requires layout-free continuation')
    if args.fast_boot and not args.continue_layout_free:
        parser.error('Faster boot is available only for layout-free discovery')
    if args.continue_layout_free and (args.demonstration or args.allow_progression):
        parser.error('Layout-free continuation requires Boston L1 without a demonstration')
    if args.compare_forecast and (not args.seed_from or len(copies)%2 or args.demonstration):
        parser.error('Forecast comparison requires a saved champion and paired copies')
    if args.compare_speed and (not args.seed_from or args.generations % 2 or args.demonstration
                               or args.allow_progression or args.compare_forecast):
        parser.error('Speed comparison requires a saved champion, an even number of waves and fresh L1 only')
    if args.compare_shadow and (not args.seed_from or len(copies) != 6 or args.generations % 3
                                or args.demonstration or args.allow_progression
                                or args.compare_forecast or args.compare_speed):
        parser.error('Shadow comparison requires a saved champion, six copies, a multiple of three waves and fresh L1 only')
    with operator.training_lock(operator.LOCK):
        ancestors=[p.pid for p in psutil.Process().parents()]
        for copy in dict.fromkeys(copies + holdout_copies):
            operator.require_idle(operator.inventory(),copy,os.getpid(),ancestor_pids=ancestors)
            report=operator.preflight(copy)
            if not report['ok']:raise RuntimeError(report['errors'])
        operator.limit_resources(worker_count)
        rng=np.random.default_rng(args.seed)
        net=tr.PolicyNet2()
        prior = proposal = None
        if args.seed_from:
            prior = restore_team(net, args.seed_from)
        elif args.continue_layout_free:
            proposal = restore_layout_free_proposal(net, args.continue_layout_free)
        else:
            tr.load_pretrained(net,tr.MODEL)
        weights=net.state_dict()
        directory=operator.ROOT/'analysis'/('coverage-team-'+uuid.uuid4().hex[:10])
        directory.mkdir()
        save_frozen_base(directory, weights, args.continue_layout_free)
        print(directory,'base',tr.policy_id(net),flush=True)
        print('Campaign scope:', 'Boston L1 to L5' if args.allow_progression else 'Boston L1 only', flush=True)
        if args.compare_shadow:
            variants = shadow_variants(prior)
            (directory/'comparison-teams.json').write_text(json.dumps(variants))
            arms = list(variants)
            with ProcessPoolExecutor(len(copies)) as pool:
                for wave in range(args.generations):
                    assignments = {copy: arms[(i + wave) % len(arms)] for i, copy in enumerate(copies)}
                    jobs = [(copy, weights, variants[assignments[copy]], args.seed + wave*len(copies) + i//3)
                            for i, copy in enumerate(copies)]
                    for job, _, result in completed_rollouts(pool, jobs, capture_shadow=True):
                        result.update(wave=wave, arm=assignments[job[0]], team_id=team_id(job[2]))
                        with (directory/'shadow-comparison.jsonl').open('a') as f:
                            f.write(json.dumps(result)+'\n')
            return
        population = [random_team(rng) for _ in range(max(3, len(copies)-1))]
        initial_team = prior or proposal
        if initial_team:
            population[0] = initial_team
            population[1] = offspring(initial_team, initial_team, rng)
        if proposal:
            population[1] = defense_placement_candidate(proposal, rng) or population[1]
            population[-1] = nearby_plan_candidate(proposal, rng) or population[-1]
        if args.demonstration:
            from layout_memory import demonstrations
            stages=demonstrations(args.demonstration)
            layout=stages[1]
            for i in range(1,len(population)):
                # Explore execution order: progress files store the finished layout.
                candidate=population[i]
                if prior and prior.get('layout'):
                    candidate=population[i]=deepcopy(prior)
                candidate['plan']=[]
                if prior and prior.get('layout'):
                    candidate=population[i]=loadout_candidate(candidate,rng)
                    candidate['camera_pause']=(np.asarray(candidate.get('camera_pause',np.zeros(6)))+rng.normal(0,2,6)).tolist()
                if not (prior and prior.get('layout')):
                    candidate['layout']=deepcopy(layout)
                candidate['later_layouts']={str(k):deepcopy(v) for k,v in stages.items() if k>1}
                vary = list(candidate['later_layouts'].values()) if prior and prior.get('layout') else [candidate['layout']]
                for actions in vary:
                    if i==2:actions.sort(key=lambda item:item['kind']=='garrison')
                    if i>2:rng.shuffle(actions)
            if prior and prior.get('layout'):
                population[1]['refuge']=dict(scale=1.,aspect=float(rng.uniform(.7,1.5)),
                                             defense_weight=float(rng.uniform(.08,.22)))
        base=tr.policy_id(net)
        view_revision='playable-overview-v3-bounded-targets-shelter-v2-specials-v1-retries-v2-verified-ready-v1-native-unlock-v1'
        explore_without_layout = not args.demonstration and not (prior or {}).get('layout')
        if explore_without_layout and not args.allow_progression:
            view_revision += '-placement-feedback-v4-debt-cancel-v1'
        if args.click_start:
            view_revision += '-click-start-v1'
        if args.goal_margin:
            view_revision += '-goal-margin-v1'
        evidence={}
        prices={}
        defenders = {}
        resumed_cast_probe = None
        loadout_neighbor = None
        missile_reference = None
        resumed_speed_pair = None
        discovery_seeds = set()
        resume_directory = args.seed_from or args.continue_layout_free
        if resume_directory and (resume_directory/'fitness.json').exists():
            ledger=json.loads((resume_directory/'fitness.json').read_text())
            if ledger['base']!=base:raise ValueError('Campaign fitness base mismatch')
            if ledger.get('view_revision')==view_revision:evidence=ledger['evidence']
            prices=ledger.get('layout_prices',{})
            if 'discovery_seeds' in ledger:
                discovery_seeds.update(ledger['discovery_seeds'])
            else:
                discovery_seeds.update(int(key.removeprefix('seed/'))
                                       for samples in ledger['evidence'].values() for key in samples
                                       if key.startswith('seed/'))
        if resume_directory and not (args.compare_forecast or args.compare_speed):
            best_budget=None
            previous_pause_variant = None
            paths=[resume_directory/name for name in ('trials.jsonl','extra-trials.jsonl')]
            previous_holdout = resume_directory/'holdout.jsonl'
            if previous_holdout.is_file():
                discovery_seeds.update(seed for trial in records(previous_holdout)
                                       if (seed := fitness.l1_outbreak_seed(trial)) is not None)
            for trial in chain.from_iterable(records(path) for path in paths if path.is_file()):
                if (observed_seed := fitness.l1_outbreak_seed(trial)) is not None:
                    discovery_seeds.add(observed_seed)
                if trial.get('view_revision')==view_revision:
                    fitness.record(evidence,trial)
                    if (proposal is not None and resumed_cast_probe is None
                            and trial.get('team') == proposal):
                        resumed_cast_probe = cast_candidate(trial, rng)
                    if (args.loadout_neighbors and loadout_neighbor is None
                            and trial.get('team') == proposal):
                        candidate = early_loadout_candidate(trial, rng, ability=args.loadout_neighbors)
                        if candidate is not None:
                            loadout_neighbor = candidate
                    if args.battle_neighbors in ('missile-followup', 'missile-footprint'):
                        reference = missile_trial_reference(trial)
                        if reference is not None and (missile_reference is None or reference[0] > missile_reference[0]):
                            missile_reference = reference
                    if args.continue_layout_free and has_defense_evidence(trial):
                        defender = checkpoint_team(dict(base=base, team_id=trial['team_id'],
                                                        team=trial['team']), base)
                        defenders[defender['team_id']] = trial
                        if args.click_start and resumed_speed_pair is None:
                            challenger = speed_probe(trial)
                            if challenger and fitness.prefix_id(challenger, 1) not in evidence:
                                resumed_speed_pair = (trial['team'], challenger)
                    if args.continue_layout_free and previous_pause_variant is None:
                        previous_pause_variant = pause_variant(trial, rng)
                        if previous_pause_variant is not None:
                            checkpoint_team(dict(base=base, team_id=trial['team_id'], team=trial['team']), base)
                            population[1] = previous_pause_variant
                if not args.seed_from or not trial.get('levels'):continue
                candidate=budget_candidate(trial.get('team'),trial['levels'],prices)
                if candidate:
                    rank=(max(r['stage'] for r in trial['levels']),team_id(candidate))
                    if best_budget is None or rank>best_budget:
                        best_budget,population[-1]=rank,candidate
            for i in range(1,len(population)):
                population[i]=budget_candidate(population[i],[],prices) or population[i]
        defense_trial = best_defense_trial(defenders, evidence)
        if defense_trial is not None:
            defender = defense_trial['team']
            if defender != proposal:
                population[1] = defender
            population[-1] = (defense_duration_candidate(defense_trial, rng)
                              or planning_scale_candidate(defender, rng))
        if proposal is not None:
            population[1] = battle_sampling_candidate(proposal)
        if resumed_cast_probe is not None:
            population[-1] = resumed_cast_probe
        if proposal is not None:
            paired_early_defense = False
            matched = defenders.get(team_id(proposal))
            placement = (defense_coverage_candidate(matched, rng)
                         or defense_spacing_candidate(matched, rng))
            if placement is not None:
                population[-1] = placement
                if placement.get('garrison_coverage'):
                    matched_plan = shelter_order_candidate(placement) or placement
                    matched_plan.pop('garrison_early_coverage', None)
                    matched_plan['garrison_building_range'] = True
                    population[-1] = matched_plan
                    population[1] = dict(deepcopy(matched_plan), garrison_early_coverage=True)
                    paired_early_defense = True
            if matched is not None:
                sheltered = matched['levels'][0]['outbreak'].get('civilians_inside_pct')
                if isinstance(sheltered, (int, float)) and 0 < sheltered < 35:
                    if not proposal.get('sample_zone_geometry'):
                        population[-1] = dict(deepcopy(proposal), sample_zone_geometry=True)
                    elif not paired_early_defense:
                        if proposal.get('zone_population') and not proposal.get('zone_anchor_lookahead'):
                            population[-1] = dict(deepcopy(proposal), zone_anchor_lookahead=True)
                        else:
                            population[-1] = dict(deepcopy(proposal), zone_population=float(rng.uniform(6., 12.)))
        if proposal is not None:
            for index, candidate in zip((1, -1), planning_scale_neighbors(proposal, evidence)):
                population[index] = candidate
            if resumed_speed_pair:
                reference, challenger = resumed_speed_pair
                population[-1] = challenger
                if reference != proposal:
                    population[1] = reference
            if args.click_start and not evidence:
                for index, tool in zip((1, -1), PLACEMENT_MODES):
                    candidate = placement_mode_candidate(proposal, rng, tool)
                    if candidate is not None:
                        population[index] = candidate
        fit_outbreaks = set()
        if retest_fit:
            policy_arms, fit_outbreaks = restore_fitted_pair(args.continue_layout_free, base)
            print('Frozen target retest:', [team_id(team) for team in policy_arms],
                  'excluded fit outbreaks:', sorted(fit_outbreaks), flush=True)
        elif learn_targets:
            train_mode = proposal.get('cast_target_mode', 'sample') if learn_tools else 'sample'
            training_parent = dict(proposal, sample_battle=True, cast_target_mode=train_mode)
        elif line_flag:
            endpoint = dict(proposal)
            endpoint.pop(line_flag, None)
            policy_arms = (endpoint, dict(endpoint, **{line_flag: True}))
        elif args.battle_neighbors == 'early-first-cast':
            standard = dict(proposal)
            standard.pop('opening_cast_bias', None)
            policy_arms = (standard, dict(standard, opening_cast_bias=2.))
        elif args.battle_neighbors in ('missile-followup', 'missile-footprint'):
            if missile_reference is None:
                raise ValueError('Missile feedback comparison requires a scored fresh discovery game with native launches')
            trial = missile_reference[1]
            standard = dict(checkpoint_team(dict(base=base, team=trial['team'],
                                                  team_id=trial['team_id']), base)['team'])
            if args.battle_neighbors == 'missile-followup':
                standard.pop('missile_followup', None)
                policy_arms = (standard, dict(standard, missile_followup=10.))
            else:
                standard.pop('missile_footprint', None)
                policy_arms = (standard, dict(standard, missile_footprint=True))
        elif args.loadout_neighbors:
            if loadout_neighbor is None:
                raise ValueError('Loadout comparison requires an affordable offer in the selected policy’s discovery receipts')
            policy_arms = (proposal, loadout_neighbor)
        elif planning_sampling:
            greedy_plan = dict(proposal)
            greedy_plan.pop(planning_sampling, None)
            policy_arms = (greedy_plan, dict(greedy_plan, **{planning_sampling: True}))
        elif args.defense_neighbors:
            rosters = [operator.planning_roster((operator.owned_copy(copy) / 'steam_cloud/settings.ini')
                                               .read_text(encoding='utf-8-sig')) for copy in copies]
            defense_neighbors = available_placement_neighbors(proposal, rosters, rng, buildings_only=True)
            if not defense_neighbors:
                raise ValueError('Defense comparison needs an unequipped preference and two shared buildings')
            print('Embedded building variants:',
                  [[tr.TOOLS[step['tool']] for step, reference in zip(team['plan'], proposal['plan'])
                    if step != reference] for team in defense_neighbors], flush=True)
        elif paired_policy:
            if not proposal.get('sample_battle'):
                raise ValueError('Cast target comparison requires a sampled-battle reference')
            policy_arms = tuple(dict(proposal, cast_target_mode=mode) for mode in ('sample', 'greedy'))
        elif args.battle_neighbors:
            population[1], population[-1] = battle_neighbors(proposal, rng, battle_target)
        if args.placement_neighbors:
            rosters = [operator.planning_roster((operator.owned_copy(copy) / 'steam_cloud/settings.ini')
                                               .read_text(encoding='utf-8-sig')) for copy in copies]
            pair = available_placement_neighbors(proposal, rosters, rng)
            if not pair:
                raise ValueError('Paired placement exploration needs an unequipped preference and two shared alternatives')
            population[1], population[-1] = pair
        if prior and not (args.compare_forecast or args.compare_speed):
            previous=args.seed_from/'provisional.json'
            if previous.is_file():
                saved=checkpoint_team(json.loads(previous.read_text()),base)['team']
                if saved!=prior:population[-1]=saved
            weight = 10. if prior.get('missile_followup')!=10. else float(rng.uniform(6,14))
            population[1]=dict(deepcopy(prior),missile_followup=weight)
        archive={}
        deepest={}
        incumbent=prior
        continued={}
        require_fresh=set()
        with ProcessPoolExecutor(worker_count) as pool:
            if args.compare_speed:
                for wave in range(args.generations):
                    speed = ('speed_1', 'speed_2')[(wave + wave // 2) % 2]
                    jobs = [(copy, weights, prior, args.seed + (wave // 2) * len(copies) + i)
                            for i, copy in enumerate(copies)]
                    speeds = dict.fromkeys(copies, speed)
                    for job, _, result in completed_rollouts(pool, jobs, speeds=speeds,
                                                            capture_shadow=args.capture_shadow):
                        result.update(wave=wave, fixed_speed=speed, team_id=team_id(prior))
                        with (directory/'speed-comparison.jsonl').open('a') as f:
                            f.write(json.dumps(result)+'\n')
                return
            if args.compare_forecast:
                contender=loadout_candidate(prior,rng)
                (directory/'comparison-team.json').write_text(json.dumps(contender))
                for swap in range(2):
                    jobs=[]
                    for i,copy in enumerate(copies):
                        job=(copy,weights,contender,args.seed+swap*len(copies)+i//2)
                        jobs.append(job+(args.compare_forecast,) if (i+swap)%2 else job)
                    for job,_,result in completed_rollouts(pool,jobs,allow_progression=args.allow_progression,
                                                           capture_shadow=args.capture_shadow):
                        result.update(cnn=len(job)==5,team_id=team_id(contender))
                        with (directory/'forecast-comparison.jsonl').open('a') as f:
                            f.write(json.dumps(result)+'\n')
                        print('cnn',result['cnn'],result.get('error'),[(r['end'],r['saved']) for r in result['levels']],flush=True)
                return
            prep_usage = Counter()
            prep_seen = set()
            for generation in range(args.generations):
                fit_targets = learn_targets and generation == 0
                fit_trials = []
                alternate_teams = None
                prep_assignments = {}
                if args.prep_diversity:
                    control = generation % len(copies)
                    reference = leader if generation else proposal
                    population = [reference] * len(copies)
                    for i, copy in enumerate(copies):
                        if i == control:
                            continue
                        settings = operator.owned_copy(copy) / 'steam_cloud/settings.ini'
                        roster = operator.planning_roster(settings.read_text(encoding='utf-8-sig'))
                        candidate = next(((child, combination) for child, combination in
                                          preparation_variants(proposal, roster, prep_usage, rng)
                                          if team_id(child) not in prep_seen
                                          and fitness.prefix_id(child, 1) not in evidence), None)
                        if candidate is None:
                            raise ValueError(f'{copy} has no additional eligible preparation combinations')
                        population[i], combination = candidate
                        unit, support, after = combination
                        prep_usage.update((combination, unit, support))
                        prep_seen.add(team_id(population[i]))
                        prep_assignments[copy] = dict(unit=tr.PLACEMENTS[unit],
                                                     support=tr.TOOLS[support], after_shelter=after)
                elif fit_targets:
                    population = [training_parent] * len(copies)
                elif learn_targets or retest_fit:
                    pairs = [target_fits[target_folds[copy]][0] if learn_targets else policy_arms
                             for copy in copies]
                    population = [pair[(i+generation) % 2] for i, pair in enumerate(pairs)]
                    alternate_teams = {copy: pair[1-(i+generation) % 2]
                                       for i, (copy, pair) in enumerate(zip(copies, pairs))}
                elif args.defense_neighbors:
                    population = [((proposal, defense_neighbors[i // 2])[(i + generation) % 2])
                                  for i in range(len(copies))]
                elif paired_policy:
                    population = [policy_arms[(i+generation) % 2] for i in range(len(copies))]
                elif repeat_pair and generation:
                    population = first_wave[1:] + first_wave[:1]
                else:
                    if generation == 0:
                        population.append(proposal if battle_target is not None else None)
                    rng.shuffle(population)
                    if repeat_pair:
                        first_wave = population.copy()
                if paired_policy or (learn_targets and not fit_targets):
                    first_seed = args.seed + (len(copies) if learn_targets else 0)
                    seeds = [first_seed + i//2 for i in range(len(copies))]
                else:
                    first_seed = args.seed + generation*len(copies)
                    seeds = range(first_seed, first_seed + len(copies))
                jobs = [(copy, weights, team, seed)
                        for copy, team, seed in zip(copies, population, seeds)]
                starts=[1]*len(jobs)
                for i,(copy,_,team,_) in enumerate(jobs):
                    stage=continued.get(copy)
                    if (stage and team and team_id(team) not in require_fresh and str(stage) in team.get('later_layouts',{})
                            and starts.count(1)>len(jobs)//2+1):
                        starts[i]=stage
                continued={}
                require_fresh.clear()
                practice=[]
                affordable=[]
                cast_probes={}
                loadout_probes={}
                valid_candidates=0
                for job,start_stage,result in completed_rollouts(pool,jobs,starts,args.later_retries,training=True,
                        allow_progression=args.allow_progression,capture_shadow=args.capture_shadow,
                        fast_boot=args.fast_boot, click_start=args.click_start, goal_margin=args.goal_margin,
                        collect_cast_gradients=fit_targets and not learn_tools,
                        collect_cast_tool_gradients=fit_targets and learn_tools, alternate_teams=alternate_teams):
                    team=job[2]
                    key=team_id(team) if team else 'control'
                    result.update(view_revision=view_revision,generation=generation,team_id=key,team=team,start_stage=start_stage)
                    if args.prep_diversity:
                        result['prep_proposal'] = prep_assignments.get(job[0])
                    if fit_targets:
                        fit_trials.append(result)
                    if (observed_seed := fitness.l1_outbreak_seed(result)) is not None:
                        discovery_seeds.add(observed_seed)
                        if learn_targets and not fit_targets:
                            fold = target_folds[job[0]]
                            result['target_fit_fold'] = fold
                            result['target_fit_overlap'] = observed_seed in target_fits[fold][1]['exposed_seeds']
                        elif retest_fit:
                            result['target_fit_overlap'] = observed_seed in fit_outbreaks
                    with (directory/'trials.jsonl').open('a') as f:
                        f.write(json.dumps(result)+'\n')
                    if 'error' in result:
                        print('failed',job[0],result['error'],flush=True)
                        if not result.get('levels'):continue
                    levels=result['levels']
                    candidate=budget_candidate(team,levels,prices)
                    if candidate:affordable.append((max(r['stage'] for r in levels),candidate))
                    last=levels[-1]
                    stopped_in_planning=last.get('timeout_reason')=='planning_decisions'
                    if last['stage']>1 and (last['end'] in ('aborted','lost','won') or stopped_in_planning) and not last['advance']:
                        continued[job[0]]=last['stage']
                    if start_stage>1:
                        practice.append((start_stage,max(r['score'] for r in levels if r['stage']==start_stage),team))
                        print('practice',key,[(r['stage'],r['end'],r['saved']) for r in levels],flush=True)
                        continue
                    if team:
                        valid_candidates+=1
                        archive[key]=team
                        deepest[key]=max(deepest.get(key,1),levels[-1]['stage'],result.get('failed_stage',1))
                        fitness.record(evidence,result)
                        if explore_without_layout and not args.allow_progression and has_defense_evidence(result):
                            defenders[key] = result
                        probe=cast_candidate(result,rng)
                        if probe:cast_probes[key]=probe
                        if explore_without_layout and not args.allow_progression:
                            loadout = early_loadout_candidate(result, rng)
                            if loadout is not None:
                                loadout_probes[key] = loadout
                    print(generation,key,[(r['stage'],r['end'],r['saved'],round(r['sim'],1)) for r in levels],flush=True)
                if not valid_candidates:raise RuntimeError('No valid candidates this generation; inspect trials')
                if fit_targets:
                    target_fits = target_comparison_fits(
                        training_parent, fit_trials, target_folds, proposal.get('cast_target_mode', 'sample'),
                        learn_tools=learn_tools)
                    reports = [report for _, report in target_fits.values()]
                    for fold, report in enumerate(reports):
                        print('Live target fit:', fold, {k: v for k, v in report.items() if k != 'team'}, flush=True)
                    report_path = directory/'target-fit.tmp'
                    report_path.write_text(json.dumps(dict(folds=reports) if cross_fit else reports[0]))
                    report_path.replace(directory/'target-fit.json')
                ranked=sorted(archive,key=lambda k:fitness.ranking(evidence,archive[k]),reverse=True)
                def l1_rank(key):
                    if explore_without_layout:
                        return fitness.l1_proposal_rank(evidence, archive[key])
                    outcomes=fitness.stats(evidence,archive[key],1)
                    return outcomes['lower'],outcomes['objective']
                l1_ranked=sorted(archive,key=l1_rank,reverse=True)
                if explore_without_layout and not args.allow_progression:
                    ranked = l1_ranked
                leader=archive[l1_ranked[0]]
                report=fitness.stats(evidence,leader,1)
                print('fresh L1 leader',team_id(leader),report,flush=True)
                for filename,data in [('fitness',dict(base=base,view_revision=view_revision,evidence=evidence,layout_prices=prices,
                                                   discovery_seeds=sorted(discovery_seeds))),
                                      ('provisional',dict(team=leader,team_id=team_id(leader),base=base))]:
                    temp=directory/(filename+'.tmp')
                    temp.write_text(json.dumps(data))
                    temp.replace(directory/(filename+'.json'))
                if incumbent:
                    stages=[fitness.stats(evidence,incumbent,i) for i in range(1,6)]
                    champion=dict(team_id=team_id(incumbent),team=incumbent,base=base,
                                  generation=generation,trials=stages[0]['starts'],fresh_stages=stages)
                    temp=directory/'champion.tmp'
                    temp.write_text(json.dumps(champion))
                    temp.replace(directory/'champion.json')
                # Replicate the leader on independent boards and reserve one L1 mutation.
                alternate = incumbent or leader
                if explore_without_layout and incumbent is None:
                    defense_trial = best_defense_trial(defenders, evidence)
                    if defense_trial is None:
                        alternate = defense_placement_candidate(leader, rng) or alternate
                    else:
                        defender = defense_trial['team']
                        if defender != leader and generation % 2 == 0:
                            alternate = defender
                        elif generation % 4 == 1:
                            alternate = (defense_duration_candidate(defense_trial, rng)
                                         or planning_scale_candidate(defender, rng))
                        else:
                            alternate = planning_scale_candidate(defender, rng)
                population = [leader, alternate]
                require_fresh.update(team_id(t) for t in population)
                population.append(l1_candidate(leader,rng) if generation%2==0 else offspring(leader,leader,rng,stage=1))
                repeat = fitness.replication_candidate(evidence, (archive[k] for k in l1_ranked), population)
                if repeat and len(copies)>=6:
                    population.append(repeat)
                    require_fresh.add(team_id(repeat))
                probe=next((cast_probes[k] for k in l1_ranked if k in cast_probes),None)
                nearby = (nearby_plan_candidate(leader, rng)
                          if explore_without_layout and generation % 2 == 0 else None)
                early = next((loadout_probes[k] for k in l1_ranked if k in loadout_probes), None)
                if early is not None:
                    population.append(early)
                    require_fresh.add(team_id(early))
                elif nearby is not None:
                    population.append(nearby)
                elif generation%2==0:
                    defender=deepcopy(incumbent or leader)
                    if generation%4==0:
                        defender['missile_followup']=float(rng.uniform(6,14))
                    else:
                        defender['missile_reserve']=float(rng.uniform(2,6))
                    population.append(defender)
                elif generation%4==1 and leader.get('layout'):
                    population.append(dict(deepcopy(leader),garrison_relocation=rng.integers(0,16,size=2).tolist()))
                elif generation%4==3:
                    population.append(dict(deepcopy(leader),special_probe=float(rng.uniform(16,24))))
                elif probe and not practice:population.append(probe)
                elif practice:
                    specialist=max(practice,key=lambda entry:(entry[0],entry[1],team_id(entry[2])))[2]
                    population.append(specialist)
                    require_fresh.add(team_id(specialist))
                elif affordable:
                    population.append(max(affordable,key=lambda entry:(entry[0],team_id(entry[1])))[1])
                if len(population)<len(copies):
                    population.append(loadout_candidate(leader,rng))
                while len(population)<len(copies):
                    stage_parent=ranked[0]
                    stage=deepest[stage_parent] if len(population)%2 else 1
                    key=stage_parent if stage>1 else l1_ranked[int(rng.integers(min(2,len(l1_ranked))))]
                    child=offspring(archive[key],leader,rng,stage=stage)
                    population.append(budget_candidate(child,[],prices) or child)
                if args.battle_neighbors and not repeat_pair and generation + 1 < args.generations:
                    pair = battle_neighbors(leader, rng)
                    population = [leader, deepcopy(leader), *pair]
                    require_fresh.update(team_id(team) for team in pair)
                elif not repeat_pair and args.click_start and generation % 2 == 0 and generation + 1 < args.generations:
                    pair = shelter_cast_pair(defenders, evidence, rng)
                    if pair is not None:
                        population[-2:] = pair
                        require_fresh.update(team_id(team) for team in pair)
            # Frozen arms on fresh boards. The game chooses its own outbreak seeds.
            matched_reference = args.loadout_neighbors or args.battle_neighbors in (
                'early-first-cast', 'police-line', 'missile-followup', 'missile-footprint')
            reference = policy_arms[0] if matched_reference else prior
            distinct=[archive[k] for k in ranked if archive[k]!=reference and
                      (args.allow_progression or reference is None or
                       fitness.prefix_id(archive[k],1)!=fitness.prefix_id(reference,1))]
            qualified=[t for t in distinct if fitness.promote(evidence,t,reference) is t]
            if args.qualified_holdout_only and not qualified:
                print('Reserved evaluation deferred: no discovery policy qualified', flush=True)
                return
            challenger=next(iter(qualified or distinct),leader)
            stage=next((i for i in range(1,6 if args.allow_progression else 2) if reference is None or
                        fitness.prefix_id(challenger,i)!=fitness.prefix_id(reference,i)),1)
            pairs = len(holdout_copies)//2
            waves = (6+pairs-1)//pairs if challenger in qualified else 1
            seed = args.seed+(args.generations+1)*len(copies)
            evaluation=[]
            for wave in range(waves):
                jobs,arms = holdout_assignments(holdout_copies,weights,challenger,reference,seed,wave)
                for job,_,result in completed_rollouts(pool,jobs,allow_progression=args.allow_progression,
                                                       capture_shadow=args.capture_shadow, click_start=args.click_start):
                    result.update(arm=arms[job[0]],team_id=team_id(job[2]) if job[2] else 'control',
                                  holdout_round=wave,
                                  discovery_overlap=fitness.l1_outbreak_seed(result) in discovery_seeds)
                    evaluation.append(result)
                    with (directory/'holdout.jsonl').open('a') as f:
                        f.write(json.dumps(result)+'\n')
                if args.qualified_holdout_only and fitness.holdout_samples(
                        evaluation, stage, discovery_seeds=discovery_seeds) is None:
                    print('Reserve evaluation ended after an ineligible comparison wave; records retained', flush=True)
                    break
            if challenger in qualified and fitness.holdout_passed(
                    evaluation, pairs*waves, stage, discovery_seeds=discovery_seeds):
                stages=[fitness.stats(evidence,challenger,i) for i in range(1,6)]
                record=dict(team_id=team_id(challenger),team=challenger,base=base,generation=generation,
                            trials=stages[0]['starts'],fresh_stages=stages,holdout_stage=stage,holdout_opponent=team_id(reference) if reference else 'gru')
                temp=directory/'champion.tmp'
                temp.write_text(json.dumps(record))
                temp.replace(directory/'champion.json')
                print('promoted after fresh holdout',record['team_id'],flush=True)



if __name__=='__main__':
    main()
