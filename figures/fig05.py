import os,pathlib,subprocess
import cartopy,geopandas
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.ak as exp
from uafgi.util import wrfutil,cartopyutil,gisutil
import akfigs


ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'#pathlib.Path(os.environ['HOME']) / 'av/data/lader/sx3'
geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid


# \caption{Map of the study area including the Alaska panhandle.  The todo-color outline shows the domain used to run WRF to generate estimates of maximum snow depth.  The todo-color squares show \SI{30}{\kilo\meter} square \emph{tiles} used to divide the overall domain into computationally managable pieces.}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def main():
    #map_crs = cartopy.crs.epsg(3338)    # Alaska Albers
    map_crs = akfigs.map_crs()
    map_extent = ((320-30)*1000, (1510+0)*1000, (710-0)*1000, (1425+30)*1000)    # xmin, xmax, ymin, ymax; ymin in South

#    map_extent = (-320000, 1510*1000, 110000, 1425*1000)    # xmin, xmax, ymin, ymax; ymin in South

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(7.2,5.5))
    ax.set_extent(map_extent, map_crs)

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 7, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # The tile squares (plot for map)
    shape_feature = cartopy.feature.ShapelyFeature(
        cartopy.io.shapereader.Reader(str(exp.dir / 'ak_domains.shp')).geometries(),
        map_crs)
    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)


#    snow_grid = wrfutil.wrf_info(geo_nc)
#    snow_crs = cartopyutil.crs(snow_grid.wkt)

    # Read the tile squares for our own analysis
    tile_df = geopandas.read_file(str(exp.dir / 'ak_domains.shp'))


    # Plot jdom numbers
    for jdom,col_df in tile_df.groupby('jdom'):

        if jdom <= 43:
            idom = 87
        elif jdom in (44,45):
            idom = col_df.idom.nsmallest(2).iloc[-1]    # Second smallest
        else:
            idom = col_df.idom.min()


        tile_grid = exp.gridD.sub(idom,jdom, 10,10, margin=False)
        
        GT = exp.gridD.geotransform
        x0 = GT[0] + GT[1] * idom
        y0 = GT[3] + GT[5] * jdom

        y = y0 + 0.5 * exp.gridD.dy
        x = x0 - 1000   # Margin for text

        ax.text(x,y, f'{jdom}', transform=map_crs, verticalalignment='center_baseline', horizontalalignment='right',
            fontdict={'size':8})


    # Plot idom numbers
    for idom,col_df in tile_df.groupby('idom'):

        if idom <= 98:
            jdom = 35
        else:
            jdom = col_df.jdom.min()

        tile_grid = exp.gridD.sub(idom,jdom, 10,10, margin=False)
        
        GT = exp.gridD.geotransform
        x0 = GT[0] + GT[1] * idom
        y0 = GT[3] + GT[5] * jdom

        x = x0 + 0.5 * exp.gridD.dx
        y = y0 + 1000    # Margin

        ax.text(x,y, f'{idom}', transform=map_crs,
            rotation=90,
            horizontalalignment='center', verticalalignment='bottom',
            fontdict={'size':8})




#    print(tiles_df)

#    # The overall bounding box (as a Shapely polygon)
#    snow_grid = wrfutil.wrf_info(geo_nc)
#    snow_crs = cartopyutil.crs(snow_grid.wkt)
#    bbox = snow_grid.bounding_box()
#    bbox_feature = cartopy.feature.ShapelyFeature(bbox, snow_crs)
#    ax.add_feature(bbox_feature, facecolor='none', edgecolor='brown', lw=1.0, linestyle='--')


    akfigs.plot_cities(ax,
        text_kwargs=dict(
            fontdict = {'size': 8, 'color': 'blue', 'fontweight': 'bold'}),
        marker_kwargs=dict(
            marker='*', markersize=2, color='black', alpha=0.9))

    # Add graticules
    gl = ax.gridlines(draw_labels=True,
          linewidth=0.3, color='grey', alpha=0.5, x_inline=False, y_inline=False, dms=True, linestyle='-')
    gl.xlabel_style = {'size': 9}
    gl.ylabel_style = {'size': 9}
    gl.ylabels_bottom = False


    ofname = pathlib.Path('./fig05.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off



    # ==================================================================
    # Make the inset map
#    imap_extent = (-820*1000, 1900*1000, 0*1000, 2400*1000)
    # Same as fig01 map_extent, 
    imap_extent = (-820*1000, 2500*1000, -100*1000, 2400*1000)
#    imap_extent = akfigs.allalaska_map_extent

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


    ofname = pathlib.Path('./fig05-inset.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off





main()
