import unittest
import pandas as pd
from gtfs import util
from io import StringIO
from datetime import time

freq_data = '''
trip_id,start_time,end_time,headway_secs
METRO 0110100101,05:00:00,05:59:59,1200
METRO 0110100101,06:00:00,06:59:59,900
METRO 0110100101,07:00:00,07:59:59,900
METRO 0110100101,08:00:00,08:59:59,900
METRO 0110100101,09:00:00,09:59:59,900
METRO 0110100101,10:00:00,10:59:59,900
METRO 0110100101,11:00:00,11:59:59,900
METRO 0110100101,12:00:00,12:59:59,900
METRO 0110100101,13:00:00,13:59:59,900
METRO 0110100101,14:00:00,14:59:59,900
METRO 0110100101,15:00:00,15:59:59,900
METRO 0110100101,16:00:00,16:59:59,900
METRO 0110100101,17:00:00,17:59:59,900
METRO 0110100101,18:00:00,18:59:59,900
METRO 0110100101,19:00:00,19:59:59,900
METRO 0110100101,20:00:00,20:59:59,900
METRO 0110100101,21:00:00,21:59:59,900
METRO 0110100101,22:00:00,22:59:59,900
METRO 0110100101,23:00:00,23:59:59,3600
METRO 0110700107,05:00:00,05:59:59,900
METRO 0110700107,06:00:00,06:59:59,720
METRO 0110700107,07:00:00,07:59:59,720
METRO 0110700107,08:00:00,08:59:59,720
METRO 0110700107,09:00:00,09:59:59,720
METRO 0110700107,10:00:00,10:59:59,720
METRO 0110700107,11:00:00,11:59:59,720
METRO 0110700107,12:00:00,12:59:59,720
METRO 0110700107,13:00:00,13:59:59,1800
METRO 0110700107,14:00:00,14:59:59,900
METRO 0110700107,15:00:00,15:59:59,900
METRO 0110700107,16:00:00,16:59:59,900
METRO 0110700107,17:00:00,17:59:59,900
METRO 0110700107,18:00:00,18:59:59,900
METRO 0110700107,19:00:00,19:59:59,900
METRO 0110700107,20:00:00,20:59:59,900
METRO 0110700107,21:00:00,21:59:59,900
METRO 0110700107,22:00:00,22:59:59,900
METRO 0110700107,23:00:00,23:59:59,3600
'''


class Tests(unittest.TestCase):
    def test_compress_frequencies(self):
        freqs = pd.read_csv(StringIO(freq_data))
        freqs = util.compress_frequencies(freqs)

        group = freqs['METRO 0110100101']
        self.assertEqual(len(group), 3)
        self.assertEqual(util.secs_to_gtfs_time(group[0]['start']), '5:00:00')
        self.assertEqual(util.secs_to_gtfs_time(group[0]['end']), '5:59:59')
        self.assertEqual(util.secs_to_gtfs_time(group[1]['start']), '6:00:00')
        self.assertEqual(util.secs_to_gtfs_time(group[1]['end']), '22:59:59')
        self.assertEqual(util.secs_to_gtfs_time(group[2]['start']), '23:00:00')
        self.assertEqual(util.secs_to_gtfs_time(group[2]['end']), '23:59:59')

    def test_next_vehicle_dep(self):
        # we're leaving at 7:20:00
        dep_time = util.time_to_secs(time(hour=7, minute=20))

        # the trip span starts at 5:00:00
        trip_span_start = util.time_to_secs(time(hour=5, minute=0))

        # the top we want departs 45min into each vehicle
        stop_dep_relative = util.time_to_secs(time(minute=45))

        # new vehicles depart every 10 minutes
        headway = util.time_to_secs(time(minute=10))

        next_dep_time = util.next_vehicle_dep(dep_time, trip_span_start, stop_dep_relative, headway)
        self.assertEqual(util.secs_to_gtfs_time(next_dep_time), '7:25:00')

    def test_n_vehicles(self):
        freq = {
            'start': 0,
            'end': 999,
            'period': 10
        }
        n_vehicles = util.n_vehicles(freq)
        self.assertEqual(n_vehicles, 100)

    def test_transfer_possible_false(self):
        freqs_from = [{
            'start': 1000,
            'end': 1999,
            'period': 10
        }]
        freqs_to = [{
            'start': 0,
            'end': 299,
            'period': 10
        }]

        # impossible b/c the TO trip stops running
        # before the FROM trip starts arriving
        p = util.transfer_possible(freqs_from, freqs_to, wait_time=0, transfer_time=0)
        self.assertFalse(p)

    def test_transfer_possible_true(self):
        freqs_from = [{
            'start': 1000,
            'end': 1999,
            'period': 10
        }]
        freqs_to = [{
            'start': 2000,
            'end': 2999,
            'period': 10
        }]
        p = util.transfer_possible(freqs_from, freqs_to, wait_time=0, transfer_time=0)
        self.assertTrue(p)

    def test_transfer_possible_wait_time(self):
        freqs_from = [{
            'start': 1000,
            'end': 1999,
            'period': 10
        }]
        freqs_to = [{
            'start': 0,
            'end': 999,
            'period': 10
        }]

        # assuming FROM vehicles arrive 120s before they depart,
        # so even though the TO trip stops running before the FROM trip starts
        # running, the first FROM vehicle arrives in time to catch the last TO
        # vehicle
        p = util.transfer_possible(freqs_from, freqs_to, wait_time=120, transfer_time=0)
        self.assertTrue(p)

        # if there was no wait time, then the FROM vehicle arrives after the TO
        # trip stops running
        p = util.transfer_possible(freqs_from, freqs_to, wait_time=0, transfer_time=0)
        self.assertFalse(p)

    def test_transfer_possible_transfer_time(self):
        freqs_from = [{
            'start': 1000,
            'end': 1999,
            'period': 10
        }]
        freqs_to = [{
            'start': 0,
            'end': 1119,
            'period': 10
        }]

        # if there is transfer time, this means we need the TO trip
        # to stop running later to accomodate for this transfer time
        p = util.transfer_possible(freqs_from, freqs_to, wait_time=0, transfer_time=120)
        self.assertFalse(p)

        # with no transfer time, it's possible to make the last transfer
        p = util.transfer_possible(freqs_from, freqs_to, wait_time=0, transfer_time=0)
        self.assertTrue(p)

        # or, if the TO trip stops running later, then it's possible as well
        freqs_to[0]['end'] = 1139
        p = util.transfer_possible(freqs_from, freqs_to, wait_time=0, transfer_time=120)
        self.assertTrue(p)
