"""Input labels matching nn_play2.make_obs() output order (NOBS=32).

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
    'Zombie trend (k/s / 1000, clip +-3)',
    'Civilian slope (frac/s, clip +-1)',
    'CTA charges (/ 2)',
    'Helicopter active',
    'Rally charges (/ 3)',
    'Medevac+Seek combined (/ 8)',
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
