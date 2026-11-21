"""Bounded private one-attempt shelter-opportunity trace (seed 352571).

Launches exactly one serial fresh-L1 RAW frozen parent bf3fc52369fc3746
attempt on inst19 (speed_1, click_start, training off, no updates) with the
original pinned GRU and unchanged model selection including READY. The only
addition is the opt-in passive Shelter trace: per 0.5 s battle samples it
records each closed zone's observed occupants, zombies inside, and outside
threat counts at the fixed 30/60/120 m rings plus the nearest outside
distance, stamped with the first decision's actual legal cast identities,
deck stock, and selected action after the sample, and one reserved
first-observed breach row per zone. Every receipt is sample-bounded: no
claim is made about transients between samples. Tracing performs no extra
native reads, no RNG, and no change to reward, observations, or masks; the
disabled path is byte-identical by construction. No challenger, no gate, no
replacement, no promotion path. Before launching, the three distinct stage-1
native outbreak seeds registered by the 350571 timing journal must all be
present in the exclusion audit. The single attempt fails closed on any
error, duplicate outbreak seed, or unverified roster restoration; the native
session is a bounded header-matched archive and both planning and battle
rosters are restored on every exit.
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
import shelter_reward
import team_search as search
import team_timing_ablation as tta

SEED = 352571
COPY = 'inst19'
JOURNAL = f'analysis/coverage-shelter-opportunity-{SEED}'
PRIOR_JOURNALS = ('analysis/coverage-team-timing-350571/outcomes.jsonl',)


def prior_seeds():
    """Every stage-1 outbreak seed registered by the prior 350571 timing
    journal, fail-closed on structure; the journal must hold exactly three
    distinct seeds (the duplicated child aborted before recording)."""
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
    weights, arms = tta.population_arms()
    if arms[0][:2] != ('parent', tta.TEAM_ID):
        raise ValueError('Population arms lead with something other than the RAW parent')
    tta.bundle('timing')
    seeds, counts, family = tta.exclusion_audit(ROOT / 'analysis')
    prior = prior_seeds()
    if len(prior) != 3 or not set(prior) <= set(seeds):
        raise ValueError('350571 three distinct native seeds not all excluded')
    return dict(profile='shelter-opportunity-probe', team=tta.TEAM_ID, base=tta.BASE_ID,
                incumbent=tta.TEAM_ID, seed=seed, copy=COPY, speed='speed_1',
                click_start=True, training=False, challenger=None, gate=None,
                trace_cap=shelter_reward.ZONE_TRACE_LIMIT,
                budget=dict(attempts=1, replacements=0, updates=0),
                prior_timing_seeds=prior,
                exclusion_sha256=hashlib.sha256(json.dumps(seeds).encode()).hexdigest(),
                exclusion_total=len(seeds), journals=len(counts),
                diagnostic_family=family, journal=JOURNAL)


def historical_planning_roster():
    """The RAW parent's own archived planning roster for this copy from the
    350571 timing outcomes, fail-closed on missing or ambiguous values."""
    historical = None
    for name in PRIOR_JOURNALS:
        for row in compare.records(ROOT / name):
            if (row.get('team_id') == tta.TEAM_ID and row.get('copy') == COPY):
                value = tuple(row.get('initial_planning_roster') or ())
                if value and historical is not None and historical != value:
                    raise ValueError(f'Ambiguous archived planning roster for {COPY}')
                historical = historical or value
    if not historical:
        raise ValueError(f'Missing archived parent planning roster for {COPY}')
    return historical


def execute(operator, directory, settings, weights, team, policy_id,
            exclusion, historical, tag):
    """Run the single registered attempt and persist it fail-closed.

    For every session-bound physical attempt the available passive trace is
    written BEFORE eligibility rejection, explicitly labelled with the
    ineligible reason; duplicates and other ineligibility never enter the
    eligible outcomes journal, never earn a replacement, and never rejoin
    unbound samples. Both rosters are restored and verified on every exit.
    """
    originals = tta.roster_lines(settings)
    restoration_path = directory / 'roster-restoration.json'
    state = {'verified': False}
    try:
        tta.set_line(settings, originals['plan'], ' '.join(historical).encode())
        result = dict(copy=COPY, seed=SEED, levels=[], error='pool never yielded')
        level, session, chain = {}, {}, []
        with (directory / 'attempts.jsonl').open('x', encoding='utf-8') as attempts:
            def record(row):
                attempts.write(json.dumps(row) + '\n')
                attempts.flush()
                os.fsync(attempts.fileno())

            record(dict(episode=tag, attempt=0, phase='probe', arm='parent',
                        copy=COPY, policy_seed=SEED, policy_id=policy_id,
                        status='scheduled'))
            try:
                with ProcessPoolExecutor(1) as pool:
                    for _, _, result in search.completed_rollouts(
                            pool, [(COPY, weights, team, SEED)],
                            click_start=True, speeds={COPY: 'speed_1'},
                            shelter_opportunity_probe=True):
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
            actions = level.get('battle_actions')
            samples = list((actions or {}).get('shelter_trace') or ())
            breaches = list((actions or {}).get('shelter_trace_breaches') or ())
            gaps = list((actions or {}).get('shelter_trace_gaps') or ())
            truncated = int((actions or {}).get('shelter_trace_truncated') or 0)
            gap_dropped = int((actions or {}).get('shelter_trace_gap_dropped') or 0)
            observed = chain[-1] if chain else None
            bound = (session.get('status') == 'archived' and observed is not None)
            eligible = error is None
            if bound:
                # Session-bound: the samples belong to this physical attempt,
                # so they are persisted even when eligibility rejects it.
                if actions is None or 'shelter_trace' not in actions:
                    samples_source = 'unlocated'
                elif not samples:
                    samples_source = 'journal_present_no_closed_zone_rows'
                else:
                    samples_source = 'journal'
                (directory / 'shelter-trace.jsonl').write_text(
                    ''.join(json.dumps(row) + '\n' for row in samples),
                    encoding='utf-8')
                (directory / 'shelter-trace-summary.json').write_text(json.dumps(dict(
                    copy=COPY, seed=SEED, outbreak_seed=observed,
                    board=level.get('board'), log_started=level.get('log_started'),
                    eligible=eligible, ineligible_reason=error,
                    samples_source=samples_source,
                    samples=len(samples),
                    decisions_stamped=sum(1 for row in samples
                                          if row.get('decision') is not None),
                    breach_rows=breaches, gaps=gaps,
                    truncated=truncated, gap_dropped=gap_dropped,
                    cap=shelter_reward.ZONE_TRACE_LIMIT),
                    indent=2), encoding='utf-8')
            finished = dict(episode=tag, attempt=0, phase='probe', arm='parent',
                            copy=COPY, policy_seed=SEED, policy_id=policy_id,
                            status='finished', err=error, eligible=eligible,
                            ineligible_reason=error, saved=level.get('saved'),
                            saved_frac=level.get('saved'), win=level.get('win'),
                            end=level.get('end'), start_kind=level.get('start_kind'),
                            outbreak_seed=observed,
                            prior_attempt_seeds=chain[:-1],
                            native_session=session,
                            ready_zones=level.get('ready_zones'),
                            board=level.get('board'),
                            log_started=level.get('log_started'),
                            trace_persisted=bound,
                            trace_samples=len(samples), trace_breach_rows=len(breaches),
                            trace_gaps=len(gaps), trace_truncated=truncated,
                            trace_gap_dropped=gap_dropped)
            record(finished)
            if error is None:
                with (directory / 'outcomes.jsonl').open('x', encoding='utf-8') as outcomes:
                    outcomes.write(json.dumps(dict(
                        result, arm='parent', team_id=policy_id,
                        outbreak_seed=observed, native_session=session)) + '\n')
            if error:
                raise RuntimeError(f'shelter opportunity probe failed closed (no '
                                   f'replacement): {tag}: {error}')
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true',
                        help='Launch the single parent attempt; default prints the offline plan')
    args = parser.parse_args()
    registration = plan()
    if not args.run:
        print(json.dumps(registration, indent=2))
        return
    weights, arms = tta.population_arms()
    team = arms[0][2]
    policy_id = tta.TEAM_ID
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
                'click_start', 'training', 'trace_cap', 'budget', 'prior_timing_seeds',
                'exclusion_sha256', 'exclusion_total', 'journal')},
            archive={'base.pt': tta.BASE_SHA, 'provisional.json': tta.PROVISIONAL_SHA},
            code_sha256={name: hashlib.sha256((Path(tta.__file__).resolve().parent / name)
                                              .read_bytes()).hexdigest()
                         for name in ('team_search.py', 'nn_play2.py', 'shelter_reward.py',
                                      'team_timing_ablation.py', 'team_shelter_probe.py')}),
            indent=2), encoding='utf-8')
        settings = operator.owned_copy(COPY) / 'steam_cloud/settings.ini'
        historical = historical_planning_roster()
    execute(operator, directory, settings, weights, team, policy_id,
            exclusion, historical, f'shelter-opportunity-{SEED}_probe_0_parent')


if __name__ == '__main__':
    main()
