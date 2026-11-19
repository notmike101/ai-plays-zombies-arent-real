"""Offline observational benchmark for two-second combat forecasts."""
import argparse
from bisect import bisect_left
from collections import Counter
import json
import math
from pathlib import Path
import time

import numpy as np
import psutil
import torch
from torch import nn

from crowd_forecast import CrowdForecast


def episodes(path):
    seen = set()
    for line in path.read_text().splitlines():
        row = json.loads(line)
        for level in row['levels']:
            s = level.get('shadow') or {}
            seed = (level.get('outbreak') or {}).get('seed')
            if (level['start_kind'] != 'fresh' or seed is None or seed in seen
                    or not s.get('native_footer') or s.get('truncated')):
                continue
            actual = level['battle_actions']
            times = actual.get('deploy_sim_seconds') or []
            names = actual.get('logged_deployments') or []
            if len(times) != len(names) or len(times) != len(s['casts']):
                continue
            if any(c['tool'] != 'missile' or name != 'cruise_missile'
                   or t is None or abs(t - c['sim']) > .5
                   for c, name, t in zip(s['casts'], names, times)):
                continue
            seen.add(seed)
            yield row['copy'], s


def encode(frame):
    grid = np.asarray(frame['grid'][:3], dtype=np.float32).reshape(3, 6, 8)
    totals = np.broadcast_to(np.float32([frame['civilians'], frame['zombies']])[:, None, None],
                             (2, 6, 8))
    return np.log1p(np.concatenate((grid, totals)))


def commands(casts, start, end):
    scheduled = np.zeros((2, 48), dtype=np.float32)
    for cast in casts:
        if start - 8 <= cast['sim'] <= end:
            scheduled[int(cast['sim'] > start), cast['cell']] += 1
    return scheduled.reshape(2, 6, 8)


def aligned(a, b):
    return abs(a[2] - b[2]) <= 1e-5 and math.dist(a[:2], b[:2]) * a[2] <= 1


def chains(shadow, steps):
    frames = shadow['frames']
    times = [f['sim'] for f in frames]
    for i in range(0, len(frames), 3):
        indices = [i]
        for _ in range(steps):
            a = indices[-1]
            b = bisect_left(times, times[a] + 2)
            if b == len(times) or times[b] - times[a] > 2.65 or any(
                    not aligned(frames[i]['camera'], f['camera']) for f in frames[a:b+1]):
                break
            indices.append(b)
        if len(indices) == steps + 1:
            yield [frames[j] for j in indices], shadow['casts']


def tensors(examples):
    x = np.stack([encode(f[0]) for f, _ in examples])
    y = np.stack([encode(f[-1]) for f, _ in examples])
    a = np.stack([commands(c, f[0]['sim'], f[-1]['sim']) for f, c in examples])
    return tuple(torch.from_numpy(z) for z in (x, a, y))


class Dynamics(nn.Module):
    def __init__(self, conditioned):
        super().__init__()
        self.conditioned = conditioned
        self.net = nn.Sequential(nn.Conv2d(7 if conditioned else 5, 16, 3, padding=1),
                                 nn.ReLU(), nn.Conv2d(16, 5, 3, padding=1))
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, state, action):
        features = torch.cat((state, action), dim=1) if self.conditioned else state
        return (state + self.net(features)).clamp_min(0)


def fit(data, conditioned):
    model = Dynamics(conditioned)
    opt = torch.optim.Adam(model.parameters(), lr=.002)
    x, action, y = data
    for _ in range(25):
        for idx in torch.randperm(len(x)).split(64):
            prediction = model(x[idx], action[idx])
            loss = (prediction - y[idx]).square().mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model.eval()


def predict(model, frames, casts, x):
    action = torch.from_numpy(np.stack([
        commands(c, f[0]['sim'], f[1]['sim']) for f, c in zip(frames, casts)]))
    if model is None:
        return x
    if isinstance(model, CrowdForecast):
        crowd = model(x[:, :3]).clamp_min(0)
        # The legacy CNN has no population head. Keep its totals at persistence.
        return torch.cat((crowd, x[:, 2:]), dim=1)
    return model(x, action)


