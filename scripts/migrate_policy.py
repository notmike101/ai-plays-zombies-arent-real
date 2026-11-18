"""Explicit v3->v4 migration into a NEW file, preserving old weights and Adam state."""
import argparse
import copy
import hashlib
from pathlib import Path
import tempfile

import torch
import nn_play2 as train


def schema3_inputs():
    # The only semantic correction: live aircraft never granted another stock charge.
    return [s.replace('charges / max', 'charges+alive heli / max')
            for s in train.checkpoint_schema()['inputs'][:332]]


def migrate(data):
    old=data.get('schema',{});new=train.checkpoint_schema()
    if old.get('version')!=3 or old.get('inputs')!=schema3_inputs() or any(
            old.get(k)!=new[k][:n] for k,n in [('tools',72),('cells',72*48)]):
        raise ValueError('Expected exact schema3 meanings; refusing reinterpretation')
    if data.get('learning')!=train.learning_config():
        raise ValueError('Learning contract differs; review before migration')
    result=copy.deepcopy(data)
    with torch.random.fork_rng():
        torch.manual_seed(4)
        net=train.PolicyNet2()
    sd=net.state_dict();names=list(sd)
    if set(data['policy'])!=set(sd):raise ValueError('Unexpected source parameters')
    for name,target in sd.items():
        source=data['policy'][name]
        expected=list(target.shape)
        if name=='gru.weight_ih_l0':expected[1]=332
        if name.startswith('hu.'):expected[0]=72
        if name.startswith('hc.'):expected[0]=72*48
        if list(source.shape)!=expected or not torch.isfinite(source).all():
            raise ValueError('Unexpected source tensor shape: '+name)
        if name=='gru.weight_ih_l0':target.zero_()
        if name=='hu.bias':target.fill_(-4.)
        slices=tuple(slice(0,size) for size in source.shape)
        target[slices]=source
    opt=result.get('optimizer')
    if not opt or len(opt['param_groups'])!=1:
        raise ValueError('Expected saved Adam optimizer')
    ids=opt['param_groups'][0]['params']
    if len(ids)!=len(names) or set(opt['state'])!=set(ids):
        raise ValueError('Incomplete optimizer state')
    for ident,name in zip(ids,names):
        state=opt['state'][ident]
        for key in ('exp_avg','exp_avg_sq'):
            source=state[key]
            if source.shape!=data['policy'][name].shape:
                raise ValueError('Invalid Adam moment shape: '+name)
            expanded=torch.zeros_like(sd[name])
            expanded[tuple(slice(0,size) for size in source.shape)]=source
            state[key]=expanded
    result['policy']=sd;result['schema']=new
    result['run_id']='migrated-'+hashlib.sha256(str(data.get('run_id')).encode()).hexdigest()[:12]
    net.load_state_dict(sd)
    optimizer=torch.optim.Adam(net.parameters());optimizer.load_state_dict(opt)
    return result


def migrate_file(source,destination):
    source,destination=Path(source),Path(destination)
    if destination.exists() or source.resolve()==destination.resolve():
        raise FileExistsError('Migration requires a new destination; source is preserved')
    raw=source.read_bytes()
    import io
    data=migrate(torch.load(io.BytesIO(raw),map_location='cpu',weights_only=True))
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.migrate-',dir=destination.parent) as temp:
        output=Path(temp)/'checkpoint.pt';torch.save(data,output)
        # Windows rename refuses an existing destination, including a racing writer.
        output.rename(destination)
    assert source.read_bytes()==raw,'Source changed during migration'
    return dict(source_sha256=hashlib.sha256(raw).hexdigest(),destination=str(destination),schema=4)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    args=parser.parse_args();print(migrate_file(args.source,args.destination))
