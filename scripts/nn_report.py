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
        result.append(dict(zip(fields, key), attempts=len(attempts),
            completed_known=len(values), at_least_35_percent=successes,
            success_rate=successes/len(values) if values else None,
            minimum_saved=min(values) if values else None,
            mean_saved=statistics.mean(values) if values else None,
            median_saved=statistics.median(values) if values else None,
            incomplete=incomplete, unknown_outcome=unknown, errors=errors))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--history', type=Path, default=Path(__file__).resolve().parents[1]/'analysis/nn_hist3.jsonl')
    args = ap.parse_args()
    rows = [json.loads(line) for line in args.history.read_text(encoding='utf-8').splitlines() if line.strip()]
    groups = aggregate(rows)
    print(json.dumps({'groups': groups,
          'note': 'Success rates use known completed outcomes only. Timeouts, errors and unknowns remain visible. No all-level claim follows from missing levels.'}, indent=2))


if __name__ == '__main__':
    main()
