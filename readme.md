# Transit demand model prototype
(for PolicySpace)

- discrete event simulation
- includes roads component, using OSM data
    - treat roads (edges) as FIFO queues, which assumes that cars/buses don't pass each other in roads
- includes public transit component, using GTFS data
    - buses will travel via the road network
- support for a map visualization of the output data from a simulation run

## Setup

- Install requirements: `pip install -r requirements.txt`
- Build `cython` extensions: `python setup.py build_ext --inplace`
- Change config values if desired, in `config.py`

## Running

Run `python main.py <PLACE> <GTFS_PATH> <POLICYSPACE_RUN_OUTPUT_FOLDER> <DATE>`.

Example:

```
python main.py "Belo Horizonte, Brazil" "data/gtfs/gtfs_bhtransit.zip" "/tmp/seal/run__2018-04-22T14_43_51.895867/0" "22/2/2017 10:00"
```

- The `<PLACE>` parameter is for loading in the map and road network data from OpenStreetMap.
- The `<GTFS_PATH>` parameter should point to a [GTFS](https://developers.google.com/transit/gtfs/reference/) zip file for the place of interest.
- The `<POLICYSPACE_RUN_OUTPUT_FOLDER>` should point to the folder where a single [PolicySpace](https://bitbucket.org/furtadobb/policyspace2) run's output data was saved. This folder should contain a `transit` subfolder that contains two files: `start.json` and `end.json`. These contain the necessary agent, firm, and house data to run the transit simulation.
- The `<DATE>` parameter specifies a date to use for the public transit component (e.g. uses the schedule of that day).

Optionally add `--debug` as a flag. This will limit the amount of agents loaded and public transit trips scheduled so the simulation loads and runs faster for debugging purposes.

The transit simulation will be run once for `start.json` and once for `end.json`.

---

# Caveats

- Need to calibrate road travel times/capacities, so that e.g. buses reaching stops align to their schedule. They should be fairly well-calibrated now.
    - If the `--debug` flag is used, the simulation keeps track of bus delays (here "delay" means both arriving late and arriving early) and will warn if the delay is created than `ACCEPTABLE_DELAY_MARGIN`, set in `config.py`.
- The public transit component has trouble routing trips that are near the end-of-day because we don't consider any trips that start after midnight.
- Public transit routing only considers the combinations of the two closest stops to an agent's departure location and the two closest stops to an agent's destination. Ideally we could consider more or have some heuristic for filtering out nearby stops, but considering anymore vastly slows down agent routing time.
- We are currently only considering work commutes.
    - We estimate commute time by assuming average speed of 80km/h and using the point-to-point distance from an agent's home to their firm, then have agents leave to arrive somewhere between 7-9am, based on this estimated commute time.
- Road capacity is estimated by heuristic, see `road/__init__.py`, where `capacity` is set.
- OpenStreetMap data is fairly incomplete, so we are missing speed information about many roads, and try to estimate them based on similar roads. There are `DEFAULT_ROAD_SPEED` configuration options in `config.py` to influence these estimates.
- The GTFS lat, lon of bus stops may not be very accurate, which causes buses to be mapped to incorrect roads. This can cause routing problems. As a fallback, if a route cannot be found between two bus stops, we just use the scheduled travel time.
    - E.g. if the schedule says the bus departs from stop X at 10:00 and arrives at it's next stop Y at 10:15, and we can't find a route through the road network between these stops, we assume it takes 15min to travel between those stops. So if the stop is delayed and arrives at stop X at 10:02, and we just say that the bus will arrive at stop Y at 10:17.
- Footpaths between transit stops are considered just as point-to-point distances, using the `FOOTPATH` related options in `config.py`.
- Road travel time is estimated by rough heuristic based on current occupancy and estimated capacity, see the `edge_travel_time` method in `road/router.py`.

---

# TODO

- Need to schedule agents coming back after work
- Have agents use public transit based on income
- Waiting at intersections

# Enhancements

- conditional re-planning/re-routing at intersections
- route caching (travel habit formation)
- parking time/availability
- random events like accidents

---

# Visualization

## Setup

```
cd viz
npm install -d
```

Then create a file `viz/token.js` with the contents:

```js
const MAPBOX_TOKEN = '<YOUR MAPBOX TOKEN>';

export default MAPBOX_TOKEN;

```

## Run

```
npm start
```

Then visit `localhost:8081`

