import utm
import math
import config
from geohash import encode
from road.quadtree import QuadTree


class ZoneGrid:
    def __init__(self, geo, cell_size):
        """indexes a geography as a UTM
        grid with the specified cell size (in meters).
        Query with idx.intersect(bounds)"""
        self.cell_size = cell_size
        x1, y1, zone_no, zone_let = utm.from_latlon(*geo.bounds[:2])
        x2, y2, zone_no, zone_let = utm.from_latlon(*geo.bounds[2:])
        self.bbox = (x1, y1, x2, y2)
        idx = QuadTree.from_bbox(self.bbox)
        self.w = x2 - x1
        self.h = y2 - y1
        self.per_row = math.ceil(self.w/cell_size)
        self.per_col = math.ceil(self.h/cell_size)
        for y in range(0, self.per_col):
            for x in range(0, self.per_row):
                i = x + y*self.per_row
                bx1 = x1 + x*cell_size
                bx2 = bx1 + cell_size
                by1 = y1 + y*cell_size
                by2 = by1 + cell_size
                idx.insert(i, (bx1, by1, bx2, by2))
        self.idx = idx

    def lookup(self, lat, lon):
        x, y, zone_no, zone_let = utm.from_latlon(lat, lon)
        matches = self.idx.intersect((x, y, x, y))
        i = matches.pop(0)
        x = i % self.per_row
        y = math.floor(i / self.per_row)
        return x, y


def geohash(lat, lon, precision=config.GEOHASH_PRECISION):
    """
    precision   km (approx)
    1           ±2500
    2           ±630
    3           ±78
    4           ±20
    5           ±2.4
    6           ±0.61
    7           ±0.076
    8           ±0.019
    9           ±0.0024
    10          ±0.00060
    11          ±0.000074
    """
    return encode(lat, lon, precision)

