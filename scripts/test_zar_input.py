"""Offline contract checks; never inject or target a game PID."""
import ctypes
import struct
import unittest
from unittest.mock import patch

from zar_input import OFF, VirtualInput


class InputContract(unittest.TestCase):
    def test_drag_posts_button_edges_and_held_moves(self):
        vi = VirtualInput.__new__(VirtualInput)
        vi.buf = (ctypes.c_char * 256)()
        vi._hb = 0
        vi.hwnd = 1
        vi._origin = lambda: (0, 0, 0, 0, 1920, 1200)
        with patch('zar_input.user32.PostMessageW') as post, patch('zar_input.time.sleep'):
            vi.drag(10, 20, 30, 40, steps=2)
        messages = [(c.args[1], c.args[2]) for c in post.call_args_list]
        self.assertEqual(messages, [(0x200, 0), (0x201, 1),
                                    (0x200, 1), (0x200, 1), (0x202, 0)])
        self.assertEqual(struct.unpack_from('<I', vi.buf, OFF['buttons'])[0], 0)

    def test_inject_reuses_an_existing_section(self):
        vi = VirtualInput.__new__(VirtualInput)
        vi.open_section = lambda: None
        with patch('zar_input.os.path.exists', side_effect=AssertionError('reinjection')):
            vi.inject()

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
