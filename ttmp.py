import numpy as np
from tqdm import tqdm
from datetime import timedelta
from gtfs.util import load_gtfs, walking_time
from scipy.spatial import KDTree
from collections import defaultdict

def gtfs_time_to_secs(time):
    h, m, s = time.split(':')
    return int(s) + (int(m) * 60) + (int(h) * 60 * 60)


def time_to_secs(time):
    return (time.hour * 60 + time.minute) * 60 + time.second


def secs_to_gtfs_time(secs):
    return str(timedelta(seconds=int(secs)))


gtfs = load_gtfs('data/gtfs/gtfs_bhtransit.zip')

# Data pre-processing
trips = {}
n_trips = 0 # temp
trip_freqs = gtfs['frequencies'].groupby('trip_id')
trip_stops = gtfs['stop_times'].groupby('trip_id')
stops = defaultdict(lambda: defaultdict(list))
for trip_id, freqs in tqdm(trip_freqs):
    spans = [(gtfs_time_to_secs(s), gtfs_time_to_secs(e), headway)
             for s, e, headway in freqs[['start_time', 'end_time', 'headway_secs']].values]
    starts = []
    for start, end, headway in spans:
        starts.extend(np.arange(start, end, headway))

    sched = []
    for i, stop in enumerate(trip_stops.get_group(trip_id).itertuples()):
        # TODO this assumes they are sorted by stop sequence already
        arr, dep = gtfs_time_to_secs(stop.arrival_time), gtfs_time_to_secs(stop.departure_time)

        # in the Belo Horizonte data, stop arrival/departure times were offset
        # by the first trip's departure time.
        # we want it to be relative to t=0 instead
        arr -= starts[0]
        dep -= starts[0]
        sched.append((stop.stop_id, arr, dep))

        for start in starts:
            stops[stop.stop_id][trip_id].append((i, arr+start, dep+start, start))

    trips[trip_id] = {
        'sched': sched,
        'starts': starts
    }

    n_trips += len(starts) # temp

print('Spatial-indexing stops...')
indirect_transfers = defaultdict(list) # TODO can/should prob be a network
stop_coords = gtfs['stops'][['stop_lat', 'stop_lon']].values
_kdtree = KDTree(stop_coords)

base_transfer_time = 2*60 # lower-bound time-delta overhead for changing trips
footpath_delta_base = 2*60 # footpath_delta = delta_base + km / speed_kmh
footpath_speed_kmh = 5 / 3600
footpath_delta_max = 7*60 # all footpaths longer than that are discarded as invalid

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
        walking_time(coord, (lat, lon), footpath_delta_base, footpath_speed_kmh)
        for lat, lon in stops[['stop_lat', 'stop_lon']].values]

    # pair as `(stop_iid, time)`
    return list(zip(stops['stop_id'].values, times))

closest = 5
print('Indirect transfers')
for stop in tqdm(gtfs['stops'].itertuples(), total=len(gtfs['stops'])):
    coord = stop.stop_lat, stop.stop_lon

    # get closest stops to this one
    neighbors = closest_stops(coord, n=closest+1)

    # skip the first, it's the stop itself
    neighbors = neighbors[1:]

    # filter out long transfers
    neighbors = [n for n in neighbors if n[1] <= footpath_delta_max]
    indirect_transfers[stop.stop_id] = neighbors

from multiprocessing import Pool
def process_transfers_mp():
    # Transfer pre-processing
    transfers = {}
    pbar = tqdm(total=len(trips))
    def update(arg):
        trip_id, txs = arg
        transfers[trip_id] = txs
        pbar.update()
    def err(ex):
        raise ex
    pool = Pool(processes=4)
    for trip_id, trip_data in trips.items():
        pool.apply_async(process_transfers, args=(trip_id, trip_data), callback=update, error_callback=err)
    pool.close()
    pool.join()
    pbar.close()
    return transfers

def process_transfers(trip_id, trip_data):
    # skip first stop of the trip
    # no need for transfers there;
    # if we wanted to transfer at the first stop
    # we just wouldn't go on this trip at all
    transfers = defaultdict(lambda: defaultdict(list))
    for stop_id, arr, dep in trip_data['sched'][1:]:
        # direct transfers
        for trip_id_, sched in stops[stop_id].items():
            if trip_id_ == trip_id:
                continue
            txs = transfers_for_stop(trip_data, sched, arr + base_transfer_time)
            for start, (i, _, _, other_start) in txs.items():
                transfers[start][stop_id].append((trip_id_, other_start, i, base_transfer_time))
        # indirect transfers
        for stop_id_, walk_time in indirect_transfers[stop_id]:
            for trip_id_, sched in stops[stop_id_].items():
                if trip_id_ == trip_id:
                    continue
                txs = transfers_for_stop(trip_data, sched, arr + walk_time)
                for start, (i, _, _, other_start) in txs.items():
                    transfers[start][stop_id].append((trip_id_, other_start, i, walk_time))
    return trip_id, dict(transfers)


def transfers_for_stop(trip_data, sched, time):
    transfers = {}
    sched_ = sched[:]
    for start in trip_data['starts']:
        if not sched_:
            break
        try:
            # assumes sorted by arrival time, ascending,
            # which maps departure time sorting (tx[2] is departure time)
            idx = next(i for i, tx in enumerate(sched_) if tx[2] >= start + time)
            transfers[start] = sched_[idx]

            # we can whittle down the size of this list
            # because we know next iterations will always be later
            # or equivalent in time than/to this one.
            sched_ = sched_[idx:]
        except StopIteration:
            # if we can't find a connecting trip for this start,
            # we won't find any for subsequent ones, so break
            break
    return transfers


import json
from time import time

s = time()
transfers = process_transfers_mp()
print(time() - s)

with open('transfers.json', 'w') as f:
    json.dump(transfers, f)

# Transfer reduction
# for trip_id, trip_data in trips:
#     for start in trip_data['starts']:
#         # stops to arrival time
#         trip_arrivals = defaultdict(float('inf'))

#         # stops to earliest change time
#         earliest_change_time = defaultdict(float('inf'))

#         for arr, dep, stop_id in reversed(trip_data['sched']):
#             trip_arrivals[stop_id] = min(trip_arrivals[stop_id], arr)
#             for stop_id_, trip_id_, transfer_time in transfers[trip_id]:
#                 trip_arrivals[stop_id_] = min(trip_arrivals[stop_id_], arr + transfer_time)
#             pass

