"""Native observations and player gestures for the appended policy actions."""
import math

import numpy as np

from game_controls import Controls, KEY_ACTIONS, PickerNavigationError
from game_mechanics import UNITS, UNIT_IDS, PERKS
from native_hud import read_panel
from native_state import NativeState
from spatial import project, centers, features, inside_polygon, grid_bins, closest_indices, XF, YF
from spatial import overview_geometry, OVERVIEW_MAX_FILL, OVERVIEW_CENTER_TOLERANCE
from scripts.mechanic_contract import EXTRA_TOOLS, EXTRA_LABELS, GRID_CHANNELS, PANEL_ACTIONS, STATE_CHANNELS

PLACEMENTS = {2:'Garrison',3:'Mortar',4:'Napalm',5:'Nest',6:'Mine',7:'C4',8:'GasMortar'}
PLACEMENTS.update({72+EXTRA_TOOLS.index('place_'+name):name for name in UNITS
                   if 'place_'+name in EXTRA_TOOLS})
DRAGS = {'select_box','drag_world','shift_drag_world','drag_corner','drag_edge'}
SELECTORS = ('unit','building','wall','gate','evac','corner','helicopter','vehicle','medevac')
SPEED_TICKS = {'speed_half':1, 'speed_1':2, 'speed_2':4, 'speed_4':8}
NONSPATIAL = set(KEY_ACTIONS)-{'pan_up','pan_left','pan_down','pan_right'} | {
    'zone_finish','zone_back','cancel_tool','undo'} | {'panel_'+name for name in PANEL_ACTIONS}


def pan_room(projected,width,height):
    if len(projected)<3:return {}
    points=projected/np.array([width,height])
    fill, offset = overview_geometry(points)
    if fill <= OVERVIEW_MAX_FILL:
        x, y = np.where(np.abs(offset) > OVERVIEW_CENTER_TOLERANCE, offset, 0.)
        return dict(pan_left=-x, pan_right=x, pan_up=-y, pan_down=y)
    lo,hi=points.min(axis=0),points.max(axis=0)
    # Allow close inspection when zoomed in, while keeping the playable area in frame.
    top_left=np.array([.03,.025]);bottom_right=np.array([.97,.69])
    keep=.95*np.minimum(hi-lo,bottom_right-top_left)
    right,down=hi-top_left-keep
    left,up=bottom_right-lo-keep
    return dict(pan_left=left,pan_right=right,pan_up=up,pan_down=down)


