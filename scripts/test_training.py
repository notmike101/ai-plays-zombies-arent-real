"""Offline trainer regressions. Never attach to a game PID."""
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
import nn_play2 as train


class LearningTests(unittest.TestCase):
    def test_battle_credit_survives_long_planning_prefix(self):
        for n in (0, 20, 60):
            rews, vals = [0.]*n+[2.], [.3]*n+[.5]
            adv, ret = train.gae(rews, vals, planning=[True]*n+[False])
            self.assertAlmostEqual(ret[0], 2.)
            self.assertAlmostEqual(adv[0], 2.-vals[0])

    def test_phase_aware_gae_preserves_battle_discount_and_bootstrap(self):
        _, ret = train.gae([0., 0.], [0., 0.], planning=[True, False],
                           gamma=.5, lam=1., bootstrap=4.)
        np.testing.assert_allclose(ret, [4., 2.])
        with self.assertRaises(ValueError):
            train.gae([1.], [0.], planning=[])

    def test_planning_receives_measured_outcome_after_long_battle(self):
        rewards = [0., 0., -.2, -.3, 1.75]
        vals = [.7, -.1, .4, -.8, .3]
        phases = [True, True, False, False, False]
        elapsed = [0., 0., 10., 20., .1]
        adv, ret = train.gae(rewards, vals, planning=phases, sim_elapsed=elapsed)
        np.testing.assert_allclose(ret[:2], [1.25, 1.25])
        np.testing.assert_allclose(adv[:2], [.55, 1.35])
        _, battle = train.gae(rewards[2:], vals[2:], sim_elapsed=elapsed[2:])
        np.testing.assert_allclose(ret[2:], battle)

    def test_paused_decisions_do_not_attenuate_battle_credit(self):
        _, normal = train.gae([0., -1.], [.2, .3], sim_elapsed=[.1, .1])
        _, paused = train.gae([0., 0., 0., -1.], [.2, .2, .2, .3],
                              sim_elapsed=[0., 0., .1, .1])
        self.assertAlmostEqual(normal[0], paused[0])

    def test_battle_discount_scales_with_simulation_elapsed(self):
        _, ret = train.gae([0., 1.], [0., 0.], gamma=.9, lam=.8,
                           sim_elapsed=[.2, .1])
        self.assertAlmostEqual(ret[0], (.9 * .8)**2)
        with self.assertRaisesRegex(ValueError, 'elapsed'):
            train.gae([0.], [0.], sim_elapsed=[float('nan')])

    def test_picker_cooldown_masks_only_the_rejected_purchase(self):
        st=dict(planning=True, costs={'Police': 1, 'Bomber': 1},
                unlocked=['Police', 'Bomber'], sp=2)
        police, bomber = (train.TOOLS.index('buy_'+name) for name in ('Police','Bomber'))
        self.assertEqual(train.masks_for(st)[0][bomber],1)
        st['picker_blocked']=[(bomber,0)]
        mask,_=train.masks_for(st)
        self.assertEqual(mask[bomber],0)
        self.assertEqual(mask[police],1)

    def test_spatial_actions_cannot_click_the_planning_hud(self):
        st = dict(planning=True, deck=[])
        for tool in range(2, 34):
            mask = train.cell_mask(st, tool, np.ones(train.NC))
            for cell in np.flatnonzero(mask):
                self.assertLess(train.cell_of_px(cell, 1920, 1200)[1], 840)

    def test_planning_geometry_keeps_only_viable_start_and_end_cells(self):
        boundary = [(100, 100), (900, 100), (100, 700)]
        state = dict(planning=True, playarea_boundary=boundary)
        starts = train.planning_geometry_masks(state, 1000, 1000)
        for tool in (10, 15, 17, 18):
            start_cells = []
            for start in range(train.NC):
                active = dict(state, anchor=(tool, start))
                geometry = train.planning_geometry_masks(active, 1000, 1000)
                active['geometry_cells'] = geometry
                tools, cells = train.masks_for(active)
                expected = [train.WORLD_CELLS[start] and train.WORLD_CELLS[end] and end != start
                            and (tool != 10 or (start // 8 != end // 8 and start % 8 != end % 8))
                            and not train.outside_playarea(active, tool, end, 1000, 1000)
                            for end in range(train.NC)]
                np.testing.assert_array_equal(train.cell_mask(active, tool, cells), expected)
                self.assertEqual(bool(tools[tool]), any(expected))
                self.assertTrue(tools[train.TOOLS.index('cancel_tool')])
                start_cells.append(any(expected))
            np.testing.assert_array_equal(starts[tool], start_cells)
        self.assertEqual(train.planning_geometry_masks(dict(state, planning=False), 1000, 1000), {})

    def test_battle_geometry_filters_unplayable_clicks_and_cast_endpoints(self):
        state = dict(planning=False, playarea_boundary=[(0, 0), (900, 0), (50, 900), (0, 900)],
                     sim=40, deck=[dict(name=name, key='1', unlock=20, pending=False, charges=1)
                                   for name in ('Firebomb', 'Demolition')])
        targets = [None] * train.NC
        targets[10], targets[15] = (900, 200), (100, 100)
        state['battle_targets'] = {24: targets}
        for current in (
                state, dict(state, anchor=(24, 10)), dict(state, anchor=(24, 15))):
            masks = train.battle_geometry_masks(current, 1000, 1000)
            self.assertTrue(masks)
            for tool, mask in masks.items():
                np.testing.assert_array_equal(
                    mask, [not train.outside_playarea(current, tool, cell, 1000, 1000)
                           for cell in range(train.NC)])
        current = dict(state, anchor=(24, 10))
        current['geometry_cells'] = train.battle_geometry_masks(current, 1000, 1000)
        tools, _ = train.masks_for(current)
        self.assertFalse(tools[24])
        self.assertTrue(tools[train.TOOLS.index('cancel_tool')])

    def test_battle_geometry_uses_pending_gesture_created_by_live_controls(self):
        mechanics = train.Mechanics.__new__(train.Mechanics)
        mechanics.env = SimpleNamespace(cw=1000, ch=1000)
        mechanics.controls = None
        for name, start in (('shift_drag_world', 15), ('drag_world', 8), ('select_box', 8)):
            with self.subTest(tool=name):
                state = dict(planning=False, playarea_boundary=[(0, 0), (900, 0), (50, 900), (0, 900)])
                mechanics.execute(state, name, start)
                self.assertEqual(state['gesture_anchor'], (name, start))
                masks = train.battle_geometry_masks(state, 1000, 1000)
                if name == 'select_box':
                    self.assertEqual(masks, {})
                    continue
                tool = train.TOOLS.index(name)
                np.testing.assert_array_equal(
                    masks[tool], [not train.outside_playarea(state, tool, cell, 1000, 1000)
                                  for cell in range(train.NC)])

    def test_unconfirmed_building_retries_apply_only_to_the_same_target_and_camera(self):
        targets = [None] * train.NC
        targets[34], targets[35] = (430, 560), (520, 560)
        camera = (1631., 1318., .58)
        st = dict(planning=True, build_targets=targets, native=dict(camera=camera))
        retries = {(2, 35): (8, camera, targets[35])}
        masked = dict(planning=True, build_targets=targets,
                      placement_blocked=train.blocked_placement_cells(st, retries, 4))
        tools, cells = train.masks_for(masked)
        self.assertTrue(tools[2])
        self.assertFalse(train.cell_mask(masked, 2, cells)[35])
        self.assertTrue(train.cell_mask(masked, 2, cells)[34])
        self.assertTrue(train.cell_mask(masked, 3, cells)[35])
        targets[34] = None
        self.assertFalse(train.masks_for(masked)[0][2])
        self.assertEqual(train.blocked_placement_cells(st, retries, 8), {})
        targets[35] = (526, 560)
        self.assertEqual(train.blocked_placement_cells(st, retries, 4), {})
        targets[35] = (520, 560)
        st['native']['camera'] = (1635., 1318., .58)
        self.assertEqual(train.blocked_placement_cells(st, retries, 4), {})

    def test_building_tools_require_a_target_above_the_hud(self):
        targets = [None]*train.NC
        targets[-1] = np.array([1680, 912])
        mu, _ = train.masks_for(dict(planning=True, deck=[], build_targets=targets))
        self.assertTrue(all(mu[u] == 0 for u in (2, 3, 5, 8, 9)))

    def test_ppo_updates_with_conditional_cell_masks_and_finite_diagnostics(self):
        net = train.PolicyNet2()
        obs = np.zeros((2, train.NOBS), dtype=np.float32)
        mu, mc = np.zeros(train.NU), np.zeros(train.NC)
        mu[2], mc[3] = 1, 1
        tr = dict(obs=obs, us=[2,2], cs=[3,3], ulps=[0.,0.], clps=[0.,0.],
                  masks=[(mu,mc)]*2, rews=[0.,1.], sim_elapsed=[.1,.1], bootstrap=0.)
        before = train.policy_id(net)
        opt = torch.optim.Adam(net.parameters(), lr=3e-4)
        diag = train.ppo_update(net, [tr], opt, epochs=1)
        self.assertNotEqual(train.policy_id(net), before)
        self.assertAlmostEqual(diag['approx_kl'], 0.)
        self.assertEqual(diag['clip_fraction'], 0.)
        self.assertEqual(diag['entropy'], 0.)
        self.assertTrue(all(v is None or np.isfinite(v) for v in diag.values()))

    def test_extra_tool_entropy_shapes_only_planning_loss(self):
        net = train.PolicyNet2()
        obs = np.zeros((2, train.NOBS), dtype=np.float32)
        mu, mc = np.zeros(train.NU), np.zeros(train.NC)
        mu[1:3], mc[3] = 1, 1
        tr = dict(obs=obs, us=[1,2], cs=[3,3], ulps=[-.7,-.7], clps=[0.,0.],
                  masks=[(mu,mc)]*2, rews=[0.,1.], sim_elapsed=[.1,.1], bootstrap=0.)
        opt = torch.optim.SGD(net.parameters(), lr=0.)
        def loss(bonus):
            return train.ppo_update(net, [tr], opt, epochs=1,
                                    planning_tool_entropy_bonus=bonus)['loss']

        self.assertEqual(loss(.045), loss(0.))
        obs[0, train.PLANNING_INDEX] = 1.
        bonus_delta = loss(0.) - loss(.045)
        self.assertGreater(bonus_delta, .025)
        self.assertLess(bonus_delta, .035)

    def test_early_loadout_records_native_flight_and_delay_fields(self):
        rules = dict(police_unlock_seconds=0, police_arrival_seconds=8,
                     missile_unlock_seconds=30, missile_flight_seconds=2.5,
                     nuke_unlock_seconds=90, nuke_delay_seconds=45)
        offers = dict(costs={'Police': 1, 'Missile': 2, 'Nuke': 15},
                      unlocked={'Police', 'Missile', 'Nuke'}, sp=2, rules=rules)
        self.assertEqual(train.opening_loadout_options(offers),
                         {'Police': {'cost': 1, 'first_effect': 8.},
                          'Missile': {'cost': 2, 'first_effect': 32.5}})
        self.assertEqual(train.opening_loadout_options(dict(offers, sp=15))['Nuke'],
                         {'cost': 15, 'first_effect': 135.})
        del rules['missile_flight_seconds']
        self.assertNotIn('Missile', train.opening_loadout_options(offers))

    def test_loadout_mask_requires_unlocked_affordable_skill_points(self):
        st = dict(planning=True, loadout={'Police': 1}, sp=1,
                  costs={'Police': 1, 'Heli': 2, 'Stungas': 1}, unlocked={'Police', 'Heli'})
        mu, _ = train.masks_for(st)
        self.assertEqual(mu[34], 1)
        self.assertEqual(mu[36], 0)
        self.assertEqual(mu[37], 0)
        self.assertEqual(mu[53], 1)

    def test_actual_roster_preserves_gaps_and_reordered_hotkeys(self):
        dump = {'economy': {'loadout Police': '1', 'loadout Heli': '1'},
                'config': {'heli_unlock_seconds': '30'}}
        deck = train.build_deck(dump, list('123456T'), ['Heli', '-', 'Police', '-', '-', '-', '-'])
        self.assertEqual([(s['name'], s['key'], s['unlock']) for s in deck],
                         [('Heli', '1', 30), ('Police', '3', 0)])

    def test_cell_distribution_depends_on_selected_tool(self):
        logits = torch.zeros(train.NU * train.NC)
        logits[2*train.NC+3] = 20
        logits[3*train.NC+9] = 20
        self.assertEqual(int(train.cell_distribution(logits, 2, np.ones(train.NC)).probs.argmax()), 3)
        self.assertEqual(int(train.cell_distribution(logits, 3, np.ones(train.NC)).probs.argmax()), 9)

    def test_rejected_cells_stay_masked_until_the_target_becomes_legal(self):
        st=dict(planning=False,
                deck=[dict(name='Missile',key='1',charges=1,unlock=0,pending=False)],
                sim=0.,playarea_boundary=[(0,0),(500,0),(500,900),(0,900)],
                outside_retries={26:{7}})
        train.update_outside_retries(st,1920,1200)
        tools,cells=train.masks_for(st)
        self.assertTrue(tools[26])
        self.assertFalse(train.cell_mask(st,26,cells)[7])
        st['world_cells']=np.eye(1,train.NC,k=7,dtype=bool)[0]
        tools,_=train.masks_for(st)
        self.assertFalse(tools[26])
        self.assertTrue(tools[0])
        st['playarea_boundary']=[(0,0),(1920,0),(1920,1200),(0,1200)]
        train.update_outside_retries(st,1920,1200)
        tools,cells=train.masks_for(st)
        self.assertTrue(tools[26])
        self.assertTrue(train.cell_mask(st,26,cells)[7])

    def test_boundary_checks_actual_building_and_both_battle_endpoints(self):
        boundary=[(0,0),(500,0),(500,900),(0,900)]
        targets=[None]*48
        targets[7]=(450,220)
        st=dict(planning=True,playarea_boundary=boundary,build_targets=targets)
        self.assertFalse(train.outside_playarea(st,2,7,1920,1200))
        self.assertTrue(train.outside_playarea(st,4,7,1920,1200))
        st.update(planning=False,anchor=(22,0))
        self.assertTrue(train.outside_playarea(st,22,7,1920,1200))
        self.assertFalse(train.outside_playarea(st,22,8,1920,1200))
        self.assertFalse(train.outside_playarea(st,train.TOOLS.index('zoom_out'),7,1920,1200))

    def test_targeted_abilities_snap_only_the_target_not_drag_direction(self):
        targets=[None]*48;targets[9]=(433,344)
        st={'planning':False,'battle_targets':{19:targets,24:targets}}
        self.assertEqual(np.flatnonzero(train.cell_mask(st,19,np.ones(48))).tolist(),[9])
        self.assertEqual(train.battle_point(st,19,9,1920,1200),(433,344))
        st['anchor']=(24,9)
        self.assertGreater(train.cell_mask(st,24,np.ones(48)).sum(),1)

    def test_geometry_endpoint_cannot_wrap_or_repeat_anchor(self):
        st = dict(planning=True, anchor=(10, 47), deck=[])
        mu, mc = train.masks_for(st)
        self.assertEqual(list(np.flatnonzero(mu)), [10, train.TOOLS.index('cancel_tool')])
        self.assertEqual(mc[47], 0)

    def test_zero_reward_terminal_returns(self):
        adv, ret = train.gae([0, 0, 0], [1, 1, 1], gamma=1, lam=1)
        np.testing.assert_allclose(adv, [-1, -1, -1])
        np.testing.assert_allclose(ret, [0, 0, 0])

    def test_lambda_and_bootstrap(self):
        adv, ret = train.gae([1, 2], [3, 4], gamma=.5, lam=0,
                             bootstrap=6)
        np.testing.assert_allclose(adv, [0, 1])
        np.testing.assert_allclose(ret, [3, 5])
        adv, _ = train.gae([1, 2], [3, 4], gamma=.5, lam=1,
                           bootstrap=6)
        np.testing.assert_allclose(adv, [.5, 1])

    def test_each_pid_is_owned_by_one_batch(self):
        active, overlap = set(), []
        lock = threading.Lock()

        def episode(args):
            pid = args[0]
            with lock:
                if pid in active:
                    overlap.append(pid)
                active.add(pid)
            time.sleep(.01)
            with lock:
                active.remove(pid)
            return {'pid': pid}

        with patch.object(train, 'run_episode', episode):
            jobs = train.episode_batches([101, 102, 103], {}, False, 'test', 3)
            with ThreadPoolExecutor(3) as pool:
                rows = list(pool.map(train.run_batch, jobs))
        self.assertEqual(overlap, [])
        self.assertEqual([[r['pid'] for r in batch] for batch in rows],
                         [[101]*3, [102]*3, [103]*3])
        with self.assertRaises(ValueError):
            train.episode_batches([101, 101], {}, False, 'test', 2)

    def test_checkpoint_restores_adam_and_retains_previous(self):
        net = train.PolicyNet2()
        opt = torch.optim.Adam(net.parameters())
        sum(p.sum() for p in net.parameters()).backward()
        opt.step()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'model.pt'
            train.save_checkpoint(net, opt, path, 'run-a')
            original = path.read_bytes()
            restored = train.PolicyNet2()
            self.assertEqual(torch.load(path, weights_only=True)['learning'], train.learning_config())
            resumed = torch.optim.Adam(restored.parameters())
            train.load_checkpoint(restored, resumed, path)
            self.assertTrue(resumed.state)
            for a, b in zip(net.parameters(), restored.parameters()):
                torch.testing.assert_close(a, b)
            train.save_checkpoint(net, opt, path, 'run-b')
            self.assertEqual(Path(str(path) + '.previous').read_bytes(), original)

    def test_only_train_mode_can_update(self):
        self.assertTrue(train.training_enabled('train', False))
        for mode, random in [('play', False), ('greedy', False), ('train', True)]:
            self.assertFalse(train.training_enabled(mode, random))



class PlanningRecoveryTests(unittest.TestCase):
    def test_debt_recovery_telemetry_preserves_active_gestures(self):
        st = dict(planning=True, native=dict(selection=dict(polygon=[])))
        self.assertTrue(train.debt_without_draft(st, -401))
        self.assertFalse(train.debt_without_draft(st, -.5))
        for blockers in (dict(planning=False), dict(dialog=True),
                         dict(anchor=(10, 3)), dict(gesture_anchor=('drag_world', 0)),
                         dict(native=dict(selection=dict(polygon=[(0, 0)])))):
            self.assertFalse(train.debt_without_draft(dict(st, **blockers), -401))


class DragReceiptTests(unittest.TestCase):
    def test_dispatch_receipt_times_the_existing_drag_without_repeating_it(self):
        calls = []
        vi = SimpleNamespace(drag=lambda *points: calls.append(points))
        with (patch.object(train.time, 'time_ns', side_effect=[1_000_000, 461_000_000]),
              patch.object(train.time, 'perf_counter_ns', side_effect=[9_000_000, 459_000_000])):
            receipt = train.timed_drag(vi, (11, 22), (33, 44))
        self.assertEqual(calls, [(11, 22, 33, 44)])
        self.assertEqual(receipt, dict(started_wall_ms=1., ended_wall_ms=461., dispatch_ms=450.))


class PopulationPressureTests(unittest.TestCase):
    def test_first_outnumbered_and_low_population_are_separate(self):
        events = {}
        train.record_population_pressure(events, {'civ': 60, 'zomb': 40}, 100, 1.0)
        self.assertEqual(events, {})
        train.record_population_pressure(events, {'civ': 45, 'zomb': 45}, 100, 2.0)
        train.record_population_pressure(events, {'civ': 10, 'zomb': 80}, 100, 3.0)
        train.record_population_pressure(events, {'civ': 3, 'zomb': 90}, 100, 4.0)
        self.assertEqual(events, {'first_outnumbered_sim': 2.0,
                                  'first_live_at_retry_floor_sim': 3.0})

    def test_severe_failure_uses_official_completed_or_retry_scores(self):
        self.assertTrue(train.severe_outcome(.0999, 'aborted'))
        self.assertTrue(train.severe_outcome(0., 'lost'))
        self.assertFalse(train.severe_outcome(.10, 'aborted'))
        self.assertIsNone(train.severe_outcome(.01, 'timeout'))
        self.assertIsNone(train.severe_outcome(None, 'lost'))

if __name__ == '__main__':
    unittest.main()
