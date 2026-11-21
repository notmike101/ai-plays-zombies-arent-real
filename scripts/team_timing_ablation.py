"""Registered layout-free team discovery ablation (named private profiles).

timing (default, seed 342571, protocol preserved unchanged):
Frozen sampled incumbent 0d1d56160623a3a1 versus challenger 26be8cee926eaa85,
which removes only opening_cast_bias=2.0. Discovery: two paired policy seeds
two arms, serial alternating copies, no replacements. Advance only on two
challenger NATURAL wins and a strictly higher official-saved mean across both
scheduled scored attempts per arm (finite scores mandatory even on abort;
native abort-retry chains count; nothing dropped); any unknown fails the gate.
Screen: four NEW paired policy seeds x two arms (evaluation rows for the unchanged 35% consistency
gate). Fresh L1 only, never a known outbreak, bound header-matched raw native
sessions, and both planning and battle rosters restored on every exit. No
promotion; no replacement ever.

population-weight (seed 344571, tracker line 24): the same frozen incumbent
and GRU versus one challenger 8d4ed60fdb803689 that reduces only
zone_population 8.649016304182014 -> 4.0 (no layout replay, anchor lookahead,
sampling, battle or READY changes). After the first matched pair both arms'
closed-zone polygons are compared canonically from the native READY snapshot
(world coordinates, rotation/winding canonical, 2-corner walls excluded,
missing distinct from empty): unchanged stops without pair two and unknown
stops fail-closed. Same budget, gate, exclusion discipline as 342571, plus
explicit proof that 342571's four discovery seeds are excluded.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT)]

import psutil
import torch
import compare_spatial as compare
import nn_play2 as trainer
import team_search as search

SOURCE = ROOT / 'analysis/coverage-team-c81131e97f'
PREVIOUS = ROOT / 'analysis/coverage-team-defense-frozen-325301'
TEAM_ID, BASE_ID = 'bf3fc52369fc3746', '8a691469a829158d'
INCUMBENT_ID, CHALLENGER_ID = '0d1d56160623a3a1', '26be8cee926eaa85'
BASE_SHA = '257f0c7b1af2e0209d79686827cd67df06e041a118194e5ac3b4c326c0fd9e44'
PROVISIONAL_SHA = ('fce04d366dc8ecd04cfa0a1da5bcc4f6'
                   'f5d4256cadb9a294b5f8262544c1933d')
DIAGNOSTIC_FAMILY = 'coverage-planning-budget-f8884a26f8'
SEED = 342571
POP_SEED = 344571
POP_ZONE_POPULATION = (8.649016304182014, 4.0)
POP_CHALLENGER_ID = '8d4ed60fdb803689'
COPIES = ['inst19', 'inst20']
MAX_PHYSICAL = 12
NATURAL = ('won', 'lost')
ROSTERS = {'plan': re.compile(rb'(?m)^roster_plan([ \t]*=[ \t]*)([^\r\n]*)'),
           'battle': re.compile(rb'(?m)^roster_battle([ \t]*=[ \t]*)([^\r\n]*)')}
GATE_TEXT = ('two challenger natural wins and strictly higher natural mean; '
             'aborted diagnostic; unknown fails')
PROFILES = {
    'timing': dict(seed=SEED, incumbent=INCUMBENT_ID, challenger=CHALLENGER_ID,
                   journal='holdout.jsonl', previous_dir=None, prior_seeds=False,
                   geometry_stop=False, only_delta='opening_cast_bias 2.0 -> absent',
                   gate=GATE_TEXT),
    'population-weight': dict(
        seed=POP_SEED, incumbent=INCUMBENT_ID, challenger=POP_CHALLENGER_ID,
        journal='outcomes.jsonl', previous_dir='analysis/coverage-team-timing-342571',
        prior_seeds=True, geometry_stop=True,
        only_delta='zone_population 8.649016304182014 -> 4.0', gate=GATE_TEXT),
}


def read_verified(name, expected):
    data = (SOURCE / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'Archive digest changed: {name}')
    return data


def roster_lines(path):
    raw = path.read_bytes()
    out = {}
    for kind, pattern in ROSTERS.items():
        matches = list(pattern.finditer(raw))
        if len(matches) != 1:
            raise ValueError(f'Unverified {kind} roster in {path}')
        out[kind] = matches[0]
    return out


def set_line(path, match, value):
    raw = path.read_bytes()
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(raw[:match.start(2)] + value + raw[match.end(2):])
    temporary.replace(path)


def exclusion_audit(analysis):
    """Return (sorted seeds, per-journal counts, family proof) fail-closed."""
    seeds, counts = set(), {}

    def add(where, found):
        counts[where] = counts.get(where, 0) + len(found)
        seeds.update(found)

    for run in sorted(analysis.glob('coverage-*')):
        for name in ('results.jsonl', 'attempts.jsonl'):
            if (journal := run / name).is_file():
                add(f'{run.name}/{name}', [seed for row in compare.records(journal)
                                           if type(seed := row.get('outbreak_seed')) is int])
        if (journal := run / 'interface-retries.jsonl').is_file():
            add(f'{run.name}/interface-retries.jsonl',
                [seed for row in compare.records(journal) for attempt in row.get('original_attempts', ())
                 if type(seed := attempt.get('outbreak_seed')) is int])
        for name in ('trials.jsonl', 'holdout.jsonl', 'extra-trials.jsonl',
                     'forecast-comparison.jsonl', 'speed-comparison.jsonl'):
            if (journal := run / name).is_file():
                add(f'{run.name}/{name}',
                    [seed for row in compare.records(journal) for level in row.get('levels', ())
                     if level.get('stage') == 1
                     and type(seed := (level.get('outbreak') or {}).get('seed')) is int])
    if seeds != compare.previous_outbreak_seeds(analysis):
        raise ValueError('Exclusion collector disagrees with compare.previous_outbreak_seeds')
    paths = list(analysis.glob(f'{DIAGNOSTIC_FAMILY}/attempts.jsonl'))
    family_rows = compare.records(paths[0]) if paths else []
    finished = [row for row in family_rows if row.get('status') == 'finished']
    scored = [row for row in finished if type(row.get('outbreak_seed')) is int]
    timeout = [row for row in finished if row.get('end') == 'timeout'
               and row.get('outbreak_seed') is None]
    if (len(finished) != 6 or len(scored) != 4 or len(timeout) != 2
            or len({row['outbreak_seed'] for row in scored}) != 4):
        raise ValueError('Diagnostic family exclusion proof failed; nothing inferred for timeouts')
    return sorted(seeds), counts, dict(attempts=6, scored_outbreaks=len(scored),
                                       seedless_timeouts=len(timeout), inferred_seeds=0)


def bundle(profile_id='timing'):
    profile = PROFILES[profile_id]
    team = json.loads(read_verified('provisional.json', PROVISIONAL_SHA))['team']
    base = read_verified('base.pt', BASE_SHA)
    weights = torch.load(BytesIO(base), map_location='cpu', weights_only=True)
    policy = trainer.PolicyNet2()
    policy.load_state_dict(weights)
    if (search.team_id(team) != TEAM_ID or trainer.policy_id(policy) != BASE_ID
            or any(team.get(key) for key in ('layout', 'later_layouts'))):
        raise ValueError('Frozen bundle identity or layout mismatch')
    incumbent = dict(team, sample_garrison_sites=True)
    if search.team_id(incumbent) != profile['incumbent']:
        raise ValueError('Incumbent identity does not match the registration')
    if profile_id == 'timing':
        challenger = {key: value for key, value in incumbent.items() if key != 'opening_cast_bias'}
        if incumbent.get('opening_cast_bias') != 2.0:
            raise ValueError('Incumbent opening cast bias changed')
    else:
        if incumbent.get('zone_population') != POP_ZONE_POPULATION[0]:
            raise ValueError('Incumbent zone population changed')
        challenger = dict(incumbent, zone_population=POP_ZONE_POPULATION[1])
    changed = ({key for key in set(challenger) ^ set(incumbent)}
               | {key for key in set(challenger) & set(incumbent)
                  if challenger[key] != incumbent[key]})
    if changed != ({'opening_cast_bias'} if profile_id == 'timing' else {'zone_population'}):
        raise ValueError('Challenger differs by more than the registered single gene')
    if search.team_id(challenger) != profile['challenger']:
        raise ValueError('Arm identity does not match the registration')
    return weights, incumbent, challenger


def canonical_closed_zones(zones):
    """Canonically ordered closed-zone polygons from a READY native snapshot.

    None means the snapshot was missing (unknown geometry, distinct from an
    empty list meaning zero closed zones at READY). Polylines with fewer than
    three distinct vertices are two-corner walls or corridors and excluded.
    Polygons compare equal under any vertex rotation or winding direction."""
    if zones is None:
        return None
    closed = []
    for zone in zones:
        points = [(float(x), float(y)) for x, y in zone]
        while len(points) > 1 and points[0] == points[-1]:
            points.pop()
        distinct = [point for index, point in enumerate(points)
                    if index == 0 or point != points[index - 1]]
        if len(distinct) < 3:
            continue
        rotations = [tuple(distinct[index:] + distinct[:index]) for index in range(len(distinct))]
        reversed_points = list(reversed(distinct))
        rotations += [tuple(reversed_points[index:] + reversed_points[:index])
                      for index in range(len(reversed_points))]
        closed.append(min(rotations))
    return sorted(closed)


def geometry_verdict(incumbent_zones, challenger_zones):
    incumbent = canonical_closed_zones(incumbent_zones)
    challenger = canonical_closed_zones(challenger_zones)
    if incumbent is None or challenger is None:
        return 'unknown'
    return 'unchanged' if incumbent == challenger else 'changed'

def finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value <= 1)


def official(result):
    """Return (scored slot outcome, consumed fresh-L1 outbreak seeds, error).

    A native abort-retry chain keeps the final scored outcome for its slot;
    every consumed outbreak (abort and retry alike) is reported for exclusion.
    A finite in-range official score is mandatory even on an abort, and a
    timeout never yields an inferred seed or score."""
    levels = result.get('levels') or []
    if (error := result.get('error') or result.get('cleanup_error')) or not levels:
        return {}, [], error or 'no verified fresh L1 world'
    first = levels[0]
    if (first.get('stage') != 1 or first.get('start_kind') != 'fresh'
            or first.get('attempt', 0) or first.get('layout_receipts')):
        return first, [], 'no verified fresh L1 world'
    chain = [first]
    while chain[-1].get('end') == 'aborted' and len(chain) < len(levels):
        following = levels[len(chain)]
        if (following.get('attempt') != chain[-1].get('attempt', 0) + 1
                or following.get('stage') != 1 or following.get('start_kind') != 'fresh'):
            break
        if following.get('layout_receipts'):
            return following, [], 'unexpected replay receipt'
        chain.append(following)
    level = chain[-1]
    if level.get('end') not in NATURAL + ('aborted',):
        return level, [], f'unexpected end {level.get("end")}'
    seeds = [seed for lv in chain if type(seed := (lv.get('outbreak') or {}).get('seed')) is int]
    if len(seeds) != len(chain):
        return level, seeds, 'no native L1 outbreak seed (timeout is not an inferred seed)'
    if not finite(level.get('saved')):
        return level, seeds, 'official score missing, non-finite, or out of range (even on abort)'
    return level, seeds, None


def gate(rows, per_arm=2):
    """Registered discovery semantics: compare exactly two scheduled scored
    native outcomes per arm (four finite outcomes total; native abort-retry
    chains included; nothing dropped); any unknown fails; challenger needs two
    NATURAL wins and a strictly higher official-saved mean across both slots.
    Natural-only means, per-arm wins, and abort status are reported separately
    and never substituted into the advancing comparison."""
    unknowns = [row['episode'] for row in rows
                if row['status'] != 'finished' or row.get('err') or row.get('outbreak_seed') is None
                or row.get('end') not in NATURAL + ('aborted',) or not finite(row.get('saved'))]
    arms = {arm: [row for row in rows if row['arm'] == arm]
            for arm in ('challenger', 'incumbent')}

    def stats(rows_of_arm):
        clean = [row for row in rows_of_arm if not row.get('err') and finite(row.get('saved'))]
        natural = [row['saved'] for row in clean if row.get('end') in NATURAL]
        return (sum(row['saved'] for row in clean) / len(clean) if clean else None,
                sum(natural) / len(natural) if natural else None)

    challenger_mean, challenger_natural = stats(arms['challenger'])
    incumbent_mean, incumbent_natural = stats(arms['incumbent'])
    wins = {arm: sum(1 for row in rows_of_arm if not row.get('err') and row.get('end') == 'won')
            for arm, rows_of_arm in arms.items()}
    exact_slots = all(len(rows_of_arm) == per_arm for rows_of_arm in arms.values())
    return dict(unknowns=unknowns, slots={arm: len(rows_of_arm) for arm, rows_of_arm in arms.items()},
                challenger_wins=wins['challenger'], incumbent_wins=wins['incumbent'],
                challenger_mean=challenger_mean, incumbent_mean=incumbent_mean,
                natural_only={'challenger': challenger_natural, 'incumbent': incumbent_natural},
                diagnostics={'aborted': {arm: [row['saved'] for row in rows_of_arm
                                               if row.get('end') == 'aborted'
                                               and finite(row.get('saved'))]
                                         for arm, rows_of_arm in arms.items()}},
                advance=bool(not unknowns and exact_slots and wins['challenger'] >= per_arm
                             and challenger_mean is not None and incumbent_mean is not None
                             and challenger_mean > incumbent_mean))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=sorted(PROFILES), default='timing',
                        help='Named private registration; timing preserves the 342571 protocol')
    parser.add_argument('--run', action='store_true',
                        help='Run the registered twelve-attempt serial plan; default is offline validation only')
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    weights, incumbent, challenger = bundle(args.profile)
    arms = {'incumbent': (profile['incumbent'], incumbent),
            'challenger': (profile['challenger'], challenger)}
    seeds, counts, family = exclusion_audit(ROOT / 'analysis')
    prior_seeds = []
    if profile['prior_seeds']:
        prior_seeds = sorted({level['outbreak']['seed']
                              for row in compare.records(
                                  ROOT / profile['previous_dir'] / profile['journal'])
                              for level in row.get('levels') or ()
                              if level.get('stage') == 1 and type(level.get('outbreak')) is dict
                              and type(level['outbreak'].get('seed')) is int})
        if len(prior_seeds) != 4 or not set(prior_seeds) <= set(seeds):
            raise ValueError('Prior registered discovery seeds are not all excluded')
    if not args.run:
        print(json.dumps(dict(profile=args.profile, incumbent=profile['incumbent'],
                              challenger=profile['challenger'],
                              only_delta=profile['only_delta'],
                              geometry_stop=profile['geometry_stop'],
                              prior_timing_seeds=prior_seeds,
                              exclusion_sha256=hashlib.sha256(
                                  json.dumps(seeds).encode()).hexdigest(),
                              exclusion_total=len(seeds), journals=len(counts),
                              diagnostic_family=family,
                              plan=dict(discovery=4, screen=8, max_physical=MAX_PHYSICAL,
                                        policy_seeds=list(range(profile['seed'],
                                                                profile['seed'] + 6)))), indent=2))
        return
    directory = ROOT / f"analysis/coverage-team-timing-{profile['seed']}"
    directory.mkdir()
    operator = search.operator
    with operator.training_lock(operator.LOCK):
        for copy in COPIES:
            operator.require_idle(operator.inventory(), copy, os.getpid(),
                                  ancestor_pids=[p.pid for p in psutil.Process().parents()])
            if not (check := operator.preflight(copy))['ok']:
                raise RuntimeError(check['errors'])
        operator.limit_resources(1)
        exclusion = set(seeds)
        (directory / 'exclusion-audit.json').write_text(json.dumps(
            dict(seeds=seeds, journals=counts, diagnostic_family=family), indent=2), encoding='utf-8')
        (directory / 'frozen-manifest.json').write_text(json.dumps(dict(
            team=TEAM_ID, base=BASE_ID, incumbent=profile['incumbent'],
            challenger=profile['challenger'],
            only_delta=profile['only_delta'], seed=profile['seed'], copies=COPIES,
            speed='speed_1', click_start=True, training=False, layout_replay=False,
            exclusion_sha256=hashlib.sha256(json.dumps(seeds).encode()).hexdigest(),
            exclusion_total=len(seeds), diagnostic_family=family,
            budget=dict(discovery=4, screen=8, max_physical=MAX_PHYSICAL, replacements=0),
            gate=profile['gate'], geometry_stop=profile['geometry_stop'],
            prior_timing_seeds=prior_seeds,
            previous_screen=(ROOT / profile['previous_dir']).name if profile['previous_dir']
                            else PREVIOUS.name,
            archive={'base.pt': BASE_SHA, 'provisional.json': PROVISIONAL_SHA},
            code_sha256={name: hashlib.sha256((Path(__file__).resolve().parent / name)
                                              .read_bytes()).hexdigest()
                         for name in ('team_search.py', 'nn_play2.py', 'compare_spatial.py',
                                      'team_timing_ablation.py')}), indent=2), encoding='utf-8')
        settings = {copy: operator.owned_copy(copy) / 'steam_cloud/settings.ini' for copy in COPIES}
        originals = {copy: roster_lines(path) for copy, path in settings.items()}
        restoration_path = directory / 'roster-restoration.json'
        physical = 0
        rows, pool_errors = [], []
        try:
            historical = {}
            previous_journal = (PREVIOUS / profile['journal'] if profile['previous_dir'] is None
                                else ROOT / profile['previous_dir'] / profile['journal'])
            for row in compare.records(previous_journal):
                if row.get('team_id') == profile['incumbent'] and row.get('copy') in COPIES:
                    value = tuple(row.get('initial_planning_roster') or ())
                    if value and historical.setdefault(row['copy'], value) != value:
                        raise ValueError(f'Ambiguous archived planning roster for {row["copy"]}')
            if set(historical) != set(COPIES):
                raise ValueError('Missing archived incumbent planning roster for a copy')
            for copy, path in settings.items():
                set_line(path, roster_lines(path)['plan'], ' '.join(historical[copy]).encode())
            with ProcessPoolExecutor(1) as pool, \
                    (directory / 'attempts.jsonl').open('x', encoding='utf-8') as attempts, \
                    (directory / 'outcomes.jsonl').open('x', encoding='utf-8') as outcomes:
                def record(row, stream):
                    stream.write(json.dumps(row) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())

                used = set()
                def attempt(index, phase, seed):
                    nonlocal physical
                    if physical >= MAX_PHYSICAL:
                        raise RuntimeError('Physical budget exceeded')
                    arm = 'incumbent' if (index // 2 + index) % 2 == 0 else 'challenger'
                    policy_id, team = arms[arm]
                    copy = COPIES[index % 2]
                    tag = f"team-timing-{profile['seed']}_{phase}_{index}_{arm}"
                    operator.require_idle(operator.inventory(), copy, os.getpid(),
                                          ancestor_pids=[p.pid for p in psutil.Process().parents()])
                    if not (check := operator.preflight(copy))['ok']:
                        raise RuntimeError('; '.join(check['errors']))
                    operator.require_resource_headroom(1)
                    physical += 1
                    record(dict(episode=tag, attempt=0, phase=phase, arm=arm, copy=copy,
                                policy_seed=seed, policy_id=policy_id,
                                status='scheduled'), attempts)
                    prior, level, observed, session = [], {}, None, {}
                    try:
                        result = dict(copy=copy, seed=seed, levels=[], error='pool never yielded')
                        for _, _, result in search.completed_rollouts(
                                pool, [(copy, weights, team, seed)],
                                click_start=True, speeds={copy: 'speed_1'}):
                            pass
                        level, chain, error = official(result)
                        observed = chain[-1] if chain else None
                        if error is None:
                            for consumed in chain:
                                if consumed in exclusion or consumed in used:
                                    error = f'duplicate outbreak seed {consumed}'
                                    break
                            if error is None:
                                prior, _ = sorted(used), used.update(chain)
                        session = compare.archive_native_session(
                            operator.owned_copy(copy), directory, tag, copy,
                            level.get('log_started'))
                        if error is None and session.get('status') != 'archived':
                            error = f'native session {session.get("status")}'
                    except Exception as failure:
                        level, session = {}, {}
                        error = f'launcher failure: {failure}'
                    finished = dict(episode=tag, attempt=0, phase=phase, arm=arm, copy=copy,
                                    policy_seed=seed, policy_id=policy_id, status='finished',
                                    err=error, saved=level.get('saved'),
                                    saved_frac=level.get('saved'), win=level.get('win'),
                                    end=level.get('end'), start_kind=level.get('start_kind'),
                                    outbreak_seed=observed,
                                    prior_attempt_seeds=prior,
                                    native_session=session,
                                    ready_zones=level.get('ready_zones'),
                                    first_deployments=((level.get('battle_actions') or {})
                                                       .get('deploy_sim_seconds') or [])[:3])
                    record(finished, attempts)
                    rows.append(finished)
                    if error:
                        pool_errors.append(f'{tag}: {error}')
                    else:
                        record(dict(result, arm=arm, team_id=policy_id, holdout_index=index,
                                    outbreak_seed=observed, discovery_overlap=observed in exclusion,
                                    native_session=session), outcomes)
                geometry = None
                for index in range(4):
                    attempt(index, 'discovery', profile['seed'] + index // 2)
                    if pool_errors:
                        break
                    if profile['geometry_stop'] and index == 1:
                        geometry = geometry_verdict(rows[0].get('ready_zones'),
                                                    rows[1].get('ready_zones'))
                        (directory / 'geometry-check.json').write_text(json.dumps(dict(
                            verdict=geometry,
                            incumbent=canonical_closed_zones(rows[0].get('ready_zones')),
                            challenger=canonical_closed_zones(rows[1].get('ready_zones'))),
                            indent=2), encoding='utf-8')
                        if geometry == 'unknown':
                            pool_errors.append(
                                f'{rows[1]["episode"]}: unknown closed-zone geometry at READY')
                            break
                        if geometry == 'unchanged':
                            break
                decision = gate([row for row in rows if row['phase'] == 'discovery'])
                if profile['geometry_stop']:
                    decision = dict(decision, geometry_verdict=geometry,
                                    advance=bool(decision['advance'] and geometry == 'changed'))
                (directory / 'discovery-gate.json').write_text(
                    json.dumps(decision, indent=2), encoding='utf-8')
                if decision['advance'] and not pool_errors:
                    for index in range(8):
                        attempt(index, 'evaluation', profile['seed'] + 2 + index // 2)
                        if pool_errors:
                            break
                evaluation = [row for row in rows if row['phase'] == 'evaluation']
                decision = dict(decision, screen=gate(evaluation, per_arm=4) if evaluation else None,
                                promotion='registered 35% consistency screen owns promotion')
                (directory / 'decision.json').write_text(json.dumps(decision, indent=2), encoding='utf-8')
            native = compare.physical_attempts(directory / 'attempts.jsonl')
            (directory / 'consistency.json').write_text(json.dumps({
                actor: compare.heldout_consistency(native, actor, discovery_seeds=exclusion)
                for actor in (profile['incumbent'], profile['challenger'])},
                indent=2), encoding='utf-8')
        finally:
            restoration = {}
            for copy, path in settings.items():
                state = {'verified': False}
                for kind in ('plan', 'battle'):
                    try:
                        set_line(path, roster_lines(path)[kind], originals[copy][kind].group(2))
                        state[kind] = True
                    except Exception as error:
                        state[kind] = str(error)
                try:
                    current = roster_lines(path)
                    state['verified'] = all(
                        current[kind].group(2) == originals[copy][kind].group(2)
                        for kind in ('plan', 'battle'))
                except Exception as error:
                    state['verified'] = str(error)
                restoration[copy] = state
            restoration_path.write_text(json.dumps(restoration, indent=2), encoding='utf-8')
        if pool_errors:
            raise RuntimeError('Native validation stopped fail-closed (no replacement): '
                               + '; '.join(pool_errors))
        if not all(state['verified'] is True for state in restoration.values()):
            raise RuntimeError('Roster restoration unverified; see roster-restoration.json')


if __name__ == '__main__':
    main()
