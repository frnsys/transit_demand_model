import json
import random
import logging
import osmnx as ox
from road import Roads
from sim import TransitSim, Agent
from gtfs import Transit
from datetime import datetime
from shapely.geometry import Point

random.seed(0)
logging.basicConfig(level=logging.INFO)


def random_point(geo):
    """rejection sample a point within geo shape"""
    minx, miny, maxx, maxy = geo.bounds
    point = None
    while point is None:
        lat = random.uniform(minx, maxx)
        lon = random.uniform(miny, maxy)
        pt = Point(lat, lon)
        if geo.contains(pt):
            point = (lat, lon)
    return point

if __name__ == '__main__':
    place = 'Belo Horizonte, Brazil'
    gdf = ox.gdf_from_place(place)
    geo = gdf['geometry'].unary_union
    transit = Transit('data/gtfs/gtfs_bhtransit.zip')
    dt = datetime(year=2017, month=2, day=22, hour=10)
    router = transit.router_for_day(dt)
    roads = Roads(place, transit=transit)
    sim = TransitSim(transit, router, roads)

    agents = []
    n_agents = 100
    for i in range(n_agents):
        dep_time = random.randint(0, 60*60*24)

        start, end = random_point(geo), random_point(geo)
        # TODO need to get consistent about coordinate ordering!
        # though not alone: <https://stackoverflow.com/a/13579921/1097920>
        start = start[1], start[0]
        end = end[1], end[0]

        public = random.choice([True, False])
        agent = Agent(id=i, dep_time=dep_time, start=start, end=end, public=public)
        agents.append(agent)

    sim.run(agents)

    # for deckgl visualization
    data = sim.export()

    with open('viz/assets/trips.json', 'w') as f:
        json.dump(data['trips'], f)

    with open('viz/assets/coord.json', 'w') as f:
        json.dump(data['place'], f)

    with open('viz/assets/stops.json', 'w') as f:
        json.dump(data['stops'], f)
