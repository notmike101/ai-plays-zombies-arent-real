"""Per-episode credit from native civilian positions and safe-zone geometry."""
import hashlib

import numpy as np

from spatial import inside_polygon
CREDIT = .05


BREACH_COST = .10
SAMPLE_SECONDS = .5
DURATION_MAX_INTERVAL = 1.25
DURATION_CAP = 30.
PERIMETER_METRES = 150.
ZONE_TRACE_LIMIT = 240
TRACE_GAP_S = 1.25
TRACE_RING_METRES = (30., 60., 120.)


def garrison_reach(area, base, per_metre, cap):
    """Derive firing radius from the native building footprint."""
    area = np.asarray(area)
    valid = np.isfinite(area) & (area > 0.)
    radius = base + per_metre * np.sqrt(np.where(valid, area, 0.))
    if cap > 0.:
        radius = np.minimum(radius, cap)
    return np.where(valid, radius, 0.)


def garrison_perimeter_gain(zones, existing, targets, radius, existing_radius=None):
    """Estimate the additional perimeter reached by each placement."""
    polygons = [p for p in zones if len(p) >= 3]
    if not polygons or not len(targets):
        return np.zeros(len(targets), dtype=np.float32)
    starts = np.concatenate(polygons)
    edges = np.concatenate([np.roll(p, -1, axis=0) - p for p in polygons])
    lengths = np.linalg.norm(edges, axis=1)
    cumulative = np.cumsum(lengths)
    if cumulative[-1] <= 0:
        return np.zeros(len(targets), dtype=np.float32)
    samples = (np.arange(96) + .5) * cumulative[-1] / 96
    bins = np.searchsorted(cumulative, samples, side='right')
    fraction = (samples - cumulative[bins] + lengths[bins]) / lengths[bins]
    points = starts[bins] + fraction[:, None] * edges[bins]
    if existing_radius is None:
        existing_radius = radius
    if len(existing):
        existing_radius2 = np.asarray(existing_radius) ** 2
        covered = ((points[:, None] - existing) ** 2).sum(axis=-1) <= existing_radius2
        covered &= existing_radius2 > 0.
        points = points[~covered.any(axis=1)]
    radius2 = np.broadcast_to(np.asarray(radius) ** 2, (len(targets),))
    reached = ((targets[:, None] - points) ** 2).sum(axis=-1) <= radius2[:, None]
    reached &= radius2[:, None] > 0.
    return (reached.sum(axis=1) / len(samples)).astype(np.float32)


