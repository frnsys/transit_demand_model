import networkx as nx

G = nx.DiGraph()
G.add_edges_from([
    ('A', 'B', {'weight': 2}),
    ('B', 'C', {'weight': 3}),
    ('A', 'C', {'weight': 4}),
    ('C', 'D', {'weight': 1}),
    ('A', 'E', {'weight': 1}),
    ('E', 'F', {'weight': 1}),
    ('F', 'C', {'weight': 1}),
])

length, path = nx.single_source_dijkstra(G, 'A', target='D')
print(path)


from itertools import count
from heapq import heappush, heappop
def dijkstra(G, sources, target, weight):
    G_succ = G._succ if G.is_directed() else G._adj

    push = heappush
    pop = heappop
    dists = {}  # dictionary of final distances
    seen = {}
    # fringe is heapq with 3-tuples (distance,c,node)
    # use the count c to avoid comparing nodes (may not be able to)
    c = count()
    fringe = []
    paths = {source: [source] for source in sources}
    for source in sources:
        seen[source] = 0
        push(fringe, (0, next(c), source))
    while fringe:
        (d, _, v) = pop(fringe)
        if v in dists:
            continue  # already searched this node.
        dists[v] = d
        if v == target:
            break
        for u, e in G_succ[v].items():
            cost = weight(v, u, e, dists[v])
            if cost is None:
                continue
            vu_dist = dists[v] + cost
            if u in dists:
                if vu_dist < dists[u]:
                    raise ValueError('Contradictory paths found:',
                                     'negative weights?')
            elif u not in seen or vu_dist < seen[u]:
                seen[u] = vu_dist
                push(fringe, (vu_dist, next(c), u))
                paths[u] = paths[v] + [u]

    # The optional predecessor and path dictionaries can be accessed
    # by the caller via the pred and paths objects passed as arguments.
    try:
        return dists[target], paths[target]
    except KeyError:
        raise nx.NetworkXNoPath('No path to {}.'.format(target))


def weight(v, u, e, d):
    print('FROM:', v)
    print('TO:', u)
    print('EDGE:', e)
    print('CUR DIST:', d)
    return e['weight']


sources = {'A'}
target = 'D'
dist, path = dijkstra(G, sources, target, weight)
print(dist, path)