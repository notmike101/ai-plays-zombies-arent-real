"""Native observations and player gestures for the appended policy actions."""
import math

import numpy as np

from game_controls import Controls, KEY_ACTIONS
from game_mechanics import UNITS, UNIT_IDS, PERKS
from native_hud import read_panel
from native_state import NativeState
from spatial import project, centers, features, XF, YF
from scripts.mechanic_contract import EXTRA_TOOLS, EXTRA_LABELS, GRID_CHANNELS, PANEL_ACTIONS

PLACEMENTS = {2:'Garrison',3:'Mortar',4:'Napalm',5:'Nest',6:'Mine',7:'C4',8:'GasMortar'}
PLACEMENTS.update({72+EXTRA_TOOLS.index('place_'+name):name for name in UNITS
                   if 'place_'+name in EXTRA_TOOLS})
DRAGS = {'select_box','drag_world','shift_drag_world'}
SELECTORS = ('unit','building','wall','gate','evac','corner')
NONSPATIAL = set(KEY_ACTIONS)-{'pan_up','pan_left','pan_down','pan_right'} | {
    'zone_finish','zone_back','cancel_tool','undo'} | {'panel_'+name for name in PANEL_ACTIONS}


def extra_masks(st):
    masks=np.zeros((len(EXTRA_TOOLS),48),dtype=np.float32)
    if 'native' not in st:return masks
    sel=st['native']['selection'];planning=st['planning'];polygon=len(sel['polygon'])
    selected=any(len(sel[k]) for k in ('units','zones','walls','evac')) or sel['gate']>=0
    for i,name in enumerate(EXTRA_TOOLS):
        mask=masks[i];mask[:]=np.repeat(YF<.70,len(XF))
        enabled=True
        if name.startswith('place_'):enabled=planning and name[6:] in st['planning_roster']
        elif name.startswith('equip_'):
            enabled=planning;mask[:]=0;mask[:7]=1
        elif name.startswith('perk_'):
            enabled=planning;mask[:]=0
            target=name[5:].replace('clear','-')
            for slot in (1,2):
                p=st['perks'][slot]
                mask[slot]=not p['locked'] and p['name']!=target and (
                    target=='-' or target not in [p['name'] for p in st['perks']])
        elif name.startswith('panel_'):enabled=name[6:] in st['hud']['actions']
        elif name.startswith('select_') and name[7:] in SELECTORS:
            mask *= [point is not None for point in st['targets'][name[7:]]]
        elif name=='arm_slot':
            enabled=planning;mask[:]=0;mask[:7]=[n!='-' for n in st['planning_roster']]
        elif name in ('zone_begin','zone_corner','zone_finish','zone_back'):
            enabled=planning and (name=='zone_begin' or polygon>0)
            if name=='zone_finish':enabled=enabled and polygon>=3
        elif name=='undo':enabled=planning
        elif name in ('move_selection','reaim_selection','officer_mode','officer_paint'):
            enabled=selected
        elif name=='refund_selection':enabled=planning or len(sel['evac'])>0
        elif name=='detonate_all':enabled=not planning and bool(np.any(st['native']['units']['kind']==9))
        elif name.startswith('speed_'):enabled=not planning
        if name in NONSPATIAL or name.startswith('pan_'):
            mask[:]=0;mask[0]=1
        if not enabled:mask[:]=0
    if st.get('gesture_anchor'):
        active=st['gesture_anchor'][0]
        for i,name in enumerate(EXTRA_TOOLS):
            if name not in (active,'cancel_tool'):masks[i]=0
    return masks


def nearest_per_cell(points, width, height):
    points=np.asarray(points).reshape(-1,2)
    visible=((points[:,0]>=0)&(points[:,0]<width)&(points[:,1]>=.07*height)&(points[:,1]<.8*height))
    points=points[visible]
    result=[None]*48
    if len(points):
        col=np.abs(points[:,:1]/width-XF).argmin(1)
        row=np.abs(points[:,1:]/height-YF).argmin(1)
        bins=row*8+col
        order=np.argsort(((points-centers(width,height)[bins])**2).sum(1),kind='stable')
        _,first=np.unique(bins[order],return_index=True)
        for i in order[first]:result[bins[i]]=tuple(map(int,points[i]))
    return result


