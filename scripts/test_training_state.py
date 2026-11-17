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

    def test_log_outcome_requires_this_session_footer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'episode.jsonl'
            rows = [{'ev': 'header', 'wall': 100, 'session': {'sp_total': 2}},
                    {'ev': 'footer', 'phase': 'lost', 'stats': {'saved_pct': 12.5}}]
            path.write_text('\n'.join(map(json.dumps, rows)))
            self.assertIsNone(env_zar.read_session(path, 101))
            data = env_zar.read_session(path, 100)
            self.assertEqual(data['footer']['stats']['saved_pct'], 12.5)
            path.write_text(json.dumps(rows[0]) + '\n{"ev":')
            self.assertIsNone(env_zar.read_session(path, 100)['footer'])


if __name__ == '__main__':
    unittest.main()
