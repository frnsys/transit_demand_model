# import json
import random
import logging
import osmnx as ox
from road import Map
from sim import Sim, Vehicle, Passenger
from gtfs import Transit, RouteType
from datetime import datetime
from shapely.geometry import Point
from functools import partial

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


# def car_next()


if __name__ == '__main__':
    place = 'Belo Horizonte, Brazil'
    gdf = ox.gdf_from_place(place)
    geo = gdf['geometry'].unary_union
    transit = Transit('data/gtfs/gtfs_bhtransit.zip')
    dt = datetime(year=2017, month=2, day=22, hour=10)
    router = transit.router_for_day(dt)
    map = Map(place, transit=transit)
    sim = Sim(map)

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
    # TODO we also assume that e.g. buses make it from the bus depot
    # to their first stop without any issue. if we wanted to get really
    # detailed we could also simulate the bus coming from the depot
    # to the first stop.
    # for trip_id, sched in transit.trip_stops:
    #     if trip_id not in router.valid_trips:
    #         continue
    #     first_stop = sched.iloc[0]

        # # buses should use roads
        # type = transit.trip_type(trip_id)
        # if type is RouteType.BUS:
        #     # map.router.
        #     pass
        #     # pre-compute road routes for buses
        #     route = map.router.route
        # else:
        #     route = sched

        # veh = Vehicle(id=trip_id, route=route, passengers=[])

        # # queue all vehicles for this trip for this day
        # for start in transit.trip_starts[trip_id]:
        #     # TODO veh.next
        #     sim.queue(start, veh.next)

    # TODO generate road trips
    n_agents = 10
    for agent in range(n_agents):
        dep_time = random.randint(0, 60*60*24)

        start, end = random_point(geo), random_point(geo)
        # TODO need to get consistent about coordinate ordering!
        # though not alone: <https://stackoverflow.com/a/13579921/1097920>
        start = start[1], start[0]
        end = end[1], end[0]

        public = random.choice([True, False])
        public = False # TEMP
        if public:
            # TODO
            route, time = router.route(start, end, dep_time)
            pas = Passenger(id=agent, route=route)
        else:
            route = map.router.route(start, end)
            veh = Vehicle(id=agent, route=route, passengers=[agent], current=None)
        sim.queue(dep_time, partial(map.router.next, veh))
    sim.run()

    # TODO
    # for deckgl visualization
    # data = sim.export()

    # with open('viz/assets/trips.json', 'w') as f:
    #     json.dump(data['trips'], f)

    # with open('viz/assets/coord.json', 'w') as f:
    #     json.dump(data['place'], f)

    # with open('viz/assets/stops.json', 'w') as f:
    #     json.dump(data['stops'], f)

"""
so we have:

- vehicles, which have an id, a type (e.g. bus, car, etc), a route, and a set of passengers
- if the vehicle is a road network, then we just hand off the vehicle to the
road network and let that generate events
- otherwise, we let the vehicle generate events directly
"""
