from libcpp cimport bool
from libcpp.vector cimport vector
from libcpp.map cimport map
from numpy.math cimport INFINITY

ctypedef unsigned int Stop

ctypedef enum ConnectionType:
    empty, trip, foot

ctypedef struct Connection:
    unsigned int id
    double dep_time
    Stop dep_stop
    double arr_time
    Stop arr_stop
    unsigned int trip_id
    ConnectionType type

ctypedef struct Footpath:
    Stop dep_stop
    Stop arr_stop
    double time

cdef double BASE_TRANSFER_TIME = 120

cdef class CSA:
    cdef:
        map[Stop, vector[Footpath]] footpaths
        vector[Connection] connections
        int max_stop

    def __init__(self, list connections, dict footpaths):
        # TODO assumes that connections is sorted by dep time, ascending
        self.max_stop = 0
        for i, con in enumerate(connections):
            if con['dep_stop'] > self.max_stop:
                self.max_stop = con['dep_stop']
            if con['arr_stop'] > self.max_stop:
                self.max_stop = con['arr_stop']
            con['type'] = ConnectionType.trip
            con['id'] = i
            self.connections.push_back(con)

        for stop, fps in footpaths.items():
            [self.footpaths[stop].push_back(fp) for fp in fps]

    # def n_connections(self):
    #     return self.connections.size()

    cpdef route(self, unsigned int start, unsigned int end, double dep_time):
        cdef:
            int in_idx
            Connection c
            vector[int] in_connection
            vector[double] earliest_arrival
            double earliest = INFINITY
            list route = []
            Connection dummy

        dummy.type = ConnectionType.empty

        # initialize vectors
        in_connection.assign(self.max_stop, -1)
        earliest_arrival.assign(self.max_stop, INFINITY)
        earliest_arrival[start] = dep_time

        for c in self.connections:
            # skip connections departing before our departure time
            if c.dep_time < dep_time: continue

            in_idx = in_connection[c.dep_stop]
            in_con = dummy if in_idx < 0 else self.connections[in_idx]
            if is_reachable(c, start, earliest_arrival[c.dep_stop], in_con) and c.arr_time < earliest_arrival[c.arr_stop]:
                in_connection[c.arr_stop] = c.id
                earliest_arrival[c.arr_stop] = c.arr_time
                # expand_footpaths(c, footpaths, stop_incoming)
                if c.arr_stop == end:
                    earliest = min(earliest, c.arr_time)
            elif c.arr_time > earliest:
                break

        c = self.connections[in_connection[end]]
        while c.dep_stop != start:
            route.append(c)
            c = self.connections[in_connection[c.dep_stop]]

        # return route reversed (i.e. in proper order)
        return route[::-1]
        # return reversed(route) # TODO does this work?
        # return in_connection


cdef bool is_reachable(Connection c, unsigned int start, double earliest_arrival, Connection in_con):
    return c.dep_time >= earliest_arrival and (c.dep_stop == start or connects(in_con, c))

cdef bool connects(Connection in_con, Connection c):
    if in_con.type == ConnectionType.trip:
        return (in_con.trip_id == c.trip_id \
            or in_con.arr_time <= c.dep_time - BASE_TRANSFER_TIME)
    elif in_con.type == ConnectionType.foot:
        return in_con.arr_time <= c.dep_time
    return False


# def expand_footpaths(con, footpaths, stop_incoming):
#     # scan outgoing footpaths from the arrival stop
#     # note: path.dep_stop == con.arr_stop
#     paths = footpaths[con.arr_stop]
#     for path in paths:
#         # find existing best connection coming into the footpath's arrival stop
#         # to see if this footpath gets there faster than it
#         best = stop_incoming.get(path.arr_stop)
#         if best is None or con.arr_time + path.time < best.arr_time:
#             stop_incoming[path.arr_stop] = FootConnection(
#                 dep_stop=path.dep_stop,
#                 arr_stop=path.arr_stop,
#                 dep_time=con.arr_time,
#                 arr_time=con.arr_time + path.time
#             )



