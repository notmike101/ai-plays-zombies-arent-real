"""Population search over planning sequences and battle targeting on real game copies."""
import argparse
import campaign_fitness as fitness
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
from itertools import chain
import json
import os
from pathlib import Path
from time import monotonic
import uuid

import numpy as np
import psutil
import torch

import local_agent as operator
import nn_play2 as tr
from nn_report import records
from spatial import project
import zar_boot


def matching(prefix):
    return [i for i, name in enumerate(tr.TOOLS) if name.startswith(prefix)]


# A proposal samples a family, a preferred member and spatial parameters.
# These groups balance the proposal distribution across differently sized menus.
FAMILIES = [sorted(tr.PLACEMENTS), [10, 15, 16, 17, 18, 9],
            matching('buy_'), matching('equip_'), matching('perk_'), list(range(tr.NU))]
CASTS = sorted(tr.U2ABILITY)
MISSILE = tr.ABILITY_U['Missile']
MISSILE_ROW = CASTS.index(MISSILE)
SELECT_BUILDING = tr.TOOLS.index('select_building')
BUILDING_SPECIALS = {name.removeprefix('panel_'):i for i,name in enumerate(tr.TOOLS)
                     if name.startswith('panel_building_') and name.rsplit('_',1)[1].isdigit()}
GRID_START = tr.INPUT_LABELS.index('Grid civilians cell 1 (log1p count)')
PAN = [tr.TOOLS.index('pan_'+name) for name in ('up','left','down','right')]
PAUSE = tr.TOOLS.index('pause_toggle')
PAUSED = tr.INPUT_LABELS.index('Simulation paused (0/1)')
READY_LEGAL = tr.INPUT_LABELS.index('READY land and budget legal (0/1)')
REPAIRS=[tr.TOOLS.index(name) for name in ('undo','refund_selection','cancel_tool','zone_back')]


def gene(rng):
    family = int(rng.integers(len(FAMILIES)))
    return dict(family=family, tool=int(rng.choice(FAMILIES[family])),
                duration=int(rng.integers(2, 8)), x=int(rng.integers(8)),
                y=int(rng.integers(5)), dx=int(rng.integers(-2, 3)),
                dy=int(rng.integers(-2, 3)), weights=rng.normal(0, 1, 5).tolist())


def random_team(rng):
    return dict(plan=[gene(rng) for _ in range(int(rng.integers(2, 7)))],
                battle=rng.normal(0, 1, (len(CASTS), 5)).tolist(),
                cast_bias=rng.uniform(-1, 7, len(CASTS)).tolist(),
                idle_bias=float(rng.uniform(-1, 3)),
                camera_pause=rng.normal(0,2,6).tolist(),blocked_tool=int(rng.choice(REPAIRS)))


def loadout_candidate(parent,rng):
    candidate=deepcopy(parent)
    pick=gene(rng)
    pick.update(family=2,tool=int(rng.choice(FAMILIES[2])),duration=1)
    candidate['plan'].insert(0,pick)
    if 'blocked_tool' not in candidate:candidate['blocked_tool']=int(rng.choice(REPAIRS))
    return candidate


def l1_candidate(parent,rng):
    if not parent.get('refuge'):return offspring(parent,parent,rng)
    # Isolate the change in initial protection from changes in battle behavior.
    child=deepcopy(parent)
    scale=child['refuge']['scale']
    choices=[v for v in (.8,1.,1.15,1.3,1.45) if abs(v-scale)>.05]
    child['refuge']['scale']=float(rng.choice(choices))
    return child


def cast_candidate(trial,rng):
    levels=trial.get('levels',[])
    if not levels or not trial.get('team'):return None
    first=levels[0]
    if first.get('start_kind')!='fresh' or first['stage']!=1:return None
    actions=first.get('battle_actions',{})
    if actions.get('cast_available',0)<10 or actions.get('cast_sampled')!=0:return None
    child=deepcopy(trial['team'])
    child['cast_timing']=[float(rng.uniform(.5,7.)),float(rng.uniform(.5,6.))]
    return child


def vary_layout(layout,rng):
    if not layout:return
    index=int(rng.integers(len(layout)))
    move=rng.choice(('reorder','translate','duplicate','remove','prioritize','thin','scale_zone'))
    if move=='scale_zone':
        zones=[item for item in layout if item['kind']=='zone']
        if zones:
            item=zones[int(rng.integers(len(zones)))]
            points=np.asarray(item['points'])
            center=points.mean(axis=0)
            item['points']=(center+(points-center)*rng.uniform(.75,1.4)).tolist()
            item.pop('observed_cost',None)
    elif move=='reorder':
        layout.insert(int(rng.integers(len(layout))),layout.pop(index))
    elif move=='prioritize':
        kind=layout[index]['kind']
        layout.sort(key=lambda item:item['kind']!=kind)
    elif move=='thin':
        kind=layout[index]['kind']
        positions=[i for i,item in enumerate(layout) if item['kind']==kind]
        if len(positions)>1:
            count=int(rng.integers(1,len(positions)))
            for i in sorted(rng.choice(positions,count,replace=False),reverse=True):layout.pop(i)
    elif move=='remove':
        if len(layout)>1:layout.pop(index)
    else:
        item=deepcopy(layout[index])
        span=np.ptp(np.concatenate([a['points'] for a in layout]),axis=0)
        offset=rng.normal(size=2)*np.maximum(1.,span*.025)
        item['points']=(np.asarray(item['points'])+offset).tolist()
        item.pop('observed_cost',None)
        if move=='translate':layout[index]=item
        else:layout.insert(index+1,item)


