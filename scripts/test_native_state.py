"""Native layouts and bounds without a live game or native memory writes."""
import struct
import unittest
from unittest.mock import Mock, patch

import numpy as np

from native_state import NativeState, WALL, EVAC, HELI, VEHICLE, MEDEVAC


class NativeTests(unittest.TestCase):
    def test_fixed_record_strides_and_offsets(self):
        for dtype, size in [(WALL,192),(EVAC,52),(HELI,144),(VEHICLE,400),(MEDEVAC,96)]:
            self.assertEqual(dtype.itemsize,size)
        raw=bytearray(400)
        struct.pack_into('<2f',raw,0,10.,20.)
        struct.pack_into('<q',raw,352,17)
        raw[317]=2
        row=np.frombuffer(raw,VEHICLE)[0]
        self.assertEqual(row['carried'],17)
        self.assertEqual(row['kind'],2)
        np.testing.assert_array_equal(row['pos'],[10.,20.])

    def test_map_sparse_keys_and_byte_values(self):
        state=NativeState(Mock(base=0))
        memory={100:struct.pack('<Qq',0x10000|3,2),
            0x10000:struct.pack('<8Q',0,0,41,0,0,99,0,0),
            0x10040:bytes([0,0,5,0,0,2,0,0]),
            0x10048:struct.pack('<8Q',0,0,71,0,0,83,0,0)}
        state.read=lambda address,size:memory[address]
        self.assertEqual(state.mapping(100,'u1'),{41:5,99:2})
        memory[100]=struct.pack('<Qq',0x10000|3,3)
        with self.assertRaisesRegex(RuntimeError,'changed'):state.mapping(100,'u1')

    def test_negative_array_count_and_oversized_map_fail(self):
        state=NativeState(Mock(base=0))
        state.read=Mock(return_value=struct.pack('<Qq',0,-1))
        with self.assertRaisesRegex(RuntimeError,'count'):state.array_at(100,'u1')
        state.read.return_value=struct.pack('<Qq',0x10000|32,1)
        with self.assertRaisesRegex(RuntimeError,'capacity'):state.mapping(100,'u1')

    def test_read_bounds_and_short_reads_fail(self):
        state=NativeState(Mock(h=0))
        for address,size in [(1,8),(65536,-1),(65536,65*1024*1024)]:
            with self.assertRaisesRegex(RuntimeError,'extent'):state.read(address,size)
        with patch('native_state.memscan.read',return_value=b''):
            with self.assertRaisesRegex(RuntimeError,'Incomplete'):state.read(65536,8)


if __name__=='__main__':unittest.main()
