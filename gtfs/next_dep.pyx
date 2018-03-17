# cython: profile=True

from libc.math cimport ceil
import numpy as np
cimport numpy as np

cdef int BASE_TRANSFER_TIME = 120

cdef tuple next_soonest_vehicle(double dep, np.ndarray[np.float32_t, ndim=2] mat):
    # columns: start, period, last_dep
    cdef np.uint64_t idx
    cdef np.ndarray[np.float32_t] starts = mat[:,0]
    cdef np.ndarray[np.float32_t] periods = mat[:,1]
    cdef np.ndarray[np.float32_t] next_veh_idxs
    cdef np.ndarray[np.float32_t] next_veh_times

    # calculate indices and times of next departing vehicles
    next_veh_idxs = np.maximum(0, np.ceil((dep - starts)/periods))
    next_veh_times = starts + (next_veh_idxs * periods)

    # filter out vehicles that have stopped running
    next_veh_times[mat[:,2] < dep] = np.inf

    # get idx of soonest departing vehicle
    idx = np.argmin(next_veh_times)
    return idx, next_veh_times[idx]


cpdef weight(double cur_time, dict valid_stops_spans_mats, tuple v, tuple u, dict e, double d):
    cdef double transfer_time, time, dep_time
    cdef np.uint64_t trip_id
    cdef np.ndarray trips_spans_mat

    # continuing on the same trip,
    # just need transit time between these stops
    if u[0] == v[0]:
        return None, e['time']

    # else, transferring
    transfer_time = e.get('time', BASE_TRANSFER_TIME)

    # note that d is the distance to the node v.
    # current time, including transfer time and transit time
    time = cur_time + d + transfer_time

    # find soonest-departing trip
    # TODO translate returned arr idx to trip id
    trips_spans_mat = valid_stops_spans_mats[u]
    if not trips_spans_mat.size:
        return None, float('inf')

    trip_id, dep_time = next_soonest_vehicle(time, trips_spans_mat)
    return trip_id, dep_time - (time - transfer_time)

