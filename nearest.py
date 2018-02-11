from tqdm import tqdm
import osmnx as ox
from gtfs import load_gtfs
from trip import to_xy
from simulation import Sim

place = 'Belo Horizonte, Brazil'
sim = Sim(place)
coord = (-19.821486, -43.946748)

def nearest_node(network, coord):
    pos = to_xy(network, *coord)
    pos = pos[::-1] # should be y, x
    n, dist = ox.get_nearest_node(network.G, pos, method='euclidean', return_dist=True)
    return network.G.nodes[n]

path = 'gtfs/gtfs_bhtransit.zip'
gtfs = load_gtfs(path)
stops = [(r.stop_lat, r.stop_lon) for i, r in gtfs['stops'].iterrows()]

nearest = []
for coord in tqdm(stops):
    n = nearest_node(sim.network, coord)
    nearest.append((float(n['lat']), float(n['lon'])))

import json
with open('viz/assets/nearest.json', 'w') as f:
    json.dump(nearest, f)