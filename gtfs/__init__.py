"""
routing/search procedure:

- generate a trip network, which shows how trips connect together (an edge
between trips represents a transfer between trips)
- given a start stop, find trips after the departure time that include that stop
- given an end stop, find trips after the departure time that include that stop
- find shortest paths through the trip network connecting these trips

TODO need to handle cases where a given stop is unexpectedly out of service or something
which will affect the trip network (might potentially ruin transfers)
or if certain trips are suspended, delayed, etc...

- then, when we actually execute the route, we go to the stop network and run
through that (TODO details)

want to provide a trip-level route that assumes the network is as described.
that is, if the network info has no delays, we route assuming no delays.

when we generate the trip network, we don't create edges for every _possible_
transfer (that blows up the number of edges in the graph, for Belo Horizonte,
the edge count was at 24.5 million), just transfers that would be optimal.
which is to say, transfers which are for the next departing trip for a particular
stop sequence. for Belo Horizonte, this cut the edge count down to about 4.7 million.
"""

import os
import json
import hashlib
import logging
import networkx as nx
from tqdm import tqdm
from functools import partial
from itertools import starmap
from scipy.spatial import KDTree
from collections import defaultdict
from .calendar import Calendar
from . import util

logger = logging.getLogger(__name__)

base_transfer_time = 2*60 # lower-bound time-delta overhead for changing trips
footpath_delta_base = 2*60 # footpath_delta = delta_base + km / speed_kmh
footpath_speed_kmh = 5 / 3600
footpath_delta_max = 7*60 # all footpaths longer than that are discarded as invalid
footpath_closest_stops = 5 # number of closest stops to consider for non-same stop walking transfer


def nodetype(u):
    """parse serialized network nodes"""
    t, s = u[1:-1].split(',')
    return int(t), int(s)


