import numpy as np


def lerp(pt1, pt2, step):
    return [(pt1+p*(pt2-pt1), p) for p in np.arange(0, 1+step, step)]


def segments(start_time, legs, map, step=0.1):
    """break trip into segments, e.g. for visualization purposes"""
    time = start_time
    segs = []
    last = None
    for start, end, edge, travel_time in legs:
        pts = segment_leg(map, start, end, edge)
        segs.extend([[lng, lat, time + (p * travel_time)] for (lat, lng), p in pts])
        if segs:
            last = segs.pop(-1) # first segment is same as last leg's last segment
        time += travel_time
    return segs + [last]


def segment_leg(map, u, v, edge, step=0.1):
    """segments a leg of a trip
    (a leg a part of a trip that corresponds to an edge)"""
    geo = edge.get('geometry')
    if geo is None:
        pt1, pt2 = map.network.nodes[u], map.network.nodes[v]
        pt1 = np.array([pt1['x'], pt1['y']])
        pt2 = np.array([pt2['x'], pt2['y']])
        pts = lerp(pt1, pt2, step=step)
    else:
        pts = [(geo.interpolate(p, normalized=True).coords[0], p)
               for p in np.arange(0, 1+step, step)]
    return [(map.to_latlng(*pt), p) for pt, p in pts]


