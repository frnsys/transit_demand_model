import math
import config
import networkx as nx
from itertools import count
from heapq import heappush, heappop
from collections import namedtuple

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
        path = astar(self.network, edge_s.to, edge_e.frm, weight=edge_weight, heuristic=self.heuristic)

        # adjust start node
        path[0] = (edge_s.to, None)

        # TODO we aren't checking how far `start` and `end`
        # are from `s_pt` and `e_pt`. these should probably be walk actions?
        route = [Leg(frm=edge_s.frm, to=edge_s.to, edge_no=edge_s.no, p=(1-edge_s.p))]
        for (u, _), (v, e_no) in zip(path, path[1:]):
            route.append(Leg(frm=u, to=v, edge_no=e_no, p=1.))
        route.append(Leg(frm=path[-1][0], to=edge_e.to, edge_no=edge_e.no, p=edge_e.p))
        return route

    def heuristic(self, u, v):
        u = self.network.nodes[u]
        v = self.network.nodes[v]
        return math.sqrt((u['x']-v['x'])**2 + (u['y'] - v['y'])**2)


def edge_weight(edges):
    """determines the attractiveness/speed of a
    network edge; the lower the better"""
    # there may be multiple edges;
    # default to the shortest
    edges = [(idx, edge_travel_time(data)) for idx, data in edges.items()]
    return min(edges, key=lambda e: e[1])


def edge_travel_time(edge):
    """travel time for a traveler entering an edge"""
    # assuming people always drive at maxspeed
    time = (edge['length']/edge['maxspeed'])

    # occupancy, including this new vehicle
    occupancy = edge['occupancy'] + 1

    # assuming each vehicle takes its own lane
    # if possible
    occupancy_per_lane = 1 + (occupancy-1)//edge['lanes']

    # really not sure how best to calculate this
    congestion_multiplier = 1 + math.sqrt(occupancy_per_lane**2/edge['capacity'])

    return (time * congestion_multiplier)/config.SPEED_FACTOR



def astar(G, source, target, heuristic=None, weight='weight'):
    if source not in G or target not in G:
        msg = 'Either source {} or target {} is not in G'
        raise nx.NodeNotFound(msg.format(source, target))

    if heuristic is None:
        # The default heuristic is h=0 - same as Dijkstra's algorithm
        def heuristic(u, v):
            return 0

    push = heappush
    pop = heappop

    # The queue stores priority, node, cost to reach, parent, and selected edge.
    # Uses Python heapq to keep in priority order.
    # Add a counter to the queue to prevent the underlying heap from
    # attempting to compare the nodes themselves. The hash breaks ties in the
    # priority and is guaranteed unique for all nodes in the graph.
    c = count()
    queue = [(0, next(c), source, 0, None, None)]

    # Maps enqueued nodes to distance of discovered paths and the
    # computed heuristics to target. We avoid computing the heuristics
    # more than once and inserting the node into the queue too many times.
    enqueued = {}
    # Maps explored nodes to parent closest to the source.
    explored = {}
    ancestors = {}

    while queue:
        # Pop the smallest item from queue.
        _, __, curnode, dist, parent, edge = pop(queue)

        if curnode == target:
            path = [(curnode, edge)]
            node = parent
            while node is not None:
                # node = explored[node]
                prev_node, edge = ancestors[node]
                path.append((node, edge))
                node = prev_node
            path.reverse()
            return path

        if curnode in explored:
            continue

        explored[curnode] = parent
        ancestors[curnode] = (parent, edge)

        for neighbor, edges in G[curnode].items():
            if neighbor in explored:
                continue
            edge, cost = weight(edges)
            ncost = dist + cost
            if neighbor in enqueued:
                qcost, h = enqueued[neighbor]
                # if qcost < ncost, a longer path to neighbor remains
                # enqueued. Removing it would need to filter the whole
                # queue, it's better just to leave it there and ignore
                # it when we visit the node a second time.
                if qcost <= ncost:
                    continue
            else:
                h = heuristic(neighbor, target)
            enqueued[neighbor] = ncost, h
            push(queue, (ncost + h, next(c), neighbor, ncost, curnode, edge))

    raise NoRoadRouteFound
