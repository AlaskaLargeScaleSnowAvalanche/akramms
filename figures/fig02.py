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
# \caption{Elevation data from Juneau area}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

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
            transform=map_crs, cmap=cmap, vmin=0, vmax=2000)


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
        
        ofname = pathlib.Path('./fig02.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res ver

        # ---------- The colorbar
        fig,axs = plt.subplots(
            nrows=1,ncols=1,
    #        subplot_kw={'projection': map_crs},
            figsize=(8.5,5.5))
        cbar_ax = axs
        cbar = fig.colorbar(pcm_elev, ax=cbar_ax)
        cbar.ax.tick_params(labelsize=20)
        cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

        ofname = pathlib.Path('geo_cbar.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off




main()
