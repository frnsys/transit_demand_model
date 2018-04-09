# Transit demand model prototype
(for PolicySpace)

- discrete event simulation
- includes roads component, using OSM data
    - treat roads (edges) as FIFO queues, which assumes that cars/buses don't pass each other in roads
- includes public transit component, using GTFS data
    - buses will travel via the road network
- support for a map visualization of the output data from a simulation run

## PolicySpace integration

- load actual data
- determine which agents commute
- if they have vehicles, etc
- where they go (i.e. activity schedule)

## Setup

- Install dependencies: `sudo apt install libspatialindex-dev`
- Install requirements: `pip install -r requirements.txt`
- Build `cython` extensions: `python setup.py build_ext --inplace`
- Change config values if desired, in `config.py`
- Run `python main.py`

---

# Known issues

- Routes often cannot be found through the road network. This seems to be an issue with the road network data?
- Need to calibrate road travel times/capacities, so that e.g. buses reaching stops align to their schedule. I believe currently this is causing all buses to be severely delayed.
    - Need to consider `SPEED_FACTOR` in public transit as well

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

