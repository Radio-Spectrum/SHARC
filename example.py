import matplotlib.pyplot as plt
# import matplotlib.axes
import matplotlib.patches as patches
import math

r = 450 / 3
hotspot_radius = 100

fig = plt.figure(
    figsize=(8, 8), facecolor='w',
    edgecolor='k',
)  # create a figure object
ax = fig.add_subplot(1, 1, 1)  # create an axes object in the figure

def place_bs(x, y, az, clr='k'):
    # macro cell base stations
    ax.scatter(
        [x], [y], color=clr, edgecolor=clr,
        linewidth=4, label="BS",
    )

    a = az
    pa = patches.Wedge(
        (x, y), hotspot_radius, a - 60, a + 60, fill=False,
        edgecolor=clr, linestyle='solid',
    )

    ax.add_patch(pa)

se = list([[-r, 0]])
angle = int(0 - 60)
for a in range(6):
    se.extend([[
        se[-1][0] + r * math.cos(math.radians(angle)),
        se[-1][1] + r * math.sin(math.radians(angle)),
    ]])
    angle += 60
    place_bs(se[-1][0], se[-1][1], angle+60, 'r')

sector = plt.Polygon(se, fill=None, edgecolor='k')
ax.add_patch(sector)

def place_labeled_line(x1,y1, x2,y2, label):
    ax.plot([x1, x2], [y1, y2], marker='_', color="blue")
    ax.text(x1 + (x2-x1)/2 + 2, y1 + (y2 - y1)/2, label)

place_bs(0, 0, -90)
place_bs(0, 0, 90)
place_labeled_line(0,-math.sqrt(3) * r / 2, 0, hotspot_radius - 1 - math.sqrt(3) * r / 2, "hotspot_radius - 1")

plt.axis('image')
plt.title("Hotspots")
plt.xlabel("x-coordinate [m]")
plt.ylabel("y-coordinate [m]")
plt.tight_layout()
plt.legend(loc="upper left", scatterpoints=1)
plt.show()