class Shelter:
    def __init__(self, population, *, breach_cost=BREACH_COST, duration_rate=None,
                 trace=False):
        if not np.isfinite(breach_cost) or breach_cost < 0:
            raise ValueError('Invalid occupied shelter exposure cost')
        self.population = population
        self.breach_cost = breach_cost
        if duration_rate is not None and (not np.isfinite(duration_rate) or duration_rate < 0):
            raise ValueError('Invalid shelter duration rate')
        self.duration_rate = duration_rate
        self.duration_sample = None
        self.occupant_seconds = 0.
        self.duration_intervals = 0
        self.duration_credit = 0.
        self.next_sample = 0.
        self.previous = {}
        self.breached = set()
        self.credited = set()
        self.exposed = set()
        self.active_exposure = set()
        self.breach_exposures = 0
        self.presence_credit = 0.
        self.breach_penalty = 0.
        self.occupied_breaches = 0
        self.first_occupied_breach = None
        self.protected = []
        # Opt-in passive observation only: tracing never touches reward math,
        # sets, or RNG, and reads nothing beyond the native snapshot handed
        # to observe(). Recorded observations describe samples; claims about
        # transients between samples are never made.
        self.trace = bool(trace)
        self.zone_samples = []
        self.breach_rows = []
        self.trace_gaps = []
        self.trace_dropped = 0
        self.trace_gap_dropped = 0
        self._trace_prev = None
        self._trace_breached = set()
        self._stamp = 0

    @property
    def duration_basis(self):
        return min(self.occupant_seconds / self.population, DURATION_CAP)

    def observe(self, native, sim):
        if not native:
            self.duration_sample = None
            if self.trace and self._trace_prev is not None:
                self._append_gap(dict(kind='gap', reason='missing_native_snapshot',
                                      last_observed_sim=self._trace_prev, resumed_sim=None))
                self._trace_prev = None
            return 0.
        if sim < self.next_sample:
            return 0.
        self.next_sample = sim + SAMPLE_SECONDS
        units = native['units']
        civilians = units['kind']==0
        ids = units['id'][civilians]
        positions = units['pos'][civilians]
        zombies = units['pos'][units['kind']==1]
        previous = {}
        exposed = set()
        sheltered = set()
        in_breached_zone = set()
        self.protected = []
        for polygon in native['zones']:
            if len(polygon)<3:
                continue
            key = polygon.tobytes()
            lower,upper = polygon.min(axis=0),polygon.max(axis=0)
            in_box = ((positions>=lower)&(positions<=upper)).all(axis=1)
            occupants = set(ids[in_box][inside_polygon(positions[in_box],polygon)].tolist())
            if key in self.breached:
                in_breached_zone.update(occupants & self.active_exposure)
                continue
            in_box = ((zombies>=lower)&(zombies<=upper)).all(axis=1)
            if np.count_nonzero(inside_polygon(zombies[in_box],polygon))>=3:
                if key in self.previous:
                    self.breached.add(key)
                    if occupants:
                        exposed.update(occupants)
                        self.occupied_breaches += 1
                        if self.first_occupied_breach is None:
                            self.first_occupied_breach = sim
                continue
            previous[key] = occupants
            sheltered.update(occupants & self.previous.get(key,set()))
            if occupants:
                self.protected.append((polygon,min(1.,len(occupants)/(.10*self.population))))
        self.previous = previous
        new = sheltered-self.credited
        self.credited.update(new)
        credit = CREDIT*len(new)/self.population
        # Rearm only after reaching intact shelter away from a previous breach.
        safe_again = sheltered-in_breached_zone-exposed
        self.active_exposure.difference_update(safe_again)
        newly_exposed = exposed-self.active_exposure
        self.active_exposure.update(newly_exposed)
        self.exposed.update(newly_exposed)
        self.breach_exposures += len(newly_exposed)
        penalty = -self.breach_cost*len(newly_exposed)/self.population
        self.presence_credit += credit
        self.breach_penalty += penalty
        duration = 0.
        if self.duration_rate is not None:
            if self.duration_sample is not None:
                elapsed = sim - self.duration_sample
                if 0. < elapsed <= DURATION_MAX_INTERVAL:
                    self.duration_intervals += 1
                    self.occupant_seconds += elapsed * len(sheltered)
                    updated = self.duration_rate * self.duration_basis
                    duration = updated - self.duration_credit
                    self.duration_credit = updated
            self.duration_sample = sim
        if self.trace:
            self._trace_sample(native, sim)
        return credit+penalty+duration

    def _append_gap(self, row):
        if len(self.trace_gaps) < 16:
            self.trace_gaps.append(row)
        else:
            self.trace_gap_dropped += 1

    @staticmethod
    def _edge_distances(points, polygon):
        segments = np.roll(polygon, -1, axis=0) - polygon
        delta = points[:, None, :] - polygon
        axis = np.clip((delta * segments).sum(axis=-1) /
                       np.maximum((segments ** 2).sum(axis=-1), 1e-6), 0, 1)
        return np.sqrt(((delta - axis[..., None] * segments) ** 2).sum(axis=-1)).min(axis=1)

    def _trace_sample(self, native, sim):
        if self._trace_prev is not None and sim - self._trace_prev > TRACE_GAP_S:
            self._append_gap(dict(kind='gap', reason='sample_spacing',
                                  last_observed_sim=self._trace_prev, resumed_sim=float(sim)))
        self._trace_prev = sim
        units = native['units']
        civilians = units['kind'] == 0
        ids = units['id'][civilians]
        positions = units['pos'][civilians]
        zombies = units['pos'][units['kind'] == 1]
        zones, key_polygons = [], {}
        for polygon in native['zones']:
            if len(polygon) < 3:
                continue
            key = polygon.tobytes()
            key_polygons[key] = polygon
            lower, upper = polygon.min(axis=0), polygon.max(axis=0)
            in_box = ((positions >= lower) & (positions <= upper)).all(axis=1)
            occupants = set(ids[in_box][inside_polygon(positions[in_box], polygon)].tolist())
            in_box = ((zombies >= lower) & (zombies <= upper)).all(axis=1)
            inside_mask = np.zeros(len(zombies), dtype=bool)
            inside_mask[in_box] = inside_polygon(zombies[in_box], polygon)
            outside = zombies[~inside_mask]
            if len(outside):
                distance = self._edge_distances(outside, polygon)
                rings = [int(np.count_nonzero(distance <= limit))
                         for limit in TRACE_RING_METRES]
                minimum = float(distance.min())
            else:
                rings = [0, 0, 0]
                minimum = None
            zones.append(dict(zone=hashlib.sha1(key).hexdigest()[:12],
                              occupants=len(occupants),
                              zombies_inside=int(np.count_nonzero(inside_mask)),
                              zombies_within_30m=rings[0], zombies_within_60m=rings[1],
                              zombies_within_120m=rings[2],
                              nearest_outside_metres=minimum,
                              breached=int(key in self.breached)))
        if zones:
            row = dict(sim=float(sim),
                       tick=int(native['tick']) if 'tick' in native else None,
                       decision=None, selected_tool=None, selected_cell=None,
                       legal_casts=None, stock=None, zones=zones)
            if len(self.zone_samples) < ZONE_TRACE_LIMIT:
                self.zone_samples.append(row)
            else:
                self.trace_dropped += 1
        for key in self.breached - self._trace_breached:
            polygon = key_polygons.get(key)
            if polygon is None:
                continue
            lower, upper = polygon.min(axis=0), polygon.max(axis=0)
            in_box = ((positions >= lower) & (positions <= upper)).all(axis=1)
            occupants = ids[in_box][inside_polygon(positions[in_box], polygon)]
            if len(self.breach_rows) < 16:
                self.breach_rows.append(dict(
                    sim=float(sim),
                    tick=int(native['tick']) if 'tick' in native else None,
                    zone=hashlib.sha1(key).hexdigest()[:12], breach=1,
                    occupants_at_first_observed_breach=int(len(occupants))))
            else:
                self.trace_gap_dropped += 1
        self._trace_breached = set(self.breached)

    def stamp(self, decision, tool, cell, legal_casts, stock):
        if not self.trace:
            return
        while self._stamp < len(self.zone_samples):
            sample = self.zone_samples[self._stamp]
            self._stamp += 1
            if sample['decision'] is not None:
                continue
            sample.update(decision=int(decision), selected_tool=str(tool),
                          selected_cell=int(cell),
                          legal_casts=sorted(str(name) for name in legal_casts),
                          stock={str(name): float(count) for name, count in stock.items()})

    def perimeter(self, cells, radius=PERIMETER_METRES):
        pressure = np.zeros(len(cells),dtype=np.float32)
        for polygon,occupancy in self.protected:
            segments = np.roll(polygon,-1,axis=0)-polygon
            delta = cells[:,None,:]-polygon
            axis = np.clip((delta*segments).sum(axis=-1)/np.maximum((segments**2).sum(axis=-1),1e-6),0,1)
            distance = ((delta-axis[...,None]*segments)**2).sum(axis=-1).min(axis=1)
            np.maximum(pressure,occupancy*np.maximum(0.,1-np.sqrt(distance)/radius),out=pressure)
        return pressure
