import logging
from tqdm import tqdm
from .events import EventQueue

logger = logging.getLogger(__name__)

class Sim():
    def __init__(self):
        self.events = EventQueue()

    def run(self):
        """process travel;
        - the time in event = (time, action) is relative time, i.e. `time` seconds later.
        - the time we pass into the actions, i.e. `action(time)` is absolute time, i.e. timestamp
        - absolute time is the time we keep track of as the canonical event system time"""
        logger.info('Processing trips...')
        next = self.events.pop()
        with tqdm() as pbar:
            while next is not None:
                time, action = next
                new_events = action(time)
                pbar.update()
                for event in new_events:
                    countdown, next_action = event
                    next_time = time + countdown
                    self.events.push((next_time, next_action))
                next = self.events.pop()

    def queue(self, time, action):
        self.events.push((time, action))
