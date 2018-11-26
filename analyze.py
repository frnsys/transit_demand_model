"""
Plots histograms for transit simulation results:

- travel times (min)
- travel distances (km)
- travel speeds (km/h)
"""

import sys
import json
import pandas as pd
import seaborn as sns
from collections import defaultdict
from gtfs.haversine import haversine
import matplotlib.pyplot as plt

try:
    sim_output_path = sys.argv[1]
except IndexError:
    print('Please specify the sim data output path')
    sys.exit(1)

with open(sim_output_path, 'r') as f:
    data = json.load(f)

# Time in seconds
agent_travel_times = defaultdict(int)
agent_travel_dists = defaultdict(int)
for agent_id, stop_start, stop_end, stop_type, stop_deptime, time in data['agent_trips']:
    x_s, y_s = stop_start
    x_e, y_e = stop_end
    dist = haversine(x_s, y_s, x_e, y_e) # km
    elapsed = (time - stop_deptime)/60 # minutes
    agent_travel_times[agent_id] += elapsed
    agent_travel_dists[agent_id] += dist

agent_travel_speeds = {}
for agent_id, travel_time in agent_travel_times.items():
    dist = agent_travel_dists[agent_id]
    agent_travel_speeds[agent_id] = dist/travel_time/60 # km/h

df = pd.DataFrame.from_dict({
    'time': agent_travel_times,
    'distance': agent_travel_dists,
    'speed': agent_travel_speeds
})

sns.set() # set default seaborn styles
fig, axs = plt.subplots(nrows=3, figsize=(10,10))
sns.distplot(df.time, kde=False, axlabel='time (min)', ax=axs[0])
sns.distplot(df.distance, kde=False, axlabel='distance (km)', ax=axs[1])
sns.distplot(df.speed, kde=False, axlabel='speed (km/h)', ax=axs[2])
plt.savefig('travel_plots.png')
plt.show()
