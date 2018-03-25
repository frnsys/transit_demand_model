base_transfer_time = 2*60 # lower-bound time-delta overhead for changing trips
footpath_delta_base = 2*60 # footpath_delta = delta_base + km / speed_kmh
footpath_speed_kmh = 5 / 3600
footpath_delta_max = 7*60 # all footpaths longer than that are discarded as invalid
closest_indirect_transfers = 5

# max speed used if one is not specified or one cannot
# be estimated for a road segment
DEFAULT_ROAD_SPEED = 30

# NOTE this needs to be calibrated to the public transit schedule as well
SPEED_FACTOR = 2

# how far around a point to search for
# closest edges.
# this has been adjusted for performance,
# i.e. to find the closest edges
# without looking at too many
BOUND_RADIUS = 0.001
