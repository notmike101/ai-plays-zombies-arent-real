"""Population search over planning sequences and battle targeting on real game copies."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
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
                camera_pause=rng.normal(0,2,6).tolist())


def loadout_candidate(parent,rng):
    candidate=deepcopy(parent)
    pick=gene(rng)
    pick.update(family=2,tool=int(rng.choice(FAMILIES[2])),duration=1)
    candidate['plan'].insert(0,pick)
    return candidate


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
        if move=='translate':layout[index]=item
        else:layout.insert(index+1,item)


def offspring(parent, donor, rng, stage=1):
    child = deepcopy(parent)
    if stage>1 and str(stage) in child.get('later_layouts',{}):
        layout=child['later_layouts'][str(stage)]
        vary_layout(layout,rng)
        params=child.setdefault('stage_battle',{}).setdefault(str(stage),{})
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
        self.camera_pause=torch.tensor(team.get('camera_pause',[0.]*6))
        self.predict = None if forecast is None else forecast.forward

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
        else:
            tools[...,PAN]+=self.camera_pause[:4]
            tools[...,PAUSE]+=self.camera_pause[4+int(x[0,0,PAUSED].item()!=0)]
            if self.predict is not None:
                future=self.predict(grid[:3].reshape(1,3,6,8)).clamp_min(0).reshape(2,tr.NC)
                grid=torch.cat((future,grid[2:]))
            tools[..., CASTS] += self.bias
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


def rollout(job, retries=0, start_stage=1, *, training=False):
    copy, weights, team, seed, *forecast_path = job
    forecast=None
    if forecast_path:
        from crowd_forecast import CrowdForecast
        forecast=CrowdForecast().eval()
        forecast.load_state_dict(torch.load(forecast_path[0],weights_only=True))
    destination=('campaign','continue' if start_stage>1 else 'stage1')
    env = zar_boot.boot(operator.owned_copy(copy),destination,discard_dump_states=True)
    try:
        levels = []
        layout_receipts=[]
        stage, attempt = start_stage, 0
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
                if stage==1 and team.get('refuge'):
                    from layout_memory import fit_refuge
                    from native_state import VEC
                    points=env.array(0x650280,VEC)
                    kinds=env.array(0x6502d0,'u1')
                    if len(points)!=len(kinds):raise RuntimeError('Inconsistent planning population')
                    origin=np.array([env.scalar(r,'<f') for r in (0x665358,0x66535c)])
                    boundary=env.array(0x6652e0,VEC,limit=10000)+origin
                    layout,refuge=fit_refuge(layout,points[kinds==0]+origin,boundary,team['refuge'])
                occupied=[unit for kind,unit in BUILDINGS.items() if f'board {kind} = ' in board['_text']]
                receipts=apply_layout(env,remaining_layout(layout,board),occupied)
                if stage==1:layout_receipts=receipts
            active={**team,**team.get('stage_battle',{}).get(str(stage),{})} if team else None
            start_kind='carry' if attempt else ('fresh' if stage==1 else
                                                'continue' if stage==start_stage else 'next_level')
            options=dict(start_kind=start_kind,seed=seed,record_layout=bool(layout),greedy=True)
            if training:options['paused_seconds']=45
            row = tr.run_episode((env.pid,weights,False,f'search/{seed}/L{stage}/a{attempt}',options),
                                 policy_factory=(lambda:TeamPolicy(active,forecast)) if active else None,
                                 telemetry=False)
            if not tr.valid_trajectory(row):
                return dict(copy=copy,seed=seed,levels=levels,error=row.get('err','invalid trajectory'))
            levels.append(dict(stage=row['scenario'],end=row['end'],saved=row['saved_frac'],
                               win=row['win'],advance=row['advance'],campaign=row['campaign'],
                               attempt=attempt,start_kind=start_kind,
                               refuge=refuge,
                               outbreak=row.get('outbreak'),
                               timeout_reason=row.get('timeout_reason'),planning_blockers=row.get('planning_blockers'),
                               unmatched_layout=remaining_layout(layout,{'_text':row['layout_text']}) if layout else [],
                               layout_receipts=receipts,battle_actions=row['battle_actions'],
                               score=score(row),sim=row['sim'],board=row['board_id'],
                               actions=list(zip(row['us'],row['cs'])),log_started=row['log_started']))
            if row['advance']:
                if row['scenario']==row['board'].get('scenario_count'):break
                stage+=1
                attempt=0
            elif stage>1 and attempt<retries and row['end'] in ('aborted','lost','won'):
                attempt+=1
            else:
                break
        return dict(copy=copy,seed=seed,levels=levels,layout_receipts=layout_receipts)
    finally:
        zar_boot.stop(env)


def team_id(team):
    return hashlib.sha256(json.dumps(team,sort_keys=True).encode()).hexdigest()[:16]


def budget_candidate(team,levels):
    if not team:return None
    child=None
    for stage in levels:
        for receipt in stage.get('layout_receipts',[]):
            if receipt.get('after',0)>=0 or receipt['before']<=0:continue
            if child is None:child=deepcopy(team)
            number=stage['stage']
            layout=child.get('layout',[]) if number==1 else child.get('later_layouts',{}).get(str(number),[])
            matches=[a for a in layout if a['kind']==receipt['kind'] and
                     ('world_points' not in receipt or a['points']==receipt['world_points'])]
            if len(matches)==1:
                matches[0]['observed_cost']=receipt['before']-receipt['after']
    return child if child!=team else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copies',nargs='+',required=True)
    parser.add_argument('--generations',type=int,default=10)
    parser.add_argument('--seed',type=int,default=92851)
    parser.add_argument('--later-retries',type=int,default=2,help='Normal board retries per later stage during search only')
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
            champion=json.loads((args.seed_from/'champion.json').read_text())
            net.load_state_dict(torch.load(args.seed_from/'base.pt',weights_only=True))
            prior=champion['team']
            if team_id(prior)!=champion['team_id'] or tr.policy_id(net)!=champion['base']:
                raise ValueError('Champion and base policy do not match the saved identities')
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
        if args.seed_from and not args.compare_forecast and (args.seed_from/'trials.jsonl').is_file():
            for line in (args.seed_from/'trials.jsonl').read_text().splitlines():
                trial=json.loads(line)
                candidate=budget_candidate(trial.get('team'),trial.get('levels',[]))
                if candidate:population[-1]=candidate
        archive={}
        deepest={}
        scores=defaultdict(list)
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
                    for job,result in zip(jobs,pool.map(rollout,jobs)):
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
                futures=[pool.submit(rollout,job,args.later_retries,stage,training=True) for job,stage in zip(jobs,starts)]
                valid_candidates=0
                for team, future, job,start_stage in zip(population,futures,jobs,starts):
                    try: result=future.result()
                    except Exception as exc: result=dict(error=str(exc),copy=job[0],seed=job[3])
                    key=team_id(team) if team else 'control'
                    result.update(generation=generation,team_id=key,team=team,start_stage=start_stage)
                    with (directory/'trials.jsonl').open('a') as f:
                        f.write(json.dumps(result)+'\n')
                    if 'error' in result:
                        print('failed',job[0],result['error'],flush=True)
                        continue
                    levels=result['levels']
                    candidate=budget_candidate(team,levels)
                    if candidate:affordable.append((max(r['stage'] for r in levels),candidate))
                    last=levels[-1]
                    if last['stage']>1 and last['end'] in ('aborted','lost','won') and not last['advance']:
                        continued[job[0]]=last['stage']
                    if start_stage>1:
                        practice.append((start_stage,max(r['score'] for r in levels if r['stage']==start_stage),team))
                        print('practice',key,[(r['stage'],r['end'],r['saved']) for r in levels],flush=True)
                        continue
                    if team:
                        valid_candidates+=1
                        archive[key]=team
                        deepest[key]=max(deepest.get(key,1),levels[-1]['stage'])
                        best=[max(r['score'] for r in levels if r['stage']==stage)
                              for stage in sorted({r['stage'] for r in levels})]
                        scores[key].append([sum(r[0] for r in best),sum(r[1] for r in best),
                                            sum(r[2] for r in best),best[-1][3]])
                    print(generation,key,[(r['stage'],r['end'],r['saved'],round(r['sim'],1)) for r in levels],flush=True)
                if not valid_candidates:raise RuntimeError('No valid candidates this generation; inspect trials')
                ranked=sorted(scores,key=lambda k:tuple(np.mean(scores[k],axis=0)),reverse=True)
                elites=[archive[k] for k in ranked[:2]]
                population=list(elites)
                if affordable:population.append(max(affordable,key=lambda entry:entry[0])[1])
                if practice:
                    specialist=max(practice,key=lambda entry:(entry[0],entry[1]))[2]
                    if specialist not in population:population.append(specialist)
                    require_fresh.add(team_id(specialist))
                if len(copies)>=6:
                    population.append(random_team(rng))
                while len(population)<len(copies):
                    parent=elites[int(rng.integers(len(elites)))]
                    population.append(offspring(parent,elites[int(rng.integers(len(elites)))],
                                                rng,stage=deepest[team_id(parent)]))
                print('elite',ranked[0],len(scores[ranked[0]]),np.mean(scores[ranked[0]],axis=0),flush=True)
                champion = dict(team_id=ranked[0], team=archive[ranked[0]], base=tr.policy_id(net),
                                generation=generation, trials=len(scores[ranked[0]]))
                temp=directory/'champion.tmp'
                temp.write_text(json.dumps(champion))
                temp.replace(directory/'champion.json')
            # New boards and seeds: these scores never drive candidate selection.
            jobs=[(copy,weights,archive[ranked[0]] if i%2==0 else None,
                   args.seed+(args.generations+1)*len(copies)+i//2) for i,copy in enumerate(copies)]
            for job,result in zip(jobs,pool.map(rollout,jobs)):
                result['team_id']=ranked[0] if job[2] else 'control'
                with (directory/'holdout.jsonl').open('a') as f:
                    f.write(json.dumps(result)+'\n')


if __name__=='__main__':
    main()
