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
# \caption{Elevation data from Juneau area}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

ak_work_dir = exp.dir.parents[0] / (exp.dir.parts[-1] + '_work')

_dup_coords = [
    # (idom, jdom, Id)
    ((112,43,12093), (112,44,2479)),
    ((112,43,12094), (112,44,2480)),
]


def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

    #map_extent = subgrid.extent(order='xxyy')
    map_extent = (1096*1000, 1100*1000,   1139*1000, 1141*1000)


#    subgrid = exp.gridD.sub(112, 43, 100, 100, margin=True)
#    map_extent = subgrid.extent(order='xxyy')



    for idup in (0,1):

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(8.5,5.5))
        ax.set_extent(map_extent, map_crs)
        ax.set_facecolor((20./255, 30./255, 53./255))


    #    for idom,jdom in ((112,43), (112,44)):    # Dups span two adjacent tiles
        for idom,jdom in ((112,43),):     # Margins overlap
            # Resample DEM to 100m resolution
            dem_tif = exp.dir / 'dem' / f'ak_dem_{idom:03d}_{jdom:03d}.tif'
            landcover_tif = exp.dir / 'landcover' / f'ak_landcover_{idom:03d}_{jdom:03d}.tif'
            print('dem_tif ', dem_tif)
            with ioutil.TmpDir() as tdir:
    #            xyres = 10    # Resample to 60m
    #
    #            print('AA1')
    #            dem_tif_lr = tdir.location / dem_tif.parts[-1]
    #            ds = gdal.Warp(dem_tif_lr, dem_tif,
    #                xRes=xyres, yRes=xyres, resampleAlg='average')
    #            ds = None
    #
    #            print('AA2')
    #            landcover_tif_lr = tdir.location / landcover_tif.parts[-1]
    #            ds = gdal.Warp(landcover_tif_lr, landcover_tif,
    #                xRes=xyres, yRes=xyres, resampleAlg='average')
    #            ds = None

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
                    img, origin='upper', transform=map_crs, extent=img_extent, alpha=0.8)
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

        centroid = pra_multi.convex_hull.centroid
        deltay = 500 if jdom == 43 else -500
        ax.text(
            centroid.x, centroid.y + deltay, f'({idom},{jdom})', transform=map_crs, verticalalignment='center', horizontalalignment='center',
            fontdict = {'fontweight': 'bold'})



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
