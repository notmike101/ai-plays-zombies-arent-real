"""Offline contract checks; never inject or target a game PID."""
import ctypes
import struct
import unittest
from unittest.mock import patch

from zar_input import OFF, VirtualInput


class InputContract(unittest.TestCase):
    def test_v3_move_stores_client_coordinates(self):
        vi = VirtualInput.__new__(VirtualInput)
        vi.buf = (ctypes.c_char * 256)()
        vi._hb = 0
        vi.hwnd = 1
        vi._origin = lambda: (76, 72, 11, 49, 1920, 1200)
        with patch('zar_input.user32.PostMessageW'):
            vi.move_to(960, 600)
        self.assertEqual(struct.unpack_from('<ii', vi.buf, OFF['cx']), (960, 600))


if __name__ == '__main__':
    unittest.main()
