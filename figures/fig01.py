import os,pathlib,subprocess
import cartopy
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.ak as exp
from uafgi.util import wrfutil,cartopyutil
import akfigs


ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'#pathlib.Path(os.environ['HOME']) / 'av/data/lader/sx3'
geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid


# \caption{Map of the study area including the Alaska panhandle.  The todo-color outline shows the domain used to run WRF to generate estimates of maximum snow depth.  The todo-color squares show \SI{30}{\kilo\meter} square \emph{tiles} used to divide the overall domain into computationally managable pieces.}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers
    map_extent = ((320-100)*1000, (1510+300)*1000, (710-300)*1000, (1425+100)*1000)    # xmin, xmax, ymin, ymax; ymin in South

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
    snow_grid = wrfutil.wrf_info(geo_nc)
    snow_crs = cartopyutil.crs(snow_grid.wkt)
    bbox = snow_grid.bounding_box()
    bbox_feature = cartopy.feature.ShapelyFeature(bbox, snow_crs)
    ax.add_feature(bbox_feature, facecolor='none', edgecolor='brown', lw=1.0, linestyle='--')


    akfigs.plot_cities(ax,
        text_kwargs=dict(
            fontdict = {'size': 4, 'color': 'blue', 'fontweight': 'bold'}),
        marker_kwargs=dict(
            marker='*', markersize=2, color='black', alpha=0.9))

    ofname = pathlib.Path('./fig01.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

main()
