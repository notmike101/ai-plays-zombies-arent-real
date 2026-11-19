"""Compact projection of observer frames. All vectors are captured values."""
import re
import struct

NONSPATIAL = frozenset((
    'wait', 'ready', 'officer_mode', 'officer_paint', 'arm_detonation',
    'next_special', 'pause_toggle', 'place_click', 'place_paint',
    'zone_finish', 'zone_back', 'cancel_tool', 'undo',
))


def position_kind(tool):
    if tool == 'refund_selection':
        return 'battlefield'
    if tool == 'arm_slot' or tool.startswith('equip_'):
        return 'planning slot'
    if tool.startswith('perk_'):
        return 'perk slot'
    if tool in NONSPATIAL or tool.startswith(('buy_', 'refund_', 'panel_', 'pan_', 'speed_', 'dialog_')):
        return None
    return 'battlefield'


def metadata(frame):
    graph = frame['graph']
    if not isinstance(graph.get('layers'), list):
        raise ValueError('Missing observer layers')
    layers = {layer['id']: layer for layer in graph['layers']}
    return {
        'input_labels': layers.get('input', {}).get('labels', []),
        'tools': layers.get('hu', {}).get('labels', []),
        'gru': next((name for name, layer in layers.items() if layer.get('kind') == 'gru'), 'gru'),
        'architecture': graph.get('architecture', 'GRU + linear heads'),
        'parameters': graph.get('parameters'),
        'matrices': graph.get('matrices', {}),
        'policy_id': graph.get('policy_id'),
        'team_id': graph.get('team_id'),
        'forecast_id': graph.get('forecast_id'),
        'label_warning': frame.get('label_warning'),
    }


def decision(frame, meta, skipped):
    selected, probs, values = frame['selected'], frame['probabilities'], frame['values']
    tool, flat = selected.get('hu'), selected.get('hc')
    labels = meta['tools']
    name = labels[tool] if isinstance(tool, int) and 0 <= tool < len(labels) else ''
    cells = probs.get('hc', [])
    # Schema 4 emits selected_tool * 48 + cell, with one populated probability row.
    conditional = bool(labels and len(cells) == len(labels) * 48)
    if conditional and isinstance(flat, int) and flat >= 0 and flat // 48 == tool and flat < len(cells):
        offset = tool * 48
        slot = flat % 48
        kind = position_kind(name)
        location = cells[offset:offset + 48] if kind else []
        location_logits = values.get('hc', [])[offset:offset + 48] if kind else []
    else:
        slot, kind, location, location_logits = None, None, [], []
        if frame.get('preview') and isinstance(flat, int) and 0 <= flat < len(cells) == 12 and position_kind(name):
            slot, kind, location, location_logits = flat, 'synthetic grid', cells, values.get('hc', [])
    episode = frame.get('episode', '')
    stage = re.fullmatch(r'search/\d+/L(\d+)/a\d+', episode)
    return {
        **{key: frame.get(key) for key in ('stream', 'sequence', 'timestamp', 'model_revision',
                                          'worker_pid', 'game_pid', 'phase', 'episode',
                                          'decision', 'decision_interval_ms', 'preview')},
        'stage': frame.get('stage', int(stage[1]) if stage else None),
        'campaign': frame.get('campaign', 'Boston, MA' if stage else None),
        'policy_mode': frame.get('policy_mode', 'greedy' if stage else None),
        'skipped': skipped, 'tool': tool, 'action': name or None, 'position_kind': kind,
        'position': slot if kind else None, 'location_probabilities': location,
        'location_logits': location_logits,
        'input': values.get('input', []), 'hidden': values.get(meta['gru'], []),
        'memory': values.get('memory', []), 'tool_logits': values.get('hu', []),
        'tool_probabilities': probs.get('hu', []), 'value': next(iter(values.get('val', [])), None),
    }


def summary(sample):
    return {key: sample[key] for key in ('sequence', 'action', 'phase', 'model_revision', 'skipped',
                                         'timestamp', 'decision', 'hidden', 'position_kind', 'position')}


def weight_tile(directory, sample, meta, matrix, row, column):
    stream, revision = sample['stream'], sample['model_revision']
    shape = meta['matrices'].get(matrix)
    if (not isinstance(shape, list) or len(shape) != 3
            or not all(type(n) is int for n in shape)
            or not isinstance(stream, str) or not re.fullmatch(r'\d+-[0-9a-f]{12}', stream)
            or not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{16}', revision)):
        return None
    rows, cols, offset = shape
    if not (0 <= row < rows and 0 <= column < cols and 0 <= offset
            and offset + rows * cols * 4 <= 32 * 1024 * 1024):
        return None
    path = directory / f'{stream}-{revision}.weights'
    width = min(32, cols - column)
    decode = struct.Struct(f'<{width}f')
    try:
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            return None
        with path.open('rb') as source:
            values = []
            for i in range(row, min(row + 16, rows)):
                source.seek(offset + (i * cols + column) * 4)
                values.append(list(decode.unpack(source.read(decode.size))))
        return {'matrix': matrix, 'rows': rows, 'columns': cols, 'row': row,
                'column': column, 'values': values}
    except (OSError, struct.error):
        return None
