"""Read-only, SHA-pinned player state. Layouts come from the native F6 reflection tables.

Entity kinds are simulation kinds, not toolbar IDs: mortar payloads distinguish
Gas/Fire/Howitzer/MLRS and turret payloads distinguish Railgun.
"""
import struct

import numpy as np

import memscan
from env_zar import ZAREnvError


def record(size, fields):
    return np.dtype(dict(names=[x[0] for x in fields], formats=[x[2] for x in fields],
                         offsets=[x[1] for x in fields], itemsize=size))


VEC = ('<f4', 2)
AI = record(56, [('mode',0,'u1'), ('way',16,VEC), ('way_t',24,'<f4'),
    ('walled',40,'u1'), ('fire_turn',44,VEC), ('fire_until',52,'<f4')])
PATCH = record(48, [('kind',0,'u1'), ('pos',4,VEC), ('radius',12,'<f4'),
    ('start',16,'<f4'), ('until',20,'<f4'), ('shooter',24,'<u8'), ('source',32,'u1')])
WALL = record(192, [('a',120,VEC), ('b',128,VEC), ('full_hp',152,'<f4'),
    ('level',160,'<i8'), ('build_left',168,'<f4'), ('build_total',172,'<f4')])
EVAC = record(52, [('kind',0,'u1'), ('a',4,VEC), ('b',12,VEC), ('dir',20,VEC),
    ('length',28,'<f4'), ('half_width',32,'<f4'), ('radius',36,'<f4'),
    ('attract_r',40,'<f4'), ('cost',44,'<f4'), ('hold_suppressed',48,'u1')])
HELI = record(144, [('pos',0,VEC), ('dir',8,VEC), ('vel',16,VEC),
    ('cooldown',24,'<f4'), ('mode',28,'u1'), ('mag',32,'<i4'), ('mags_used',40,'<i8'),
    ('leaving',48,'u1'), ('rearm_t',52,'<f4'), ('home',64,VEC), ('kills',80,'<i8'),
    ('ret_aim',104,VEC), ('heli_target',116,VEC), ('heli_has_order',124,'u1'),
    ('dmg',132,'<f4'), ('alive',136,'u1')])
VEHICLE = record(400, [('pos',0,VEC), ('dir',8,VEC), ('speed',16,'<f4'),
    ('alive',20,'u1'), ('dmg',24,'<f4'), ('gun_t',28,('<f4',4)), ('mag',44,'<i4'),
    ('mags_used',48,'<i8'), ('reload_t',56,'<f4'), ('kills',64,'<i8'),
    ('target',88,'<i4'), ('goal',92,VEC), ('turret',296,VEC), ('aim',304,VEC),
    ('aiming',316,'u1'), ('kind',317,'u1'), ('returning',318,'u1'), ('parked',319,'u1'),
    ('rearm_t',320,'<f4'), ('rearms',328,'<i8'), ('leaving',336,'u1'), ('left',344,'u1'),
    ('carried',352,'<i8'), ('landed',360,'<i8'), ('route',380,VEC), ('routing',388,'u1'),
    ('plowing',389,'u1'), ('pushing',392,'<i8')])
MEDEVAC = record(96, [('pos',0,VEC), ('dir',8,VEC), ('vel',16,VEC),
    ('phase',28,'u1'), ('spot',32,VEC), ('drop',40,VEC), ('ordered',56,'u1'),
    ('carried',64,'<i8'), ('landed',72,'<i8'), ('dmg',84,'<f4'), ('alive',88,'u1')])