def extra_masks(st):
    masks=np.zeros((len(EXTRA_TOOLS),48),dtype=np.float32)
    if st.get('dialog'):
        for name in ('dialog_confirm','dialog_cancel'):masks[EXTRA_TOOLS.index(name),0]=1
        return masks
    if 'native' not in st:return masks
    sel=st['native']['selection'];planning=st['planning'];polygon=len(sel['polygon'])
    selected=any(len(sel[k]) for k in ('units','zones','helicopters','evac')) or sel['gate']>=0
    for i,name in enumerate(EXTRA_TOOLS):
        mask=masks[i];mask[:]=st.get('world_cells',np.repeat(YF<.70,len(XF)))
        enabled=True
        if name.startswith('dialog_'):enabled=False
        elif name in ('place_click','place_paint'):enabled=planning
        elif name.startswith('place_'):
            enabled=planning and name[6:] in st['planning_roster']
            if name[6:] in ('Sniper','FireMortar','Railgun','Howitzer','MLRS'):
                mask *= [p is not None for p in st.get('build_targets',[None]*48)]
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
        elif name in ('corridor_wider','corridor_narrower'):enabled=planning
        elif name.startswith('pan_'):enabled=st.get('pan_room',{}).get(name,1.)>.018
        elif name in ('zoom_in','zoom_out'):enabled=not st.get('corridor_armed',False)
        elif name=='arm_slot':
            enabled=planning;mask[:]=0;mask[:7]=[n!='-' for n in st['planning_roster']]
        elif name in ('zone_begin','zone_corner','zone_finish','zone_back'):
            enabled=planning and (name=='zone_begin' or polygon>0)
            if name=='zone_finish':enabled=enabled and polygon>=3
        elif name in ('undo','drag_corner','drag_edge','insert_corner','remove_corner'):
            enabled=planning
            if name!='undo' and not st.get('gesture_anchor'):
                kind='corner' if name in ('drag_corner','remove_corner') else 'edge'
                mask *= [p is not None for p in st['targets'][kind]]
        elif name=='move_selection':
            u=st['native']['units']
            enabled=planning and (bool(np.any((u['kind']==2)&np.isin(u['id'],sel['units']))) or bool(len(sel['helicopters'])))
        elif name in ('officer_mode','officer_paint'):
            u=st['native']['units']
            enabled=planning and bool(np.any((u['kind']==2)&np.isin(u['id'],sel['units'])))
        elif name=='reaim_selection':
            enabled=planning and selected
        elif name=='refund_selection':enabled=planning or len(sel['evac'])>0
        elif name=='arm_detonation':enabled=not planning and bool(np.any(st['native']['units']['kind']==9))
        elif name in SPEED_TICKS:
            enabled=not planning and (st.get('paused') or st.get('speed_ticks')!=SPEED_TICKS[name])
        elif name=='pause_toggle':enabled=not planning
        if name in NONSPATIAL or name.startswith('pan_'):
            mask[:]=0;mask[0]=1
        if not enabled:mask[:]=0
    if planning:
        for tool, cell in st.get('picker_blocked', ()):
            if tool >= 72:
                masks[tool-72,cell] = 0
    if st.get('gesture_anchor'):
        active=st['gesture_anchor'][0]
        for i,name in enumerate(EXTRA_TOOLS):
            if name not in (active,'cancel_tool'):masks[i]=0
    return masks


def outside_panel(points, bounds):
    points=np.asarray(points).reshape(-1,2)
    if bounds is None:return np.ones(len(points),dtype=bool)
    left,top,right,bottom=bounds
    return ~((points[:,0]>=left)&(points[:,0]<=right)&
             (points[:,1]>=top)&(points[:,1]<=bottom))


def nearest_per_cell(points, width, height, bounds=None):
    points=np.asarray(points).reshape(-1,2)
    visible=((points[:,0]>=0)&(points[:,0]<width)&(points[:,1]>=.07*height)&(points[:,1]<.8*height))
    points=points[visible & outside_panel(points,bounds)]
    result=[None]*48
    if len(points):
        bins=grid_bins(points,width,height)
        for i in closest_indices(points,bins,centers(width,height)):
            result[bins[i]]=tuple(map(int,points[i]))
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


