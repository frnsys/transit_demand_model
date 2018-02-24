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

import os
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


class Transit:
    def __init__(self, gtfs_path, save_path, closest_indirect_transfers=3):
        """
        `closest_indirect_transfers` determines the number of closest stops for which
        indirect (walking) transfers are generated for. if you encounter a lot of
        "no path" errors, you may want to increase this number as it will be more likely
        to link separate routes. but note that it exponentially increases the processing time
        and can drastically increase memory usage.
        """
        gtfs = util.load_gtfs(gtfs_path)
        self._parse_calendar(gtfs)
        self._parse_trips(gtfs)
        self._index_stops(gtfs)
        self._transfer_times = {}

        if os.path.exists(save_path):
            logger.debug('Loading existing trip network...')
            self.trip_network = nx.read_edgelist(save_path, data=True, create_using=nx.MultiDiGraph(), nodetype=int)
        else:
            logger.debug('No existing trip network, computing new one')
            self.trip_network = self._compute_trip_network(gtfs, closest_indirect_transfers)

            logger.debug('Saving trip network...')
            nx.write_edgelist(self.trip_network, save_path, data=True)
        logger.debug('Done')

    def _parse_calendar(self, gtfs):
        """parse calendar data for service days/changes/exceptions"""
        # associate services with their operating weekdays
        # NOTE this data provies start and end dates for services
        # but for our simulation we are treating this timetable as ongoing
        calendar = gtfs['calendar']
        service_days = {day: [] for day in enum.Weekday}
        for i, row in calendar.iterrows():
            service_id = row.service_id
            for day, services in service_days.items():
                if row[day.name.lower()] == 1:
                    services.append(service_id)
        self.service_days = service_days

        # parse 'date' column as date objects
        # then group by date, so we can quickly query
        # service changes for a given date
        service_changes = gtfs['calendar_dates']
        service_changes['date'] = pd.to_datetime(service_changes.date, format='%Y%m%d').dt.date
        self.service_changes = service_changes.groupby('date')

        # map service_id->[trip_ids]
        self.services = {name: group['trip_id'].values
                         for name, group in gtfs['trips'].groupby('service_id')}

    def _index_stops(self, gtfs):
        """prep kdtree for stop nearest neighbor querying;
        only consider stops that are in trips"""
        logger.debug('Spatial-indexing stops...')

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

        # create reverse map of stop_id->iid
        self.stops_iids = {r.stop_id: i for i, r in self.stops.iterrows()}

        # build kdtree index
        stop_coords = self.stops[['stop_lat', 'stop_lon']].values
        self._kdtree = KDTree(stop_coords)

    def _parse_trips(self, gtfs):
        """parse trips (stop sequences) data"""
        logger.debug('Parsing trips...')
        timetable = gtfs['stop_times']

        # map trip_id->[stops]
        # sort by stop sequence so we know each trip group
        # has stops in the correct order
        self.trips = timetable.sort_values('stop_sequence').groupby('trip_id')

        # create map of iid->trip_id
        # and reverse map of trip_id->iid
        trip_ids = sorted(self.trips.groups.keys())
        self.iids_trips = {i: trip_id for i, trip_id in enumerate(trip_ids)}
        self.trips_iids = {trip_id: i for i, trip_id in enumerate(trip_ids)}

        # convert gtfs time strings to equivalent integer seconds
        # so we can leverage pandas indexing for performance reasons
        times_in_seconds = timetable.apply(
            lambda row: (
                util.gtfs_time_to_secs(row.arrival_time),
                util.gtfs_time_to_secs(row.departure_time)),
            axis=1)
        timetable['arr_sec'], timetable['dep_sec'] = zip(*times_in_seconds)

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
        self.trips_to_stop_seq = {}
        self.stop_seq_to_trips = defaultdict(list)
        for trip_id, stops in self.trips:
            stop_ids = stops['stop_id'].values

            # generate an id for this stop sequence
            stop_seq_id = '_'.join(map(str, stop_ids))

            # map stop sequences to their trips
            self.stop_seq_to_trips[stop_seq_id].append(trip_id)

            # reverse lookup so we can get
            # the stop sequence graph from a trip_id
            self.trips_to_stop_seq[trip_id] = stop_seq_id

        timetable['stop_seq_id'] = timetable.apply(lambda row: self.trips_to_stop_seq[row.trip_id], axis=1)

        # index the stops timetable so that we can quickly
        # lookup departures for a particular stop_id
        # and sort based on departure time in seconds
        # for slicing based on departure times.
        # this lets us, for example,
        # find trips departing from stop x after 10:00:00
        self.stops_trips_sched = timetable.set_index(['stop_id', 'dep_sec']).sort_index(level='dep_sec')

        # TODO still needed?
        # create graphs for each stop sequence
        # self.stop_seq_graphs = {}
        # for stop_seq_str, stop_ids in stop_seqs.items():
        #     g = nx.DiGraph()
        #     for frm, to in zip(stop_ids, stop_ids[1:]):
        #         g.add_edge(frm, to)
        #     self.stop_seq_graphs[stop_seq_str] = g

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

        # TODO use existing self.stops_trips_sched
        # stop_seqs = stop_seqs.set_index('dep_sec').sort_index()
        # stop_seqs = self.stops_trips_sched.groupby('stop_id')
        stop_seqs = self.stops_trips_sched.reset_index(level='stop_id').groupby('stop_id')

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
        for edges in tqdm(map(fn, self.stops.itertuples()), total=len(self.stops)):
            for frm, to, data in edges:
                trip_network.add_edge(frm, to, **data)

        return trip_network

    def _process_direct_transfers(self, stop_id, group):
        """process direct transfers that occur at the given stop.
        """
        stop_iid = self.stops_iids[stop_id]
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
            frm = self.trips_iids[frm]
            for to, ssid in valid_transfers[['trip_id', 'stop_seq_id']].values:
                # already seen this stop sequence?
                # if so, skip
                if ssid in seen:
                    continue

                seen.add(ssid)
                to = self.trips_iids[to]

                yield frm, to, {'stop_id': stop_iid}
                                # 'transfer_time': base_transfer_time} TODO dont
                                # need this b/c its a constant

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
        from_trips = stop_trips.get_group(row.stop_id)
        from_trips = from_trips[['trip_id', 'arr_sec', 'stop_seq_id']].values

        this_stop_iid = self.stops_iids[row.stop_id]
        for stop_id, transfer_time in neighbors:
            group = stop_trips.get_group(stop_id)
            stop_iid = self.stops_iids[stop_id]

            # cache walking transfer times between stops
            transfer_key = '{}->{}'.format(this_stop_iid, stop_iid)
            if transfer_key not in self._transfer_times:
                self._transfer_times[transfer_key] = transfer_time

            for frm, arrival_time, stop_seq_id in from_trips:
                arrival_time_after_walking = arrival_time + transfer_time

                # can only transfer to trips that depart
                # after the incoming trip arrives
                valid_transfers = group.loc[arrival_time_after_walking:]

                # (see note in process_direct_transfers)
                seen = {stop_seq_id}
                frm = self.trips_iids[frm]
                for to, ssid in valid_transfers[['trip_id', 'stop_seq_id']].values:
                    if ssid in seen:
                        continue

                    seen.add(ssid)
                    to = self.trips_iids[to]

                    yield frm, to, {
                        'from_stop_id': this_stop_iid,
                        'to_stop_id': stop_iid}
                        # 'transfer_time': transfer_time} # TODO don't need this
                        # will look up from self._transfer_times

    def _get_transit_time(frm, to, edges):
        import ipdb; ipdb.set_trace()
        return 1

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

        # pair as `(stop_id, time)`
        return list(zip(stops['stop_id'].values, times))

    def services_for_dt(self, dt):
        """returns operating service ids
        for a given datetime"""
        # gives weekday as an int,
        # where `monday = 0`
        weekday = enum.Weekday(dt.weekday())

        # get list of service ids as a copy
        # so we can add/remove according to service changes
        services = self.service_days[weekday][:]

        # check if there are any service changes for the date
        for service_id, change in self.service_changes_for_dt(dt).items():
            if change is enum.ServiceChange.ADDED:
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
            return {c.service_id: enum.ServiceChange(c.exception_type) for i, c in changes.iterrows()}
        except KeyError:
            return {}

    def trips_for_services(self, service_ids):
        """get trip ids that encompass a given list of service ids"""
        trips = set()
        for service_id in service_ids:
            trip_ids = self.services.get(service_id, [])
            trips = trips | set(trip_ids)
        return trips

    def trip_route(self, start_stop, end_stop, dt):
        """compute a trip-level route between
        a start and an end stop for a given datetime"""
        # look only for trips starting after the departure time
        seconds = util.time_to_secs(dt.time())
        start_trips = self.stops_trips_sched.loc[start_stop].loc[seconds:]['trip_id'].values
        end_trips = self.stops_trips_sched.loc[end_stop].loc[seconds:]['trip_id'].values

        # only consider trips which are operating for the datetime
        service_ids = set(self.services_for_dt(dt)) | set(self.services_for_dt(dt + timedelta(days=1)))
        trip_ids = self.trips_for_services(service_ids)
        start_trips = set(start_trips) & trip_ids
        end_trips = set(end_trips) & trip_ids

        # convert to network ids
        start_trips = [self.trips_iids[id] for id in start_trips]
        end_trips = [self.trips_iids[id] for id in end_trips]

        # find shortest paths between each start-end trip pair
        paths = []
        for start_trip, end_trip in tqdm(product(start_trips, end_trips)):
            try:
                # TODO go according to travel time, not just transfer time
                path = nx.dijkstra_path(self.trip_network, start_trip, end_trip, self._get_transit_time)
                path  = [self.iids_trips[i] for i in path]
            except nx.exception.NetworkXNoPath:
                continue
            paths.append(path)
        return paths

    # TODO BELOW: POTENTIAL CUTS
    def graph_for_trip(self, trip_id):
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

    def equivalent_trips(self, trip_id):
        """returns set of equivalent trips for a trip_id,
        i.e. those that have the same sequence of stops
        (though the trips do not need to start/end at the same times)"""
        stop_seq_str = self.trip_to_stop_seq[trip_id]
        equivalent = set(self.stop_seq_trips[stop_seq_str]) - {trip_id}
        return equivalent
