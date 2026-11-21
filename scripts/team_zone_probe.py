"""Bounded private one-attempt zone-lookahead diagnostic (seed 346571).

Launches exactly one serial fresh-L1 incumbent 0d1d56160623a3a1 attempt on
inst19 (speed_1, click_start, training off, no updates) from the frozen
layout-free timing bundle. Every naturally-selected unanchored zone_rect
planning decision (up to 24 receipts) records its final effective cell
logits, the actual legal mask and sampled cell, and the lookahead gain
vector plus lookahead-replayed logits recomputed by shared scoring on the
same native snapshot in the exact production float32 operation order
(zone bias, then plan grid term, then distance). No challenger, no gate,
no replacement, no promotion path. The single attempt fails closed on any
error, duplicate outbreak seed, or unverified roster restoration; the
native session is a bounded header-matched archive and both planning and
battle rosters are restored on every exit.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT)]

import psutil

import compare_spatial as compare
import nn_play2 as trainer
import team_search as search
import team_timing_ablation as tta

SEED = 346571
COPY = 'inst19'
JOURNAL = f'analysis/coverage-zone-lookahead-{SEED}'
PRIOR_JOURNALS = ('analysis/coverage-team-timing-342571/outcomes.jsonl',
                  'analysis/coverage-team-timing-344571/outcomes.jsonl')


def prior_seeds():
    """Every stage-1 outbreak seed registered by the two prior timing
    journals, fail-closed on structure; the 344571 journal may legitimately
    hold fewer than four rows (pair-two stop), so all found rows count."""
    found = set()
    for name in PRIOR_JOURNALS:
        if not (ROOT / name).is_file():
            continue
        found.update(level['outbreak']['seed']
                     for row in compare.records(ROOT / name)
                     for level in row.get('levels') or ()
                     if level.get('stage') == 1 and type(level.get('outbreak')) is dict
                     and type(level['outbreak'].get('seed')) is int)
    return sorted(found)


def plan(seed=SEED):
    tta.bundle('timing')
    seeds, counts, family = tta.exclusion_audit(ROOT / 'analysis')
    prior = prior_seeds()
    if not prior or not set(prior) <= set(seeds):
        raise ValueError('Registered timing discovery seeds are not all excluded')
    return dict(profile='zone-lookahead-probe', team=tta.TEAM_ID, base=tta.BASE_ID,
                incumbent=tta.INCUMBENT_ID, seed=seed, copy=COPY, speed='speed_1',
                click_start=True, training=False, challenger=None, gate=None,
                probe_cap=trainer.ZONE_PROBE_LIMIT,
                budget=dict(attempts=1, replacements=0, updates=0),
                prior_timing_seeds=prior,
                exclusion_sha256=hashlib.sha256(json.dumps(seeds).encode()).hexdigest(),
                exclusion_total=len(seeds), journals=len(counts),
                diagnostic_family=family, journal=JOURNAL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true',
                        help='Launch the single incumbent attempt; default prints the offline plan')
    args = parser.parse_args()
    registration = plan()
    if not args.run:
        print(json.dumps(registration, indent=2))
        return
    weights, incumbent, _ = tta.bundle('timing')
    policy_id = tta.INCUMBENT_ID
    seeds = tta.exclusion_audit(ROOT / 'analysis')[0]
    exclusion = set(seeds)
    directory = ROOT / JOURNAL
    directory.mkdir()
    operator = search.operator
    with operator.training_lock(operator.LOCK):
        operator.require_idle(operator.inventory(), COPY, os.getpid(),
                              ancestor_pids=[p.pid for p in psutil.Process().parents()])
        if not (check := operator.preflight(COPY))['ok']:
            raise RuntimeError('; '.join(check['errors']))
        operator.require_resource_headroom(1)
        operator.limit_resources(1)
        (directory / 'exclusion-audit.json').write_text(json.dumps(
            dict(seeds=seeds, diagnostic_family=registration['diagnostic_family']),
            indent=2), encoding='utf-8')
        (directory / 'frozen-manifest.json').write_text(json.dumps(dict(
            **{key: registration[key] for key in
               ('profile', 'team', 'base', 'incumbent', 'seed', 'copy', 'speed',
                'click_start', 'training', 'probe_cap', 'budget', 'prior_timing_seeds',
                'exclusion_sha256', 'exclusion_total', 'journal')},
            archive={'base.pt': tta.BASE_SHA, 'provisional.json': tta.PROVISIONAL_SHA},
            code_sha256={name: hashlib.sha256((Path(tta.__file__).resolve().parent / name)
                                              .read_bytes()).hexdigest()
                         for name in ('team_search.py', 'nn_play2.py',
                                      'team_timing_ablation.py', 'team_zone_probe.py')}),
            indent=2), encoding='utf-8')
        settings = operator.owned_copy(COPY) / 'steam_cloud/settings.ini'
        originals = tta.roster_lines(settings)
        restoration_path = directory / 'roster-restoration.json'
        tag = f'zone-lookahead-{SEED}_probe_0_incumbent'
        state = {'verified': False}
        try:
            historical = None
            for row in compare.records(tta.PREVIOUS / 'holdout.jsonl'):
                if row.get('team_id') == tta.INCUMBENT_ID and row.get('copy') == COPY:
                    value = tuple(row.get('initial_planning_roster') or ())
                    if value and historical is not None and historical != value:
                        raise ValueError(f'Ambiguous archived planning roster for {COPY}')
                    historical = historical or value
            if not historical:
                raise ValueError(f'Missing archived incumbent planning roster for {COPY}')
            tta.set_line(settings, tta.roster_lines(settings)['plan'],
                         ' '.join(historical).encode())
            result = dict(copy=COPY, seed=SEED, levels=[], error='pool never yielded')
            level, session, chain = {}, {}, []
            with (directory / 'attempts.jsonl').open('x', encoding='utf-8') as attempts:
                def record(row):
                    attempts.write(json.dumps(row) + '\n')
                    attempts.flush()
                    os.fsync(attempts.fileno())

                record(dict(episode=tag, attempt=0, phase='probe', arm='incumbent',
                            copy=COPY, policy_seed=SEED, policy_id=policy_id,
                            status='scheduled'))
                try:
                    with ProcessPoolExecutor(1) as pool:
                        for _, _, result in search.completed_rollouts(
                                pool, [(COPY, weights, incumbent, SEED)],
                                click_start=True, speeds={COPY: 'speed_1'},
                                zone_lookahead_probe=True):
                            pass
                    level, chain, error = tta.official(result)
                    if error is None:
                        for consumed in chain:
                            if consumed in exclusion:
                                error = f'duplicate outbreak seed {consumed}'
                                break
                    session = compare.archive_native_session(
                        operator.owned_copy(COPY), directory, tag, COPY,
                        level.get('log_started'))
                    if error is None and session.get('status') != 'archived':
                        error = f'native session {session.get("status")}'
                except Exception as failure:
                    level, session, chain = {}, {}, []
                    error = f'launcher failure: {failure}'
                actions = level.get('battle_actions') or {}
                receipts = list(actions.get('zone_lookahead') or ())
                truncated = int(actions.get('zone_lookahead_truncated') or 0)
                observed = chain[-1] if chain else None
                finished = dict(episode=tag, attempt=0, phase='probe', arm='incumbent',
                                copy=COPY, policy_seed=SEED, policy_id=policy_id,
                                status='finished', err=error, saved=level.get('saved'),
                                saved_frac=level.get('saved'), win=level.get('win'),
                                end=level.get('end'), start_kind=level.get('start_kind'),
                                outbreak_seed=observed,
                                prior_attempt_seeds=chain[:-1],
                                native_session=session,
                                ready_zones=level.get('ready_zones'),
                                board=level.get('board'),
                                log_started=level.get('log_started'),
                                probe_receipts=len(receipts), probe_truncated=truncated)
                record(finished)
                if error is None:
                    with (directory / 'outcomes.jsonl').open('x', encoding='utf-8') as outcomes:
                        outcomes.write(json.dumps(dict(
                            result, arm='incumbent', team_id=policy_id,
                            outbreak_seed=observed, native_session=session)) + '\n')
                    (directory / 'zone-probe.jsonl').write_text(
                        ''.join(json.dumps(row) + '\n' for row in receipts),
                        encoding='utf-8')
                    (directory / 'probe-summary.json').write_text(json.dumps(dict(
                        copy=COPY, seed=SEED, outbreak_seed=observed,
                        board=level.get('board'), log_started=level.get('log_started'),
                        receipts=len(receipts), truncated=truncated,
                        cap=trainer.ZONE_PROBE_LIMIT,
                        argmax_differs=sum(1 for row in receipts
                                           if row['lookahead_argmax'] != row['actual_argmax']),
                        argmax_ties_differ=sum(1 for row in receipts
                                               if row['lookahead_ties'] != row['actual_ties']),
                        greedy_matches_selected=sum(1 for row in receipts
                                                    if row['cell'] == row['actual_argmax'])),
                        indent=2), encoding='utf-8')
                if error:
                    raise RuntimeError(f'zone probe failed closed (no replacement): '
                                       f'{tag}: {error}')
        finally:
            for kind in ('plan', 'battle'):
                try:
                    tta.set_line(settings, tta.roster_lines(settings)[kind],
                                 originals[kind].group(2))
                    state[kind] = True
                except Exception as restore_error:
                    state[kind] = str(restore_error)
            try:
                current = tta.roster_lines(settings)
                state['verified'] = all(
                    current[kind].group(2) == originals[kind].group(2)
                    for kind in ('plan', 'battle'))
            except Exception as restore_error:
                state['verified'] = str(restore_error)
            restoration_path.write_text(json.dumps({COPY: state}, indent=2),
                                        encoding='utf-8')
        if state['verified'] is not True:
            raise RuntimeError('Roster restoration unverified; see roster-restoration.json')


if __name__ == '__main__':
    main()
