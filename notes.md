only direct:
before: 7944042
after 7401194

only indirect:
before: 16515605
after: 15749147

total
before: 24459647
after: 23150341

(note this roughly doubles processing time)
after connecting only to the soonest stop sequence id, only direct: 1507381
after connecting only to the soonest stop sequence id, only indirect: 3182167
total: 4689548

when using (trip_id, stop_id) nodes instead of just trip_id nodes:
only direct: 1507381 (nodes: 215383)
both: 4689548 (nodes: 239667)

with trip links: 4923011

with closest_indirect_transfers=8, rather than 3: 9541190

---

times:
TOOK: 0.004011392593383789
TOOK: 0.002736806869506836
TOOK: 76.94536232948303
TOOK: 415.93137073516846

after:
TOOK: 0.00402069091796875
TOOK: 0.0025954246520996094
TOOK: 0.04661273956298828
TOOK: 1.2811040878295898

---

START NODES: [((3608, 8824), 0), ((4150, 8824), 0)]
END NODES: [((3753, 1026), 0), ((3754, 1026), 0), ((3757, 1026), 0), ((3758, 1026), 0), ((3759, 1026), 0), ((3760, 1026), 0), ((3761, 1026), 0), ((3762, 1026), 0), ((3763, 1026), 0), ((3764, 1026), 0), ((3765, 1026), 0), ((3766, 1026), 0), ((3769, 1026), 0), ((3770, 1026), 0), ((3771, 1026), 0), ((3772, 1026), 0), ((3773, 1026), 0), ((3774, 1026), 0)]
n start: 2
n end: 18                                                                                                                            paths: [(4150, 8824), (4149, 8836), (4149, 2098), (4149, 2096), (4149, 2095), (4149, 2093), (4149, 2091), (4149, 7665), (4149, 6048), (4149, 6046), (4149, 6419), (4149, 6416), (4149, 3608), (3766, 3607), (3766, 3609), (3766, 3611), (3766, 1028), (3766, 1026)]
TOOK: 0.04579949378967285
---
START NODES: [((4414, 1401), 370), ((299, 2966), 0), ((4404, 2966), 0), ((4409, 2966), 0)]
END NODES: [((2048, 2939), 0), ((2050, 2939), 0), ((2051, 2939), 0), ((2052, 2939), 0), ((2053, 2939), 0), ((2055, 2939), 0), ((2057, 2939), 0), ((2058, 2939), 0), ((2059, 2939), 0), ((2060, 2939), 0), ((2062, 2569), 483), ((2064, 2569), 483), ((2065, 2569), 483), ((2066, 2569), 483), ((2067, 2569), 483), ((2068, 2939), 0), ((2070, 2939), 0), ((2071, 2939), 0), ((2102, 2939), 0), ((2104, 2939), 0), ((2105,
2939), 0), ((2106, 2939), 0), ((2107, 2939), 0), ((3406, 2939), 0), ((3408, 2939), 0), ((3409, 2939), 0), ((3410, 2939), 0), ((3411,
2939), 0), ((3414, 2939), 0), ((3416, 2939), 0), ((3417, 2939), 0), ((3418, 2939), 0), ((3419, 2939), 0), ((3421, 2939), 0), ((3423,
2939), 0), ((3424, 2939), 0), ((3433, 2939), 0), ((3435, 2939), 0), ((3436, 2939), 0), ((3437, 2939), 0)]
n start: 4
n end: 40
paths: [(4404, 2966), (417, 4827), (417, 4825), (417, 4823), (417, 4821), (417, 4819), (417, 2189), (417, 4590), (417, 829), (4680, 975), (4641, 1819), (4641, 1820), (4641, 1821), (4641, 1823), (4641, 1824), (4641, 1828), (32, 1830), (3629, 1831), (4389, 8), (4389,
15), (4389, 1), (4389, 14), (4389, 2), (4389, 16), (4389, 12), (3433, 2995), (3433, 1435), (3433, 1437), (3433, 1439), (3433, 1440),
(3433, 2576), (3433, 2573), (3433, 2572), (2065, 2569)]

---

going from trip ids to stop seqs:
[01:58<00:00, 79.23it/s] -> [00:16<00:00, 559.91it/s] (~7x faster)
13,213,695 direct edges -> 385,454 direct edges (~34x less)

when checking for overlapping service days before making a direct edge, we go from
385,454 -> 345,073

got indirect edges: 1,200,062

total of: 1,545,135 edges

with the graph created, we have:
- nodes: 41,627
- edges: 1,544,241 (assuming some edges are duplicates?)

after linking nodes belong to the same stop seq, edge count is: 1,585,551

