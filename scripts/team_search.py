"""Population search over planning sequences and battle targeting on real game copies."""
import argparse
import campaign_fitness as fitness
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import uuid

import numpy as np
import psutil
import torch

import local_agent as operator
import nn_play2 as tr
import zar_boot


def matching(prefix):
    return [i for i, name in enumerate(tr.TOOLS) if name.startswith(prefix)]


# A proposal samples a family, a preferred member and spatial parameters.
# These groups balance the proposal distribution across differently sized menus.
FAMILIES = [sorted(tr.PLACEMENTS), [10, 15, 16, 17, 18, 9],
            matching('buy_'), matching('equip_'), matching('perk_'), list(range(tr.NU))]
CASTS = sorted(tr.U2ABILITY)
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
    child['cast_timing']=[float(rng.uniform(2,7)),float(rng.uniform(.5,3.))]
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
        if st['planning'] or st.get('anchor') or st.get('dialog'):
            return
        boundary = st.get('playarea_boundary')
        if boundary is None:
            return
        centers = [tr.cell_of_px(cell,width,height) for cell in range(tr.NC)]
        inside = tr.inside_polygon(centers,boundary)
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
                best = demand.expand_as(self.cast_targets).masked_fill(~self.cast_targets,-torch.inf).amax(dim=-1)
                tools[...,CASTS] += gain*torch.where(self.cast_targets.any(dim=-1), best.tanh(), 0.)
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


def rollout(job, retries=0, start_stage=1, *, training=False, observe=False, practice_retry=False):
    copy, weights, team, seed, *forecast_path = job
    forecast=None
    if forecast_path:
        from crowd_forecast import CrowdForecast
        forecast=CrowdForecast().eval()
        forecast.load_state_dict(torch.load(forecast_path[0],weights_only=True))
    destination=('campaign','continue' if start_stage>1 else 'stage1')
    env=None
    levels=[]
    result=dict(copy=copy,seed=seed,levels=levels)
    stage,attempt=start_stage,0
    try:
        env=zar_boot.boot(operator.owned_copy(copy),destination,discard_dump_states=True)
        layout_receipts=[]
        while stage <= 5:
            layout = (team or {}).get('layout',[]) if stage==1 else (team or {}).get('later_layouts',{}).get(str(stage),[])
            receipts=[]
            refuge=None
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
                occupied=[unit for kind,unit in BUILDINGS.items() if f'board {kind} = ' in board['_text']]
                receipts=apply_layout(env,remaining_layout(layout,board),occupied,boundary=boundary)
                if stage==1 and attempt==0:layout_receipts=receipts
            active={**team,**team.get('stage_battle',{}).get(str(stage),{})} if team else None
            start_kind='carry' if attempt else ('fresh' if stage==1 else
                                                'continue' if stage==start_stage else 'next_level')
            options=dict(start_kind=start_kind,seed=seed,record_layout=bool(layout),greedy=True)
            if training:options['paused_seconds']=45
            row = tr.run_episode((env.pid,weights,False,f'search/{seed}/L{stage}/a{attempt}',options),
                                 policy_factory=(lambda:TeamPolicy(active,forecast)) if active else None,
                                 telemetry=observe)
            if not tr.valid_trajectory(row):
                result.update(failed_stage=stage,failed_attempt=attempt,error=row.get('err','invalid trajectory'))
                break
            levels.append(dict(stage=row['scenario'],end=row['end'],saved=row['saved_frac'],
                               win=row['win'],advance=row['advance'],campaign=row['campaign'],
                               attempt=attempt,start_kind=start_kind,
                               refuge=refuge,
                               outbreak=row.get('outbreak'),
                               timeout_reason=row.get('timeout_reason'),planning_blockers=row.get('planning_blockers'),
                               unmatched_layout=remaining_layout(layout,{'_text':row['layout_text']}) if layout else [],
                               layout_receipts=receipts,battle_actions=row['battle_actions'],
                               outside_playarea_actions=row.get('outside_playarea_actions',0)+
                                   sum(r.get('result')=='outside_playarea' for r in receipts),
                               playarea_cost=tr.OUTSIDE_PLAYAREA_COST/tr.SAVED_REWARD_SCALE,
                               reward_components=row.get('reward_components',{}),
                               score=score(row),sim=row['sim'],board=row['board_id'],
                               actions=list(zip(row['us'],row['cs'])),log_started=row['log_started']))
            if row['advance']:
                if row['scenario']==row['board'].get('scenario_count'):break
                stage+=1
                attempt=0
            elif (stage>1 or (practice_retry and training and row['win'])) and attempt<retries and row['end'] in ('aborted','lost','won'):
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
        if 'blocked_tool' in obj and (type(obj['blocked_tool'])!=int or obj['blocked_tool'] not in REPAIRS):
            raise ValueError('Invalid campaign recovery action')
    fields(team,('plan','battle','cast_bias','idle_bias'),('layout','later_layouts','stage_battle','camera_pause','blocked_tool','refuge','cast_timing'))
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
        fields(override,optional=('battle','cast_bias','camera_pause','blocked_tool','cast_timing'))
        battle(override)
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


