"""Retrieve Boston planning demonstrations as continuous map-coordinate actions."""
import re
from pathlib import Path
import numpy as np
from game_controls import Controls, PickerNavigationError
from spatial import inside_polygon, project

BUILDINGS={'garrison':'Garrison','mortar':'Mortar','sniper':'Sniper','nest':'Nest'}


def parse_records(lines):
    stages={}
    for line in lines:
        match=re.fullmatch(r'hist_carry (\d+) (\w+) = (.+)',line)
        if not match:continue
        stage,kind,record=match.groups()
        if kind not in (*BUILDINGS,'zone','gate','evac'):continue
        fields=list(map(float,record.split()))
        if kind=='zone':
            count=int(fields[0])
            if not 2<=count<=128 or len(fields)<1+2*count:raise ValueError('Invalid recorded geometry')
            points=np.array(fields[1:1+2*count]).reshape(-1,2)
            kind='wall' if count==2 else 'zone'
        elif kind in (*BUILDINGS,'gate'):
            points=[fields[:2]]
        elif kind=='evac' and fields[0] in (0,1):
            kind='corridor' if fields[0]==0 else 'hold'
            points=[fields[1:3],fields[3:5]]
        else:continue
        if not np.isfinite(points).all():raise ValueError('Nonfinite demonstration')
        stages.setdefault(int(stage),[]).append(dict(kind=kind,points=np.asarray(points).tolist()))
    return stages


def demonstrations(path):
    return parse_records(Path(path).read_text().splitlines())


def remaining_layout(actions, dump):
    existing=parse_records(line.replace('board ','hist_carry 1 ',1)
                           for line in dump['_text'].splitlines() if line.startswith('board ')).get(1,[])
    missing=[]
    for action in actions:
        for i,item in enumerate(existing):
            if item['kind']!=action['kind'] or len(item['points'])!=len(action['points']):continue
            points=item['points']
            if np.allclose(points,action['points'],atol=2.,rtol=0) or (
                    item['kind']=='wall' and np.allclose(points[::-1],action['points'],atol=2.,rtol=0)):
                existing.pop(i)
                break
        else:missing.append(action)
    return missing


def fit_refuge(actions,civilians,boundary,params):
    """Score equally sized refuge proposals against the observed planning population."""
    index=next((i for i,a in enumerate(actions) if a['kind']=='zone'),None)
    if index is None or not len(civilians):return actions,None
    original=np.asarray(actions[index]['points'])
    center=original.mean(axis=0)
    relative=original-center
    area=.5*abs(relative[:,0]@np.roll(relative[:,1],1)-relative[:,1]@np.roll(relative[:,0],1))
    if area<=0:return actions,None
    side=np.sqrt(area*params['aspect'])
    box=np.array([[-1,-1],[1,-1],[1,1],[-1,1]])*[side/2,area/(2*side)]
    sample=civilians[np.linspace(0,len(civilians)-1,min(2048,len(civilians)),dtype=int)]
    defenders=np.asarray([a['points'][0] for a in actions if a['kind'] in BUILDINGS]).reshape(-1,2)
    def assess(polygon):
        sheltered=float(inside_polygon(sample,polygon).mean())
        guarded=float(inside_polygon(defenders,polygon).mean()) if len(defenders) else 0.
        return sheltered+params['defense_weight']*guarded,sheltered
    best,initial=assess(original)
    winner,coverage=original,initial
    axes=np.quantile(sample,np.linspace(.1,.9,9),axis=0)
    for x in axes[:,0]:
        for y in axes[:,1]:
            for shape in (relative,box):
                polygon=shape*params['scale']+[x,y]
                if not inside_polygon(polygon,boundary).all():continue
                score,covered=assess(polygon)
                if score>best:best,coverage,winner=score,covered,polygon
    result=list(actions)
    if winner is not original:result[index]=dict(kind='zone',points=winner.tolist())
    return result,dict(sample=len(sample),original_covered=initial,proposed_covered=coverage,
                       points=winner.tolist())


def visible_points(env,ctrl,world):
    size=np.array([env.cw,env.ch])
    lower,upper=size*[.055,.10],size*[.935,.70]
    center=(lower+upper)/2
    previous=None
    for attempt in range(20):
        camera=[env.scalar(r,'<f') for r in (0x6553ac,0x6553b0,0x6553b4)]
        points=project(world,camera,env.cw,env.ch)
        if np.all((points>=lower)&(points<=upper)):
            return [tuple(map(round,p)) for p in points]
        if attempt==19 or env.scalar(0x667868,'<B'):break
        if attempt==0:ctrl.disarm()
        extent=np.ptp(points,axis=0)
        if np.any(extent>upper-lower):
            if previous is not None and camera[2]==previous[2]:break
            ctrl.zoom(-1,tuple(map(round,center)))
        else:
            offset=(points.min(axis=0)+points.max(axis=0))/2-center
            axis=np.argmax(np.abs(offset)/size)
            key=(('pan_left','pan_right'),('pan_up','pan_down'))[axis][int(offset[axis]>0)]
            ctrl.key_action(key)
        previous=camera
    return []


def apply_layout(env,actions,occupied=(), *, boundary=None):
    ctrl=Controls(env)
    origin=np.array([env.scalar(r,'<f') for r in (0x665358,0x66535c)])
    records=[]
    rejected=set()
    protected=set(occupied)|{BUILDINGS[a['kind']] for a in actions if a['kind'] in BUILDINGS}
    for action in actions:
        if env.game_state()['phase']!='planning':raise RuntimeError('Layout lost planning phase')
        kind=action['kind']
        before=env.money()
        if before is None:raise RuntimeError('Missing native budget')
        if before<=0:break
        if before<action.get('observed_cost',0):
            records.append(dict(kind=kind,result='below_observed_cost',before=before,
                                observed_cost=action['observed_cost']))
            break
        if boundary is not None and not inside_polygon(action['points'],boundary).all():
            records.append(dict(kind=kind,result='outside_playarea',world_points=action['points']))
            continue
        points=visible_points(env,ctrl,np.array(action['points'])-origin)
        if not points:
            records.append(dict(kind=kind,result='outside_view'))
            continue
        if kind in BUILDINGS:
            unit=BUILDINGS[kind]
            roster=ctrl.planning_roster()
            if unit not in roster:
                slots=sorted((i for i,name in enumerate(roster) if name not in protected),
                             key=lambda i:roster[i]!='-')
                for slot in slots:
                    if (unit,slot) in rejected:continue
                    try:
                        ctrl.equip_unit(unit,slot)
                        break
                    except PickerNavigationError:
                        if ctrl.planning_roster()!=roster:raise
                        rejected.add((unit,slot))
                        records.append(dict(kind=kind,result='picker_rejected',slot=slot))
                else:
                    records.append(dict(kind=kind,result='no_free_roster_slot'))
                    continue
            ctrl.place(unit,points[0])
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
        records.append(dict(kind=kind,points=points,world_points=action['points'],before=before,after=after))
    return records
