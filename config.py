base_transfer_time = 2*60 # lower-bound time-delta overhead for changing trips
footpath_delta_base = 2*60 # footpath_delta = delta_base + km / speed_kmh
footpath_speed_kmh = 5 / 3600
footpath_delta_max = 7*60 # all footpaths longer than that are discarded as invalid
closest_indirect_transfers = 5

# max speed used if one is not specified or one cannot
# be estimated for a road segment
# https://wiki.openstreetmap.org/wiki/Key:highway
# https://en.wikivoyage.org/wiki/Driving_in_Brazil
# TODO get better values
DEFAULT_ROAD_SPEEDS = {
    'disused': 0,
    'living_street': 30,
    'residential': 30,
    'motorway': 110,
    'primary': 110,
    'trunk': 110,
    'secondary': 80,
    'tertiary': 60,

    # according to the OSM wiki (link above),
    # the 'road' value is for an unknown type.
    # defaulting to:
    'road': 60
}

SPEED_FACTOR = 1

# how far around a point to search for
# closest edges.
# this has been adjusted for performance,
# i.e. to find the closest edges
# without looking at too many
BOUND_RADIUS = 0.001

# +/- 0.61km
GEOHASH_PRECISION = 6
