# import json
import random
import logging
import osmnx as ox
from road import Map
from sim import Sim, Vehicle, Passenger
from gtfs import Transit, RouteType, WalkLeg, TransferLeg, NoRouteFound
from datetime import datetime
from shapely.geometry import Point
from functools import partial
from collections import defaultdict
import networkx as nx

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


def public_transit_next(stops, vehicle, time):
    events = []
    vehicle.current += 1
    cur_stop = vehicle.route.iloc[vehicle.current]

    # pickup passengers
    trip_id = vehicle.id.split('_')[0]
    for (end_stop, action) in stops[cur_stop['stop_id']][trip_id]:
        print(vehicle.id, 'Picking up passengers at', cur_stop.stop_id, time)
        vehicle.passengers[end_stop].append(action)
        stops[cur_stop['stop_id']][trip_id] = []

    # dropoff passengers
    for action in vehicle.passengers[cur_stop['stop_id']]:
        print(vehicle.id, 'Dropping off passengers at', cur_stop.stop_id, time)
        events.extend(action(time))
        vehicle.passengers[cur_stop['stop_id']] = []

    try:
        next_stop = vehicle.route.iloc[vehicle.current + 1]
    except IndexError:
        # trip is done
        return events
    time = next_stop['arr_sec'] - cur_stop['dep_sec']
    events.append((time, partial(public_transit_next, stops, vehicle)))
    return events


def on_bus_arrive(stops, transit, router, road_vehicle, transit_vehicle, time):
    # we have two vehicles:
    # - one which represents the public transit side of the bus
    #   (picking up and dropping off passengers)
    # - one which represents the bus as it travels on roads

    # pick-up/drop-off
    events = public_transit_next(stops, transit_vehicle, time)

    # prepare to depart
    try:
        cur_stop = transit_vehicle.route.iloc[transit_vehicle.current]
        next_stop = transit_vehicle.route.iloc[transit_vehicle.current + 1]
        time_to_dep = cur_stop['dep_sec'] - cur_stop['arr_sec']
    except IndexError:
        # trip is done
        return events

    # figure out road route
    start = transit.stops.loc[cur_stop.stop_id][['stop_lat', 'stop_lon']].values
    end = transit.stops.loc[next_stop.stop_id][['stop_lat', 'stop_lon']].values
    try:
        route = map.router.route(start, end)
    except nx.NetworkXNoPath:
        # TODO seems like something is wrong with the map
        # it cant't find a path but there is a relatively
        # short one on OSM and Google Maps
        # import ipdb; ipdb.set_trace()
        return []
    road_vehicle.route = route
    road_vehicle.current = None # so we don't double-leave the current edge

    # setup on arrive trigger
    on_arrive = partial(on_bus_arrive, stops, transit, router, road_vehicle, transit_vehicle)

    # override last event
    events[-1] = (time_to_dep, partial(map.router.next, road_vehicle, on_arrive))
    return events


def passenger_next(transit, stops, passenger, time):
    try:
        leg = passenger.route.pop(0)
    except IndexError:
        print(passenger.id, 'ARRIVED', time, datetime.fromtimestamp(time))
        return []
    action = partial(passenger_next, transit, stops, passenger)
    if isinstance(leg, WalkLeg):
        print(passenger.id, 'Walking', time)
        rel_time = leg.time
        return [(rel_time, action)]
    elif isinstance(leg, TransferLeg):
        print(passenger.id, 'Transferring', time)
        rel_time = leg.time
        return [(rel_time, action)]
    else:
        # wait at stop
        # TODO how long do we wait to see if they re-plan?
        # or check if there is an equivalent trip they can take?

        # convert from iids to ids
        dep_stop = transit.stop_idx.id[leg.dep_stop]
        arr_stop = transit.stop_idx.id[leg.arr_stop]
        trip_id = transit.trip_idx.id[leg.trip_id]
        print(passenger.id, 'Waiting at stop', dep_stop, time)
        stops[dep_stop][trip_id].append((arr_stop, action))
        return []




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
    # we also assume that e.g. buses make it from the bus depot
    # to their first stop without any issue. if we wanted to get really
    # detailed we could also simulate the bus coming from the depot
    # to the first stop.
    valid_trips = list(router.valid_trips)[:200]
    for trip_id, sched in transit.trip_stops:
        # TODO temp limit trips for faster runs
        if trip_id not in valid_trips:
        # if trip_id not in router.valid_trips:
            continue
        first_stop = sched.iloc[0]

        # buses should use roads
        type = transit.trip_type(trip_id)

        # queue all vehicles for this trip for this day
        for i, start in enumerate(transit.trip_starts[trip_id]):
            id = '{}_{}'.format(trip_id, i)
            veh = Vehicle(id=id, route=sched, passengers=defaultdict(list), current=-1)

            if type is RouteType.BUS:
                # bus will calc route when it needs to
                road_vehicle = Vehicle(id='{}_ROAD'.format(id), route=[], passengers=[], current=None)
                action = partial(on_bus_arrive, sim.stops, transit, router, road_vehicle)
            else:
                action = partial(public_transit_next, sim.stops)
            action = partial(action, veh)
            sim.queue(start, action)
            # TEMP just starting one of each trip
            break

    n_agents = 100
    for agent in range(n_agents):
        dep_time = random.randint(0, 60*60*24)

        start, end = random_point(geo), random_point(geo)
        # TODO need to get consistent about coordinate ordering!
        # though not alone: <https://stackoverflow.com/a/13579921/1097920>
        start = start[1], start[0]
        end = end[1], end[0]

        public = random.choice([True, False])
        if public:
            try:
                route, time = router.route(start, end, dep_time)
                pas = Passenger(id=agent, route=route)
                sim.queue(dep_time, partial(passenger_next, transit, sim.stops, pas))
            except NoRouteFound:
                # just skipping for now
                # this has happened because the departure time
                # is late and we don't project schedules into the next day
                continue
        else:
            route = map.router.route(start, end)
            veh = Vehicle(id=agent, route=route, passengers=[agent], current=None)
            sim.queue(dep_time, partial(map.router.next, veh, lambda t: []))

    print('N EVENTS START', len(sim.events))
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
