import os,pathlib,subprocess
import cartopy
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.ak as exp
from uafgi.util import gdalutil
from akfigs import *


# \caption{Map of the study area including the Alaska panhandle.  The todo-color outline shows the domain used to run WRF to generate estimates of maximum snow depth.  The todo-color squares show \SI{30}{\kilo\meter} square \emph{tiles} used to divide the overall domain into computationally managable pieces.}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

ccsm_tif = pathlib.Path(os.environ['HOME']) / 'av/data/lader/sx3' / 'ccsm_2010_sx3.tif'

def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers
    map_extent = (320000, 1510*1000, 710000, 1425*1000)    # xmin, xmax, ymin, ymax; ymin in South

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))
    ax.set_extent(map_extent, map_crs)


    snow_grid, snow_data, snow_nd = gdalutil.read_raster(ccsm_tif)
    pcm_elev = ax.pcolormesh(
        snow_grid.centersx, snow_grid.centersy, snow_data,
        alpha=0.5, rasterized=True,
        transform=map_crs)#, cmap=cmap, vmin=0, vmax=2000)


#    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 7, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

#    shape_feature = cartopy.feature.ShapelyFeature(
#        cartopy.io.shapereader.Reader(str(exp.dir / 'ak_domains.shp')).geometries(),
#        map_crs)
#
#    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)


    # Plot Juneau and other cities
    # https://scitools.org.uk/cartopy/docs/latest/tutorials/understanding_transform.html
    for lon, lat, city_name in SECities:
#        lon,lat = (-134.4201, 58.3005)
        ax.plot(lon, lat, transform=cartopy.crs.PlateCarree(), marker='o', markersize=2, color='blue', alpha=0.5)
        # https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.text.html
        ax.text(lon, lat, f'  {city_name}', transform=cartopy.crs.PlateCarree(),
            fontdict = {'size': 4, 'color': 'black'})

    ofname = pathlib.Path('./fig04.pdf')
    with TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

main()
