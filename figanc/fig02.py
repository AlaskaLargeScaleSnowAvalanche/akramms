import os,pathlib,subprocess
import numpy as np
import cartopy
import cartopy.io.img_tiles
from osgeo import gdal
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.aksc5 as exp
from akfigs import *
from uafgi.util import gdalutil,cptutil,ioutil,cartopyutil
import matplotlib.colors
import matplotlib.patheffects
import akfigs
from osgeo_utils import gdal_calc
# \caption{Elevation data from Juneau area}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D


def main():
    map_crs = akfigs.map_crs()

    map_extent = akfigs.anchorage_map_extent

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))
    ax.set_extent(map_extent, map_crs)
    ax.set_facecolor((82./255,117./255,168./255))    # LANDSAT color for open water


    with ioutil.TmpDir() as tdir:

        dem_tif_lr, landcover_tif_lr = akfigs.resample_lr(
            expmod, expmod.anchorage_tiles(), tdir,
            vars=['dem', 'landcover'])

        dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif_lr)
        landcover_grid, landcover_data, landcover_nd = gdalutil.read_raster(landcover_tif_lr)
        dem_data[dem_data <= 0] = np.nan    # Knock out ocean
        glacier_mask_in = (landcover_data == 12)

        # ------- Plot bed elevations EVERYWHERE
        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m
        cmap = cptutil.discrete_cmap(10, base_cmap=cmap, nkeep=6)
        print('dem_data shape ', dem_data.shape)

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=dem_grid.extent())


        if True:
            dem_data[glacier_mask_in] = np.nan    # Knock out glaciers
            pcm_elev = ax.pcolormesh(
                dem_grid.centersx, dem_grid.centersy, dem_data,
                alpha=0.5, rasterized=True,
                transform=map_crs, cmap=cmap, vmin=0, vmax=1200)



        # ---------- Plot land cover
        glacier_data = np.zeros(dem_data.shape, dtype='d') + 1
        glacier_data[~glacier_mask_in] = np.nan    # Knock out non-glaciers
        glacier_cmap=matplotlib.colors.ListedColormap([(217/255.,232/255.,255/255.)])

        ax.pcolormesh(
            dem_grid.centersx, dem_grid.centersy, glacier_data,
            alpha=0.3, rasterized=True,
            transform=map_crs, cmap=glacier_cmap)


        akfigs.plot_cities(ax, 'anchorage',
            text_kwargs=dict(
                fontdict = {'size': 7, 'color': 'black', 'fontweight': 'bold',
#                'alpha': 0.8,
                'path_effects': [matplotlib.patheffects.withStroke(linewidth=2, foreground="white")]}),
            marker_kwargs=dict(
                marker='*', markersize=2, color='white', alpha=0.9))


        # Add graticules
        if True:
            gl = ax.gridlines(draw_labels=True,
                  linewidth=0.3, color='white', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
            gl.xlocator = matplotlib.ticker.MultipleLocator(0.5)    # lon gridlines every 0.5 deg
            gl.xlabel_style = {'size': 8}
            gl.ylabel_style = {'size': 8}
            gl.ylabels_right = False

    ofname = pathlib.Path('./fig02.pdf')
    with TrimmedPdf(ofname) as tname:
        fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=300)   # Hi-res ver
#    ofname = pathlib.Path('./fig02.pdf')
#    with TrimmedPdf(ofname) as tname:
#        fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res ver

    # ---------- The colorbar
    if True:
        fig,axs = plt.subplots(
            nrows=1,ncols=1,
#            subplot_kw={'projection': map_crs},
            figsize=(8.5,5.5))
        cbar_ax = axs
        cbar = fig.colorbar(pcm_elev, ax=cbar_ax, ticks=[0,200,400,600,800,1000,1200])
        cbar.ax.set_yticklabels(['0 m', '200', '400', '600', '800', '1000', '1200 m',])
        cbar.ax.tick_params(labelsize=12)
        cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

        ofname = pathlib.Path('geo_cbar.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off


    # ==================================================================
    # Make the inset map
#    imap_extent = (-820*1000, 1900*1000, 0*1000, 2400*1000)
    # Same as fig01 map_extent, 
    imap_extent = akfigs.anchorage_map_extent

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


    ofname = pathlib.Path('./fig02-inset.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off



main()
