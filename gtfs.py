"""
reference:

- <https://developers.google.com/transit/gtfs/reference/>
- <https://developers.google.com/transit/gtfs/examples/gtfs-feed>
- this repo has some functionality, but no py3 support yet: <https://github.com/google/transitfeed>
"""

import zipfile
import pandas as pd
from io import StringIO

path = 'gtfs/gtfs_bhtransit.zip'


def load_gtfs(path):
    """load a GTFS zip and return
    as a dictionary with dataframes"""
    zip = zipfile.ZipFile(path, mode='r')
    data = {}
    for f in zip.namelist():
        k = f.strip('.txt')
        contents = zip.read(f).decode('utf8')
        data[k] = pd.read_csv(StringIO(contents))
    return data


gtfs = load_gtfs(path)
stops = [(r.stop_lat, r.stop_lon) for i, r in gtfs['stops'].iterrows()]
