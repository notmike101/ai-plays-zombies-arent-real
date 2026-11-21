"""Offline fixture tests for team_timing_ablation (no game, no training).

Fake rollouts/operator/archive over a tmp analysis tree prove: the scheduled
fsync row lands before every launch, discovery uses two paired seeds and the
screen uses FOUR new policy seeds S+2..S+5 each once per arm on alternating
copies, duplicate or unknown outcomes fail closed without replacement, aborted
scores stay diagnostic-only, the run directory is never overwritten, and both
roster_plan and roster_battle come back byte-identical on every exit.
Run: python -m unittest test_team_timing_ablation from scripts/.
"""
import contextlib
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
os.chdir(REPO)
import compare_spatial as compare
import team_search as search
import team_timing_ablation as tta

REAL_SOURCE = Path(REPO) / 'analysis' / 'coverage-team-c81131e97f'
S = tta.SEED
SETTINGS = 'noise=1\nroster_plan = {} {}\nmid=2\nroster_battle={}\n'
ARCHIVED = {'inst19': ['alpha', 'beta'], 'inst20': ['gamma', 'delta']}
ORIGINALS = {'inst19': 'orig19 plan|b19', 'inst20': 'orig20 plan|b20'}


def lines(pairs):
    return [json.dumps(row) for row in pairs]

SETTINGS = 'noise=1\nroster_plan = {}\nmid=2\nroster_battle={}\n'

class FakeOperator:
    LOCK = 'fixture-lock'

    def __init__(self, root, headroom_fail_at=None):
        self.root = root
        self.headroom_fail_at = headroom_fail_at
        self.headroom_calls = []

    def training_lock(self, path):
        return contextlib.nullcontext()

    def inventory(self):
        return {}

    def require_idle(self, inventory, copy, pid, ancestor_pids=()):
        return None

    def preflight(self, copy):
        return {'ok': True, 'errors': []}

    def require_resource_headroom(self, copy_count):
        self.headroom_calls.append(copy_count)
        if self.headroom_fail_at == len(self.headroom_calls):
            raise ValueError('Insufficient headroom: need 2 GiB free disk')


    def limit_resources(self, limit):
        return None

    def owned_copy(self, copy):
        return self.root / 'copies' / copy


class FakePool:
    def __enter__(self):
        return 'pool'

    def __exit__(self, *error):
        return False


