import enum
import config
import logging
import numpy as np
from . import util
from tqdm import tqdm
from .calendar import Calendar
from scipy.spatial import KDTree
from .router import TransitRouter

logger = logging.getLogger(__name__)


class RouteType(enum.Enum):
    """https://developers.google.com/transit/gtfs/reference/#routestxt"""
    TRAM      = 0 # also: streetcar, light rail
    METRO     = 1 # also: subway
    RAIL      = 2
    BUS       = 3
    FERRY     = 4
    CABLE     = 5 # street-level cable car
    GONDOLA   = 6 # suspended cable car
    FUNICULAR = 7 # steep incline rail


class Transit:
    def __init__(self, gtfs_path):
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
        self.footpaths = self._compute_footpaths(gtfs, config.closest_indirect_transfers)
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

        self.trips = gtfs['trips'].set_index('trip_id')
        self.stops = gtfs['stops'].set_index('stop_id')

        # TODO TESTING for faster lookups
        self.stops_list = self.stops.to_dict('records')

        self.route_types = {r.route_id: RouteType(r.route_type) for r in gtfs['routes'].itertuples()}

        self.trip_idx = util.IntIndex(gtfs['trips']['trip_id'].unique())
        self.stop_idx = util.IntIndex(gtfs['stops']['stop_id'].unique())

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

        # index the stops timetable so that we can quickly
        # lookup departures for a particular stop_id
        # and sort based on departure time in seconds
        # for slicing based on departure times.
        # this lets us, for example,
        # find trips departing from stop x after 10:00:00
        self.stops_trips_sched = timetable.set_index(['stop_id', 'dep_sec']).sort_index(level='dep_sec')

        # for resolving/executing trips
        self.timetable = timetable

        # for determining overall trip start/end times
        self.freqs = gtfs['frequencies'].groupby('trip_id')

    def _compute_connections(self, gtfs):
        logger.info('Processing trip frequencies into connections...')
        connections = []
        trip_starts = {}
        freqs = gtfs['frequencies'].groupby('trip_id')
        for trip_id, spans in tqdm(freqs):
            cons, starts = self._connections_for_trip(trip_id, spans)
            connections.extend(cons)
            trip_starts[trip_id] = starts
        self.trip_starts = trip_starts

        # must be sorted by departure time, ascending, for CSA
        return sorted(connections, key=lambda c: c['dep_time'])

    def _connections_for_trip(self, trip_id, spans):
        trip_stops = list(self.trip_stops.get_group(trip_id).itertuples())
        starts, connections = [], []

        # compute start time of each vehicle
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
        return connections, starts

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
            neighbors = [n for n in neighbors if n[1] <= config.footpath_delta_max]

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
        stops = self.stops.iloc[idxs]

        # compute estimated walking times
        times = [
            (stop.Index, util.walking_time(
                coord, (stop.stop_lat, stop.stop_lon),
                config.footpath_delta_base, config.footpath_speed_kmh))
            for stop in stops.itertuples()]

        # pair as `(stop_id, time)`
        return times

    def trip_type(self, trip_id):
        """return what type of route a trip
        is on, e.g. bus, metro, etc"""
        route_id = self.trips.loc[trip_id]['route_id']
        return self.route_types[route_id]

    def router_for_day(self, dt):
        """get a public transit router
        for the specified day"""
        return TransitRouter(self, dt)
