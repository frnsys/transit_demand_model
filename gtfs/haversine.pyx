from libc.math cimport asin, sin, cos, sqrt, M_PI

cdef double to_radians(double deg):
    return deg * (M_PI/180)

cpdef double haversine(double lat1, double lon1, double lat2, double lon2):
    cdef double km
    lon1, lat1, lon2, lat2 = [
        to_radians(v) for v in
        [lon1, lat1, lon2, lat2]]
    km = 6367 * 2 * asin(sqrt(
        sin((lat2 - lat1)/2)**2 +
        cos(lat1) * cos(lat2) * sin((lon2 - lon1)/2)**2))
    return km
