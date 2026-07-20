import akfigs,time
import os,pathlib,subprocess,glob
import numpy as np
import shapely,cartopy
import cartopy.io.img_tiles
from osgeo import gdal
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.aksc5 as expmod
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


#def doplot(section, xdata_tif, ofname, map_extent=None, idom=113, jdom=45, xyres=10, vminmax=None, cpt='palettes/WhiteBlueGreenYellowRed.cpt', ncpt=14, cbar_fname=None, delta_extent=None):

def doplot(section, xdata_dir, ofname, map_extent=None, xyres=10, vminmax=None, cpt='palettes/WhiteBlueGreenYellowRed.cpt', ncpt=14, cbar_fname=None, delta_extent=None):

    xyres = 1000


    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

    map_crs = akfigs.map_crs()
    map_extent = me = akfigs.anchorage_map_extent    # xxyy
    map_poly = shapely.geometry.box(me[0], me[2], me[1], me[3])    #xyxy

    tiledf = expmod.gridD.intersecting_tiles(map_poly)



    # Resample DEM to 100m resolution
    with ioutil.TmpDir(remove=False) as tdir:
        os.makedirs(tdir.location, exist_ok=True)
        time.sleep(1)

        # -------------- The Data
        xdata_vrt = tdir.location / 'data.vrt'
        files = [xdata_dir / f'{xdata_dir.parts[-2]}-{tup.idom:03d}-{tup.jdom:03d}-F-{xdata_dir.parts[-1]}.tif' for tup in tiledf.itertuples()]
        gdalutil.build_vrt(files, xdata_vrt)


        print('AA0')
        dem_tif_lr = tdir.location / (dem_vrt.parts[-1][:-4] + '.tif')
        print('dem_tif_lr ', dem_tif_lr)
        print('BEGIN warp dem')
        ds = gdal.Warp(dem_tif_lr, dem_vrt,
            outputBounds=map_extent,
            xRes=xyres, yRes=xyres, resampleAlg='nearest')
        ds = None
        print('AA1')

    return



    landcover_dir = expmod.dir / 'landcover'
    landcover_vrt = landcover_dir / f'{expmod.name}_landcover.vrt'
    gdalutil.build_vrt(sorted(list(glob.glob(f'{landcover_dir}/*.tif'))), landcover_vrt)
    print('BB2')

    dem_dir = expmod.dir / 'dem'
    dem_vrt = dem_dir / f'{expmod.name}_dem.vrt'
    gdalutil.build_vrt(sorted(list(glob.glob(f'{dem_dir}/{expmod.name}_dem_???_???.tif'))), dem_vrt)
    print('BB3')
    # -------------------------------------------






    if True:
        print('AA1')
        landcover_tif_lr = tdir.location / (landcover_vrt.parts[-1][:-4] + '.tif')
        ds = gdal.Warp(landcover_tif_lr, landcover_vrt,
            outputBounds=map_extent,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None

        print('AA2')
        xdata_tif_lr = tdir.location / (xdata_vrt.parts[-1][:-4] + '.tif')
        ds = gdal.Warp(xdata_tif_lr, xdata_vrt,
            outputBounds=map_extent,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None
        print('AA3')





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
        if delta_extent is not None:
            map_extent = [a+b for a,b in zip(map_extent, delta_extent)]
        print('map_extent ', map_extent)

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(3.0,3.0))
        ax.set_extent(map_extent, map_crs)
#        ax.set_facecolor((82./255,117./255,168./255))    # LANDSAT color for open water
        ax.set_facecolor((126./255,143./255,168./255))    # LANDSAT color for open water


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

       
#        ofname = pathlib.Path('./figmosaic.pdf')
        print(f'Saving main plot to {ofname}')
        with TrimmedPng(pathlib.Path(ofname)) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=300)   # Hi-res ver

        return






def main():


    eagle_river_poly = shapely.from_wkt('POLYGON ((233815.974524026 1272859.89287865,255285.501067563 1272859.89287865,255285.501067563 1254411.52725591,233815.974524026 1254411.52725591,233815.974524026 1272859.89287865))')
    xt = eagle_river_poly.bounds    # minx, miny, maxx, maxy
    eagle_river_extent = (xt[0], xt[2], xt[1], xt[3])

    for city, map_extent in (
        ('EagleRiver', eagle_river_extent),):

        xyres=10

        section = f'{expmod.name}-ccsm-past-sclapse-All-30'

        svar = 'max_height'
        xdata_dir = pub_dir / section / 'max_height'
        doplot(section, xdata_dir, f'figmosaic_{city}_max_height.png', map_extent=map_extent, xyres=xyres, vminmax=(0,3),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'figmosaic_{svar}_cbar.pdf')


        return


        # 0-300 kPa scale same as used in Buehler paper:
        # https://nhess.copernicus.org/preprints/nhess-2022-11/nhess-2022-11-ATC1.pdf
        svar = 'max_pressure'
        xdata_tif = pub_dir / section / 'max_pressure' / f'{section}-{idom:03d}-{jdom:03d}-F-{svar}.tif'
        doplot(section, xdata_tif, f'figmosaic_{city}_max_pressure.png', idom=idom, jdom=jdom, xyres=xyres, vminmax=(0,300),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'figmosaic_{svar}_cbar.pdf', delta_extent=delta_extent)

        svar = 'max_velocity'
        xdata_tif = pub_dir / section / 'max_velocity' / f'{section}-{idom:03d}-{jdom:03d}-F-{svar}.tif'
        doplot(section, xdata_tif, f'figmosaic_{city}_max_velocity.png', idom=idom, jdom=jdom, xyres=xyres, vminmax=(0,40),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'figmosaic_{svar}_cbar.pdf', delta_extent=delta_extent)







main()
