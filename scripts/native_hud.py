"""Decode the game's observed selection panel; no game calls or memory writes."""
import math
import struct

from env_zar import ZAREnvError


def panel_actions(panel, width, height):
    if len(panel) != 0x868:
        raise ZAREnvError('Invalid HUD panel length')
    def get(offset, fmt):
        return struct.unpack_from('<'+fmt, panel, offset)[0]
    left, top, right, bottom = struct.unpack_from('<4f', panel)
    if not all(math.isfinite(v) for v in (left,top,right,bottom)) or right <= left:
        raise ZAREnvError('Invalid HUD panel rectangle')
    scale = width/(right+12)
    if not .5 <= scale <= 4:
        raise ZAREnvError('Invalid HUD panel scale')
    actions = {}
    def point(name, x, y):
        x, y = x*scale, y*scale
        if not math.isfinite(x+y) or not 0 <= x < width or not 0 <= y < height:
            raise ZAREnvError('HUD action outside client')
        actions[name] = (round(x),round(y))
    def rect(name, offset):
        x,y,x2,y2 = struct.unpack_from('<4f',panel,offset)
        if x2 <= x or y2 <= y:
            raise ZAREnvError('Invalid HUD action rectangle')
        point(name,(x+x2)/2,(y+y2)/2)
    for name,flag,offset in [('level_up',0x2b9,0x39c),('refund_level',0x2c0,0x3ac),
            ('target_toggle',0x3bc,0x3c0),('next_special',0x388,0x38c),
            ('upgrades_page',0x42c,0x430),('upgrades_back',0x440,0x430)]:
        if get(flag,'B'): rect(name,offset)
    if get(0x3d0,'B'): rect('detonate',0x3e8)
    if get(0x3e0,'q') >= 0: rect('vehicle_leave',0x3e8)
    count=get(0x340,'q')
    if not 0 <= count <= 4: raise ZAREnvError('Invalid building choice count')
    for i in range(count):
        ability, availability = get(0x348+i,'B'),get(0x34d+i,'B')
        if not 1 <= ability <= 15 or availability > 2:
            raise ZAREnvError('Invalid building choice')
        if availability == 0:
            point(f'building_{ability}',(left+right)/2,get(0x354,'f')+28*i+12)
    if get(0x358,'B'):
        point('building_officer_1',left+12,get(0x35c,'f')+12)
        point('building_officer_0',right-12,get(0x35c,'f')+12)
    if get(0x440,'B'):
        count=get(0x448,'q')
        if not 0 <= count <= 4: raise ZAREnvError('Invalid upgrade choice count')
        for i in range(count):
            y=get(0x470,'f')+i*82+60
            point(f'upgrade_buy_{i}',right-12,y)
            point(f'upgrade_refund_{i}',left+12,y)
    return actions


def read_panel(env):
    if env.scalar(0x6553e8,'<I') != 2:
        return dict(actions={}, valid=False)
    snapshot=env.vi.hud_snapshot()
    age=env.scalar(0x68e590,'<Q')-snapshot['frame']
    if not 0 <= age <= 8:
        raise ZAREnvError('Stale native HUD frame')
    if not snapshot['valid']:
        return dict(actions={},valid=False)
    panel=snapshot['panel']
    return dict(actions=panel_actions(panel,env.cw,env.ch),valid=True,
                unit=struct.unpack_from('<q',panel,0x2d0)[0],
                building=struct.unpack_from('<q',panel,0x2f8)[0],
                far_first=bool(panel[0x3bd]),level=struct.unpack_from('<q',panel,0x2c8)[0])