def offspring(parent, donor, rng, stage=1):
    child = deepcopy(parent)
    if stage>1:
        layout=child.get('later_layouts',{}).get(str(stage),[])
        vary_layout(layout,rng)
        params=child.setdefault('stage_battle',{}).setdefault(str(stage),{})
        params['blocked_tool']=int(rng.choice(REPAIRS))
        for key in ('battle','cast_bias','camera_pause'):
            base=np.asarray(params.get(key,child.get(key,np.zeros(6))))
            params[key]=(base+rng.normal(0,.35,base.shape)).tolist()
        return child
    i = int(rng.integers(max(1,len(child['plan']))))
    replacement = deepcopy(donor['plan'][int(rng.integers(len(donor['plan'])))]) if donor['plan'] and rng.random()<.5 else gene(rng)
    if child['plan']:child['plan'][i]=replacement
    elif rng.random()<.5:child['plan'].append(replacement)
    if len(child['plan']) < 7 and rng.random()<.35:
        child['plan'].insert(i, gene(rng))
    if len(child['plan']) > 1 and rng.random()<.25:
        child['plan'].pop(i)
    for key in ('battle','cast_bias'):
        base = np.asarray((donor if rng.random()<.5 else parent)[key])
        child[key] = (base + rng.normal(0,.35,base.shape)).tolist()
    child['camera_pause']=(np.asarray(child.get('camera_pause',np.zeros(6)))+rng.normal(0,2,6)).tolist()
    child['blocked_tool']=int(rng.choice(REPAIRS))
    layout=child.get('layout')
    if layout:vary_layout(layout,rng)
    if 'refuge' in child:
        for key,lo,hi in [('scale',.65,1.5),('aspect',.4,2.5),('defense_weight',.01,.5)]:
            child['refuge'][key]=float(np.clip(child['refuge'][key]*np.exp(rng.normal(0,.2)),lo,hi))
    return child


