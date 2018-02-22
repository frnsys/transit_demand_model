import numpy as np
import networkx as nx
from gtfs import load_gtfs
from dateutil import parser
from scipy.spatial import KDTree
from itertools import tee, product
from collections import defaultdict
from datetime import datetime, date

# TODO some representation of time
# so we can plan with the bus schedules
now = datetime.now().timestamp()


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)

buses = load_gtfs('data/gtfs/gtfs_bhtransit.zip')

# stops are nodes in the bus network
# access with `stops.loc[stop_id]`
stops = buses['stops'].set_index('stop_id')

# routes group trips together as one service
# e.g. the L is a _route_ which consists
# of multiple trips, e.g. a train at 10AM, a train at 10:10AM, etc...
# this maps trip ids to their route ids.
trips = buses['trips'].set_index('trip_id')

# times describe sequences of stops
# (i.e. how they're linked together)
times = buses['stop_times'].groupby('trip_id')

# create network of route networks
G = nx.DiGraph()

# map of stop -> routes to see where transfers are
stops_routes = defaultdict(set)
for trip_id, df in times:
    route_id = trips.loc[trip_id]['route_id']

    df = df.sort_values('stop_sequence')

    # this might be redundant,
    # but perhaps some trips on the same route have different stops?
    # TODO verify if this does indeed happen
    for (i, row_i), (j, row_j) in pairwise(df.iterrows()):
        stop_i, stop_j = row_i['stop_id'], row_j['stop_id']
        stops_routes[stop_i].add(route_id)
        stops_routes[stop_j].add(route_id)

        # all routes are part of the same network
        # but we want to isolate routes to be subnetworks,
        # linked only at transfer stations.
        # this isolation is enforced by uniquely identifying
        # stop ids with their routes
        stop_i = '{}_{}'.format(route_id, stop_i)
        stop_j = '{}_{}'.format(route_id, stop_j)

        G.add_edge(stop_i, stop_j)
        data = G.nodes[stop_i]
        if 'arrivals' not in data:
            data['arrivals'] = set()
        if 'departures' not in data:
            data['departures'] = set()
        data['arrivals'].add(row_i['arrival_time'])
        data['departures'].add(row_i['departure_time'])

for node, data in G.nodes(data=True):
    data['arrivals'] = sorted(data.get('arrivals', []))
    data['departures'] = sorted(data.get('departures', []))

# link transfer stops
for stop_id, routes in stops_routes.items():
    for route_i in routes:
        for route_j in routes:
            if route_i == route_j:
                continue
            u = '{}_{}'.format(route_i, stop_id)
            v = '{}_{}'.format(route_j, stop_id)
            G.add_edge(u, v)


# stop coords for searching
stops = [(r.stop_lat, r.stop_lon) for i, r in buses['stops'].iterrows()]
stops = np.array(stops)
kdt = KDTree(stops)


def soonest(now, times):
    """return the next closest time
    from a list of times"""
    # TODO while we dont have actual dates
    # we eventually want to incorporate dates more properly
    # (more specifically, days of the week)
    times = [
        datetime.combine(
            date.min,
            parser.parse(t).time()) for t in times]
    now = datetime.combine(date.min, now.time())

    # bisecting would be faster...
    for t in times:
        if (t-now).total_seconds() >= 0:
            return t


def edge_weight(u, v, edges):
    # find next arrival time from current time
    # assuming that travel time between stops
    # is the same, regardless of current time
    start_time = G.nodes[u]
    end_time = G.nodes[v]

    # TODO add transfer time
    return 1


def planned_trip(time, start, end):
    time = now # TODO
    pass


# TODO
# for bus routing, we don't need to actually find a path
# through the route network
# we just find the trip that starts and ends with each
def route(start, end, time):
    """start & end are arbitrary coordinates"""
    starts = closest_stops(start)
    ends = closest_stops(end)

    # find soonest trips for each end stop
    # we start with end stops b/c
    # we want to minimize for arrival time
    soonest_trips = []
    for stop_id, dist in ends:
        # get all trips for this stop id
        trips = buses['stop_times'].loc[buses['stop_times']['stop_id'] == stop_id]

        # filter to trips that are coming up
        idx = trips.apply(lambda x: parser.parse(x['arrival_time']).time() > time, axis=1)
        trips = trips[idx]

    # also filter to future trips for start
    for stop_id, dist in starts:
        # get all trips for this stop id
        trips = buses['stop_times'].loc[buses['stop_times']['stop_id'] == stop_id]

        # filter to trips that are coming up
        idx = trips.apply(lambda x: parser.parse(x['departure_time']).time() > time, axis=1)
        trips = trips[idx]


    import ipdb; ipdb.set_trace()
    for (start, d_s), (end, d_e) in product(starts, ends):
        # TODO incorporate times of walking to/from start/end stops
        # and waiting for next bus at start
        path = shortest_path(start, end)
    return path

# 102656000014

def shortest_path(u, v):
    return nx.dijkstra_path(G, u, v, edge_weight)


def closest_stops(coord, k=5):
    """closest k stop ids for given coord"""
    dists, idxs = kdt.query(coord, k=k)
    stops = buses['stops'].loc[idxs]
    return zip(stops['stop_id'].tolist(), dists)


def stops_to_nodes(stops):
    results = []
    for stop_id, dist in stops:
        for route_id in stops_routes[stop_id]:
            results.append((
                '{}_{}'.format(route_id, stop_id), dist))
    return results

start = (-19.947662, -43.984870)
end = (-19.923902, -43.920878)
route(start, end)


# - find closest bus points to start point
# - find shortest route through bus network
#   - edge weights should incorporate weighting time, anticipated crowdedness?

# TODO integrate the following
# - trips tell us (among other things) what `service_id` each trip has so we know which days the services run
# - trips tell us arrival/departure times, integrate that
# - route planning, should take into account arrival/departure times, support
# adding delays
# - need to subroute between stops for processing actual bus travel
