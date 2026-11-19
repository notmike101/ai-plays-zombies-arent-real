"""Fresh-campaign evidence for selecting and retesting stage policies."""
import hashlib
import json
import math


def prefix_id(team,stage):
    prefix={k:v for k,v in team.items() if k not in ('later_layouts','stage_battle')}
    for key in ('later_layouts','stage_battle'):
        prefix[key]={k:v for k,v in team.get(key,{}).items() if int(k)<=stage}
    return hashlib.sha256(json.dumps([stage,prefix],sort_keys=True).encode()).hexdigest()[:16]


def record(evidence,trial):
    team=trial.get('team')
    if not team or trial.get('arm') or trial.get('start_stage',1)!=1:return
    for stage,row in enumerate(trial.get('levels',[]),1):
        if row['stage']!=stage or row.get('attempt',0) or row.get('start_kind')!=('fresh' if stage==1 else 'next_level'):break
        seed=(row.get('outbreak') or {}).get('seed')
        sample=f'seed/{seed}' if seed is not None else f"log/{trial['copy']}/{row['log_started']}"
        won=row['end']=='won' and row['saved'] is not None and row['saved']>=.35
        samples=evidence.setdefault(prefix_id(team,stage),{})
        value=[won,row['saved'] or 0.]
        samples[sample]=min(samples.get(sample,value),value)
        if not won:break


def stats(evidence,team,stage):
    samples=evidence.get(prefix_id(team,stage),{})
    n=len(samples)
    wins=sum(won for sample,(won,_) in samples.items() if sample.startswith('seed/'))
    if not n:return dict(starts=0,wins=0,lower=0.,mean=0.)
    p=wins/n
    z=1.96
    lower=(p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/(1+z*z/n)
    return dict(starts=n,wins=wins,lower=max(0.,lower),mean=sum(s for _,s in samples.values())/n)


def ranking(evidence,team):
    stages=[stats(evidence,team,i) for i in range(1,6)]
    depth=next((i for i,s in enumerate(stages) if s['wins']<2),5)
    return (depth,*(s['lower'] for s in stages),*(s['mean'] for s in stages))

def promote(evidence, challenger, incumbent):
    for stage in range(1,6):
        if incumbent is not None and prefix_id(challenger,stage)==prefix_id(incumbent,stage):continue
        new=stats(evidence,challenger,stage)
        if new['wins']<2:return incumbent
        if incumbent is None or new['lower']>stats(evidence,incumbent,stage)['lower']:return challenger
        return incumbent
    return incumbent


def holdout_passed(rows, expected, stage=1):
    arms={'candidate':{},'reference':{}}
    for trial in rows:
        if trial['arm']=='extra':continue
        samples=arms['candidate' if trial['arm']=='candidate' else 'reference']
        levels=trial.get('levels',[])
        if not levels or levels[0].get('start_kind')!='fresh':return False
        seed=(levels[0].get('outbreak') or {}).get('seed')
        if seed is None:return False
        outcome=(False,0.)
        for index in range(stage):
            if index>=len(levels):return False
            row=levels[index]
            if row['stage']!=index+1 or row.get('attempt',0):return False
            saved=row['saved'] or 0.
            qualified=row['end']=='won' and saved>=.35
            if index+1==stage:outcome=(qualified,saved)
            if not qualified:break
        samples[seed]=outcome
    if any(len(s)!=expected for s in arms.values()):return False
    def totals(samples):
        return tuple(map(sum,zip(*samples.values())))
    wins,saved=totals(arms['candidate'])
    old_wins,old_saved=totals(arms['reference'])
    return wins>=2 and wins>old_wins and saved>old_saved
