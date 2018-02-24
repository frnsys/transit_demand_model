import json
import enum
import math
import logging
import pandas as pd
import networkx as nx
from tqdm import tqdm
from gtfs import load_gtfs
from functools import partial
from datetime import timedelta
from scipy.spatial import KDTree
from collections import defaultdict
from itertools import product, starmap

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

base_transfer_time = 2*60 # lower-bound time-delta overhead for changing trips
footpath_delta_base = 2*60 # footpath_delta = delta_base + km / speed_kmh
footpath_speed_kmh = 5 / 3600
footpath_delta_max = 7*60 # all footpaths longer than that are discarded as invalid
footpath_closest_stops = 5 # number of closest stops to consider for non-same stop walking transfer


def walking_time(coord_a, coord_b, delta_base=footpath_delta_base, speed_kmh=footpath_speed_kmh):
    """Calculate footpath time-delta in seconds between two stops,
        based on their lon/lat distance (using Haversine Formula) and walking-speed constant.
        adapted from: <https://github.com/mk-fg/trip-based-public-transit-routing-algo/blob/master/tb_routing/gtfs.py#L198>"""
    # Alternative: use UTM coordinates and KDTree (e.g. scipy) or spatial dbs
    lon1, lat1, lon2, lat2 = (
        math.radians(float(v)) for v in
        [coord_a[0], coord_a[1], coord_b[0], coord_b[1]] )
    km = 6367 * 2 * math.asin(math.sqrt(
        math.sin((lat2 - lat1)/2)**2 +
        math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1)/2)**2 ))
    return delta_base + km / speed_kmh


def gtfs_time_to_secs(time):
    h, m, s = time.split(':')
    return int(s) + (int(m) * 60) + (int(h) * 60 * 60)


class ServiceChange(enum.Enum):
    """https://developers.google.com/transit/gtfs/reference/#calendar_datestxt"""
    ADDED   = 1
    REMOVED = 2


class RouteType(enum.Enum):
    """https://developers.google.com/transit/gtfs/reference/#routestxt"""
    TRAM      = '0' # also: streetcar, light rail
    METRO     = '1' # also: subway
    RAIL      = '2'
    BUS       = '3'
    FERRY     = '4'
    CABLE     = '5' # street-level cable car
    GONDOLA   = '6' # suspended cable car
    FUNICULAR = '7' # steep incline rail


WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


