"""Small player-view grid from verified native positions, never screenshots."""
import numpy as np

XF = np.linspace(.11, .88, 8)
YF = np.linspace(.16, .76, 6)
NC = 48


def project(points, camera, width, height):
    center = np.asarray(camera[:2])
    return (np.asarray(points).reshape(-1, 2)-center) * [camera[2], -camera[2]] + [width/2, height/2]


def centers(width, height):
    return np.array([(x*width, y*height) for y in YF for x in XF])


def features(points, kinds, rectangles, zones, width, height):
    xy = centers(width, height)
    counts = np.zeros((5, NC), dtype=np.float32)
    targets = [None]*NC
    # Bound the grid to the playable viewport, keeping UI clicks out of actions.
    def indices(pts):
        pts = np.asarray(pts).reshape(-1, 2)
        valid = ((pts[:, 0] >= .055*width) & (pts[:, 0] <= .935*width) &
                 (pts[:, 1] >= .10*height) & (pts[:, 1] <= .80*height))
        col = np.abs(pts[:, :1]/width - XF).argmin(axis=1)
        row = np.abs(pts[:, 1:]/height - YF).argmin(axis=1)
        return row*8+col, valid
    bins, visible = indices(points)
    for channel, mask in enumerate((kinds == 0, kinds == 1, (kinds >= 2) & (kinds != 3))):
        counts[channel] = np.bincount(bins[visible & mask], minlength=NC)
    rectangles = np.asarray(rectangles).reshape(-1, 4)
    mids = (rectangles[:, :2]+rectangles[:, 2:])/2
    bins, visible = indices(mids)
    for point, cell in zip(mids[visible], bins[visible]):
        counts[3, cell] += 1
        old = targets[cell]
        if old is None or np.square(point-xy[cell]).sum() < np.square(old-xy[cell]).sum():
            targets[cell] = point
    for polygon in zones:
        vertices = np.asarray(polygon)
        inside = np.zeros(NC, dtype=bool)
        for a, b in zip(vertices, np.roll(vertices, -1, axis=0)):
            crosses = (a[1] > xy[:, 1]) != (b[1] > xy[:, 1])
            if a[1] != b[1]:
                inside ^= crosses & (xy[:, 0] < (b[0]-a[0])*(xy[:, 1]-a[1])/(b[1]-a[1])+a[0])
        counts[4, inside] = 1
    return {'counts': counts, 'build_targets': targets}