class Transit:
    network_file = 'network.gz'
    transfers_file = 'transfer.json'

    def __init__(self, gtfs_path, save_path, closest_indirect_transfers=3):
        """
        `closest_indirect_transfers` determines the number of closest stops for which
        indirect (walking) transfers are generated for. if you encounter a lot of
        "no path" errors, you may want to increase this number as it will be more likely
        to link separate routes. but note that it exponentially increases the processing time
        and can drastically increase memory usage.
        """
        gtfs = util.load_gtfs(gtfs_path)
        self._process_gtfs(gtfs)
        self.calendar = Calendar(gtfs, self.trip_iids)

        # prep kdtree for stop nearest neighbor querying;
        # only consider stops that are in trips
        logger.debug('Spatial-indexing stops...')
        stop_coords = self.stops[['stop_lat', 'stop_lon']].values
        self._kdtree = KDTree(stop_coords)

        self._transfer_times = {}

        if os.path.exists(save_path):
            logger.debug('Loading existing trip data and network...')
            self._load(save_path)
        else:
            logger.debug('No existing trip network, computing new one')
            self.trip_network = self._compute_trip_network(closest_indirect_transfers)

            logger.debug('Saving trip network...')
            self._save(save_path)

        logger.debug('Done')

    def _load(self, save_path):
        self.trip_network = nx.read_edgelist(
            os.path.join(save_path, self.network_file),
            data=True,
            delimiter='\t',
            create_using=nx.DiGraph(),
            nodetype=nodetype)

        with open(os.path.join(save_path, self.transfers_file), 'r') as f:
            data = json.load(f)
            self.trips_to_transfer_stops = {int(i): s for i, s in data['trip_transfer_stops'].items()}
            self._transfer_times = data['transfer_times']

    def _save(self, save_path):
        os.mkdir(save_path)
        nx.write_edgelist(
            self.trip_network,
            os.path.join(save_path, self.network_file),
            data=True, delimiter='\t')

        with open(os.path.join(save_path, self.transfers_file), 'w') as f:
            json.dump({
                'trip_transfer_stops': self.trips_to_transfer_stops,
                'transfer_times': self._transfer_times
            }, f)

    def _process_gtfs(self, gtfs):
        logger.debug('Processing GTFS data...')

        # get stop_ids that are part of trips
        stops_with_trips = gtfs['stop_times']['stop_id'].unique()

        # filter stop data only to these stops
        # save for later lookup of iid->stop_id
        # where iid is the internal id for the stop
        # rather than the actual stop_id.
        # (so we aren't dealing with clumsy stop_id strings)
        self.stops = gtfs['stops']
        self.stops = self.stops[self.stops['stop_id'].isin(stops_with_trips)]
        self.stops.reset_index(drop=True, inplace=True)

        self.trips = gtfs['trips']

        # replace:
        # - trip ids with internal trip ids (trip iids)
        # - stop ids with internal stop ids (stop iids)
        timetable = gtfs['stop_times']
        self.trip_iids = {v:k for k, v in self.trips['trip_id'].items()}
        self.stop_iids = {v:k for k, v in self.stops['stop_id'].items()}

        # convert gtfs time strings to equivalent integer seconds
        # so we can leverage pandas indexing for performance reasons
        changes = timetable.apply(
            lambda row: (
                (self.trip_iids[row.trip_id], self.stop_iids[row.stop_id]),
                util.gtfs_time_to_secs(row.arrival_time),
                util.gtfs_time_to_secs(row.departure_time)),
            axis=1)
        timetable[['trip_id', 'stop_id']], timetable['arr_sec'], timetable['dep_sec'] = zip(*changes)

        # map trip_id->[stops]
        # sort by stop sequence so we know each trip group
        # has stops in the correct order
        self.trip_stops = timetable.sort_values('stop_sequence').groupby('trip_id')

        # many trips have the same sequence of stops,
        # they just depart at different times.
        # this leads to a lot of redundancy in routing.
        # for example, if it's 09:00:00 and
        # there is a trip departing at 09:15:00,
        # and exact same trips departing at 09:30:00,
        # 10:00:00, etc, we only want to consider the soonest trip.
        # this vastly cuts down on the graph size (in my experiment
        # with Belo Horizonte data, it cut the number of edges down by 80%,
        # which was a reduction of ~18.5 million edges).
        # so we need to index trips by their stop sequences to
        # identify which trips are equivalent.
        trips_to_stop_seq = {}
        for trip_id, stops in self.trip_stops:
            # generate an id for this stop sequence
            stop_seq = stops['stop_id'].values
            stop_seq_id = '_'.join(map(str, stop_seq)).encode('utf8')
            stop_seq_id = hashlib.md5(stop_seq_id).hexdigest()

            # reverse lookup so we can get
            # the stop sequence graph from a trip_id
            trips_to_stop_seq[trip_id] = stop_seq_id

        timetable['stop_seq_id'] = timetable.apply(lambda row: trips_to_stop_seq[row.trip_id], axis=1)

        # index the stops timetable so that we can quickly
        # lookup departures for a particular stop_id
        # and sort based on departure time in seconds
        # for slicing based on departure times.
        # this lets us, for example,
        # find trips departing from stop x after 10:00:00
        self.stops_trips_sched = timetable.set_index(['stop_id', 'dep_sec']).sort_index(level='dep_sec')

    def _compute_trip_network(self, closest_indirect_transfers):
        """
        generate the trip network for trip-level routing.
        this is a directed graph,
        b/c even though in theory if a transfer is
        possible one way, it's possible the other way but
        1) there may be edge cases where this is not the case or, more likely,
        2) transfer times are not always equal both ways, and also
        3) trip transfers have to go with time, i.e. can only
        transfer to a trip later in time.
        """
        trip_network = nx.DiGraph()

        # figure out which trips share stop_ids to identify direct transfers
        stop_seqs = self.stops_trips_sched.reset_index(level='stop_id').groupby('stop_id')

        # count unique stop sequences through each stop
        # and get the stop_ids of those with > 1.
        # those are "meaningful" (direct) transfers
        # (i.e. transfers not between two of the same stop sequence)
        transfer_stops = stop_seqs.stop_seq_id.nunique()
        transfer_stops = transfer_stops[transfer_stops > 1]
        transfer_stops = transfer_stops.index.values
        to_process = [(stop_id, group) for stop_id, group in stop_seqs if stop_id in transfer_stops]

        self.trips_to_transfer_stops = defaultdict(set)

        # direct transfers (i.e. at the same stop)
        # (multiprocessing here does not
        # add much of an increase in speed)
        logger.debug('Parsing direct transfers...')
        for edges in tqdm(starmap(self._process_direct_transfers, to_process), total=len(to_process)):
            for frm, to in edges:
                trip_iid, stop_iid = frm
                self.trips_to_transfer_stops[trip_iid].add(stop_iid)
                trip_network.add_edge(frm, to)

        # indirect transfers (i.e. between nearby stops)
        logger.debug('Parsing indirect transfers...')
        fn = partial(self._compute_indirect_transfers, stop_seqs, closest_indirect_transfers)
        for edges in tqdm(map(fn, self.stops.itertuples(index=True)), total=len(self.stops)):
            for frm, to in edges:
                trip_iid, stop_iid = frm
                self.trips_to_transfer_stops[trip_iid].add(stop_iid)
                trip_network.add_edge(frm, to)

        logger.debug('Linking trip-stops...')
        # for each trip, select stop_ids that there are nodes for (keep track in
        # dict), sort by stop sequence (should already be afaik due to departure
        # times), then iterate pairwise and create edges
        for trip_iid, stop_iids in tqdm(self.trips_to_transfer_stops.items()):
            # get transfer stop ids in correct stop sequence order for the trip
            stop_seq = self.trip_stops.get_group(trip_iid)
            stop_seq = stop_seq[stop_seq['stop_id'].isin(stop_iids)]
            stops = stop_seq[['stop_id', 'dep_sec', 'arr_sec']].values

            for (stop_id_a, dep_a, _), (stop_id_b, dep_b, arr_b) in zip(stops, stops[1:]):
                frm = (trip_iid, stop_id_a)
                to = (trip_iid, stop_id_b)
                travel_time = arr_b - dep_a
                trip_network.add_edge(frm, to, weight=travel_time)

        # easy way to look up which of a trip's stops are transfer stops
        self.trips_to_transfer_stops = {t: list(s) for t, s in self.trips_to_transfer_stops.items()}

        return trip_network

    def _process_direct_transfers(self, stop_id, group):
        """process direct transfers that occur at the given stop.
        """
        for frm, arrival_time, stop_seq_id in group[['trip_id', 'arr_sec', 'stop_seq_id']].values:
            # can only transfer to trips that depart
            # after the incoming trip arrives, accounting
            # for typical transfer time
            arrival_time = arrival_time + base_transfer_time
            valid_transfers = group.loc[arrival_time:]

            # also skip trips that have the same stop sequence as this one,
            # assuming that people would not want to transfer to a later
            # trip that is making the exact same stops as the one they're
            # currently on.
            # we also keep track of stop sequences we've added edges for,
            # so we only add an edge for the first time we see that stop
            # sequence (such that we only create an edge for
            # the soonest departing trip with that stop sequence; since
            # these groups are already sorted by departure time, that should
            # be the first trip with that stop sequence)
            # in both cases we're assuming that people always want to make the
            # soonest transfer.
            # these assumptions help reduce the number of edges in the network.
            seen = {stop_seq_id}
            frm = (frm, stop_id)
            for to, ssid in valid_transfers[['trip_id', 'stop_seq_id']].values:
                # already seen this stop sequence?
                # if so, skip
                if ssid in seen:
                    continue

                seen.add(ssid)
                to = (to, stop_id)
                yield frm, to

    def _compute_indirect_transfers(self, stop_trips, closest, row):
        """compute edges for indirect transfers;
        i.e. for transfers that aren't at the same stop, but within walking distance.
        will only look at the `closest` stops. increasing `closest` will exponentially
        increase processing time."""
        coord = row.stop_lat, row.stop_lon

        # get closest stops to this one
        neighbors = self.closest_stops(coord, n=closest+1)

        # skip the first, it's the stop itself
        neighbors = neighbors[1:]

        # filter out long transfers
        neighbors = [n for n in neighbors if n[1] <= footpath_delta_max]

        # get trips departing from this stop
        from_trips = stop_trips.get_group(row.Index)
        from_trips = from_trips[['trip_id', 'arr_sec', 'stop_seq_id']].values

        for stop_id, transfer_time in neighbors:
            group = stop_trips.get_group(stop_id)

            # cache walking transfer times between stops
            transfer_key = '{}->{}'.format(row.stop_id, stop_id)
            if transfer_key not in self._transfer_times:
                self._transfer_times[transfer_key] = transfer_time

            for frm, arrival_time, stop_seq_id in from_trips:
                arrival_time_after_walking = arrival_time + transfer_time

                # can only transfer to trips that depart
                # after the incoming trip arrives
                valid_transfers = group.loc[arrival_time_after_walking:]

                # (see note in process_direct_transfers)
                seen = {stop_seq_id}
                frm = (frm, row.Index) # Index is the stop iid
                for to, ssid in valid_transfers[['trip_id', 'stop_seq_id']].values:
                    if ssid in seen:
                        continue

                    seen.add(ssid)
                    to = (to, stop_id)
                    yield frm, to

    def _get_transit_time(self, frm, to, edge):
        if 'weight' in edge:
            return edge['weight']
        frm_trip_iid, frm_stop_iid = frm
        to_trip_iid, to_stop_iid = to
        key = '{}->{}'.format(frm_stop_iid, to_stop_iid)
        return self._transfer_times.get(key, base_transfer_time)

    def closest_stops(self, coord, n=5):
        """closest n stop ids for given coord, paired
        with estimated walking time"""
        dists, idxs = self._kdtree.query(coord, k=n)

        # convert indices to stops
        stops = self.stops.loc[idxs]

        # compute estimated walking times
        times = [
            util.walking_time(coord, (lat, lon), footpath_delta_base, footpath_speed_kmh)
            for lat, lon in stops[['stop_lat', 'stop_lon']].values]

        # pair as `(stop_iid, time)`
        return list(zip(idxs, times))

    def trip_route(self, start_stop, end_stop, dt):
        """compute a trip-level route between
        a start and an end stop for a given datetime"""
        # convert to iids
        start_stop = self.stop_iids[start_stop]
        end_stop = self.stop_iids[end_stop]

        # look only for trips starting after the departure time
        seconds = util.time_to_secs(dt.time())
        start_trips = self.stops_trips_sched.loc[start_stop].loc[seconds:]['trip_id'].values
        end_trips = self.stops_trips_sched.loc[end_stop].loc[seconds:]['trip_id'].values

        # only consider trips which are operating for the datetime
        trip_ids = self.calendar.trips_for_day(dt)
        start_trips = set(start_trips) & trip_ids
        end_trips = set(end_trips) & trip_ids

        # if the same trip is in the start and end sets,
        # it means we can take just that trip, no transfers.
        # so just return that
        same_trips = set(start_trips) & set(end_trips)
        if same_trips:
            return [[(t, start_stop), (t, end_stop)] for t in same_trips]

        # filter equivalent start trips (i.e. those with the same stop sequence)
        # down to soonest-departing ones, assuming people want to take the
        # soonest trip.
        # the `first()` call assumes that these are sorted by departure time,
        # which they should be
        start_trips = self.stops_trips_sched[self.stops_trips_sched.trip_id.isin(start_trips)]
        start_trips = start_trips.loc[start_stop].groupby('stop_seq_id').first()['trip_id'].values

        # TODO any way to reduce end nodes to one per stop sequence too?
        # challenge is that whereas with start trips we could look for soonest
        # departing one, we can't use a similar approach for end trips since
        # we don't know when the soonest one is (the soonest end trip may not
        # be accessible from the soonest start trip)
        # NOTE: actually, in my tests, it seems like the routing took _less_
        # time with more end nodes

        # find closest transfer stops for these trips
        start_nodes = [self._next_node_stop(trip_iid, start_stop) for trip_iid in start_trips]
        end_nodes = [self._next_node_stop(trip_iid, end_stop) for trip_iid in end_trips]

        # add START and END nodes to simplify pathfinding
        self.trip_network.add_edges_from([('START', node, {'weight': travel_time}) for node, travel_time in start_nodes])
        self.trip_network.add_edges_from([(node, 'END', {'weight': travel_time}) for node, travel_time in end_nodes])

        length, path = nx.single_source_dijkstra(self.trip_network, 'START', target='END', weight=self._get_transit_time)
        self.trip_network.remove_nodes_from(['START', 'END'])
        path[0], path[-1] = start_stop, end_stop
        return path, length

    def _next_node_stop(self, trip_id, stop_id, reverse=False):
        """given a trip iid and stop iid, find the soonest
        stop in this trip that has a node in the trip network
        (so we can use it for trip-level routing).
        - if the specified stop _is_ a node in the trip network, just
        reutrn that node.
        - if `reverse` is False, return the _soonest_ node (i.e. the
        first to come _after_ the specified stop iid)
        - if `reverse` is True, instead find the most _recent_ node (i.e. the
        first to come _before_ the specified stop iid_"""
        stop_iids = self.trips_to_transfer_stops[trip_id]

        # if this is already a network node, just use that
        if stop_id in stop_iids:
            return (trip_id, stop_id), 0

        # should be sorted in stop sequence/dep sec
        all_stops = self.trip_stops.get_group(trip_id)
        stop_dep_sec = all_stops[all_stops.stop_id == stop_id]['dep_sec'].iat[0]
        if reverse:
            order_filter = all_stops['dep_sec'] < stop_dep_sec
        else:
            order_filter = all_stops['dep_sec'] > stop_dep_sec
        stop_id, arr_sec = all_stops[
            order_filter & (all_stops['stop_id'].isin(stop_iids))
        ][['stop_id', 'arr_sec']].values[0]

        # the travel time calcluation isn't super precise,
        # given that, if we're going backwards (reverse=True)
        # we should be subtracting the to-stop's arrival time
        # from the from-stop's departure time.
        return (trip_id, stop_id), abs(arr_sec - stop_dep_sec)
