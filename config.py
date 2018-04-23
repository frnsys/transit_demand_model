# lower-bound time-delta overhead for changing trips
BASE_TRANSFER_TIME = 2*60

# footpath_delta = delta_base + km / speed_kmh
FOOTPATH_DELTA_BASE = 2*60
FOOTPATH_SPEED_KMH = 5 / 3600

# all footpaths longer than that are discarded as invalid
FOOTPATH_DELTA_MAX = 7*60

# generates footpath transfers between this
# amount of nearby transit stops
CLOSEST_INDIRECT_TRANSFERS = 5

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
    'services': 80,

    # according to the OSM wiki (link above),
    # the 'road' value is for an unknown type.
    # defaulting to:
    'road': 60
}

# scale travel speeds by this amount
SPEED_FACTOR = 1

# how much a bus can be delayed (+/-)
# if the delay is greater than this amount,
# and the --debug flag is used,
# then the simulation will log a warning
ACCEPTABLE_DELAY_MARGIN = 5*60

# how far around a point to search for
# closest edges.
# this has been adjusted for performance,
# i.e. to find the closest edges
# without looking at too many
BOUND_RADIUS = 0.001

# +/- 0.61km
# for using zones
GEOHASH_PRECISION = 6

OUTPUT_PATH = '/tmp/seal_transit'
