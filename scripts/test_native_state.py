"""Native layouts and bounds without a live game or native memory writes."""
import struct
import unittest
from unittest.mock import Mock, patch

import numpy as np

from native_state import NativeState, WALL, EVAC, HELI, VEHICLE, MEDEVAC, AI


class NativeTests(unittest.TestCase):
    def snapshot_reader(self):
        e=Mock(base=0,cw=1920,ch=1200);clock=[0];reads=[]
        e.scalar.side_effect=lambda r,f:clock[0] if r==0x6514e8 else 1 if r==0x6553b4 else 0
        def array(r,dtype,**kwargs):
            reads.append(r)
            if r==0x656bb0:clock[0]+=1  # Other systems can advance after coherent units.
            return np.zeros(0,dtype=dtype)
        e.array.side_effect=array
        state=NativeState(e)
        def read(address,size):
            reads.append(address)
            return bytes(size)
        state.read=Mock(side_effect=read)
        for name in ('mapping','zones','terrain','fire','bridge_health','paint','selection'):
            setattr(state,name,Mock(return_value={}))
        return state,clock,reads

    def test_world_read_can_cross_tick_after_coherent_unit_arrays(self):
        state,clock,reads=self.snapshot_reader()
        result=state.snapshot()
        self.assertEqual(result['tick'],0);self.assertEqual(clock[0],1)
        self.assertEqual(reads.count(0x650280),1)

    def test_unit_arrays_retry_if_tick_changes_during_aligned_read(self):
        state,clock,reads=self.snapshot_reader();original=state.read.side_effect
        def read(r,size):
            result=original(r,size)
            if r==0x650280 and reads.count(r)<=5:clock[0]+=1
            return result
        state.read.side_effect=read
        result=state.snapshot()
        self.assertEqual(result['tick'],5);self.assertEqual(reads.count(0x650280),6)

    def test_batched_unit_headers_preserve_offsets_and_shapes(self):
        state=NativeState(Mock(base=0))
        headers=bytearray(0x1a0)
        offsets=[0,0x28,0x50,0xa0,0xc8,0xf0,0x118,0x140,0x190]
        for index,offset in enumerate(offsets,1):
            struct.pack_into('<Qq',headers,offset,index*65536,1)
        state.read=Mock(side_effect=lambda addr,size:headers if addr==0x650280 else bytes([addr//65536])*size)
        units=state.units()
        self.assertEqual(units['pos'].shape,(1,2))
        for index,key in enumerate(('pos','dir','kind','timer','converting','hp','ztype','contact','id'),1):
            self.assertEqual(units[key].tobytes(),bytes([index])*units[key].nbytes)

    def test_persistent_count_mismatch_reports_reason_and_never_uses_torn_units(self):
        state,_,_=self.snapshot_reader()
        state.units=Mock(return_value={'pos':np.zeros((1,2)),'kind':np.zeros(2)})
        with patch('native_state.time.sleep'),self.assertRaisesRegex(RuntimeError,'count mismatches=20'):
            state.snapshot()
        self.assertEqual(state.units.call_count,20)

    def test_terrain_requires_matching_storage_and_known_codes(self):
        e=Mock(base=0);e.scalar.side_effect=lambda r,f:{0x656a48:2,0x656a50:2,0x656a40:2.}[r]
        state=NativeState(e)
        memory={0x656a58:struct.pack('<Qq',0x10000,4),0x656a80:struct.pack('<Qq',0x20000,1),
                0x10000:b'\x04',0x10001:b'\x00',0x10002:b'\x01',0x20000:struct.pack('<Q',2)}
        state.read=Mock(side_effect=lambda address,size:memory[address])
        result=state.terrain([(1,1),(3,1),(1,3),(-.1,1),(4,1)])
        self.assertEqual(result['codes'].tolist(),[4,0,1,-1,-1])
        self.assertEqual(result['bridges'].tolist(),[0,1,0,0,0])
        self.assertTrue(all(call.args[1]<=16 for call in state.read.call_args_list))
        memory[0x10000]=b'\xff'
        with self.assertRaisesRegex(RuntimeError,'code'):state.terrain([(1,1)])
        memory[0x656a58]=struct.pack('<Qq',0x10000,3)
        with self.assertRaisesRegex(RuntimeError,'storage'):state.terrain([])

    def test_fire_samples_sparse_tiles_and_subcell_masks(self):
        e=Mock(base=0);e.scalar.side_effect=lambda r,f:{0x654f40:64,0x654f48:32,0x654f50:2,0x654f58:1}[r]
        state=NativeState(e);tile=bytearray(0x1c10);tile[0]=3
        struct.pack_into('<H',tile,0x400,65535);struct.pack_into('<H',tile,0xc00,15)
        memory={0x654f60:struct.pack('<Qq',0x10000,2),0x10000:struct.pack('<Q',0x20000),
            0x10008:struct.pack('<Q',0),0x20000:bytes(tile)}
        state.read=Mock(side_effect=lambda address,size:memory[address])
        result=state.fire([(1,1),(257,1),(-1,1)])
        self.assertEqual(result['flags'].tolist(),[3,0,0])
        self.assertEqual(result['green'].tolist(),[1.,0.,0.])
        self.assertEqual(result['burnt'].tolist(),[.25,0.,0.])
        self.assertTrue(all(c.args[1]<=0x1c10 for c in state.read.call_args_list))

    def test_bridge_damage_keys_project_to_native_anchor_cells(self):
        e=Mock(base=0);e.scalar.side_effect=lambda r,f:{0x656a48:10,0x656a50:20,0x656a40:2.}[r]
        e.array.return_value=np.array([[23,60,100],[24,-10,100]],dtype='<i8')
        state=NativeState(e);b=state.bridge_health()
        np.testing.assert_array_equal(b['pos'],[[7.,5.],[9.,5.]])
        self.assertEqual(b['hp'].tolist(),[60,-10])
        e.array.return_value=np.array([[200,60,100]],dtype='<i8')
        with self.assertRaisesRegex(RuntimeError,'bridge'):state.bridge_health()

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
        payload = b''.join(memory[x] for x in (0x10000, 0x10040, 0x10048))
        state.read=Mock(side_effect=[memory[100], payload, memory[100]])
        self.assertEqual(state.mapping(100,'u1'),{41:5,99:2})
        self.assertEqual(state.read.call_args_list[1].args, (0x10000, len(payload)))
        changed = struct.pack('<Qq',0x20000|3,2)
        state.read=Mock(side_effect=[memory[100], payload, changed,
                                    changed, payload, changed])
        self.assertEqual(state.mapping(100,'u1'),{41:5,99:2})
        self.assertEqual(state.read.call_args_list[4].args, (0x20000, len(payload)))
        state.read=Mock(side_effect=[memory[100], payload, changed] * 3)
        with self.assertRaisesRegex(RuntimeError,'changed during read at RVA 0x64'):
            state.mapping(100,'u1')
        self.assertEqual(state.read.call_count,9)
        state.read=Mock(side_effect=[struct.pack('<Qq',0x10000|3,3), payload] * 3)
        with self.assertRaisesRegex(RuntimeError,'changed during read at RVA 0x64'):
            state.mapping(100,'u1')
        self.assertEqual(state.read.call_count,6)

    def test_map_values_skip_native_cache_line_padding(self):
        for dtype,size,per_line in [(('<f4',5),20,3),(AI,56,1)]:
            with self.subTest(size=size):
                state=NativeState(Mock(base=0));cap=8
                extent=(cap//per_line)*64+(cap%per_line)*size
                raw=bytearray(b'\xff'*extent)
                index=3;offset=(index//per_line)*64+(index%per_line)*size
                raw[offset:offset+size]=bytes(size)
                memory={100:struct.pack('<Qq',0x10000|3,1),
                    0x10000:struct.pack('<8Q',0,0,0,42,0,0,0,0),
                    0x10040:bytes(raw),
                    0x10040+extent:struct.pack('<8Q',0,0,0,71,0,0,0,0)}
                payload = b''.join(memory[x] for x in (0x10000, 0x10040, 0x10040+extent))
                state.read=Mock(side_effect=[memory[100], payload, memory[100]])
                result=state.mapping(100,dtype)
                self.assertEqual(list(result),[42])
                if np.dtype(dtype).names:
                    for field in np.dtype(dtype).names:
                        self.assertTrue(np.all(result[42][field]==0))
                else:self.assertEqual(result[42].tobytes(),bytes(size))

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

    def test_paint_signed_coordinates_and_unknown_kind(self):
        state=NativeState(Mock())
        key=struct.unpack('<Q',struct.pack('<ii',-2,3))[0]
        state.mapping=Mock(return_value={key:np.uint8(2)})
        paint=state.paint()
        np.testing.assert_array_equal(paint['pos'],[[-6,14]])
        np.testing.assert_array_equal(paint['kind'],[2])
        state.mapping.return_value={key:np.uint8(9)}
        with self.assertRaisesRegex(RuntimeError,'paint'):state.paint()


if __name__=='__main__':unittest.main()
