"""Native-control boundaries; these tests never attach to a game."""
import unittest
from unittest.mock import Mock, patch

from game_controls import Controls, wait_until, unit_choices
from game_mechanics import UNITS


class ControlsTests(unittest.TestCase):
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

    def test_picker_replaces_current_entry_with_clear_and_preserves_order(self):
        self.assertEqual(unit_choices('-'), list(UNITS))
        self.assertEqual(unit_choices('Mortar'), ['-']+[n for n in UNITS if n != 'Mortar'])
        with self.assertRaises(ValueError): unit_choices('unknown')

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
