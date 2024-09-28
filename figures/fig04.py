import os,pathlib,subprocess
import cartopy,pyproj
import cartopy.io.img_tiles
from akramms import config
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from akramms import downscale_snow
import akramms.experiment.ak as exp
from uafgi.util import gdalutil,cartopyutil,cptutil,wrfutil
from akfigs import *
import cartopy.feature
import akfigs

# \caption{Map of the study area including the Alaska panhandle.  The todo-color outline shows the domain used to run WRF to generate estimates of maximum snow depth.  The todo-color squares show \SI{30}{\kilo\meter} square \emph{tiles} used to divide the overall domain into computationally managable pieces.}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

#	float sx3(south_north, west_east) ;
#		sx3:sr_y = 1 ;
#		sx3:sr_x = 1 ;
#		sx3:stagger = "M" ;
#		sx3:description = "Maximum 3-day snowfall" ;
#		sx3:units = "mm" ;
#		sx3:MemoryOrder = "XY " ;
#		sx3:FieldType = 104 ;
#		sx3:_FillValue = -999.f ;
ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'#pathlib.Path(os.environ['HOME']) / 'av/data/lader/sx3'
geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid

def main():
#    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers
    map_crs = akfigs.map_crs()
#    map_extent = (320000, 1510*1000, 710000, 1425*1000)    # xmin, xmax, ymin, ymax; ymin in South
    map_extent = (155*1000, 1680*1000, 510*1000, 1645*1000)    # xmin, xmax, ymin, ymax; ymin in South

    for ix,(year0,year1) in enumerate(((1981,2010), (2031,2060))):
        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(5.5,5.5))
        ax.set_extent(map_extent, map_crs)

        print(f'------------------ (year0,year1) = ({year0}, {year1})')

        snow_grid = wrfutil.wrf_info(geo_nc)
        snow_data,snow_nd = downscale_snow.read_sx3_multi(
            [ccsm_dir / f'ccsm_sx3_{year}.nc' for year in range(year0,year1+1)])

    #    print('Reading snow from ', ccsm_tif)
    #    snow_grid, snow_data, snow_nd = gdalutil.read_raster(ccsm_tif)
        print('snow_nd = ', snow_nd)
        snow_nd = -999.0    # Set snow_nd correctly
        snow_data[snow_data == snow_nd] = np.nan
        vmin = 0#np.nanmin(snow_data)
        vmax = 700#np.nanmax(snow_data)
        print('Min Max sx3 ', np.nanmin(snow_data), np.nanmax(snow_data))

        # This follows E3SM convention for precip
        # See here for suggested colormaps
        # https://docs.e3sm.org/e3sm_diags/_build/html/master/colormaps.html
        cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
        cmap = cptutil.discrete_cmap(14, cmap)


    #    snow_crs = pyproj.CRS.from_string(snow_grid.wkt)
        snow_crs = cartopyutil.crs(snow_grid.wkt)
        pcm_sx3 = ax.pcolormesh(
            snow_grid.centersx, snow_grid.centersy, snow_data,
            #alpha=0.5, #rasterized=True,
            rasterized=True,
            transform=snow_crs, cmap=cmap, vmin=vmin, vmax=vmax)

        # https://scitools.org.uk/cartopy/docs/v0.14/matplotlib/feature_interface.html
        ax.add_feature(cartopy.feature.BORDERS, alpha=0.5, linewidth=0.5)    # edgecolor='gray'
        ax.add_feature(cartopy.feature.COASTLINE, alpha=0.5, linewidth=0.5)

    #    ax.add_image(cartopy.io.img_tiles.OSM(cache=True), 7, alpha=1)    # Use level 7 (lower # is coarser)
    #    ax.coastlines(resolution='50m', color='grey', linewidth=0.5)

    #    shape_feature = cartopy.feature.ShapelyFeature(
    #        cartopy.io.shapereader.Reader(str(exp.dir / 'ak_domains.shp')).geometries(),
    #        map_crs)
    #
    #    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)


        plot_cities(ax,
            text_kwargs=dict(
                fontdict = {'size': 7, 'color': 'black', 'fontweight': 'bold'}),
            marker_kwargs=dict(
                marker='*', markersize=2, color='black', alpha=0.9))


        # Add graticules
        gl = ax.gridlines(draw_labels=True,
              linewidth=0.3, color='grey', alpha=0.5, x_inline=False, y_inline=False, dms=True, linestyle='-')
        gl.xlabel_style = {'size': 9}
        gl.ylabel_style = {'size': 9}
#        if ix == 0:
#            gl.xlabels_bottom = False
#        else:
        if True:
            gl.xlabels_top = False        

        gl.ylabels_right = False


        ofname = pathlib.Path(f'./fig04-{year0}-{year1}.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off



        # ---------- The colorbar
        fig,axs = plt.subplots(
            nrows=1,ncols=1,
    #        subplot_kw={'projection': map_crs},
            figsize=(160/25.4,160/25.4))
        cbar_ax = axs
        cbar = fig.colorbar(pcm_sx3, ax=cbar_ax, ticks=[0,100,200,300,400,500,600,700])
        labels = cbar.ax.set_yticklabels(['0 mm', '100', '200', '300', '400', '500', '600', '>700 mm'])
#        # Make labels bold
#        ticks_font = matplotlib.font_manager.FontProperties(weight='bold')
#        for label in labels:
#            label.set_fontproperties(ticks_font)
        cbar.ax.tick_params(labelsize=10)
        cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately

        ofname = pathlib.Path('fig04-cbar.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off



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


    ofname = pathlib.Path('./fig04-inset.pdf')
    with akfigs.TrimmedPdf(ofname) as tname:
        fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off


main()
