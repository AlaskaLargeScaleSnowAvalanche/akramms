import pathlib,os
import statistics
import numpy as np
import shapely
import akfigs
import matplotlib.pyplot as plt

import akramms.experiment.aksc5c as expmod
from akramms import downscale_snow,config
from uafgi.util import wrfutil,cartopyutil,cptutil,gdalutil,gisutil

from osgeo import gdal



def read_and_align(path, srs, width, height, GT):

    xres = GT[1]
    yres = GT[5]
    minX = GT[0]
    maxX = minX + (width * xres)
    maxY = GT[3]
    minY = maxY + (height * yres) # GT[5] is usually negative

    ds0 = gdal.Open(path)
    ds1 = gdal.Warp(
        '', ds0, format='MEM',
        xRes=xres, yRes=yres, width=width, height=height, outputBounds=[minX, minY, maxX, maxY],
        dstSRS=srs,
        resampleAlg='nearest')
    return gdalutil.read_ds(ds1)


def main():

    past_tif = config.HARNESS / 'outputs/wrf_era5_agg3/acsnow_agg3_4km_1940_2023_030.tif'
    fut_tifs = [config.HARNESS / 'outputs/wrf_fut_agg3' / x \
        for x in ('acsnow_agg3_4km_2039_2068_030.tif', 'acsnow_agg3_4km_2069_2098_030.tif')]


    # Regrid to a common grid
    ref_ds = gdal.Open(past_tif)
    GT = list(ref_ds.GetGeoTransform())
    GT[1] = 0.5 * GT[1]    # Cells are offset by 1/2 gridcell between the past and future
    GT[5] = 0.5 * GT[5]
    align_kwargs = (ref_ds.GetProjection(), ref_ds.RasterXSize*2, ref_ds.RasterYSize*2, GT)

  
    past_grid,past_data,past_nd = read_and_align(past_tif, *align_kwargs)
    print('past_data ', past_data.shape)


    # Average together the futures
    fut_grid,fut_data,fut_nd = read_and_align(fut_tifs[0], *align_kwargs)
    for fut_tif in fut_tifs[1:]:
        _,x_data,_ = read_and_align(fut_tif, *align_kwargs)
        fut_data += x_data
    fut_data *= 1. / len(fut_tifs)


    # Reproject futures onto past


    # ---------------------------------------
    def finish_plot(fig, ax, ofname):
        ofname = pathlib.Path(ofname)
        ax.coastlines(resolution='10m', color='grey', linewidth=0.5)

#        akfigs.plot_cities(ax, 'scalaska',
#            text_kwargs=dict(
#                fontdict = {'size': 7, 'color': 'black', 'fontweight': 'bold'}),
#            marker_kwargs=dict(
#                marker='*', markersize=2, color='black', alpha=0.9))

        # Add graticules
        if True:
            gl = ax.gridlines(draw_labels=True,
                  linewidth=0.3, color='grey', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
            gl.xlabel_style = {'size': 7}
            gl.ylabel_style = {'size': 7}
            gl.ylabels_bottom = False



        with akfigs.TrimmedPdf(ofname) as tname:
            fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off
        plt.close()
    # ---------------------------------------

    # Set up map to show South Central Alaska
    # Set up map to show South Central Alaska
    map_crs = akfigs.map_crs()
    mb = shapely.from_wkt('POLYGON ((-74568.1507070947 1607941.62451704,978745.51811548 1636969.95397279,991186.230739369 1048109.55644205,-49686.7254593174 1031521.9396102,-74568.1507070947 1607941.62451704))').bounds    # (minx, miny, maxx, maxy)
    map_extent = (mb[0], mb[2], mb[1], mb[3]) # xmin, xmax, ymin, ymax; ymin in South  (Same as fig04)

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(4,3))
#        figsize=(8.5,3.5))

    ax.set_extent(map_extent, map_crs)

    diff_data = fut_data - past_data
    print('vmin vmax ', np.min(diff_data), np.max(diff_data))

    cmap,_,_ = cptutil.read_cpt('palettes/seismic.cpt', reverse=False)
    fut_crs = cartopyutil.crs(fut_grid.wkt)
    pcm = ax.pcolormesh(
        fut_grid.centersx, fut_grid.centersy, diff_data,
        rasterized=True,
        transform=fut_crs, cmap=cmap, vmin=-250, vmax=250)#)#, cmap=cmap, vmin=, vmax=)

    finish_plot(fig, ax, 'snow_fut-past_sc.pdf')

    # ----------------
    # ---------- The colorbar
    fig,axs = plt.subplots(
        nrows=1,ncols=1,
        figsize=(8.5,3.5))
    cbar_ax = axs
    cbar = fig.colorbar(pcm, ax=cbar_ax, ticks=[-250,0,250])
    cbar.ax.set_yticklabels(['-250', '0 $kg/m^2$', '250'])
    cbar.ax.tick_params(labelsize=12)
    cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

    ofname = pathlib.Path('snow_fut-past_sc_cbar.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=300)   # Hi-res version; add margin so text is not cut off


main()
