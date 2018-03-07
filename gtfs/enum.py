import enum


class RouteType(enum.Enum):
    """https://developers.google.com/transit/gtfs/reference/#routestxt"""
    TRAM      = 0 # also: streetcar, light rail
    METRO     = 1 # also: subway
    RAIL      = 2
    BUS       = 3
    FERRY     = 4
    CABLE     = 5 # street-level cable car
    GONDOLA   = 6 # suspended cable car
    FUNICULAR = 7 # steep incline rail


class MoveType(enum.Enum):
    WALK = 0
    RIDE = 1
