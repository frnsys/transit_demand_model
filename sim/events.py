import uuid
import heapq


class EventQueue():
    """a heap-based priority queue
    for discrete event simulation.
    A thin wrapper around Python's heapq,
    keeping event actions separate so that
    the heap can accept items with the same
    priority."""
    def __init__(self):
        self.heap = []
        self.actions = {}

    def push(self, event):
        time, action = event

        key = uuid.uuid4().hex
        if key in self.actions:
            raise KeyError('Action key already exists')
        self.actions[key] = action

        event = (time, key)
        heapq.heappush(self.heap, event)

    def pop(self):
        try:
            time, key = heapq.heappop(self.heap)
        except IndexError:
            return None
        event = time, self.actions[key]
        del self.actions[key]
        return event
