"""No live PIDs: planning polygon mask parity, discriminator and CLI wiring."""
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import numpy as np

import nn_play2 as train


class PlanningMaskTests(unittest.TestCase):
    def test_polygon_mask_applies_exact_geometry_without_audit_or_feedback(self):
        state = dict(planning=True, playarea_boundary=[(100, 100), (900, 100), (100, 700)])
        zone = train.TOOLS.index('zone_rect')
        candidate = dict(state, anchor=(zone, 5))
        train.update_geometry_masks(candidate, 1000, 1000, placement_feedback=False,
                                    planning_audit=False, planning_mask=False)
        self.assertNotIn('geometry_cells', candidate)
        self.assertTrue(train.masks_for(candidate)[0][zone])
        train.update_geometry_masks(candidate, 1000, 1000, placement_feedback=False,
                                    planning_audit=False, planning_mask=True)
        self.assertIn('geometry_cells', candidate)
        tools, cells = train.masks_for(candidate)
        self.assertFalse(tools[zone])
        self.assertTrue(tools[train.TOOLS.index('cancel_tool')])
        battle = dict(candidate, planning=False)
        train.update_geometry_masks(battle, 1000, 1000, placement_feedback=False,
                                    planning_audit=False, planning_mask=True)
        self.assertNotIn('geometry_cells', battle)

    def test_polygon_mask_preserves_screen_masks_when_polygon_covers_every_cell(self):
        centers = [train.cell_of_px(cell, 1000, 1000) for cell in range(train.NC)]
        state = dict(planning=True, build_targets=list(centers),
                     playarea_boundary=[(0, 0), (4000, 0), (4000, 4000), (0, 4000)])
        screen, exact = dict(state), dict(state)
        train.update_geometry_masks(exact, 1000, 1000, placement_feedback=False,
                                    planning_audit=False, planning_mask=True)
        screen_tools, screen_cells = train.masks_for(screen)
        exact_tools, exact_cells = train.masks_for(exact)
        np.testing.assert_array_equal(screen_tools, exact_tools)
        for tool in np.flatnonzero(screen_tools):
            np.testing.assert_array_equal(train.cell_mask(screen, tool, screen_cells),
                                          train.cell_mask(exact, tool, exact_cells))

    def test_planning_mask_pair_changes_only_the_mask_option(self):
        import compare_spatial as comp
        with patch.object(comp.operator, 'owned_copy'), patch.object(comp.zar_boot, 'boot'), \
                patch.object(comp.zar_boot, 'stop'), patch.object(train, 'run_episode') as run:
            for training in (True, False):
                options = []
                for arm, exact in comp.PLANNING_POLYGON_MASK.items():
                    comp.episode(('inst13', arm, {}, 123, 'test', training), audit_signal=True)
                    settings = run.call_args.args[0][4].copy()
                    self.assertEqual(settings.pop('planning_polygon_mask'), exact)
                    self.assertEqual(settings['experiment_signal'], 'receipts')
                    for untouched in ('fixed_speed', 'fixed_clock', 'planning_zone_audit',
                                      'ready_coverage_credit', 'occupied_breach_cost',
                                      'battle_boundary_filter', 'shelter_geometry_input',
                                      'settle_cast_target', 'gate_receipts'):
                        self.assertNotIn(untouched, settings)
                    options.append(settings)
                self.assertEqual(*options)

    def test_planning_masks_cli_uses_one_warm_actor_for_both_arms(self):
        import compare_spatial as comp
        torch = train.torch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'analysis').mkdir()
            net = train.PolicyNet2()
            adam = torch.optim.Adam(train.PolicyNet2().parameters(), lr=3e-4).state_dict()

            def collect(pool, jobs, run, **kwargs):
                return [dict(end='timeout', saved_frac=None, start_kind='fresh',
                             outbreak={'seed': 336500 + index}, us=[], obs=[],
                             battle_actions={}, reward_components={},
                             ready_choices={'legal_steps': 3, 'declined_steps': 3},
                             ready_stats=None, shelter=None,
                             outside_targets={'wall/41': 2 - index},
                             experiment_signal={'receipts': {'planning_polygon_mask': bool(index)}})
                        for index in range(len(jobs))]

            with patch('sys.argv', ['compare_spatial', '--copies', 'inst13', 'inst14',
                                    '--eval-copies', 'inst17', 'inst18', '--seed', '336571',
                                    '--train-rounds', '1', '--eval-rounds', '2',
                                    '--compare-planning-masks', '--warm-start', 'paired.pt',
                                    'preparation_control']), \
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
                                               {'arm': 'preparation_control', 'sha256': 'a' * 64})), \
                    patch.object(comp.trainer, 'valid_trajectory', lambda row: True), \
                    patch.object(comp.trainer, 'ppo_update', lambda *args, **kwargs: {}), \
                    patch.object(comp, 'retain_natural_win', lambda *args: -1.), \
                    patch.object(comp, 'collect_pairs', side_effect=collect):
                comp.main()
            run, = (root/'analysis').iterdir()
            self.assertTrue(run.name.startswith('coverage-planning-masks-'))
            rows = [json.loads(line) for line in (run/'results.jsonl').read_text().splitlines()]
            self.assertEqual({row['arm'] for row in rows}, {'mask_screen', 'mask_polygon'})
            self.assertEqual({row['policy_id'] for row in rows}, {train.policy_id(net)})
            training = [row for row in rows if row['phase'] == 'train']
            self.assertEqual(len(training), 2)
            for row in training:
                self.assertEqual(row['ready_choices']['legal_steps'], 3)
                self.assertIn(row['outside_playarea_targets'],
                              [{'wall/41': 2}, {'wall/41': 1}])
                self.assertIn('ready_stats', row)
                self.assertIn('shelter', row)
            snapshot = torch.load(run/'paired.pt', weights_only=False)
            self.assertEqual(snapshot['config']['comparison'], 'planning_polygon_mask')
            self.assertEqual(snapshot['config']['planning_polygon_mask_by_arm'],
                             {'mask_screen': False, 'mask_polygon': True})
            for name in snapshot['weights']['mask_screen']:
                self.assertTrue(torch.equal(snapshot['weights']['mask_screen'][name],
                                            snapshot['weights']['mask_polygon'][name]))


if __name__ == '__main__':
    unittest.main()