note sure what changes this, but edge count is now 1,555,853
number of nodes is still 41,627
the density of this graph is very low, `nx.density(G)` yields 0.0008979016480904062
`(n_edges/n_nodes**2)`

---

dictionary access:
   796    889567    1295858.0      1.5     16.0              cost = weight(v, u, e)

custom weight function:
   257    390733   84587843.0    216.5     97.0              _, cost = weight(v, u, e, dists[v])

   266    390713   77938748.0    199.5     96.6              _, cost = weight(v, u, e, dists[v])

   254    390733   44812532.0    114.7     94.7              _, cost = weight(v, u, e, dists[v])

   265    390733   32504436.0     83.2     92.3              _, cost = weight(v, u, e, dists[v])

FROM HERE ON it's called more, need to debug that

   263    492217   37757736.0     76.7     92.8              _, cost = weight(v, u, e, dists[v]) # but it got called more?

   261    492217   17826383.0     36.2     87.2              _, cost = weight(v, u, e, dists[v]) # much faster, still getting called more?

   262    492217   10265490.0     20.9     79.6              _, cost = weight(v, u, e, dists[v]) # after compiling with cython, no changes to code

   265    581906   10400017.0     17.9     76.8              _, cost = weight(v, u, e, dists[v]) # with some type delcarations, getting called more still?


   265    581787    8079353.0     13.9     72.6              _, cost = weight(v, u, e, dists[v]) # with some more type declarations. also getting called more, no idea why...


   265    581787   10030225.0     17.2     76.9              _, cost = weight(v, u, e, dists[v]) # after more type defs and some changes, slowed?

   265    581787    9165889.0     15.8     75.5              _, cost = weight(v, u, e, dists[v]) # changing some checking around

   265    581787    9985432.0     17.2     77.0              _, cost = weight(v, u, e, dists[v])

   265    226005    3477272.0     15.4     75.3              _, cost = weight(v, u, e, dists[v]) # fixed issue where was mistakenly not considering still-running rather than no-longer-running vehicles

removing indirect transfers does not significantly decrease weight calls (n nodes: 39,065, n edges: 376,641):

   265    189987    3062388.0     16.1     71.8              _, cost = weight(v, u, e, dists[v])


pretty wide range of routing times at this point, from 0.19s to 25s

963 ns ± 5.64 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)

no python changes, compiled
601 ns ± 6.27 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)

using libc.math.ceil instead of math.ceil
597 ns ± 3.98 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)

with type declarations
325 ns ± 18.7 ns per loop (mean ± std. dev. of 7 runs, 1000000 loops each)

