from collections import defaultdict, namedtuple

Connection = namedtuple('Connection', ['dep_time', 'dep_stop', 'arr_time', 'arr_stop', 'trip_id'])

BASE_TRANSFER_TIME = 120

def binary_search(cons, dep_time):
    lo, hi = 0, len(cons)
    while lo < hi:
        mid = (lo+hi)//2
        cmpval = cons[mid].dep_time - dep_time
        if cmpval < 0:
            lo = mid+1
        elif cmpval > 0:
            hi = mid
        else:
            # b/c there may be duplicate entries,
            # find the first one
            while cons[mid-1].dep_time == dep_time:
                mid -= 1
            return mid
    return -1

def csa(connections, start, end, dep_time):
    # keep track of earliest incoming connection to a stop
    stop_incoming = {}

    # keep track of earliest arrivals to each stop
    earliest_arrivals = defaultdict(lambda: float('inf'))
    earliest_arrivals[start] = dep_time

    # binary search seems slower?
    # could have to do with the slice operation?
    # start_idx = binary_search(connections, dep_time)
    # for c in connections[start_idx:]:
    for c in connections:
        # skip connections departing before our departure time
        if c.dep_time < dep_time: continue
        ok = c.dep_stop == start
        in_con = stop_incoming.get(c.dep_stop)
        if (ok or connects(in_con, c)) and is_reachable(c, earliest_arrivals):
            earliest_arrivals[c.arr_stop] = c.arr_time
            stop_incoming[c.arr_stop] = c
        elif c.arr_time > earliest_arrivals[end]:
            break

    # build route
    route = []
    c = stop_incoming[end]
    while c.dep_stop != start:
        route.append(c)
        c = stop_incoming[c.dep_stop]
    return list(reversed(route))


def connects(in_con, out_con):
    return in_con is not None and \
        (in_con.trip_id == out_con.trip_id \
        or in_con.arr_time <= out_con.dep_time - BASE_TRANSFER_TIME)


def is_reachable(c, earliest_arrivals):
    # if departing after our earliest arrival to the departing stop
    # and arriving before the earliest arrival to the arrival stop
    return c.dep_time >= earliest_arrivals[c.dep_stop] \
        and c.arr_time < earliest_arrivals[c.arr_stop]