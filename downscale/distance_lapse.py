import os
import numpy as np
from akramms import config,params
from uafgi.util import gdalutil,wrfutil
from osgeo import gdalconst
import matplotlib.pyplot as plt
import pandas as pd
import seaborn

sx3_dir = config.roots.syspath('{DATA}/lader/sx3')

gridA, lapseA, lapseA_nd = gdalutil.read_raster('lapse.tif')
gridA, distanceA, distanceA_nd = gdalutil.read_raster('distance.tif')
wrfdemA,wrfdemA_nd = wrfutil.read_raw(
    os.path.join(sx3_dir, 'geo_southeast.nc'), 'HGT_M')
wrfdemA = wrfdemA[0,:,:]

if True:
    mask_in = (distanceA != distanceA_nd)
    #plt.scatter(distanceA[mask_in], lapseA[mask_in])
    df = pd.DataFrame({'distance': distanceA[mask_in], 'lapse': lapseA[mask_in]})

    df = df[df.lapse > 0.01]
    df = df[df.lapse < 0.17]

    # Bin the data
    bin_width = 30000.
    by_bin_width = 1. / bin_width
    bin = np.floor(df['distance'] * by_bin_width + .5) * bin_width * .001    # km
    df['bin'] = bin.astype('i')

else:
    mask_in = (wrfdemA != wrfdemA_nd)
    df = pd.DataFrame({'elev': wrfdemA[mask_in], 'lapse': lapseA[mask_in]})


    # Bin the data
    bin_width = 100.
    by_bin_width = 1. / bin_width
    df['bin'] = np.floor(df['elev'] * by_bin_width + 5) * bin_width


#grp = df[['bin', 'lapse']].groupby('bin')


print('Plotting boxplot')
seaborn.boxplot(df, x='bin', y='lapse')
print('Showing it')
plt.show()


#
#
#
## Bin the data
#bin_width = 10000.
#by_bin_width = 1. / bin_width
#df['bin'] = np.floor(df['distance'] * by_bin_width + 5) * bin_width
#grp = df[['bin', 'lapse']].groupby('bin')
#
#df_mean = grp.mean().rename({'lapse': 'mean'})
#df_std = grp.std().rename({'lapse': 'std'})
#
#
#
#print(mean)
#
#
#
##distanceA = distanceA[mask_in]
##lapseA = lapseA[mask_in]
#
#
#
#
##bins = np.linspace(0,600000, 10000.)
##digi = np.digitize(
#
#
##plt.show()
#
#
#
