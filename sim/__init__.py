import logging
from .base import Sim
from tqdm import tqdm
from functools import partial
from collections import defaultdict
from recordclass import recordclass
from road.router import NoRoadRouteFound
from gtfs.router import WalkLeg, TransferLeg, TransitLeg, NoTransitRouteFound
from gtfs import RouteType

logger = logging.getLogger(__name__)

Vehicle = recordclass('Vehicle', ['id', 'route', 'passengers', 'current'])
Passenger = recordclass('Passenger', ['id', 'route'])
Agent = recordclass('Agent', ['id', 'start', 'end', 'dep_time', 'public'])


class TransitSim(Sim):
    def __init__(self, transit, router, roads, cache_routes=True):
        super().__init__()
        self.transit = transit
        self.router = router
        self.roads = roads

        # for loading/unloading public transit passengers
        self.stops = defaultdict(lambda: defaultdict(list))

        # bus route caching
        # can increase speed, but
        # then buses may use "stale" routes
        # or be unable to re-plan according to congestion
        self.route_cache = {}
        self.cache_routes = cache_routes

    def run(self, agents):
        self.queue_public_transit()
        self.queue_agents(agents)
        super().run()

    def queue_agents(self, agents):
        """queue agents trip,
        which may be via car or public transit"""
        logger.info('Preparing agents...')
        for agent in tqdm(agents):
            if agent.public:
                try:
                    route, time = self.router.route(agent.start, agent.end, agent.dep_time)
                    pas = Passenger(id=agent.id, route=route)
                    self.queue(agent.dep_time, partial(self.passenger_next, pas))
                except NoTransitRouteFound:
                    # just skipping for now
                    # this has happened because the departure time
                    # is late and we don't project schedules into the next day
                    continue
            else:
                route = self.roads.route(agent.start, agent.end)
                veh = Vehicle(id=agent.id, route=route, passengers=[agent.id], current=None)
                self.queue(agent.dep_time, partial(self.roads.router.next, veh, lambda t: []))

    def queue_public_transit(self):
        """
        prepare all trips for day
        pre-queue events for all public transit trips
        they should always be running, regardless of if there
        are any passengers, since they can affect traffic,
        and the implementation is easier this way b/c we aren't
        juggling specific spawning conditions for these trips.
        we also assume that e.g. buses make it from the bus depot
        to their first stop without any issue. if we wanted to get really
        detailed we could also simulate the bus coming from the depot
        to the first stop.
        """
        logger.info('Preparing public transit vehicles...')
        for trip_id, sched in tqdm(self.transit.trip_stops):
            # faster access as a list of dicts
            sched = sched.to_dict('records')
            if trip_id not in self.router.valid_trips:
                continue

            # check the route type;
            # buses should use roads
            type = self.transit.trip_type(trip_id)

            # queue all vehicles for this trip for this day
            for i, start in enumerate(self.transit.trip_starts[trip_id]):
                id = '{}_{}'.format(trip_id, i)
                veh = Vehicle(id=id, route=sched, passengers=defaultdict(list), current=-1)

                if type is RouteType.BUS:
                    # bus will calc route when it needs to
                    road_vehicle = Vehicle(id='{}_ROAD'.format(id), route=[], passengers=[], current=None)
                    action = partial(self.on_bus_arrive, road_vehicle)
                else:
                    action = self.transit_next
                action = partial(action, veh)
                self.queue(start, action)

    def transit_next(self, vehicle, time):
        """action for public transit vehicles"""
        events = []
        vehicle.current += 1
        cur_stop = vehicle.route[vehicle.current]

        # pickup passengers
        trip_id = vehicle.id.split('_')[0]
        for (end_stop, action) in self.stops[cur_stop['stop_id']][trip_id]:
            logger.info('[{}] {} Picking up passengers at {}'.format(time, vehicle.id, cur_stop['stop_id']))
            vehicle.passengers[end_stop].append(action)
            self.stops[cur_stop['stop_id']][trip_id] = []

        # dropoff passengers
        for action in vehicle.passengers[cur_stop['stop_id']]:
            logger.info('[{}] {} Dropping off passengers at {}'.format(time, vehicle.id, cur_stop['stop_id']))
            events.extend(action(time))
            vehicle.passengers[cur_stop['stop_id']] = []

        try:
            next_stop = vehicle.route[vehicle.current + 1]
        except IndexError:
            # trip is done
            return events

        # schedule next leg of trip
        time = next_stop['arr_sec'] - cur_stop['dep_sec']
        events.append((time, partial(self.transit_next, vehicle)))
        return events


    def on_bus_arrive(self, road_vehicle, transit_vehicle, time):
        """triggers when a bus arrives at its next stop in the road network.
        buses have to be handled specially because they are a hybrid
        public transit and road vehicle
        we have two vehicles:
        - one which represents the public transit side of the bus
        (picking up and dropping off passengers)
        - one which represents the bus as it travels on roads"""

        # pick-up/drop-off
        events = self.transit_next(transit_vehicle, time)

        # prepare to depart
        try:
            cur_stop = transit_vehicle.route[transit_vehicle.current]
            next_stop = transit_vehicle.route[transit_vehicle.current + 1]
            time_to_dep = cur_stop['dep_sec'] - cur_stop['arr_sec']
        except IndexError:
            # trip is done
            return events

        # figure out road route
        try:
            start, end = cur_stop['stop_id'], next_stop['stop_id']
            if self.cache_routes and (start, end) in self.route_cache:
                route = self.route_cache[(start, end)][:]
            else:
                route = self.roads.route_bus(start, end)
                self.route_cache[(start, end)] = route[:]
        except NoRoadRouteFound:
            # TODO seems like something is wrong with the roads map
            # it cant't find a path but there is a relatively
            # short one on OSM and Google Maps
            # import ipdb; ipdb.set_trace()
            logger.warn('Ignoring no road route found!')
            return []

        # update route
        road_vehicle.route = route

        # so we don't double-leave the current edge
        # otherwise we get negative occupancies in roads
        road_vehicle.current = None

        # setup on arrive trigger
        on_arrive = partial(self.on_bus_arrive, road_vehicle, transit_vehicle)

        # override last event
        events[-1] = (time_to_dep, partial(self.roads.router.next, road_vehicle, on_arrive))
        return events


    def passenger_next(self, passenger, time):
        """action for individual public transit passengers"""
        try:
            leg = passenger.route.pop(0)
        except IndexError:
            logger.info('[{}] {} Arrived'.format(time, passenger.id))
            return []

        # setup next actoin
        action = partial(self.passenger_next, passenger)

        if isinstance(leg, WalkLeg):
            logger.info('[{}] {} Walking'.format(time, passenger.id))
            rel_time = leg.time
            return [(rel_time, action)]

        elif isinstance(leg, TransferLeg):
            logger.info('[{}] {} Transferring'.format(time, passenger.id))
            rel_time = leg.time
            return [(rel_time, action)]

        elif isinstance(leg, TransitLeg):
            # wait at stop
            # TODO how long do we wait to see if they re-plan?
            # or check if there is an equivalent trip they can take?

            # convert from iids to ids
            dep_stop = self.transit.stop_idx.id[leg.dep_stop]
            arr_stop = self.transit.stop_idx.id[leg.arr_stop]
            trip_id = self.transit.trip_idx.id[leg.trip_id]

            logger.info('[{}] {} Waiting at stop {}'.format(time, passenger.id, dep_stop))
            self.stops[dep_stop][trip_id].append((arr_stop, action))
            return []


    # TODO
    def export(self):
        """return simulation run data in a form
        easy to export to JSON for visualization"""
        trips = []
        for trip in self.trips.values():
            trips.append({
                'vendor': 0,
                'segments': trip.segments(self.map)
            })

        stops = [s['coord'] for s in self.map.stops.values()]

        return {
            'place': {
                'lat': float(self.map.place_meta['lat']),
                'lng': float(self.map.place_meta['lon'])
            },
            'trips': trips,
            'stops': stops
        }
