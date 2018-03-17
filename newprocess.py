import hashlib
import networkx as nx
from gtfs import util
from collections import defaultdict
from tqdm import tqdm
from gtfs.calendar import Calendar
from scipy.spatial import KDTree
from time import time as TIME
from gtfs.next_dep import weight


s = TIME()

BASE_TRANSFER_TIME = 120

gtfs = util.load_gtfs('data/gtfs/gtfs_bhtransit.zip')

# TODO try selecting just metro routes for now
# import ipdb; ipdb.set_trace()

timetable = gtfs['stop_times']

# convert gtfs time strings to equivalent integer seconds
# so we can leverage pandas indexing for performance reasons
changes = timetable.apply(
    lambda row: (
        util.gtfs_time_to_secs(row.arrival_time),
        util.gtfs_time_to_secs(row.departure_time)),
    axis=1)
timetable['arr_sec'], timetable['dep_sec'] = zip(*changes)

# map trip_id->[stops]
# sort by stop sequence so we know each trip group
# has stops in the correct order
trip_stops = timetable.sort_values('stop_sequence').groupby('trip_id')

# compute stop sequence hashes to identify equivalent trips
print('computing stop sequence hashes')
stop_seq_ids_to_stop_seqs = {}
trips_to_stop_seq = {}
for trip_id, stops in tqdm(trip_stops):
    # generate an id for this stop sequence
    stop_seq = stops['stop_id'].values.tolist()
    stop_seq_id = '_'.join(map(str, stop_seq)).encode('utf8')
    stop_seq_id = hashlib.md5(stop_seq_id).hexdigest()
    stop_seq_ids_to_stop_seqs[stop_seq_id] = stop_seq

    # reverse lookup so we can get
    # the stop sequence graph from a trip_id
    trips_to_stop_seq[trip_id] = stop_seq_id

# group trips by stop seq and use (stop_seq, stop) nodes
# this goes from 4705 trips to 791 stop seqs
# this is b/c trips with equivalent stop sequences
# are the same trip, just represented for different service days
stop_seqs = defaultdict(list)
for trip_id, stop_seq in trips_to_stop_seq.items():
    stop_seqs[stop_seq].append(trip_id)

# merge trip frequency entries where possible
print('merging and processing trip frequencies')
freqs = util.compress_frequencies(gtfs['frequencies'])
stops_spans = defaultdict(lambda: defaultdict(defaultdict))
stop_seq_scheds = {}
trip_scheds = {}
for trip_id, spans in tqdm(freqs.items()):
    trip_sched, stop_spans = util.trip_spans_to_stop_spans(
        trip_id,
        spans,
        trip_stops.get_group(trip_id).itertuples())
    # TODO may want to overwrite arr_sec and
    # dep_sec in self.trip_stops with trip_sched
    # so they are relative rather than absolute times
    trip_scheds[trip_id] = trip_sched
    stop_seq = trips_to_stop_seq[trip_id]

    # assuming that all trips for a stop seq
    # share a time schedule, i.e. have the same
    # transit time between stops
    stop_seq_scheds[stop_seq] = trip_sched

    for stop_iid, spans in stop_spans:
        stops_spans[stop_iid][stop_seq][trip_id] = spans

# turn stop seq scheds into graphs
stop_seq_g = nx.DiGraph()
for stop_seq, sched in stop_seq_scheds.items():
    for stop_a, stop_b in zip(sched, sched[1:]):
        stop_seq_g.add_edge((stop_seq, stop_a.stop_id), (stop_seq, stop_b.stop_id), time=stop_b.transit_time)

calendar = Calendar(gtfs)
stop_seqs_to_service_days = defaultdict(set)
for service_id, trip_ids in calendar.services.items():
    for trip_id in trip_ids:
        stop_seq = trips_to_stop_seq[trip_id]
        stop_seqs_to_service_days[stop_seq].update(calendar.service_days[service_id])

G = nx.DiGraph()