class NativeState:
    def __init__(self, env):
        self.env = env
        env.validate_build()

    def read(self, address, size):
        if not 0 <= size <= 64*1024*1024 or size and address < 65536:
            raise ZAREnvError('Invalid native read extent')
        data = memscan.read(self.env.h, address, size) if size else b''
        if data is None or len(data) != size:
            raise ZAREnvError('Incomplete native state read')
        return data

    def array_at(self, address, dtype, limit=500000):
        pointer, count = struct.unpack('<Qq', self.read(address, 16))
        if not 0 <= count <= limit:
            raise ZAREnvError('Invalid native array count')
        dtype = np.dtype(dtype)
        return np.frombuffer(self.read(pointer, count*dtype.itemsize), dtype).copy()

    def mapping(self, rva, dtype):
        """Odin integer-key map: packed pointer/log-capacity, keys, values, hashes."""
        header, count = struct.unpack('<Qq', self.read(self.env.base+rva, 16))
        if count == 0:
            return {}
        power, pointer = header & 63, header & ~63
        if not 0 <= power <= 20 or not 0 < count <= 1 << power:
            raise ZAREnvError('Invalid native map capacity')
        capacity, dtype = 1 << power, np.dtype(dtype)
        keys = np.frombuffer(self.read(pointer, capacity*8), '<u8')
        values = np.frombuffer(self.read(pointer+capacity*8, capacity*dtype.itemsize), dtype)
        hashes = np.frombuffer(self.read(pointer+capacity*(8+dtype.itemsize), capacity*8), '<u8')
        used = np.flatnonzero(hashes)
        if len(used) != count:
            raise ZAREnvError('Native map changed during read')
        return {int(keys[i]): values[i].copy() for i in used}

    def zones(self):
        e = self.env
        headers = e.array(0x65ccb0, 'V80', limit=1000)
        result = []
        for header in headers:
            raw = header.tobytes()
            pointer, count = struct.unpack_from('<Qq', raw)
            if not 0 <= count <= 10000:
                raise ZAREnvError('Invalid zone vertex count')
            vertices = np.frombuffer(self.read(pointer, count*8), '<f4').reshape(-1,2).copy()
            result.append(vertices)
        return result

    def paint(self):
        paint = self.mapping(0x6509c8, 'u1')
        if any(value not in (1, 2) for value in paint.values()):
            raise ZAREnvError('Unknown native terrain paint')
        # Native plan capture packs signed cell x/y into the low/high32 bits.
        cells = np.asarray(list(paint), dtype='<u8').view('<i4').reshape(-1,2)
        return dict(pos=(cells.astype(np.float32)+.5)*4,
                    kind=np.asarray(list(paint.values()), dtype='u1'))

    def selection(self):
        e = self.env
        return dict(units=e.array(0x65c490,'<u8'),
                    helicopters=e.array(0x65c4b8,'<i8'),
                    zones=e.array(0x65c4f8,'<i8'),
                    evac=e.array(0x65c520,'<i8'),
                    zone=e.scalar(0x65c4e0,'<q'),
                    edge=e.scalar(0x65c4e8,'<q'),
                    gate=e.scalar(0x65c4f0,'<q')-1,
                    building=e.scalar(0x6593b0,'<q')-1,
                    polygon=e.array(0x65ccd8,VEC,limit=10000),
                    menu=bool(e.scalar(0x666870,'<B')))

    def snapshot(self):
        e = self.env
        for _ in range(5):
            try:
                tick = e.scalar(0x6514e8, '<q')
                units = {name: e.array(rva, dtype) for name, rva, dtype in (
                    ('pos',0x650280,VEC), ('dir',0x6502a8,VEC), ('kind',0x6502d0,'u1'),
                    ('timer',0x650320,'<f4'), ('converting',0x650348,'u1'),
                    ('hp',0x650370,'<f4'), ('ztype',0x650398,'u1'),
                    ('contact',0x6503c0,'<f4'), ('id',0x650410,'<u8'))}
                if len({len(a) for a in units.values()}) != 1:
                    continue
                if any(not np.isfinite(units[k]).all() for k in ('pos','dir','timer','hp','contact')):
                    raise ZAREnvError('Nonfinite native entity state')
                if np.any(units['kind'] > 10):
                    raise ZAREnvError('Unknown native entity kind')
                maps = {name: self.mapping(rva, dtype) for name,rva,dtype in (
                    ('level',0x6508d8,'<i8'), ('far_first',0x6508f8,'u1'),
                    ('payload',0x650988,'u1'), ('trap_kind',0x6509a8,'u1'),
                    ('upgrades',0x650968,('u1',4)), ('ai',0x650898,AI),
                    ('boosts',0x650918,('<f4',5)), ('officer_kind',0x650ba0,'u1'),
                    ('roof',0x650858,'<i8'), ('kills',0x6543f0,'<i4'))}
                walls = e.array(0x656bb0,WALL,limit=10000)
                wall_pointer = e.scalar(0x656bb0,'<Q')
                wall_hp = [self.array_at(wall_pointer+i*192+80,'<f4') for i in range(len(walls))]
                result = dict(units=units, unit_maps=maps, zones=self.zones(),
                    playarea=e.array(0x6652e0,VEC,limit=10000),
                    walls=walls, wall_hp=wall_hp, paint=self.paint(), selection=self.selection(),
                    hazards=e.array(0x654ef0,PATCH,limit=100000),
                    evac=e.array(0x657e40,EVAC,limit=10000),
                    gates=e.array(0x65d3d8,VEC,limit=10000),
                    helicopters=e.array(0x65c580,HELI,limit=10000),
                    vehicles=e.array(0x65c5a8,VEHICLE,limit=10000),
                    medevacs=e.array(0x65cbe0,MEDEVAC,limit=10000),
                    buildings={name: e.array(rva,dtype) for name,rva,dtype in (
                        ('rect',0x656680,('<f4',4)), ('destroyed',0x6566d8,'u1'),
                        ('damage',0x656700,'<f4'), ('max_hp',0x656728,'<f4'),
                        ('class',0x658f00,'u1'), ('ability',0x658f50,'u1'),
                        ('officer_kind',0x658f78,'u1'),
                        ('area',0x658d70,'<f4'), ('center',0x658d98,VEC))},
                    camera=[e.scalar(rva,'<f') for rva in (0x6553ac,0x6553b0,0x6553b4)],
                    tick=tick)
                if tick == e.scalar(0x6514e8,'<q'):
                    return result
            except ZAREnvError:
                if _ == 4:
                    raise
        raise ZAREnvError('Native snapshot changed during read')
