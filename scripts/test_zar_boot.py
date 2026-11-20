"""Offline boot boundary checks; no processes are launched."""
import unittest
from unittest.mock import patch

from zar_boot import (COPIES, boot, copy_path, menu_points, campaign_in_progress,
                      campaign_cleared, main, placement_bindings, click_start_settings)


class BootBoundary(unittest.TestCase):
    def test_click_start_resets_only_the_saved_placement_mode(self):
        original = 'place_paint = true\nroster_plan = Garrison Mortar\n'
        result = click_start_settings(original)
        self.assertEqual(result, original.replace('true', 'false'))
        self.assertEqual(click_start_settings(result), result)
        self.assertEqual(click_start_settings(''), '\nplace_paint = false\n')

    def test_placement_bindings_are_idempotent_and_reject_conflicts(self):
        text=placement_bindings('difficulty = normal\nbind_place_click = NONE\n')
        self.assertIn('bind_place_click = K',text)
        self.assertIn('bind_place_paint = J',text)
        self.assertEqual(placement_bindings(text),text)
        with self.assertRaisesRegex(RuntimeError,'Expected'):
            placement_bindings('bind_place_click = B\n')

    def test_cli_requires_explicit_preparation_of_missing_copies(self):
        with patch('sys.argv', ['zar_boot.py', 'inst99999']), \
                patch('zar_boot.Path.exists', return_value=False), \
                patch('zar_boot.subprocess.Popen') as launch:
            with self.assertRaisesRegex(ValueError, 'prepare-game'):
                main()
            launch.assert_not_called()

    def test_unplayed_campaign_uses_shorter_play_now_panel(self):
        self.assertEqual(menu_points(1920, 1200, unplayed=True)[2], (.446, .610))
        self.assertNotEqual(menu_points(1920, 1200)[2], (.446, .610))
        with self.assertRaisesRegex(RuntimeError, 'Uncalibrated'):
            menu_points(3840, 2160, unplayed=True)

    def test_progress_selects_the_campaign_button_layout(self):
        self.assertEqual(campaign_cleared('version = 5\nresume_stage = 0\nperks = Extra_Zones - -'), 0)
        for count in range(6):
            progress = '\n'.join(f'stage {i} = {"bronze" if i <= count else "none"} 0 played'
                                 for i in range(1, 6))
            self.assertEqual(campaign_in_progress(progress), 0 < count < 5)
            self.assertEqual(campaign_cleared(progress), count)
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