# Direct transfers
print('direct transfers')
for stop_id, stop_seqs in tqdm(stops_spans.items()):
    if len(stop_seqs) <= 1:
        continue
    for stop_seq, trips_spans in stop_seqs.items():
        spans = sum(trips_spans.values(), [])
        frm = (stop_seq, stop_id)
        for stop_seq_, trips_spans_ in stop_seqs.items():
            spans_ = sum(trips_spans_.values(), [])
            if stop_seq == stop_seq_ \
                or not stop_seqs_to_service_days[stop_seq] & stop_seqs_to_service_days[stop_seq_] \
                or not util.transfer_possible(spans, spans_, transfer_time=BASE_TRANSFER_TIME):
                continue
            to = (stop_seq_, stop_id)
            G.add_edge(frm, to)


footpath_delta_base = 2*60 # footpath_delta = delta_base + km / speed_kmh
footpath_speed_kmh = 5 / 3600
footpath_delta_max = 7*60 # all footpaths longer than that are discarded as invalid

stop_coords = gtfs['stops'][['stop_lat', 'stop_lon']].values
_kdtree = KDTree(stop_coords)
def closest_stops(coord, n=5):
    """closest n stop ids for given coord, paired
    with estimated walking time"""
    # TODO we should probably use UTM positions instead of lat lons
    # for more accurate distances
    dists, idxs = _kdtree.query(coord, k=n)

    # convert indices to stops
    stops = gtfs['stops'].loc[idxs]

    # compute estimated walking times
    times = [
        (id, util.walking_time(coord, (lat, lon), footpath_delta_base, footpath_speed_kmh))
        for id, lat, lon in stops[['stop_id', 'stop_lat', 'stop_lon']].values]

    # pair as `(stop_iid, time)`
    # return list(zip(idxs, times))
    return times

closest = 5
print('indirect transfers')
for stop in tqdm(gtfs['stops'].itertuples(), total=len(gtfs['stops'])):
    coord = stop.stop_lat, stop.stop_lon

    # get closest stops to this one
    neighbors = closest_stops(coord, n=closest+1)

    # skip the first, it's the stop itself
    neighbors = neighbors[1:]

    # filter out long transfers
    neighbors = [n for n in neighbors if n[1] <= footpath_delta_max]

    # for each stop sequence departing from this stop
    stop_seqs = stops_spans[stop.stop_id]
    for stop_seq, trips_spans in stop_seqs.items():
        spans = sum(trips_spans.values(), [])
        frm = (stop_seq, stop.stop_id)

        # compare to stop sequences departing from neighbor stops
        for stop_id, transfer_time in neighbors:
            stop_seqs_ = stops_spans[stop_id]
            transfer_time = max(BASE_TRANSFER_TIME, transfer_time)

            for stop_seq_, trips_spans_ in stop_seqs_.items():
                spans_ = sum(trips_spans_.values(), [])
                if stop_seq == stop_seq_ \
                    or not stop_seqs_to_service_days[stop_seq] & stop_seqs_to_service_days[stop_seq_] \
                    or not util.transfer_possible(spans, spans_, transfer_time=transfer_time):
                    continue
                to = (stop_seq_, stop_id)
                G.add_edge(frm, to, time=transfer_time)

# link stop_seq-stop nodes
stop_seqs_to_transfer_stops = defaultdict(set)
for stop_seq, stop_id in G.nodes:
    stop_seqs_to_transfer_stops[stop_seq].add(stop_id)

for stop_seq, stop_ids in stop_seqs_to_transfer_stops.items():
    stops = stop_seq_ids_to_stop_seqs[stop_seq]
    stops = [stop for stop in stops if stop in stop_ids]
    # note: it's possible the same stop appears multiple times
    # in a stop sequence (e.g. if a trip loops back in some way)
    for stop_a, stop_b in zip(stops, stops[1:]):
        time = nx.dijkstra_path_length(
            stop_seq_g,
            (stop_seq, stop_a),
            (stop_seq, stop_b),
            weight='time')
        G.add_edge(
            (stop_seq, stop_a),
            (stop_seq, stop_b),
            time=time
        )


import numpy as np
def next_soonest_vehicle(dep, mat):
    starts = mat[:,0]
    periods = mat[:,1]
    next_train_idxs = np.maximum(0, np.ceil((dep - starts)/periods))
    next_train_times = starts + (next_train_idxs * periods)
    next_train_times[mat[:,2] >= dep] = np.inf
    idx = np.argmin(next_train_times)
    return idx, next_train_times[idx]


