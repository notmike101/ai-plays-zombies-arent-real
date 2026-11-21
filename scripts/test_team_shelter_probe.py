"""Game-free regression checks for the shelter-opportunity probe driver:
session-bound physical attempts persist their passive trace BEFORE any
eligibility rejection (duplicates labelled ineligible, never promoted to
outcomes, never replaced), unbound attempts persist nothing, and both
rosters are always restored."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT)]

import team_shelter_probe as probe


@contextmanager
def fake_lock(path):
    yield path


def fake_operator(copy_root):
    import types
    return types.SimpleNamespace(
        LOCK=str(copy_root / 'lock'), training_lock=fake_lock,
        inventory=lambda: {}, require_idle=lambda *a, **k: None,
        preflight=lambda copy: {'ok': True, 'errors': []},
        require_resource_headroom=lambda n: None, limit_resources=lambda n: None,
        owned_copy=lambda copy: copy_root)


def level_with_trace():
    return dict(saved=90, win=False, end='aborted', start_kind='fresh',
                board='b1', log_started=123, ready_zones=[[[0., 0.], [1., 0.], [1., 1.]]],
                battle_actions=dict(
                    shelter_trace=[
                        dict(sim=.5, tick=10, decision=None, selected_tool=None,
                             selected_cell=None, legal_casts=None, stock=None,
                             zones=[dict(zone='abc', occupants=2)]),
                        dict(sim=1., tick=20, decision=3, selected_tool='Mine',
                             selected_cell=9, legal_casts=['Mine'], stock={'Mine': 1.},
                             zones=[]),
                    ],
                    shelter_trace_breaches=[dict(sim=1., tick=20, zone='abc', breach=1,
                                                 occupants_at_first_observed_breach=2)],
                    shelter_trace_gaps=[], shelter_trace_truncated=0,
                    shelter_trace_gap_dropped=0))


class ExecuteTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        settings = self.root / 'steam_cloud' / 'settings.ini'
        settings.parent.mkdir(parents=True)
        settings.write_text('roster_plan = Mortar Nest\nroster_battle = Sniper\n',
                            encoding='utf-8')
        self.settings = settings
        self.directory = self.root / 'journal'
        self.directory.mkdir()
        self.operator = fake_operator(self.root)
        self.result = dict(copy='inst19', seed=352571, levels=[level_with_trace()])

    def run_execute(self, chain, error, session):
        with mock.patch.object(probe.search, 'completed_rollouts',
                               lambda pool, jobs, **kw: iter([('job', 1, self.result)])), \
                mock.patch.object(probe.tta, 'official',
                                  lambda result: (result['levels'][0], chain, error)), \
                mock.patch.object(probe.compare, 'archive_native_session',
                                  lambda *a, **k: session):
            probe.execute(self.operator, self.directory, self.settings,
                          {'w': 1}, {'t': 1}, 'bf3fc52369fc3746',
                          {3266897190}, ('Garrison', 'Mine'), 'tag-0')
        return self.directory

    def read_rows(self, name):
        path = self.directory / name
        return [json.loads(line) for line in
                path.read_text(encoding='utf-8').splitlines()]

    def assert_roster_restored(self):
        text = self.settings.read_text(encoding='utf-8')
        self.assertIn('roster_plan = Mortar Nest', text)
        self.assertIn('roster_battle = Sniper', text)
        restoration = json.loads((self.directory / 'roster-restoration.json')
                                 .read_text(encoding='utf-8'))
        self.assertIs(restoration['inst19']['verified'], True)

    def test_duplicate_attempt_persists_trace_as_ineligible_then_fails_closed(self):
        with self.assertRaises(RuntimeError) as caught:
            self.run_execute([3266897190], None, {'status': 'archived', 'path': 'p'})
        self.assertIn('duplicate outbreak seed 3266897190', str(caught.exception))
        self.assertIn('no replacement', str(caught.exception))
        samples = self.read_rows('shelter-trace.jsonl')
        self.assertEqual([row['sim'] for row in samples], [.5, 1.])
        summary = json.loads((self.directory / 'shelter-trace-summary.json')
                             .read_text(encoding='utf-8'))
        self.assertIs(summary['eligible'], False)
        self.assertEqual(summary['ineligible_reason'], 'duplicate outbreak seed 3266897190')
        self.assertEqual(summary['samples_source'], 'journal')
        self.assertEqual((summary['samples'], summary['decisions_stamped']), (2, 1))
        self.assertEqual(summary['outbreak_seed'], 3266897190)
        self.assertEqual(len(summary['breach_rows']), 1)
        self.assertEqual(summary['cap'], 240)
        self.assertFalse((self.directory / 'outcomes.jsonl').exists())
        rows = self.read_rows('attempts.jsonl')
        self.assertEqual([row['status'] for row in rows], ['scheduled', 'finished'])
        finished = rows[1]
        self.assertIs(finished['eligible'], False)
        self.assertEqual(finished['ineligible_reason'], 'duplicate outbreak seed 3266897190')
        self.assertIs(finished['trace_persisted'], True)
        self.assertEqual(finished['trace_samples'], 2)
        self.assertFalse((self.directory / 'replacements.jsonl').exists())
        self.assert_roster_restored()

    def test_eligible_attempt_writes_one_outcome_and_trace(self):
        self.run_execute([900000001], None, {'status': 'archived', 'path': 'p'})
        outcomes = self.read_rows('outcomes.jsonl')
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]['team_id'], 'bf3fc52369fc3746')
        self.assertEqual(outcomes[0]['outbreak_seed'], 900000001)
        summary = json.loads((self.directory / 'shelter-trace-summary.json')
                             .read_text(encoding='utf-8'))
        self.assertIs(summary['eligible'], True)
        self.assertIsNone(summary['ineligible_reason'])
        rows = self.read_rows('attempts.jsonl')
        self.assertIs(rows[1]['eligible'], True)
        self.assert_roster_restored()

    def test_unbound_attempt_persists_no_trace_and_fails_closed(self):
        with self.assertRaises(RuntimeError) as caught:
            self.run_execute([900000002], None, {'status': 'missing'})
        self.assertIn('native session missing', str(caught.exception))
        self.assertFalse((self.directory / 'shelter-trace.jsonl').exists())
        self.assertFalse((self.directory / 'shelter-trace-summary.json').exists())
        self.assertFalse((self.directory / 'outcomes.jsonl').exists())
        rows = self.read_rows('attempts.jsonl')
        self.assertIs(rows[1]['trace_persisted'], False)
        self.assert_roster_restored()

    def test_launcher_failure_persists_no_trace_and_fails_closed(self):
        def boom(pool, jobs, **kw):
            raise RuntimeError('dead game')
            yield ()
        with mock.patch.object(probe.search, 'completed_rollouts', boom), \
                mock.patch.object(probe.tta, 'official') as official:
            with self.assertRaises(RuntimeError) as caught:
                probe.execute(self.operator, self.directory, self.settings,
                              {'w': 1}, {'t': 1}, 'bf3fc52369fc3746',
                              {3266897190}, ('Garrison', 'Mine'), 'tag-0')
        self.assertIn('launcher failure: dead game', str(caught.exception))
        official.assert_not_called()
        self.assertFalse((self.directory / 'shelter-trace.jsonl').exists())
        self.assertFalse((self.directory / 'outcomes.jsonl').exists())
        self.assert_roster_restored()


if __name__ == '__main__':
    unittest.main()
