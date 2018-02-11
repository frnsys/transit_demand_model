import numpy as np
from pyqtree import Index
from shapely import geometry
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
plt.style.use('ggplot')

# distance we expect the bus stop to be from the road
# will pad all bounding boxes accordingly
radius = 0.1

pt = geometry.Point(0.6, 0.4)
bbox = (-0.3, -0.3, 1.4, 1.4)
paths = [
    [(0, 0), (0.2, 0.6), (0.5, 0.9), (1, 1)],
    [(0.8, 0.2), (0.5, 0.8), (0.5, 0.9)],
    [(0.4, 0.05), (0.5, 0.1), (0.6, 0.07), (0.65, 0)],
    [(0, 1.2), (0.2, 0.9), (0.2, 0.65), (0.3, 0.4), (0.3, 0.3)],
]

idx = Index(bbox)
lines = []

for i, path in enumerate(paths):
    # create line
    line = geometry.LineString(path)

    # bboxes
    x1, y1, x2, y2 = line.bounds
    bounds = x1-radius, y1-radius, x2+radius, y2+radius
    idx.insert(i, bounds)

    lines.append((line, bounds))

# query point
pt_bounds = pt.x-radius, pt.y-radius, pt.x+radius, pt.y+radius
matches = idx.intersect(pt_bounds)

# find closest path
closest_path = min(matches, key=lambda i: lines[i][0].distance(pt))
closest_line = lines[closest_path][0]

# find closest point on closest path
p = closest_line.project(pt, normalized=True)
closest_pt = closest_line.interpolate(p, normalized=True)


# visualize ---

fig = plt.figure()
ax = fig.add_subplot(111)
ax.set_title('finding nearest paths')
ax.set_xlim([bbox[0], bbox[2]])
ax.set_ylim([bbox[1], bbox[3]])

# plot lines and their bounding boxes
for line, bounds in lines:
    ax.plot(*line.xy, color='0.2')
    poly = geometry.box(*bounds)
    mpl_poly = Polygon(np.array(poly.exterior), facecolor='b', lw=2, ec='b', alpha=0.2)
    ax.add_patch(mpl_poly)

# plot query point
poly = geometry.box(*pt_bounds)
mpl_poly = Polygon(np.array(poly.exterior), facecolor='r', lw=0, alpha=0.2)
ax.add_patch(mpl_poly)
ax.plot(*pt.xy, 'ro')

# highlight matched lines
for match in matches:
    line = lines[match][0]
    ax.plot(*line.xy, color='g')

# highlight closest line and pt
ax.plot(*closest_line.xy, color='r')
ax.plot(*closest_pt.xy, 'r*', markersize=12)

plt.show()


