import networkx as nx

SPEED_FACTOR = 2


class Router():
    def __init__(self, network):
        self.network = network
        self.trips = {}

    def route(self, start, end):
        """returns shortest weighted path
        between start & end as a sequence of nodes"""
        return nx.dijkstra_path(self.network, start, end, edge_weight)

    def travel(self, path):
        # last node in path
        # is destination
        if len(path) < 2:
            return

        frm, to = path[:2]
        edge = self.network[frm][to]
        time = travel_time(edge)

        # choose quickest edge
        edge = min(edge.values(), key=edge_travel_time)

        return frm, to, edge, time


def edge_weight(u, v, edges):
    """determines the attractiveness/speed of a
    network edge; the lower the better"""
    # there may be multiple edges;
    # default to the shortest
    return min(e['length'] for e in edges.values())


def edge_travel_time(edge):
    """travel time for a traveler entering an edge"""
    # TODO get clarification on these terms and how they're being used here
    return (edge['length'] * ((edge['occupancy'] + 1)/edge['capacity']) * edge['maxspeed'])/SPEED_FACTOR


def travel_time(edges):
    # there may be multiple edges
    # default to shortest
    return min(edge_travel_time(edge) for edge in edges.values())
