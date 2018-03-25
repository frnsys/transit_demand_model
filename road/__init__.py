"""
network types:
- 'drive' – get drivable public streets (but not service roads)
- 'drive_service' – get drivable public streets, including service roads
- 'walk' – get all streets and paths that pedestrians can use (this network type ignores one-way directionality)
- 'bike' – get all streets and paths that cyclists can use
- 'all' – download all (non-private) OSM streets and paths
- 'all_private' – download all OSM streets and paths, including private-access ones
<http://geoffboeing.com/2016/11/osmnx-python-street-networks/>

edge attributes (may not all be present):
- maxspeed (str)
- length (float)
- oneway (bool)
- highway (str or list of strs, one of 'residential', 'secondary', tertiary', 'trunk',
  'primary', 'motorway', 'unclassified', and any of those followed with '_link')
- lanes (str or list of str)
- access (str)
- junction (str)
- tunnel (str, e.g. 'yes')
- bridge (str, e.g. 'yes', 'viaduct')
"""

import os
import math
import config
import pyproj
import logging
import requests
import osmnx as ox
import numpy as np
from tqdm import tqdm
from .router import Router
from shapely import geometry
from .quadtree import QuadTree
from collections import defaultdict
from recordclass import recordclass

logger = logging.getLogger(__name__)

OSM_NOMINATIM = 'https://nominatim.openstreetmap.org/search'
ox.settings.data_folder = 'data/networks'
geo_proj = pyproj.Proj({'init':'epsg:4326'}, preserve_units=True)

Edge = recordclass('Edge', ['id', 'frm', 'to', 'no', 'data', 'p', 'pt'])


def lookup_place(place):
    params = {'q': place, 'format': 'json'}
    resp = requests.get(OSM_NOMINATIM, params=params)
    results = resp.json()
    return results[0]


