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
        vi.model_only = False
        vi._origin = lambda: (0, 0, 0, 0, 1920, 1200)
        with patch('zar_input.user32.PostMessageW') as post, patch('zar_input.time.sleep'):
            vi.drag(10, 20, 30, 40, steps=2)
        messages = [(c.args[1], c.args[2]) for c in post.call_args_list]
        self.assertEqual(messages, [(0x200, 0), (0x201, 1),
                                    (0x200, 1), (0x200, 1), (0x202, 0)])
        self.assertEqual(struct.unpack_from('<I', vi.buf, OFF['buttons'])[0], 0)

    def test_model_only_posts_private_messages_with_original_parameters(self):
        vi = VirtualInput.__new__(VirtualInput)
        vi.hwnd = 1
        vi.model_only = True
        with patch('zar_input.user32.PostMessageW') as post:
            vi._post(0x100, 0x20, 0x00390001)
        post.assert_called_once_with(1, 0x8100, 0x20, 0x00390001)

    def test_module_snapshot_retries_transient_invalid_handle_without_truncating(self):
        vi = VirtualInput.__new__(VirtualInput)
        vi.pid = 123
        invalid = ctypes.c_void_p(-1).value
        handle = 0x100000042

        def read_first(seen, entry):
            self.assertEqual(seen.value, handle)
            entry._obj.szModule = 'example.dll'
            entry._obj.modBaseAddr = 0x140000000
            return True

        with (patch('zar_input.kernel32') as api,
              patch('zar_input.ctypes.GetLastError', return_value=24),
              patch('zar_input.time.sleep')):
            api.CreateToolhelp32Snapshot.side_effect = [invalid, handle]
            api.Module32FirstW.side_effect = read_first
            self.assertEqual(vi._remote_module_base(None, 'example.dll'), 0x140000000)
            self.assertEqual(api.CreateToolhelp32Snapshot.call_count, 2)
            self.assertEqual(api.CloseHandle.call_args.args[0].value, handle)
            api.Module32FirstW.assert_called_once()

    def test_module_snapshot_permanent_failure_never_enumerates_invalid_handle(self):
        vi = VirtualInput.__new__(VirtualInput)
        vi.pid = 123
        with (patch('zar_input.kernel32') as api,
              patch('zar_input.ctypes.GetLastError', return_value=5)):
            api.CreateToolhelp32Snapshot.return_value = ctypes.c_void_p(-1).value
            self.assertIsNone(vi._remote_module_base(None, 'example.dll'))
            api.CreateToolhelp32Snapshot.assert_called_once()
            api.Module32FirstW.assert_not_called()
            api.CloseHandle.assert_not_called()

    def test_inject_reuses_an_existing_section(self):
        vi = VirtualInput.__new__(VirtualInput)
        vi.open_section = lambda: None
        with patch('zar_input.os.path.exists', side_effect=AssertionError('reinjection')):
            vi.inject()

    def test_v3_move_stores_client_coordinates(self):
        import numpy as np
        vi = VirtualInput.__new__(VirtualInput)
        vi.buf = (ctypes.c_char * 256)()
        vi._hb = 0
        vi.hwnd = 1
        vi.model_only = False
        vi._origin = lambda: (76, 72, 11, 49, 1920, 1200)
        with patch('zar_input.user32.PostMessageW') as post:
            vi.move_to(np.int64(960), np.int64(600))
            self.assertIs(type(post.call_args.args[3]),int)
        self.assertEqual(struct.unpack_from('<ii', vi.buf, OFF['cx']), (960, 600))


if __name__ == '__main__':
    unittest.main()
