import graph_tool as gt
from graph_tool import topology

g = gt.Graph(directed=True)

# automatically adds missing nodes
e1 = g.add_edge(0, 1)

# will add a parallel edge
e2 = g.add_edge(0, 1)

e3 = g.add_edge(1, 2)
e4 = g.add_edge(0, 2)

# https://graph-tool.skewed.de/static/doc/quickstart.html#sec-property-maps
# https://graph-tool.skewed.de/static/doc/graph_tool.html#graph_tool.PropertyMap
# https://graph-tool.skewed.de/static/doc/quickstart.html#sec-internal-props
eprop = g.new_edge_property('int16_t')
g.edge_properties['some name'] = eprop
# g.edge_properties['some name'][(0, 1)] = 10 # defaults to the first matching edge
g.edge_properties['some name'][e1] = 10
g.edge_properties['some name'][e2] = 20
g.edge_properties['some name'][e3] = 10
g.edge_properties['some name'][e4] = 30

vprop = g.new_vertex_property('string')
g.vertex_properties['some name'] = vprop
g.vertex_properties['some name'][0] = 'foo'


# https://graph-tool.skewed.de/static/doc/gt_format.html
# slower, but smaller file
# g.save('graph.gt.xz')
# gt.load_graph('graph.gt.xz')

# faster, but larger file
g.save('graph.gt')
g = gt.load_graph('graph.gt')


# https://graph-tool.skewed.de/static/doc/topology.html#graph_tool.topology.shortest_path
# https://graph-tool.skewed.de/static/doc/topology.html#graph_tool.topology.all_shortest_paths
nodes, edges = topology.shortest_path(g, g.vertex(0), g.vertex(2), weights=g.edge_properties['some name'])
paths = topology.all_shortest_paths(g, g.vertex(0), g.vertex(2), weights=g.edge_properties['some name'])

import ipdb; ipdb.set_trace()
