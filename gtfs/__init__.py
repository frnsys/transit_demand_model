import logging
import numpy as np
from . import util
from .csa import CSA
from tqdm import tqdm
from .calendar import Calendar
from scipy.spatial import KDTree
from collections import namedtuple
from itertools import product
from .enum import MoveType, RouteType

logger = logging.getLogger(__name__)

base_transfer_time = 2*60 # lower-bound time-delta overhead for changing trips
footpath_delta_base = 2*60 # footpath_delta = delta_base + km / speed_kmh
footpath_speed_kmh = 5 / 3600
footpath_delta_max = 7*60 # all footpaths longer than that are discarded as invalid


TransitLeg = namedtuple('TransitLeg', ['dep_stop', 'arr_stop', 'time', 'type'])


class IntIndex:
    def __init__(self, ids):
        self.id = {}
        self.idx = {}
        for i, id in enumerate(ids):
            self.id[i] = id
            self.idx[id] = i



class Transit:
    def __init__(self, gtfs_path, closest_indirect_transfers=5):
        """
        `closest_indirect_transfers` determines the number of closest stops for which
        indirect (walking) transfers are generated for. if you encounter a lot of
        "no path" errors, you may want to increase this number as it will be more likely
        to link separate routes. but note that it exponentially increases the processing time
        and can drastically increase memory usage.
        """
        gtfs = util.load_gtfs(gtfs_path)
        self.calendar = Calendar(gtfs)
        self._process_gtfs(gtfs)
        self._kdtree = self._index_stops(self.stops)
        self.footpaths = self._compute_footpaths(gtfs, closest_indirect_transfers)
        self.connections = self._compute_connections(gtfs)
        logger.info('Done')

    def _index_stops(self, stops):
        """prep kdtree for stop nearest neighbor querying;
        only consider stops that are in trips"""
        logger.info('Spatial-indexing stops...')
        stop_coords = stops[['stop_lat', 'stop_lon']].values
        return KDTree(stop_coords)

    def _process_gtfs(self, gtfs):
        logger.info('Processing GTFS data...')

        self.trips = gtfs['trips']
        self.stops = gtfs['stops']
        self.route_types = {r.route_id: RouteType(r.route_type) for r in gtfs['routes'].itertuples()}

        self.trip_idx = IntIndex(gtfs['trips']['trip_id'].unique())
        self.stop_idx = IntIndex(gtfs['stops']['stop_id'].unique())

        timetable = gtfs['stop_times']
        changes = timetable.apply(
            lambda row: (
                util.gtfs_time_to_secs(row.arrival_time),
                util.gtfs_time_to_secs(row.departure_time)),
            axis=1)
        timetable['arr_sec'], timetable['dep_sec'] = zip(*changes)

        # map trip_id->[stops]
        # sort by stop sequence so we know each trip group
        # has stops in the correct order
        self.trip_stops = timetable.sort_values('stop_sequence').groupby('trip_id')

        # map trip_id->[stops]
        # sort by stop sequence so we know each trip group
        # has stops in the correct order
        self.trip_stops = timetable.sort_values('stop_sequence').groupby('trip_id')

        # index the stops timetable so that we can quickly
        # lookup departures for a particular stop_id
        # and sort based on departure time in seconds
        # for slicing based on departure times.
        # this lets us, for example,
        # find trips departing from stop x after 10:00:00
        self.stops_trips_sched = timetable.set_index(['stop_id', 'dep_sec']).sort_index(level='dep_sec')

        # for resolving/executing trips
        self.timetable = timetable

    def _compute_connections(self, gtfs):
        logger.info('Processing trip frequencies into connections...')
        connections = []
        freqs = gtfs['frequencies'].groupby('trip_id')
        for trip_id, spans in tqdm(freqs):
            cons = self._connections_for_trip(trip_id, spans)
            connections.extend(cons)

        # must be sorted by departure time, ascending, for CSA
        return sorted(connections, key=lambda c: c['dep_time'])

    def _connections_for_trip(self, trip_id, spans):
        trip_stops = list(self.trip_stops.get_group(trip_id).itertuples())
        starts, connections = [], []
        for span in spans.itertuples():
            start = util.gtfs_time_to_secs(span.start_time)
            end = util.gtfs_time_to_secs(span.end_time)
            starts.extend(np.arange(start, end, span.headway_secs))

        # assuming they are sorted by stop sequence already
        trip_stops = list(trip_stops)
        for dep_stop, arr_stop in zip(trip_stops, trip_stops[1:]):
            dep = dep_stop.dep_sec
            arr = arr_stop.arr_sec

            # in the Belo Horizonte data, stop arrival/departure times were offset
            # by the first trip's departure time.
            # we want it to be relative to t=0 instead
            arr -= starts[0]
            dep -= starts[0]

            for start in starts:
                connections.append({
                    'arr_time': arr+start,
                    'dep_time': dep+start,
                    'arr_stop': self.stop_idx.idx[arr_stop.stop_id],
                    'dep_stop': self.stop_idx.idx[dep_stop.stop_id],
                    'trip_id': self.trip_idx.idx[trip_id]
                })
        return connections

    def _compute_footpaths(self, gtfs, closest):
        logger.info('Computing footpaths ({} closest)...'.format(closest))
        footpaths = {}
        for stop in tqdm(gtfs['stops'].itertuples(), total=len(gtfs['stops'])):
            coord = stop.stop_lat, stop.stop_lon

            # get closest stops to this one
            neighbors = self.closest_stops(coord, n=closest+1)

            # skip the first, it's the stop itself
            neighbors = neighbors[1:]

            # filter out long transfers
            neighbors = [n for n in neighbors if n[1] <= footpath_delta_max]

            footpaths[self.stop_idx.idx[stop.stop_id]] = [{
                'dep_stop': self.stop_idx.idx[stop.stop_id],
                'arr_stop': self.stop_idx.idx[stop_id],
                'time': transfer_time
            } for stop_id, transfer_time in neighbors]
        return footpaths

    def closest_stops(self, coord, n=5):
        """closest n stop ids for given coord, paired
        with estimated walking time"""
        # TODO we should probably use UTM positions instead of lat lons
        # for more accurate distances
        dists, idxs = self._kdtree.query(coord, k=n)

        # convert indices to stops
        stops = self.stops.loc[idxs]

        # compute estimated walking times
        times = [
            (id, util.walking_time(coord, (lat, lon), footpath_delta_base, footpath_speed_kmh))
            for id, lat, lon in stops[['stop_id', 'stop_lat', 'stop_lon']].values]

        # pair as `(stop_id, time)`
        return times

    def trip_type(self, trip_iid):
        """return what type of route a trip
        is on, e.g. bus, metro, etc"""
        route_id = self.trips.iloc[trip_iid]['route_id']
        return self.route_types[route_id]

    def router_for_day(self, dt):
        """get a public transit router
        for the specified day"""
        return TransitRouter(self, dt)


