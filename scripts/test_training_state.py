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
            def emit(*args, **kwargs):
                (dumps/'fresh.state').write_bytes(b'replay')
                (dumps/'fresh.txt').write_text('[where]\nphase = planning\n')
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
