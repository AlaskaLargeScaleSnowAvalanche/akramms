import os,pathlib,subprocess
import cartopy
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.ak as exp
from uafgi.util import wrfutil,cartopyutil,gisutil
import akfigs
import shapely.geometry

ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'#pathlib.Path(os.environ['HOME']) / 'av/data/lader/sx3'
geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid


# \caption{Map of the study area including the Alaska panhandle.  The todo-color outline shows the domain used to run WRF to generate estimates of maximum snow depth.  The todo-color squares show \SI{30}{\kilo\meter} square \emph{tiles} used to divide the overall domain into computationally managable pieces.}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def main():
    map_crs = akfigs.map_crs()

#    map_extent = ((320-180)*1000, 1670*1000, 300*1000, (1425+230)*1000)    # xmin, xmax, ymin, ymax; ymin in South
    map_extent = akfigs.sealaska_map_extent
    print('map_extent ', map_extent)

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,11.))
    ax.set_extent(map_extent, crs=map_crs)

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 7, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # The tile squares
    shape_feature = cartopy.feature.ShapelyFeature(
        cartopy.io.shapereader.Reader(str(exp.dir / 'ak_domains.shp')).geometries(),
        map_crs)
    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)

    # The overall bounding box (as a Shapely polygon)
    bbox_feature = akfigs.wrf_bbox_feature()
    ax.add_feature(bbox_feature, facecolor='none', edgecolor='brown', lw=1.0, linestyle='--')


    akfigs.plot_cities(ax,
        text_kwargs=dict(
            fontdict = {'size': 8, 'color': 'blue', 'fontweight': 'bold'}),
        marker_kwargs=dict(
            marker='*', markersize=2, color='black', alpha=0.9))

    # Add graticules
    gl = ax.gridlines(draw_labels=True,
          linewidth=0.3, color='gray', alpha=0.5, x_inline=False, y_inline=False, dms=True, linestyle='-')
    gl.xlabel_style = {'size': 9}
    gl.ylabel_style = {'size': 9}

    ofname = pathlib.Path('./fig01.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off


    # ==================================================================
    # Make the inset map
    imap_extent = akfigs.allalaska_map_extent

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(3.0,2.0))
    ax.set_extent(imap_extent, crs=map_crs)

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 6, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # The overall bounding box
    ax.add_feature(bbox_feature, facecolor='none', edgecolor='brown', lw=1.0, linestyle='--')


    # The original map bounds
    map_extent_poly = gisutil.xxyy_to_poly(*map_extent)
#    x0,x1,y0,y1 = map_extent
#    map_extent_poly = shapely.geometry.Polygon([
#            (x0,y0),
#            (x1,y0),
#            (x1,y1),
#            (x0,y1),
#            (x0,y0)])
    map_extent_feature = cartopy.feature.ShapelyFeature(map_extent_poly, map_crs)
    ax.add_feature(map_extent_feature, facecolor='none', edgecolor='black', lw=1.0)

    # Outline this map
    x0,x1,y0,y1 = imap_extent
    imap_extent_poly = shapely.geometry.Polygon([
            (x0,y0),
            (x1,y0),
            (x1,y1),
            (x0,y1),
            (x0,y0)])
    imap_extent_feature = cartopy.feature.ShapelyFeature(imap_extent_poly, map_crs)
    ax.add_feature(imap_extent_feature, facecolor='none', edgecolor='black', lw=2.0)



    ofname = pathlib.Path('./fig01-inset.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off

main()