def unit_names(units, maps):
    base={4:'Sniper',5:'Mortar',6:'Garrison',7:'Nest',8:'Mine',9:'C4',10:'Battleship'}
    names=np.full(len(units['kind']),'',dtype='<U12')
    for kind,name in base.items():names[units['kind']==kind]=name
    for i in np.flatnonzero(np.isin(units['kind'],[5,7,8,9])):
        kind,uid=units['kind'][i],units['id'][i]
        name=names[i]
        payload=int(maps['payload'].get(int(uid),0))
        trap=int(maps['trap_kind'].get(int(uid),0))
        if kind==5:name={0:'Mortar',1:'GasMortar',2:'FireMortar',3:'Howitzer',4:'MLRS'}.get(payload,'')
        if kind==7 and payload==5:name='Railgun'
        if trap==1:name='ChemMine'
        if trap==2:name='Napalm'
        names[i]=name
    return names


def observation(snapshot, roster, perks, hud, paint_mode, legal, land_fraction, width, height):
    s=snapshot;sel=s['selection'];u=s['units'];maps=s['unit_maps']
    camera=s['camera'];g=lambda x:math.log1p(max(float(x),0))
    result=[camera[0]/10000,camera[1]/10000,camera[2]/8,float(paint_mode),float(legal),land_fraction]
    result += [g(len(sel[k])) for k in ('polygon','units','zones','walls','evac')]
    result += [UNIT_IDS.get(name,0)/42 for name in roster]
    for perk in perks:
        result += [(PERKS.index(perk['name'])+1)/8 if perk['name']!='-' else 0,float(perk['locked'])]
    selected=np.isin(u['id'],sel['units'])
    indices=np.flatnonzero(selected)
    detail=[0.]*19
    if len(indices):
        i=indices[0];uid=int(u['id'][i]);ai=maps['ai'].get(uid)
        detail=[u['kind'][i]/10,maps['payload'].get(uid,0)/5,maps['trap_kind'].get(uid,0)/2,
            maps['level'].get(uid,1)/4,g(u['hp'][i]),u['contact'][i]/100,u['timer'][i]/60,
            *u['dir'][i],float(maps['far_first'].get(uid,0)),maps['officer_kind'].get(uid,0)/2,
            float(ai['mode'])/8 if ai is not None else 0,g(maps['kills'].get(uid,0)),
            float(u['converting'][i]),*maps['boosts'].get(uid,[0.]*5)]
    result += detail
    def histogram(points):
        xy=project(points,camera,width,height)
        if not len(xy):return np.zeros(48)
        visible=((xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=.07*height)&(xy[:,1]<.8*height))
        col=np.abs(xy[:,:1]/width-XF).argmin(1);row=np.abs(xy[:,1:]/height-YF).argmin(1)
        return np.bincount((row*8+col)[visible],minlength=48)
    names=unit_names(u,maps)
    channels=[u['pos'][names==name] for name in UNITS if name not in ('Spikes','Oil')]
    channels += [s['paint']['pos'][s['paint']['kind']==kind] for kind in (1,2)]
    buildings=s['buildings'];valid=buildings['destroyed']==0
    channels += [buildings['center'][valid&(buildings['class']==kind)] for kind in range(1,8)]
    channels += [buildings['center'][valid&(buildings['damage']>0)],
        (s['walls']['a']+s['walls']['b'])/2,
        s['evac']['a'][s['evac']['kind']==0],s['evac']['a'][s['evac']['kind']==1],
        s['helicopters']['pos'][s['helicopters']['alive']!=0],
        s['medevacs']['pos'][s['medevacs']['alive']!=0],
        s['vehicles']['pos'][s['vehicles']['alive']!=0],s['hazards']['pos'],u['pos'][selected]]
    channels += [u['pos'][(u['kind']==1)&(u['ztype']==kind)] for kind in range(8)]
    assert len(channels)==len(GRID_CHANNELS)
    for points in channels:result.extend(np.log1p(histogram(points)).tolist())
    result += [float(name in hud['actions']) for name in PANEL_ACTIONS]
    assert len(result)==len(EXTRA_LABELS)
    if not np.isfinite(result).all():raise RuntimeError('Nonfinite mechanics observation')
    return list(map(float,result))


