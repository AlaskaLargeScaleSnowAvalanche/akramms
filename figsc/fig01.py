import os,pathlib,subprocess
import cartopy,geopandas
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.aksc5 as exp
from uafgi.util import wrfutil,cartopyutil,gisutil
import akfigs


# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def main():
    map_crs = akfigs.map_crs()
    map_extent = list(akfigs.anchorage_map_extent)
    map_extent[0] -= 5000
    map_extent[-1] += 5000

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(7.2,5.5))
    ax.set_extent(map_extent, map_crs)

    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 9, alpha=1)    # Use level 7 (lower # is coarser)
#    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    # Read the tile squares for our own analysis
    ijdom = {(combo.idom, combo.jdom) for combo in exp.anchorage()}
    tile_df = geopandas.read_file(str(exp.dir / 'aksc5_domains.shp'))
    ijdom_col = tile_df.apply(lambda row: (row.idom,row.jdom), axis=1)
    tile_df = tile_df[ijdom_col.isin(ijdom)]

#    for tile in tile_df.geometry:
#        print(tile.bounds)
#    return

    # The tile squares (plot for map)
    shape_feature = cartopy.feature.ShapelyFeature(
        list(tile_df.geometry),
#        cartopy.io.shapereader.Reader(str(exp.dir / 'aksc5_domains.shp')).geometries(),
        map_crs)
    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)

    # Determine set of idom/jdom in our run


    # Plot jdom numbers
    for jdom,col_df in tile_df.groupby('jdom'):

#        if jdom <= 43:
#            idom = 87
#        elif jdom in (44,45):
#            idom = col_df.idom.nsmallest(2).iloc[-1]    # Second smallest
#        else:
        if True:
            idom = col_df.idom.min()


        tile_grid = exp.gridD.sub(idom,jdom, 10,10, margin=False)

        GT = exp.gridD.geotransform
        x0 = GT[0] + GT[1] * idom
        y0 = GT[3] + GT[5] * jdom

        y = y0 + 0.5 * exp.gridD.dy
        x = x0 - 1000   # Margin for text

        ax.text(
            x,y, f'{jdom}',
            fontweight='bold',
            transform=map_crs, verticalalignment='center_baseline', horizontalalignment='right',
            fontdict={'size':8})


    # Plot idom numbers
    for idom,col_df in tile_df.groupby('idom'):

#        if idom <= 98:
#            jdom = 35
#        else:
        if True:
            jdom = col_df.jdom.min()

        tile_grid = exp.gridD.sub(idom,jdom, 10,10, margin=False)
        
        GT = exp.gridD.geotransform
        x0 = GT[0] + GT[1] * idom
        y0 = GT[3] + GT[5] * jdom

        x = x0 + 0.5 * exp.gridD.dx
        y = y0 + 1000    # Margin

        ax.text(x,y, f'{idom}', transform=map_crs,
            #rotation=90,
            fontweight='bold',
            horizontalalignment='center', verticalalignment='bottom',
            fontdict={'size':8})

    akfigs.plot_cities(ax, 'anchorage',
        text_kwargs=dict(
            fontdict = {'size': 7, 'color': 'blue', 'fontweight': 'bold'}),
        marker_kwargs=dict(
            marker='*', markersize=2, color='black', alpha=0.9))

    # Add graticules
    if True:
        gl = ax.gridlines(draw_labels=True,
              linewidth=0.3, color='grey', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
        gl.xlabel_style = {'size': 9}
        gl.ylabel_style = {'size': 9}
        gl.ylabels_bottom = False


    ofname = pathlib.Path('./fig01.pdf')
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


    ofname = pathlib.Path('./fig01-inset.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off





main()
