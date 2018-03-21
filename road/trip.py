import numpy as np

class Group:
    def __init__(self):
        self.stops_order = []

        # group passengers by destination stop
        self.passengers = {}

        # group people awaiting pickup by boarding stop
        # and remember their destination stop
        self.pickups = {}

    def add_agent(self, agent, stop, next_fn):
        if stop not in self.stops:
            self.passengers[stop] = [agent]
            # new stop added, re-order
            self.stops_order = sorted(self.stops.keys(), key=lambda s: self.schedule[s])
        else:
            self.passengers[stop].append(agent)

    def next(self):
        next_stop = self.stops_order[0]
        return self.schedule[next_stop], self.arrive


class Trip:
    def __init__(self, id, start, end, router, start_time=0):
        """
        given a start and end node, compute a route through the road network.
        """
        self.id = id
        self.start = start
        self.end = end
        self.router = router
        self.path = router.route(start, end)
        self.legs = []
        self.prev = (None, start_time)
        self.start_time = start_time