def completed_rollouts(pool,jobs,starts=None,retries=0,training=False):
    if starts is None:starts=[1]*len(jobs)
    observed=next((j[0] for j in jobs if j[2]),None) if training else None
    practice_copy=next((j[0] for j,stage in zip(jobs,starts) if training and j[2] and stage==1),None)
    futures={pool.submit(rollout,job,retries,stage,training=training,observe=job[0]==observed,
                         practice_retry=job[0]==practice_copy):(job,stage)
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
    parser.add_argument('--seed',type=int,default=92851)
    parser.add_argument('--stage-retries','--later-retries',dest='later_retries',type=int,default=2,
                        help='Training retries on later stages and below-target first-stage wins')
    parser.add_argument('--seed-from',type=Path,help='Start with a previous search champion and its frozen GRU')
    parser.add_argument('--demonstration',type=Path,help='Seed candidates from a local Boston progress file')
    parser.add_argument('--compare-forecast',type=Path,help='Evaluate the same saved champion with and without its CNN forecast')
    args=parser.parse_args()
    copies=args.copies
    if not 4<=len(copies)<=8 or len(set(copies))!=len(copies) or args.generations<1 or args.later_retries<0:
        parser.error('Use 4–8 distinct owned copies and positive generations')
    if args.compare_forecast and (not args.seed_from or len(copies)%2 or args.demonstration):
        parser.error('Forecast comparison requires a saved champion and paired copies')
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
        view_revision='playable-overview-v2-bounded-targets'
        evidence={}
        prices={}
        if args.seed_from and (args.seed_from/'fitness.json').exists():
            ledger=json.loads((args.seed_from/'fitness.json').read_text())
            if ledger['base']!=base:raise ValueError('Campaign fitness base mismatch')
            if ledger.get('view_revision')==view_revision:evidence=ledger['evidence']
            prices=ledger.get('layout_prices',{})
        cast_probe=None
        if args.seed_from and not args.compare_forecast and (args.seed_from/'trials.jsonl').is_file():
            best_budget=None
            for line in (args.seed_from/'trials.jsonl').read_text().splitlines():
                trial=json.loads(line)
                if trial.get('view_revision')==view_revision:fitness.record(evidence,trial)
                if not trial.get('levels'):continue
                if prior and trial.get('team')==prior:cast_probe=cast_candidate(trial,rng) or cast_probe
                candidate=budget_candidate(trial.get('team'),trial['levels'],prices)
                if candidate:
                    rank=(max(r['stage'] for r in trial['levels']),team_id(candidate))
                    if best_budget is None or rank>best_budget:
                        best_budget,population[-1]=rank,candidate
            for i in range(1,len(population)):
                population[i]=budget_candidate(population[i],[],prices) or population[i]
        if prior and not args.compare_forecast:
            population[1]=l1_candidate(prior,rng)
            previous=args.seed_from/'provisional.json'
            if previous.is_file():
                saved=checkpoint_team(json.loads(previous.read_text()),base)['team']
                if saved!=prior:population[-1]=saved
            if cast_probe:population[1]=cast_probe
        archive={}
        deepest={}
        incumbent=prior
        continued={}
        require_fresh=set()
        with ProcessPoolExecutor(len(copies)) as pool:
            if args.compare_forecast:
                contender=loadout_candidate(prior,rng)
                (directory/'comparison-team.json').write_text(json.dumps(contender))
                for swap in range(2):
                    jobs=[]
                    for i,copy in enumerate(copies):
                        job=(copy,weights,contender,args.seed+swap*len(copies)+i//2)
                        jobs.append(job+(args.compare_forecast,) if (i+swap)%2 else job)
                    for job,_,result in completed_rollouts(pool,jobs):
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
                for job,start_stage,result in completed_rollouts(pool,jobs,starts,args.later_retries,training=True):
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
                probe=next((cast_probes[k] for k in l1_ranked if k in cast_probes),None)
                if probe and (generation%2==0 or not practice):population.append(probe)
                elif practice:
                    specialist=max(practice,key=lambda entry:(entry[0],entry[1],team_id(entry[2])))[2]
                    population.append(specialist)
                    require_fresh.add(team_id(specialist))
                elif affordable:
                    population.append(max(affordable,key=lambda entry:(entry[0],team_id(entry[1])))[1])
                while len(population)<len(copies):
                    stage_parent=ranked[0]
                    stage=deepest[stage_parent] if len(population)%2 else 1
                    key=stage_parent if stage>1 else l1_ranked[int(rng.integers(min(2,len(l1_ranked))))]
                    child=offspring(archive[key],leader,rng,stage=stage)
                    population.append(budget_candidate(child,[],prices) or child)
            # Frozen arms on fresh boards. The game chooses its own outbreak seeds.
            distinct=[archive[k] for k in ranked if archive[k]!=prior]
            qualified=[t for t in distinct if fitness.promote(evidence,t,prior) is t]
            challenger=next(iter(qualified or distinct),leader)
            stage=next((i for i in range(1,6) if prior is None or
                        fitness.prefix_id(challenger,i)!=fitness.prefix_id(prior,i)),1)
            jobs=[(copy,weights,challenger if i%2==0 else prior,
                   args.seed+(args.generations+1)*len(copies)+i//2) for i,copy in enumerate(copies)]
            evaluation=[]
            arms={copy:('extra' if i>=2*(len(copies)//2) else 'candidate' if i%2==0 else 'incumbent' if prior else 'gru')
                  for i,copy in enumerate(copies)}
            for job,_,result in completed_rollouts(pool,jobs):
                result.update(arm=arms[job[0]],team_id=team_id(job[2]) if job[2] else 'control')
                evaluation.append(result)
                with (directory/'holdout.jsonl').open('a') as f:
                    f.write(json.dumps(result)+'\n')
            if challenger in qualified and fitness.holdout_passed(evaluation,len(copies)//2,stage):
                stages=[fitness.stats(evidence,challenger,i) for i in range(1,6)]
                record=dict(team_id=team_id(challenger),team=challenger,base=base,generation=generation,
                            trials=stages[0]['starts'],fresh_stages=stages,holdout_stage=stage,holdout_opponent=team_id(prior) if prior else 'gru')
                temp=directory/'champion.tmp'
                temp.write_text(json.dumps(record))
                temp.replace(directory/'champion.json')
                print('promoted after fresh holdout',record['team_id'],flush=True)



if __name__=='__main__':
    main()
