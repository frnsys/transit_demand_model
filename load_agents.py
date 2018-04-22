import json
import random
import logging
import osmnx as ox
from road import Roads
from sim import TransitSim, Agent, Stop
from gtfs import Transit, util
from datetime import datetime
from shapely.geometry import Point

random.seed(0)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('main')

if __name__ == '__main__':
    place = 'Belo Horizonte, Brazil'
    gdf = ox.gdf_from_place(place)
    geo = gdf['geometry'].unary_union

    logger.info('Preparing public transit data...')
    transit = Transit('data/gtfs/gtfs_bhtransit.zip')

    logger.info('Preparing public transit router...')
    dt = datetime(year=2017, month=2, day=22, hour=10)
    router = transit.router_for_day(dt)

    # print(router.csa.route_many([0,1,2,3], [4,5,6,7], [0,0,0,0]))
    # import ipdb; ipdb.set_trace()

    logger.info('Preparing public transit road network...')
    transit_roads = Roads(place, transit=transit, type='drive_service', buffer=2000)

    logger.info('Preparing private road network...')
    roads = Roads(place, type='drive', buffer=2000)

    logger.info('Preparing sim...')
    sim = TransitSim(transit, router, roads, transit_roads)

    snapshot = json.load(open('/tmp/seal/run__2018-04-22T14_43_51.895867/0/transit/start.json', 'r'))

    agents = []
    for id, agent in snapshot['agents'].items():
        # TODO need to get consistent about coordinate ordering!
        # though not alone: <https://stackoverflow.com/a/13579921/1097920>
        # we are using lat, lon ordering
        x, y, house_id, firm_id = agent
        start = y, x

        # check if agent is within bounds
        pt = Point(x, y)
        if not geo.contains(pt):
            continue

        # TODO temporarily only traveling to firms
        if firm_id is None:
            continue
        x, y = snapshot['firms'][str(firm_id)]
        end = y, x

        # assume people try to arrive at work by 7-9am
        target_arrival_time = random.randint(7*60*60, 9*60*60)

        # rough estimate of travel time
        avg_speed = 80 #km/h
        dist = util.haversine(start[0], start[1], end[0], end[1]) # km
        expected_travel_time = dist/avg_speed
        dep_time = target_arrival_time - expected_travel_time

        # travel plan
        stops = [Stop(start=start, end=end, dep_time=dep_time)]

        public = random.choice([True, False])
        agent = Agent(id=id, stops=stops, public=public)
        agents.append(agent)

    agents = agents[:1000]
    sim.run(agents)
    import ipdb; ipdb.set_trace()