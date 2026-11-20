"""No live PIDs: game-state boundary and reward tests."""
import struct
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import env_zar
import nn_play2 as train


class StateTests(unittest.TestCase):
    def test_private_ppo_retries_both_arms_after_transient_native_map_change(self):
        from compare_spatial import collect_pairs
        from unittest.mock import Mock
        jobs = [('inst13', 'standard', {}, 123, 'first'),
                ('inst14', 'balanced', {}, 123, 'second')]
        pool = Mock()
        paired = [{'saved_frac': .31}, {'saved_frac': .34}]
        pool.map.side_effect = [[{'saved_frac': .3}, {'err': 'Native map changed during read'}], paired]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(collect_pairs(pool, jobs, Path(directory)), paired)
            self.assertEqual(pool.map.call_args.args[1], jobs)
            self.assertIn('Native map changed', (Path(directory)/'interface-retries.jsonl').read_text())

    def test_private_ppo_preserves_boot_failure_without_returning_a_score(self):
        import compare_spatial
        message = 'inst13 failed at injection: argument 1: OverflowError'
        with patch.object(compare_spatial.operator, 'owned_copy'), \
                patch.object(compare_spatial.zar_boot, 'boot', side_effect=env_zar.ZAREnvError(message)), \
                patch.object(compare_spatial.zar_boot, 'stop') as stop:
            self.assertEqual(compare_spatial.episode(('inst13', 'standard', {}, 123, 'test')),
                             {'err': message})
            stop.assert_not_called()

    def test_consistency_keeps_incomplete_or_weak_held_out_blocks_visible(self):
        from compare_spatial import heldout_consistency
        cohort = [dict(phase='evaluation', policy_id='frozen', start_kind='fresh',
                       outbreak_seed=i, end='won', win=True, saved_frac=.4) for i in range(30)]
        self.assertTrue(heldout_consistency(cohort, 'frozen')['passed'])
        from_other_arm = dict(phase='train', policy_id='different-policy', outbreak_seed=4)
        self.assertFalse(heldout_consistency([from_other_arm, *cohort], 'frozen')['passed'])
        resumed = heldout_consistency(cohort, 'frozen', discovery_seeds={11, 71})
        self.assertEqual(resumed['discovery_overlap'], 1)
        self.assertFalse(resumed['passed'])
        malformed = [dict(cohort[0], outbreak_seed=[]), *cohort[1:]]
        self.assertEqual(heldout_consistency(malformed, 'frozen')['incomplete'], 1)
        cohort[0]['end'] = 'timeout'
        self.assertEqual(heldout_consistency(cohort, 'frozen')['incomplete'], 1)
        self.assertFalse(heldout_consistency(cohort, 'frozen')['passed'])
        cohort[0]['end'] = 'won'
        for row in cohort[:10]:
            row['saved_frac'] = .3
        self.assertFalse(heldout_consistency(cohort, 'frozen')['passed'])

    def test_phase_loss_weighting_keeps_both_phases_visible(self):
        phases = train.torch.tensor([True, False, False, False])
        weights = train.phase_loss_weights(phases)
        self.assertAlmostEqual(float(weights[phases].sum()), 2.)
        self.assertAlmostEqual(float(weights[~phases].sum()), 2.)
        self.assertEqual(train.phase_loss_weights(phases[1:]).tolist(), [1., 1., 1.])

    def test_missile_reward_comparison_uses_same_network_without_layout_override(self):
        import compare_spatial
        with patch.object(compare_spatial.operator, 'owned_copy'), \
                patch.object(compare_spatial.zar_boot, 'boot'), \
                patch.object(compare_spatial.zar_boot, 'stop'), \
                patch.object(train, 'run_episode') as run:
            for arm, enabled in [('unshaped', False), ('missile_credit', True)]:
                compare_spatial.episode(('inst13', arm, {}, 123, 'test'))
                self.assertEqual(run.call_args.args[0][4],
                                 dict(start_kind='fresh', seed=123, missile_credit=enabled))
                self.assertIs(run.call_args.kwargs['policy_factory'], train.PolicyNet2)
            for arm in ('standard', 'balanced'):
                compare_spatial.episode(('inst13', arm, {}, 123, 'test'))
                self.assertEqual(run.call_args.args[0][4],
                                 dict(start_kind='fresh', seed=123, missile_credit=True,
                                      fixed_speed='speed_1', fixed_clock=True))

    def test_breach_comparison_uses_normal_speed_and_changes_only_penalty(self):
        import compare_spatial
        with patch.object(compare_spatial.operator, 'owned_copy'), patch.object(compare_spatial.zar_boot, 'boot'), \
                patch.object(compare_spatial.zar_boot, 'stop'), patch.object(train, 'run_episode') as run:
            for arm, cost in compare_spatial.BREACH_COSTS.items():
                compare_spatial.episode(('inst13', arm, {}, 123, 'test'))
                self.assertEqual(run.call_args.args[0][4],
                    dict(start_kind='fresh', seed=123, missile_credit=True, fixed_speed='speed_2',
                         fixed_clock=True, occupied_breach_cost=cost))
                self.assertIs(run.call_args.kwargs['policy_factory'], train.PolicyNet2)

    def test_reserved_ppo_copies_refuse_overlap_before_taking_lock(self):
        import compare_spatial
        with patch('sys.argv', ['compare_spatial', '--copies', 'a', 'b', '--eval-copies', 'a', 'c']), \
                patch.object(compare_spatial.operator,'training_lock') as lock:
            with self.assertRaises(SystemExit):
                compare_spatial.main()
            lock.assert_not_called()

    def test_missile_civilian_loss_is_charged_at_native_impact(self):
        events = [
            {'seq': 1, 'ev': 'deploy', 'what': 'cruise_missile', 'sim': 1},
            {'seq': 2, 'ev': 'bomb', 'what': 'cruise_missile', 'sim': 2.5,
             'killed': {'civilians': 4, 'zombies': 30}},
            {'seq': 3, 'ev': 'bomb', 'what': 'fire_bomb', 'sim': 2.5,
             'killed': {'civilians': 20}},
            {'seq': 4, 'ev': 'bomb', 'what': 'cruise_missile', 'sim': 4,
             'killed': {'civilians': 3}},
        ]
        events.append(events[1].copy())
        rewards = [0., 0., 0.]
        footer = dict(combat_events=events, combat_events_truncated=False)
        stats = train.charge_missile_civilian_loss(footer, [1., 2., 3.], rewards, 100)
        self.assertEqual(rewards, [0., 0., -.04])
        self.assertEqual(stats, dict(confirmed=7, assigned=4))
        self.assertIsNone(train.charge_missile_civilian_loss(
            dict(footer, combat_events_truncated=True), [1., 2., 3.], rewards, 100))

    def test_planning_scan_codes_match_physical_keys(self):
        from zar_input import SC
        for vk,sc in train.U_HOTKEY.values():self.assertEqual(sc,SC[vk])

    def test_repeated_tool_selection_cancels_before_rearming(self):
        e = self.env()
        with patch('game_controls.Controls') as controls:
            e._arm(0x42, 48)
            e._arm(0x42, 48)
        self.assertEqual(controls.return_value.arm.call_args_list,
                         [unittest.mock.call(0x42,48)]*2)

    def test_dump_retries_one_missing_request_only_in_unobstructed_world(self):
        from unittest.mock import Mock
        e=self.env();expected={'where':{'phase':'planning'}}
        e._dump_once=Mock(side_effect=[None,expected]);e.scalar=Mock(return_value=0)
        e.game_state=Mock(return_value={'phase':'planning'})
        self.assertEqual(e.dump(),expected);self.assertEqual(e._dump_once.call_count,2)
        for blocked in ('modal','menu','outside'):
            e._dump_once=Mock(return_value=None)
            e.scalar=Mock(side_effect=lambda r,f:int(r==(0x667868 if blocked=='modal' else 0x666870)))
            e.game_state=Mock(side_effect=env_zar.ZAREnvError('outside') if blocked=='outside' else None)
            self.assertIsNone(e.dump());self.assertEqual(e._dump_once.call_count,1)
        e._dump_once=Mock(return_value=None);e.scalar=Mock(return_value=0);e.game_state=Mock()
        self.assertIsNone(e.dump());self.assertEqual(e._dump_once.call_count,2)

    def test_training_discards_only_its_new_replay_snapshots(self):
        from types import SimpleNamespace
        e = self.env()
        with tempfile.TemporaryDirectory() as root, patch.object(env_zar.time, 'sleep'):
            e.root = root
            copy = Path(root)/'game-copies'/'inst1'
            dumps = copy/'debug_dumps'
            dumps.mkdir(parents=True)
            (dumps/'old.state').write_bytes(b'evidence')
            e.copy_dir = lambda: str(copy)
            writes = 0
            def emit(*args, **kwargs):
                nonlocal writes
                writes += 1
                (dumps/'fresh.state').write_bytes(b'replay')
                (dumps/'fresh.txt').write_text('[where]\nphase = planning\n' + '\n'*writes)
            e.vi = SimpleNamespace(key_press=emit)
            e.discard_dump_states = True
            self.assertEqual(e.dump()['where']['phase'], 'planning')
            self.assertFalse((dumps/'fresh.state').exists())
            self.assertTrue((dumps/'fresh.txt').exists())
            self.assertEqual((dumps/'old.state').read_bytes(), b'evidence')
            e.discard_dump_states = False
            self.assertIsNotNone(e.dump())
            self.assertTrue((dumps/'fresh.state').exists())

    def test_picker_rejection_preserves_skill_points_and_verifies_no_purchase(self):
        from game_controls import PickerNavigationError
        from unittest.mock import Mock

        env = Mock()
        initial = {'Rally': 0}
        st = dict(loadout=initial, sp=2, costs={'Rally': 2})
        env.change_loadout.side_effect = PickerNavigationError('missed row')
        env.loadout_levels.return_value = initial
        self.assertFalse(train.apply_loadout_action(env, st, 'Rally', 1))
        self.assertEqual(st['sp'], 2)
        self.assertEqual(st['loadout'], initial)
        env.loadout_levels.return_value = {'Rally': 1}
        with self.assertRaises(PickerNavigationError):
            train.apply_loadout_action(env, st, 'Rally', 1)
        env.change_loadout.side_effect = None
        env.change_loadout.return_value = {'Rally': 1}
        self.assertTrue(train.apply_loadout_action(env, st, 'Rally', 1))
        self.assertEqual(st['sp'], 0)

    def test_planning_cap_allows_one_policy_dialog_decision(self):
        self.assertTrue(train.planning_limit_reached(60, 60, False))
        self.assertFalse(train.planning_limit_reached(60, 60, True))
        self.assertTrue(train.planning_limit_reached(61, 60, True))

    def test_geometry_uses_native_land_cap_and_budget(self):
        e = self.env()
        values = {0x659258: 1, 0x65ce58: 0, 0x659308: 30, 0x659310: 100,
                  0x65d9e0: 1., 0x64df20: 30., 0x64df24: 12.,
                  0x64df28: 1., 0x64df2c: 159.}
        e.scalar = lambda address, fmt: values[address]
        e.money = lambda: 0.
        self.assertTrue(e.geometry_legal())
        values[0x659308] = 31
        self.assertEqual(e.geometry_blockers(), ["safe_zones_too_big"])
        self.assertFalse(e.geometry_legal())
        values[0x659308] = 13
        values[0x65d9e0] = 159.
        self.assertFalse(e.geometry_legal())
        values[0x659308] = 12
        self.assertTrue(e.geometry_legal())
        e.money = lambda: -.51
        self.assertEqual(e.geometry_blockers(), ["over_budget"])
        self.assertFalse(e.geometry_legal())
        values[0x659308] = 13
        self.assertEqual(e.geometry_blockers(), ["safe_zones_too_big", "over_budget"])
        values[0x659258] = 0
        with patch.object(env_zar.time, 'sleep'), self.assertRaises(env_zar.ZAREnvError):
            e.geometry_legal()

    def test_invalid_geometry_undo_preserves_previous_board(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        e = self.env()
        before = {'_text': 'board unit = Garrison 1 2', 'economy': {'money': '3000'}}
        changed = {'_text': before['_text']+'\nboard zone = 4 ...', 'economy': {'money': '100'}}
        e.dump = Mock(side_effect=[changed, before])
        e.geometry_legal = Mock(side_effect=[False, True])
        e.vi = SimpleNamespace(combo_press=Mock())
        with patch.object(env_zar.time, 'sleep'):
            self.assertEqual(e.finish_geometry(before), before)
        e.vi.combo_press.assert_called_once_with([0x11], 0x5A, sc=44, hold=.12)
        e.dump = Mock(side_effect=[changed, changed])
        e.geometry_legal = Mock(side_effect=[False, True])
        with patch.object(env_zar.time, 'sleep'), self.assertRaises(env_zar.ZAREnvError):
            e.finish_geometry(before)

    def test_loadout_uses_receipt_checked_shared_controls(self):
        with patch('game_controls.Controls') as controls:
            expected = {'Cluster': 1}
            controls.return_value.change_loadout.return_value = expected
            e = self.env()
            self.assertEqual(e.change_loadout('Cluster', 1), expected)
            controls.assert_called_once_with(e)
            controls.return_value.change_loadout.assert_called_once_with('Cluster', 1)

    def test_won_board_continues_instead_of_retrying_same_level(self):
        from types import SimpleNamespace
        e = self.env()
        e.game_state = unittest.mock.Mock(side_effect=[{'phase':'won'}, {'phase':'planning'}])
        e.obs = lambda: {'civ': 100}
        e.vi = SimpleNamespace(key_press=unittest.mock.Mock())
        with patch.object(env_zar.time, 'sleep'):
            self.assertEqual(e.to_planning(), {'civ':100})
        e.vi.key_press.assert_called_once_with(0x0D, sc=28)

    def env(self):
        e = env_zar.ZAREnv.__new__(env_zar.ZAREnv)
        e.h, e.base = 0, 0
        return e

    def test_native_stock_uses_float_array_enum_order(self):
        e = self.env()
        values = {0x656488: 28., 0x656488+10*4: 1.}
        e.scalar = lambda address, fmt: values.get(address, 0.)
        stock = e.battle_stock()
        self.assertEqual(stock['Police'], 28)
        self.assertEqual(stock['Stungas'], 1)
        self.assertEqual(stock['Heli'], 0)

    def test_money_uses_dump_field_and_accepts_zero(self):
        def read(h, address, size):
            return struct.pack('<f', 0.0 if address == 0x65d9c0 else 3111.0)
        with patch.object(env_zar.memscan, 'read', read):
            self.assertEqual(self.env().money(), 0.0)

    def test_missing_memory_is_not_zero(self):
        with patch.object(env_zar.memscan, 'read', return_value=None):
            with self.assertRaises(env_zar.ZAREnvError):
                self.env().game_state()

    def test_money_preserves_native_debt_and_rejects_invalid_reads(self):
        for value in (-734., float('nan'), float('inf'), -1e7, 1e7):
            with self.subTest(value=value), patch.object(env_zar.memscan, 'read',
                                                       return_value=struct.pack('<f', value)):
                self.assertEqual(self.env().money(), -734. if value == -734. else None)

    def test_dump_section_headers_with_descriptions(self):
        d = env_zar.ZAREnv.dump_parse('[economy]\nmoney = 0\n[plan] (map frame)\nboard unit = Garrison 1 2\n')
        self.assertEqual(d['economy'], {'money': '0'})
        self.assertEqual(d['plan']['board unit'], 'Garrison 1 2')

    def test_no_purchase_or_cast_bonus(self):
        for purchases in (0, 60):
            self.assertEqual(train.outcome_reward(.35, 'won'), 1.75)
        self.assertEqual(train.outcome_reward(None, 'timeout'), 0)

    def test_unknown_terminal_is_not_a_training_sample(self):
        self.assertFalse(train.valid_trajectory({'end': 'won', 'saved_frac': None}))
        self.assertTrue(train.valid_trajectory({'end': 'timeout', 'bootstrap': 2}))
        for row in ({'end': 'won', 'saved_frac': float('nan')},
                    {'end': 'lost', 'saved_frac': 1.1},
                    {'end': 'unknown', 'saved_frac': .5},
                    {'end': 'timeout', 'bootstrap': float('inf')}):
            self.assertFalse(train.valid_trajectory(row))

    def test_infection_cost_uses_the_next_state_without_floor(self):
        self.assertEqual(train.transition_reward({'infections': 0}, {'infections': 100}, 100), -1)
        self.assertAlmostEqual(sum(train.transition_reward({'infections': i}, {'infections': i+1}, 100)
                             for i in range(100)), -1.0)
        self.assertEqual(train.transition_reward({'infections': 1}, {'infections': 1}, 100), 0)

    def test_ready_failure_never_becomes_battle(self):
        class Env:
            def game_state(self):
                return dict(phase='planning', paused=False)
            vi = type('Input', (), {'key_press': lambda *a, **k: None})()
        with patch.object(train.time, 'sleep'), self.assertRaises(env_zar.ZAREnvError):
            train.ready_once(Env())

    def test_search_pause_limit_resets_on_resume_and_is_opt_in(self):
        state=dict(phase='playing',paused=True)
        limits={'paused_seconds':45}
        self.assertEqual(train.battle_timeout(state,20,0,None,limits),(None,20))
        self.assertEqual(train.battle_timeout(state,65,0,20,limits),('continuous_pause',20))
        self.assertEqual(train.battle_timeout(state,65,0,20,{}),(None,20))
        state['paused']=False
        self.assertEqual(train.battle_timeout(state,64,0,20,limits),(None,None))
        self.assertEqual(train.battle_timeout(state,600,0,None,{}),('battle_clock',None))

    def test_ready_phase_preserves_the_native_budget_and_stock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'episode.jsonl'
            rows = [
                dict(ev='header', wall=100),
                dict(ev='phase', to='playing', reason='resume', stats=dict(money=77)),
                {'ev': 'phase', 'from': 'planning', 'to': 'playing', 'reason': 'ready',
                 'stats': {'money': 1815, 'stock': {'garrison': 0, 'airstrike': 1}, 'garrisons': 2}},
                dict(ev='footer', stats=dict(money=999)),
            ]
            path.write_text('\n'.join(map(json.dumps, rows)))
            result = env_zar.read_session(path, 100)
            self.assertEqual(result['ready_stats'],
                             dict(money=1815, stock=dict(garrison=0, airstrike=1), garrisons=2))
            path.write_text('\n'.join(map(json.dumps, rows[:2] + rows[3:])))
            self.assertIsNone(env_zar.read_session(path, 100)['ready_stats'])

    def test_ready_skill_points_use_last_native_pre_ready_loadout_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'episode.jsonl'
            header = dict(ev='header', wall=100, session=dict(sp_unspent=2))
            ready = {'ev': 'phase', 'from': 'planning', 'to': 'playing', 'reason': 'ready',
                     'stats': {'money': 1815}}
            first = dict(ev='loadout', phase='planning', sp_unspent=0)
            latest = dict(ev='loadout', phase='planning', sp_unspent=1)
            late = dict(ev='loadout', phase='playing', sp_unspent=2)

            def recorded(rows):
                path.write_text('\n'.join(map(json.dumps, rows)))
                return env_zar.read_session(path, 100, expected_wall=100)['ready_loadout_sp']

            self.assertEqual(recorded([header, first, latest, ready, late]), 1)
            self.assertIsNone(recorded([header, ready, late]))
            self.assertIsNone(recorded([header, first, dict(latest, sp_unspent=-1), ready]))
            self.assertIsNone(recorded([header, first, latest]))

    def test_retry_evidence_requires_a_fresh_official_snapshot(self):
        env = env_zar.ZAREnv.__new__(env_zar.ZAREnv)
        env.log_started = env.log_header_wall = 100
        with tempfile.TemporaryDirectory() as tmp:
            env.log_path = Path(tmp) / 'episode.jsonl'
            header = dict(ev='header', wall=100)
            low = dict(ev='snapshot', phase='playing', sim=100.03, stats=dict(saved_pct=9.9))

            def write(begin, event):
                env.log_path.write_text('\n'.join(map(json.dumps, (begin, event))))

            write(header, low)
            self.assertAlmostEqual(env.logged_saved_fraction(100.5), .099)
            self.assertIsNone(env.logged_saved_fraction(99.0))
            self.assertIsNone(env.logged_saved_fraction(104.0))
            write(header, dict(low, stats=dict(saved_pct=39)))
            self.assertEqual(env.logged_saved_fraction(101), .39)
            for ignored in (dict(low, ev='footer'), dict(low, phase='planning'),
                            dict(low, stats=dict(saved_pct=float('nan')))):
                write(header, ignored)
                self.assertIsNone(env.logged_saved_fraction(101))
            write(dict(header, wall=101), low)
            self.assertIsNone(env.logged_saved_fraction(101))

    def test_log_outcome_requires_this_session_footer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'episode.jsonl'
            rows = [{'ev': 'header', 'wall': 100, 'session': {'sp_total': 2}},
                    {'ev':'outbreak','seed':37,'safe_zones':2,'civilians_inside_pct':11.8},
                    {'ev':'arm','what':'fire_bomb'}, {'ev':'deploy','what':'fire_bomb'},
                    {'ev':'bomb','what':'fire_bomb'},
                    {'ev': 'footer', 'phase': 'lost', 'stats': {'saved_pct': 12.5}}]
            path.write_text('\n'.join(map(json.dumps, rows)))
            self.assertIsNone(env_zar.read_session(path, 101))
            data = env_zar.read_session(path, 100)
            self.assertEqual(data['footer']['stats']['saved_pct'], 12.5)
            self.assertEqual(data['deployments'],['fire_bomb'])
            self.assertNotIn('combat_events', data)
            self.assertIsNone(env_zar.read_session(path, 90, expected_wall=99, capture_events=True))
            captured = env_zar.read_session(path, 90, expected_wall=100, capture_events=True)
            self.assertEqual(captured['combat_events'], [rows[3], rows[4]])
            self.assertFalse(captured['combat_events_truncated'])
            self.assertEqual(data['outbreak'],{'seed':37,'safe_zones':2,'civilians_inside_pct':11.8})
            later = [{'ev': 'header', 'wall': 120}, {'ev': 'footer', 'stats': {'saved_pct': 99}}]
            path.write_text('\n'.join(map(json.dumps, rows[:-1] + later)))
            self.assertIsNone(env_zar.read_session(path, 100, expected_wall=100)['footer'])
            path.write_text('\n'.join(map(json.dumps, [rows[0]] + [rows[4]] * 1025 + [rows[-1]])))
            bounded = env_zar.read_session(path, 100, capture_events=True)
            self.assertEqual(len(bounded['combat_events']), 1024)
            self.assertTrue(bounded['combat_events_truncated'])
            path.write_text(json.dumps(rows[0]) + '\n{"ev":')
            self.assertIsNone(env_zar.read_session(path, 100)['footer'])


if __name__ == '__main__':
    unittest.main()
