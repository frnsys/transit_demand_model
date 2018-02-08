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
import hashlib
import pyproj
import osmnx as ox
from collections import defaultdict
from router import Router

DEFAULT_SPEED = 30
ox.settings.data_folder = 'networks'


class TransitNetwork():
    def __init__(self, place, distance=10000):
        self.place = place
        self.save_file = hashlib.md5(place.encode('utf8')).hexdigest()

        if os.path.exists(os.path.join(ox.settings.data_folder, self.save_file)):
            G = ox.load_graphml(self.save_file)
        else:
            # the first search result isn't always what we want
            # so keep trying until we find something that clicks
            # see: <https://github.com/gboeing/osmnx/issues/16>
            # a more likely problem is that a place is returned as a point
            # rather than a shape, so we fall back to `graph_from_address`
            try:
                G = ox.graph_from_place(place, network_type='drive', simplify=True)
            except ValueError:
                print('Shape was not found for "{}"'.format(place))
                print('Falling back to address search at distance={}'.format(distance))
                G = ox.graph_from_address(place, network_type='drive', simplify=True, distance=distance)
            G = ox.project_graph(G)
            ox.save_graphml(G, filename=self.save_file)

        crs = G.graph['crs']
        self.utm_proj = pyproj.Proj(crs, preserve_units=True)
        self.G = G

        self._prepare_network()
        self.router = Router(self)

    def _prepare_network(self):
        """preprocess the network as needed"""
        # some `maxspeed` edge attributes are missing
        # (in particular, `highway=residential` are missing them)
        # do our best to estimate the missing values
        missing_speeds = []
        impute_speeds = defaultdict(list)

        # add occupancy to edges
        # and impute values where possible
        for e, d in self.G.edges.items():
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