class Transit:
    def __init__(self, gtfs_path, trip_network_path, closest_indirect_transfers=3):
        """
        `closest_indirect_transfers` determines the number of closest stops for which
        indirect (walking) transfers are generated for. if you encounter a lot of
        "no path" errors, you may want to increase this number as it will be more likely
        to link separate routes. but note that it exponentially increases the processing time
        and can drastically increase memory usage.
        """
        gtfs = load_gtfs(gtfs_path)
        self._parse_calendar(gtfs)
        self._parse_trips(gtfs)
        self._index_stops(gtfs)
        self._transfer_times = {}

        try:
            logger.debug('Trying to load existing trip network')
            with open('trip_index.json', 'r') as f:
                data = json.load(f)
                self.trip_node = data['trip_node']
                self.stop_node = data['stop_node']
                self.node_trip = {i: trip_id for trip_id, i in self.trip_node.items()}
            self.trip_network = nx.read_edgelist('edgelist.gz', data=True, create_using=nx.MultiDiGraph(), nodetype=int)
        except FileNotFoundError:
            logger.debug('No existing trip network, computing new one')
            self.trip_network = self._compute_trip_network(gtfs, closest_indirect_transfers)

            logger.debug('Saving trip network...')
            nx.write_edgelist(self.trip_network, 'edgelist.gz', data=True)
            with open('trip_index.json', 'w') as f:
                json.dump({
                    'trip_node': self.trip_node,
                    'stop_node': self.stop_node
                }, f)
        logger.debug('Done')

    def _parse_calendar(self, gtfs):
        """parse calendar data for service days/changes/exceptions"""
        # associate services with their operating weekdays
        # NOTE this data provies start and end dates for services
        # but for our simulation we are treating this timetable as ongoing
        calendar = gtfs['calendar']
        service_days = {i: [] for i, day in enumerate(WEEKDAYS)}
        for i, row in calendar.iterrows():
            service_id = row.service_id
            for day, services in service_days.items():
                if row[WEEKDAYS[day]] == 1:
                    services.append(service_id)
        self.service_days = service_days

        # parse 'date' column as date objects
        # then group by date, so we can quickly query
        # service changes for a given date
        service_changes = gtfs['calendar_dates']
        service_changes['date'] = pd.to_datetime(service_changes.date, format='%Y%m%d').dt.date
        self.service_changes = service_changes.groupby('date')

    def _index_stops(self, gtfs):
        """prep kdtree for stop nearest neighbor querying;
        only consider stops that are in trips"""
        logger.debug('Spatial-indexing stops...')
        stops_with_trips = gtfs['stop_times']['stop_id'].unique()
        stops = gtfs['stops']
        self.stops_with_trips = stops[stops['stop_id'].isin(stops_with_trips)]
        self.stops_with_trips.reset_index(drop=True, inplace=True)
        stop_coords = self.stops_with_trips[['stop_lat', 'stop_lon']].values
        self._kdtree = KDTree(stop_coords)

    def _parse_trips(self, gtfs):
        """parse trips (stop sequences)
        into a stop network"""
        logger.debug('Parsing trips...')

        self.services = {name: group.trip_id.values
                         for name, group in gtfs['trips'].groupby('service_id')}
        self.trips = gtfs['stop_times'].groupby('trip_id')

        # TODO this is happening twice
        times_in_seconds = gtfs['stop_times'].apply(
            lambda row: (gtfs_time_to_secs(row.arrival_time), gtfs_time_to_secs(row.departure_time)),
            axis=1)
        gtfs['stop_times']['arr_sec'], gtfs['stop_times']['dep_sec'] = zip(*times_in_seconds)
        self.stops_to_trips = gtfs['stop_times'].set_index(['stop_id', 'dep_sec']).sort_index(level='dep_sec')

        # TODO clean this up
        stop_seqs = {}
        self.stop_seq_trips = defaultdict(list)
        self.stop_seq_graphs = {}
        self.trip_to_stop_seq = {}
        for trip_id, stops in self.trips:
            stops = stops.sort_values('stop_sequence')
            stop_ids = stops['stop_id'].values

            # convert the sequence of stop ids into
            # something hashable
            stop_seq_str = '_'.join(map(str, stop_ids))

            # many trips will have the same sequence of stops,
            # we'll leverage that to avoid creating redundant graphs
            self.stop_seq_trips[stop_seq_str].append(trip_id)

            # reverse lookup so we can get the stop sequence graph
            # from a trip_id
            self.trip_to_stop_seq[trip_id] = stop_seq_str

            if stop_seq_str not in stop_seqs:
                stop_seqs[stop_seq_str] = stop_ids

        self.stop_seq_ids = {}
        for i, stop_seq_str in enumerate(stop_seqs.keys()):
            self.stop_seq_ids[stop_seq_str] = i

        for stop_seq_str, stop_ids in stop_seqs.items():
            g = nx.DiGraph()
            for frm, to in zip(stop_ids, stop_ids[1:]):
                g.add_edge(frm, to)
            self.stop_seq_graphs[stop_seq_str] = g

    def _equivalent_trips(self, trip_id):
        """returns set of equivalent trips for a trip_id,
        i.e. those that have the same sequence of stops
        (though the trips do not need to start/end at the same times)"""
        stop_seq_str = self.trip_to_stop_seq[trip_id]
        equivalent = set(self.stop_seq_trips[stop_seq_str]) - {trip_id}
        return equivalent

    def _compute_trip_network(self, gtfs, closest_indirect_transfers):
        """
        generate the trip network for trip-level routing.
        this is a directed graph,
        b/c even though in theory if a transfer is
        possible one way, it's possible the other way but
        1) there may be edge cases where this is not the case or, more likely,
        2) transfer times are not always equal both ways, and also
        3) trip transfers have to go with time, i.e. can only
        transfer to a trip later in time.
        using a multi-directed graph b/c it's possible there are
        multiple places to transfer between trips
        """
        trip_network = nx.MultiDiGraph()
        stop_seqs = gtfs['stop_times']
        trip_ids = stop_seqs['trip_id'].unique()
        self.trip_node = {trip_id: i for i, trip_id in enumerate(trip_ids)}
        self.node_trip = {i: trip_id for i, trip_id in enumerate(trip_ids)}

        stop_ids = stop_seqs['stop_id'].unique()
        self.stop_node = {stop_id: i for i, stop_id in enumerate(stop_ids)}
        self.node_stop = {i: stop_id for i, stop_id in enumerate(stop_ids)}

        # convert GTFS times (which are in the format 'HH:MM:SS')
        # to integer seconds, so we can leverage pandas indexing
        # for performance reasons
        times_in_seconds = stop_seqs.apply(
            lambda row: (gtfs_time_to_secs(row.arrival_time), gtfs_time_to_secs(row.departure_time)),
            axis=1)
        stop_seqs['stop_seq_id'] = stop_seqs.apply(lambda row: self.stop_seq_ids[self.trip_to_stop_seq[row.trip_id]], axis=1)
        stop_seqs['arr_sec'], stop_seqs['dep_sec'] = zip(*times_in_seconds)

        # stop_seqs = stop_seqs[['dep_sec', 'arr_sec', 'stop_id', 'trip_id', 'stop_seq_id']].set_index('dep_sec').sort_index()
        stop_seqs = stop_seqs.set_index('dep_sec').sort_index()
        stop_seqs = stop_seqs.groupby('stop_id')
        # stop_seqs.set_index(['dep_sec', 'stop_seq_id']).sort_index(level='dep_sec')[100:]

        # direct transfers (i.e. at the same stop)
        # (multiprocessing here does not
        # add much of an increase in speed)
        logger.debug('Parsing direct transfers...')
        for edges in tqdm(starmap(self._process_direct_transfers, stop_seqs), total=len(stop_seqs)):
            for frm, to, data in edges:
                trip_network.add_edge(frm, to, **data)

        # indirect transfers (i.e. between nearby stops)
        logger.debug('Parsing indirect transfers...')
        fn = partial(self._compute_indirect_transfers, stop_seqs, closest_indirect_transfers)
        for edges in tqdm(map(fn, self.stops_with_trips.itertuples()), total=len(self.stops_with_trips)):
            for frm, to, data in edges:
                trip_network.add_edge(frm, to, **data)

        return trip_network

    def _compute_indirect_transfers(self, stop_trips, closest, row):
        """compute edges for indirect transfers;
        i.e. for transfers that aren't at the same stop, but within walking distance.
        will only look at the `closest` stops. increasing `closest` will exponentially
        increase processing time."""
        coord = row.stop_lat, row.stop_lon

        # get trips departing from this stop
        from_trips = stop_trips.get_group(row.stop_id)[['trip_id', 'arr_sec', 'stop_seq_id']].values

        # get closest stops to this one
        neighbors = self.closest_stops(coord, n=closest+1)

        # skip the first, it's the stop itself
        neighbors = neighbors[1:]

        # filter out long transfers
        neighbors = [n for n in neighbors if n[1] <= footpath_delta_max]

        this_stop_iid = self.stop_node[row.stop_id]
        for stop_id, transfer_time in neighbors:
            group = stop_trips.get_group(stop_id)
            stop_iid = self.stop_node[stop_id]
            transfer_key = '{}->{}'.format(this_stop_iid, stop_iid)
            if transfer_key not in self._transfer_times:
                self._transfer_times[transfer_key] = transfer_time

            for frm, arrival_time, stop_seq_id in from_trips:
                arrival_time_after_walking = arrival_time + transfer_time

                # can only transfer to trips that depart
                # after the incoming trip arrives
                valid_transfers = group.loc[arrival_time_after_walking:]

                seen = {stop_seq_id}
                frm = self.trip_node[frm]
                for to, ssid in valid_transfers[['trip_id', 'stop_seq_id']].values:
                    if ssid in seen:
                        continue
                    seen.add(ssid)
                    to = self.trip_node[to]
                    yield frm, to, {
                        'from_stop_id': this_stop_iid,
                        'to_stop_id': stop_iid}
                        # 'transfer_time': transfer_time} # TODO don't need this
                        # will look up from self._transfer_times

    def _process_direct_transfers(self, stop_id, group):
        stop_iid = self.stop_node[stop_id]
        for frm, arrival_time, stop_seq_id in group[['trip_id', 'arr_sec', 'stop_seq_id']].values:
            # can only transfer to trips that depart
            # after the incoming trip arrives, accounting
            # for typical transfer time
            arrival_time = arrival_time + base_transfer_time
            valid_transfers = group.loc[arrival_time:]

            # also skip trips that have the same stop sequence as this one,
            # assuming that people would not want to transfer to a later
            # trip that is making the exact same stops as the one they're
            # currently on
            # we make this assumption and the similar next one
            # to reduce the number of edges in the network
            # valid_transfers = group[group.stop_seq_id != stop_seq_id]
            # valid_transfers = valid_transfers.groupby('stop_seq_id').first()

            # select only the soonest trip for each stop sequence,
            # assuming that people want to make the soonest transfer
            # (already sorted by departure time)
            # valid_transfers = valid_transfers.groupby('stop_seq_id').first()
            seen = {stop_seq_id}
            frm = self.trip_node[frm]
            for to, ssid in valid_transfers[['trip_id', 'stop_seq_id']].values:
                if ssid in seen:
                    continue

                seen.add(ssid)
                to = self.trip_node[to]

                # reduce each set of valid transfers

                # TODO should add time between trips
                # though i think that is dependent on knowing the starting stop, so nvm
                yield frm, to, {'stop_id': stop_iid}
                                # 'transfer_time': base_transfer_time} TODO dont
                                # need this b/c its a constant

    def _graph_for_trip(self, trip_id):
        """get the stop sequence graph for a trip id"""
        stop_seq_str = self.trip_to_stop_seq[trip_id]
        return self.stop_seq_graphs[stop_seq_str]

    def transfers_for_stop(self, stop_id):
        """return direct and indirect transfers for a stop id"""
        try:
            direct = self.transfer_stops.get_group(stop_id)
        except KeyError:
            direct = []

        indirect = self.walking_transfer_stops[stop_id]
        return direct, indirect

    def closest_stops(self, coord, n=5):
        """closest n stop ids for given coord, paired
        with estimated walking time"""
        dists, idxs = self._kdtree.query(coord, k=n)

        # convert indices to stops
        stops = self.stops_with_trips.loc[idxs]

        # compute estimated walking times
        times = [
            walking_time(coord, (lat, lon))
            for lat, lon in stops[['stop_lat', 'stop_lon']].values]

        # pair as `(stop_id, time)`
        return list(zip(stops['stop_id'].values, times))

    def services_for_dt(self, dt):
        """returns operating service ids
        for a given datetime"""
        # gives weekday as an int,
        # where `monday = 0`
        weekday = dt.weekday()

        # get list of service ids as a copy
        # so we can add/remove according to service changes
        services = self.service_days[weekday][:]

        # check if there are any service changes for the date
        for service_id, change in self.service_changes_for_dt(dt).items():
            if change is ServiceChange.ADDED:
                services.append(service_id)
            else:
                try:
                    services.remove(service_id)
                except ValueError:
                    pass
        return services

    def service_changes_for_dt(self, dt):
        """return a dict of `{service_id: ServiceChange}`
        describing service changes (additions or removals
        for a given datetime"""
        try:
            changes = self.service_changes.get_group(dt.date())
            return {c.service_id: ServiceChange(c.exception_type) for i, c in changes.iterrows()}
        except KeyError:
            return {}

    def trips_for_services(self, service_ids):
        """get trip ids that encompass a given list of service ids"""
        trips = set()
        for service_id in service_ids:
            try:
                trip_ids = self.services[service_id]
            except KeyError:
                # seems like some service_ids are missing?
                continue
            trips = trips | set(trip_ids)
        return trips

    def trip_route(self, start_stop, end_stop, dt, n_soonest=10):
        t = dt.time()
        seconds = (t.hour * 60 + t.minute) * 60 + t.second
        service_ids = set(self.services_for_dt(dt)) | set(self.services_for_dt(dt + timedelta(days=1)))
        trip_ids = self.trips_for_services(service_ids)

        # find trips with this start stop
        # TODO filter to those starting after the specified times
        # we may also want to look at the X soonest?
        start_trips = self.stops_to_trips.loc[start_stop].loc[seconds:]['trip_id'].values
        end_trips = self.stops_to_trips.loc[end_stop].loc[seconds:]['trip_id'].values

        # only consider trips which are operating for the datetime
        start_trips = set(start_trips) & trip_ids
        end_trips = set(end_trips) & trip_ids

        # convert to network ids
        start_trips = [self.trip_node[id] for id in start_trips]
        end_trips = [self.trip_node[id] for id in end_trips]

        # TODO there is likely a more efficient way to do this
        paths = []
        for start_trip, end_trip in tqdm(product(start_trips, end_trips)):
            # TODO check if the end_trip arrival time is after start_trip departure time
            try:
                path = nx.dijkstra_path(self.trip_network, start_trip, end_trip, 'transfer_time')
                path  = [self.node_trip[i] for i in path]
            except nx.exception.NetworkXNoPath:
                continue
            paths.append(path)

        return paths


if __name__ == '__main__':
    transit = Transit('data/gtfs/gtfs_bhtransit.zip', 'trip_network.graph')

    from datetime import datetime
    dt = datetime(year=2017, month=2, day=27, hour=10)
    start_stop = '00103226701049'
    end_stop = '00103205200346'
    paths = transit.trip_route(start_stop, end_stop, dt)
    print(paths)

    import ipdb; ipdb.set_trace()

    # options
    # return a sequence of trips, with end stops
    # station -> trip (0 cost) -> (other trips, potentially)

    """
    routing/search procedure:

    - generate a trip network, which shows how trips connect together (an edge
    between trips represents a transfer between trips)
    - given a start stop, find trips after the departure time that include that stop
    - given an end stop, find trips after the departure time that include that stop
    - find shortest paths through the trip network connecting these trips (TODO
    don't want to search _every_ pair...)

    TODO need to handle cases where a given stop is unexpectedly out of service or something
    which will affect the trip network (might potentially ruin transfers)
    or if certain trips are suspended, delayed, etc...

    - then, when we actually execute the route, we go to the stop network and run
    through that (TODO details)

    want to provide a trip-level route that assumes the network is as described.
    that is, if the network info has no delays, we route assuming no delays.
    """

