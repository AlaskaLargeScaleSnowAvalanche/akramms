import os,pathlib,subprocess
import numpy as np
import cartopy
import cartopy.io.img_tiles
from osgeo import gdal
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.akse as expmod
from akfigs import *
from uafgi.util import gdalutil,cptutil,ioutil,cartopyutil
import shapely.geometry.multipolygon
# \caption{Elevation data from Juneau area}
import akfigs

import matplotlib.patches

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D


idom0,idom1 = (107,115)
jdom0,jdom1 = (41,48)



def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

#    idom,jdom = (113,45)    # Juneau tile

    xyres = 180    # Resample to 100m

    # Get overall map domain
    polys = list()
    for idom in range(idom0,idom1):
        for jdom in range(jdom0,jdom1):
            polys.append(expmod.gridD.poly(idom, jdom, margin=False))

    allpolys = shapely.geometry.multipolygon.MultiPolygon(polys)
    index_box = allpolys.envelope  # Smallest rectangle with sides oriented to axes
    xx,yy = index_box.exterior.coords.xy
    map_extent = (xx[0], xx[1], yy[2], yy[0])

#    print('map_extent ', map_extent)
#    return

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))
    ax.set_extent(map_extent, map_crs)
    ax.set_facecolor((20./255, 30./255, 53./255))


    # Resample DEM to 100m resolution
    with ioutil.TmpDir() as tdir:
        for idom in range(idom0,idom1):
            for jdom in range(jdom0,jdom1):
#            for jdom in range(jdom0,jdom0+1):

                print('ijdom ', idom, jdom)

                subgrid = expmod.gridD.sub(idom, jdom, xyres, xyres, margin=True)

                dem_tif = expmod.dir / 'dem' / f'{expmod.name}_dem_{idom:03d}_{jdom:03d}.tif'
                snow_tif = expmod.dir / 'snow' / f'{expmod.name}_ccsm_1981_2010_lapse_{idom:03d}_{jdom:03d}.tif'

                # Avoid tiles that are not part of our domain
                if not os.path.exists(dem_tif):
                    continue


                print('dem_tif ', dem_tif)

                dem_tif_lr = tdir.location / dem_tif.parts[-1]
                ds = gdal.Warp(dem_tif_lr, dem_tif,
                    xRes=xyres, yRes=xyres, resampleAlg='average')
                ds = None

        #        snow_tif_lr = snow_tif    # For some reason gdalwarp isn't working here
                snow_tif_lr = tdir.location / snow_tif.parts[-1]
                ds = gdal.Warp(snow_tif_lr, snow_tif,
                    xRes=xyres, yRes=xyres, resampleAlg='average')
                ds = None

                dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif_lr)
                dem_mask = (dem_data <= 0)
                dem_data[dem_mask] = np.nan


                # ------- Plot bed elevations EVERYWHERE
        #        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m

                shade = cartopyutil.plot_hillshade(
                    ax, dem_data,
                    transform=map_crs, extent=subgrid.extent('xxyy'))

                # ---------- Plot snow
                # This follows E3SM convention for precip
                # See here for suggested colormaps
                # https://docs.e3sm.org/e3sm_diags/_build/html/master/colormaps.html
                cmap,_,_ = cptutil.read_cpt('palettes/WhiteBlueGreenYellowRed.cpt')
                cmap = cptutil.discrete_cmap(14, cmap)

                snow_grid, snow_data, snow_nd = gdalutil.read_raster(snow_tif_lr)
                vmin = np.nanmin(snow_data)
                vmax = np.nanmax(snow_data)
                snow_data[dem_mask] = np.nan
                print('vmin vmax ', vmin, vmax)
                # https://stackoverflow.com/questions/56649160/clip-off-pcolormesh-outside-of-circular-set-boundary-in-cartopy
                pcm_snow = ax.pcolormesh(
                    subgrid.centersx, subgrid.centersy, snow_data,
                    alpha=0.5, rasterized=True,
                    transform=map_crs, cmap=cmap, vmin=0, vmax=700)


                pcm_snow.set_clip_path(cartopyutil.poly_clip_path(ax, expmod.gridD.poly(idom, jdom, margin=False)))

        akfigs.plot_cities(ax,
            only={'Haines', 'Juneau'},
            text_kwargs=dict(
                fontdict = {'size': 8, 'color': 'red', 'fontweight': 'bold'}),
            marker_kwargs=dict(
                marker='*', markersize=2, color='red', alpha=0.9))


        # Add graticules
        gl = ax.gridlines(draw_labels=True,
              linewidth=0.3, color='grey', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
        gl.xlabel_style = {'size': 9}
        gl.ylabel_style = {'size': 9}
        gl.xlabels_top = False        
        gl.ylabels_right = False



        ofname = pathlib.Path('./fig10.pdf')
        with TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off

#        # ---------- The colorbar
#        fig,axs = plt.subplots(
#            nrows=1,ncols=1,
#    #        subplot_kw={'projection': map_crs},
#            figsize=(8.5,5.5))
#        cbar_ax = axs
#        cbar = fig.colorbar(pcm_elev, ax=cbar_ax)
#        cbar.ax.tick_params(labelsize=20)
#        cbar_ax.remove()   # https://stackoverflow.com/questions/40813148/save-colorbar-for-scatter-plot-separately
#
#        ofname = pathlib.Path('geo_cbar.pdf')
#        with TrimmedPdf(ofname) as tname:
#            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off


        # ==================================================================
        # Make the inset map
    #    imap_extent = (-820*1000, 1900*1000, 0*1000, 2400*1000)
        # Same as fig01 map_extent, 
        imap_extent = (-520*1000, 2500*1000, -00*1000, 2400*1000)
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


        ofname = pathlib.Path('./fig10-inset.pdf')
        with akfigs.TrimmedPdf(ofname) as tname:
            fig.savefig(tname, dpi=300, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off



main()
