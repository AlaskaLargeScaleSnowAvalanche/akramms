import os,pathlib,subprocess
import numpy as np
import cartopy
import cartopy.io.img_tiles
from osgeo import gdal
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.akse as expmod
from akramms import archive
from akfigs import *
from uafgi.util import gdalutil,cptutil,ioutil,cartopyutil,gisutil
import matplotlib.colors
import geopandas
# \caption{Elevation data from Juneau area}

#pub_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_publish')
pub_dir = expmod.root_dir / 'publish'

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def colorbar():

        # ---------- The colorbar
        fig,axs = plt.subplots(
            nrows=1,ncols=1,
    #        subplot_kw={'projection': map_crs},
            figsize=(2.5,2.5))
        cbar_ax = axs
        cbar = fig.colorbar(pcm_elev, ax=cbar_ax)
        cbar.ax.tick_params(labelsize=20)
        cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

        ofname = pathlib.Path('geo_cbar.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off


def doplot(section, xdata_tif, ofname, map_extent=None, idom=113, jdom=45, xyres=10, vminmax=None, cpt='palettes/WhiteBlueGreenYellowRed.cpt', ncpt=14, cbar_fname=None):
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

#    idom,jdom = (113,45)    # Juneau tile

    landcover_tif = expmod.dir / 'landcover' / f'{expmod.name}_landcover_{idom:03d}_{jdom:03d}.tif'
#    release_zip = expmod.dir / f'{expmod.name}-ccsm-1981-2010-lapse-For-30' / f'arc-{idom:03d}-{jdom:03d}' / 'RELEASE.zip'

    # Resample DEM to 100m resolution
    dem_tif = expmod.dir / 'dem' / f'{expmod.name}_dem_{idom:03d}_{jdom:03d}.tif'
    print('dem_tif ', dem_tif)
    with ioutil.TmpDir() as tdir:
#        xyres = 10    # Resample to 100m

        dem_tif_lr = tdir.location / dem_tif.parts[-1]
        ds = gdal.Warp(dem_tif_lr, dem_tif,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None

        landcover_tif_lr = tdir.location / landcover_tif.parts[-1]
        ds = gdal.Warp(landcover_tif_lr, landcover_tif,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None

        xdata_tif_lr = tdir.location / xdata_tif.parts[-1]
        ds = gdal.Warp(xdata_tif_lr, xdata_tif,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None


        tilegrid = expmod.gridD.sub(idom, jdom, xyres, xyres, margin=False)
        tile_extent = tilegrid.extent(order='xxyy')    # INCUDES margin

        mtilegrid = expmod.gridD.sub(idom, jdom, xyres, xyres, margin=True)
        mtile_extent = mtilegrid.extent(order='xxyy')    # INCUDES margin
        print('mtile_extent ', mtile_extent)
        x0,x1,y0,y1 = mtile_extent
        dmx,dmy = expmod.gridD.domain_margin
        if map_extent is None:
            map_extent = tile_extent
#        map_extent = (x0+dmx+7000, x1-dmx-13000, y0+dmy+10000, y1-dmy-10000)
        print('map_extent ', map_extent)

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(3.0,3.0))
        ax.set_extent(map_extent, map_crs)
        ax.set_facecolor((82./255,117./255,168./255))    # LANDSAT color for open water


        landcover_grid, landcover_data, landcover_nd = gdalutil.read_raster(landcover_tif_lr)
        xdata_grid, xdata_data, xdata_nd = gdalutil.read_raster(xdata_tif_lr)
        print('xdata min max ', np.nanmin(xdata_data), np.nanmax(xdata_data))

        dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif_lr)
        dem_data[dem_data <= 0] = np.nan    # Knock out ocean
        glacier_mask_in = (landcover_data == 12)

        # ------- Plot bed elevations EVERYWHERE
        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m
        print('dem_data shape ', dem_data.shape)

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=mtile_extent)


        # ---------- Plot land cover (only glaciated areas)
        glacier_data = np.zeros(dem_data.shape, dtype='d') + 1
        glacier_data[~glacier_mask_in] = np.nan    # Knock out non-glaciers
        glacier_cmap=matplotlib.colors.ListedColormap([(217/255.,232/255.,255/255.)])

        ax.pcolormesh(
            mtilegrid.centersx, mtilegrid.centersy,
            glacier_data,
            alpha=0.5, rasterized=True,
            transform=map_crs, cmap=glacier_cmap)


        # Plot actual data
        xdata_data[xdata_data == 0] = np.nan
#        cmap,_,_ = cptutil.read_cpt('palettes/YlOrRd_09.cpt')
        cmap,_,_ = cptutil.read_cpt(cpt)
        cmap = cptutil.discrete_cmap(ncpt, cmap)

        kwargs = dict(
            alpha=0.5, rasterized=True,
            transform=map_crs, cmap=cmap)
        if vminmax is not None:
            kwargs['vmin'] = vminmax[0]
            kwargs['vmax'] = vminmax[1]
        print('Plotting with kwargs ', kwargs)
        pcm = ax.pcolormesh(
            tilegrid.centersx, tilegrid.centersy,
            xdata_data, **kwargs)


        # ---------- The colorbar
        if cbar_fname is not None:
            fig2,axs2 = plt.subplots(
                nrows=1,ncols=1,
        #        subplot_kw={'projection': map_crs},
                figsize=(2.5,2.5))
            cbar_ax = axs2
            cbar = fig2.colorbar(pcm, ax=cbar_ax)
            cbar.ax.tick_params(labelsize=8)
            cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

#            ofname = pathlib.Path('geo_cbar.pdf')
            with TrimmedPdf(cbar_fname) as tname:
                fig2.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off



#        # ---------- Plot Extent
#        extent_shp = pub_dir / section / 'extent' / f'{section}-{idom:d}-{jdom:d}-F-extent.shp'
#        extdf = geopandas.read_file(str(extent_shp))
#        for pra in extdf.geometry:
#            pra_feature = cartopy.feature.ShapelyFeature(pra, map_crs)
#            ax.add_feature(pra_feature, facecolor=None, edgecolor='black', lw=0.3)

       
#        ofname = pathlib.Path('./fig12.pdf')
        print(f'Saving main plot to {ofname}')
        with TrimmedPng(pathlib.Path(ofname)) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res ver

        return






def main():
    for idom,jdom,city in ((110,42,'Haines'), (113,45,'Juneau')):
        xyres=20

        section = f'{expmod.name}-ccsm-1981-2010-lapse-All-30'

        svar = 'max_height'
        xdata_tif = pub_dir / section / 'max_height' / f'{section}-{idom:03d}-{jdom:03d}-F-{svar}.tif'
        doplot(section, xdata_tif, f'fig12_{city}_max_height.png', idom=idom, jdom=jdom, xyres=xyres, vminmax=(0,3),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'fig12_{svar}_cbar.pdf')

        # 0-300 kPa scale same as used in Buehler paper:
        # https://nhess.copernicus.org/preprints/nhess-2022-11/nhess-2022-11-ATC1.pdf
        svar = 'max_pressure'
        xdata_tif = pub_dir / section / 'max_pressure' / f'{section}-{idom:03d}-{jdom:03d}-F-{svar}.tif'
        doplot(section, xdata_tif, f'fig12_{city}_max_pressure.png', idom=idom, jdom=jdom, xyres=xyres, vminmax=(0,300),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'fig12_{svar}_cbar.pdf')

        svar = 'max_velocity'
        xdata_tif = pub_dir / section / 'max_velocity' / f'{section}-{idom:03d}-{jdom:03d}-F-{svar}.tif'
        doplot(section, xdata_tif, f'fig12_{city}_max_velocity.png', idom=idom, jdom=jdom, xyres=xyres, vminmax=(0,40),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'fig12_{svar}_cbar.pdf')







main()
