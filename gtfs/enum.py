import enum


class ServiceChange(enum.Enum):
    """https://developers.google.com/transit/gtfs/reference/#calendar_datestxt"""
    ADDED   = 1
    REMOVED = 2


class RouteType(enum.Enum):
    """https://developers.google.com/transit/gtfs/reference/#routestxt"""
    TRAM      = '0' # also: streetcar, light rail
    METRO     = '1' # also: subway
    RAIL      = '2'
    BUS       = '3'
    FERRY     = '4'
    CABLE     = '5' # street-level cable car
    GONDOLA   = '6' # suspended cable car
    FUNICULAR = '7' # steep incline rail


class Weekday(enum.Enum):
    MONDAY    = 0
    TUESDAY   = 1
    WEDNESDAY = 2
    THURSDAY  = 3
    FRIDAY    = 4
    SATURDAY  = 5
    SUNDAY    = 6
