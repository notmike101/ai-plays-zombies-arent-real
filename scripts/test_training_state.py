"""No live PIDs: game-state boundary and reward tests."""
import struct
import unittest
from unittest.mock import patch
import env_zar


class StateTests(unittest.TestCase):
    def env(self):
        e = env_zar.ZAREnv.__new__(env_zar.ZAREnv)
        e.h, e.base = 0, 0
        return e

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


if __name__ == '__main__':
    unittest.main()
