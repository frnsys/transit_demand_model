def edge_weight(u, v, edges):
    """determines the attractiveness/speed of a
    network edge; the lower the better"""
    # there may be multiple edges;
    # default to the shortest
    edges = [(
		idx,
		edge_travel_time(d['length'], d['maxspeed'], d['occupancy'], d['capacity']))
		for idx, d in edges.items()]
    return min(edges, key=lambda e: e[1])


cpdef edge_travel_time(double length, double maxspeed, unsigned int occupancy, unsigned int capacity):
    """travel time for a traveler entering an edge"""
    # TODO get clarification on these terms and how they're being used here
    return (length * ((occupancy + 1)/capacity) * maxspeed)
