"""Offline boot boundary checks; no processes are launched."""
import unittest
from unittest.mock import patch

from zar_boot import COPIES, boot, copy_path, menu_points, campaign_in_progress


class BootBoundary(unittest.TestCase):
    def test_progress_selects_the_campaign_button_layout(self):
        for count in range(6):
            progress = '\n'.join(f'stage {i} = {"bronze" if i <= count else "none"} 0 played'
                                 for i in range(1, 6))
            self.assertEqual(campaign_in_progress(progress), 0 < count < 5)
        for size in ((1920, 1200), (3840, 2160)):
            self.assertLess(menu_points(*size, True)[2][1], menu_points(*size)[2][1])

    def test_menu_layouts_are_explicit_and_fractional(self):
        for size in ((1920, 1200), (3840, 2160)):
            self.assertTrue(all(0 < n < 1 for point in menu_points(*size) for n in point))
        self.assertNotEqual(menu_points(1920, 1200), menu_points(3840, 2160))
        with self.assertRaisesRegex(RuntimeError, 'Uncalibrated'):
            menu_points(800, 600)

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
