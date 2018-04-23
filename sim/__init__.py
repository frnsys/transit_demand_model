import enum
import logging
from .base import Sim
from tqdm import tqdm
from functools import partial
from collections import defaultdict
from recordclass import recordclass
from road.router import NoRoadRouteFound, edge_travel_time
from gtfs.router import WalkLeg, TransferLeg, TransitLeg, NoTransitRouteFound
from gtfs import RouteType

logger = logging.getLogger(__name__)

Vehicle = recordclass('Vehicle', ['id', 'route', 'passengers', 'current', 'type'])
Passenger = recordclass('Passenger', ['id', 'route'])
Stop = recordclass('Stop', ['start', 'end', 'dep_time', 'type'])
Agent = recordclass('Agent', ['id', 'stops', 'public'])

ACCEPTABLE_DELAY_MARGIN = 5*60

class VehicleType(enum.Enum):
    Public = 0
    Private = 1

class StopType(enum.IntEnum):
    Commute = 0

Stop.Type = StopType


class TransitSim(Sim):
    def __init__(self, transit, router, roads, transit_roads, cache_routes=True, debug=False):
        super().__init__()
        self.transit = transit
        self.router = router
        self.roads = roads
        self.transit_roads = transit_roads

        # for loading/unloading public transit passengers
        self.stops = defaultdict(lambda: defaultdict(list))

        # bus route caching
        # can increase speed, but
        # then buses may use "stale" routes
        # or be unable to re-plan according to congestion
        self.route_cache = {}
        self.cache_routes = cache_routes

        # track (road) vehicle trips,
        # for exporting (visualization) purposes
        # self.history = defaultdict(list)

        self.debug = debug

        # only if debug=True
        # for calibrating road network speed
        # to bus schedules
        self.last_deps = {}
        self.delays = []

        # only if debug=True
        # for debugging where
        # routes aren't found on the road network
        self.road_route_failures = set()

        # all output data
        self.data = {
            'agent_trips': [],
            'road_capacities': defaultdict(list)
        }

    def run(self, agents):
        self.queue_public_transit()
        self.queue_agents(agents)
        super().run()

    def on_agent_arrive(self, agent, stop, time):
        # record data
        self.data['agent_trips'].append((agent.id, stop.start, stop.end, stop.type, float(stop.dep_time), float(time)))

        if not agent.stops:
            return []

        # schedule next stop
        return [self.route_agent(agent)]

    def route_agent(self, agent):
        if not agent.stops:
            return

        stop = agent.stops.pop(0)

        on_arrive = partial(self.on_agent_arrive, agent, stop)
        if agent.public:
            try:
                route, time = self.router.route(stop.start, stop.end, stop.dep_time)
                pas = Passenger(id=agent.id, route=route)
                return stop.dep_time, partial(self.passenger_next, pas, on_arrive)
            except NoTransitRouteFound:
                # TODO just skipping for now
                # this has happened because the departure time
                # is late and we don't project schedules into the next day
                return
        else:
            try:
                route = self.roads.route(stop.start, stop.end)
            except NoRoadRouteFound:
                # TODO just skipping for now
                # likely because something is wrong with the road network
                # see other place we are catching NoRoadRouteFound
                logger.warn('Ignoring no road route found! ({} -> {})'.format(stop.start, stop.end))
                return
            veh = Vehicle(id=agent.id, route=route, passengers=[agent.id], current=None, type=VehicleType.Private)
            return stop.dep_time, partial(self.road_next, veh, on_arrive)

    def queue_agents(self, agents):
        """queue agents trip,
        which may be via car or public transit"""
        logger.info('Preparing agents...')
        for agent in tqdm(agents):
            ev = self.route_agent(agent)
            if ev is not None:
                self.queue(*ev)

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
        if self.debug:
            valid_trips = sorted(list(self.router.valid_trips))[:10]
        else:
            valid_trips = self.router.valid_trips
        for trip_id, sched in tqdm(self.transit.trip_stops):
            # faster access as a list of dicts
            sched = sched.to_dict('records')
            if trip_id not in valid_trips:
                continue

            # check the route type;
            # buses should use roads
            type = self.transit.trip_type(trip_id)

            # queue all vehicles for this trip for this day
            for i, start in enumerate(self.transit.trip_starts[trip_id]):
                id = '{}_{}'.format(trip_id, i)
                veh = Vehicle(id=id, route=sched, passengers=defaultdict(list), current=-1, type=VehicleType.Public)

                if type is RouteType.BUS:
                    # bus will calc route when it needs to
                    road_vehicle = Vehicle(id='{}_ROAD'.format(id), route=[], passengers=[], current=None, type=VehicleType.Public)
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
            logger.debug('[{}] {} Picking up passengers at {}'.format(time, vehicle.id, cur_stop['stop_id']))
            vehicle.passengers[end_stop].append(action)
            self.stops[cur_stop['stop_id']][trip_id] = []

        # dropoff passengers
        for action in vehicle.passengers[cur_stop['stop_id']]:
            logger.debug('[{}] {} Dropping off passengers at {}'.format(time, vehicle.id, cur_stop['stop_id']))
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
        cur_stop = transit_vehicle.route[transit_vehicle.current]

        if self.debug:
            last_dep = self.last_deps.get(transit_vehicle.id)
            if last_dep is not None:
                # we compare scheduled vs actual travel times rather than
                # scheduled vs actual arrival times to control for drift.
                # if we compared arrival times, earlier days would accumulate
                # and likely cause all subsequent arrivals to be delayed.
                # comparing travel times avoids this and also
                # lets us better diagnose where the largest travel time
                # discrepancies are.
                last_stop = transit_vehicle.route[transit_vehicle.current-1]
                scheduled_travel_time = cur_stop['arr_sec'] - last_stop['dep_sec']
                actual_travel_time = time - last_dep
                delay = actual_travel_time - scheduled_travel_time
                # for calibration, want to take the absolute value
                if abs(delay) > ACCEPTABLE_DELAY_MARGIN:
                # otherwise:
                # if delay > ACCEPTABLE_DELAY_MARGIN:
                    # print('TRAVEL EXCEPTION: {:.2f}min'.format(delay/60))
                    self.delays.append(delay)

        # prepare to depart
        try:
            next_stop = transit_vehicle.route[transit_vehicle.current + 1]
            time_to_dep = cur_stop['dep_sec'] - cur_stop['arr_sec']

            # for tracking travel times
            self.last_deps[transit_vehicle.id] = time + time_to_dep
        except IndexError:
            # trip is done
            return events

        # so we don't double-leave the current edge
        # otherwise we get negative occupancies in roads
        road_vehicle.current = None

        # setup on arrive trigger
        on_arrive = partial(self.on_bus_arrive, road_vehicle, transit_vehicle)

        # figure out road route
        try:
            start, end = cur_stop['stop_id'], next_stop['stop_id']
            if self.cache_routes and (start, end) in self.route_cache:
                route = self.route_cache[(start, end)][:]
            else:
                route = self.transit_roads.route_bus(start, end)
                self.route_cache[(start, end)] = route[:]

            # update route
            road_vehicle.route = route

            # override last event
            events[-1] = (time_to_dep, partial(self.road_next, road_vehicle, on_arrive))
        except NoRoadRouteFound:
            # this seems to occur if the GTFS bus stop lat/lons
            # are inaccurate, so when we map the stop position to
            # a road network position, it maps incorrectly.

            # get inferred stop position on road network
            if self.debug:
                start_pt = (
                    self.transit_roads.stops[start].pt.x,
                    self.transit_roads.stops[start].pt.y)
                end_pt = (
                    self.transit_roads.stops[end].pt.x,
                    self.transit_roads.stops[end].pt.y)
                self.road_route_failures.add(((start_pt, end_pt), (start, end)))
            logger.warn('Ignoring no road route found! (STOP{} -> STOP{}) Falling back to bus schedule.'.format(start, end))

            # as a fallback, just assume the bus arrives on time
            # this is really not ideal, because we pull the bus out of traffic
            # and so it becomes unaffected by congestion, and can't participate
            # in congestion
            scheduled_travel_time = next_stop['arr_sec'] - cur_stop['dep_sec']
            events[-1] = (time_to_dep, lambda time: [(scheduled_travel_time, on_arrive)])

        return events


    def passenger_next(self, passenger, on_arrive, time):
        """action for individual public transit passengers"""
        try:
            leg = passenger.route.pop(0)
        except IndexError:
            logger.debug('[{}] {} Arrived'.format(time, passenger.id))
            return on_arrive(time)

        # setup next action
        action = partial(self.passenger_next, passenger, on_arrive)

        if isinstance(leg, WalkLeg):
            logger.debug('[{}] {} Walking'.format(time, passenger.id))
            rel_time = leg.time
            return [(rel_time, action)]

        elif isinstance(leg, TransferLeg):
            logger.debug('[{}] {} Transferring'.format(time, passenger.id))
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

            logger.debug('[{}] {} Waiting at stop {}'.format(time, passenger.id, dep_stop))
            self.stops[dep_stop][trip_id].append((arr_stop, action))
            return []

    def road_travel(self, path, vehicle_type):
        """travel along road route"""
        # last node in path
        # is destination
        if len(path) < 2:
            return

        leg = path[0]
        if vehicle_type is VehicleType.Public:
            edge = self.transit_roads.network[leg.frm][leg.to][leg.edge_no]
        else:
            edge = self.roads.network[leg.frm][leg.to][leg.edge_no]

        # where leg.p is the proportion of the edge we travel
        time = edge_travel_time(edge) * leg.p

        return leg, edge, time

    def road_next(self, vehicle, on_arrive, time):
        """compute next event in road trip"""
        edge = vehicle.current
        if edge is not None:
            # leave previous edge
            edge['occupancy'] -= 1
            if edge['occupancy'] < 0:
                raise Exception('occupancy should be positive')
            vehicle.route.pop(0)
            self.data['road_capacities'][edge['id']].append((int(edge['occupancy']), float(time)))

        # compute next leg
        leg = self.road_travel(vehicle.route, vehicle.type)

        # arrived
        if leg is None:
            return on_arrive(time)

        # TODO replanning can occur here too,
        # e.g. if travel_time exceeds expected travel time
        leg, edge, travel_time = leg

        # enter edge
        edge['occupancy'] += 1
        if edge['occupancy'] <= 0:
            raise Exception('adding occupant shouldnt make it 0')
        self.data['road_capacities'][edge['id']].append((int(edge['occupancy']), float(time)))

        vehicle.current = edge

        # cast to avoid errors with serializing numpy types
        # self.history[vehicle.id].append((float(time), float(travel_time), leg))

        # return next event
        # TODO this assumes agents don't stop at
        # lights/intersections, so should add in some time,
        # but how much?
        # or will it not affect the model much?
        return [(travel_time, partial(self.road_next, vehicle, on_arrive))]

    def export(self):
        """return simulation run data in a form
        easy to export to JSON for visualization"""
        logger.info('Exporting...')
        trips = []
        for trip in tqdm(self.history.values()):
            # print(len(trip)) # trips are quite long...
            trips.append({
                'vendor': 0,
                'segments': self.roads.segments(trip)
            })

        coords = [(e.pt.x, e.pt.y) for e in self.roads.stops.values()]
        stops = self.roads.to_latlon_bulk(coords)

        return {
            'place': {
                'lat': float(self.roads.place_meta['lat']),
                'lng': float(self.roads.place_meta['lon'])
            },
            'trips': trips,
            'stops': stops
        }
