# import the packages
import matplotlib.pyplot as plt
from matplotlib.transforms import Affine2D
import mpl_toolkits.axisartist.floating_axes as floating_axes

# set the figure size
plt.rcParams["figure.figsize"] = [7.00, 3.50]
plt.rcParams["figure.autolayout"] = True

# plot the figure
fig = plt.figure()

scales = (0, 5, 0, 5)

# Add 2D affine transformation
t = Affine2D().rotate_deg(25)

# Add floating axes
h = floating_axes.GridHelperCurveLinear(t, scales)
ax = floating_axes.FloatingSubplot(fig, 111, grid_helper=h)

fig.add_subplot(ax)

plt.show()
