# to show plots
# import matplotlib
# matplotlib.rcParams['interactive'] = True

import numpy as np
import networkx as nx
from heap import Heap

# create a random directed graph for our road network
G = nx.fast_gnp_random_graph(50, 0.1, directed=True, seed=1)

# create random edge properties
for e, d in G.edges.items():
    d.update({
        'length': np.random.beta(1,1) * 100,
        'capacity': np.random.beta(1,1) * 100,
        'free_flow': np.random.beta(1,1) * 100,
        'occupancy': 0
    })
# nx.draw(G)


def travel_time(edge):
    # travel time for a traveler entering an edge
    # TODO get a lot of clarification on these terms and how they're being used
    # here
    return edge['length'] * ((edge['occupancy'] + 1)/edge['capacity']) * edge['free_flow']


def travel(path, prev=None):
    if prev is not None:
        edge, prev_time = prev

        # leave previous edge
        edge['occupancy'] -= 1
        path.pop(0)
    else:
        prev_time = 0

    if len(path) < 2:
        print('arrived')
        return

    frm, to = path[:2]
    edge = G[frm][to]

    # time accumulates
    time = travel_time(edge) + prev_time

    # enter edge
    edge['occupancy'] += 1

    # return next event to process
    return (time, lambda: travel(path, prev=(edge, time)))


def route(start, end):
    """returns shortest weighted path
    between start & end as a sequence of nodes"""
    # TODO currently just considering length
    # but need to incorporate other factors
    return nx.dijkstra_path(G, start, end, lambda u, v, d: d['length'])


if __name__ == '__main__':
    events = Heap()

    # plan routes
    n_agents = 2
    for agent in range(n_agents):
        start, end = np.random.choice(G.nodes(), 2)
        path = route(start, end)
        print(agent, ':', path)
        event = travel(path)
        events.push(event)

    # process travel
    next = events.pop_safe()
    while next is not None:
        time, action = next
        event = action()
        if event is not None:
            events.push(event)
        next = events.pop_safe()

    print('travel finished')
