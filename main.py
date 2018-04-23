import os
import json
import click
import config
import random
import logging
import osmnx as ox
from time import time
from road import Roads
from sim import TransitSim, Agent, Stop
from gtfs import Transit, util
from shapely.geometry import Point
from dateutil import parser

random.seed(0)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('main')

def split_path(path, splits=2):
    parts = []
    for _ in range(splits):
        head, tail = os.path.split(path)
        parts.append(tail)
        path = head
    return path, parts[::-1]


@click.command()
@click.argument('place')
@click.argument('sim_output_path')
@click.argument('sim_datetime')
@click.option('--debug', is_flag=True)
def run(place, sim_output_path, sim_datetime, debug):
    """
    Example params:
    place = 'Belo Horizonte, Brazil'
    sim_output_path = '/tmp/seal/run__2018-04-22T14_43_51.895867/0'
    sim_datetime = '22/2/2017 10:00'

    If debug=True:
        collects some debugging data for routing
        and road speed calibration
        also uses less agents and a subset of the
        public transit trips for shorter run time
    """
    START = time()

    # TODO select date based on simulation data?
    dt = parser.parse(sim_datetime)

    # generate sim name based on sim output path
    # so we can associate this transit simulation
    # with a particular simulation run
    _, sim_name = split_path(sim_output_path, splits=2)
    sim_name = '_'.join(sim_name)
    sim_transit_path = os.path.join(sim_output_path, 'transit')

    # figure out what transit snapshots we need to simulate
    snapshots = [fname for fname in os.listdir(sim_transit_path) if fname.endswith('.json')]

    # prepare output path as needed
    results_output_path = os.path.join(config.OUTPUT_PATH, sim_name)

    # get geospatial data
    gdf = ox.gdf_from_place(place)
    geo = gdf['geometry'].unary_union

    logger.info('Preparing public transit data...')
    transit = Transit('data/gtfs/gtfs_bhtransit.zip')

    logger.info('Preparing public transit router...')
    router = transit.router_for_day(dt)

    logger.info('Preparing public transit road network...')
    transit_roads = Roads(place, transit=transit, type='drive_service', buffer=2000)

    logger.info('Preparing private road network...')
    roads = Roads(place, type='drive', buffer=2000)

    for fname in snapshots:
        logger.info('Preparing sim for snapshot "{}"...'.format(fname))
        with open(os.path.join(sim_transit_path, fname), 'r') as f:
            snapshot = json.load(f)
        sim = TransitSim(transit, router, roads, transit_roads, debug=debug)

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
            stops = [Stop(start=start, end=end, dep_time=dep_time, type=Stop.Type.Commute)]

            public = random.choice([True, False])
            agent = Agent(id=id, stops=stops, public=public)
            agents.append(agent)

        if debug:
            agents = agents[:100]
        sim.run(agents)

        logger.info('Saving simulation results...')
        s = time()
        output_path = os.path.join(results_output_path, fname)
        if not os.path.exists(results_output_path):
            os.makedirs(results_output_path)
        with open(output_path, 'w') as f:
            json.dump(sim.data, f)
        logger.info('Saving simulation results took {}s'.format(time() - s))
    logger.info('Total run time: {}s'.format(time() - START))


if __name__ == '__main__':
    run()