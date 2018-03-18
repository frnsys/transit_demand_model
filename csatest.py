# import hashlib
from gtfs import util
from collections import defaultdict, namedtuple
from tqdm import tqdm
from time import time as TIME
from gtfs.calendar import Calendar
from scipy.spatial import KDTree
import numpy as np
from csa import csa

TripStop = namedtuple('TripStop', ['stop_id', 'rel_arr', 'rel_dep'])
StopSpan = namedtuple('StopSpan', ['arr', 'dep'])
Connection = namedtuple('Connection', ['dep_time', 'dep_stop', 'arr_time', 'arr_stop', 'trip_id'])

def get_connections(trip_id, spans, trip_stops):
    """given a set of spans for a trip,
    convert the trip stop schedule to a schedule
    of relative arrival/departure times,
    and compute arrival/departure spans for each stop along the trip"""
    starts = []
    for start, end, headway in spans:
        starts.extend(np.arange(start, end, headway))

    trip_sched = []
    stops_spans = []
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
        # trip_sched.append(TripStop(stop_id=stop.stop_id, rel_arr=arr, rel_dep=dep))

        stop_spans = []
        for start in starts:
            stop_spans.append(Connection(arr_time=arr+start, dep_time=dep+start, arr_stop=arr_stop.stop_id, dep_stop=dep_stop.stop_id, trip_id=trip_id))
        # stops_spans.append((stop.stop_id, stop_spans))
        stops_spans.append((None, stop_spans))
    return trip_sched, stops_spans

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
# print('computing stop sequence hashes')
# stop_seq_ids_to_stop_seqs = {}
# trips_to_stop_seq = {}
# for trip_id, stops in tqdm(trip_stops):
#     # generate an id for this stop sequence
#     stop_seq = stops['stop_id'].values.tolist()
#     stop_seq_id = '_'.join(map(str, stop_seq)).encode('utf8')
#     stop_seq_id = hashlib.md5(stop_seq_id).hexdigest()
#     stop_seq_ids_to_stop_seqs[stop_seq_id] = stop_seq

#     # reverse lookup so we can get
#     # the stop sequence graph from a trip_id
#     trips_to_stop_seq[trip_id] = stop_seq_id

# # group trips by stop seq and use (stop_seq, stop) nodes
# # this goes from 4705 trips to 791 stop seqs
# # this is b/c trips with equivalent stop sequences
# # are the same trip, just represented for different service days
# stop_seqs = defaultdict(list)
# for trip_id, stop_seq in trips_to_stop_seq.items():
#     stop_seqs[stop_seq].append(trip_id)

calendar = Calendar(gtfs)

# reduce connections to only those for this day
from datetime import datetime
valid_trips = calendar.trips_for_day(datetime.now())

# merge trip frequency entries where possible
print('merging and processing trip frequencies')
freqs = util.compress_frequencies(gtfs['frequencies'])
stops_spans = defaultdict(lambda: defaultdict(defaultdict))
stop_seq_scheds = {}
trip_scheds = {}
all_connections = []
for trip_id, spans in tqdm(freqs.items()):
    if trip_id not in valid_trips:
        continue
    trip_sched, stop_spans = get_connections(
        trip_id,
        spans,
        trip_stops.get_group(trip_id).itertuples())
    for _, spans in stop_spans:
        all_connections.extend(spans)

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



# closest = 5
# print('indirect transfers')
# for stop in tqdm(gtfs['stops'].itertuples(), total=len(gtfs['stops'])):
#     coord = stop.stop_lat, stop.stop_lon

#     # get closest stops to this one
#     neighbors = closest_stops(coord, n=closest+1)

#     # skip the first, it's the stop itself
#     neighbors = neighbors[1:]

#     # filter out long transfers
#     neighbors = [n for n in neighbors if n[1] <= footpath_delta_max]

#     # for each stop sequence departing from this stop
#     stop_seqs = stops_spans[stop.stop_id]
#     for stop_seq, trips_spans in stop_seqs.items():
#         spans = sum(trips_spans.values(), [])
#         frm = (stop_seq, stop.stop_id)

#         # compare to stop sequences departing from neighbor stops
#         for stop_id, transfer_time in neighbors:
#             stop_seqs_ = stops_spans[stop_id]
#             transfer_time = max(BASE_TRANSFER_TIME, transfer_time)

#             for stop_seq_, trips_spans_ in stop_seqs_.items():
#                 spans_ = sum(trips_spans_.values(), [])
#                 if stop_seq == stop_seq_ \
#                     or not stop_seqs_to_service_days[stop_seq] & stop_seqs_to_service_days[stop_seq_] \
#                     or not util.transfer_possible(spans, spans_, transfer_time=transfer_time):
#                     continue
#                 to = (stop_seq_, stop_id)
#                 # G.add_edge(frm, to, time=transfer_time)
#                 span = StopSpan(arr=1, dep=1)
#                 all_connections.append(span)


s = TIME()
all_connections = sorted(all_connections, key=lambda c: c.dep_time)
print('sorted in', TIME() - s)

print(len(all_connections))

s = TIME()
dep_time = 16000
route = csa(all_connections, '00110998801965', '00101153700105', dep_time)
print(route)
print(TIME() - s)


# import ipdb; ipdb.set_trace()