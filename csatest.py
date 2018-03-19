# import hashlib
from gtfs import util
from collections import defaultdict, namedtuple
from tqdm import tqdm
from time import time as TIME
from gtfs.calendar import Calendar
from scipy.spatial import KDTree
import numpy as np
from csa import csa, Connection

TripStop = namedtuple('TripStop', ['stop_id', 'rel_arr', 'rel_dep'])
StopSpan = namedtuple('StopSpan', ['arr', 'dep'])

Footpath = namedtuple('Footpath', ['dep_stop', 'arr_stop', 'time'])

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


# reduce connections to only those for this day
from datetime import datetime
calendar = Calendar(gtfs)
valid_trips = calendar.trips_for_day(datetime.now())
# valid_trips = calendar.trips_for_day(datetime(month=3,day=18,year=2018,hour=0,minute=0,second=0))

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



closest = 5
print('footpaths')
footpaths = {}
for stop in tqdm(gtfs['stops'].itertuples(), total=len(gtfs['stops'])):
    coord = stop.stop_lat, stop.stop_lon

    # get closest stops to this one
    neighbors = closest_stops(coord, n=closest+1)

    # skip the first, it's the stop itself
    neighbors = neighbors[1:]

    # filter out long transfers
    neighbors = [n for n in neighbors if n[1] <= footpath_delta_max]

    footpaths[stop.stop_id] = [
        Footpath(dep_stop=stop.stop_id, arr_stop=stop_id, time=transfer_time)
        for stop_id, transfer_time in neighbors]

print('preprocessing:', TIME() - s)


s = TIME()
all_connections = sorted(all_connections, key=lambda c: c.dep_time)
print('sorted in', TIME() - s)

print(len(all_connections))

s = TIME()
dep_time = 16000
route = csa(all_connections, footpaths, '00110998801965', '00101153700105', dep_time)
print(route)
print(TIME() - s)


# import ipdb; ipdb.set_trace()
