"""Round-level win/frac trend from analysis/nn_hist2.jsonl."""
import collections
import json
import sys

path = r'D:\zar-scratch\analysis\nn_hist2.jsonl'
agg = collections.defaultdict(lambda: [0, 0, 0.0, []])
for ln in open(path):
    r = json.loads(ln)
    a = agg[r['level']]
    a[0] += 1
    a[1] += int(r['win'])
    a[2] += r['frac']
    a[3].append(r['frac'])
for lvl in sorted(agg, key=lambda x: (x[0] if x[0] else 'zz')):
    n, w, fs, fr = agg[lvl]
    fr.sort()
    p50 = fr[len(fr) // 2]
    print(f'{lvl:>6} eps {n:>3} wins {w:>2} ({100 * w / n:5.1f}%) '
          f'meanfrac {fs / n:.3f} p50 {p50:.3f} max {fr[-1]:.3f}')
