"""Input labels matching nn_play2.make_obs() output order.

MAINTENANCE CONTRACT (root AGENTS.md): any feature add/remove/reorder or
semantic/normalization change in make_obs() MUST update, in the SAME change:
this list, visualizer/test_labels.py EXPECT table, and (on width change)
visualizer/demo.py width. Names embed exact normalization because the browser
renders these strings verbatim as node labels.

Missing-value convention: crowd slots beyond len(blobs) are -1.0 ("nothing
detected"), distinct from a legitimate 0.0 detection; the browser label says
so via the shared '(px / ...)' suffix plus extent feature 26.
"""
INPUT_LABELS = [
    'Civilians alive (log1p)',
    'Zombies alive (log1p)',
    'Converting now (log1p)',
    'Corpses (log1p)',
    'Police alive (log1p)',
    'Money ($ / 1000)',
    'Elapsed time (s / 300, cap 2)',
    'Civilian fraction alive',
    'Zombie trend (per sim s / 1000, clip +-3)',
    'Civilian slope (frac/sim s, clip +-1)',
    'Deck slot 1 castable (charges / max)',
    'Deck slot 2 castable (charges / max)',
    'Deck slot 3 castable (charges / max)',
    'Deck slot 4 castable (charges / max)',
    'Crowd 1 X (client width frac)',
    'Crowd 1 Y (client height frac)',
    'Crowd 1 weight (px / 6000)',
    'Crowd 2 X (client width frac)',
    'Crowd 2 Y (client height frac)',
    'Crowd 2 weight (px / 6000)',
    'Crowd 3 X (client width frac)',
    'Crowd 3 Y (client height frac)',
    'Crowd 3 weight (px / 6000)',
    'Crowd 4 X (client width frac)',
    'Crowd 4 Y (client height frac)',
    'Crowd 4 weight (px / 6000)',
    'Crowd extent (detections / 4)',
    'Previous tool',
    'Previous cell',
    'Purchase succeeded',
    'Planning phase',
    'Budget spent (/ 1, cap 1)',
]

INPUT_LABELS += [f'Grid {channel} cell {i+1} (log1p count)'
                 for channel in ('civilians', 'zombies', 'defenders', 'buildings')
                 for i in range(48)]
INPUT_LABELS += [f'Grid safe zone cell {i+1} (center inside: 0/1)' for i in range(48)]
ABILITY_LABEL_ORDER = ('Police', 'Bomber', 'Heli', 'Stungas', 'Firebomb', 'CallArms',
             'APC', 'Demolition', 'Rally', 'SeekDestroy', 'Bus', 'Missile',
             'Medevac', 'Dozer', 'Cluster', 'Tank', 'AC130', 'Cure', 'Nuke')
for name in ABILITY_LABEL_ORDER:
    INPUT_LABELS += [f'{name} loadout level (/ 10)',
                     f'{name} castable (charges / max)',
                     f'{name} pending arrival (remaining sim s / 60)']
INPUT_LABELS += ['Unspent skill points (/ 10)', 'Geometry anchor tool (/ 72; -1 absent)',
                 'Geometry anchor cell (/ 48; -1 absent)']

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.mechanic_contract import EXTRA_LABELS
INPUT_LABELS += EXTRA_LABELS

OPENING_TIMING_LABELS = [
    label for name in ABILITY_LABEL_ORDER for label in (
        f'{name} equipped and purchased for battle (0/1)',
        f'{name} projected opening unlock (sim s / 60, cap 2; -1 unavailable)',
        f'{name} configured first effect delay (sim s / 60, cap 2; -1 unavailable)')
]
SHELTER_OCCUPANCY_LABEL = 'Living civilians inside closed safe zones (fraction)'
SHELTER_GEOMETRY_LABELS = [
    f'Rectangle shelter cell {cell}: projected additional living civilians (fraction)'
    for cell in range(1, 49)
]


def validate(nobs=None, labels=None):
    """Hard gate before training launch: labels must match model width."""
    labels = INPUT_LABELS if labels is None else labels
    if nobs is not None and len(labels) != nobs:
        raise ValueError(
            f'{len(labels)} input labels vs model width {nobs}: update '
            'visualizer/labels.py in the same change as make_obs()/NOBS')
    if len(set(labels)) != len(labels):
        raise ValueError('duplicate input labels')
    return labels