class Mechanics:
    def __init__(self,env):
        self.env=env;self.controls=Controls(env);self.reader=NativeState(env)

    def refresh(self,st):
        e=self.env;c=self.controls;s=self.reader.snapshot()
        if e.scalar(0x6553d4,'<f') or e.scalar(0x6553d8,'<f'):
            raise RuntimeError('Policy projection requires top-down camera')
        hud=read_panel(e);roster=c.planning_roster();perks=c.perks()
        legal=e.geometry_legal() if st['planning'] else False
        total=e.scalar(0x659310,'<q');covered=e.scalar(0x659308,'<q')
        camera=s['camera'];p=lambda pts:project(pts,camera,e.cw,e.ch)
        spatial=features(p(s['units']['pos']),s['units']['kind'],
            p(s['buildings']['rect'].reshape(-1,2)).reshape(-1,4),[p(z) for z in s['zones']],e.cw,e.ch)
        st.update(grid=spatial['counts'],build_targets=spatial['build_targets'],native=s,hud=hud,
            planning_roster=roster,perks=perks,ready_legal=legal,
            mechanics_features=observation(s,roster,perks,hud,e.scalar(0x665160,'<B'),legal,
                covered/max(total,1),e.cw,e.ch))
        kinds=s['units']['kind'];defenders=(kinds>=2)&(kinds!=3)
        targets=dict(unit=s['units']['pos'][defenders],building=s['buildings']['center'],
            wall=(s['walls']['a']+s['walls']['b'])/2,gate=s['gates'],evac=s['evac']['a'],
            corner=np.concatenate(s['zones']) if s['zones'] else np.empty((0,2)))
        st['targets']={key:nearest_per_cell(p(pts),e.cw,e.ch) for key,pts in targets.items()}
        for slot in st.get('deck',[]):
            if slot['name']=='Heli':slot['alive']=bool(np.any(s['helicopters']['alive']))

    def execute(self,st,name,cell):
        e=self.env;c=self.controls;xy=(round(XF[cell%8]*e.cw),round(YF[cell//8]*e.ch))
        if name.startswith('equip_'):return c.equip_unit(name[6:].replace('clear','-'),cell)
        if name.startswith('perk_'):return c.equip_perk(name[5:].replace('clear','-'),cell)
        if name.startswith('panel_'):return c.panel_action(name[6:])
        if name.startswith('select_') and name[7:] in SELECTORS:
            return c.select(st['targets'][name[7:]][cell])
        if name=='select_add':return c.select(xy,additive=True)
        if name in DRAGS:
            if not st.get('gesture_anchor'):st['gesture_anchor']=(name,cell);return
            _,start=st.pop('gesture_anchor');point=(round(XF[start%8]*e.cw),round(YF[start//8]*e.ch))
            if name=='select_box':return c.select(point,xy)
            return c.gesture(point,xy,shift=name=='shift_drag_world')
        if name in ('move_selection','reaim_selection'):return c.move_selection(xy,reaim=name=='reaim_selection')
        if name=='arm_slot':return c.arm(*[(49,2),(50,3),(51,4),(52,5),(53,6),(54,7),(84,20)][cell])
        if name in ('click_world','right_click_world'):return c.gesture(xy,right=name=='right_click_world')
        if name in ('zone_begin','zone_corner'):return c.polygon_corner(xy,begin=name=='zone_begin')
        if name=='zone_finish':return c.polygon_finish()
        if name=='zone_back':return c.polygon_back()
        if name=='cancel_tool':st.pop('gesture_anchor',None);return c.cancel()
        if name=='refund_selection':return c.refund(xy)
        if name=='undo':return c.undo()
        if name in KEY_ACTIONS:return c.key_action(name)
        if name in ('zoom_in','zoom_out'):return c.zoom(1 if name=='zoom_in' else -1,xy)
        raise ValueError('Unimplemented mechanics action: '+name)
