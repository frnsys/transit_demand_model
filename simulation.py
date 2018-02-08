import networkx as nx
from trip import Trip
from events import EventQueue
from network import TransitNetwork


class Sim():
    def __init__(self, place):
        self.events = EventQueue()
        self.trips = {}
        self.network = TransitNetwork(place)

    def run(self, trips, strict=True):
        """where trips is a dict of {agent_id: (start, end, time)}"""
        # TODO should take into account different modes and so on
        for id, (start, end, time) in trips.items():
            try:
                trip = Trip(id, start, end, self.network.router)
            except nx.exception.NetworkXNoPath:
                if strict:
                    raise
            self.trips[id] = trip
            event = trip.next()
            self.events.push(event)

        # process travel
        next = self.events.pop()
        while next is not None:
            time, action = next
            event = action()
            if event is not None:
                self.events.push(event)
            next = self.events.pop()
