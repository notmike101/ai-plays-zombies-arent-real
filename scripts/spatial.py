"""Small player-view grid from verified native positions, never screenshots."""
import numpy as np

XF = np.linspace(.11, .88, 8)
YF = np.linspace(.16, .76, 6)
NC = 48
OVERVIEW_MAX_FILL = 1.09
OVERVIEW_CENTER_TOLERANCE = .028


def overview_geometry(points):
    """Measure the playable bounds in normalized viewport coordinates."""
    lo, hi = points.min(axis=0), points.max(axis=0)
    return max((hi-lo)/[.76, .595]), (hi+lo)/2-[.50, .35]


def project(points, camera, width, height):
    center = np.asarray(camera[:2])
    return (np.asarray(points).reshape(-1, 2)-center) * [camera[2], -camera[2]] + [width/2, height/2]


def centers(width, height):
    return np.array([(x*width, y*height) for y in YF for x in XF])


def grid_bins(points,width,height):
    points=np.asarray(points).reshape(-1,2)
    def nearest(values,axis):
        right=np.clip(np.searchsorted(axis,values),0,len(axis)-1)
        left=np.maximum(right-1,0)
        return np.where(np.abs(values-axis[left])<=np.abs(values-axis[right]),left,right)
    return nearest(points[:,1]/height,YF)*8+nearest(points[:,0]/width,XF)


def closest_indices(points,bins,xy):
    """Linear-time nearest target per cell; ties preserve original entity order."""
    distance=np.square(points-xy[bins]).sum(axis=1)
    minimum=np.full(NC,np.inf);np.minimum.at(minimum,bins,distance)
    candidates=np.flatnonzero(distance==minimum[bins])
    first=np.full(NC,len(points),dtype=np.int64)
    np.minimum.at(first,bins[candidates],candidates)
    return first[first<len(points)]


def inside_polygon(points, vertices):
    points=np.asarray(points).reshape(-1,2);vertices=np.asarray(vertices).reshape(-1,2)
    inside=np.zeros(len(points),dtype=bool)
    for a,b in zip(vertices,np.roll(vertices,-1,axis=0)):
        crosses=(a[1]>points[:,1]) != (b[1]>points[:,1])
        if a[1]!=b[1]:
            inside ^= crosses & (points[:,0] < (b[0]-a[0])*(points[:,1]-a[1])/(b[1]-a[1])+a[0])
    return inside


def features(points, kinds, rectangles, zones, width, height):
    xy = centers(width, height)
    counts = np.zeros((5, NC), dtype=np.float32)
    targets = [None]*NC
    # Bound the grid to the playable viewport, keeping UI clicks out of actions.
    def indices(pts):
        pts = np.asarray(pts).reshape(-1, 2)
        valid = ((pts[:, 0] >= .055*width) & (pts[:, 0] <= .935*width) &
                 (pts[:, 1] >= .10*height) & (pts[:, 1] <= .80*height))
        return grid_bins(pts,width,height), valid
    bins, visible = indices(points)
    for channel, mask in enumerate((kinds == 0, kinds == 1, (kinds >= 2) & (kinds != 3))):
        counts[channel] = np.bincount(bins[visible & mask], minlength=NC)
    rectangles = np.asarray(rectangles).reshape(-1, 4)
    mids = (rectangles[:, :2]+rectangles[:, 2:])/2
    bins, visible = indices(mids)
    points, cells = mids[visible], bins[visible]
    counts[3] = np.bincount(cells, minlength=NC)
    # Stable distance order preserves the first building when distances tie.
    for i in closest_indices(points,cells,xy):
        targets[cells[i]] = points[i]
    for polygon in zones:
        counts[4, inside_polygon(xy,polygon)] = 1
    return {'counts': counts, 'build_targets': targets}