def observation(snapshot, roster, perks, hud, paint_mode, legal, land_fraction, width, height,
                gesture_anchor=None, armed=(0,0,0), paused=False, speed=2, dialog=False, evac_tool=(False,False,150.)):
    s=snapshot;sel=s['selection'];u=s['units'];maps=s['unit_maps']
    camera=s['camera'];g=lambda x:math.log1p(max(float(x),0))
    result=[camera[0]/10000,camera[1]/10000,camera[2]/8,float(paint_mode),float(legal),land_fraction]
    result += [g(len(sel[k])) for k in ('polygon','units','zones','helicopters','evac')]
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
            float(u['converting'][i]),*maps['boosts'].get(uid,[1.]*5)]
    result += detail
    def histogram(points):
        xy=project(points,camera,width,height)
        if not len(xy):return np.zeros(48)
        visible=((xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=.07*height)&(xy[:,1]<.8*height))
        return np.bincount(grid_bins(xy[visible],width,height),minlength=48)
    defenders=np.flatnonzero(u['kind']>=4)
    names=unit_names({key:u[key][defenders] for key in ('kind','id')},maps)
    channels=[u['pos'][defenders[names==name]] for name in UNITS if name not in ('Spikes','Oil')]
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
    result.extend(inside_polygon(centers(width,height),project(s['playarea'],camera,width,height)))
    result += [EXTRA_TOOLS.index(gesture_anchor[0])/128 if gesture_anchor else -1.,
               gesture_anchor[1]/48 if gesture_anchor else -1.,armed[0]/42,*armed[1:]]
    result += [float(paused),speed/8]
    codes=s['terrain']['codes']
    result += [*np.where(codes<0,-1.,codes/5),*s['terrain']['bridges']]
    bi=sel['building'];detail=[0.]*7
    if 0<=bi<len(buildings['center']):
        detail=[1.,buildings['class'][bi]/7,buildings['ability'][bi]/15,
            buildings['officer_kind'][bi]/2,buildings['damage'][bi]/max(buildings['max_hp'][bi],1),
            g(buildings['area'][bi]),float(int(buildings['height_packed'][bi])&65535)/1000]
    result += detail
    result += [float(v)/4 for v in maps['upgrades'].get(int(u['id'][indices[0]]),[0]*4)] if len(indices) else [0.]*4
    w=s['walls'];ev=s['evac'];he=s['helicopters'];ve=s['vehicles'];me=s['medevacs'];ha=s['hazards'];mo=s['mutations'];br=s['bridges']
    he=he[he['alive']!=0];ve=ve[ve['alive']!=0];me=me[me['alive']!=0]
    hp=s.get('wall_hp',[])
    wall_fraction=[float(np.mean(v))/max(float(w['full_hp'][i]),1) if len(v) else 0 for i,v in enumerate(hp)]
    breached=[float(np.mean(v<=0)) if len(v) else 0 for v in hp]
    log=lambda v:np.log1p(np.maximum(v,0))
    groups=[((w['a']+w['b'])/2,[wall_fraction,breached,w['level']/4,w['build_left']/60]),
        (ev['a'],[ev['half_width']*2/1000,ev['radius']/1000,ev['attract_r']/1000,ev['hold_suppressed']]),
        (he['pos'],[log(he['mag']),he['cooldown']/60,log(he['dmg']),he['leaving'],he['rearm_t']/60,
                    he['mode']/8,he['heli_target'][:,0]/10000,he['heli_target'][:,1]/10000]),
        (ve['pos'],[ve['kind']/4,log(ve['mag']),log(ve['dmg']),ve['returning'],ve['parked'],ve['rearm_t']/60,
                    ve['leaving'],log(ve['carried']),log(ve['landed']),ve['routing'],ve['plowing'],
                    ve['goal'][:,0]/10000,ve['goal'][:,1]/10000]),
        (me['pos'],[me['phase']/8,log(me['carried']),log(me['landed']),log(me['dmg']),me['ordered']]),
        (ha['pos'],[ha['kind']/8,ha['radius']/1000,ha['until']/600]),
        (mo['pos'],[np.ones(len(mo)),mo['radius']/1000,mo['start']/600,mo['until']/600,
                    log(mo['members']),mo['kind']/8]),
        (br['pos'],[np.ones(len(br['hp'])),np.maximum(br['hp'],0)/br['full'],log(br['full'])])]
    assert sum(len(values) for _,values in groups)==len(STATE_CHANNELS)
    for points,values in groups:
        xy=project(points,camera,width,height)
        visible=(xy[:,0]>=0)&(xy[:,0]<width)&(xy[:,1]>=.07*height)&(xy[:,1]<.8*height)
        bins=grid_bins(xy[visible],width,height)
        count=np.maximum(np.bincount(bins,minlength=48),1)
        for value in values:
            result.extend(np.bincount(bins,weights=np.asarray(value)[visible],minlength=48)/count)
    result += [float(dialog),float(evac_tool[0]),float(evac_tool[1]),evac_tool[2]/1000]
    for name in ('flags','green','burnt','oil'):
        result.extend(s['fire'][name]/(255 if name=='flags' else 1))
    assert len(result)==len(EXTRA_LABELS)
    finite = np.isfinite(result)
    if not finite.all():
        labels = ', '.join(EXTRA_LABELS[i] for i in np.flatnonzero(~finite)[:4])
        raise RuntimeError(f'Nonfinite mechanics observation: {labels}')
    return list(map(float,result))


