import os
import json
import click
import config
import random
import logging
import osmnx as ox
import pandas as pd
from time import time
from road import Roads
from sim import TransitSim, Agent, Stop
from gtfs import Transit, util
from shapely.geometry import Point
from dateutil import parser
from collections import defaultdict

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


def get_decile(df, decile):
    return df[(df >= df.quantile(decile)) & (df <= df.quantile(decile+0.1))].dropna().index.values.tolist()


@click.command()
@click.argument('place')
@click.argument('gtfs_path')
@click.argument('sim_output_path')
@click.argument('sim_date')
@click.option('--debug', is_flag=True)
def run(place, gtfs_path, sim_output_path, sim_date, debug):
    """
    Example params:
    place = 'Belo Horizonte, Brazil'
    gtfs_path = 'data/gtfs/gtfs_bhtransit.zip'
    sim_output_path = '/tmp/seal/run__2018-04-22T14_43_51.895867/0'
    sim_date = '22/2/2017'

    If debug=True:
        collects some debugging data for routing
        and road speed calibration
        also uses less agents and a subset of the
        public transit trips for shorter run time
    """
    START = time()

    # TODO select date based on simulation data?
    dt = parser.parse(sim_date)

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
    transit = Transit(gtfs_path)

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
        sim = TransitSim(transit, router, roads, transit_roads,
                         save_history=True, history_window=(8*60*60, 8*60*60+5*60), debug=debug)

        # compute data needed to determine car ownership
        last_wages = {}
        houses = defaultdict(list)
        for id, agent in snapshot['agents'].items():
            x, y, house_id, firm_id, last_wage = agent

            # only keep track of working members
            if firm_id is not None:
                houses[house_id].append(id)
                last_wages[id] = last_wage

        last_wages_df = pd.DataFrame.from_dict(last_wages, orient='index')
        deciles = {}
        for decile in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            ids = get_decile(last_wages_df, decile)
            for id in ids:
                deciles[id] = decile

        # plan trips
        agents = []
        for id, agent in snapshot['agents'].items():
            # TODO need to get consistent about coordinate ordering!
            # though not alone: <https://stackoverflow.com/a/13579921/1097920>
            # we are using lat, lon ordering
            x, y, house_id, firm_id, last_wage = agent
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

            n_working_family = len(houses[house_id])
            decile = deciles.get(id)

            # decile is None if last_wage was None
            # so just use public transit in that case
            if decile is None:
                public = True

            # otherwise, see if a car is available
            else:
                decile_prob = config.WAGE_TO_CAR_OWNERSHIP_QUANTILES[decile]
                car_prob = (1/n_working_family) * decile_prob
                public = not random.random() <= car_prob

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

        logger.info('Exporting visualization data...')
        s = time()
        fname = 'viz_{}'.format(fname)
        output_path = os.path.join(results_output_path, fname)
        if not os.path.exists(results_output_path):
            os.makedirs(results_output_path)
        with open(output_path, 'w') as f:
            json.dump(sim.export(), f)
        logger.info('Saving visualization data took {}s'.format(time() - s))
    logger.info('Total run time: {}s'.format(time() - START))


if __name__ == '__main__':
    run()