class TeamPolicy(tr.PolicyNet2):
    def __init__(self, team, forecast=None):
        super().__init__()
        self.team = team
        self.steps = [(g, t) for g in team['plan'] for t in range(g['duration'])]
        self.index = 0
        self.coords = torch.arange(tr.NC)
        self.battle = torch.tensor(team['battle'])
        self.bias = torch.tensor(team['cast_bias'])
        self.cast_timing = team.get('cast_timing')
        self.shelter_defense = team.get('shelter_defense',0.)
        self.missile_reserve = team.get('missile_reserve',0.)
        self.missile_followup = team.get('missile_followup',0.)
        self.missile_in_flight = False
        self.missile_charges = 0.
        self.occupied_shelter = False
        self.special_probe = team.get('special_probe',0.)
        self.special_steps = 0
        self.inspected_buildings = set()
        self.special_tools = []
        self.special_cells = []
        self.shelter_perimeter = torch.zeros(tr.NC)
        self.cast_targets = torch.zeros((len(CASTS),tr.NC),dtype=torch.bool)
        self.camera_pause=torch.tensor(team.get('camera_pause',[0.]*6))
        self.predict = None if forecast is None else forecast.forward
        self.campaign_team_id=team_id(team)
        self.campaign_forecast_id=None
        self.campaign_forecast_parameters=0
        if forecast is not None:
            digest=hashlib.sha256()
            for parameter in forecast.parameters():
                digest.update(parameter.detach().cpu().numpy().tobytes())
                self.campaign_forecast_parameters+=parameter.numel()
            self.campaign_forecast_id=digest.hexdigest()[:16]

    def set_cast_targets(self, st, tools, cells, width, height):
        self.cast_targets.zero_()
        self.shelter_perimeter.zero_()
        self.missile_in_flight = False
        self.occupied_shelter = False
        self.missile_charges = 0.
        if st['planning'] or st.get('anchor') or st.get('dialog'):
            return
        boundary = st.get('playarea_boundary')
        if boundary is None:
            return
        centers = [tr.cell_of_px(cell,width,height) for cell in range(tr.NC)]
        inside = tr.inside_polygon(centers,boundary)
        if (self.shelter_defense or self.missile_reserve) and st.get('shelter') and st.get('native'):
            self.occupied_shelter = bool(st['shelter'].protected)
            camera = st['native']['camera']
            world = (np.asarray(centers)-[width/2,height/2])/[camera[2],-camera[2]]+camera[:2]
            self.shelter_perimeter = torch.from_numpy(st['shelter'].perimeter(world))
        for row,tool in enumerate(CASTS):
            if not tools[tool]:
                continue
            eligible = tr.cell_mask(st,tool,cells).astype(bool)
            if tool in st.get('battle_targets',{}):
                points = [tr.battle_point(st,tool,cell,width,height) for cell in range(tr.NC)]
                eligible &= tr.inside_polygon(points,boundary)
            else:
                eligible &= inside
            self.cast_targets[row] = torch.from_numpy(eligible)
        if (self.missile_followup or self.missile_reserve) and self.cast_targets[MISSILE_ROW].any():
            missile = next((slot for slot in st.get('deck',[]) if slot['name']=='Missile'),None)
            if missile:
                self.missile_in_flight = st['sim'] < missile.get('last_cast_t',-np.inf)+missile.get('flight',0.)
                if self.occupied_shelter:
                    self.missile_charges = missile['charges']

    def set_special_probe(self, st, width, height):
        self.special_tools = []
        self.special_cells = []
        if (not st['planning'] or not st.get('native') or self.special_steps>=6
                or self.index<len(self.steps) or st.get('anchor') or st.get('gesture_anchor')):
            return
        native = st['native']
        if not native['zones']:
            return
        self.special_steps += 1
        selected = native['selection']['building']
        if selected>=0:
            self.inspected_buildings.add(selected)
        self.special_tools = [BUILDING_SPECIALS[key] for key in st['hud']['actions'] if key in BUILDING_SPECIALS]
        if not self.special_tools:
            buildings = native['buildings']
            viable = np.flatnonzero((buildings['class']>0)&(buildings['destroyed']==0)&(buildings['ability']==0))
            viable = [i for i in viable if i not in self.inspected_buildings]
            if viable and native['zones']:
                points = project(buildings['center'][viable],native['camera'],width,height).astype(int)
                candidates = {tuple(point):i for point,i in zip(points,viable)}
                for cell,point in enumerate(st['targets']['building']):
                    index = candidates.get(point)
                    if index is None:
                        continue
                    left,bottom,right,top = buildings['rect'][index]
                    corners = [(left,bottom),(left,top),(right,bottom),(right,top)]
                    if any(tr.inside_polygon(corners,zone).all() for zone in native['zones']):
                        self.special_cells.append(cell)

    def forward(self, x, h=None):
        tools, cells, value, h = super().forward(x, h)
        grid = x[0,0,GRID_START:GRID_START+5*tr.NC].reshape(5,tr.NC)
        cells = cells.reshape(tr.NU,tr.NC)
        if x[0,0,tr.PLANNING_INDEX]:
            if self.index < len(self.steps):
                g, t = self.steps[self.index]
                tools[..., FAMILIES[g['family']]] += 5
                tools[..., g['tool']] += 7
                px, py = (g['x']+t*g['dx'])%8, (g['y']+t*g['dy'])%5
                distance = (self.coords%8-px).abs()+(self.coords//8-py).abs()
                cells = cells + torch.tensor(g['weights']) @ grid - distance
                self.index += 1
            else:
                tools[...,tr.TOOLS.index('ready')] += 15
                if self.special_tools:
                    tools[...,self.special_tools] += self.special_probe
                elif self.special_cells:
                    tools[...,SELECT_BUILDING] += self.special_probe
                    cells[SELECT_BUILDING,self.special_cells] += self.special_probe
                if 'blocked_tool' in self.team and not x[0,0,READY_LEGAL]:
                    tools[...,self.team['blocked_tool']]+=12
        else:
            tools[...,PAN]+=self.camera_pause[:4]
            tools[...,PAUSE]+=self.camera_pause[4+int(x[0,0,PAUSED].item()!=0)]
            if self.predict is not None:
                future=self.predict(grid[:3].reshape(1,3,6,8)).clamp_min(0).reshape(2,tr.NC)
                grid=torch.cat((future,grid[2:]))
            tools[..., CASTS] += self.bias
            if self.cast_timing is not None:
                gain, threshold = self.cast_timing
                demand = grid[1] - .75*grid[0] - threshold
                defense = self.shelter_defense*self.shelter_perimeter*(grid[1]/3).tanh()
                demand = demand+defense
                if self.shelter_defense:
                    cells[CASTS] += defense*self.cast_targets
                best = demand.expand_as(self.cast_targets).masked_fill(~self.cast_targets,-torch.inf).amax(dim=-1)
                tools[...,CASTS] += gain*torch.where(self.cast_targets.any(dim=-1), best.tanh(), 0.)
            if self.missile_in_flight:
                tools[...,MISSILE] -= self.missile_followup
            if self.missile_charges>0:
                pressure = self.shelter_perimeter*(grid[1]/3).tanh()
                legal_pressure = pressure*self.cast_targets[MISSILE_ROW]
                tools[...,MISSILE] -= self.missile_reserve*(1.-legal_pressure.max())/self.missile_charges
                cells[MISSILE] += self.missile_reserve*legal_pressure
            tools[...,tr.TOOLS.index('wait')] += self.team['idle_bias']
            cells[CASTS] += self.battle @ grid
        return tools, cells.reshape(1,1,-1), value, h


def score(row):
    # Retain official outcomes first. Failed boards get a search gradient from
    # simulated survival time. A paused wall-clock minute adds zero area.
    last = area = 0.
    for sim, civ, *_ in row['trail']:
        stop = min(120., max(last, sim))
        area += (stop-last)*min(1., max(0., civ/row['civ0']))
        last = stop
    return [int(bool(row['advance'])),int(bool(row['win'])),
            float(row['saved_frac'] or 0.) if row['win'] else 0.,area/120.]


def rollout(job, retries=0, start_stage=1, *, training=False, observe=False, observer_interval=.2,
            practice_retry=False, allow_progression=False, capture_shadow=False, fixed_speed=None):
    timing = {'started': monotonic()}
    if start_stage>1 and not allow_progression:
        raise ValueError('Later-stage starts require explicit campaign progression')
    copy, weights, team, seed, *forecast_path = job
    forecast=None
    if forecast_path:
        from crowd_forecast import CrowdForecast
        forecast=CrowdForecast().eval()
        forecast.load_state_dict(torch.load(forecast_path[0],weights_only=True))
    destination=('campaign','continue' if start_stage>1 else 'stage1')
    env=None
    levels=[]
    result=dict(copy=copy,seed=seed,levels=levels,timing=timing)
    stage,attempt=start_stage,0
    try:
        env=zar_boot.boot(operator.owned_copy(copy),destination,discard_dump_states=True)
        timing['board_ready'] = monotonic()
        layout_receipts=[]
        while stage <= 5:
            layout = (team or {}).get('layout',[]) if stage==1 else (team or {}).get('later_layouts',{}).get(str(stage),[])
            receipts=[]
            refuge=None
            relocation=None
            if layout or start_stage>1:
                env.to_planning()
                board=env.dump()
                if not board or not board['where']['stage'].startswith(f'{stage-1} '):
                    raise RuntimeError(f'Expected live Boston stage {stage}')
            if layout:
                from layout_memory import apply_layout, remaining_layout, BUILDINGS
                from native_state import VEC
                origin=np.array([env.scalar(r,'<f') for r in (0x665358,0x66535c)])
                boundary=env.array(0x6652e0,VEC,limit=10000)+origin
                if stage==1 and team.get('refuge'):
                    from layout_memory import fit_refuge
                    points=env.array(0x650280,VEC)
                    kinds=env.array(0x6502d0,'u1')
                    if len(points)!=len(kinds):raise RuntimeError('Inconsistent planning population')
                    layout,refuge=fit_refuge(layout,points[kinds==0]+origin,boundary,team['refuge'])
                if stage==1 and attempt==0 and team.get('garrison_relocation') is not None:
                    from layout_memory import relocate_garrison
                    points=env.array(0x658d98,VEC)+origin
                    layout,relocation=relocate_garrison(layout,points,team['garrison_relocation'])
                occupied=[unit for kind,unit in BUILDINGS.items() if f'board {kind} = ' in board['_text']]
                receipts=apply_layout(env,remaining_layout(layout,board),occupied,boundary=boundary)
                if stage==1 and attempt==0:layout_receipts=receipts
            active={**team,**team.get('stage_battle',{}).get(str(stage),{})} if team else None
            start_kind='carry' if attempt else ('fresh' if stage==1 else
                                                'continue' if stage==start_stage else 'next_level')
            options=dict(start_kind=start_kind,seed=seed,record_layout=bool(layout),greedy=True,
                         allow_progression=allow_progression, observer_interval=observer_interval)
            if training:options['paused_seconds']=45
            if capture_shadow:options['capture_shadow']=True
            if fixed_speed:options['fixed_speed']=fixed_speed
            episode_started = monotonic()
            row = tr.run_episode((env.pid,weights,False,f'search/{seed}/L{stage}/a{attempt}',options),
                                 policy_factory=(lambda:TeamPolicy(active,forecast)) if active else None,
                                 telemetry=observe)
            episode_finished = monotonic()
            if not tr.valid_trajectory(row):
                result.update(failed_stage=stage,failed_attempt=attempt,error=row.get('err','invalid trajectory'))
                break
            levels.append(dict(stage=row['scenario'],end=row['end'],saved=row['saved_frac'],
                               win=row['win'],advance=row['advance'],campaign=row['campaign'],
                               attempt=attempt,start_kind=start_kind,
                               timing=dict(started=episode_started, battle_started=row.get('battle_started'),
                                           finished=episode_finished),
                               refuge=refuge,garrison_relocation=relocation,
                               outbreak=row.get('outbreak'),
                               timeout_reason=row.get('timeout_reason'),planning_blockers=row.get('planning_blockers'),
                               unmatched_layout=remaining_layout(layout,{'_text':row['layout_text']}) if layout else [],
                               layout_receipts=receipts,battle_actions=row['battle_actions'],
                               selected_placements=row.get('selected_placements',{}),
                               outside_playarea_actions=row.get('outside_playarea_actions',0)+
                                   sum(r.get('result')=='outside_playarea' for r in receipts),
                               playarea_cost=tr.OUTSIDE_PLAYAREA_COST/tr.SAVED_REWARD_SCALE,
                               outside_targets=row.get('outside_targets',{}),
                               reward_components=row.get('reward_components',{}),
                               shelter=row.get('shelter',{}),
                               special_activations=row.get('special_activations',{}),
                               special_objective=row.get('reward_components',{}).get('special_activation',0.)/tr.SAVED_REWARD_SCALE,
                               shelter_objective=sum(row.get('reward_components',{}).get(k,0.)
                                   for k in ('shelter','occupied_breach'))/tr.SAVED_REWARD_SCALE,
                               score=score(row),sim=row['sim'],board=row['board_id'],
                               actions=list(zip(row['us'],row['cs'])),log_started=row['log_started']))
            if capture_shadow and 'shadow' in row:
                levels[-1]['shadow'] = dict(row['shadow'], copy=copy,
                                             team=team_id(active) if active else None)
            if row['advance']:
                if not allow_progression or row['scenario']==row['board'].get('scenario_count'):break
                stage+=1
                attempt=0
            elif allow_progression and (stage>1 or (practice_retry and training and row['win'])) and attempt<retries and row['end'] in ('aborted','lost','won'):
                attempt+=1
            else:
                break
        result['layout_receipts']=layout_receipts
    except (RuntimeError,OSError,ValueError) as exc:
        result.update(failed_stage=stage,failed_attempt=attempt,error=str(exc))
    finally:
        if env is not None:
            try:zar_boot.stop(env)
            except psutil.TimeoutExpired as exc:
                result['cleanup_error']=str(exc)
                print('game exit unconfirmed',copy,env.pid,exc,flush=True)
        timing['finished'] = monotonic()
    return result


def team_id(team):
    return hashlib.sha256(json.dumps(team,sort_keys=True).encode()).hexdigest()[:16]


def checkpoint_team(record,base):
    """Only reviewed strategy fields may enter a public model bundle."""
    from layout_memory import BUILDINGS
    team=record['team']
    def fields(obj,required=(),optional=()):
        if not isinstance(obj,dict) or not set(required)<=obj.keys()<=set(required)|set(optional):
            raise ValueError('Unexpected campaign strategy fields')
    def numeric(value,shape):
        a=np.asarray(value)
        if a.shape!=shape or a.dtype.kind not in 'fiu' or not np.isfinite(a).all():
            raise ValueError('Invalid campaign strategy numbers')
    def battle(obj):
        for k,shape in [('battle',(len(CASTS),5)),('cast_bias',(len(CASTS),)),('camera_pause',(6,))]:
            if k in obj:numeric(obj[k],shape)
        if 'cast_timing' in obj:
            numeric(obj['cast_timing'],(2,))
            gain,threshold=obj['cast_timing']
            if not (0<=gain<=8 and 0<=threshold<=8):
                raise ValueError('Invalid campaign cast timing')
        if 'missile_followup' in obj:
            numeric(obj['missile_followup'],())
            if not 0<=obj['missile_followup']<=16:
                raise ValueError('Invalid missile follow-up weight')
        if 'missile_reserve' in obj:
            numeric(obj['missile_reserve'],())
            if not 0<=obj['missile_reserve']<=8:
                raise ValueError('Invalid missile reserve weight')
        if 'shelter_defense' in obj:
            numeric(obj['shelter_defense'],())
            if not 0<=obj['shelter_defense']<=8:
                raise ValueError('Invalid shelter defense weight')
        if 'special_probe' in obj:
            numeric(obj['special_probe'],())
            if not 0<=obj['special_probe']<=24:
                raise ValueError('Invalid special-building probe weight')
        if 'blocked_tool' in obj and (type(obj['blocked_tool'])!=int or obj['blocked_tool'] not in REPAIRS):
            raise ValueError('Invalid campaign recovery action')
    fields(team,('plan','battle','cast_bias','idle_bias'),('layout','later_layouts','stage_battle','camera_pause','blocked_tool','refuge','cast_timing','shelter_defense','special_probe','missile_reserve','garrison_relocation','missile_followup'))
    battle(team)
    numeric(team['idle_bias'],())
    if not isinstance(team['plan'],list) or len(team['plan'])>64:raise ValueError('Invalid campaign plan')
    for g in team['plan']:
        fields(g,('family','tool','duration','x','y','dx','dy','weights'))
        for k,low,high in [('family',0,len(FAMILIES)-1),('tool',0,tr.NU-1),('duration',1,60),
                           ('x',0,7),('y',0,4),('dx',-7,7),('dy',-5,5)]:
            if type(g[k])!=int or not low<=g[k]<=high:raise ValueError('Invalid campaign planning gene')
        numeric(g['weights'],(5,))
    for k in ('later_layouts','stage_battle'):fields(team.get(k,{}),optional=('2','3','4','5'))
    for override in team.get('stage_battle',{}).values():
        fields(override,optional=('battle','cast_bias','camera_pause','blocked_tool','cast_timing','shelter_defense','missile_reserve','missile_followup'))
        battle(override)
    if 'garrison_relocation' in team:
        numeric(team['garrison_relocation'],(2,))
        if any(type(value) is not int or not 0<=value<128 for value in team['garrison_relocation']):
            raise ValueError('Invalid garrison relocation')
    if 'refuge' in team:
        fields(team['refuge'],('scale','aspect','defense_weight'))
        for value in team['refuge'].values():numeric(value,())
        if min(team['refuge']['scale'],team['refuge']['aspect'])<=0:raise ValueError('Invalid refuge geometry')
    for layout in [team.get('layout',[]),*team.get('later_layouts',{}).values()]:
        if not isinstance(layout,list) or len(layout)>4096:raise ValueError('Invalid campaign layout')
        for a in layout:
            fields(a,('kind','points'),('observed_cost',))
            kind=a['kind']
            if kind not in (*BUILDINGS,'gate','zone','wall','hold','corridor'):raise ValueError('Unknown placement')
            n=len(a['points'])
            if not (3<=n<=128 if kind=='zone' else n==(2 if kind in ('wall','hold','corridor') else 1)):
                raise ValueError('Invalid placement geometry')
            numeric(a['points'],(n,2))
            if 'observed_cost' in a:
                numeric(a['observed_cost'],())
                if a['observed_cost']<0:raise ValueError('Invalid placement cost')
    if record['base']!=base or record['team_id']!=team_id(team):raise ValueError('Campaign policy identity mismatch')
    return dict(base=base,team_id=record['team_id'],team=team)


def restore_team(net,directory):
    if (directory/'champion.json').is_file():
        record=json.loads((directory/'champion.json').read_text())
        net.load_state_dict(torch.load(directory/'base.pt',weights_only=True))
    else:
        from checkpoints import verify_bundle
        record=verify_bundle(directory).get('campaign_team')
        if not record:raise ValueError('This checkpoint bundle has no campaign team')
        tr.load_pretrained(net,directory/'nn_policy4.pt')
    return checkpoint_team(record,tr.policy_id(net))['team']


def holdout_assignments(copies, weights, challenger, incumbent, seed, wave):
    jobs = []
    arms = {}
    for index,copy in enumerate(copies):
        candidate = (index+wave)%2==0
        team = challenger if candidate else incumbent
        jobs.append((copy,weights,team,seed+wave*len(copies)+index//2))
        arms[copy] = ('extra' if index>=2*(len(copies)//2) else
                      'candidate' if candidate else 'incumbent' if incumbent else 'gru')
    return jobs,arms


def shadow_variants(champion):
    timing = deepcopy(champion)
    targeting = deepcopy(champion)
    timing['cast_bias'][MISSILE_ROW] -= 3.
    targeting['battle'][MISSILE_ROW][0] -= 2.
    return {'control': champion, 'timing': timing, 'civilian_avoidance': targeting}


def completed_rollouts(pool,jobs,starts=None,retries=0,training=False, *, allow_progression=False,
                       capture_shadow=False, speeds=None):
    if starts is None:starts=[1]*len(jobs)
    primary = next((job for job in jobs if job[2]), jobs[0] if jobs else None)
    practice_copy=next((j[0] for j,stage in zip(jobs,starts) if training and j[2] and stage==1),None)
    futures={pool.submit(rollout,job,retries,stage,training=training,observe=True,
                         observer_interval=.2 if training and job is primary else 1.,
                         practice_retry=job[0]==practice_copy,allow_progression=allow_progression,
                         capture_shadow=capture_shadow,
                         fixed_speed=speeds[job[0]] if speeds else None):(job,stage)
             for job,stage in zip(jobs,starts,strict=True)}
    for future in as_completed(futures):
        job,stage=futures[future]
        try:result=future.result()
        except Exception as exc:result=dict(copy=job[0],seed=job[3],levels=[],error=str(exc),failed_stage=stage)
        yield job,stage,result


def budget_candidate(team,levels,prices=None):
    if not team:return None
    if prices is None:prices={}
    layouts={'1':team.get('layout',[]),**team.get('later_layouts',{})}
    def key(stage,action):
        points = [[float(x),float(y)] for x,y in action['points']]
        return json.dumps([stage,action['kind'],points],separators=(',',':'))
    for stage in levels:
        for receipt in stage.get('layout_receipts',[]):
            if receipt.get('after',0)>=0 or receipt['before']<=0:continue
            number=str(stage['stage'])
            layout=layouts.get(number,[])
            matches=[a for a in layout if a['kind']==receipt['kind'] and
                     ('world_points' not in receipt or a['points']==receipt['world_points'])]
            if len(matches)==1:
                where=key(number,matches[0])
                prices[where]=min(prices.get(where,float('inf')),receipt['before']-receipt['after'])
    changes=[(stage,i,prices[key(stage,a)]) for stage,layout in layouts.items() for i,a in enumerate(layout)
             if key(stage,a) in prices and a.get('observed_cost')!=prices[key(stage,a)]]
    if not changes:return None
    child=deepcopy(team)
    for stage,i,price in changes:
        layout=child['layout'] if stage=='1' else child['later_layouts'][stage]
        layout[i]=dict(layout[i],observed_cost=price)
    return child


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copies',nargs='+',required=True)
    parser.add_argument('--generations',type=int,default=10)
    parser.add_argument('--allow-progression',action='store_true',help='Explicitly allow Boston L2–L5')
    parser.add_argument('--seed',type=int,default=92851)
    parser.add_argument('--stage-retries','--later-retries',dest='later_retries',type=int,default=2,
                        help='Training retries on later stages and below-target first-stage wins')
    parser.add_argument('--seed-from',type=Path,help='Start with a previous search champion and its frozen GRU')
    parser.add_argument('--demonstration',type=Path,help='Seed candidates from a local Boston progress file')
    parser.add_argument('--compare-forecast',type=Path,help='Evaluate the same saved champion with and without its CNN forecast')
    parser.add_argument('--compare-shadow',action='store_true',
                        help='Capture fixed-plan missile preference comparisons without promotion')
    parser.add_argument('--compare-speed',action='store_true',help='Compare fixed stock 1x and 2x on fresh L1 boards')
    parser.add_argument('--capture-shadow',action='store_true',help='Record bounded crowd frames and confirmed stock spends for offline analysis')
    args=parser.parse_args()
    copies=args.copies
    if not 4<=len(copies)<=8 or len(set(copies))!=len(copies) or args.generations<1 or args.later_retries<0:
        parser.error('Use 4–8 distinct owned copies and positive generations')
    if args.compare_forecast and (not args.seed_from or len(copies)%2 or args.demonstration):
        parser.error('Forecast comparison requires a saved champion and paired copies')
    if args.compare_speed and (not args.seed_from or args.generations % 2 or args.demonstration
                               or args.allow_progression or args.compare_forecast):
        parser.error('Speed comparison requires a saved champion, an even number of waves and fresh L1 only')
    if args.compare_shadow and (not args.seed_from or len(copies) != 6 or args.generations % 3
                                or args.demonstration or args.allow_progression
                                or args.compare_forecast or args.compare_speed):
        parser.error('Shadow comparison requires a saved champion, six copies, a multiple of three waves and fresh L1 only')
    with operator.training_lock(operator.LOCK):
        ancestors=[p.pid for p in psutil.Process().parents()]
        for copy in copies:
            operator.require_idle(operator.inventory(),copy,os.getpid(),ancestor_pids=ancestors)
            report=operator.preflight(copy)
            if not report['ok']:raise RuntimeError(report['errors'])
        operator.limit_resources(len(copies))
        rng=np.random.default_rng(args.seed)
        net=tr.PolicyNet2()
        prior=None
        if args.seed_from:
            prior=restore_team(net,args.seed_from)
        else:
            tr.load_pretrained(net,tr.MODEL)
        weights=net.state_dict()
        directory=operator.ROOT/'analysis'/('coverage-team-'+uuid.uuid4().hex[:10])
        directory.mkdir()
        torch.save(weights,directory/'base.pt')
        print(directory,'base',tr.policy_id(net),flush=True)
        print('Campaign scope:', 'Boston L1 to L5' if args.allow_progression else 'Boston L1 only', flush=True)
        if args.compare_shadow:
            variants = shadow_variants(prior)
            (directory/'comparison-teams.json').write_text(json.dumps(variants))
            arms = list(variants)
            with ProcessPoolExecutor(len(copies)) as pool:
                for wave in range(args.generations):
                    assignments = {copy: arms[(i + wave) % len(arms)] for i, copy in enumerate(copies)}
                    jobs = [(copy, weights, variants[assignments[copy]], args.seed + wave*len(copies) + i//3)
                            for i, copy in enumerate(copies)]
                    for job, _, result in completed_rollouts(pool, jobs, capture_shadow=True):
                        result.update(wave=wave, arm=assignments[job[0]], team_id=team_id(job[2]))
                        with (directory/'shadow-comparison.jsonl').open('a') as f:
                            f.write(json.dumps(result)+'\n')
            return
        population=[random_team(rng) for _ in copies[1:]]
        if prior:
            population[0]=prior
            population[1]=offspring(prior,prior,rng)
        if args.demonstration:
            from layout_memory import demonstrations
            stages=demonstrations(args.demonstration)
            layout=stages[1]
            for i in range(1,len(population)):
                # Explore execution order: progress files store the finished layout.
                candidate=population[i]
                if prior and prior.get('layout'):
                    candidate=population[i]=deepcopy(prior)
                candidate['plan']=[]
                if prior and prior.get('layout'):
                    candidate=population[i]=loadout_candidate(candidate,rng)
                    candidate['camera_pause']=(np.asarray(candidate.get('camera_pause',np.zeros(6)))+rng.normal(0,2,6)).tolist()
                if not (prior and prior.get('layout')):
                    candidate['layout']=deepcopy(layout)
                candidate['later_layouts']={str(k):deepcopy(v) for k,v in stages.items() if k>1}
                vary = list(candidate['later_layouts'].values()) if prior and prior.get('layout') else [candidate['layout']]
                for actions in vary:
                    if i==2:actions.sort(key=lambda item:item['kind']=='garrison')
                    if i>2:rng.shuffle(actions)
            if prior and prior.get('layout'):
                population[1]['refuge']=dict(scale=1.,aspect=float(rng.uniform(.7,1.5)),
                                             defense_weight=float(rng.uniform(.08,.22)))
        base=tr.policy_id(net)
        view_revision='playable-overview-v3-bounded-targets-shelter-v2-specials-v1-retries-v1'
        evidence={}
        prices={}
        if args.seed_from and (args.seed_from/'fitness.json').exists():
            ledger=json.loads((args.seed_from/'fitness.json').read_text())
            if ledger['base']!=base:raise ValueError('Campaign fitness base mismatch')
            if ledger.get('view_revision')==view_revision:evidence=ledger['evidence']
            prices=ledger.get('layout_prices',{})
        if args.seed_from and not (args.compare_forecast or args.compare_speed):
            best_budget=None
            paths=[args.seed_from/name for name in ('trials.jsonl','extra-trials.jsonl')]
            for trial in chain.from_iterable(records(path) for path in paths if path.is_file()):
                if trial.get('view_revision')==view_revision:fitness.record(evidence,trial)
                if not trial.get('levels'):continue
                candidate=budget_candidate(trial.get('team'),trial['levels'],prices)
                if candidate:
                    rank=(max(r['stage'] for r in trial['levels']),team_id(candidate))
                    if best_budget is None or rank>best_budget:
                        best_budget,population[-1]=rank,candidate
            for i in range(1,len(population)):
                population[i]=budget_candidate(population[i],[],prices) or population[i]
        if prior and not (args.compare_forecast or args.compare_speed):
            previous=args.seed_from/'provisional.json'
            if previous.is_file():
                saved=checkpoint_team(json.loads(previous.read_text()),base)['team']
                if saved!=prior:population[-1]=saved
            weight = 10. if prior.get('missile_followup')!=10. else float(rng.uniform(6,14))
            population[1]=dict(deepcopy(prior),missile_followup=weight)
        archive={}
        deepest={}
        incumbent=prior
        continued={}
        require_fresh=set()
        with ProcessPoolExecutor(len(copies)) as pool:
            if args.compare_speed:
                for wave in range(args.generations):
                    speed = ('speed_1', 'speed_2')[(wave + wave // 2) % 2]
                    jobs = [(copy, weights, prior, args.seed + (wave // 2) * len(copies) + i)
                            for i, copy in enumerate(copies)]
                    speeds = dict.fromkeys(copies, speed)
                    for job, _, result in completed_rollouts(pool, jobs, speeds=speeds,
                                                            capture_shadow=args.capture_shadow):
                        result.update(wave=wave, fixed_speed=speed, team_id=team_id(prior))
                        with (directory/'speed-comparison.jsonl').open('a') as f:
                            f.write(json.dumps(result)+'\n')
                return
            if args.compare_forecast:
                contender=loadout_candidate(prior,rng)
                (directory/'comparison-team.json').write_text(json.dumps(contender))
                for swap in range(2):
                    jobs=[]
                    for i,copy in enumerate(copies):
                        job=(copy,weights,contender,args.seed+swap*len(copies)+i//2)
                        jobs.append(job+(args.compare_forecast,) if (i+swap)%2 else job)
                    for job,_,result in completed_rollouts(pool,jobs,allow_progression=args.allow_progression,
                                                           capture_shadow=args.capture_shadow):
                        result.update(cnn=len(job)==5,team_id=team_id(contender))
                        with (directory/'forecast-comparison.jsonl').open('a') as f:
                            f.write(json.dumps(result)+'\n')
                        print('cnn',result['cnn'],result.get('error'),[(r['end'],r['saved']) for r in result['levels']],flush=True)
                return
            for generation in range(args.generations):
                if generation==0:population.append(None)  # Repeat the control in the held-out block.
                rng.shuffle(population)
                jobs=[(copy,weights,team,args.seed+generation*len(copies)+i)
                      for i,(copy,team) in enumerate(zip(copies,population))]
                starts=[1]*len(jobs)
                for i,(copy,_,team,_) in enumerate(jobs):
                    stage=continued.get(copy)
                    if (stage and team and team_id(team) not in require_fresh and str(stage) in team.get('later_layouts',{})
                            and starts.count(1)>len(jobs)//2+1):
                        starts[i]=stage
                continued={}
                require_fresh.clear()
                practice=[]
                affordable=[]
                cast_probes={}
                valid_candidates=0
                for job,start_stage,result in completed_rollouts(pool,jobs,starts,args.later_retries,training=True,
                        allow_progression=args.allow_progression,capture_shadow=args.capture_shadow):
                    team=job[2]
                    key=team_id(team) if team else 'control'
                    result.update(view_revision=view_revision,generation=generation,team_id=key,team=team,start_stage=start_stage)
                    with (directory/'trials.jsonl').open('a') as f:
                        f.write(json.dumps(result)+'\n')
                    if 'error' in result:
                        print('failed',job[0],result['error'],flush=True)
                        if not result.get('levels'):continue
                    levels=result['levels']
                    candidate=budget_candidate(team,levels,prices)
                    if candidate:affordable.append((max(r['stage'] for r in levels),candidate))
                    last=levels[-1]
                    stopped_in_planning=last.get('timeout_reason')=='planning_decisions'
                    if last['stage']>1 and (last['end'] in ('aborted','lost','won') or stopped_in_planning) and not last['advance']:
                        continued[job[0]]=last['stage']
                    if start_stage>1:
                        practice.append((start_stage,max(r['score'] for r in levels if r['stage']==start_stage),team))
                        print('practice',key,[(r['stage'],r['end'],r['saved']) for r in levels],flush=True)
                        continue
                    if team:
                        valid_candidates+=1
                        archive[key]=team
                        deepest[key]=max(deepest.get(key,1),levels[-1]['stage'],result.get('failed_stage',1))
                        fitness.record(evidence,result)
                        probe=cast_candidate(result,rng)
                        if probe:cast_probes[key]=probe
                    print(generation,key,[(r['stage'],r['end'],r['saved'],round(r['sim'],1)) for r in levels],flush=True)
                if not valid_candidates:raise RuntimeError('No valid candidates this generation; inspect trials')
                ranked=sorted(archive,key=lambda k:fitness.ranking(evidence,archive[k]),reverse=True)
                def l1_rank(key):
                    outcomes=fitness.stats(evidence,archive[key],1)
                    return outcomes['lower'],outcomes['objective']
                l1_ranked=sorted(archive,key=l1_rank,reverse=True)
                leader=archive[l1_ranked[0]]
                report=fitness.stats(evidence,leader,1)
                print('fresh L1 leader',team_id(leader),report,flush=True)
                for filename,data in [('fitness',dict(base=base,view_revision=view_revision,evidence=evidence,layout_prices=prices)),
                                      ('provisional',dict(team=leader,team_id=team_id(leader),base=base))]:
                    temp=directory/(filename+'.tmp')
                    temp.write_text(json.dumps(data))
                    temp.replace(directory/(filename+'.json'))
                if incumbent:
                    stages=[fitness.stats(evidence,incumbent,i) for i in range(1,6)]
                    champion=dict(team_id=team_id(incumbent),team=incumbent,base=base,
                                  generation=generation,trials=stages[0]['starts'],fresh_stages=stages)
                    temp=directory/'champion.tmp'
                    temp.write_text(json.dumps(champion))
                    temp.replace(directory/'champion.json')
                # Replicate the leader on independent boards and reserve one L1 mutation.
                population=[leader,incumbent or leader]
                require_fresh.update(team_id(t) for t in population)
                population.append(l1_candidate(leader,rng) if generation%2==0 else offspring(leader,leader,rng,stage=1))
                repeat = fitness.replication_candidate(evidence, (archive[k] for k in l1_ranked), population)
                if repeat and len(copies)>=6:
                    population.append(repeat)
                    require_fresh.add(team_id(repeat))
                probe=next((cast_probes[k] for k in l1_ranked if k in cast_probes),None)
                if generation%2==0:
                    defender=deepcopy(incumbent or leader)
                    if generation%4==0:
                        defender['missile_followup']=float(rng.uniform(6,14))
                    else:
                        defender['missile_reserve']=float(rng.uniform(2,6))
                    population.append(defender)
                elif generation%4==1 and leader.get('layout'):
                    population.append(dict(deepcopy(leader),garrison_relocation=rng.integers(0,16,size=2).tolist()))
                elif generation%4==3:
                    population.append(dict(deepcopy(leader),special_probe=float(rng.uniform(16,24))))
                elif probe and not practice:population.append(probe)
                elif practice:
                    specialist=max(practice,key=lambda entry:(entry[0],entry[1],team_id(entry[2])))[2]
                    population.append(specialist)
                    require_fresh.add(team_id(specialist))
                elif affordable:
                    population.append(max(affordable,key=lambda entry:(entry[0],team_id(entry[1])))[1])
                if len(population)<len(copies):
                    population.append(loadout_candidate(leader,rng))
                while len(population)<len(copies):
                    stage_parent=ranked[0]
                    stage=deepest[stage_parent] if len(population)%2 else 1
                    key=stage_parent if stage>1 else l1_ranked[int(rng.integers(min(2,len(l1_ranked))))]
                    child=offspring(archive[key],leader,rng,stage=stage)
                    population.append(budget_candidate(child,[],prices) or child)
            # Frozen arms on fresh boards. The game chooses its own outbreak seeds.
            distinct=[archive[k] for k in ranked if archive[k]!=prior and
                      (args.allow_progression or prior is None or
                       fitness.prefix_id(archive[k],1)!=fitness.prefix_id(prior,1))]
            qualified=[t for t in distinct if fitness.promote(evidence,t,prior) is t]
            challenger=next(iter(qualified or distinct),leader)
            stage=next((i for i in range(1,6 if args.allow_progression else 2) if prior is None or
                        fitness.prefix_id(challenger,i)!=fitness.prefix_id(prior,i)),1)
            pairs = len(copies)//2
            waves = (6+pairs-1)//pairs if challenger in qualified else 1
            seed = args.seed+(args.generations+1)*len(copies)
            evaluation=[]
            for wave in range(waves):
                jobs,arms = holdout_assignments(copies,weights,challenger,prior,seed,wave)
                for job,_,result in completed_rollouts(pool,jobs,allow_progression=args.allow_progression,
                                                       capture_shadow=args.capture_shadow):
                    result.update(arm=arms[job[0]],team_id=team_id(job[2]) if job[2] else 'control',
                                  holdout_round=wave)
                    evaluation.append(result)
                    with (directory/'holdout.jsonl').open('a') as f:
                        f.write(json.dumps(result)+'\n')
            if challenger in qualified and fitness.holdout_passed(evaluation,pairs*waves,stage):
                stages=[fitness.stats(evidence,challenger,i) for i in range(1,6)]
                record=dict(team_id=team_id(challenger),team=challenger,base=base,generation=generation,
                            trials=stages[0]['starts'],fresh_stages=stages,holdout_stage=stage,holdout_opponent=team_id(prior) if prior else 'gru')
                temp=directory/'champion.tmp'
                temp.write_text(json.dumps(record))
                temp.replace(directory/'champion.json')
                print('promoted after fresh holdout',record['team_id'],flush=True)



if __name__=='__main__':
    main()