class Mechanics:
    def __init__(self,env):
        self.env=env;self.controls=Controls(env);self.reader=NativeState(env)
        self.building_membership=None

    def building_in_playarea(self,buildings,playarea):
        previous=self.building_membership
        if previous is None or not np.array_equal(previous[0],buildings) or not np.array_equal(previous[1],playarea):
            self.building_membership=(buildings.copy(),playarea.copy(),inside_polygon(buildings,playarea))
        return self.building_membership[2]

    def refresh(self,st):
        e=self.env;c=self.controls;s=self.reader.snapshot()
        if e.scalar(0x6553d4,'<f') or e.scalar(0x6553d8,'<f'):
            raise RuntimeError('Policy projection requires top-down camera')
        st['dialog']=bool(e.scalar(0x667868,'<B'))
        active=bool(e.scalar(0x6651e0,'<B') or e.scalar(0x6651e2,'<B'))
        hold=bool(e.scalar(0x6651e1,'<B'))
        st['corridor_armed']=active and not hold
        hud=dict(actions={},valid=False) if st['dialog'] else read_panel(e)
        roster=c.planning_roster();perks=c.perks()
        bounds=hud.get('bounds')
        st['world_cells']=np.repeat(YF<.70,len(XF)) & outside_panel(centers(e.cw,e.ch),bounds)
        legal=e.geometry_legal() if st['planning'] else False
        total=e.scalar(0x659310,'<q');covered=e.scalar(0x659308,'<q')
        camera=s['camera'];p=lambda pts:project(pts,camera,e.cw,e.ch)
        spatial=features(p(s['units']['pos']),s['units']['kind'],
            p(s['buildings']['rect'].reshape(-1,2)).reshape(-1,4),[p(z) for z in s['zones']],e.cw,e.ch)
        paused=bool(e.scalar(0x665fa2,'<B'));speed=e.scalar(0x666868,'<q')
        st.update(grid=spatial['counts'],build_targets=spatial['build_targets'],native=s,hud=hud,
            paused=paused,speed_ticks=speed,
            planning_roster=roster,perks=perks,ready_legal=legal,
            mechanics_features=observation(s,roster,perks,hud,e.scalar(0x665160,'<B'),legal,
                covered/max(total,1),e.cw,e.ch,st.get('gesture_anchor'),
                [e.scalar(rva,'<B') for rva in (0x667060,0x65d2e1,0x65d309)],
                paused,speed,st['dialog'],
                (active and not hold,active and hold,e.scalar(0x6651ec,'<f'))))
        boundary=p(s['playarea'])
        st['pan_room']=pan_room(boundary,e.cw,e.ch)
        st['playarea_boundary']=boundary
        kinds=s['units']['kind'];defenders=(kinds>=2)&(kinds!=3)
        targets=dict(unit=s['units']['pos'][defenders],building=s['buildings']['center'],
            wall=(s['walls']['a']+s['walls']['b'])/2,gate=s['gates'],evac=s['evac']['a'],
            corner=np.concatenate(s['zones']) if s['zones'] else np.empty((0,2)),
            edge=np.concatenate([(z+np.roll(z,-1,axis=0))/2 for z in s['zones'] if len(z)>2])
                if any(len(z)>2 for z in s['zones']) else np.empty((0,2)),
            helicopter=s['helicopters']['pos'][s['helicopters']['alive']!=0],
            vehicle=s['vehicles']['pos'][s['vehicles']['alive']!=0],
            medevac=s['medevacs']['pos'][s['medevacs']['alive']!=0])
        st['targets']={key:nearest_per_cell(p(pts),e.cw,e.ch,bounds) for key,pts in targets.items()}
        b=s['buildings'];valid=(b['destroyed']==0)&self.building_in_playarea(b['center'],s['playarea'])
        st['build_targets']=nearest_per_cell(p(b['center'][valid]),e.cw,e.ch,bounds)
        rules=st.get('rules',{})
        height=(b['height_packed']&65535).astype(float)/10
        height=np.where(height>0,height,float(rules.get('building_unknown_height',9)))
        depth=np.minimum(b['rect'][:,2]-b['rect'][:,0],b['rect'][:,3]-b['rect'][:,1])
        topple=valid & (height>=float(rules.get('demolition_min_height',60))) & (
            height>=depth*float(rules.get('topple_slenderness',.6)))
        st['battle_targets']={19:nearest_per_cell(p(s['units']['pos'][kinds==6]),e.cw,e.ch,bounds),
                              24:nearest_per_cell(p(b['center'][topple]),e.cw,e.ch,bounds)}
        for slot in st.get('deck',[]):
            if slot['name']=='Heli':slot['alive']=bool(np.any(s['helicopters']['alive']))

    def execute(self,st,name,cell):
        e=self.env;c=self.controls;xy=(round(XF[cell%8]*e.cw),round(YF[cell//8]*e.ch))
        if name in ('corridor_wider','corridor_narrower'):
            if not st.get('corridor_armed'):c.arm(81,16)
            return c.zoom(1 if name=='corridor_wider' else -1,xy)
        if name.startswith('dialog_'):return c.dialog(name=='dialog_confirm')
        if name.startswith('equip_'):
            try:
                return c.equip_unit(name[6:].replace('clear','-'),cell)
            except PickerNavigationError:
                if c.planning_roster() != st['planning_roster']:
                    raise
                return False
        if name.startswith('perk_'):
            try:
                return c.equip_perk(name[5:].replace('clear','-'),cell)
            except PickerNavigationError:
                if c.perks() != st['perks']:
                    raise
                return False
        if name.startswith('panel_building_') and name.rsplit('_',1)[0]=='panel_building':
            ability=int(name.rsplit('_',1)[1])
            index=st['native']['selection']['building']
            before=st['native']['buildings']['ability']
            c.panel_action(name[6:])
            if 0<=index<len(before) and not before[index] and e.scalar(0x6593b0,'<q')-1==index:
                after=e.array(0x658f50,'u1')
                if index<len(after) and after[index]==ability:
                    return index,ability
            return None
        if name.startswith('panel_'):return c.panel_action(name[6:])
        if name.startswith('select_') and name[7:] in SELECTORS:
            return c.select(st['targets'][name[7:]][cell])
        if name=='select_add':return c.select(xy,additive=True)
        if name in DRAGS:
            if not st.get('gesture_anchor'):
                st['gesture_anchor']=(name,cell)
                if name in ('drag_corner','drag_edge'):
                    st['gesture_point']=st['targets'][name[5:]][cell]
                return
            _,start=st.pop('gesture_anchor');point=(round(XF[start%8]*e.cw),round(YF[start//8]*e.ch))
            if name in ('drag_corner','drag_edge'):
                point=st.pop('gesture_point');c.cancel()
                return c.drag_handles(point,xy)
            if name=='select_box':return c.select(point,xy)
            return c.gesture(point,xy,shift=name=='shift_drag_world')
        if name in ('insert_corner','remove_corner'):
            c.cancel()
            return c.gesture(st['targets']['edge' if name=='insert_corner' else 'corner'][cell],right=True)
        if name in ('move_selection','reaim_selection'):return c.move_selection(xy,reaim=name=='reaim_selection')
        if name=='arm_slot':return c.arm(*[(49,2),(50,3),(51,4),(52,5),(53,6),(54,7),(84,20)][cell])
        if name in ('click_world','right_click_world'):return c.gesture(xy,right=name=='right_click_world')
        if name in ('zone_begin','zone_corner'):return c.polygon_corner(xy,begin=name=='zone_begin')
        if name=='zone_finish':return c.polygon_finish()
        if name=='zone_back':return c.polygon_back()
        if name=='cancel_tool':
            st.pop('anchor',None);st.pop('gesture_anchor',None);st.pop('gesture_point',None);return c.cancel()
        if name=='refund_selection':return c.refund(xy)
        if name=='undo':return c.undo()
        if name.startswith('pan_'):
            return c.key_action(name,pan_hold=float(np.clip(st['pan_room'][name]*.65,.01,.15)))
        if name in KEY_ACTIONS:return c.key_action(name)
        if name in ('zoom_in','zoom_out'):return c.zoom(1 if name=='zoom_in' else -1,xy)
        raise ValueError('Unimplemented mechanics action: '+name)
