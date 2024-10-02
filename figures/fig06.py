import os,pathlib,subprocess
import numpy as np
import cartopy,geopandas
import cartopy.io.img_tiles
from osgeo import gdal
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.ak as exp
from akfigs import *
from uafgi.util import gdalutil,cptutil,ioutil,cartopyutil
import shapely.geometry.multipolygon 
import akfigs

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

ak_work_dir = exp.dir.parents[0] / (exp.dir.parts[-1] + '_work')

# Original dups, these were deemed too ugly
#_dup_coords = [
#    # (idom, jdom, Id)
#    ((112,43,12093), (112,44,2479)),
#    ((112,43,12094), (112,44,2480)),
#]

idom0,jdom0 = (105,43)
idom1,jdom1 = (105,44)
_dup_coords = [
    # (idom, jdom, Id)
    ((105,43,6946), (105,44,1754)),
    ((105,43,6886), (105,44,1758)),
]


def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

    #map_extent = subgrid.extent(order='xxyy')
#    map_extent = (1096*1000, 1100*1000,   1139*1000, 1141*1000)


#    subgrid = exp.gridD.sub(112, 43, 100, 100, margin=True)
#    map_extent = subgrid.extent(order='xxyy')

    extent0 = exp.gridD.sub(idom0, jdom0, 100, 100, margin=False).extent(order='xxyy')
    extent1 = exp.gridD.sub(idom1, jdom1, 100, 100, margin=False).extent(order='xxyy')
#    map_extent = (extent0[0], extent1[1], extent1[2], extent0[3])
    map_extent = (extent0[0]+2*1000, extent0[0]+5*1000, extent0[2]-1*1000, extent0[2]+1*1000)
#    map_extent = extent0

    for idup in (0,1):

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(5.5,5.5))
        ax.set_extent(map_extent, map_crs)
        ax.set_facecolor((20./255, 30./255, 53./255))


    #    for idom,jdom in ((112,43), (112,44)):    # Dups span two adjacent tiles
        for idom,jdom in ((idom0,jdom0),):     # Margins overlap
            # Resample DEM to 100m resolution
            dem_tif = exp.dir / 'dem' / f'ak_dem_{idom:03d}_{jdom:03d}.tif'
            landcover_tif = exp.dir / 'landcover' / f'ak_landcover_{idom:03d}_{jdom:03d}.tif'
            print('dem_tif ', dem_tif)
            with ioutil.TmpDir() as tdir:

                # Grid the tile images are defined on.
                subgrid = exp.gridD.sub(idom, jdom, 10, 10, margin=True)
                img_extent = subgrid.extent(order='xxyy')

                print('AA3')
                dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif)
                dem_data[dem_data <= 0] = np.nan

        #        landcover_grid, landcover_data, landcover_nd = gdalutil.read_raster(landcover_tif_lr)

                # ------- Plot bed elevations EVERYWHERE
        #        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m

                print('AA4')
                shade = cartopyutil.plot_hillshade(
                    ax, dem_data,
                    transform=map_crs, extent=img_extent,
                    rasterized=True)

                print('AA5')
                img = plt.imread(str(landcover_tif))
                img_landcover = ax.imshow(
                    img, origin='upper', transform=map_crs, extent=img_extent, alpha=0.6)
                print('AA6')



        # Plot the duplicate PRAs
        dups_df = geopandas.read_file(str(ak_work_dir / 'dups.gpkg')).set_index(['idom','jdom','Id'])
        pras = list()
        for dup_coord in _dup_coords:
            dupx = dup_coord[idup]
            idom,jdom = dupx[:2]
            pra = dups_df.loc[dupx].geometry.iloc[0]
            pras.append(pra)
            print('pra ', pra)

            shape_feature = cartopy.feature.ShapelyFeature(pra, map_crs)
            ax.add_feature(shape_feature, facecolor='pink', alpha=.7, edgecolor='black', lw=0.3)

        # Get a general center point of all the polygons we just plotted
        pra_multi = shapely.geometry.multipolygon.MultiPolygon(pras)


        # Plot the tile box for the PRAs we just plotted
    #    tile_df = geopandas.read_file(str(exp.dir / 'ak_domains.shp')).set_index(['idom','jdom'])
    #    tile_poly = tile_df.loc[idom,jdom].geometry
        tile_poly = exp.gridD.poly(idom,jdom)
        shape_feature = cartopy.feature.ShapelyFeature(tile_poly, map_crs)
        ax.add_feature(shape_feature, facecolor='none', alpha=.6, edgecolor='black', linestyle='--', lw=1)
        subgrid = exp.gridD.sub(idom, jdom, 10, 10, margin=True)

#        centroid = pra_multi.convex_hull.centroid
        deltay = 100 if jdom == 43 else -100
        ax.text(
            map_extent[0]+ 400, extent0[2] + deltay,
            #centroid.x, centroid.y + deltay,
            f'({idom},{jdom})', transform=map_crs, verticalalignment='center', horizontalalignment='center',
            fontdict = {'fontweight': 'bold', 'size': 12})

        # Add graticules
        gl = ax.gridlines(draw_labels=True,
              linewidth=0.3, color='navy', alpha=0.5, x_inline=False, y_inline=False,
            dms=False,    # Degrees/Minutes/Seconds vs. Decimal
            linestyle='-')
        gl.xlabel_style = {'size': 9}
        gl.ylabel_style = {'size': 9}
        if idup == 0:
            gl.xlabels_bottom = False
        else:
            gl.xlabels_top = False

        ofname = pathlib.Path(f'./fig06-{idup}.pdf')
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


main()
