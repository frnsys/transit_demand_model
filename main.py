# import json
import random
import logging
import osmnx as ox
from road import Map
from sim import Sim, Vehicle
from gtfs import Transit
from datetime import datetime
from shapely.geometry import Point

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
    map = Map(place, transit=transit)
    sim = Sim(map, dt.timestamp())

    # prepare all trips for day
    # pre-queue events for all public transit trips
    # they should always be running, regardless of if there
    # are any passengers, since they can affect traffic,
    # and the implementation is easier this way b/c we aren't
    # juggling specific spawning conditions for these trips.
    # TODO however, pre-queuing all public transit trips ahead
    # of time doesn't account for the possibility of trips
    # on the same e.g. tracks being delayed because of delays
    # in earlier trips sharing the same e.g. track. at least,
    # for metro trips. since buses use the road network, the delays
    # should propagate.
    # perhaps after a trip stops, it re-queues the next time it will run?
    trips = {}
    for trip_id, group in transit.trip_stops:
        if trip_id not in router.valid_trips:
            continue
        first_stop = group.iloc[0]
        # TODO should keep track of route type
        # TODO buses should use roads
        veh = Vehicle(id=trip_id, stop=first_stop['stop_id'], passengers=[])
        trips[trip_id] = veh
        # TODO this needs to be based off of frequencies rather than stop_times
        sim.queue(first_stop['dep_sec'], veh.next)

    # TODO generate road trips
    n_agents = 10
    for agent in range(n_agents):
        dep_time = random.randint(0, 60*60*24)
        start, end = random_point(geo), random_point(geo)
        public = random.choice([True, False])
        if public:
            # TODO
            route, time = router.route(start, end, dep_time)
        else:
            veh = Vehicle(id=agent)
            trips[agent] = veh
        sim.queue(dep_time, veh.next)
    # sim.run()

    # TODO
    # for deckgl visualization
    # data = sim.export()

    # with open('viz/assets/trips.json', 'w') as f:
    #     json.dump(data['trips'], f)

    # with open('viz/assets/coord.json', 'w') as f:
    #     json.dump(data['place'], f)

    # with open('viz/assets/stops.json', 'w') as f:
    #     json.dump(data['stops'], f)
