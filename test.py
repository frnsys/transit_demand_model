import logging
from gtfs import Transit
from datetime import datetime
from time import time as TIME

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    transit = Transit('data/gtfs/gtfs_bhtransit.zip')
    # transit = Transit('data/gtfs/gtfs_asheville.zip', 'data/transit/asheville.gz')
    # import ipdb; ipdb.set_trace()

    s = TIME()
    dt = datetime(year=2017, month=2, day=22, hour=10)
    router = transit.router_for_day(dt)
    print('loading router took', TIME() - s)
    # start = '00110998801965'
    # end = '00101153700105'
    s = TIME()
    start = (-19.821486,-43.946748)
    end = (-19.9178,-43.93337)
    route, time = router.route(start, end, dt)
    print('routing took', TIME() - s)
    import ipdb; ipdb.set_trace()


    # import ipdb; ipdb.set_trace()
    #dt = datetime(year=2017, month=2, day=22, hour=4)

    ## 4) [WORKS]
    ## easy, no transfers
    ## start_stop = '00110998800035'
    ## end_stop = '00105955800001'
    #start = (-19.821486,-43.946748)
    #end = (-19.9178,-43.93337)
    #paths = transit.trip_route(start, end, dt)
    #print('paths:', paths)
    ## print('---')

    ## 1) [WORKS]
    #start = (-19.920846733136, -43.8850293374623)
    #end = (-19.9145681320285, -43.8823756325257)
    ##start_stop = '00101991703006' # 2094
    ##end_stop = '00112885800041' # 8828
    ###
    ### expecting something like:
    ### 901   0410800308 # 3608
    ###   00101991703006 (06:04:58) (2094, this happens to be a transfer stop too)
    ###   00112893300056 (06:09:48) (TRANSFER) # 8846
    ### 9208  0120702007 # 3862
    ###   00112893300056 (06:24:01) # 8846
    ###   00112885800041 (06:28:40) # (8828, also happens to be a transfer stop)
    ### start_nodes should include (3608, 2094)
    ### end_nodes should include (3862, 8828)
    ### expected: (3608, 2094) -> ... - > (3608, 8846) -> (3862, 8846) -> ... -> (3862, 8828)
    #paths = transit.trip_route(start, end, dt)
    #print('paths:', paths)
    #print('---')

    ### 2) repeat of 1), except starting on non-transfer stops [WORKS]
    ### 901   0410800308 # 3608
    ## start_stop = '00112884500028' # 8824
    ## end_stop = '00100918800001' # 1026
    #start = (-19.9213988706738, -43.878418788464)
    #end = (-19.9238852702832, -43.8968610758699)
    ## transfer at: 00100918801188 # 1028
    ## first is off network, (3608, 8824), departs 07:03:38)
    ## start nodes should include (3608, 8226)
    ## that has a path to (3608, 1028) , departs at 07:26:34
    ## transfer at that start node to (3752, 1028) (trip 9201  0520701007, 18:00:31)
    ## end at: (3752, 1026) (18:03:50)
    #paths = transit.trip_route(start, end, dt)
    #print('paths:', paths)
    #print('---')

    ### no path was found
    ### TODO manually find path
    ##start_stop = '00103226701049' # 2939
    ##end_stop = '00103205200346' # 2966
    ### start trip: 205   0110700907 # 296
    ##paths = transit.trip_route(start_stop, end_stop, dt)
    ##print('paths:', paths)

    #import ipdb; ipdb.set_trace()