class Roads():
    """manages the road network"""

    def __init__(self, place, transit=None, distance=10000):
        self.place = place
        self.transit = transit
        self.id = place.lower().replace(' ', '_')
        self.place_meta = lookup_place(place)
        xmin, xmax, ymin, ymax = [float(p) for p in self.place_meta['boundingbox']] # lat lon
        self.bbox = (xmin, ymin, xmax, ymax)

        if os.path.exists(os.path.join(ox.settings.data_folder, self.id)):
            logger.info('Loading existing network')
            G = ox.load_graphml(self.id)
        else:
            # the first search result isn't always what we want
            # so keep trying until we find something that clicks
            # see: <https://github.com/gboeing/osmnx/issues/16>
            # a more likely problem is that a place is returned as a point
            # rather than a shape, so we fall back to `graph_from_address`
            try:
                logger.info('Downloading network')
                G = ox.graph_from_place(place, network_type='drive', simplify=True)
            except ValueError:
                print('Shape was not found for "{}"'.format(place))
                print('Falling back to address search at distance={}'.format(distance))
                G = ox.graph_from_address(place, network_type='drive', simplify=True, distance=distance)
            G = ox.project_graph(G)
            ox.save_graphml(G, filename=self.id)

        crs = G.graph['crs']
        self.utm_proj = pyproj.Proj(crs, preserve_units=True)
        self.network = G

        self._prepare_network()
        self.router = Router(self)

    def to_xy(self, lat, lon):
        return pyproj.transform(geo_proj, self.utm_proj, lon, lat)

    def to_latlon(self, x, y):
        lon, lat = pyproj.transform(self.utm_proj, geo_proj, x, y)
        return lat, lon

    def nearest_node(self, coord):
        """find the nearest node in the road
        network to the given coordinate"""
        pos = self.to_xy(*coord)
        # pos = pos[::-1] # should be y, x TODO check this
        n, dist = ox.get_nearest_node(self.network, pos, method='euclidean', return_dist=True)
        return self.network.nodes[n]

    def _infer_transit_stops(self):
        """map public transit stops to road network positions"""
        self.stops = {}
        if self.transit is not None:
            logger.info('Inferring transit stop network positions...')
            for i, r in tqdm(self.transit.stops.iterrows(), total=len(self.transit.stops)):
                coord = r.stop_lat, r.stop_lon
                self.stops[i] = self.find_closest_edge(coord)

    def _prepare_network(self):
        """preprocess the network as needed"""
        # some `maxspeed` edge attributes are missing
        # (in particular, `highway=residential` are missing them)
        # do our best to estimate the missing values
        self.edges = {}
        missing_speeds = []
        impute_speeds = defaultdict(list)

        # setup quadtree
        logger.info('Preparing quadtree index...')
        self.idx = self._make_qt_index()

        # map public transit stops to road network
        self._infer_transit_stops()

        # add occupancy to edges
        # and impute values where possible
        logger.info('Preparing edges...')
        for e, d in tqdm(self.network.edges.items()):
            # <https://wiki.openstreetmap.org/wiki/Josm/styles/lane_features>
            lanes = d.get('lanes', 1)
            if isinstance(lanes, str):
                lanes = int(lanes)
            elif isinstance(lanes, list):
                # just add up lanes if multiple are listed
                # TODO not sure if this is appropriate
                lanes = sum(int(l) for l in lanes)

            # sometimes this `lanes` value is set to `-1`,
            # unclear why. the link above gives some hint that
            # it's data misentry?
            d['lanes'] = max(lanes, 1)

            # track which edges we need to
            # impute `maxspeed` data for
            if 'maxspeed' not in d:
                missing_speeds.append(d)
            else:
                highway = d['highway']
                maxspeed = d['maxspeed']
                if isinstance(maxspeed, list):
                    # TODO if multiple speeds are listed,
                    # take the average -- does this make sense?
                    maxspeed = sum(int(s) for s in maxspeed)/len(maxspeed)
                else:
                    maxspeed = int(maxspeed)
                if not isinstance(highway, list):
                    highway = [highway]
                for hw in highway:
                    impute_speeds[hw].append(maxspeed)
                d['maxspeed'] = maxspeed

            # estimate vehicle capacity
            # TODO this is made up for now
            capacity = math.ceil(d['length']/20 * d['lanes'])

            d.update({
                'occupancy': 0,
                'capacity': capacity
            })

        # impute missing speeds
        for d in missing_speeds:
            highway = d['highway']
            if isinstance(highway, list):
                speeds = []
                for hw in highway:
                    speeds.extend(impute_speeds[hw])
            else:
                speeds = impute_speeds[highway]
            try:
                d['maxspeed'] = sum(speeds)/len(speeds)
            except ZeroDivisionError:
                d['maxspeed'] = config.DEFAULT_ROAD_SPEED

    def _make_qt_index(self):
        """create the quadtree index"""
        # in lat, lon
        idx = QuadTree.from_bbox(self.bbox)
        # idx = Index(self.bbox)
        for i, (e, data) in tqdm(enumerate(self.network.edges.items()), total=len(self.network.edges.items())):
            if 'geometry' not in data:
                u = self.network.nodes[e[0]]
                v = self.network.nodes[e[1]]
                line = geometry.LineString([
                    (u['x'], u['y']),
                    (v['x'], v['y'])
                ])
                data['geometry'] = line
            else:
                line = data['geometry']
            # in x,y, convert to lat,lon
            bounds = line.bounds
            a = self.to_latlon(bounds[0], bounds[1])
            b = self.to_latlon(bounds[2], bounds[3])
            bounds = (
                a[0] - config.BOUND_RADIUS,
                a[1] - config.BOUND_RADIUS,
                b[0] + config.BOUND_RADIUS,
                b[1] + config.BOUND_RADIUS)

            u, v, edge_no = e
            idx.insert(i, bounds)
            self.edges[i] = (u, v, edge_no, data)
        return idx

    def find_closest_edge(self, coord):
        """given a query point, will find
        the closest edge/path in the self to that point,
        as well as the closest point on that edge
        (described as a 0-1 position along that edge,
        e.g. 0.5 means halfway along that edge)"""
        pt = self.to_xy(*coord)
        pt = geometry.Point(*pt)

        idx = None
        r = config.BOUND_RADIUS
        while idx is None:
            bounds = coord[0]-r, coord[1]-r, coord[0]+r, coord[1]+r

            # find closest box
            matches = self.idx.intersect(bounds)

            # find closest edge
            if not matches:
                r *= 2 # expand search area
                continue

            idx = min(matches, key=lambda i: self.edges[i][-1]['geometry'].distance(pt))
        u, v, edge_no, edge_data = self.edges[idx]

        # find closest point on closest edge
        line = edge_data['geometry']
        p = line.project(pt, normalized=True)
        pt = line.interpolate(p, normalized=True)
        edge = Edge(id=idx, frm=u, to=v, no=edge_no, data=edge_data, p=p, pt=pt)

        return edge

    def route(self, start, end):
        return self.router.route(start, end)

    def route_bus(self, start_stop, end_stop):
        start_edge = self.stops[start_stop]
        end_edge = self.stops[end_stop]
        return self.router.route_edges(start_edge, end_edge)

    def segments(self, legs, step=0.1):
        """break trip into segments, e.g. for visualization purposes"""
        segs = []
        last = None
        for time, travel_time, edge in legs:
            pts = self.segment_leg(edge.frm, edge.to, edge.edge_no)
            # TODO coordinate ordering??
            segs.extend([[lon, lat, time + (p * travel_time)] for (lat, lon), p in pts])
            if segs:
                last = segs.pop(-1) # first segment is same as last leg's last segment
        return segs + [last]

    def segment_leg(self, u, v, edge_no, step=0.1):
        """segments a leg of a trip
        (a leg a part of a trip that corresponds to an edge)"""
        edge = self.network.get_edge_data(u, v, key=edge_no)
        geo = edge.get('geometry')
        if geo is None:
            pt1, pt2 = self.network.nodes[u], self.network.nodes[v]
            pt1 = np.array([pt1['x'], pt1['y']])
            pt2 = np.array([pt2['x'], pt2['y']])
            pts = lerp(pt1, pt2, step=step)
        else:
            pts = [(geo.interpolate(p, normalized=True).coords[0], p)
                for p in np.arange(0, 1+step, step)]
        return [(self.to_latlon(*pt), p) for pt, p in pts]


def lerp(pt1, pt2, step):
    return [(pt1+p*(pt2-pt1), p) for p in np.arange(0, 1+step, step)]
