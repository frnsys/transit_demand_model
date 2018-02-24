from gtfs import Transit
from datetime import datetime

if __name__ == '__main__':
    transit = Transit('data/gtfs/gtfs_bhtransit.zip', 'data/transit/bh.gz')

    dt = datetime(year=2017, month=2, day=27, hour=10)
    start_stop = '00103226701049'
    end_stop = '00103205200346'
    paths = transit.trip_route(start_stop, end_stop, dt)
    print(paths)