using numpy to operate on the full matrix
8.05 µs ± 49.4 ns per loop (mean ± std. dev. of 7 runs, 100000 loops each)
(~8000 nanoseconds on 24 entries roughly 333ns per entry, and time doesn't grow much with matrix size)


   223   7633538   22125527.0      2.9     44.7              next = util.next_vehicle_dep(time, span)

   226   7633288   10490449.0      1.4     25.7              next = next_vehicle_dep(time, span.start, span.last_dep, span.period)

   214    382393     424151.0      1.1      1.0      trips_spans = {tid: spans for tid, spans
   215    382393    2932721.0      7.7      7.2                     in stops_spans[to_stop][to_stop_seq].items()
   216                                                              if tid in valid_trips}

see if we can reduce calls to next_vehicle_dep



228    382412    7302541.0     19.1     29.1      all_spans = sum(([s for s in v if time < s.last_dep] for v in trips_spans.values()), [])
229    382412     421135.0      1.1      1.7      if not all_spans:
230    105445     216015.0      2.0      0.9          return None, float('inf')
231
232    276967    6316939.0     22.8     25.2      all_spans_mat = np.array([[s.start, s.period] for s in all_spans])
233                                               # TODO translate returned arr idx to trip id
234    276967    6937146.0     25.0     27.7      trip_id, dep_time = next_soonest_vehicle(time, all_spans_mat)



5503A 0211000910
5503A 0210806008
5503A 0211400814

route_id, service_id, trip_id
5503A 02,10,5503A 0211000910,Goiania A (Principal) - Dia Util-Ferias De Julho,0,,
5503A 02,08,5503A 0210806008,Goiania A (Principal) - Dia Util,0,,
5503A 02,14,5503A 0211400814,Goiania A (Principal) - Dia Util-Ferias De Verao,0,,

5503A 0211000910,04:30:00,04:30:00,00109588100160,00100010,,0,0,
5503A 0211000910,04:32:47,04:32:47,00105649000110,00100011,,0,0,
5503A 0211000910,04:33:49,04:33:49,00105010600700,00100012,,0,0,
5503A 0211000910,04:34:41,04:34:41,00102023200363,00100013,,0,0,
5503A 0211000910,04:35:17,04:35:17,00102023200107,00100014,,0,0,
5503A 0211000910,04:35:50,04:35:50,00103205201312,00100015,,0,0,
5503A 0211000910,04:36:29,04:36:29,00103205201386,00100016,,0,0,
5503A 0211000910,04:37:06,04:37:06,00103205200131,00100017,,0,0,
5503A 0211000910,04:40:33,04:40:33,00102659800840,00100018,,0,0,
5503A 0211000910,04:41:43,04:41:43,00102659801030,00100019,,0,0,
5503A 0211000910,04:43:28,04:43:28,00101260203357,00100020,,0,0,
5503A 0211000910,04:44:10,04:44:10,00101260203165,00100021,,0,0,
5503A 0211000910,04:45:51,04:45:51,00101260202789,00100022,,0,0,
5503A 0211000910,04:47:14,04:47:14,00101260202557,00100023,,0,0,
5503A 0211000910,04:49:45,04:49:45,00101260202115,00100024,,0,0,
5503A 0211000910,04:51:18,04:51:18,00101260201647,00100025,,0,0,
5503A 0211000910,04:53:07,04:53:07,00101260201201,00100026,,0,0,
5503A 0211000910,04:55:15,04:55:15,00101260200853,00100027,,0,0,
5503A 0211000910,04:56:40,04:56:40,00101260200605,00100028,,0,0,
5503A 0211000910,04:57:40,04:57:40,00101260200285,00100029,,0,0,
5503A 0211000910,05:04:17,05:04:17,00101865200555,00100030,,0,0,
5503A 0211000910,05:12:01,05:12:01,00101722800900,00100031,,0,0,
5503A 0211000910,05:14:08,05:14:08,00100376100344,00100032,,0,0,
5503A 0211000910,05:15:59,05:15:59,00100376100648,00100033,,0,0,
5503A 0211000910,05:17:03,05:17:03,00100376100914,00100034,,0,0,
5503A 0211000910,05:19:12,05:19:12,00100226400110,00100035,,0,0,
5503A 0211000910,05:21:25,05:21:25,00103203700176,00100036,,0,0,
5503A 0211000910,05:23:40,05:23:40,00100673100474,00100037,,0,0,
5503A 0211000910,05:26:23,05:26:23,00100314000471,00100038,,0,0,
5503A 0211000910,05:27:56,05:27:56,00100376100397,00100039,,0,0,
5503A 0211000910,05:37:02,05:37:02,00101865200360,00100040,,0,0,
5503A 0211000910,05:37:59,05:37:59,00101865200580,00100041,,0,0,
5503A 0211000910,05:40:45,05:40:45,00101865201300,00100042,,0,0,
5503A 0211000910,05:42:51,05:42:51,00101865201440,00100043,,0,0,
5503A 0211000910,05:44:54,05:44:54,00101260200330,00100044,,0,0,
5503A 0211000910,05:47:39,05:47:39,00101260200870,00100045,,0,0,
5503A 0211000910,05:49:13,05:49:13,00101260201200,00100046,,0,0,
5503A 0211000910,05:50:54,05:50:54,00101260201648,00100047,,0,0,
5503A 0211000910,05:52:19,05:52:19,00101260202258,00100048,,0,0,
5503A 0211000910,05:54:59,05:54:59,00101260202530,00100049,,0,0,
5503A 0211000910,05:55:35,05:55:35,00101260202622,00100050,,0,0,
5503A 0211000910,05:56:59,05:56:59,00101260202900,00100051,,0,0,
5503A 0211000910,05:57:41,05:57:41,00101260203080,00100052,,0,0,
5503A 0211000910,06:00:08,06:00:08,00102659801069,00100053,,0,0,
5503A 0211000910,06:00:31,06:00:31,00111922600090,00100054,,0,0,
5503A 0211000910,06:01:23,06:01:23,00111920000320,00100055,,0,0,
5503A 0211000910,06:01:40,06:01:40,00109581200012,00100056,,0,0,
5503A 0211000910,06:03:18,06:03:18,00109581200182,00100057,,0,0,
5503A 0211000910,06:04:23,06:04:23,00100153600231,00100058,,0,0,
5503A 0211000910,06:04:55,06:04:55,00103449200016,00100059,,0,0,
5503A 0211000910,06:05:15,06:05:15,00103701500082,00100060,,0,0,
5503A 0211000910,06:05:48,06:05:48,00101050600185,00100061,,0,0,
5503A 0211000910,06:06:42,06:06:42,00102023200116,00100062,,0,0,
5503A 0211000910,06:07:18,06:07:18,00102023200362,00100063,,0,0,
5503A 0211000910,06:07:36,06:07:36,00105010600763,00100064,,0,0,
5503A 0211000910,06:08:50,06:08:50,00105649000107,00100065,,0,0,
5503A 0211000910,06:09:23,06:09:23,00109588100160,00100066,,0,0,

5503A 0210806008,04:30:00,04:30:00,00109588100160,00100010,,0,0,
5503A 0210806008,04:32:47,04:32:47,00105649000110,00100011,,0,0,
5503A 0210806008,04:33:49,04:33:49,00105010600700,00100012,,0,0,
5503A 0210806008,04:34:41,04:34:41,00102023200363,00100013,,0,0,
5503A 0210806008,04:35:17,04:35:17,00102023200107,00100014,,0,0,
5503A 0210806008,04:35:50,04:35:50,00103205201312,00100015,,0,0,
5503A 0210806008,04:36:29,04:36:29,00103205201386,00100016,,0,0,
5503A 0210806008,04:37:06,04:37:06,00103205200131,00100017,,0,0,
5503A 0210806008,04:40:33,04:40:33,00102659800840,00100018,,0,0,
5503A 0210806008,04:41:43,04:41:43,00102659801030,00100019,,0,0,
5503A 0210806008,04:43:28,04:43:28,00101260203357,00100020,,0,0,
5503A 0210806008,04:44:10,04:44:10,00101260203165,00100021,,0,0,
5503A 0210806008,04:45:51,04:45:51,00101260202789,00100022,,0,0,
5503A 0210806008,04:47:14,04:47:14,00101260202557,00100023,,0,0,
5503A 0210806008,04:49:45,04:49:45,00101260202115,00100024,,0,0,
5503A 0210806008,04:51:18,04:51:18,00101260201647,00100025,,0,0,
5503A 0210806008,04:53:07,04:53:07,00101260201201,00100026,,0,0,
5503A 0210806008,04:55:15,04:55:15,00101260200853,00100027,,0,0,
5503A 0210806008,04:56:40,04:56:40,00101260200605,00100028,,0,0,
5503A 0210806008,04:57:40,04:57:40,00101260200285,00100029,,0,0,
5503A 0210806008,05:04:17,05:04:17,00101865200555,00100030,,0,0,
5503A 0210806008,05:12:01,05:12:01,00101722800900,00100031,,0,0,
5503A 0210806008,05:14:08,05:14:08,00100376100344,00100032,,0,0,
5503A 0210806008,05:15:59,05:15:59,00100376100648,00100033,,0,0,
5503A 0210806008,05:17:03,05:17:03,00100376100914,00100034,,0,0,
5503A 0210806008,05:19:12,05:19:12,00100226400110,00100035,,0,0,
5503A 0210806008,05:21:25,05:21:25,00103203700176,00100036,,0,0,
5503A 0210806008,05:23:40,05:23:40,00100673100474,00100037,,0,0,
5503A 0210806008,05:26:23,05:26:23,00100314000471,00100038,,0,0,
5503A 0210806008,05:27:56,05:27:56,00100376100397,00100039,,0,0,
5503A 0210806008,05:37:02,05:37:02,00101865200360,00100040,,0,0,
5503A 0210806008,05:37:59,05:37:59,00101865200580,00100041,,0,0,
5503A 0210806008,05:40:45,05:40:45,00101865201300,00100042,,0,0,
5503A 0210806008,05:42:51,05:42:51,00101865201440,00100043,,0,0,
5503A 0210806008,05:44:54,05:44:54,00101260200330,00100044,,0,0,
5503A 0210806008,05:47:39,05:47:39,00101260200870,00100045,,0,0,
5503A 0210806008,05:49:13,05:49:13,00101260201200,00100046,,0,0,
5503A 0210806008,05:50:54,05:50:54,00101260201648,00100047,,0,0,
5503A 0210806008,05:52:19,05:52:19,00101260202258,00100048,,0,0,
5503A 0210806008,05:54:59,05:54:59,00101260202530,00100049,,0,0,
5503A 0210806008,05:55:35,05:55:35,00101260202622,00100050,,0,0,
5503A 0210806008,05:56:59,05:56:59,00101260202900,00100051,,0,0,
5503A 0210806008,05:57:41,05:57:41,00101260203080,00100052,,0,0,
5503A 0210806008,06:00:08,06:00:08,00102659801069,00100053,,0,0,
5503A 0210806008,06:00:31,06:00:31,00111922600090,00100054,,0,0,
5503A 0210806008,06:01:23,06:01:23,00111920000320,00100055,,0,0,
5503A 0210806008,06:01:40,06:01:40,00109581200012,00100056,,0,0,
5503A 0210806008,06:03:18,06:03:18,00109581200182,00100057,,0,0,
5503A 0210806008,06:04:23,06:04:23,00100153600231,00100058,,0,0,
5503A 0210806008,06:04:55,06:04:55,00103449200016,00100059,,0,0,
5503A 0210806008,06:05:15,06:05:15,00103701500082,00100060,,0,0,
5503A 0210806008,06:05:48,06:05:48,00101050600185,00100061,,0,0,
5503A 0210806008,06:06:42,06:06:42,00102023200116,00100062,,0,0,
5503A 0210806008,06:07:18,06:07:18,00102023200362,00100063,,0,0,
5503A 0210806008,06:07:36,06:07:36,00105010600763,00100064,,0,0,
5503A 0210806008,06:08:50,06:08:50,00105649000107,00100065,,0,0,
5503A 0210806008,06:09:23,06:09:23,00109588100160,00100066,,0,0,

START, LAST_DEP, PERIOD

```
all_spans = sum(([s for s in v if time < s.last_dep] for v in trips_spans.values()), [])
all_spans_mat = np.array([[s.start, s.last_dep, s.period] for s in all_spans])
```

---

if you can accomplish a transfer via a direct transfer over a walking transfer, we can remove that line

at start: 37.376 mean edges per node

weight function is called 226,005 times

---

BLOG POST NOTES:

- existing state-of-the-art route planning techniques emphasize heavy preprocessing (and memory usage), under the assumption that the structure of public transit networks are more or less static (at least, change must less frequently than the preprocessing step takes). this heavy preprocessing is a trade-off for faster querying times. and for most route planning applications, querying time is all that matters (if I'm looking up a route on my phone, the faster I get one the better!). with the transfer pattern method, which, at least according to the papers I read, is the current state of the art, essentially precomputes all Pareto-optimal sets of routes between every point in the network and querying is more or less just a lookup in this database.
- for our application, we couldn't afford heavy preprocessing times since we wanted to be able to modify the network and see changes the resulting in routing/travel patterns. that is, we couldn't make the assumption that these public transit networks are essentially static.

At the start, I wasn't familiar at all with the space of route planning (or even what the name for the problem was). So I read through some papers to learn what the primary techniques are, how they stack up, how they're received within the field, and so on. And I went in trying my own implementation, and spent many hours trying things out, sketching solutions out, and compared to the state-of-the-art they were probably all fairly naive, but I ended up gaining a much better understanding of the challenges in the field as well as a better appreciation of the current solutions.

---

INPUTS:

- START (LAT, LON)
- DEPARTURE_TIME
- END (LAT, LON)

PREP:

- SQ: Map of STOP -> [SEQUENCES]
- QS: Map of SEQUENCE -> [STOPS -> [SPANS]]

PROCEDURE:

GRAPH EXTENSION
1) S <- Get `n` closest stops to START
2) For s in S:
    1) For q in SQ[s]:
        1) P <- spans in QS[q][s] where p.last_dep >= DEPARTURE_TIME + walk_time(START, s)
        2) If P
            1) Find d = soonest_dep_time(P)
            2) time_to_board = d - DEPARTURE_TIME
            3) Add edge (START, q, weight=time_to_board, stop=s)
