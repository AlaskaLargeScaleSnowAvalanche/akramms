import os,pathlib
import numpy as np
#import scipy
from akramms import config,params
from uafgi.util import gdalutil,wrfutil,cartopyutil,cptutil,gisutil
from osgeo import gdalconst
import matplotlib.pyplot as plt
import pandas as pd
import seaborn
import akfigs,aklapse
import akramms.experiment.ak as exp
from akramms import downscale_snow
import cartopy.io.img_tiles

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
    map_crs = akfigs.map_crs()
    map_extent = (155*1000, 1680*1000, 510*1000, 1645*1000)    # xmin, xmax, ymin, ymax; ymin in South  (Same as fig04)

#    map_crs = cartopyutil.crs('+proj=aea +lat_0=50 +lon_0=-154 +lat_1=55 +lat_2=65 +x_0=0 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs +type=crs')

#    map_extent = ((320-30)*1000, (1510+0)*1000, (710-0)*1000, (1425+30)*1000)    # xmin, xmax, ymin, ymax; ymin in South

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
            fontdict = {'size': 8, 'color': 'black', 'fontweight': 'bold'}),
        marker_kwargs=dict(
            marker='*', markersize=2, color='black', alpha=0.9))

    # Add graticules
    gl = ax.gridlines(draw_labels=True,
          linewidth=0.3, color='grey', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
    gl.xlabel_style = {'size': 9}
    gl.ylabel_style = {'size': 9}
    gl.xlabels_top = False        
    gl.ylabels_right = False

    ofname = pathlib.Path('./fig07.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off


    # ---------- The colorbar
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
#        subplot_kw={'projection': map_crs},
        figsize=(108/25.4,108/25.4))
    cbar_ax = axs
    km = 1000.
    cbar = fig.colorbar(pcm_lapse, ax=cbar_ax,
        ticks=[0.,0.05,0.1,0.15,0.2,0.25,0.3])
    cbar.ax.set_yticklabels(['0.00 m/km', '0.05', '0.10', '0.15', '0.20', '0.25', '.30 m/km'])
    cbar.ax.tick_params(labelsize=10)
    cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

    ofname = pathlib.Path('fig07-cbar.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off

    # ==================================================================
    # Make the inset map
#    imap_extent = (-820*1000, 1900*1000, 0*1000, 2400*1000)
    # Same as fig01 map_extent, 
    imap_extent = (-820*1000, 2500*1000, -100*1000, 2400*1000)
#    imap_extent = akfigs.allalaska_map_extent

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(2.5,1.5))
    ax.set_extent(imap_extent, crs=map_crs)

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 6, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # The overall bounding box
    bbox_feature = akfigs.wrf_bbox_feature()
    ax.add_feature(bbox_feature, facecolor='none', edgecolor='brown', lw=1.0, linestyle='--')


    # The original map bounds
    map_extent_feature = cartopy.feature.ShapelyFeature(gisutil.xxyy_to_poly(*map_extent), map_crs)
    ax.add_feature(map_extent_feature, facecolor='none', edgecolor='blue', lw=0.5)

    # Outline this map (so the inset map looks inset)
    imap_extent_feature = cartopy.feature.ShapelyFeature(gisutil.xxyy_to_poly(*imap_extent), map_crs)
    ax.add_feature(imap_extent_feature, facecolor='none', edgecolor='black', lw=2.0)


    ofname = pathlib.Path('./fig07-inset.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off