# @profile
# def weight(cur_time, valid_stops_spans_mats, v, u, e, d):
#     frm_stop_seq, frm_stop = v
#     to_stop_seq, to_stop = u

#     # continuing on the same trip,
#     # just need transit time between these stops
#     if frm_stop_seq == to_stop_seq:
#         return None, e['time']

#     # else, transferring
#     transfer_time = e.get('time', BASE_TRANSFER_TIME)

#     # note that d is the distance to the node v.
#     # current time, including transfer time and transit time
#     time = cur_time + d + transfer_time

#     # find soonest-departing trip
#     trips_spans_mat = valid_stops_spans_mats[to_stop][to_stop_seq]
#     # TODO translate returned arr idx to trip id
#     try:
#         trip_id, dep_time = next_soonest_vehicle(time, trips_spans_mat)
#     except IndexError:
#         return None, float('inf')

#     # total travel time
#     transfer_time = dep_time - (time - transfer_time)
#     return trip_id, transfer_time


from itertools import count
from heapq import heappush, heappop
@profile
def dijkstra(G, sources, target, weight):
    push = heappush
    pop = heappop
    dists = {}  # dictionary of final distances
    seen = {}
    # fringe is heapq with 3-tuples (distance,c,node)
    # use the count c to avoid comparing nodes (may not be able to)
    c = count()
    fringe = []
    paths = {source: [source] for source in sources}
    for source in sources:
        seen[source] = 0
        push(fringe, (0, next(c), source))
    while fringe:
        (d, _, v) = pop(fringe)
        if v in dists:
            continue  # already searched this node.
        dists[v] = d
        if v == target:
            break
        for u, e in G._succ[v].items():
            _, cost = weight(v, u, e, dists[v])
            if cost is None:
                continue
            vu_dist = dists[v] + cost
            if u in dists:
                if vu_dist < dists[u]:
                    raise ValueError('Contradictory paths found:',
                                     'negative weights?')
            elif u not in seen or vu_dist < seen[u]:
                seen[u] = vu_dist
                push(fringe, (vu_dist, next(c), u))
                paths[u] = paths[v] + [u]

    # The optional predecessor and path dictionaries can be accessed
    # by the caller via the pred and paths objects passed as arguments.
    try:
        return dists[target], paths[target]
    except KeyError:
        raise nx.NetworkXNoPath('No path to {}.'.format(target))

print('preprocessing:', TIME() - s)


from datetime import datetime
valid_trips = calendar.trips_for_day(datetime.now())
# v = ('fc7afbd42eac6b6c22167e01b96b7cf0', '00107210303385')
# u = ('ea106f21a0a50bda74ac1631d12ca96e', '00107210303257')
# e = {'transfer_time': 258.52657829096506}
# weight(v, u, e, 18000, 0, valid_trips)

# filter to trips running today
valid_stops_spans = {}
valid_stops_spans_mats = {}
for stop_id, stop_seqs in stops_spans.items():
    valid_stops_spans[stop_id] = {}
    valid_stops_spans_mats[stop_id] = {}
    for stop_seq, trips_spans in stop_seqs.items():
        trips_spans = {tid: spans for tid, spans
                       in trips_spans.items()
                       if tid in valid_trips}
        valid_stops_spans[stop_id][stop_seq] = trips_spans
        all_spans = sum(trips_spans.values(), [])
        all_spans_mat = np.array([[s.start, s.period, s.last_dep] for s in all_spans], dtype=np.float32)
        valid_stops_spans_mats[(stop_seq, stop_id)] = all_spans_mat

from functools import partial

cur_time = 28800 # 8AM
s = TIME()
wfn = partial(weight, cur_time, valid_stops_spans_mats)
start = ('a45bed228cbd8a5d4312619194d03207', '00100153600230')
target = ('28ff8d521882e74f87c3cd1ca7d5e154', '00112885800062')
dist, path = dijkstra(G, {start}, target, wfn)
print(path)
print(dist)
print('routing:', TIME() - s)

# import ipdb; ipdb.set_trace()
