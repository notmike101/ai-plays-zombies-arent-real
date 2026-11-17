"""Round/level trend from analysis/nn_hist2.jsonl.

Level identity = civ0 (starting civilians): 8142 = L1 (Boston). Unknown civ0
values print as-is so the L2+ bases become visible as the model climbs.
"""
import collections
import json

path = r'D:\zar-scratch\analysis\nn_hist2.jsonl'
agg = collections.defaultdict(lambda: [0, 0, 0.0, []])
rounds = collections.defaultdict(lambda: [0, 0])
CIV = {8142: 'L1'}
for ln in open(path):
    r = json.loads(ln)
    key = CIV.get(r.get('civ0'), f"civ0={r.get('civ0')}")
    a = agg[key]
    a[0] += 1
    a[1] += int(r['win'])
    a[2] += r['frac']
    a[3].append(r['frac'])
    rd = rounds[r['level']]
    rd[0] += 1
    rd[1] += int(r['win'])
print('--- per level ---')
for lvl in sorted(agg):
    n, w, fs, fr = agg[lvl]
    fr.sort()
    print(f'{lvl:>12} eps {n:>3} wins {w:>2} ({100 * w / n:5.1f}%) '
          f'meanfrac {fs / n:.3f} p50 {fr[len(fr) // 2]:.3f} max {fr[-1]:.3f}')
print('--- per round (service order) ---')
for rd in sorted(rounds):
    n, w = rounds[rd]
    print(f'{rd:>12} eps {n:>3} wins {w:>2} ({100 * w / n:5.1f}%)')
