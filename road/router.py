import numpy as np
from itertools import count
from functools import partial
from heapq import heappush, heappop
from collections import defaultdict, namedtuple

SPEED_FACTOR = 2 # NOTE this needs to be calibrated to the public transit schedule as well

# `p` tells us the proportion of the edge we actually travel,
# e.g. if we start earlier or later along the road
Leg = namedtuple('Leg', ['frm', 'to', 'edge', 'p'])

class Router():
    """road network router"""

    def __init__(self, map, network):
        self.map = map
        self.network = network

        # keep track of trips
        self.trips = defaultdict(list)

    def route(self, start, end):
        """compute a road route
        between a start and end coordinate"""
        # find the closest edges to the start
        # and end positions, then the road network nodes
        # that the edge goes to (for the start)
        # and the node that the edge comes from (for the end)
        # TODO clean this up
        s_id, _, s_p, s_pt = self.map.find_closest_edge(start)
        s_from, s_to, s_idx = s_id.split('_')
        e_id, _, e_p, e_pt = self.map.find_closest_edge(end)
        e_from, e_to, e_idx = e_id.split('_')

        s_to = int(s_to)
        e_from = int(e_from)
        s_idx = int(s_idx)
        e_idx = int(e_idx)

        path, dist = dijkstra(self.network, s_to, e_from, edge_weight)

        # adjust start node
        path[0] = (s_to, None)

        # TODO we aren't checking how far `start` and `end`
        # are from `s_pt` and `e_pt`. these should probably be walk actions?
        route = [Leg(frm=int(s_from), to=s_to, edge=s_idx, p=(1-s_p))]
        for (u, _), (v, e) in zip(path, path[1:]):
            route.append(Leg(frm=u, to=v, edge=e, p=1.))
        route.append(Leg(frm=path[-1][0], to=int(e_to), edge=e_idx, p=e_p))
        return route

    def travel(self, path):
        # last node in path
        # is destination
        if len(path) < 2:
            return

        leg = path[0]
        try:
            edge = self.network[leg.frm][leg.to][leg.edge]
        except KeyError:
            import ipdb; ipdb.set_trace()

        # where leg.p is the proportion of the edge we travel
        time = edge_travel_time(edge) * leg.p

        return leg, edge, time

    def next(self, vehicle, time):
        """compute next event in trip"""
        edge = vehicle.current
        if edge is not None:
            # leave previous edge
            edge['occupancy'] -= 1
            if edge['occupancy'] < 0:
                raise Exception('occupancy should be positive')
            vehicle.route.pop(0)

        # compute next leg
        leg = self.travel(vehicle.route)

        # arrived
        if leg is None:
            return []

        # TODO replanning can occur here too,
        # e.g. if travel_time exceeds expected travel time
        leg, edge, travel_time = leg

        # enter edge
        edge['occupancy'] += 1
        if edge['occupancy'] <= 0:
            raise Exception('adding occupant shouldnt make it 0')

        vehicle.current = edge
        self.trips[vehicle.id].append(leg)

        # return next event
        # TODO this assumes agents don't stop at
        # lights/intersections, so should add in some time,
        # but how much?
        # or will it not affect the model much?
        return [(travel_time, partial(self.next, vehicle))]


def edge_weight(u, v, edges):
    """determines the attractiveness/speed of a
    network edge; the lower the better"""
    # there may be multiple edges;
    # default to the shortest
    edges = [(idx, edge_travel_time(data)) for idx, data in edges.items()]
    return min(edges, key=lambda e: e[1])


def edge_travel_time(edge):
    """travel time for a traveler entering an edge"""
    # TODO get clarification on these terms and how they're being used here
    tt = (edge['length'] * ((edge['occupancy'] + 1)/edge['capacity']) * edge['maxspeed'])/SPEED_FACTOR
    return tt


def segments(start_time, legs, map, step=0.1):
    """break trip into segments, e.g. for visualization purposes"""
    time = start_time
    segs = []
    last = None
    for start, end, edge, travel_time in legs:
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


def dijkstra(G, source, target, weight):
    G_succ = G._succ if G.is_directed() else G._adj

    paths = {}
    paths[source] = [source]
    push = heappush
    pop = heappop
    dist = {}  # dictionary of final distances
    seen = {}
    # fringe is heapq with 3-tuples (distance,c,node)
    # use the count c to avoid comparing nodes (may not be able to)
    c = count()
    fringe = []
    seen[source] = 0
    push(fringe, (0, next(c), source))
    while fringe:
        (d, _, v) = pop(fringe)
        if v in dist:
            continue  # already searched this node.
        dist[v] = d
        if v == target:
            break
        for u, e in G_succ[v].items():
            edge, cost = weight(v, u, e)
            if cost is None:
                continue
            vu_dist = dist[v] + cost
            if u in dist:
                if vu_dist < dist[u]:
                    raise ValueError('Contradictory paths found:',
                                     'negative weights?')
            elif u not in seen or vu_dist < seen[u]:
                seen[u] = vu_dist
                push(fringe, (vu_dist, next(c), u))
                if paths is not None:
                    paths[u] = paths[v] + [(u, edge)]

    return paths[target], dist
