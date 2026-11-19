"""Report actual saved outcomes, keeping checkpoints, levels and board starts separate."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics


def aggregate(rows):
    groups = defaultdict(list)
    fields = ('run_id', 'checkpoint_id', 'scenario', 'start_kind', 'mode')
    for row in rows:
        if row.get('kind', 'episode') != 'episode':
            continue
        groups[tuple(row.get(k, 'unknown') for k in fields)].append(row)
    result = []
    for key, attempts in groups.items():
        values, incomplete, unknown, errors = [], 0, 0, 0
        for row in attempts:
            if 'err' in row:
                errors += 1
            elif row.get('end') == 'timeout':
                incomplete += 1
            elif row.get('end') not in ('won', 'lost', 'aborted'):
                unknown += 1
            else:
                value = row.get('saved_frac')
                if isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1:
                    values.append(value)
                else:
                    unknown += 1
        successes = sum(v >= .35 for v in values)
        wins=sum(r.get('end')=='won' and 'err' not in r for r in attempts)
        qualifying=sum(r.get('end')=='won' and 'err' not in r and
                       isinstance(r.get('saved_frac'),(int,float)) and .35<=r['saved_frac']<=1 for r in attempts)
        result.append(dict(zip(fields, key), attempts=len(attempts),
            completed_known=len(values), at_least_35_percent=successes,
            game_wins=wins,qualifying_wins=qualifying,qualifying_rate_all_starts=qualifying/len(attempts),
            success_rate=successes/len(values) if values else None,
            minimum_saved=min(values) if values else None,
            mean_saved=statistics.mean(values) if values else None,
            median_saved=statistics.median(values) if values else None,
            incomplete=incomplete, unknown_outcome=unknown, errors=errors))
    return result


def records(path):
    with path.open(encoding='utf-8') as f:
        for line in f:
            if not line.strip():continue
            try:yield json.loads(line)
            except json.JSONDecodeError:
                if line.endswith('\n'):raise


def search_rows(directory):
    for filename,mode in [('trials.jsonl','search'),('holdout.jsonl','holdout'),
                          ('forecast-comparison.jsonl','forecast')]:
        path=directory/filename
        if not path.is_file():continue
        for trial in records(path):
            name=mode
            if mode=='forecast':name+='-cnn' if trial['cnn'] else '-current'
            if trial.get('start_stage',1)>1:name='practice'
            common=dict(run_id=directory.name,checkpoint_id=trial['team_id'],mode=name)
            for level in trial.get('levels',[]):
                yield dict(common,scenario=level['stage'],end=level['end'],saved_frac=level['saved'],
                           start_kind=level.get('start_kind','fresh' if level['stage']==1 else 'next_level'))
            if 'error' in trial:
                yield dict(common,scenario=trial.get('failed_stage','unknown'),start_kind='unknown',err=trial['error'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    source=ap.add_mutually_exclusive_group()
    source.add_argument('--history', type=Path, default=Path(__file__).resolve().parents[1]/'analysis/nn_hist4.jsonl')
    source.add_argument('--search-dir',type=Path)
    args = ap.parse_args()
    if args.search_dir and not args.search_dir.is_dir():ap.error('Search directory does not exist')
    rows=search_rows(args.search_dir) if args.search_dir else records(args.history)
    groups = aggregate(rows)
    print(json.dumps({'groups': groups,
          'note': 'success_rate uses known saved percentages. qualifying_rate_all_starts uses all starts assigned to the group. Errors without a confirmed stage appear separately.'}, indent=2))


if __name__ == '__main__':
    main()
