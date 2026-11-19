"""Fit a two-simulated-second spatial forecast; hold out entire game processes."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn


class CrowdForecast(nn.Module):
    def __init__(self):
        super().__init__()
        self.residual=nn.Sequential(nn.Conv2d(3,16,3,padding=1),nn.ReLU(),
                                    nn.Conv2d(16,2,3,padding=1))
        nn.init.zeros_(self.residual[-1].weight)
        nn.init.zeros_(self.residual[-1].bias)

    def forward(self, grid):
        return grid[:,:2]+self.residual(grid)


def pairs(path):
    with np.load(path) as data:
        sim, camera, grid = (data[k] for k in ('sim','camera','grids'))
    rows=[]
    previous=-1.
    for i,t in enumerate(sim):
        if t-previous < .5:continue
        j=np.searchsorted(sim,t+2.)
        if j>=len(sim) or sim[j]-t>2.65:continue
        if np.linalg.norm(camera[i,:2]-camera[j,:2])*camera[i,2] > 1.:continue
        if abs(camera[i,2]-camera[j,2])>1e-5:continue
        rows.append((grid[i],grid[j,:2]))
        previous=t
    if not rows:return None
    return tuple(torch.from_numpy(np.stack(part)) for part in zip(*rows))


def fit(directory, seed=2405):
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    games=[]
    for path in sorted(directory.glob('*.npz')):
        sample=pairs(path)
        if sample is not None and len(sample[0])>=3:games.append((path.name,sample))
    if len(games)<6:raise ValueError('Need at least six distinct games with aligned future frames')
    rng=np.random.default_rng(seed)
    rng.shuffle(games)
    split=max(2,len(games)//3)
    test,train=games[:split],games[split:]
    net=CrowdForecast()
    opt=torch.optim.Adam(net.parameters(),lr=.003)
    x,y=(torch.cat(parts) for parts in zip(*(sample for _,sample in train)))
    for _ in range(40):
        for idx in torch.randperm(len(x)).split(64):
            loss=(net(x[idx])-y[idx]).square().mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        metrics=[]
        for name,(x,y) in test:
            metrics.append(dict(game=name,frames=len(x),
                            cnn=(net(x)-y).square().mean((0,2,3)).tolist(),
                            persistence=(x[:,:2]-y).square().mean((0,2,3)).tolist()))
    return net,dict(seed=seed,train_games=[name for name,_ in train],test=metrics,
                    train_pairs=sum(len(sample[0]) for _,sample in train))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    dest=args.directory/'forecast.pt'
    if dest.exists():parser.error('Forecast already exists in this directory')
    net,report=fit(args.directory)
    torch.save(net.state_dict(),dest)
    (args.directory/'forecast-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':
    main()