def errors(pred, actual):
    totals = (pred[:, 3:].mean((2, 3)).expm1() - actual[:, 3:, 0, 0].expm1()).abs()
    grid = (pred[:, :2].expm1() - actual[:, :2].expm1()).abs().mean((2, 3))
    z = actual[:, 1].flatten(1).expm1()
    chosen = pred[:, 1].flatten(1).argmax(1)
    regret = 1 - (z.gather(1, chosen[:, None]).squeeze(1) / z.amax(1).clamp_min(1))
    return torch.cat((totals, grid, torch.where(z.amax(1) > 0, regret, 0.)[:, None]), dim=1)


def evaluate(model, samples, horizon):
    x = torch.from_numpy(np.stack([encode(f[0]) for f, _ in samples]))
    casts = [c for _, c in samples]
    for step in range(horizon):
        x = predict(model, [f[step:step+2] for f, _ in samples], casts, x)
    actual = torch.from_numpy(np.stack([encode(f[-1]) for f, _ in samples]))
    return errors(x, actual)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path)
    parser.add_argument('cnn', type=Path)
    args = parser.parse_args()
    psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
    torch.set_num_threads(1)
    torch.manual_seed(92)
    games = list(episodes(args.ledger))
    copies = sorted({c for c, _ in games})
    if len(copies) < 6:
        parser.error('Need at least six copies with attributable session data')
    train, calibration, test = copies[:-3], copies[-3:-2], copies[-2:]
    subset = lambda copies, h: [sample for c, s in games if c in copies for sample in chains(s, h)]
    training = subset(train, 1)
    if not training:
        parser.error('No aligned training transitions')
    data = tensors(training)
    cnn = CrowdForecast().eval()
    cnn.load_state_dict(torch.load(args.cnn, map_location='cpu', weights_only=True))
    models = {'persistence': None, 'archived_cnn': cnn, 'state_only': fit(data, False),
              'action_conditioned': fit(data, True)}
    report = dict(train=train, calibration=calibration, test=test, training_windows=len(training),
                  decision_use='refused',
                  refusal_reasons=['future receipt schedule is supplied for retrospective evaluation',
                                   'isolated action effects and counterfactuals are unvalidated',
                                   'calibration uses one held-out copy'],
                  games=dict(Counter(c for c, _ in games)), horizons={},
                  metrics=['global_civilian_mae', 'global_zombie_mae', 'civilian_cell_mae',
                           'zombie_cell_mae', 'hotspot_regret'])
    with torch.inference_mode():
        for h in (1, 2, 3):
            held, calibrate = subset(test, h), subset(calibration, h)
            if not held or not calibrate:
                continue
            row = dict(windows=len(held), models={})
            for name, model in models.items():
                scores = evaluate(model, held, h)
                row['models'][name] = scores.mean(0).tolist()
                if name == 'action_conditioned':
                    ceiling = evaluate(model, calibrate, h).amax(0)
                    row['calibration_max'] = ceiling.tolist()
                    row['fraction_inside_ceiling'] = (scores <= ceiling).float().mean(0).tolist()
                    groups = [any(f[0]['sim'] < c['sim'] <= f[-1]['sim'] for c in casts) for f, casts in held]
                    row['receipt_windows'] = sum(groups)
                    if any(groups):
                        row['with_receipt_conditioned'] = scores[groups].mean(0).tolist()
                        row['with_receipt_state_only'] = evaluate(models['state_only'], held, h)[groups].mean(0).tolist()
            report['horizons'][h] = row
        fixed = subset(test, 3)
        if fixed:
            report['fixed_three_step_cohort'] = {
                'windows': len(fixed),
                'action_conditioned': [
                    evaluate(models['action_conditioned'], [(f[:h+1], c) for f, c in fixed], h)
                    .mean(0).tolist() for h in (1, 2, 3)
                ],
            }
        report['forecast_windows_per_second'] = {}
        for size in (1, 64):
            batch = training[:size]
            start = time.perf_counter()
            for _ in range(100):
                evaluate(models['action_conditioned'], batch, 1)
            report['forecast_windows_per_second'][len(batch)] = (
                100 * len(batch) / (time.perf_counter() - start))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
