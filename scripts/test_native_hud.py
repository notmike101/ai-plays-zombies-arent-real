"""HUD bounds, seqlock and action coordinates without attaching to a game."""
import ctypes
import struct
import unittest
from unittest.mock import Mock, patch

from native_hud import panel_actions, read_panel
from zar_input import VirtualInput


class HudTests(unittest.TestCase):
    def panel(self):
        b=bytearray(0x868)
        struct.pack_into('<4f',b,0,788,72,1268,516)
        struct.pack_into('<q',b,0x3e0,-1)
        return b

    def test_native_buttons_scale_and_disabled_choices(self):
        b=self.panel();b[0x3bc]=1
        struct.pack_into('<4f',b,0x3c0,796,424,1260,448)
        struct.pack_into('<q',b,0x340,3)
        b[0x348:0x34b]=bytes([2,3,15]);b[0x34d:0x350]=bytes([0,2,0])
        struct.pack_into('<f',b,0x354,300)
        self.assertEqual(panel_actions(b,1920,1200),
            dict(target_toggle=(1542,654),building_2=(1542,468),building_15=(1542,552)))

    def test_invalid_coordinates_and_counts_fail(self):
        b=self.panel();struct.pack_into('<q',b,0x340,5)
        with self.assertRaisesRegex(RuntimeError,'count'):panel_actions(b,1920,1200)
        b=self.panel();struct.pack_into('<f',b,0,float('nan'))
        with self.assertRaisesRegex(RuntimeError,'rectangle'):panel_actions(b,1920,1200)

    def test_action_discriminator_and_medevac_departure(self):
        b=self.panel();struct.pack_into('<4f',b,0x3e8,800,400,1260,430)
        b[0x3d0]=7
        self.assertNotIn('detonate',panel_actions(b,1920,1200))
        b[0x3d0]=8
        self.assertIn('detonate',panel_actions(b,1920,1200))
        b[0x3d0]=0;struct.pack_into('<q',b,0x3e0,2)
        self.assertIn('medevac_leave',panel_actions(b,1920,1200))

    def test_menu_and_stale_frames_cannot_supply_actions(self):
        env=Mock(cw=1920,ch=1200)
        env.scalar.return_value=1
        self.assertFalse(read_panel(env)['valid']);env.vi.hud_snapshot.assert_not_called()
        env.scalar.side_effect=[2,100]
        env.vi.hud_snapshot.return_value=dict(frame=80,valid=True,panel=self.panel())
        with self.assertRaisesRegex(RuntimeError,'Stale'):read_panel(env)

    def test_shared_mapping_seqlock_and_protocol(self):
        raw=ctypes.create_string_buffer(4096)
        vi=VirtualInput.__new__(VirtualInput);vi.hud_view=ctypes.addressof(raw)
        def header(sequence=2,version=1):
            ctypes.memmove(vi.hud_view,struct.pack('<IIQQII',0x5a485544,version,sequence,55,1,2),32)
        header();self.assertEqual(vi.hud_snapshot()['frame'],55)
        header(sequence=3)
        with self.assertRaisesRegex(RuntimeError,'consistent'):vi.hud_snapshot()
        header(version=2)
        with self.assertRaisesRegex(RuntimeError,'layout'):vi.hud_snapshot()
        header()
        real=ctypes.string_at
        def changed(address,size):
            return struct.pack('<Q',4) if address==vi.hud_view+8 else real(address,size)
        with patch('zar_input.ctypes.string_at',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'consistent'):vi.hud_snapshot()


if __name__=='__main__':unittest.main()
