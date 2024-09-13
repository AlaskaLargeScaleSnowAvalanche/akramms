import os,pathlib
import numpy as np
#import scipy
from akramms import config,params
from uafgi.util import gdalutil,wrfutil
from osgeo import gdalconst
import matplotlib.pyplot as plt
import pandas as pd
import seaborn
import akfigs,aklapse
import akramms.experiment.ak as exp
from akramms import downscale_snow


# =================================================================
dfc_tif = exp.dir / 'ak_DFC.tif'
gridA, dfcA, dfcA_nd = gdalutil.read_raster(exp.dir / 'ak_DFC.tif')
#dfcA[dfcA == 0] = np.nan

#lapseA = downscale_snow.lapse_by_distance_from_coast(dfcA)

ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'
geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid
sx3_nc = ccsm_dir / 'ccsm_sx3_2010.nc'    # Use 2010 data

sx3A,sx3A_nd = wrfutil.read_raw(sx3_nc, 'sx3')

#gridA, lapseA, lapseA_nd = gdalutil.read_raster('lapse.tif')
#gridA, dfcA, dfcA_nd = gdalutil.read_raster(exp.dir / 'ak_DFC.tif')
wrfdemA,wrfdemA_nd = wrfutil.read_raw(geo_nc, 'HGT_M')
wrfdemA = wrfdemA[0,:,:]

# =================================================
# Compute lapse empirically
if True:
    # Approximate proper handling of unused cells.  Reduce errors in gaussian_filter below.
    # See icebin C++ and prototype Python code for correct treatment.
    # https://github.com/citibeth/icebin/blob/d09ba3a0da04bab65adacd0c5e2f4cb50e116a0b/slib/icebin/smoother.cpp
    sx3_mean = np.mean(sx3A[sx3A != sx3A_nd])
    sx3A[sx3A == sx3A_nd] = sx3_mean

    lapseA = aklapse.compute_lapse(wrfdemA, sx3A, gridA.dy, gridA.dx)
    mask_out = np.logical_or.reduce((sx3A == sx3A_nd, sx3A <= 0, wrfdemA<200., np.isnan(lapseA)))
    mask_out2 = np.logical_or.reduce((sx3A == sx3A_nd, sx3A <= 0, wrfdemA<200., np.isnan(lapseA), lapseA<0.))

    print('mask_out ', np.sum(mask_out))
    print('TOTAL cells ', mask_out.shape[0] * mask_out.shape[1])
    lapseA_mean = np.mean(lapseA[np.logical_not(mask_out2)])
    print('lapseA_mean ', lapseA_mean)
    lapseA[mask_out2] = lapseA_mean
#    lapseA = scipy.ndimage.gaussian_filter(lapseA, sigma=10)
    lapseA[mask_out] = 0.

# =================================================

if True:
    mask_in = (dfcA != dfcA_nd)
    #plt.scatter(dfcA[mask_in], lapseA[mask_in])
    df = pd.DataFrame({'distance': dfcA[mask_in], 'lapse': lapseA[mask_in]})

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
ax = seaborn.boxplot(df, x='bin', y='lapse')
#bp.set_xticks([0,90,180,270,360,450,540,600])
labels = ax.get_xticklabels()
#print(type(labels[0]))
ax.set_xticklabels([
    '0','30','',
    '90','','',
    '180','','',
    '270','','',
    '360','','',
    '450','','',
    '540','','600'])
ax.set_ylabel('')    # lapse ([m snow] / km)
ax.set_xlabel('')    # bin (distance from coast in km)

print('Showing it')


ofname = pathlib.Path('fig09.pdf')
with akfigs.TrimmedPdf(ofname) as tname:
    plt.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off

#plt.show()


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
##dfcA = dfcA[mask_in]
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
