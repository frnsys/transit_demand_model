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
