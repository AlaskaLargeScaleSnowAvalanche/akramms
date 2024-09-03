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
# \caption{Elevation data from Juneau area}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

    idom,jdom = (113,45)    # Juneau tile

    # Resample DEM to 100m resolution
    dem_tif = exp.dir / 'dem' / f'ak_dem_{idom:03d}_{jdom:03d}.tif'
    snow_tif = exp.dir / 'snow' / f'ak_ccsm_1981_2010_lapse_{idom:03d}_{jdom:03d}.tif'
    print('dem_tif ', dem_tif)
    with ioutil.TmpDir() as tdir:
        xyres = 60    # Resample to 100m

        dem_tif_lr = tdir.location / dem_tif.parts[-1]
        ds = gdal.Warp(dem_tif_lr, dem_tif,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None

#        snow_tif_lr = snow_tif    # For some reason gdalwarp isn't working here
        snow_tif_lr = tdir.location / snow_tif.parts[-1]
        ds = gdal.Warp(snow_tif_lr, snow_tif,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None

        subgrid = exp.gridD.sub(idom, jdom, xyres, xyres, margin=True)
        map_extent = subgrid.extent(order='xxyy')

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(8.5,5.5))
        ax.set_extent(map_extent, map_crs)
        ax.set_facecolor((20./255, 30./255, 53./255))


        dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif_lr)
        dem_data[dem_data <= 0] = np.nan


        # ------- Plot bed elevations EVERYWHERE
#        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=map_extent)

        # ---------- Plot snow
        # This follows E3SM convention for precip
        # See here for suggested colormaps
        # https://docs.e3sm.org/e3sm_diags/_build/html/master/colormaps.html
        cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
        cmap = cptutil.discrete_cmap(14, cmap)

        snow_grid, snow_data, snow_nd = gdalutil.read_raster(snow_tif_lr)
        vmin = np.nanmin(snow_data)
        vmax = np.nanmax(snow_data)
        print('vmin vmax ', vmin, vmax)
        pcm_snow = ax.pcolormesh(
            subgrid.centersx, subgrid.centersy, snow_data,
            alpha=0.5, rasterized=True,
            transform=map_crs, cmap=cmap, vmin=0, vmax=700)

        ofname = pathlib.Path('./fig07.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off

#        # ---------- The colorbar
#        fig,axs = plt.subplots(
#            nrows=1,ncols=1,
#    #        subplot_kw={'projection': map_crs},
#            figsize=(8.5,5.5))
#        cbar_ax = axs
#        cbar = fig.colorbar(pcm_elev, ax=cbar_ax)
#        cbar.ax.tick_params(labelsize=20)
#        cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately
#
#        ofname = pathlib.Path('geo_cbar.pdf')
#        with TrimmedPdf(ofname) as tname:
#            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off




main()
