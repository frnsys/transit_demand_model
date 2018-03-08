# import json
import logging
import numpy as np
from map import Map
from sim import Sim
from gtfs import Transit

logging.basicConfig(level=logging.INFO)


if __name__ == '__main__':
    place = 'Belo Horizonte, Brazil'
    transit = Transit('data/gtfs/gtfs_bhtransit.zip', 'data/transit/bh')
    map = Map(place, transit=transit)
    sim = Sim(map)

    # plan routes
    # n_agents = 5000
    # n_agents = 2000
    n_agents = 10
    trips = {}

    for agent in range(n_agents):
        # start, end = np.random.choice(sim.map.network.nodes(), 2)
        start = (-19.821486,-43.946748)
        end = (-19.9178,-43.93337)
        # public = np.random.choice([True, False])
        public = True
        trips[agent] = (start, end, max(0, 1500 + 500 * np.random.randn()), public)
    sim.run(trips, strict=True)

    # for deckgl visualization
    # data = sim.export()

    # with open('viz/assets/trips.json', 'w') as f:
    #     json.dump(data['trips'], f)

    # with open('viz/assets/coord.json', 'w') as f:
    #     json.dump(data['place'], f)

    # with open('viz/assets/stops.json', 'w') as f:
    #     json.dump(data['stops'], f)