3) S <- Get `n` closest stops to END
    2) For s in S:
        1) For q in SQ[s]:
            2) Add edge (q, END, weight=walk_time(s, END), stop=s)

QUERYING (WEIGHT FUNCTION)
Given an from node u, a to node v, a set of edges between these nodes E, a time t, and current path p
1)

---

OLD:

GRAPH EXTENSION
1) S <- Get `n` closest stops to START
2) For s in S:
    1) For q in SQ[s]:
        1) P <- spans in QS[q][s] where p.last_dep >= DEPARTURE_TIME + walk_time(START, s)
        2) If P
            1) Find d = soonest_dep_time(P)
            2) time_to_board = d - DEPARTURE_TIME
            3) Check if edge(START, q) already exists
                - if False: Add edge (START, q, weight=time_to_board, stop=s)
                - if True: Update edge weight to time_to_board if it is less than the existing value, and also update stop=s
1) S <- Get `n` closest stops to END
    2) For s in S:
        1) For q in SQ[s]:
            2) Check if edge(q, END) already exists
                - if False: Add edge (q, END, weight=walk_time(s, END, stop=s)
                - if True: Update edge weight to walk_time(s, END) if it is less than the existing value, and also update stop=s


---

references for CSA:

- <https://blog.trainline.eu/9159-our-routing-algorithm>

> Prune bad solution early
>
> To get those performances, we had to extend the algorithm for it to be able to prune some solutions, which means getting rid of the worst ones. Indeed, as we search for many results over the day, we scan the connections over a large span of time and the algorithm computes routes to stations very far away from the actual destination. Suboptimal solutions could easily pile up as a consequence.
>
> To avoid considering connections that are not interesting, we build a static graph of the railway network. The cost on each edge is the shortest duration possible considering all the trains on that edge.
>
> Before each search, we do a one-to-all Dijkstra search from the destination. This gives us a lower bound at any stations of the duration to reach the destination. This bound allows us to know that an intermediate solution will never be able to improve an existing solution reducing the search tree.
>
> Dijkstra’s pruning technique must not be confused with A* that changes the order in which the nodes are considered. Even with Dijkstra’s pruning, we consider all the connections in the same sequence.

- <https://github.com/trainline-eu/csa-challenge>
- <https://ljn.io/posts/so-you-want-to-build-a-journey-planner/>
- <https://github.com/trainline-eu/csa-challenge/blob/master/csa.py>

cython refs:

- <http://cython.readthedocs.io/en/latest/src/userguide/wrapping_CPlusPlus.html?highlight=map>
- <https://github.com/cython/cython/blob/master/Cython/Includes/libcpp/map.pxd>
- <https://github.com/explosion/preshed/blob/master/preshed/maps.pyx>
- python arrays in cython
- cython structs
- <http://docs.cython.org/en/latest/src/tutorial/cdef_classes.html>

---

(unlikely to change)
sorted in 1.0925776958465576
n connections: 841339

basic implementation:
considered 40124 connections
run time: 0.06232619285583496

with minimum change times:
considered 40123 connections
run time: 0.04313087463378906

---

for c in self.connections: 8.440017700195312e-05
for i in range(self.connections.size()): 0.0004191398620605469

0.00020122528076171875
0.0002243518829345703


still not working though
0.006216287612915039

working, it seems (w/o footpaths):
0.0004668235778808594

with footpaths:
0.0009014606475830078

compare to python implementation: 0.06341552734375 (~70x)

(this is for a day with 841,339 connections, sunday)

for monday, which has 5,769,591 connections:
python: 0.34987640380859375
cython: 0.0014557838439941406
~240x

---

[{'dep_stop': 8065, 'trip_id': 2511, 'arr_time': 17305.0, 'arr_stop': 8068, 'dep_time': 17235.0, 'type': 1}, {'dep_stop': 8068, 'trip_id': 2511, 'arr_time': 17385.0, 'arr_stop': 8066, 'dep_time': 17305.0, 'type': 1}, {'dep_stop': 8066, 'trip_id': 2511, 'arr_time': 17444.0, 'arr_stop': 8063, 'dep_time': 17385.0, 'type': 1}, {'dep_stop': 8063, 'trip_id': 2511, 'arr_time': 17525.0, 'arr_stop': 8062, 'dep_time': 17444.0, 'type': 1}, {'dep_stop': 8062, 'trip_id': 2511, 'arr_time': 17626.0, 'arr_stop': 8059, 'dep_time': 17525.0, 'type': 1}, {'dep_stop': 8059, 'trip_id': 2511, 'arr_time': 17743.0, 'arr_stop': 8056, 'dep_time': 17626.0, 'type': 1}, {'dep_stop': 8056, 'trip_id': 2511, 'arr_time': 17838.0, 'arr_stop': 8054, 'dep_time': 17743.0, 'type': 1}, {'dep_stop': 8054, 'trip_id': 2495, 'arr_time': 18264.0, 'arr_stop': 4569, 'dep_time': 17980.0, 'type': 1}, {'dep_stop': 4569, 'trip_id': 2495, 'arr_time': 18304.0, 'arr_stop': 4571, 'dep_time': 18264.0, 'type': 1}, {'dep_stop': 4571, 'trip_id': 2495, 'arr_time': 18352.0, 'arr_stop': 4573, 'dep_time': 18304.0, 'type': 1}, {'dep_stop': 4573, 'trip_id': 2495, 'arr_time': 18476.0, 'arr_stop': 4576, 'dep_time': 18352.0, 'type': 1}, {'dep_stop': 4576, 'trip_id': 2495, 'arr_time': 18593.0, 'arr_stop': 4579, 'dep_time': 18476.0, 'type': 1}, {'dep_stop': 4579, 'trip_id': 2495, 'arr_time': 18689.0, 'arr_stop': 1354, 'dep_time': 18593.0, 'type': 1}]

goal:
[{'dep_stop': 8065, 'trip_id': 2511, 'arr_time': 17305.0, 'arr_stop': 8068, 'dep_time': 17235.0, 'type': 1}, {'dep_stop': 8054, 'trip_id': 2495, 'arr_time': 18264.0, 'arr_stop': 4569, 'dep_time': 17980.0, 'type': 1}, {'dep_stop': 4579, 'trip_id': 2495, 'arr_time': 18689.0, 'arr_stop': 1354, 'dep_time': 18593.0, 'type': 1}]

---

# lat, lon
start = (-19.9741332241246, -44.0222417010139)
end = (-19.971944530036897, -44.022082980148106)
s_id, _, s_p, s_pt = map.find_closest_edge(start)
e_id, _, e_p, e_pt = map.find_closest_edge(end)
s_from, s_to, s_idx = [int(i) for i in s_id.split('_')]
e_from, e_to, e_idx = [int(i) for i in e_id.split('_')]

s_to -> 181517724kk
e_from -> 316656169 (-19.9725734, -44.0217701)

# look at edges, compare road names against map
map.network[s_to]
!list(map.network[s_to].values())

# see connected nodes
succs = list(map.network.successors(s_to))
[1815177277, 2310027911]

# check node positions on map
map.network.node[1815177277]
(-19.9746913, -44.022617)

map.network.node[2310027911]
(-19.9749829, -44.0222145)

# going off the maps, 1815177277 seems the best choice
succs = list(map.network.successors(1815177277))
[4748862402, 4676474485, 1815177253]

# wrong direction
4748862402
(-19.9749055, -44.0225573)

# looks good
4676474485
(-19.9726319, -44.0232614)

# wrong way
1815177253
(-19.9749149, -44.0229389)

# using 4676474485
succs = list(map.network.successors(4676474485))
[1815177277, 4676479023]

# back to where we came
1815177277

# looks good
4676479023
(-19.9720585, -44.02325)

# using 4676479023
succs = list(map.network.successors(4676479023))
# no successors???

!list(map.network.predecessors(e_from))
[316656052, 316656158]

# tried loading in the graph unsimplified, no diff.

---

edge
{'maxspeed': 35.80071174377224, 'geometry': <shapely.geometry.linestring.LineString object at 0x7f715c305278>, 'oneway': False, 'leng
th': 175.88525573245687, 'name': 'Rua Geraldo Vasconcelos', 'highway': 'residential', 'osmid': 221668572, 'occupancy': -1, 'lanes': 1
, 'capacity': 8.794262786622843}

vehicle
Vehicle(id='9202  0321001110_ROAD', route=[Leg(frm=78690781, to=3821228023, edge=0, p=0.8027790437522202), Leg(frm=3821228023, to=78690781, edge=0, p=0.21767712625141725)], passengers=[], current={'maxspeed': 35.80071174377224, 'geometry': <shapely.geometry.linestring.LineString object at 0x7f715c305278>, 'oneway': False, 'length': 175.88525573245687, 'name': 'Rua Geraldo Vasconcelos', 'highway': 'residential', 'osmid': 221668572, 'occupancy': -1, 'lanes': 1, 'capacity': 8.794262786622843})

vehicle.route
[Leg(frm=78690781, to=3821228023, edge=0, p=0.8027790437522202), Leg(frm=3821228023, to=78690781, edge=0, p=0.21767712625141725)]


ENTERING 8894811 3501B 0110803308_ROAD
ENTERING 221668572 9202  0321400814_ROAD
ENTERING 221668572 9202  0321300713_ROAD
ENTERING 8894811 3501B 0111400714_ROAD
ENTERING 8894811 3501B 0111300713_ROAD
ENTERING 8894811 3501B 0111000910_ROAD
ENTERING 221668572 9202  0321001110_ROAD
ENTERING 221668572 9202  0320805208_ROAD
LEAVING 8894811 3501B 0110803308_ROAD
LEAVING 8894811 3501B 0110803308_ROAD
LEAVING 8894811 3501B 0110803308_ROAD
LEAVING 8894811 3501B 0110803308_ROAD
LEAVING 8894811 3501B 0110803308_ROAD

original ordering:
ENTERING 221668572 9202  0321400814_0_ROAD
ENTERING 8894811 3501B 0111300713_0_ROAD
ENTERING 221668572 9202  0320805208_0_ROAD
ENTERING 8894811 3501B 0111400714_0_ROAD
ENTERING 221668572 9202  0321300713_0_ROAD
ENTERING 221668572 9202  0321001110_0_ROAD
ENTERING 8894811 3501B 0110803308_0_ROAD
ENTERING 8894811 3501B 0111000910_0_ROAD
LEAVING 221668572 9202  0321400814_0_ROAD
LEAVING 221668572 9202  0321400814_0_ROAD
LEAVING 221668572 9202  0321400814_0_ROAD
ENTERING 221668572 9202  0321400814_0_ROAD
LEAVING 221668572 9202  0320805208_0_ROAD
LEAVING 221668572 9202  0320805208_0_ROAD <-

for comparison:
ENTERING 221668572 9202  0321400814_0_ROAD
ENTERING 221668572 9202  0320805208_0_ROAD
ENTERING 221668572 9202  0321300713_0_ROAD
ENTERING 221668572 9202  0321001110_0_ROAD
LEAVING 221668572 9202  0321400814_0_ROAD
LEAVING 221668572 9202  0321400814_0_ROAD
LEAVING 221668572 9202  0321400814_0_ROAD
ENTERING 221668572 9202  0321400814_0_ROAD
LEAVING 221668572 9202  0320805208_0_ROAD
LEAVING 221668572 9202  0320805208_0_ROAD

ENTERING 8894811 3501B 0111300713_0_ROAD
ENTERING 8894811 3501B 0111400714_0_ROAD
ENTERING 8894811 3501B 0110803308_0_ROAD
ENTERING 8894811 3501B 0111000910_0_ROAD


ENTER e 144755785 v 1404A 0520804908_0_ROAD occ 0
ENTER e 8894811 v 3501B 0110803308_0_ROAD occ 0
ENTER e 8894811 v 3501B 0111000910_0_ROAD occ 1
ENTER e 144755785 v 1404A 0521400814_0_ROAD occ 1
ENTER e 221668572 v 9202  0320805208_0_ROAD occ 0
ENTER e 8894811 v 3501B 0111400714_0_ROAD occ 2
ENTER e 8894811 v 3501B 0111300713_0_ROAD occ 3
ENTER e 144755785 v 1404A 0521300513_0_ROAD occ 2
ENTER e 221668572 v 9202  0321300713_0_ROAD occ 1
ENTER e 221668572 v 9202  0321001110_0_ROAD occ 2
ENTER e 221668572 v 9202  0321400814_0_ROAD occ 3
ENTER e 144755785 v 1404A 0521001210_0_ROAD occ 3
LEAVE e 8894811 v 3501B 0110803308_0_ROAD occ 3
LEAVE e 8894811 v 3501B 0110803308_0_ROAD occ 2
LEAVE e 8894811 v 3501B 0110803308_0_ROAD occ 1
LEAVE e 8894811 v 3501B 0110803308_0_ROAD occ 0
LEAVE e 8894811 v 3501B 0110803308_0_ROAD occ -1


ENTER e 8894811 v 3501B 0111300713_0_ROAD occ 1
ENTER e 221668572 v 9202  0321400814_0_ROAD occ 1
ENTER e 144755785 v 1404A 0521001210_0_ROAD occ 1
ENTER e 221668572 v 9202  0320805208_0_ROAD occ 3
LEAVE e 144755785 v 1404A 0521001210_0_ROAD occ 1
LEAVE e 144755785 v 1404A 0521001210_0_ROAD occ 0
ENTER e 144755785 v 1404A 0521001210_0_ROAD occ 1
LEAVE e 221668572 v 9202  0321400814_0_ROAD occ 0
LEAVE e 221668572 v 9202  0321400814_0_ROAD occ -1

I think what's happening is this:

- some road events happen immediately next, taking countdown time=0
- if there are multiple of these events queued, they happen in random order
- so we might get an ENTER <ROAD> happening in 0 sec and an immediate LEAVE <ROAD> happening after, also in 0sec
- what could be happening is that they are unordered if they are schedule for the same time, so we execute the LEAVE <ROAD> first, before the ENTER <ROAD>, and thus we get negative occupancy

---

defaultdict(<function Sim.__init__.<locals>.<lambda> at 0x7fbe5bc9c950>, {'00101865205600': defaultdict(<class 'list'>, {'813   0211000110': []}), '00130311900120': defaultdict(<class 'list'>, {'305   0210801108': []}), '00107409200240': defaultdict(<class 'list'>, {'21
02  0111001010': []}), '00112385400932': defaultdict(<class 'list'>, {'9202  0320805208': []}), '00105567300150': defaultdict(<class 'list'>, {'9412  1320800408': []}), '00112146800351': defaultdict(<class 'list'>, {'3503A 0121300613': []}), '00100980200007': defaultdic
t(<class 'list'>, {'318   0210800808': []})})

---

69017it [00:17, 3849.60it/s]

without closest edge caching:
65852it [00:29, 2232.71it/s]
slower, but I expect closest edge caching will cause memory issues at some point.

with edge caching just for buses:
64968it [00:14, 4510.70it/s]

with route caching for buses:
65767it [00:10, 6412.12it/s]
