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

class Bus:
    def __init__(self, trip_iid, sched):
        self.id = trip_iid
        self.stop_idx = -1
        self.sched = sched
        self.passengers = defaultdict(list)

    def next(self, time):
        # TODO if this is a bus, this should
        # actually go through the road network
        # to influence/be influenced by traffic.
        # other route types just follow the schedule directly.
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
            return events
        time = time + next_stop['arr_sec'] - cur_stop['dep_sec']
        events.append((time, self.next))
        return events


def start_atrip(id, path, time):
    try:
        leg = path.pop(0)
    except IndexError:
        print(id, 'ARRIVED', time)
        return []
    action = partial(start_atrip, id, path)
    if leg['type'] is MoveType.WALK:
        print(id, 'Walking', time)
        time = time + leg['time']
        return [(time, action)]
    else:
        # wait at stop
        # TODO need to check if they arrive on time
        print(id, 'Waiting at stop', leg['start'], time)
        stops[leg['start']][leg['trip']].append((leg['end'], action))
        return []


if __name__ == '__main__':
    dt = datetime(year=2017, month=2, day=22, hour=8)
    from time import time as T
    s = T()

    start = (-19.821486,-43.946748)
    end = (-19.9178,-43.93337)
    path1 = transit.trip_route(start, end, dt)
    print('path:', path1)

    start = (-19.920846733136, -43.8850293374623)
    end = (-19.9145681320285, -43.8823756325257)
    path2 = transit.trip_route(start, end, dt)
    print('path:', path2)

    start = (-19.9213988706738, -43.878418788464)
    end = (-19.9238852702832, -43.8968610758699)
    path3 = transit.trip_route(start, end, dt)
    print('path:', path3)

    # pre-queue events for all public transit trips
    # they should always be running, regardless of if there
    # are any passengers, since they can affect traffic,
    # and the implementation is easier this way b/c we aren't
    # juggling specific spawning conditions for these trips.
    # TODO however, pre-queuing all public transit trips ahead
    # of time doesn't account for the possibility of trips
    # on the same e.g. tracks being delayed because of delays
    # in earlier trips sharing the same e.g. track.
    # TODO need to account for weekdays/what the current week day is,
    # and trips across days.
    # perhaps after a trip stops, it re-queues the next time it will run?
    time = 0
    events = EventQueue()
    for trip_iid, group in transit.trip_stops:
        first_stop = group.iloc[0]
        bus = Bus(trip_iid, group)
        events.push((first_stop['dep_sec'], bus.next))

    # create departure events for agents
    # we created the above paths for hour=8 so use that in seconds
    dep_time = 8 * 60 * 60
    for i, path in enumerate([path1, path2, path3]):
        events.push((dep_time, partial(start_atrip, i, path)))

    # run
    next = events.pop()
    while next is not None:
        time, action = next
        new_events = action(time)
        for event in new_events:
            events.push(event)
        next = events.pop()

    print(T() - s)
    import ipdb; ipdb.set_trace()

"""
TODO
- have to initialize all public transit in the simulation. makes most sense for
it to always be running, since it will affect traffic. and it makes it easier to attach
agents to the transit groups. so these should run even if there are no people aboard.
"""
