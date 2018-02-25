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
import pandas as pd
import networkx as nx
from tqdm import tqdm
from functools import partial
from datetime import timedelta
from scipy.spatial import KDTree
from collections import defaultdict
from itertools import product, starmap
from . import util, enum

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

base_transfer_time = 2*60 # lower-bound time-delta overhead for changing trips
footpath_delta_base = 2*60 # footpath_delta = delta_base + km / speed_kmh
footpath_speed_kmh = 5 / 3600
footpath_delta_max = 7*60 # all footpaths longer than that are discarded as invalid
footpath_closest_stops = 5 # number of closest stops to consider for non-same stop walking transfer

# TODO standardize the internal trip/stop id stuff so
# that it's always iid except at public user input/output points

class Transit:
    def __init__(self, gtfs_path, save_path, closest_indirect_transfers=2):
        """
        `closest_indirect_transfers` determines the number of closest stops for which
        indirect (walking) transfers are generated for. if you encounter a lot of
        "no path" errors, you may want to increase this number as it will be more likely
        to link separate routes. but note that it exponentially increases the processing time
        and can drastically increase memory usage.
        """
        gtfs = util.load_gtfs(gtfs_path)
        self._process_gtfs(gtfs)

        # TODO this can come after we figure out general trip routing
        # self._parse_calendar(gtfs)

        # prep kdtree for stop nearest neighbor querying;
        # only consider stops that are in trips
        logger.debug('Spatial-indexing stops...')
        stop_coords = self.stops[['stop_lat', 'stop_lon']].values
        self._kdtree = KDTree(stop_coords)

        self._transfer_times = {}

        if os.path.exists(save_path):
            logger.debug('Loading existing trip network...')
            def nodetype(u):
                t, s = u[1:-1].split(',')
                return int(t), int(s)
            self.trip_network = nx.read_edgelist(save_path,
                                                 data=True,
                                                 delimiter='\t',
                                                 create_using=nx.DiGraph(),
                                                 nodetype=nodetype)

            with open('/tmp/foo.json', 'r') as f:
                self.trips_to_transfer_stops = {int(i): s for i, s in json.load(f).items()}
            with open('/tmp/bar.json', 'r') as f:
                self._transfer_times = json.load(f)
        else:
            logger.debug('No existing trip network, computing new one')
            self.trip_network = self._compute_trip_network(closest_indirect_transfers)

            logger.debug('Saving trip network...')
            nx.write_edgelist(self.trip_network, save_path, data=True, delimiter='\t')
            with open('/tmp/foo.json', 'w') as f:
                json.dump(self.trips_to_transfer_stops, f)
            with open('/tmp/bar.json', 'w') as f:
                json.dump(self._transfer_times, f)

        logger.debug('Done')

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
        to_replace = {
            'trip_id': {v:k for k, v in self.trips['trip_id'].items()},
            'stop_id': {v:k for k, v in self.stops['stop_id'].items()}
        }
        timetable.replace(to_replace=to_replace, inplace=True)
        # TODO see if this is faster?
        # timetable['trip_id'] = timetable['trip_id'].map(lambda id: self.trips['trip_id'].Index)
        # timetable['stop_id'] = timetable['stop_id'].map(lambda id: self.trips['stop_id'].Index)

        # convert gtfs time strings to equivalent integer seconds
        # so we can leverage pandas indexing for performance reasons
        times_in_seconds = timetable.apply(
            lambda row: (
                util.gtfs_time_to_secs(row.arrival_time),
                util.gtfs_time_to_secs(row.departure_time)),
            axis=1)
        timetable['arr_sec'], timetable['dep_sec'] = zip(*times_in_seconds)

        # map trip_id->[stops]
        # sort by stop sequence so we know each trip group
        # has stops in the correct order
        # TODO rename this, was self.trips
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
            # TODO we can probably replace these with integers too
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


    def _stop_iids(self, stop_ids):
        # from stop_ids->stop_iids (internal stop ids)
        return self.stops[self.stops['stop_id'].isin(stop_ids)].index.values

    def _trip_iids(self, trip_ids):
        # from stop_ids->stop_iids (internal stop ids)
        return self.trips[self.trips['trip_id'].isin(trip_ids)].index.values

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

        # # TODO cleanup
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
        # TODO vectorize
        times = [
            util.walking_time(coord, (lat, lon), footpath_delta_base, footpath_speed_kmh)
            for lat, lon in stops[['stop_lat', 'stop_lon']].values]

        # pair as `(stop_iid, time)`
        return list(zip(idxs, times))

    def trip_route(self, start_stop, end_stop, dt):
        """compute a trip-level route between
        a start and an end stop for a given datetime"""
        # convert to iids
        # TODO this does not keep input order
        # start_stop, end_stop = self._stop_iids([start_stop, end_stop])
        start_stop = self._stop_iids([start_stop])[0]
        end_stop = self._stop_iids([end_stop])[0]

        # look only for trips starting after the departure time
        seconds = util.time_to_secs(dt.time())
        start_trips = self.stops_trips_sched.loc[start_stop].loc[seconds:]['trip_id'].values
        end_trips = self.stops_trips_sched.loc[end_stop].loc[seconds:]['trip_id'].values

        # if the same trip is in the start and end sets,
        # it means we can take just that trip, no transfers
        # so just return that
        same_trips = set(start_trips) & set(end_trips)
        if same_trips:
            return [[(t, start_stop), (t, end_stop)] for t in same_trips]

        # SKIPPING FOR NOW
        # only consider trips which are operating for the datetime
        # service_ids = set(self.services_for_dt(dt)) | set(self.services_for_dt(dt + timedelta(days=1)))
        # trip_ids = self.trips_for_services(service_ids)
        # start_trips = set(start_trips) & trip_ids
        # end_trips = set(end_trips) & trip_ids

        print('start trips', start_trips)
        print('end trips', end_trips)

        # filter equivalent start trips down to soonest-departing ones
        # the `first()` call assumes that these are sorted by departure time,
        # which they should be
        start_trips = self.stops_trips_sched[self.stops_trips_sched.trip_id.isin(start_trips)].loc[start_stop].groupby('stop_seq_id').first()['trip_id'].values

        # TODO can first check if (start_trip, start_stop) exists
        # same for end nodes, before searching for closest transfer stop
        # find closest transfer stops for these trips
        # TODO this can be done better/faster
        start_nodes = []
        for trip_iid in start_trips:
            stop_iids = self.trips_to_transfer_stops[trip_iid]
            # TODO should select after start_stop
            # instead of iterating over all of them
            seen = False
            # assuming sorted in stop sequence
            all_stops = self.trip_stops.get_group(trip_iid)
            all_stops = all_stops[all_stops.dep_sec >= seconds]['stop_id'].values
            # something like:?
            # all_stops = all_stops[(all_stops.dep_sec >= seconds) & (all_stops.stop_id.isin(transfer_stop_iids))]
            for stop_iid in all_stops:
                if not seen and stop_iid == start_stop:
                    seen = True
                if seen and stop_iid in stop_iids:
                    start_nodes.append((trip_iid, stop_iid))
                    break
        end_nodes = []
        for trip_iid in end_trips:
            stop_iids = self.trips_to_transfer_stops[trip_iid]
            # TODO should select before end_stop
            # instead of iterating over all of them
            seen = False
            # assuming sorted in stop sequence, go in reverse
            for stop_iid in self.trip_stops.get_group(trip_iid)['stop_id'].values[::-1]:
                if not seen and stop_iid == end_stop:
                    seen = True

                if seen and stop_iid in stop_iids:
                    end_nodes.append((trip_iid, stop_iid))
                    break

        # find shortest paths between each start-end trip pair
        paths = []
        print('start nodes', start_nodes)
        print('end nodes', end_nodes)
        # TODO any way to further reduce these combinations?
        # could cache which trips connect to which other trips,
        # and immediately discard combinations which arent in that cache
        for start_node, end_node in product(start_nodes, end_nodes):
            try:
                # TODO go according to travel time, not just transfer time
                path = nx.dijkstra_path(self.trip_network, start_node, end_node, self._get_transit_time)
            except nx.exception.NetworkXNoPath:
                print('no path found for: ', start_node, end_node)
                continue
            paths.append(path)

        return paths

    # =============================
    # TEMP NOT WORRYING ABOUT THESE
    # =============================
    # def services_for_dt(self, dt):
    #     """returns operating service ids
    #     for a given datetime"""
    #     # gives weekday as an int,
    #     # where `monday = 0`
    #     weekday = enum.Weekday(dt.weekday())

    #     # get list of service ids as a copy
    #     # so we can add/remove according to service changes
    #     services = self.service_days[weekday][:]

    #     # check if there are any service changes for the date
    #     for service_id, change in self.service_changes_for_dt(dt).items():
    #         if change is enum.ServiceChange.ADDED:
    #             services.append(service_id)
    #         else:
    #             try:
    #                 services.remove(service_id)
    #             except ValueError:
    #                 pass
    #     return services

    # def service_changes_for_dt(self, dt):
    #     """return a dict of `{service_id: ServiceChange}`
    #     describing service changes (additions or removals
    #     for a given datetime"""
    #     try:
    #         changes = self.service_changes.get_group(dt.date())
    #         return {c.service_id: enum.ServiceChange(c.exception_type) for i, c in changes.iterrows()}
    #     except KeyError:
    #         return {}

    # def trips_for_services(self, service_ids):
    #     """get trip ids that encompass a given list of service ids"""
    #     trips = set()
    #     for service_id in service_ids:
    #         trip_ids = self.services.get(service_id, [])
    #         trips = trips | set(trip_ids)
    #     return trips
    #
    # def _parse_calendar(self, gtfs):
    #     """parse calendar data for service days/changes/exceptions"""
    #     # associate services with their operating weekdays
    #     # NOTE this data provies start and end dates for services
    #     # but for our simulation we are treating this timetable as ongoing
    #     calendar = gtfs['calendar']
    #     service_days = {day: [] for day in enum.Weekday}
    #     for i, row in calendar.iterrows():
    #         service_id = row.service_id
    #         for day, services in service_days.items():
    #             if row[day.name.lower()] == 1:
    #                 services.append(service_id)
    #     self.service_days = service_days

    #     # parse 'date' column as date objects
    #     # then group by date, so we can quickly query
    #     # service changes for a given date
    #     service_changes = gtfs['calendar_dates']
    #     service_changes['date'] = pd.to_datetime(service_changes.date, format='%Y%m%d').dt.date
    #     self.service_changes = service_changes.groupby('date')

    #     # map service_id->[trip_ids]
    #     self.services = {name: group['trip_id'].values
    #                      for name, group in gtfs['trips'].groupby('service_id')}


