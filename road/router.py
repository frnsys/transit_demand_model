from itertools import count
from heapq import heappush, heappop
from collections import namedtuple
from .graph import edge_weight, edge_travel_time

# `p` tells us the proportion of the edge we actually travel,
# e.g. if we start earlier or later along the road
Leg = namedtuple('Leg', ['frm', 'to', 'edge_no', 'p'])


class NoRoadRouteFound(Exception): pass


class Router():
    """road network router"""

    def __init__(self, roads):
        self.roads = roads
        self.network = roads.network

    def route(self, start, end):
        """compute a road route
        between a start and end coordinate"""
        # find the closest edges to the start
        # and end positions, then the road network nodes
        # that the edge goes to (for the start)
        # and the node that the edge comes from (for the end)
        edge_s = self.roads.find_closest_edge(start)
        edge_e = self.roads.find_closest_edge(end)
        return self.route_edges(edge_s, edge_e)

    def route_edges(self, edge_s, edge_e):
        """compute a road route between two edges
        that include 0.-1. positions along the edges"""
        path, dist = dijkstra(self.network, edge_s.to, edge_e.frm, edge_weight)

        # adjust start node
        path[0] = (edge_s.to, None)

        # TODO we aren't checking how far `start` and `end`
        # are from `s_pt` and `e_pt`. these should probably be walk actions?
        route = [Leg(frm=edge_s.frm, to=edge_s.to, edge_no=edge_s.no, p=(1-edge_s.p))]
        for (u, _), (v, e_no) in zip(path, path[1:]):
            route.append(Leg(frm=u, to=v, edge_no=e_no, p=1.))
        route.append(Leg(frm=path[-1][0], to=edge_e.to, edge_no=edge_e.no, p=edge_e.p))
        return route


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

    try:
        return paths[target], dist
    except KeyError:
        raise NoRoadRouteFound
