import math
import logging
import numpy as np
from tqdm import tqdm
from road import Roads
from matplotlib import pyplot
from descartes import PolygonPatch
from shapely.geometry import Point
from gtfs.util import load_gtfs

logging.basicConfig(level=logging.INFO)
BLUE = '#6699cc'


def plot_network(points, roads, radius=1000, labels=None, colors=None, annotate=True, fname='map.jpg'):
    # compute plot bounds
    min_x = float('inf')
    max_x = -float('inf')
    min_y = float('inf')
    max_y = -float('inf')
    for x, y in points:
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
    for i, (x, y) in enumerate(points):
        pt = Point(x, y)
        circle = pt.buffer(5)
        if colors is not None:
            color = colors[i]
        else:
            color = '#e5c110'
        patch = PolygonPatch(circle, fc=color, ec=color, alpha=0.5, zorder=2)
        ax.add_patch(patch)
        lat, lon = roads.to_latlon(x, y)
        coords.append((lat, lon))
        if annotate:
            if labels is not None:
                ax.text(x, y, '{} ({:.3f}, {:.3f})'.format(labels[i], lat, lon))
            else:
                ax.text(x, y, '{:.3f}, {:.3f})'.format(lat, lon))

    for n in tqdm(inside):
        data = roads.network.node[n]
        x, y = data['x'], data['y']
        pt = Point(x, y)
        circle = pt.buffer(2)
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
    # import ipdb; ipdb.set_trace()


if __name__ == '__main__':
    road_route_failures = {
        (((610252.242464825, -2209094.7395943375), (610075.3842662319, -2208711.320126826)), ('00101031703051', '00105783005001')),
        (((610259.3653515632, -2209075.539031996), (610698.6684789823, -2209034.4226473835)), ('00101031703049', '00103858100659')),
        (((610259.3653515632, -2209075.539031996), (610921.8057858994, -2207739.996126832)), ('00101031703049', '00101031703001')),
        (((607079.3276247387, -2197961.137387971), (607214.0146767742, -2198579.3530438226)), ('00105512504055', '00105512503705')),
        (((610259.3653515632, -2209075.539031996), (610075.3842662319, -2208711.320126826)), ('00101031703049', '00105783005001')),
        (((607079.3276247387, -2197961.137387971), (608277.3258042515, -2200236.6129044765)), ('00105512504055', '00105512501275')),
        (((610259.3653515632, -2209075.539031996), (610748.3451684971, -2208748.8358003297)), ('00101031703049', '00110896000495')),
        (((614510.2390714448, -2206490.990577282), (614051.3685043695, -2207024.6160830227)), ('00110663300580', '00110663300944')),
        (((610245.1568105182, -2209113.697144034), (610075.3842662319, -2208711.320126826)), ('00101031703053', '00105783005001')),
        (((607079.3276247387, -2197961.137387971), (607094.2998998251, -2198130.029991377)), ('00105512504055', '00105512504555'))}

    place = 'Belo Horizonte, Brazil'
    roads = Roads(place, type='drive_service', buffer=2000)

    for i, ((start, end), (start_stop, end_stop)) in enumerate(road_route_failures):
        plot_network([start, end], roads, labels=['START', 'END'], fname='road_route_failures/{}.jpg'.format(i))

    import json
    stops_debug = json.load(open('stops_debug.json', 'r'))
    gtfs = load_gtfs('data/gtfs/gtfs_bhtransit.zip')

    for i, ((start, end), (start_stop, end_stop)) in enumerate(road_route_failures):
        for coord, stop_id in [(start, start_stop), (end, end_stop)]:
            edge_ids = stops_debug[stop_id]
            stop = gtfs['stops'].set_index('stop_id').loc[stop_id]
            stop_pt = roads.to_xy(stop.stop_lat, stop.stop_lon)

            points = []
            labels = []
            colors = []
            stop_pt_ = Point(*stop_pt)
            for i, id in enumerate(edge_ids):
                edge_data = roads.edges[id][-1]
                line = edge_data['geometry']
                p = line.project(stop_pt_, normalized=True)
                pt = line.interpolate(p, normalized=True)
                points.append((pt.x, pt.y))
                labels.append('GUESS')

                # closest
                if i == 0:
                    colors.append('#00ff00')
                else:
                    colors.append('#e5c110')

            plot_network(
                [stop_pt] + points,
                roads,
                labels=['STOP {}'.format(stop_id)] + labels,
                colors=['#0000ff'] + colors,
                annotate=False,
                fname='stops_debug/{}.jpg'.format(stop_id))
