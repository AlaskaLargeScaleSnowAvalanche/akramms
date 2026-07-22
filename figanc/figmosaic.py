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
from akramms.util import resultutil
import osmnx

#pub_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_publish')
pub_dir = expmod.root_dir / 'publish.v6'

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

def doplot(section, xdata_dir, city, ofname, map_extent=None, xyres=10, vminmax=None, cpt='palettes/WhiteBlueGreenYellowRed.cpt', ncpt=14, cbar_fname=None):

    print('BEGIN doplot() ', map_extent)
    print(type(map_extent.xxyy))
    print(type(map_extent))


    #xyres = 500

    map_crs = akfigs.map_crs()
    if map_extent is None:
        map_extent = akfigs.anchorage_map_extent    # gisutil.Extent
#    map_poly = shapely.geometry.box(me[0], me[2], me[1], me[3])    #xyxy

#    tiledf = expmod.gridD.intersecting_tiles(map_poly)

    print('doplot map_extent ', map_extent)

    tdir = pathlib.Path('./figmosaic_data')
    os.makedirs(tdir, exist_ok=True)

    dem_grid, dem_data, dem_nd = gdalutil.cache_raster(
        tdir / f'{city}_dem.tif', lambda: resultutil.read_subraster(
        expmod.gridD, expmod.dir / 'dem',
        f'{expmod.name}_dem_{{idom:03d}}_{{jdom:03d}}.tif',
        map_extent, xRes=xyres, yRes=xyres, resampleAlg='cubic'))

    vname = xdata_dir.parts[-1]
    xdata_grid, xdata_data, xdata_nd = gdalutil.cache_raster(
        tdir / f'{city}_{vname}.tif', lambda: resultutil.read_subraster(
        expmod.gridD, xdata_dir,
        f'{xdata_dir.parts[-2]}-{{idom:03d}}-{{jdom:03d}}-F-{vname}.tif',
        map_extent, xRes=xyres, yRes=xyres, resampleAlg='average'))

    landcover_grid, landcover_data, landcover_nd = gdalutil.cache_raster(
        tdir / f'{city}_landcover.tif', lambda: resultutil.read_subraster(
        expmod.gridD, expmod.dir / 'landcover',
        f'{expmod.name}_landcover_{{idom:03d}}_{{jdom:03d}}.tif',
        map_extent, xRes=xyres, yRes=xyres, resampleAlg='average'))





    if True:
        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(6.0,6.0))
        print('fffffffffff ', map_extent.xxyy)
        ax.set_extent(map_extent.xxyy, map_crs)
#        ax.set_facecolor((82./255,117./255,168./255))    # LANDSAT color for open water
        ax.set_facecolor((126./255,143./255,168./255))    # LANDSAT color for open water


        dem_data[dem_data <= 0] = np.nan    # Knock out ocean
        glacier_mask_in = (landcover_data == 12)

        # ------- Plot bed elevations EVERYWHERE
        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m
        print('dem_data shape ', dem_data.shape)

        ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 14, alpha=0.8)    # Use lev

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=map_extent, alpha=1.0)



        map_extent_ll = gisutil.transform_extent(map_extent, map_crs, cartopy.crs.PlateCarree())

        # Download building footprint
#        buildings = osmnx.features_from_bbox(map_extent_ll.xyxy, tags={"building": True})
#        buildings.plot(ax=ax, transform=ccrs.PlateCarree(), facecolor='lightgray', edgecolor='none', alpha=0.7)



#        # Download street network edges
#        roads = osmnx.graph_to_gdfs(osmnx.graph_from_bbox(map_extent_ll.xyxy, network_type="all"), nodes=False)
#        roads.plot(ax=ax, transform=ccrs.PlateCarree(), color='dimgray', linewidth=0.5)



    if True:
        # ---------- Plot land cover (only glaciated areas)
        glacier_data = np.zeros(dem_data.shape, dtype='d') + 1
        glacier_data[~glacier_mask_in] = np.nan    # Knock out non-glaciers
        glacier_cmap=matplotlib.colors.ListedColormap([(217/255.,232/255.,255/255.)])

        ax.pcolormesh(
            dem_grid.centersx, dem_grid.centersy,
            glacier_data,
            alpha=0.5, rasterized=True,
            transform=map_crs, cmap=glacier_cmap)


    if True:
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
            xdata_grid.centersx, xdata_grid.centersy,
            xdata_data, **kwargs)

        print('xxxxxxxx centers')
        print(xdata_grid.centersx[-10:])
        print(dem_grid.centersx[-10:])



    if True:
        # ---------- The colorbar
        if cbar_fname is not None:
            fig2,axs2 = plt.subplots(
                nrows=1,ncols=1,
        #        subplot_kw={'projection': map_crs},
                figsize=(5,5))
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


    if True:       
#        ofname = pathlib.Path('./figmosaic.pdf')
        print(f'Saving main plot to {ofname}')
        with TrimmedPdf(pathlib.Path(ofname)) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=300)   # Hi-res ver

        return






def main():


    eagle_river_poly = shapely.from_wkt('POLYGON ((233815.974524026 1272859.89287865,255285.501067563 1272859.89287865,255285.501067563 1254411.52725591,233815.974524026 1254411.52725591,233815.974524026 1272859.89287865))')
    eagle_river_extent = gisutil.Extent(*eagle_river_poly.bounds, order='xyxy')
    print('eagle_river_extent ', eagle_river_extent)

    for city, map_extent in (
        ('EagleRiver', eagle_river_extent),):

        xyres=30

        section = f'{expmod.name}-ccsm-past-sclapse-All-30'

        svar = 'max_height'
        xdata_dir = pub_dir / section / 'max_height'
        doplot(section, xdata_dir, city, f'figmosaic_{city}_max_height.pdf', map_extent=map_extent, xyres=xyres, vminmax=(0,3),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'figmosaic_{city}_{svar}_cbar.pdf')


        # 0-300 kPa scale same as used in Buehler paper:
        # https://nhess.copernicus.org/preprints/nhess-2022-11/nhess-2022-11-ATC1.pdf
        svar = 'max_pressure'
        xdata_dir = pub_dir / section / 'max_pressure'
        doplot(section, xdata_dir, city, f'figmosaic_{city}_max_pressure.pdf', map_extent=map_extent, xyres=xyres, vminmax=(0,300),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'figmosaic_{city}_{svar}_cbar.pdf')



        return



        svar = 'max_velocity'
        xdata_tif = pub_dir / section / 'max_velocity' / f'{section}-{idom:03d}-{jdom:03d}-F-{svar}.tif'
        doplot(section, xdata_tif, city, f'figmosaic_{city}_max_velocity.png', idom=idom, jdom=jdom, xyres=xyres, vminmax=(0,40),
            cpt='palettes/ath_2024.cpt', ncpt=10, cbar_fname=f'figmosaic_{svar}_cbar.pdf', delta_extent=delta_extent)







main()
