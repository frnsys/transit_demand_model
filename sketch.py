import logging
from gtfs import Transit, MoveType
from events import EventQueue
from datetime import datetime
from functools import partial

# TODO other mixed-mode routing considerations: driving to public transit?

logging.basicConfig(level=logging.INFO)
transit = Transit('data/gtfs/gtfs_bhtransit.zip', 'data/transit/bh')

# agents queue at stops to be picked up at
# this is a map {stop_id->{trip_id->[agents]}}
from collections import defaultdict
stops = defaultdict(lambda: defaultdict(list))
trips = {}

class Vehicle:
    def __init__(self, trip_iid, sched):
        self.id = trip_iid
        self.stop_idx = -1 # the most recently visited stop
        self.sched = sched
        self.passengers = defaultdict(list)

    def past_stops(self):
        idx = self.stop_idx + 1
        return self.sched.iloc[:idx]['stop_id'].values

    def next(self, time):
        # TODO if this is a bus, this should
        # actually go through the road network
        # to influence/be influenced by traffic.
        # other route types just follow the schedule directly.
        # one way to do this is, instead of returning bus.next as the action
        # return router.next actions, and give the router an `on_arrive` hook
        # to call bus.next (triggering passenger pickup/dropoff) and then
        # the router goes again.

        events = []
        self.stop_idx += 1
        cur_stop = self.sched.iloc[self.stop_idx]

        # pickup passengers
        for (end_stop, action) in stops[cur_stop['stop_id']][self.id]:
            print(self.id, 'Picking up passengers at', cur_stop.stop_id, time)
            self.passengers[end_stop].append(action)
            stops[cur_stop['stop_id']][self.id] = []

        # dropoff passengers
        for action in self.passengers[cur_stop['stop_id']]:
            print(self.id, 'Dropping off passengers at', cur_stop.stop_id, time)
            events.extend(action(time))
            self.passengers[cur_stop['stop_id']] = []

        try:
            next_stop = self.sched.iloc[self.stop_idx + 1]
        except IndexError:
            # trip is done
            # TODO re-schedule self for next day?
            # or, schedule next trip in this route
            # need to remove self from trip list
            return events
        time = next_stop['arr_sec'] - cur_stop['dep_sec']
        events.append((time, self.next))
        return events


def start_atrip(id, path, end, time):
    try:
        leg = path.pop(0)
    except IndexError:
        print(id, 'ARRIVED', time, datetime.fromtimestamp(time))
        return []
    action = partial(start_atrip, id, path, end)
    if leg['type'] is MoveType.WALK:
        print(id, 'Walking', time)
        rel_time = leg['time']
        return [(rel_time, action)]
    elif leg['type'] is MoveType.TRANSFER:
        print(id, 'Transferring', time)
        rel_time = leg['time']
        return [(rel_time, action)]
    else:
        # check if they arrive on time
        if leg['start'] in trips[leg['trip']].past_stops():
            # re-plan
            # note that passengers can miss buses if they arrive EXACTLY
            # when the bus is supposed to depart.
            print(id, 'MISSED the bus for stop {} for trip {}, replanning'.format(leg['start'], leg['trip']))
            dt = datetime.fromtimestamp(time)
            start = transit.stops.loc[leg['start']][['stop_lat', 'stop_lon']].values
            path, length = transit.trip_route(start, end, dt)
            return [(0, partial(start_atrip, id, path, end))]

        # wait at stop
        else:
            print(id, 'Waiting at stop', leg['start'], time)
            stops[leg['start']][leg['trip']].append((leg['end'], action))
            return []

if __name__ == '__main__':
    dt = datetime(year=2017, month=2, day=12, hour=8) # sunday
    dt = datetime(year=2017, month=2, day=13, hour=8)
    from time import time as T
    s = T()

    sim_start_time = dt.replace(hour=0).timestamp()
    print('START TIME', sim_start_time)
    print('START TIME', dt.replace(hour=0))

    start1 = (-19.821486,-43.946748)
    end1 = (-19.9178,-43.93337)
    s_ = T()
    path1, length = transit.trip_route(start1, end1, dt)
    print('routing time:', T() - s_)
    print('path:', path1)
    print('='*25)
    # import ipdb; ipdb.set_trace()

    start2 = (-19.920846733136, -43.8850293374623)
    end2 = (-19.9145681320285, -43.8823756325257)
    s_ = T()
    path2, length = transit.trip_route(start2, end2, dt)
    print('routing time:', T() - s_)
    print('path:', path2)
    print('='*25)

    start3 = (-19.9213988706738, -43.878418788464)
    end3 = (-19.9238852702832, -43.8968610758699)
    s_ = T()
    path3, length = transit.trip_route(start3, end3, dt)
    print('routing time:', T() - s_)
    print('path:', path3)
    print('='*25)

    # pre-queue events for all public transit trips
    # they should always be running, regardless of if there
    # are any passengers, since they can affect traffic,
    # and the implementation is easier this way b/c we aren't
    # juggling specific spawning conditions for these trips.
    # TODO however, pre-queuing all public transit trips ahead
    # of time doesn't account for the possibility of trips
    # on the same e.g. tracks being delayed because of delays
    # in earlier trips sharing the same e.g. track.
    # perhaps after a trip stops, it re-queues the next time it will run?
    events = EventQueue()
    valid_trip_ids = transit.calendar.trips_for_day(dt)
    # print('VALID TRIP IDS IN EXECUTOR')
    # print(valid_trip_ids)
    # import ipdb; ipdb.set_trace()
    for trip_iid, group in transit.trip_stops:
        if trip_iid not in valid_trip_ids:
            continue
        first_stop = group.iloc[0]
        bus = Vehicle(trip_iid, group)
        trips[trip_iid] = bus
        events.push((sim_start_time + first_stop['dep_sec'], bus.next))

    # create departure events for agents
    # we created the above paths for hour=8 so use that in seconds
    # dep_time = 8 * 60 * 60
    dep_time = 8 * 60 * 60
    for i, (path, end) in enumerate([(path1, end1), (path2, end2), (path3, end3)]):
        print(i, 'DEPARTING AT', datetime.fromtimestamp(sim_start_time + dep_time))
        events.push((sim_start_time + dep_time, partial(start_atrip, i, path, end)))

    # run
    # time = 0
    time = sim_start_time
    next = events.pop()
    while next is not None:
        time, action = next
        new_events = action(time)
        for event in new_events:
            countdown, next_action = event
            next_time = time + countdown
            events.push((next_time, next_action))
        next = events.pop()

    print(T() - s)
    import ipdb; ipdb.set_trace()

"""
- the time in event = (time, action) is relative time, i.e. `time` seconds later.
- the time we pass into the actions, i.e. `action(time)` is absolute time, i.e. timestamp
- absolute time is the time we keep track of as the canonical event system time
"""
