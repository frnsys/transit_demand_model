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
    try:
        agent_travel_speeds[agent_id] = dist/(travel_time/60) # km/h
    except ZeroDivisionError:
        print('ZeroDivisionError, distance:', dist)
        agent_travel_speeds[agent_id] = 0

agent_trip_types = {id: 'public' if public else 'private'
                    for id, public in data['agent_trip_types'].items()}

df = pd.DataFrame.from_dict({
    'time': agent_travel_times,
    'distance': agent_travel_dists,
    'speed': agent_travel_speeds,
    'trip_type': agent_trip_types
})
df = df.dropna()

sns.set() # set default seaborn styles
df_public, df_private = df.loc[df.trip_type == 'public'], df.loc[df.trip_type == 'private']
palette = {'public': 'r', 'private': 'b'}
fig, axs = plt.subplots(nrows=4, figsize=(12,16))

for (key, unit), ax in zip([('time', 'min'), ('distance', 'km'), ('speed', 'km/h')], axs):
    for type, df_ in [('public', df_public), ('private', df_private)]:
        sns.distplot(df_[key],
                     kde=False,
                     axlabel='{} ({})'.format(key, unit),
                     color=palette[type],
                     ax=ax)
sns.scatterplot(df.distance, df.time, hue=df.trip_type,
                palette=palette, markers=['.', 'x'], ax=axs[-1])
plt.tight_layout()
plt.savefig('travel_plots.png')
plt.show()
