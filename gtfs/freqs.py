"""
utilities for dealing with trip frequencies.
currently not used; these were originally developed
for public transit routing, but we are using CSA now instead.
keeping for a bit in case we need it again.
"""

import math
from collections import namedtuple
from .util import gtfs_time_to_secs

TripSpan = namedtuple('TripSpan', ['start', 'end', 'period'])
TripStop = namedtuple('TripStop', ['stop_id', 'rel_arr', 'rel_dep', 'transit_time'])

# this doesn't include headway b/c we can get that from the trip info
# here, arr and dep are in absolute seconds
StopSpan = namedtuple('StopSpan', ['start', 'end', 'period', 'wait', 'last_dep'])

def compress_frequencies(freqs):
    freqs_compressed = {}
    for trip_id, group in freqs.groupby('trip_id'):
        group = group.sort_values('start_time')
        chunks = []
        for r in group.itertuples():
            # if no chunks, nothing to compare to,
            # so add this row in
            if not chunks:
                chunks.append({
                    'start': gtfs_time_to_secs(r.start_time),
                    'end': gtfs_time_to_secs(r.end_time),
                    'period': r.headway_secs
                })
            else:
                prev = chunks[-1]
                start, end = gtfs_time_to_secs(r.start_time), gtfs_time_to_secs(r.end_time)
                # in order to merge two entries,
                # 1) must be same period
                # 2) next entry must start within 1 second of the other,
                # e.g. previous one ends at 8:59:59 and next one starts at 9:00:00
                # 3) the next start time must sync up to the period
                if prev['period'] == r.headway_secs \
                    and start - prev['end'] <= 1 \
                    and (start - prev['start']) % r.headway_secs == 0:

                    # if these are all true, extend the previous time span
                    prev['end'] = end
                else:
                    chunks.append({
                        'start': start,
                        'end': end,
                        'period': r.headway_secs
                    })
        freqs_compressed[trip_id] = [TripSpan(**s) for s in chunks]
    return freqs_compressed


def trip_spans_to_stop_spans(trip_id, spans, trip_stops):
    """given a set of spans for a trip,
    convert the trip stop schedule to a schedule
    of relative arrival/departure times,
    and compute arrival/departure spans for each stop along the trip"""
    first_start = spans[0][0]
    trip_sched = []
    stops_spans = []
    # assuming they are sorted by stop sequence already
    for i, stop in enumerate(trip_stops):
        arr, dep = stop.arr_sec, stop.dep_sec

        # in the Belo Horizonte data, stop arrival/departure times were offset
        # by the first trip's departure time.
        # we want it to be relative to t=0 instead
        arr -= first_start
        dep -= first_start

        # calculate transit time between this stop
        # and the previous stop (0 if no previous stop)
        if not trip_sched:
            transit_time = 0
        else:
            transit_time = arr - trip_sched[-1].rel_dep

        trip_sched.append(TripStop(stop_id=stop.stop_id, rel_arr=arr, rel_dep=dep, transit_time=transit_time))

        stop_spans = []
        for start, end, headway in spans:
            # assumes the span end is not a departure time
            last_dep = ((n_vehicles(start, end, headway) - 1) * headway) + start
            stop_spans.append(StopSpan(start=start+dep, end=end+arr, period=headway, wait=dep-arr, last_dep=last_dep))
        stops_spans.append((stop.stop_id, stop_spans))
    return trip_sched, stops_spans


def next_vehicle_dep(dep, span):
    """
    calculate the soonest departure time at a stop
    based on a trip frequency/span
    - dep: int (seconds); earliest departure to consider
    - trip_span_start: int (seconds); absolute time of the trip span to
      consider
    - stop_dep_relative: int (seconds); the relative time vehicles
      depart from this stop
    - headway: int (seconds); how frequently vehicles depart along this trip

    e.g. if we have trips starting at 5:00:00 departing everything 600s,
    and the stop we're considering departs at the 300s mark in each trip,
    and we want to leave at 5:30:00 at the soonest, we'd have:
    - dep = gtfs_time_to_secs('5:30:00')
    - trip_span_start = gtfs_time_to_secs('5:00:00')
    - stop_dep_relative = 300
    - headway = 600

    note: before calling this function you'd probably want to check that
        dep < trip_span_end
    """
    if not dep < span.last_dep:
        return None
    next_train_idx = math.ceil((dep - span.start)/span.period)
    next_train_time = span.start + (next_train_idx * span.period)
    return max(span.start, next_train_time)


def n_vehicles(start, end, period):
    """number of departing vehicles for a frequency span.
    this assumes the span end is not a departure time"""
    return math.floor((end - start)/period) + 1

