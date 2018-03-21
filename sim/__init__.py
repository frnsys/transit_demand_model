import logging
from .events import EventQueue
# from .vehicle import Vehicle
from recordclass import recordclass

logger = logging.getLogger(__name__)

Vehicle = recordclass('Vehicle', ['id', 'route', 'passengers', 'current'])
Passenger = recordclass('Passenger', ['id', 'route'])

class Sim():
    def __init__(self, map):
        self.events = EventQueue()
        self.map = map

        # for loading/unloading public transit passengers
        self.stops = {}

    def run(self):
        """process travel;
        - the time in event = (time, action) is relative time, i.e. `time` seconds later.
        - the time we pass into the actions, i.e. `action(time)` is absolute time, i.e. timestamp
        - absolute time is the time we keep track of as the canonical event system time"""
        logger.info('Processing trips...')
        next = self.events.pop()
        while next is not None:
            time, action = next
            new_events = action(time)
            for event in new_events:
                countdown, next_action = event
                next_time = time + countdown
                self.events.push((next_time, next_action))
            next = self.events.pop()

    def queue(self, time, action):
        self.events.push((time, action))

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
