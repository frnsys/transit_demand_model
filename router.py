import networkx as nx


class Router():
    def __init__(self, network):
        self.network = network
        self.trips = {}

    def route(self, start, end):
        """returns shortest weighted path
        between start & end as a sequence of nodes"""
        return nx.dijkstra_path(self.network.G, start, end, edge_weight)

    def travel(self, path):
        # last node in path
        # is destination
        if len(path) < 2:
            return

        frm, to = path[:2]
        edge = self.network.G[frm][to]
        time = travel_time(edge)

        # choose quickest edge
        edge = min(edge.values(), key=_travel_time)

        return frm, to, edge, time



def edge_weight(u, v, edges):
    """determines the attractiveness/speed of a
    network edge; the lower the better"""
    # there may be multiple edges;
    # default to the shortest
    return min(e['length'] for e in edges.values())


def _travel_time(edge):
    """travel time for a traveler entering an edge"""
    # TODO get clarification on these terms and how they're being used here
    return edge['length'] * (edge['capacity']/(edge['occupancy'] + 1)) * edge['maxspeed']


def travel_time(edges):
    # there may be multiple edges
    # default to shortest
    return min(_travel_time(edge) for edge in edges.values())
