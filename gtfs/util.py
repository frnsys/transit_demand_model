"""
reference:

- <https://developers.google.com/transit/gtfs/reference/>
- <https://developers.google.com/transit/gtfs/examples/gtfs-feed>
- this repo has some functionality, but no py3 support yet: <https://github.com/google/transitfeed>
"""

import zipfile
import pandas as pd
from io import StringIO
from datetime import timedelta
from .haversine import haversine


def load_gtfs(path):
    """load a GTFS zip and return
    as a dictionary with dataframes"""
    zip = zipfile.ZipFile(path, mode='r')
    data = {}
    for f in zip.namelist():
        k = f.replace('.txt', '')
        contents = zip.read(f).decode('utf8')
        data[k] = pd.read_csv(StringIO(contents), dtype={'stop_id': str})
    return data


def walking_time(coord_a, coord_b, delta_base, speed_kmh):
    """Calculate footpath time-delta in seconds between two stops,
    based on their lon/lat distance (using Haversine Formula) and walking-speed constant.
    - `delta_base`: base walking time
    - `speed_kmh`: walking speed in km/h
    adapted from: <https://github.com/mk-fg/trip-based-public-transit-routing-algo/blob/master/tb_routing/gtfs.py#L198>"""
    # Alternative: use UTM coordinates and KDTree (e.g. scipy) or spatial dbs
    # lat, lon ordering
    km = haversine(coord_a[0], coord_a[1], coord_b[0], coord_b[1])
    return delta_base + km / speed_kmh


def gtfs_time_to_secs(time):
    h, m, s = time.split(':')
    return int(s) + (int(m) * 60) + (int(h) * 60 * 60)


def time_to_secs(time):
    return (time.hour * 60 + time.minute) * 60 + time.second


def secs_to_gtfs_time(secs):
    return str(timedelta(seconds=int(secs)))


class IntIndex:
    """two-way positional index"""
    def __init__(self, ids):
        self.id = {}
        self.idx = {}
        for i, id in enumerate(ids):
            self.id[i] = id  # to ids
            self.idx[id] = i # to iids
