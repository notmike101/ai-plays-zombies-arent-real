"""Per-episode credit from native civilian positions and safe-zone geometry."""
import numpy as np

from spatial import inside_polygon

CREDIT = .05
BREACH_COST = .10
SAMPLE_SECONDS = .5
PERIMETER_METRES = 150.


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
    def __init__(self, population, *, breach_cost=BREACH_COST):
        if not np.isfinite(breach_cost) or breach_cost < 0:
            raise ValueError('Invalid occupied shelter exposure cost')
        self.population = population
        self.breach_cost = breach_cost
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

    def observe(self, native, sim):
        if not native or sim < self.next_sample:
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
        return credit+penalty

    def perimeter(self, cells, radius=PERIMETER_METRES):
        pressure = np.zeros(len(cells),dtype=np.float32)
        for polygon,occupancy in self.protected:
            segments = np.roll(polygon,-1,axis=0)-polygon
            delta = cells[:,None,:]-polygon
            axis = np.clip((delta*segments).sum(axis=-1)/np.maximum((segments**2).sum(axis=-1),1e-6),0,1)
            distance = ((delta-axis[...,None]*segments)**2).sum(axis=-1).min(axis=1)
            np.maximum(pressure,occupancy*np.maximum(0.,1-np.sqrt(distance)/radius),out=pressure)
        return pressure
