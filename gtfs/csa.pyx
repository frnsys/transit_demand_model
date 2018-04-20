# distutils: language=c++
# TODO: Multicritera CSA (mcCSA)
# CSA: <http://i11www.iti.kit.edu/extra/publications/dpsw-isftr-13.pdf>
# Reference implementation: <https://github.com/dbsystel/practical-csa/tree/master/src/main/scala/algorithm>

from libcpp cimport bool
from libcpp.vector cimport vector
from libcpp.map cimport map
from numpy.math cimport INFINITY
from cython.parallel import prange

ctypedef unsigned int Stop

ctypedef enum ConnectionType:
    empty, trip, foot

ctypedef struct Connection:
    Stop dep_stop
    double dep_time
    Stop arr_stop
    double arr_time
    ConnectionType type
    int trip_id

ctypedef struct Footpath:
    Stop dep_stop
    Stop arr_stop
    double time

ctypedef struct Route:
    vector[Connection] path
    double time

cdef double BASE_TRANSFER_TIME = 120

cdef class CSA:
    cdef:
        int n_stops
        Connection no_connection
        vector[Connection] connections
        vector[vector[Footpath]] footpaths

    def __init__(self, list connections, dict footpaths):
        # NOTE: this assumes that connections is sorted by dep time, ascending
        self.n_stops = 0
        self.connections.reserve(len(connections))
        for i, con in enumerate(connections):
            if con['dep_stop'] > self.n_stops:
                self.n_stops = con['dep_stop']
            if con['arr_stop'] > self.n_stops:
                self.n_stops = con['arr_stop']
            con['type'] = ConnectionType.trip
            self.connections.push_back(con)
        self.n_stops += 1

        self.footpaths.reserve(len(footpaths))
        self.footpaths.assign(len(footpaths), [])
        for stop, fps in footpaths.items():
            self.footpaths[stop] = fps

        self.no_connection.type = ConnectionType.empty

    @property
    def n_connections(self):
        return self.connections.size()

    cdef Route route(self, unsigned int start, unsigned int end, double dep_time, double walk_time) nogil:
        cdef:
            Route route = make_route()
            vector[Connection] in_connections
            vector[Connection] path

        in_connections = self._route(start, end, dep_time)

        if in_connections.empty():
            return route

        # NOTE this route is backward
        path = build_route(start, end, in_connections)
        route.path = path
        route.time = path[0].arr_time - dep_time + walk_time
        return route

    cdef vector[Connection] _route(self, unsigned int start, unsigned int end, double dep_time) nogil:
        cdef:
            int in_idx
            Connection c
            vector[Connection] in_connections
            vector[double] earliest_arrivals
            double earliest = INFINITY

        # initialize vectors
        in_connections.assign(self.n_stops, self.no_connection)
        earliest_arrivals.assign(self.n_stops, INFINITY)
        earliest_arrivals[start] = dep_time

        for c in self.connections:
            # skip connections departing before our departure time
            if c.dep_time < dep_time: continue

            # check if c is reachable given current connections,
            # and if so, check if it improves current arrival times
            if is_reachable(c, start, earliest_arrivals[c.dep_stop], in_connections[c.dep_stop]) \
                and c.arr_time < earliest_arrivals[c.arr_stop]:
                in_connections[c.arr_stop] = c
                earliest_arrivals[c.arr_stop] = c.arr_time
                expand_footpaths(c, self.footpaths[c.arr_stop], in_connections)
                if c.arr_stop == end:
                    earliest = min(earliest, c.arr_time)

            # if this connection arrives after our best so far, we're done
            elif c.arr_time > earliest:
                break

        if earliest_arrivals[end] == INFINITY:
            in_connections.clear()

        return in_connections

    cpdef Route route_many(self, vector[unsigned int] starts, vector[unsigned int] ends, vector[double] dep_times, vector[double] walk_times):
        cdef:
            int i
            unsigned int j
            unsigned int n = starts.size()
            vector[Route] routes
            double best_time = INFINITY
            Route best_route

        # NOTE these routes are expected to be backwards
        routes.assign(n, make_route())
        for i in prange(n, nogil=True):
            routes[i] = self.route(starts[i], ends[i], dep_times[i], walk_times[i])

        for j in range(routes.size()):
            if routes[i].time < best_time:
                best_time = routes[i].time
                best_route = routes[i]

        return best_route


cdef vector[Connection] build_route(unsigned int start, unsigned int end, vector[Connection] in_connections) nogil:
    # build out the route to return
    # consisting of only start, end, and transfer connections
    cdef:
        vector[Connection] route
        Connection c = in_connections[end]

    route.push_back(c)
    while c.dep_stop != start:
        next_c = in_connections[c.dep_stop]
        if c.type != next_c.type or c.trip_id != next_c.trip_id:
            route.push_back(c)
        c = next_c
    route.push_back(c)

    # reverse order
    # return route[::-1]
    # TODO
    # NOTE this route is backward
    return route

# https://github.com/cython/cython/issues/1642
cdef Connection make_connection(
    Stop dep_stop,
    double dep_time,
    Stop arr_stop,
    double arr_time,
    ConnectionType type,
    int trip_id
) nogil:
    cdef Connection c
    c.dep_stop = dep_stop
    c.dep_time = dep_time
    c.arr_stop = arr_stop
    c.arr_time = arr_time
    c.type = type
    c.trip_id = trip_id
    return c

cdef Route make_route() nogil:
    cdef Route r
    r.time = INFINITY
    return r

cdef void expand_footpaths(Connection c, vector[Footpath] footpaths, vector[Connection] in_connections) nogil:
    # scan outgoing footpaths from the arrival stop
    # note: path.dep_stop == con.arr_stop
    cdef:
        Footpath path
        Connection best_con
    for path in footpaths:
        # find existing best connection coming into the footpath's arrival stop
        # to see if this footpath gets there faster than it
        best_con = in_connections[path.arr_stop]
        if best_con.type == ConnectionType.empty or c.arr_time + path.time < best_con.arr_time:
            in_connections[path.arr_stop] = make_connection(
                path.dep_stop,
                c.arr_time,
                path.arr_stop,
                c.arr_time + path.time,
                ConnectionType.foot,
                -1,
            )


cdef bool is_reachable(Connection c, unsigned int start, double earliest_arrival, Connection in_con) nogil:
    # connection c is reachable if:
    # (it departs from our starting stop OR the best connection to c's
    #   departing stop connects to this connection) AND
    #   it departs at or after our earliest arrival to c's departure stop (that
    #   is, we arrive to the stop before the connection departs)
    return c.dep_time >= earliest_arrival and (c.dep_stop == start or connects(in_con, c))


cdef bool connects(Connection in_con, Connection c) nogil:
    # if this is a trip connection, we can reach the trip if either:
    # - c is on the same trip as the incoming connection
    # - we can transfer to c in time
    if in_con.type == ConnectionType.trip:
        return (in_con.trip_id == c.trip_id \
            or in_con.arr_time <= c.dep_time - BASE_TRANSFER_TIME)

    # if this a foot connection, we just have to check
    # that we arrive before connection c departs
    elif in_con.type == ConnectionType.foot:
        return in_con.arr_time <= c.dep_time

    # if we don't have an incoming connection to c, there's no connection
    return False
