"""Offline trainer regressions. Never attach to a game PID."""
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
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
        np.testing.assert_allclose(ret, [2., 2.])
        with self.assertRaises(ValueError):
            train.gae([1.], [0.], planning=[])

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


if __name__ == '__main__':
    unittest.main()
