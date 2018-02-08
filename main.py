import json
import numpy as np
from simulation import Sim


if __name__ == '__main__':
    place = 'Brasília, Brazil'
    sim = Sim(place)

    # plan routes
    n_agents = 2000
    trips = {}
    for agent in range(n_agents):
        start, end = np.random.choice(sim.network.G.nodes(), 2)
        trips[agent] = (start, end, max(0, 1500 + 500 * np.random.randn()))
    sim.run(trips, strict=False)

    # for deckgl visualization
    trips = []
    for trip in sim.trips.values():
        trips.append({
            'vendor': 0,
            'segments': trip.segments(sim.network)
        })

    with open('viz/assets/trips.json', 'w') as f:
        json.dump(trips, f)
