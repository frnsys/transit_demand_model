import json
import logging
import numpy as np
from map import Map
from sim import Sim
from gtfs import load_gtfs

logging.basicConfig(level=logging.INFO)


if __name__ == '__main__':
    place = 'Belo Horizonte, Brazil'
    buses = load_gtfs('data/gtfs/gtfs_bhtransit.zip')
    map = Map(place, buses=buses)
    sim = Sim(map)

    # plan routes
    # n_agents = 5000
    n_agents = 100
    trips = {}
    for agent in range(n_agents):
        start, end = np.random.choice(sim.map.network.nodes(), 2)
        trips[agent] = (start, end, max(0, 1500 + 500 * np.random.randn()))
    sim.run(trips, strict=False)

    # for deckgl visualization
    data = sim.export()

    with open('viz/assets/trips.json', 'w') as f:
        json.dump(data['trips'], f)

    with open('viz/assets/coord.json', 'w') as f:
        json.dump(data['place'], f)

    with open('viz/assets/stops.json', 'w') as f:
        json.dump(data['bus_stops'], f)
