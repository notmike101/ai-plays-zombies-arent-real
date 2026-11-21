"""No live PIDs: Gate receipt trace states, attempt budget, and frozen-single CLI wiring."""
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np

import nn_play2 as train


def completed_future(result):
    from concurrent.futures import Future
    future = Future()
    future.set_result(result)
    return future


def walls_array(*segments):
    walls = np.zeros(len(segments), dtype=[('a', '<f8', (2,)), ('b', '<f8', (2,))])
    for row, (a, b) in enumerate(segments):
        walls[row]['a'] = a
        walls[row]['b'] = b
    return walls


class GateReceiptTests(unittest.TestCase):
    def test_world_point_matches_native_camera_transform(self):
        self.assertEqual(train.gate_world_point((960., 100.), (100., 200., 2.), 1920, 1200).tolist(),
                         [100., 450.])

    def test_geometry_distances_nearest_wall_segment_and_gate(self):
        walls = walls_array(((0., 0.), (10., 0.)), ((0., 20.), (10., 20.)))
        result = train.gate_geometry_distances(np.array([5., 3.]), walls, np.array([[5., 12.]]))
        self.assertEqual((result['wall_distance'], result['wall_endpoints'], result['gate_distance']),
                         (3., [[0., 0.], [10., 0.]], 9.))
        empty = train.gate_geometry_distances(np.array([5., 3.]), walls_array(), np.empty((0, 2)))
        self.assertEqual(set(empty.values()), {None})

    def test_resolution_marks_resolved_late_and_unresolved(self):
        pending = dict(decision=3, world=[5., 3.])
        walls, gates = walls_array(((0., 0.), (10., 0.))), np.array([[5., 12.]])
        resolved = train.gate_receipt_resolution(pending, planning=True, gap=0, money=4499.,
                                                 camera=(1., 2., 2.), walls=walls, gates=gates)
        self.assertEqual((resolved['status'], resolved['observation_gap']), ('resolved', 0))
        self.assertEqual((resolved['money_after'], resolved['gates_after'],
                          resolved['gates_count_after'], resolved['gate_distance_after']),
                         (4499., [[5., 12.]], 1, 9.))
        late = train.gate_receipt_resolution(pending, planning=True, gap=2, money=4499.,
                                             camera=(1., 2., 2.), walls=walls, gates=gates)
        self.assertEqual((late['status'], late['observation_gap']), ('late', 2))
        for gap, planning in ((0, False), (-1, True)):
            self.assertEqual(train.gate_receipt_resolution(
                pending, planning=planning, gap=gap, money=0., camera=(0., 0., 1.),
                walls=walls, gates=gates), {'status': 'unresolved'})

    def test_collect_pairs_attempt_budget_one_forbids_transient_replacement(self):
        from compare_spatial import collect_pairs, physical_attempts
        jobs = [('inst19', 'standard', {}, 4242, 'only')]
        pool = Mock()
        pool.submit.side_effect = [completed_future({'err': 'Native map changed during read'})]
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            results = collect_pairs(pool, jobs, run, gate_receipts=True, max_attempts=1)
            self.assertEqual(results, [{'err': 'Native map changed during read'}])
            self.assertEqual(pool.submit.call_count, 1)
            self.assertEqual(pool.submit.call_args.args[0].keywords,
                             {'observe': False, 'audit_signal': True, 'gate_receipts': True})
            self.assertEqual([(row['attempt'], row['status'], row.get('err'))
                              for row in (json.loads(line) for line in
                                          (run/'attempts.jsonl').read_text().splitlines())],
                             [(0, 'scheduled', None), (0, 'finished', 'Native map changed during read')])
            self.assertEqual([(row['attempt'], row['status'], row.get('err'))
                              for row in physical_attempts(run/'attempts.jsonl')],
                             [(0, 'finished', 'Native map changed during read')])

    def test_frozen_standard_arm_is_plain_options_plus_receipt_flag(self):
        import compare_spatial
        with patch.object(compare_spatial.operator, 'owned_copy'), \
                patch.object(compare_spatial.zar_boot, 'boot'), \
                patch.object(compare_spatial.zar_boot, 'stop'), \
                patch.object(train, 'run_episode') as run:
            compare_spatial.episode(('inst19', 'standard', {}, 123, 'test'), audit_signal=True)
            self.assertEqual(run.call_args.args[0][4],
                             dict(start_kind='fresh', seed=123, missile_credit=True,
                                  fixed_speed='speed_1', fixed_clock=True,
                                  experiment_signal='receipts'))
            compare_spatial.episode(('inst19', 'standard', {}, 123, 'test'),
                                    audit_signal=True, gate_receipts=True)
            self.assertIs(run.call_args.args[0][4]['gate_receipts'], True)

    def test_frozen_single_rejects_invalid_combinations(self):
        import compare_spatial as comp
        for argv in (['--copies', 'inst19', '--train-rounds', '0'],
                     ['--copies', 'inst19', '--warm-start', 'actor.pt', 'standard',
                      '--train-rounds', '1', '--frozen-single'],
                     ['--copies', 'a', 'b', '--warm-start', 'actor.pt', 'standard',
                      '--frozen-single'],
                     ['--copies', 'inst19', '--warm-start', 'actor.pt', 'standard',
                      '--frozen-single', '--compare-battle-boundary']):
            with self.assertRaises(SystemExit), \
                    patch('sys.argv', ['compare_spatial', *argv, '--frozen-single']
                          if '--frozen-single' not in argv else ['compare_spatial', *argv]):
                comp.main()

    def test_frozen_single_runs_one_owned_attempt_without_replacement_or_training(self):
        import compare_spatial as comp
        torch = train.torch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'analysis').mkdir()
            net = train.PolicyNet2()
            adam = torch.optim.Adam(train.PolicyNet2().parameters(), lr=3e-4).state_dict()
            seen = []

            def collect(pool, jobs, run, *, observe, policy_ids, gate_receipts, max_attempts):
                seen.append(dict(jobs=jobs, observe=observe, gate_receipts=gate_receipts,
                                 max_attempts=max_attempts))
                return [dict(end='lost', saved_frac=.2, start_kind='fresh',
                             outbreak={'seed': 31},
                             battle_actions={'gate_receipts': [{'status': 'resolved'}],
                                             'gate_receipts_dropped': 2})]

            with patch('sys.argv', ['compare_spatial', '--copies', 'inst19', '--seed', '4242',
                                    '--train-rounds', '0', '--warm-start', 'actor.pt', 'standard',
                                    '--frozen-single', '--gate-receipts']), \
                    patch.object(comp.operator, 'ROOT', root), \
                    patch.object(comp.operator, 'training_lock', return_value=nullcontext()), \
                    patch.object(comp.operator, 'inventory', return_value=[]), \
                    patch.object(comp.operator, 'require_idle'), \
                    patch.object(comp.operator, 'preflight', return_value={'ok': True}), \
                    patch.object(comp.operator, 'limit_resources'), \
                    patch.object(comp.operator, 'require_resource_headroom'), \
                    patch.object(comp, 'ProcessPoolExecutor', return_value=nullcontext()), \
                    patch.object(comp, 'load_warm_start',
                                 return_value=(net.state_dict(), adam, {123},
                                               {'arm': 'standard', 'sha256': 'a' * 64})), \
                    patch.object(comp, 'collect_pairs', side_effect=collect):
                comp.main()
            self.assertEqual(len(seen), 1)
            self.assertEqual((seen[0]['observe'], seen[0]['gate_receipts'], seen[0]['max_attempts']),
                             (False, True, 1))
            job, = seen[0]['jobs']
            self.assertEqual((job[0], job[1], job[3], job[5]), ('inst19', 'standard', 4242, False))
            run, = (root/'analysis').iterdir()
            self.assertTrue(run.name.startswith('coverage-frozen-single-'))
            summary, = (run/'results.jsonl').read_text().splitlines()
            summary = json.loads(summary)
            self.assertEqual((summary['gate_receipts'], summary['gate_receipts_dropped']),
                             ([{'status': 'resolved'}], 2))
            manifest = json.loads((run/'frozen-manifest.json').read_text())
            self.assertEqual(manifest['config']['frozen_single'], True)
            self.assertEqual(manifest['config']['eval_rounds'], 1)
            self.assertEqual(manifest['config']['copies'], ['inst19'])
            self.assertFalse((run/'paired.pt').exists())


if __name__ == '__main__':
    unittest.main()
