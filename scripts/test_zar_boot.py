"""Offline boot boundary checks; no processes are launched."""
import unittest
from unittest.mock import patch

from zar_boot import COPIES, boot, copy_path


class BootBoundary(unittest.TestCase):
    def test_only_named_copies_are_allowed(self):
        self.assertEqual(copy_path(COPIES / 'inst4'), COPIES / 'inst4')
        for path in (COPIES.parent, COPIES / '..' / 'inst4', COPIES / 'template',
                     'C:/Games/steam/steamapps/common/Zombies-Arent-Real'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                copy_path(path)

    def test_unsupported_destination_never_launches(self):
        with patch('zar_boot.subprocess.Popen') as launch:
            with self.assertRaises(ValueError):
                boot(COPIES / 'inst4', ('campaign', 'stage9'))
            launch.assert_not_called()

    def test_busy_copy_never_launches(self):
        with patch('zar_boot.copy_processes', return_value=[object()]), \
                patch('zar_boot.subprocess.Popen') as launch:
            with self.assertRaisesRegex(RuntimeError, 'already has a game'):
                boot(COPIES / 'inst4')
            launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
