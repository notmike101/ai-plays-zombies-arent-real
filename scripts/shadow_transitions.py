"""Bounded, observation-only battle transition capture."""

import numpy as np

from spatial import NC, grid_bins, project


def combat_context(native, width, height):
    """Reuse the policy snapshot, without extra game reads."""
    def counts(points):
        pixels = project(points, native['camera'], width, height)
        uv = pixels / [width, height]
        visible = ((uv >= [.055, .10]) & (uv <= [.935, .80])).all(axis=1)
        return np.bincount(grid_bins(pixels[visible], width, height), minlength=NC).tolist()

    units = native['units']
    defenders = (units['kind'] >= 2) & (units['kind'] != 3)
    walls = native['walls']
    zones = native['zones']
    shelter = [zone.tolist() for zone in zones] if sum(map(len, zones)) <= 256 else None
    return dict(
        conversion=counts(units['pos'][units['converting'] != 0]),
        defenders={int(kind): counts(units['pos'][units['kind'] == kind])
                   for kind in np.unique(units['kind'][defenders])},
        wall_midpoints=counts((walls['a'] + walls['b']) / 2),
        shelter_polygons=shelter,
        hazard_centers=counts(native['hazards']['pos']),
        mutation_centers=counts(native['mutations']['pos']),
        helicopter_positions=counts(native['helicopters']['pos'][native['helicopters']['alive'] != 0]),
        terrain=native['terrain']['codes'].tolist(),
        bridges=native['terrain']['bridges'].tolist(),
        fire={name: values.tolist() for name, values in native['fire'].items()},
    )


class TransitionCapture:
    def __init__(self, limit=2048):
        self.limit = limit
        self.states = []
        self.transitions = []
        self.pending = None
        self.truncated = False

    def observe(self, state, decision):
        index = len(self.states)
        if index >= self.limit:
            self.pending = None
            self.truncated = True
            return
        if self.pending is not None:
            dt = state['sim'] - self.states[-1]['sim']
            if dt >= 0:
                self.transitions.append(dict(self.pending, to=index, dt=dt))
        self.states.append(state)
        self.pending = dict(decision, **{'from': index}, receipt={'status': 'unknown'})

    def receipt(self, status, **evidence):
        if self.pending is not None:
            self.pending['receipt'] = dict(status=status, **evidence)
