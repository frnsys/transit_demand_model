from shapely import geometry
import matplotlib.pyplot as plt
plt.style.use('ggplot')

line = geometry.LineString([(0, 0), (0.2, 0.6), (0.5, 0.9), (1, 1)])

fig = plt.figure()
ax = fig.add_subplot(111)
ax.plot(*line.xy, color='0.75')
ax.set_title('finding nearest point on line')

# interpolation test
for d in [0, 0.2, 0.5, 0.8, 1]:
    pt = line.interpolate(d, normalized=True)
    ax.plot(*pt.xy, 'bo', markersize=3)
    ax.annotate(str(d), xy=(pt.x, pt.y), fontsize=12, color='0.3')


# find distance to closest point on line
# can use this to find the closest line
# after filtering with a quadtree
pt = geometry.Point(0.6, 0.2)
dist = line.distance(pt)
print(line.xy)
print(dist)
ax.plot(*pt.xy, 'ro')

# then find closest point on the line
p = line.project(pt, normalized=True)
closest = line.interpolate(p, normalized=True)
ax.plot(*closest.xy, 'r*', markersize=12)

plt.show()