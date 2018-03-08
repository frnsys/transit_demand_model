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

    def next(self):
        """compute next event in trip"""
        edge, prev_time = self.prev
        if edge is not None:
            # leave previous edge
            edge['occupancy'] -= 1
            if edge['occupancy'] < 0:
                raise Exception('occupancy should be positive')
            self.path.pop(0)

        # compute next leg
        leg = self.router.travel(self.path)

        # arrived
        if leg is None:
            return None

        # TODO replanning can occur here too,
        # e.g. if travel_time exceeds expected travel time
        start, end, edge, travel_time = leg

        # enter edge
        edge['occupancy'] += 1
        if edge['occupancy'] <= 0:
            raise Exception('adding occupant shouldnt make it 0')

        # time accumulates
        # TODO this assumes agents don't stop at
        # lights/intersections, so should add in some time,
        # but how much?
        # or will it not affect the model much?
        time = travel_time + prev_time

        # keep track of prev leg
        self.prev = edge, time
        self.legs.append(leg)

        # return next event
        return time, self.next

    def segments(self, map, step=0.1):
        """break trip into segments, e.g. for visualization purposes"""
        time = self.start_time
        segs = []
        last = None
        for start, end, edge, travel_time in self.legs:
            pts = segment_leg(map, start, end, edge)
            segs.extend([[lng, lat, time + (p * travel_time)] for (lat, lng), p in pts])
            if segs:
                last = segs.pop(-1) # first segment is same as last leg's last segment
            time += travel_time
        return segs + [last]


def segment_leg(map, u, v, edge, step=0.1):
    """segments a leg of a trip
    (a leg a part of a trip that corresponds to an edge)"""
    geo = edge.get('geometry')
    if geo is None:
        pt1, pt2 = map.network.nodes[u], map.network.nodes[v]
        pt1 = np.array([pt1['x'], pt1['y']])
        pt2 = np.array([pt2['x'], pt2['y']])
        pts = lerp(pt1, pt2, step=step)
    else:
        pts = [(geo.interpolate(p, normalized=True).coords[0], p)
               for p in np.arange(0, 1+step, step)]
    return [(map.to_latlng(*pt), p) for pt, p in pts]


def lerp(pt1, pt2, step):
    return [(pt1+p*(pt2-pt1), p) for p in np.arange(0, 1+step, step)]
