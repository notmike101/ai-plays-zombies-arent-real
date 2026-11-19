"""Read the trainer's existing, allowlisted results with bounded reads."""
from collections import deque
import json
import math
import re

READ_BYTES = 4 * 1024 * 1024
TRIALS = 100
ACTIONS = ('decisions', 'cast_available', 'cast_sampled', 'stock_decreased')
PARAMETERS = ('plan', 'battle', 'cast_bias', 'idle_bias', 'camera_pause', 'blocked_tool',
              'layout', 'later_layouts', 'refuge', 'stage_battle')


def parse(raw):
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError(value)
        return parsed
    try:
        data = json.loads(raw, parse_float=finite_float, parse_constant=finite_float)
        if isinstance(data, dict):
            return data
    except (ValueError, RecursionError):
        pass
    return None


def lines(path, limit):
    try:
        if path.is_symlink() or path.resolve().parent != path.parent.resolve():
            return []
        with path.open('rb') as file:
            start = max(0, file.seek(0, 2) - READ_BYTES)
            file.seek(start)
            rows = file.read(READ_BYTES).splitlines()
        rows = rows[1:] if start else rows
        return [row for raw in rows[-limit:] if (row := parse(raw)) is not None]
    except OSError:
        return []


def pick(data, keys):
    return {key: data[key] for key in keys if key in data}


def valid_score(value):
    return type(value) in (int, float) and 0 <= value <= 1


def outcome(row, *, cohort, stage, saved):
    end = row.get('end') or ('error' if row.get('err') else 'unknown')
    score = saved if end in ('won', 'lost', 'aborted') and valid_score(saved) else None
    usage = row.get('battle_actions')
    rewards = row.get('reward_components')
    return {
        **pick(row, ('campaign', 'start_kind', 'board_id', 'board', 'outbreak', 'timeout_phase',
                     'timeout_reason', 'attempt', 'run_id', 'round', 'mode', 'checkpoint_id',
                     'level', 'pid', 'log_started', 'seed', 'R')),
        'cohort': cohort, 'stage': stage, 'end': end, 'saved': None if end == 'aborted' else score,
        'at_retry': score if end == 'aborted' else None,
        'qualifies': end == 'won' and row.get('win') is True and score is not None and score >= .35,
        'usage': pick(usage, ACTIONS) if isinstance(usage, dict) else {},
        'reward': pick(rewards, ('infections', 'terminal')) if isinstance(rewards, dict) else {},
    }


def campaign_trials(directory):
    return [(cohort, trial)
            for file, cohort in [('trials.jsonl', 'Training trial'), ('holdout.jsonl', 'Held-out')]
            for trial in lines(directory / file, TRIALS)]


def campaign_outcomes(trials):
    for cohort, trial in trials:
        context = pick(trial, ('team_id', 'generation', 'arm', 'view_revision', 'seed', 'copy'))
        levels = trial.get('levels', [])
        for row in levels[:20] if isinstance(levels, list) else []:
            if isinstance(row, dict):
                yield {**outcome(row, cohort=cohort, stage=row.get('stage'), saved=row.get('saved')), **context}
        if trial.get('error'):
            yield {**outcome({}, cohort=cohort, stage=trial.get('failed_stage'), saved=None),
                   **context, 'end': 'error',
                   'start_kind': ('carry' if trial.get('failed_attempt', 0) else 'unknown')}


def overview(rows, run_id):
    runs = {}
    for row in rows:
        key = run_id(row)
        if not isinstance(key, str) or not key:
            continue
        run = runs.setdefault(key, {'id': key, 'started_at': None, 'groups': {}})
        started = row.get('log_started')
        if type(started) in (int, float) and 0 < started <= 8_640_000_000_000_000:
            if run['started_at'] is None or started < run['started_at']:
                run['started_at'] = started
        if row['saved'] is None:
            continue
        start = row.get('start_kind')
        stage = row.get('stage')
        group = (row['cohort'], start if isinstance(start, str) else None, stage if type(stage) is int else None)
        totals = run['groups'].setdefault(group, [0, 0])
        totals[0] += row['saved']
        totals[1] += 1
    return sorted((
        {**run, 'groups': [{'cohort': cohort, 'start_kind': start, 'stage': stage, 'mean': total / count, 'count': count}
                           for (cohort, start, stage), (total, count) in run['groups'].items()]}
        for run in runs.values() if run['started_at'] is not None and run['groups']),
        key=lambda run: (run['started_at'], run['id']))


def campaign_results(directory, trials, outcomes):
    teams = {}
    incumbent, leader, fitness = [next(iter(lines(directory / (name + '.json'), 1)), {})
                                  for name in ('champion', 'provisional', 'fitness')]

    def team(row):
        key, parameters = row.get('team_id'), row.get('team')
        if isinstance(key, str) and isinstance(parameters, dict):
            team_record = pick(row, ('team_id', 'generation', 'parent_id', 'parent_ids', 'parents'))
            # Layouts can be large. Keep bounded parameter snapshots for comparison.
            team_record['parameters'] = {name: value for name, value in pick(parameters, PARAMETERS).items()
                                         if len(json.dumps(value)) <= 60_000}
            teams[key] = team_record

    for _, trial in trials:
        team(trial)
    for row in (leader, incumbent):
        team(row)
    return {
        'id': directory.name, 'incumbent': pick(incumbent, ('team_id', 'base', 'generation',
                      'fresh_stages', 'holdout_stage', 'holdout_opponent')),
        'leader': pick(leader, ('team_id', 'base')), 'camera_revision': fitness.get('view_revision'),
        'outcomes': list(outcomes), 'teams': list(teams.values())[-24:],
    }


def read_results(root, run=None):
    directories = []
    for path in root.glob('coverage-team-*'):
        if not re.fullmatch(r'coverage-team-[a-f0-9]{10}', path.name):
            continue
        try:
            if path.is_dir() and not path.is_symlink() and path.resolve().parent == root.resolve():
                newest = max((p.stat().st_mtime for p in path.iterdir()
                              if p.name in ('trials.jsonl', 'holdout.jsonl', 'champion.json')), default=0)
                directories.append((newest, path))
        except OSError:
            pass
    directories.sort(reverse=True)
    paths = {path.name: path for _, path in directories[:16]}
    selected = paths.get(run) if run is not None else next(iter(paths.values()), None)
    rows = lines(root / 'nn_hist4.jsonl', 1500)
    ppo, updates = deque(maxlen=400), deque(maxlen=60)
    for row in rows:
        if row.get('kind') == 'episode':
            ppo.append(outcome(row, cohort='PPO ' + str(row.get('mode') or 'unknown'),
                               stage=row.get('scenario'), saved=row.get('saved_frac')))
        elif row.get('kind') == 'update':
            updates.append(pick(row, ('run_id', 'round', 'scenario', 'checkpoint_id', 'loss',
                                      'approx_kl', 'clip_fraction', 'entropy', 'explained_variance')))
    campaigns, campaign_overview = [], []
    for path in paths.values():
        trials = campaign_trials(path)
        outcomes = deque(campaign_outcomes(trials), maxlen=400)
        campaign_overview.extend(overview(outcomes, lambda _: path.name))
        if path == selected:
            campaigns.append(campaign_results(path, trials, outcomes))
    campaign_overview.sort(key=lambda run: (run['started_at'], run['id']))
    return {'version': 1, 'ppo': list(ppo), 'updates': list(updates), 'runs': list(paths), 'campaigns': campaigns,
            'overview': {'campaign': campaign_overview, 'ppo': overview(ppo, lambda row: row.get('run_id'))}}
