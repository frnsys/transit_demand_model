import math
import logging
import numpy as np
from tqdm import tqdm
from road import Roads
from matplotlib import pyplot
from descartes import PolygonPatch
from shapely.geometry import Point

logging.basicConfig(level=logging.INFO)
BLUE = '#6699cc'


def plot_network(start, end, roads, radius=1000, fname='map.jpg'):
    # compute plot bounds
    min_x = float('inf')
    max_x = -float('inf')
    min_y = float('inf')
    max_y = -float('inf')
    for x, y in [start, end]:
        if x - radius < min_x: min_x = x - radius
        if x + radius > max_x: max_x = x + radius
        if y - radius < min_y: min_y = y - radius
        if y + radius > max_y: max_y = y + radius

    # find nodes in the road network within those points
    # TODO check for edges that intersect as well?
    inside = []
    for n, data in tqdm(roads.network.nodes(data=True)):
        if data['x'] >= min_x and data['x'] <= max_x \
           and data['y'] >= min_y and data['y'] <= max_y:
            inside.append(n)

    fig = pyplot.figure(figsize=(20, 20), dpi=180)
    ax = fig.add_subplot(111)
    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    coords = []
    for x, y in [start, end]:
        pt = Point(x, y)
        circle = pt.buffer(30)
        patch = PolygonPatch(circle, fc='#e5c110', ec='#e5c110', alpha=0.5, zorder=2)
        ax.add_patch(patch)
        lat, lon = roads.to_latlon(x, y)
        coords.append((lat, lon))
        if (x, y) == start:
            ax.text(x, y, 'START ({}, {})'.format(lat, lon))
        elif (x, y) == end:
            ax.text(x, y, 'END ({}, {})'.format(lat, lon))

    for n in tqdm(inside):
        data = roads.network.node[n]
        x, y = data['x'], data['y']
        pt = Point(x, y)
        circle = pt.buffer(20)
        patch = PolygonPatch(circle, fc='#ff0000', ec='#ff0000', alpha=0.2, zorder=2)
        ax.add_patch(patch)
        ax.text(x, y, n, size=5, alpha=0.5)
        for to_node, edges in roads.network[n].items():
            if to_node not in inside:
                continue
            for edge in edges.values():
                # label long streets with names
                if edge['length'] >= 200 and edge.get('name'):
                    pt = edge['geometry'].interpolate(0.5, normalized=True)
                    ax.text(pt.x, pt.y, edge['name'], size=5, alpha=1, color='#0000ff')

                # draw the edge
                line = edge['geometry'].buffer(0.5)
                patch = PolygonPatch(line, fc=BLUE, ec=BLUE, alpha=0.5, zorder=2)

                # if one-way, draw arrows indicating direction
                if edge['oneway']:
                    arr_len = 10
                    n_arrs = math.ceil(edge['length']/arr_len)
                    step = 1.0/n_arrs
                    for i, s in enumerate(np.arange(0, 1.0, step)):
                        if i % 3 != 0:
                            continue
                        pt_a = edge['geometry'].interpolate(s, normalized=True)
                        pt_b = edge['geometry'].interpolate(s+step, normalized=True)
                        dx = pt_b.x - pt_a.x
                        dy = pt_b.y - pt_a.y
                        ax.arrow(pt_a.x, pt_a.y, dx, dy, head_width=6., head_length=4., fc='k', ec='k')
                ax.add_patch(patch)

    pyplot.tight_layout()
    pyplot.savefig(fname)
    print(coords)
    # import ipdb; ipdb.set_trace()


if __name__ == '__main__':
    road_route_failures = {
        ((610737.2950234852, -2202788.5159188174), (611823.5213352646, -2201178.5917434846)),
        ((614510.2390714448, -2206490.9905772824), (614051.3685043695, -2207024.6160830227)),
        ((610738.4514477034, -2202788.816111207), (610629.2842373576, -2201408.298489062)),
        ((610738.4514477034, -2202788.816111207), (611188.5482159964, -2202511.88379795)),
        ((610738.4514477034, -2202788.816111207), (610916.7416900548, -2202441.9872723194)),
        ((610737.2950234852, -2202788.5159188174), (611053.3781766766, -2202478.401636711)),
        ((610735.192646556, -2202787.9701696504), (611053.3781766766, -2202478.401636711)),
        ((610738.4514477034, -2202788.816111207), (610606.49484408, -2201512.005104267)),
        ((610037.4438296659, -2209807.105854752), (609837.2848334291, -2209893.4764031493))}

    place = 'Belo Horizonte, Brazil'
    roads = Roads(place)

    for i, (start, end) in enumerate(road_route_failures):
        plot_network(start, end, roads, fname='road_route_failures/{}.jpg'.format(i))
