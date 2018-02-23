# Transit demand model prototype
(for PolicySpace)

- treat roads (edges) as FIFO queues, which assumes that cars don't pass each other in roads
    - we can maybe find ways to remove this assumption by introducing individual variability in edge travel time
- edge (road) properties:
    - length
    - capacity
    - free-flow speed
    - occupancy (how many vehicles are on the road)

## Next steps

- bus networks
- support other public transit options which operate on independent networks (e.g. subways)
- conditional re-planning/re-routing at intersections
- refined travel time estimation
- route caching (travel habit formation)
- parking time/availability
- random events like accidents

## PolicySpace integration

- load actual data
- determine which agents commute
- if they have vehicles, etc
- where they go (i.e. activity schedule)

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


---

# graph-tool installation

download release from <https://git.skewed.de/count0/graph-tool/tags>

```
sudo apt install libcgal-dev libexpat1-dev libsparsehash-dev libcairomm-1.0-dev python3-cairo-dev
# activate your virtualenv
./autogen.sh
./configure --prefix=$HOME/.local
make install
```

also:

```
pip install pycairo
```

reference: <https://git.skewed.de/count0/graph-tool/wikis/installation-instructions#manual-compilation>
