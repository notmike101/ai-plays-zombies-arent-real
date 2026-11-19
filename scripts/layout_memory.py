"""Retrieve Boston planning demonstrations as continuous map-coordinate actions."""
import re
from pathlib import Path
import numpy as np
from game_controls import Controls
from spatial import project


def demonstrations(path):
    stages={}
    for line in Path(path).read_text().splitlines():
        match=re.fullmatch(r'hist_carry (\d+) (\w+) = (.+)',line)
        if not match:continue
        stage,kind,record=match.groups()
        fields=list(map(float,record.split()))
        if kind=='zone':
            count=int(fields[0])
            if not 2<=count<=128 or len(fields)<1+2*count:raise ValueError('Invalid recorded geometry')
            points=np.array(fields[1:1+2*count]).reshape(-1,2)
            kind='wall' if count==2 else 'zone'
        elif kind in ('garrison','gate'):
            points=[fields[:2]]
        elif kind=='evac' and fields[0] in (0,1):
            kind='corridor' if fields[0]==0 else 'hold'
            points=[fields[1:3],fields[3:5]]
        else:continue
        if not np.isfinite(points).all():raise ValueError('Nonfinite demonstration')
        stages.setdefault(int(stage),[]).append(dict(kind=kind,points=np.asarray(points).tolist()))
    return stages


def apply_layout(env,actions):
    ctrl=Controls(env)
    origin=np.array([env.scalar(r,'<f') for r in (0x665358,0x66535c)])
    records=[]
    for action in actions:
        if env.game_state()['phase']!='planning':raise RuntimeError('Layout lost planning phase')
        camera=[env.scalar(r,'<f') for r in (0x6553ac,0x6553b0,0x6553b4)]
        points=project(np.array(action['points'])-origin,camera,env.cw,env.ch)
        valid=np.all((points >= [.055*env.cw,.1*env.ch]) & (points <= [.935*env.cw,.7*env.ch]))
        kind=action['kind']
        if not valid:
            records.append(dict(kind=kind,result='outside_view'))
            continue
        points=[tuple(map(round,point)) for point in points]
        before=env.money()
        if before is None:raise RuntimeError('Missing native budget')
        if before<=0:break
        if kind=='garrison':
            if 'Garrison' not in ctrl.planning_roster():ctrl.equip_unit('Garrison',0)
            ctrl.place('Garrison',points[0])
        elif kind=='zone':
            for i,point in enumerate(points):ctrl.polygon_corner(point,begin=(i==0))
            ctrl.polygon_finish()
        elif kind=='gate':
            ctrl.arm(0x47,34)
            env.vi.click(*points[0]);ctrl.frames()
        elif kind in ('wall','corridor','hold'):
            ctrl.arm(*{'wall':(0x5A,44),'corridor':(0x51,16),'hold':(0x45,18)}[kind])
            ctrl.drag_handles(*points)
            if kind=='wall':env.vi.click(*points[-1])
            ctrl.frames()
        after=env.money()
        if after is None:raise RuntimeError('Missing post-action budget')
        records.append(dict(kind=kind,points=points,before=before,after=after))
    return records
