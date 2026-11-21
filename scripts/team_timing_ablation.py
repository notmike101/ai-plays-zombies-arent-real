"""Registered layout-free team opening-timing ablation (seed 342571).

Frozen sampled incumbent 0d1d56160623a3a1 versus challenger 26be8cee926eaa85,
which removes only opening_cast_bias=2.0. Discovery: two paired policy seeds x
two arms, serial alternating copies, no replacements. Advance only on two
challenger NATURAL wins and a strictly higher official-saved mean across both
scheduled scored attempts per arm (finite scores mandatory even on abort;
native abort-retry chains count; nothing dropped); any unknown fails the gate.
Screen: four NEW paired policy seeds x two arms (evaluation rows for the unchanged 35% consistency
gate). Fresh L1 only, never a known outbreak, bound header-matched raw native
sessions, and both planning and battle rosters restored on every exit. No
promotion; no replacement ever.
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
COPIES = ['inst19', 'inst20']
MAX_PHYSICAL = 12
NATURAL = ('won', 'lost')
ROSTERS = {'plan': re.compile(rb'(?m)^roster_plan([ \t]*=[ \t]*)([^\r\n]*)'),
           'battle': re.compile(rb'(?m)^roster_battle([ \t]*=[ \t]*)([^\r\n]*)')}


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


def bundle():
    team = json.loads(read_verified('provisional.json', PROVISIONAL_SHA))['team']
    base = read_verified('base.pt', BASE_SHA)
    weights = torch.load(BytesIO(base), map_location='cpu', weights_only=True)
    policy = trainer.PolicyNet2()
    policy.load_state_dict(weights)
    if (search.team_id(team) != TEAM_ID or trainer.policy_id(policy) != BASE_ID
            or any(team.get(key) for key in ('layout', 'later_layouts'))):
        raise ValueError('Frozen bundle identity or layout mismatch')
    incumbent = dict(team, sample_garrison_sites=True)
    challenger = {key: value for key, value in incumbent.items() if key != 'opening_cast_bias'}
    if incumbent.get('opening_cast_bias') != 2.0:
        raise ValueError('Incumbent opening cast bias changed')
    if search.team_id(incumbent) != INCUMBENT_ID or search.team_id(challenger) != CHALLENGER_ID:
        raise ValueError('Arm identity does not match the registration')
    return weights, incumbent, challenger


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
    parser.add_argument('--run', action='store_true',
                        help='Run the registered twelve-attempt serial plan; default is offline validation only')
    args = parser.parse_args()
    weights, incumbent, challenger = bundle()
    arms = {'incumbent': (INCUMBENT_ID, incumbent), 'challenger': (CHALLENGER_ID, challenger)}
    seeds, counts, family = exclusion_audit(ROOT / 'analysis')
    if not args.run:
        print(json.dumps(dict(incumbent=INCUMBENT_ID, challenger=CHALLENGER_ID,
                              exclusion_sha256=hashlib.sha256(
                                  json.dumps(seeds).encode()).hexdigest(),
                              exclusion_total=len(seeds), journals=len(counts),
                              diagnostic_family=family,
                              plan=dict(discovery=4, screen=8, max_physical=MAX_PHYSICAL,
                                        policy_seeds=list(range(SEED, SEED + 6)))), indent=2))
        return
    directory = ROOT / f'analysis/coverage-team-timing-{SEED}'
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
            team=TEAM_ID, base=BASE_ID, incumbent=INCUMBENT_ID, challenger=CHALLENGER_ID,
            only_delta='opening_cast_bias 2.0 -> absent', seed=SEED, copies=COPIES,
            speed='speed_1', click_start=True, training=False, layout_replay=False,
            exclusion_sha256=hashlib.sha256(json.dumps(seeds).encode()).hexdigest(),
            exclusion_total=len(seeds), diagnostic_family=family,
            budget=dict(discovery=4, screen=8, max_physical=MAX_PHYSICAL, replacements=0),
            gate='two challenger natural wins and strictly higher natural mean; aborted diagnostic; unknown fails',
            previous_screen=PREVIOUS.name,
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
            for row in compare.records(PREVIOUS / 'holdout.jsonl'):
                if row.get('team_id') == INCUMBENT_ID and row.get('copy') in COPIES:
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
                    tag = f'team-timing-{SEED}_{phase}_{index}_{arm}'
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
                for index in range(4):
                    attempt(index, 'discovery', SEED + index // 2)
                    if pool_errors:
                        break
                decision = gate([row for row in rows if row['phase'] == 'discovery'])
                (directory / 'discovery-gate.json').write_text(
                    json.dumps(decision, indent=2), encoding='utf-8')
                if decision['advance'] and not pool_errors:
                    for index in range(8):
                        attempt(index, 'evaluation', SEED + 2 + index // 2)
                        if pool_errors:
                            break
                evaluation = [row for row in rows if row['phase'] == 'evaluation']
                decision = dict(decision, screen=gate(evaluation, per_arm=4) if evaluation else None,
                                promotion='registered 35% consistency screen owns promotion')
                (directory / 'decision.json').write_text(json.dumps(decision, indent=2), encoding='utf-8')
            native = compare.physical_attempts(directory / 'attempts.jsonl')
            (directory / 'consistency.json').write_text(json.dumps({
                actor: compare.heldout_consistency(native, actor, discovery_seeds=exclusion)
                for actor in (INCUMBENT_ID, CHALLENGER_ID)}, indent=2), encoding='utf-8')
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
