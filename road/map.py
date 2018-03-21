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
import json
import pyproj
import hashlib
import logging
import requests
import osmnx as ox
from tqdm import tqdm
from .router import Router
from pyqtree import Index
from shapely import geometry
from collections import defaultdict

logger = logging.getLogger(__name__)

OSM_NOMINATIM = 'https://nominatim.openstreetmap.org/search'
DEFAULT_SPEED = 30
ox.settings.data_folder = 'data/networks'
geo_proj = pyproj.Proj({'init':'epsg:4326'}, preserve_units=True)
BOUND_RADIUS = 0.01 # TODO tweak this


def lookup_place(place):
    params = {'q': place, 'format': 'json'}
    resp = requests.get(OSM_NOMINATIM, params=params)
    results = resp.json()
    return results[0]


class Map():
    def __init__(self, place, transit=None, distance=10000):
        self.place = place
        self.transit = transit
        self.id = hashlib.md5(place.encode('utf8')).hexdigest()
        self.place_meta = lookup_place(place)
        xmin, xmax, ymin, ymax = [float(p) for p in self.place_meta['boundingbox']] # lat lng
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
        self.router = Router(self.network)

    def to_xy(self, lat, lng):
        return pyproj.transform(geo_proj, self.utm_proj, lng, lat)

    def to_latlng(self, x, y):
        lng, lat = pyproj.transform(self.utm_proj, geo_proj, x, y)
        return lat, lng

    def nearest_node(self, coord):
        pos = self.to_xy(*coord)
        # pos = pos[::-1] # should be y, x TODO check this
        n, dist = ox.get_nearest_node(self.network, pos, method='euclidean', return_dist=True)
        return self.network.nodes[n]

    def _infer_transit_stops(self):
        """map public transit stops to road network positions"""
        self.stops = {}
        if self.transit is not None:
            data = 'data/transit/{}.json'.format(self.id)
            if os.path.exists(data):
                logger.info('Loading existing transit stop network positions...')
                self.stops = json.load(open(data, 'r'))
            else:
                logger.info('Inferring transit stop network positions...')
                for i, r in tqdm(self.transit.stops.iterrows(), total=len(self.transit.stops)):
                    coord = r.stop_lat, r.stop_lon
                    id, edge_data, p, pt = self.find_closest_edge(coord)
                    self.stops[i] = {
                        'edge_id': id,
                        'along': p,
                        'point': (pt.x, pt.y),
                        'coord': self.to_latlng(pt.x, pt.y)
                    }
                with open(data, 'w') as f:
                    json.dump(self.stops, f)

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
            lanes = d.get('lanes', 1)
            if isinstance(lanes, str):
                lanes = int(lanes)
            elif isinstance(lanes, list):
                # just add up lanes if multiple are listed
                # TODO not sure if this is appropriate
                lanes = sum(int(l) for l in lanes)
            d['lanes'] = lanes

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

            d.update({
                'occupancy': 0,
                'capacity': d['length']/20 * d['lanes'] # TODO this is made up for now
            })

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
                d['maxspeed'] = DEFAULT_SPEED

    def _make_qt_index(self):
        # in lat, lng
        idx = Index(self.bbox)
        for e, data in tqdm(self.network.edges.items()):
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
            # in x,y, convert to lat,lng
            bounds = line.bounds
            a = self.to_latlng(bounds[0], bounds[1])
            b = self.to_latlng(bounds[2], bounds[3])
            bounds = (a[0] - BOUND_RADIUS, a[1] - BOUND_RADIUS, b[0] + BOUND_RADIUS, b[1] + BOUND_RADIUS)

            # not using osmid b/c sometimes they come as lists
            # so make the edge id out of (u, v, edge no)
            id = '_'.join([str(i) for i in e])
            idx.insert(id, bounds)
            self.edges[id] = data
        return idx

    def find_closest_edge(self, coord):
        """given a query point, will find
        the closest edge/path in the self to that point,
        as well as the closest point on that edge
        (described as a 0-1 position along that edge,
        e.g. 0.5 means halfway along that edge)"""
        pt = self.to_xy(*coord)
        pt = geometry.Point(*pt)
        bounds = coord[0]-BOUND_RADIUS, coord[1]-BOUND_RADIUS, coord[0]+BOUND_RADIUS, coord[1]+BOUND_RADIUS

        # find closest box
        matches = self.idx.intersect(bounds)

        # find closest edge
        id = min(matches, key=lambda id: self.edges[id]['geometry'].distance(pt))
        edge_data = self.edges[id]

        # find closest point on closest edge
        line = edge_data['geometry']
        p = line.project(pt, normalized=True)
        pt = line.interpolate(p, normalized=True)
        return id, edge_data, p, pt
