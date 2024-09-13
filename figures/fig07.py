import os,pathlib
import numpy as np
#import scipy
from akramms import config,params
from uafgi.util import gdalutil,wrfutil,cartopyutil,cptutil
from osgeo import gdalconst
import matplotlib.pyplot as plt
import pandas as pd
import seaborn
import akfigs,aklapse
import akramms.experiment.ak as exp
from akramms import downscale_snow


# =================================================================
#dfc_tif = exp.dir / 'ak_DFC.tif'
#gridA, dfcA, dfcA_nd = gdalutil.read_raster(exp.dir / 'ak_DFC.tif')
#dfcA[dfcA == 0] = np.nan


#lapseA = downscale_snow.lapse_by_distance_from_coast(dfcA)

ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'
geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid
sx3_nc = ccsm_dir / 'ccsm_sx3_2010.nc'    # Use 2010 data
gridA = wrfutil.wrf_info(geo_nc)
gridA_crs = cartopyutil.crs(gridA.wkt)

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

# =================================================
# Plot the empirical lapse rate!
if True:
    map_crs = cartopyutil.crs('+proj=aea +lat_0=50 +lon_0=-154 +lat_1=55 +lat_2=65 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs +type=crs')

    map_extent = ((320-30)*1000, (1510+0)*1000, (710-0)*1000, (1425+30)*1000)    # xmin, xmax, ymin, ymax; ymin in South

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))

    ax.set_extent(map_extent, map_crs)


    # This follows E3SM convention for precip
    # See here for suggested colormaps
    # https://docs.e3sm.org/e3sm_diags/_build/html/master/colormaps.html
#    cmap,_,_ = cptutil.read_cpt('palettes/Mai_Soul_DFC.cpt', scale=1000.)    # Turn to [m]
    cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
    cmap = cptutil.discrete_cmap(12, cmap)

    lapseA[lapseA == 0] = np.nan
    lapseA[wrfdemA == 0] = np.nan
#    gridA_crs = cartopyutil.crs(gridA.wkt)
    vmin = np.nanmin(lapseA)
    vmax = np.nanmax(lapseA)
    print('vmin vmax ', vmin, vmax)
    pcm_lapse = ax.pcolormesh(
        gridA.centersx, gridA.centersy, lapseA,
        rasterized=True,
        transform=gridA_crs, cmap=cmap, vmin=0., vmax=0.3)


    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)



    akfigs.plot_cities(ax,
        text_kwargs=dict(
            fontdict = {'size': 4, 'color': 'blue', 'fontweight': 'bold'}),
        marker_kwargs=dict(
            marker='*', markersize=2, color='black', alpha=0.9))

    ofname = pathlib.Path('./fig07.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off


    # ---------- The colorbar
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
#        subplot_kw={'projection': map_crs},
        figsize=(2.8,2.8))
    cbar_ax = axs
    km = 1000.
    cbar = fig.colorbar(pcm_lapse, ax=cbar_ax)
#        ticks=[90*km,140*km, 190*km, 240*km])
#    cbar.ax.set_yticklabels(['90 km', '140', '190', '240'])
    cbar.ax.tick_params(labelsize=12)
    cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

    ofname = pathlib.Path('fig07-cbar.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off
