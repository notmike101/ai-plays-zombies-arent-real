"""Native-control boundaries; these tests never attach to a game."""
import unittest
from unittest.mock import Mock, patch

from game_controls import Controls, UIFrameTimeout, wait_until, unit_choices
from game_mechanics import UNITS


class ControlsTests(unittest.TestCase):
    def test_overview_can_defer_a_camera_frame_timeout_without_masking_other_errors(self):
        import numpy as np
        env = Mock(cw=1920, ch=1200)
        env.scalar.return_value = 0
        env.game_state.return_value = {'phase': 'playing'}
        controls = Controls(env)
        controls.play_bounds = np.array([[0, 0], [1000, 1000]])
        controls.key_action = Mock(side_effect=UIFrameTimeout('lagged camera'))
        with patch('spatial.overview_geometry', return_value=(1., np.array([.5, 0.]))):
            self.assertFalse(controls.rest_view())
            controls.key_action.assert_called_once()
            controls.key_action.side_effect = RuntimeError('different error')
            with self.assertRaisesRegex(RuntimeError, 'different error'):
                controls.rest_view()

    def test_slow_ui_can_confirm_two_frames_without_resending_input(self):
        env = Mock()
        env.scalar.side_effect = [10, 10, 10, 12]
        with patch('game_controls.time.monotonic', side_effect=[0, .5, 1.1]), patch('game_controls.time.sleep'):
            Controls(env).frames()
        env.vi.assert_not_called()

    def test_endpoint_drag_releases_button_when_frame_receipt_fails(self):
        c=Controls(Mock());c.frames=Mock(side_effect=[None,RuntimeError('stalled UI')])
        with self.assertRaisesRegex(RuntimeError,'stalled UI'):
            c.drag_handles((100,200),(300,400))
        c.env.vi.button_down.assert_called_once()
        c.env.vi.button_up.assert_called_once()

    def test_rectangle_stops_when_native_draft_or_committed_geometry_diverges(self):
        import numpy as np

        existing = np.array([(0, 0), (1, 0), (1, 1), (0, 1)])
        rectangle = existing + 2
        changed = np.vstack((existing, [0, 2]))
        for status, stopped_at in (('confirmed', 4), ('commit_unconfirmed', 4),
                                   ('unexpected_committed_geometry', 4), ('modal', 2),
                                   ('draft_disarmed', 2), ('draft_vertex_count_mismatch', 2),
                                   ('draft_not_empty_after_arm', 0),
                                   ('existing_zone_changed_during_draft', 2)):
            with self.subTest(status=status):
                control = Controls(Mock())
                control.arm = Mock()
                control.polygon_corner = Mock()
                control.polygon_finish = Mock()

                def native(rva, fmt):
                    count = control.polygon_corner.call_count
                    if rva == 0x667868:
                        return status == 'modal' and count == 2
                    if rva == 0x65c488:
                        return not (status == 'draft_disarmed' and count == 2)
                    if status == 'draft_not_empty_after_arm':
                        return 1
                    return count - int(status == 'draft_vertex_count_mismatch' and count == 2)

                def zones():
                    if status == 'existing_zone_changed_during_draft' and control.polygon_corner.call_count == 2:
                        return [changed]
                    if control.polygon_finish.called:
                        if status == 'confirmed':
                            return [rectangle, existing]
                        if status == 'unexpected_committed_geometry':
                            return [changed, rectangle]
                    return [existing]

                control.env.scalar.side_effect = native
                control.env.array.return_value = rectangle
                self.assertEqual(control.zone_rectangle((100, 200), (300, 400), read_zones=zones), status)
                self.assertEqual(control.polygon_corner.call_args_list, [
                    unittest.mock.call((100, 200)),
                    unittest.mock.call((300, 200)),
                    unittest.mock.call((300, 400)),
                    unittest.mock.call((100, 400))][:stopped_at])
                control.arm.assert_called_once_with(66, 48)
                self.assertEqual(control.polygon_finish.call_count, int(stopped_at == 4))
                control.env.vi.assert_not_called()

    def test_freeform_corner_reports_whether_native_draft_advanced(self):
        control = Controls(Mock())
        control.polygon_corner = Mock()
        control.env.scalar.side_effect = lambda rva, fmt: {0x667868: 0, 0x65c488: 1, 0x65cce0: 1}[rva]
        point = (120, 341)
        self.assertEqual(control.append_shelter_corner(point, begin=True, expected=1, read_zones=list),
                         'draft_vertex_confirmed')
        self.assertEqual(control.append_shelter_corner(point, begin=False, expected=2, read_zones=list),
                         'draft_vertex_count_mismatch')
        self.assertEqual(control.polygon_corner.call_args_list,
                         [unittest.mock.call(point, begin=True), unittest.mock.call(point, begin=False)])

    def test_freeform_finish_accepts_a_native_concave_five_corner_polygon(self):
        import numpy as np

        control = Controls(Mock())
        control.env.scalar.side_effect = lambda rva, fmt: {0x667868: 0, 0x65c488: 1, 0x65cce0: 5}[rva]
        control.polygon_finish = Mock()
        polygon = np.array([(0, 0), (4, 0), (2, 2), (4, 4), (0, 4)])
        control.env.array.return_value = polygon
        zones = Mock(side_effect=[[], [polygon]])
        self.assertEqual(control.finish_shelter(zones), 'confirmed')
        control.polygon_finish.assert_called_once_with()
        control.polygon_finish.reset_mock()
        control.env.array.return_value = polygon[[0, 3, 1, 4, 2]]
        self.assertEqual(control.finish_shelter(zones), 'draft_geometry_not_simple')
        control.polygon_finish.assert_not_called()

    def test_gesture_preserves_selection_and_releases_modifier_on_failure(self):
        c=Controls(Mock());c.frames=Mock();c.cancel=Mock()
        c.env.vi.drag.side_effect=RuntimeError('input failure')
        with self.assertRaisesRegex(RuntimeError,'input failure'):
            c.gesture((10,20),(30,40),shift=True)
        c.cancel.assert_not_called()
        c.env.vi.key_up.assert_called_once_with(16,sc=42)

    def test_cancel_never_issues_move_order_without_active_tool(self):
        env = Mock()
        c = Controls(env)
        c.frames = Mock()
        c.tool_active = Mock(return_value=False)
        c.cancel()
        env.vi.click.assert_called_once_with(30, 60)
        env.vi.click.reset_mock()
        c.tool_active.return_value = True
        c.cancel()
        self.assertEqual(env.vi.click.call_args_list,
                         [unittest.mock.call(30,60,right=True),unittest.mock.call(30,60)])

    def test_additive_selection_preserves_existing_selection(self):
        env = Mock()
        c = Controls(env)
        c.frames, c.cancel = Mock(), Mock()
        c.tool_active = Mock(return_value=False)
        c.select((300,400),additive=True)
        c.cancel.assert_not_called()
        env.vi.click.assert_called_once_with(300,400)
        env.vi.key_up.assert_called_once_with(16,sc=42)

    def test_selection_and_reaim_disarm_without_deselecting(self):
        for method in ('add','move','reaim'):
            c=Controls(Mock());c.frames=Mock();c.tool_active=Mock(return_value=True)
            if method=='add':c.select((300,400),additive=True)
            else:c.move_selection((300,400),reaim=method=='reaim')
            expected=[unittest.mock.call(30,60,right=True),
                      unittest.mock.call(300,400,**({} if method=='add' else {'right':True}))]
            self.assertEqual(c.env.vi.click.call_args_list,expected)
            if method!='move':c.env.vi.key_up.assert_called_once_with(16,sc=42)

    def test_picker_replaces_current_entry_with_clear_and_preserves_order(self):
        self.assertEqual(unit_choices('-'), list(UNITS))
        self.assertEqual(unit_choices('Mortar'), ['-']+[n for n in UNITS if n != 'Mortar'])
        with self.assertRaises(ValueError): unit_choices('unknown')

    def test_picker_retries_missed_arrow_and_rejects_wrong_row(self):
        from env_zar import ZAREnvError

        for target, succeeds in ((1, True), (2, False)):
            with self.subTest(target=target):
                c = Controls(Mock())
                c.frames = Mock()
                current, opened, arrows = 0, True, []
                c.env.scalar.side_effect = lambda rva, _: opened if rva == 0x6560f0 else current

                def press(vk, **kwargs):
                    nonlocal current, opened
                    if vk == 13:
                        opened = False
                    else:
                        arrows.append(kwargs['hold'])
                        if len(arrows) == 2:
                            current = target

                def receipt(predicate, description):
                    if not predicate():
                        raise ZAREnvError('Timed out waiting for ' + description)

                c.env.vi.key_press.side_effect = press
                with patch('game_controls.wait_until', side_effect=receipt):
                    if succeeds:
                        c.pick(1)
                        self.assertFalse(opened)
                    else:
                        with self.assertRaisesRegex(ZAREnvError, 'expected 1'):
                            c.pick(1)
                        self.assertTrue(opened)
                self.assertEqual(arrows, [.05, .075])

    def test_wait_is_bounded_and_returns_the_receipt(self):
        self.assertEqual(wait_until(lambda: {'money': 42}, 'receipt'), {'money': 42})
        with self.assertRaisesRegex(RuntimeError, 'receipt'):
            wait_until(lambda: False, 'receipt', timeout=0)

    def test_invalid_roster_selection_never_sends_input(self):
        env = Mock(cw=1920, ch=1200)
        c = Controls(env)
        for name, slot in [('unknown',0),('Sniper',7),('Sniper',-1)]:
            with self.assertRaises(ValueError): c.equip_unit(name,slot)
        env.vi.key_press.assert_not_called()

    def test_native_roster_unknown_ids_are_not_empty_slots(self):
        env = Mock(cw=1920, ch=1200)
        env.scalar.side_effect=[4,2,3,5,6,7,255]
        with self.assertRaisesRegex(RuntimeError, 'roster'):
            Controls(env).planning_roster()

    def test_open_waits_for_layout_after_mode_transition(self):
        env = Mock(cw=1920, ch=1200)
        env.game_state.return_value = {'phase': 'planning'}
        env.scalar.side_effect = [1, 100, 100, 101, 102]
        with patch('game_controls.time.sleep'):
            Controls(env).open_loadout()
        self.assertEqual(env.scalar.call_count, 5)

    def test_campaign_perk_rejects_locked_or_duplicate_choice(self):
        c = Controls(Mock())
        c.perks = Mock(return_value=[dict(name='Extra_Zones', locked=False),
            dict(name='Hot_Fire', locked=True), dict(name='-', locked=False)])
        for name, slot in [('Hot_Fire', 0), ('Fall_Gas', 1), ('Hot_Fire', 2)]:
            with self.assertRaises(ValueError): c.equip_perk(name, slot)
        c.env.vi.key_press.assert_not_called()

    def test_stale_unpurchased_battle_slot_uses_clear_entry_offset(self):
        import tempfile
        from pathlib import Path
        from env_zar import NATIVE_ABILITIES
        env = Mock()
        before = dict.fromkeys(NATIVE_ABILITIES, 0)
        env.loadout_levels.side_effect = [before, dict(before, Bomber=1)]
        env.unlocked_abilities.return_value = set(before)
        c = Controls(env)
        c.battle_roster = Mock(return_value=['Missile']+['-']*6)
        c.open_loadout, c.close_loadout, c.pick = Mock(), Mock(), Mock()
        with tempfile.TemporaryDirectory() as tmp:
            env.copy_dir.return_value = tmp
            (Path(tmp)/'battle_order.txt').write_text('\n'.join(NATIVE_ABILITIES))
            self.assertEqual(c.change_loadout('Bomber', 1), dict(before, Bomber=1))
        c.pick.assert_called_once_with(1)
        env.vi.wheel.assert_not_called()


if __name__ == '__main__': unittest.main()
