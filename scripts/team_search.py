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
                idle_bias=float(rng.uniform(-1, 3)))


def offspring(parent, donor, rng):
    child = deepcopy(parent)
    i = int(rng.integers(len(child['plan'])))
    child['plan'][i] = deepcopy(donor['plan'][int(rng.integers(len(donor['plan'])))]) if rng.random()<.5 else gene(rng)
    if len(child['plan']) < 7 and rng.random()<.35:
        child['plan'].insert(i, gene(rng))
    if len(child['plan']) > 1 and rng.random()<.25:
        child['plan'].pop(i)
    for key in ('battle','cast_bias'):
        base = np.asarray((donor if rng.random()<.5 else parent)[key])
        child[key] = (base + rng.normal(0,.35,base.shape)).tolist()
    return child


class TeamPolicy(tr.PolicyNet2):
    def __init__(self, team):
        super().__init__()
        self.team = team
        self.steps = [(g, t) for g in team['plan'] for t in range(g['duration'])]
        self.index = 0
        self.coords = torch.arange(tr.NC)
        self.battle = torch.tensor(team['battle'])
        self.bias = torch.tensor(team['cast_bias'])

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


def rollout(job):
    copy, weights, team, seed = job
    env = zar_boot.boot(operator.owned_copy(copy), discard_dump_states=True)
    try:
        levels = []
        for stage in range(1,6):
            row = tr.run_episode((env.pid,weights,False,f'search/{seed}/L{stage}',
                                  dict(start_kind='fresh' if stage==1 else 'next_level',seed=seed,
                                       greedy=True)),policy_factory=(lambda:TeamPolicy(team)) if team else None,
                                 telemetry=False)
            if not tr.valid_trajectory(row):
                return dict(copy=copy,seed=seed,levels=levels,error=row.get('err','invalid trajectory'))
            levels.append(dict(stage=row['scenario'],end=row['end'],saved=row['saved_frac'],
                               score=score(row),sim=row['sim'],board=row['board_id'],
                               actions=list(zip(row['us'],row['cs'])),log_started=row['log_started']))
            if not row['advance'] or row['scenario']==row['board'].get('scenario_count'):
                break
        return dict(copy=copy,seed=seed,levels=levels)
    finally:
        zar_boot.stop(env)


def team_id(team):
    return hashlib.sha256(json.dumps(team,sort_keys=True).encode()).hexdigest()[:16]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--copies',nargs='+',required=True)
    parser.add_argument('--generations',type=int,default=10)
    parser.add_argument('--seed',type=int,default=92851)
    args=parser.parse_args()
    copies=args.copies
    if not 4<=len(copies)<=8 or len(set(copies))!=len(copies) or args.generations<1:
        parser.error('Use 4–8 distinct owned copies and positive generations')
    with operator.training_lock(operator.LOCK):
        ancestors=[p.pid for p in psutil.Process().parents()]
        for copy in copies:
            operator.require_idle(operator.inventory(),copy,os.getpid(),ancestor_pids=ancestors)
            report=operator.preflight(copy)
            if not report['ok']:raise RuntimeError(report['errors'])
        operator.limit_resources(len(copies))
        rng=np.random.default_rng(args.seed)
        net=tr.PolicyNet2()
        tr.load_pretrained(net,tr.MODEL)
        weights=net.state_dict()
        directory=operator.ROOT/'analysis'/('coverage-team-'+uuid.uuid4().hex[:10])
        directory.mkdir()
        torch.save(weights,directory/'base.pt')
        print(directory,'base',tr.policy_id(net),flush=True)
        population=[random_team(rng) for _ in copies[1:]]
        archive={}
        scores=defaultdict(list)
        with ProcessPoolExecutor(len(copies)) as pool:
            for generation in range(args.generations):
                population.append(None)  # Fixed GRU control on a fresh board.
                rng.shuffle(population)
                jobs=[(copy,weights,team,args.seed+generation*len(copies)+i)
                      for i,(copy,team) in enumerate(zip(copies,population))]
                futures=[pool.submit(rollout,job) for job in jobs]
                for team, future, job in zip(population,futures,jobs):
                    try: result=future.result()
                    except Exception as exc: result=dict(error=str(exc),copy=job[0],seed=job[3])
                    key=team_id(team) if team else 'control'
                    result.update(generation=generation,team_id=key,team=team)
                    with (directory/'trials.jsonl').open('a') as f:
                        f.write(json.dumps(result)+'\n')
                    if 'error' in result:
                        print('failed',job[0],result['error'],flush=True)
                        continue
                    levels=result['levels']
                    if team:
                        archive[key]=team
                        scores[key].append([sum(r['score'][0] for r in levels),
                                            sum(r['score'][1] for r in levels),
                                            sum(r['score'][2] for r in levels),levels[-1]['score'][3]])
                    print(generation,key,[(r['stage'],r['end'],r['saved'],round(r['sim'],1)) for r in levels],flush=True)
                if not scores:raise RuntimeError('No valid search results; inspect trials')
                ranked=sorted(scores,key=lambda k:tuple(np.mean(scores[k],axis=0)),reverse=True)
                elites=[archive[k] for k in ranked[:2]]
                population=list(elites)
                if len(population)+1 < len(copies)-1:
                    population.append(random_team(rng))
                while len(population)<len(copies)-1:
                    population.append(offspring(elites[int(rng.integers(len(elites)))],
                                                elites[int(rng.integers(len(elites)))],rng))
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
