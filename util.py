import random
from shapely.geometry import Point

def random_point(geo):
    """rejection sample a point within geo shape"""
    minx, miny, maxx, maxy = geo.bounds
    point = None
    while point is None:
        lat = random.uniform(minx, maxx)
        lon = random.uniform(miny, maxy)
        pt = Point(lat, lon)
        if geo.contains(pt):
            point = (lat, lon)
    return point