class Fixture:
    def __init__(self, root, script, archive_status='archived', headroom_fail_at=None):
        self.root = Path(root)
        self.script = script
        self.archive_status = archive_status
        self.headroom_fail_at = headroom_fail_at
        self.launches = []
        self.probe_failures = []
        self.archives = []
        analysis = self.root / 'analysis'
        analysis.mkdir(parents=True)
        family = analysis / tta.DIAGNOSTIC_FAMILY
        family.mkdir()
        scored = [dict(status='finished', end='lost', outbreak_seed=seed) for seed in (111, 222, 333, 444)]
        timeouts = [dict(status='finished', end='timeout', outbreak_seed=None) for _ in range(2)]
        (family / 'attempts.jsonl').write_text('\n'.join(lines(scored + timeouts)), encoding='utf-8')
        old = analysis / 'coverage-old'
        old.mkdir()
        (old / 'results.jsonl').write_text(
            '\n'.join(lines([dict(outbreak_seed=999)])), encoding='utf-8')
        (old / 'holdout.jsonl').write_text('\n'.join(lines([
            dict(levels=[dict(stage=1, outbreak={'seed': 888})])])), encoding='utf-8')
        previous = self.root / 'previous'
        previous.mkdir()
        (previous / 'holdout.jsonl').write_text('\n'.join(lines(
            [dict(team_id=tta.INCUMBENT_ID, copy=copy, initial_planning_roster=ARCHIVED[copy])
             for copy in tta.COPIES]
            + [dict(team_id=tta.CHALLENGER_ID, copy='inst21', initial_planning_roster=['x'])])),
            encoding='utf-8')
        for copy in tta.COPIES:
            settings = self.owned_copy(copy) / 'steam_cloud'
            settings.mkdir(parents=True)
            (settings / 'settings.ini').write_text(SETTINGS.format(*ORIGINALS[copy].split('|')),
                                                   encoding='utf-8')

    def owned_copy(self, copy):
        return self.root / 'copies' / copy

    def settings(self, copy):
        return self.owned_copy(copy) / 'steam_cloud' / 'settings.ini'

    def rollouts(self, pool, jobs, *, click_start, speeds):
        copy, weights, team, seed = jobs[0]
        journal = (self.root / 'analysis' / f'coverage-team-timing-{S}' / 'attempts.jsonl')
        rows = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()] \
            if journal.is_file() else []
        if not click_start or speeds != {copy: 'speed_1'} or not any(
                row['status'] == 'scheduled' and row['copy'] == copy and row['policy_seed'] == seed
                for row in rows):
            self.probe_failures.append((copy, seed))
        self.launches.append((copy, seed))
        spec = self.script.pop((copy, seed))
        if spec == 'raise':
            raise RuntimeError('boom')
        if spec.get('welcome_fail'):
            yield 'job', 'stage', dict(error='welcome boot', levels=[])
            return
        if spec.get('chain'):
            yield 'job', 'stage', dict(levels=[dict(stage=1, start_kind='fresh', **step)
                                               for step in spec['chain']])
            return
        level = dict(stage=1, start_kind='fresh', attempt=0, end=spec['end'], saved=spec.get('saved'),
                     win=spec['end'] == 'won', log_started=spec.get('log_started', 1000),
                     battle_actions={'deploy_sim_seconds': [1.0, 2.0, 3.0]},
                     outbreak={} if spec.get('outbreak') is None else {'seed': spec['outbreak']})
        yield 'job', 'stage', dict(levels=[level])

    def archive(self, copy_dir, run_dir, tag, copy, started_ms):
        self.archives.append((copy, tag, started_ms))
        return dict(status=self.archive_status, path=f'{tag}-{copy}.jsonl')

    def run(self, argv_run=True):
        argv = ['team_timing_ablation.py'] + (['--run'] if argv_run else [])
        saved = (sys.argv, tta.ROOT, tta.SOURCE, tta.PREVIOUS, tta.ProcessPoolExecutor,
                 search.operator, search.completed_rollouts, compare.archive_native_session)
        sys.argv = argv
        tta.ROOT = self.root
        tta.SOURCE = REAL_SOURCE
        tta.PREVIOUS = self.root / 'previous'
        tta.ProcessPoolExecutor = lambda count: FakePool()
        search.operator = self.operator = FakeOperator(self.root, self.headroom_fail_at)
        search.completed_rollouts = self.rollouts
        compare.archive_native_session = self.archive
        try:
            tta.main()
        finally:
            (sys.argv, tta.ROOT, tta.SOURCE, tta.PREVIOUS, tta.ProcessPoolExecutor,
             search.operator, search.completed_rollouts,
             compare.archive_native_session) = saved

    def attempts(self):
        return [json.loads(line) for line in
                (self.directory / 'attempts.jsonl').read_text(encoding='utf-8').splitlines()]

    @property
    def directory(self):
        return self.root / 'analysis' / f'coverage-team-timing-{S}'


def win(outbreak, saved=0.8):
    return dict(end='won', saved=saved, outbreak=outbreak)


def lost(outbreak, saved=0.2):
    return dict(end='lost', saved=saved, outbreak=outbreak)


HAPPY = {('inst19', S): win(5001, 0.9), ('inst20', S): win(5002, 0.8),
         ('inst19', S + 1): win(5004, 0.7), ('inst20', S + 1): lost(5003, 0.3)}
SCREEN = {('inst19', S + 2): lost(6001), ('inst20', S + 2): lost(6002),
          ('inst19', S + 3): lost(6003), ('inst20', S + 3): lost(6004),
          ('inst19', S + 4): lost(6005), ('inst20', S + 4): lost(6006),
          ('inst19', S + 5): lost(6007), ('inst20', S + 5): lost(6008)}


class TimingAblationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = self.temporary.name

    def fixture(self, script, **kwargs):
        return Fixture(self.root, dict(script), **kwargs)

    def rosters_intact(self):
        for copy in tta.COPIES:
            text = self.owned_settings(copy).read_text(encoding='utf-8')
            plan, battle = ORIGINALS[copy].split('|')
            self.assertEqual(text, SETTINGS.format(plan, battle))

    def owned_settings(self, copy):
        return Path(self.root) / 'copies' / copy / 'steam_cloud' / 'settings.ini'

    def test_happy_path_runs_all_twelve_and_restores(self):
        fixture = self.fixture({**HAPPY, **SCREEN})
        fixture.run()
        self.assertEqual(len(fixture.launches), 12)
        self.assertEqual(fixture.probe_failures, [])
        self.assertEqual(set(fixture.script), set())
        finished = [row for row in fixture.attempts() if row['status'] == 'finished']
        self.assertEqual(len(finished), 12)
        evaluation = [row for row in finished if row['phase'] == 'evaluation']
        self.assertEqual(len(evaluation), 8)
        for offset in range(4):
            rows = [row for row in evaluation if row['policy_seed'] == S + 2 + offset]
            self.assertEqual(sorted(row['arm'] for row in rows), ['challenger', 'incumbent'])
            self.assertEqual(sorted(row['copy'] for row in rows), ['inst19', 'inst20'])
            self.assertEqual({row['arm'] for row in rows if row['copy'] == 'inst19'},
                             {'incumbent'} if offset % 2 == 0 else {'challenger'})
        for row in evaluation:
            self.assertEqual(row['native_session']['status'], 'archived')
        gate = json.loads((fixture.directory / 'decision.json').read_text(encoding='utf-8'))
        self.assertTrue(gate['advance'])
        self.assertEqual(gate['challenger_wins'], 2)
        self.assertEqual(gate['slots'], {'challenger': 2, 'incumbent': 2})
        self.assertAlmostEqual(gate['challenger_mean'], (0.8 + 0.7) / 2)
        self.assertAlmostEqual(gate['incumbent_mean'], (0.9 + 0.3) / 2)
        self.assertEqual(gate['natural_only'], {'challenger': 0.75, 'incumbent': 0.6})
        self.assertEqual(fixture.operator.headroom_calls, [1] * 12)
        self.assertIsNotNone(gate['screen'])
        self.assertEqual(gate['screen']['slots'], {'challenger': 4, 'incumbent': 4})
        self.assertAlmostEqual(gate['screen']['challenger_mean'], 0.2)
        self.assertIn('consistency screen', gate['promotion'])
        consistency = json.loads((fixture.directory / 'consistency.json').read_text(encoding='utf-8'))
        for actor in (tta.INCUMBENT_ID, tta.CHALLENGER_ID):
            self.assertEqual(consistency[actor]['attempts'], 4)
            self.assertEqual(consistency[actor]['complete'], 4)
            self.assertEqual(consistency[actor]['discovery_overlap'], 0)
        restoration = json.loads((fixture.directory / 'roster-restoration.json').read_text(encoding='utf-8'))
        self.assertEqual([state['verified'] for state in restoration.values()], [True, True])
        self.rosters_intact()
        audit = json.loads((fixture.directory / 'exclusion-audit.json').read_text(encoding='utf-8'))
        self.assertEqual(audit['diagnostic_family'],
                         dict(attempts=6, scored_outbreaks=4, seedless_timeouts=2, inferred_seeds=0))
        self.assertEqual(set(audit['seeds']), {111, 222, 333, 444, 888, 999})
        self.assertEqual(compare.previous_outbreak_seeds(Path(self.root) / 'analysis'),
                         set(audit['seeds']) | {5001, 5002, 5003, 5004} | set(range(6001, 6009)))

    def test_rerun_never_overwrites(self):
        self.fixture({**HAPPY, **SCREEN}).run()
        with self.assertRaises(FileExistsError):
            self.fixture({**HAPPY, **SCREEN}).run()

    def test_duplicate_outbreak_fails_closed_without_screen(self):
        script = {('inst19', S): win(999), ('inst20', S): win(5002),
                  ('inst19', S + 1): win(5004), ('inst20', S + 1): lost(5003)}
        script.update(SCREEN)
        fixture = self.fixture(script)
        with self.assertRaisesRegex(RuntimeError, 'fail-closed'):
            fixture.run()
        self.assertEqual(len(fixture.launches), 1)
        self.assertFalse([row for row in fixture.attempts() if row['phase'] == 'evaluation'])
        finished = [row for row in fixture.attempts() if row['status'] == 'finished']
        self.assertTrue(any(row['err'] == 'duplicate outbreak seed 999' for row in finished))
        restoration = json.loads((fixture.directory / 'roster-restoration.json').read_text(encoding='utf-8'))
        self.assertEqual([state['verified'] for state in restoration.values()], [True, True])
        self.rosters_intact()

    def test_timeout_is_unknown_without_inferred_seed(self):
        script = {('inst19', S): dict(end='timeout', saved=None, outbreak=None),
                  ('inst20', S): win(5002), ('inst19', S + 1): win(5004),
                  ('inst20', S + 1): lost(5003)}
        fixture = self.fixture(script)
        with self.assertRaisesRegex(RuntimeError, 'fail-closed'):
            fixture.run()
        self.assertEqual(len(fixture.launches), 1)
        decision = json.loads((fixture.directory / 'decision.json').read_text(encoding='utf-8'))
        self.assertEqual(decision['unknowns'], [f'team-timing-{S}_discovery_0_incumbent'])
        self.assertFalse(decision['advance'])
        finished = [row for row in fixture.attempts() if row['status'] == 'finished'][0]
        self.assertIsNone(finished['outbreak_seed'])
        self.assertEqual(finished['end'], 'timeout')
        self.rosters_intact()

    def test_abort_counts_toward_mean_but_wins_gate_separately(self):
        script = {('inst19', S): win(5001, 0.9), ('inst20', S): win(5002, 0.8),
                  ('inst19', S + 1): dict(end='aborted', saved=0.55, outbreak=5004),
                  ('inst20', S + 1): lost(5003, 0.3)}
        fixture = self.fixture(script)
        fixture.run()
        self.assertEqual(len(fixture.launches), 4)
        gate = json.loads((fixture.directory / 'decision.json').read_text(encoding='utf-8'))
        self.assertFalse(gate['advance'])
        self.assertEqual(gate['challenger_wins'], 1)
        self.assertEqual(gate['unknowns'], [])
        self.assertAlmostEqual(gate['challenger_mean'], (0.8 + 0.55) / 2)
        self.assertAlmostEqual(gate['incumbent_mean'], (0.9 + 0.3) / 2)
        self.assertEqual(gate['natural_only'], {'challenger': 0.8, 'incumbent': 0.6})
        self.assertEqual(gate['diagnostics']['aborted']['challenger'], [0.55])
        self.assertIsNone(gate['screen'])
        self.rosters_intact()

    def test_registered_rule_rejects_natural_only_decision(self):
        script = {('inst19', S): win(5001, 0.6), ('inst20', S): win(5003, 0.5),
                  ('inst19', S + 1): win(5004, 0.45),
                  ('inst20', S + 1): dict(end='aborted', saved=0.1, outbreak=5002)}
        fixture = self.fixture({**script, **SCREEN})
        fixture.run()
        gate = json.loads((fixture.directory / 'decision.json').read_text(encoding='utf-8'))
        self.assertAlmostEqual(gate['challenger_mean'], (0.5 + 0.45) / 2)
        self.assertAlmostEqual(gate['incumbent_mean'], (0.6 + 0.1) / 2)
        self.assertTrue(gate['advance'])
        self.assertGreater(gate['natural_only']['incumbent'], gate['natural_only']['challenger'])
        self.assertIsNotNone(gate['screen'])
        self.rosters_intact()

    def test_abort_must_carry_finite_official_score(self):
        script = {('inst19', S): win(5001),
                  ('inst20', S): dict(end='aborted', saved=None, outbreak=5002),
                  ('inst19', S + 1): win(5004), ('inst20', S + 1): lost(5003)}
        fixture = self.fixture(script)
        with self.assertRaisesRegex(RuntimeError, 'fail-closed'):
            fixture.run()
        finished = [row for row in fixture.attempts() if row['status'] == 'finished']
        self.assertEqual(len(finished), 2)
        self.assertIn('official score missing', finished[1]['err'])
        gate = json.loads((fixture.directory / 'decision.json').read_text(encoding='utf-8'))
        self.assertEqual(gate['unknowns'], [f'team-timing-{S}_discovery_1_challenger'])
        self.rosters_intact()

    def test_native_abort_retry_chain_counts_and_consumes_both_outbreaks(self):
        chain = dict(chain=[dict(attempt=0, end='aborted', saved=0.099, outbreak={'seed': 7001}),
                            dict(attempt=1, end='lost', saved=0.2, outbreak={'seed': 7002})])
        script = {('inst19', S): chain, ('inst20', S): win(5002),
                  ('inst19', S + 1): win(7001), ('inst20', S + 1): lost(5003)}
        fixture = self.fixture(script)
        with self.assertRaisesRegex(RuntimeError, 'fail-closed'):
            fixture.run()
        finished = [row for row in fixture.attempts() if row['status'] == 'finished']
        self.assertEqual((finished[0]['end'], finished[0]['saved'], finished[0]['outbreak_seed']),
                         ('lost', 0.2, 7002))
        self.assertIn('duplicate outbreak seed 7001', finished[2]['err'])
        self.assertEqual(len(fixture.launches), 3)
        self.rosters_intact()

    def test_headroom_refusal_stops_before_third_launch(self):
        fixture = self.fixture({**HAPPY, **SCREEN}, headroom_fail_at=3)
        with self.assertRaisesRegex(ValueError, 'Insufficient headroom'):
            fixture.run()
        self.assertEqual(len(fixture.launches), 2)
        self.assertEqual(fixture.operator.headroom_calls, [1, 1, 1])
        self.assertFalse([row for row in fixture.attempts() if 'discovery_2' in row['episode']])
        restoration = json.loads((fixture.directory / 'roster-restoration.json').read_text(encoding='utf-8'))
        self.assertEqual([state['verified'] for state in restoration.values()], [True, True])
        self.rosters_intact()

    def test_missing_nonfinite_or_out_of_range_abort_score_is_unknown(self):
        base = dict(episode='x', phase='discovery', status='finished', err=None,
                    outbreak_seed=7, end='aborted', win=False)
        for bad in (None, float('nan'), 1.5, -0.1):
            rows = [dict(base, arm='challenger', saved=bad),
                    dict(base, arm='challenger', saved=0.5, outbreak_seed=8),
                    dict(base, arm='incumbent', end='lost', saved=0.4, outbreak_seed=9),
                    dict(base, arm='incumbent', end='won', saved=0.4, outbreak_seed=10)]
            self.assertTrue(tta.gate(rows)['unknowns'])
            self.assertFalse(tta.gate(rows)['advance'])

    def test_header_mismatch_fails_closed(self):
        script = {('inst19', S): win(5001), ('inst20', S): win(5002),
                  ('inst19', S + 1): win(5004), ('inst20', S + 1): lost(5003)}
        fixture = self.fixture(script, archive_status='header-mismatch')
        with self.assertRaisesRegex(RuntimeError, 'fail-closed'):
            fixture.run()
        decision = json.loads((fixture.directory / 'decision.json').read_text(encoding='utf-8'))
        self.assertIn('native session header-mismatch',
                      ' '.join(row['err'] for row in fixture.attempts() if row['status'] == 'finished'))
        self.assertFalse(decision['advance'])
        self.rosters_intact()

    def test_launcher_exception_finalizes_and_restores(self):
        script = {('inst19', S): 'raise', ('inst20', S): win(5002)}
        fixture = self.fixture(script)
        with self.assertRaisesRegex(RuntimeError, 'fail-closed'):
            fixture.run()
        finished = [row for row in fixture.attempts() if row['status'] == 'finished'][0]
        self.assertEqual(finished['err'], 'launcher failure: boom')
        restoration = json.loads((fixture.directory / 'roster-restoration.json').read_text(encoding='utf-8'))
        self.assertEqual([state['verified'] for state in restoration.values()], [True, True])
        self.rosters_intact()

    def test_missing_family_proof_blocks_before_any_launch(self):
        fixture = self.fixture({**HAPPY, **SCREEN})
        (Path(self.root) / 'analysis' / tta.DIAGNOSTIC_FAMILY / 'attempts.jsonl').write_text(
            '', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Diagnostic family exclusion proof failed'):
            fixture.run()
        self.assertEqual(fixture.launches, [])

    def test_planning_roster_is_staged_before_launch(self):
        fixture = self.fixture({**HAPPY, **SCREEN})
        original = fixture.settings('inst19').read_text(encoding='utf-8')
        inner = fixture.rollouts

        def spy(pool, jobs, **kwargs):
            text = fixture.settings(jobs[0][0]).read_text(encoding='utf-8')
            assert 'roster_plan = ' + ' '.join(ARCHIVED[jobs[0][0]]) in text, text
            return inner(pool, jobs, **kwargs)

        fixture.rollouts = spy
        fixture.run()
        self.assertEqual(fixture.settings('inst19').read_text(encoding='utf-8'), original)

    def test_gate_pure_semantics(self):
        row = dict(episode='x', phase='evaluation', status='finished', err=None, outbreak_seed=7,
                   end='won', saved=0.5, win=True)
        rows = [dict(row, arm='challenger'), dict(row, arm='challenger', outbreak_seed=8),
                dict(row, arm='incumbent', saved=0.4, outbreak_seed=9),
                dict(row, arm='incumbent', saved=0.4, outbreak_seed=10)]
        self.assertTrue(tta.gate(rows)['advance'])
        rows[0] = dict(rows[0], saved=0.4)
        rows[1] = dict(rows[1], saved=0.4)
        self.assertFalse(tta.gate(rows)['advance'])
        rows[0] = dict(rows[0], saved=0.5, end='aborted')
        self.assertFalse(tta.gate(rows)['advance'])
        rows[0] = dict(rows[0], end='won', saved=None)
        self.assertTrue(tta.gate(rows)['unknowns'])
        self.assertFalse(tta.gate(rows)['advance'])


if __name__ == '__main__':
    unittest.main()
