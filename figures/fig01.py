import os,pathlib,subprocess
import numpy as np
import cartopy
import shapely
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.ak as exp
from uafgi.util import wrfutil,cartopyutil,cptutil,gdalutil
import akfigs

from akramms import downscale_snow

ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'#pathlib.Path(os.environ['HOME']) / 'av/data/lader/sx3'
geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid


# \caption{Map of the study area including the Alaska panhandle.  The todo-color outline shows the domain used to run WRF to generate estimates of maximum snow depth.  The todo-color squares show \SI{30}{\kilo\meter} square \emph{tiles} used to divide the overall domain into computationally managable pieces.}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers
    map_extent = ((320-100)*1000, (1510+300)*1000, (710-300)*1000, (1425+100)*1000)    # xmin, xmax, ymin, ymax; ymin in South
#    map_extent = ((320-160)*1000, (1510+300)*1000, (710-390)*1000, (1425+200)*1000)    # xmin, xmax, ymin, ymax; ymin in South

#    map_extent = (-320000, 1510*1000, 110000, 1425*1000)    # xmin, xmax, ymin, ymax; ymin in South

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))
    ax.set_extent(map_extent, map_crs)

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 7, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # The tile squares
    shape_feature = cartopy.feature.ShapelyFeature(
        cartopy.io.shapereader.Reader(str(exp.dir / 'ak_domains.shp')).geometries(),
        map_crs)
    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)

    # The overall bounding box (as a Shapely polygon)
    snow_grid = wrfutil.wrf_info(geo_nc, wgs84=True)
    snow_crs = cartopyutil.crs(snow_grid.wkt)
#    snow_crs = cartopyutil.crs(wrfutil.grs1980_wkt)
#    snow_crs = cartopy.crs.epsg(3338)
    bbox = snow_grid.bounding_box()

    x0,x1,y0,y1 = (-638000.0000000000000000,642000, -502000.0000000000000000, 498000.)
    coords = [
        (x0,y0),
        (x1,y0),
        (x1,y1),
        (x0,y1),
        (x0,y0)]
    bbox = shapely.geometry.Polygon(coords)
    print('snow bbox ', bbox)
    print('snow wkt ', snow_grid.wkt)


    bbox_feature = cartopy.feature.ShapelyFeature(bbox, snow_crs)
    ax.add_feature(bbox_feature, facecolor='none', edgecolor='brown', lw=1.0, linestyle='--')


    # ----------- DEBUG
#    year0,year1 = (1981,2010)
#    snow_data,snow_nd = downscale_snow.read_sx3_multi(
#        [ccsm_dir / f'ccsm_sx3_{year}.nc' for year in range(year0,year1+1)])
#
#    #    print('Reading snow from ', ccsm_tif)
#    #    snow_grid, snow_data, snow_nd = gdalutil.read_raster(ccsm_tif)
#    snow_nd = -999.0    # Set snow_nd correctly

    snow_grid,snow_data,snow_nd = gdalutil.read_raster('/home/efischer/av/data/lader/sx3/ccsm_2006_sx3.tif')

    snow_data[snow_data == 0] = np.nan
    snow_data[snow_data == snow_nd] = np.nan
    vmin = 0#np.nanmin(snow_data)
    vmax = 700#np.nanmax(snow_data)
    print('Min Max sx3 ', np.nanmin(snow_data), np.nanmax(snow_data))

    # This follows E3SM convention for precip
    # See here for suggested colormaps
    # https://docs.e3sm.org/e3sm_diags/_build/html/master/colormaps.html
    cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
    cmap = cptutil.discrete_cmap(14, cmap)


    pcm_sx3 = ax.pcolormesh(
        snow_grid.centersx, snow_grid.centersy, snow_data,
        alpha=0.5, #rasterized=True,
        rasterized=True,
        transform=snow_crs, cmap=cmap, vmin=vmin, vmax=vmax)


    # ---------- Cities
    akfigs.plot_cities(ax,
        text_kwargs=dict(
            fontdict = {'size': 4, 'color': 'blue', 'fontweight': 'bold'}),
        marker_kwargs=dict(
            marker='*', markersize=2, color='black', alpha=0.9))

    ofname = pathlib.Path('./fig01.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

main()
