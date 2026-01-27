import os,pathlib,subprocess
import numpy as np
import cartopy
import cartopy.io.img_tiles
from osgeo import gdal
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.ak as exp
from akfigs import *
from uafgi.util import gdalutil,cptutil,ioutil,cartopyutil
import matplotlib.colors
import akfigs
# \caption{Elevation data from Juneau area}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def _discrete_cmap(N, base_cmap, nkeep):
    """Create an N-bin discrete colormap from the specified input map"""

    # Note that if base_cmap is a string or None, you can simply do
    #    return plt.cm.get_cmap(base_cmap, N)
    # The following works for string, None, or a colormap instance:

    base = matplotlib.pyplot.cm.get_cmap(base_cmap)
    color_list = base(np.linspace(0, 1, N))[:nkeep]
    cmap_name = base.name + str(N)
#    print('cccccccccccccccccccccccccccc ', color_list)
    return base.from_list(cmap_name, color_list, nkeep)


def main():
    map_crs = akfigs.map_crs()

    idom,jdom = (113,45)    # Juneau tile

    # Resample DEM to 100m resolution
    landcover_tif = exp.dir / 'landcover' / f'ak_landcover_{idom:03d}_{jdom:03d}.tif'
    dem_tif = exp.dir / 'dem' / f'ak_dem_{idom:03d}_{jdom:03d}.tif'
    print('dem_tif ', dem_tif)
    with ioutil.TmpDir() as tdir:
        xyres = 60    # Resample to 100m

        dem_tif_lr = tdir.location / dem_tif.parts[-1]
        ds = gdal.Warp(dem_tif_lr, dem_tif,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None

        landcover_tif_lr = tdir.location / landcover_tif.parts[-1]
        ds = gdal.Warp(landcover_tif_lr, landcover_tif,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None


        subgrid = exp.gridD.sub(idom, jdom, xyres, xyres, margin=True)
        map_extent = subgrid.extent(order='xxyy')

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(8.5,5.5))
        ax.set_extent(map_extent, map_crs)
#        ax.set_facecolor((20./255, 30./255, 53./255))
        ax.set_facecolor((82./255,117./255,168./255))    # LANDSAT color for open water


        landcover_grid, landcover_data, landcover_nd = gdalutil.read_raster(landcover_tif_lr)

        dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif_lr)
        dem_data[dem_data <= 0] = np.nan    # Knock out ocean
        glacier_mask_in = (landcover_data == 12)

        # ------- Plot bed elevations EVERYWHERE
        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m
        cmap = _discrete_cmap(10, cmap,6)
        print('dem_data shape ', dem_data.shape)
#        dem_data[0:300, 0:300] = 0
#        dem_data[300:600, 0:300] = 20

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=map_extent)


        dem_data[glacier_mask_in] = np.nan    # Knock out glaciers
        pcm_elev = ax.pcolormesh(
            subgrid.centersx, subgrid.centersy, dem_data,
            alpha=0.5, rasterized=True,
            transform=map_crs, cmap=cmap, vmin=0, vmax=1200)


#        ofname = pathlib.Path('./fig02.png')
#        with TrimmedPng(ofname) as tname:
#            fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

#        gdalutil.write_raster('dem50.tif', subgrid, dem_data, dem_nd)


        # ---------- Plot land cover
        glacier_data = np.zeros(dem_data.shape, dtype='d') + 1
        glacier_data[~glacier_mask_in] = np.nan    # Knock out non-glaciers
        glacier_cmap=matplotlib.colors.ListedColormap([(217/255.,232/255.,255/255.)])
#        glacier_cmap=matplotlib.colors.ListedColormap(['green'])

        ax.pcolormesh(
            subgrid.centersx, subgrid.centersy, glacier_data,
            alpha=0.5, rasterized=True,
            transform=map_crs, cmap=glacier_cmap)

        # Add graticules
        gl = ax.gridlines(draw_labels=True,
              linewidth=0.3, color='white', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
        gl.xlabel_style = {'size': 8}
        gl.ylabel_style = {'size': 8}
        gl.ylabels_right = False

        ofname = pathlib.Path('./fig02.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res ver

        # ---------- The colorbar
        fig,axs = plt.subplots(
            nrows=1,ncols=1,
    #        subplot_kw={'projection': map_crs},
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
    imap_extent = akfigs.sealaska_map_extent

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
