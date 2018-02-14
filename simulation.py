import networkx as nx
from trip import Trip
from events import EventQueue


class Sim():
    def __init__(self, map):
        self.events = EventQueue()
        self.map = map
        self.trips = {}

    def run(self, trips, strict=True):
        """where trips is a dict of {agent_id: (start, end, time)}"""
        # TODO should take into account different modes and so on
        for id, (start, end, time) in trips.items():
            if start == end:
                continue
            try:
                trip = Trip(id, start, end, self.map.router)
                self.trips[id] = trip
                event = trip.next()
                self.events.push(event)
            except nx.exception.NetworkXNoPath:
                if strict:
                    raise

        # process travel
        next = self.events.pop()
        while next is not None:
            time, action = next
            event = action()
            if event is not None:
                self.events.push(event)
            next = self.events.pop()

    def export(self):
        """return simulation run data in a form
        easy to export to JSON for visualization"""
        trips = []
        for trip in self.trips.values():
            trips.append({
                'vendor': 0,
                'segments': trip.segments(self.map)
            })

        bus_stops = [s['coord'] for s in self.map.bus_stops.values()]

        return {
            'place': {
                'lat': float(self.network.place_meta['lat']),
                'lng': float(self.network.place_meta['lon'])
            },
            'trips': trips,
            'bus_stops': bus_stops
        }
