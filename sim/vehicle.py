from collections import defaultdict


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