class TransitRouter:
    def __init__(self, transit, dt):
        self.T = transit
        valid_trips = self.T.calendar.trips_for_day(dt)

        # reduce connections to only those for this day
        connections = [c for c in self.T.connections if self.T.trip_idx.id[c['trip_id']] in valid_trips]

        # these need to be copied or we get a segfault?
        # TODO look into this
        footpaths_copy = {k: [dict(d) for d in v] for k, v in self.T.footpaths.items()}

        self.csa = CSA(connections, footpaths_copy)

    def route(self, start_coord, end_coord, dt, closest_stops=3):
        """compute a trip-level route between
        a start and an end stop for a given datetime"""
        # candidate start and end stops,
        # returned as [(iid, time), ...]
        # NB here we assume people have no preference b/w transit mode,
        # i.e. they are equally likely to choose a bus stop or a subway stop.
        start_stops = {s: t for s, t in self.T.closest_stops(start_coord, n=closest_stops)}
        end_stops = {s: t for s, t in self.T.closest_stops(end_coord, n=closest_stops)}
        same_stops = set(start_stops.keys()) & set(end_stops.keys())

        # if a same stop is in start and end stops,
        # walking is probably the best option
        if same_stops:
            walk_time = util.walking_time(start_coord, end_coord, footpath_delta_base, footpath_speed_kmh)
            return [TransitLeg(type=MoveType.WALK, time=walk_time)], walk_time

        best = (None, np.inf)
        dep_time = util.time_to_secs(dt.time())
        for (s_stop, s_walk), (e_stop, e_walk) in product(start_stops.items(), end_stops.items()):
            route, time = self.route_stops(s_stop, e_stop, dep_time)
            if route is not None and time < best[1]:
                best = route, time
        return best

    def route_stops(self, start_stop, end_stop, dep_time):
        start = self.T.stop_idx.idx[start_stop]
        end = self.T.stop_idx.idx[end_stop]
        return self.csa.route(start, end, dep_time)
