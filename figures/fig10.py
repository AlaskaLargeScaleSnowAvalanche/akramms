import os,pathlib,subprocess
import numpy as np
import cartopy
import cartopy.io.img_tiles
from osgeo import gdal
from akramms import config
import matplotlib.pyplot as plt
import akramms.experiment.ak as exp
from akfigs import *
from uafgi.util import gdalutil,cptutil,ioutil,cartopyutil
import shapely.geometry.multipolygon
# \caption{Elevation data from Juneau area}

import matplotlib.patches

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D


idom0,idom1 = (102,111)
jdom0,jdom1 = (41,44)



def main():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

#    idom,jdom = (113,45)    # Juneau tile

    xyres = 180    # Resample to 100m

    # Get overall map domain
    polys = list()
    for idom in range(idom0,idom1):
        for jdom in range(jdom0,jdom1):
            polys.append(exp.gridD.poly(idom, jdom, margin=False))

    allpolys = shapely.geometry.multipolygon.MultiPolygon(polys)
    index_box = allpolys.envelope  # Smallest rectangle with sides oriented to axes
    xx,yy = index_box.exterior.coords.xy
    map_extent = (xx[0], xx[1], yy[2], yy[0])

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(8.5,5.5))
    ax.set_extent(map_extent, map_crs)
    ax.set_facecolor((20./255, 30./255, 53./255))


    # Resample DEM to 100m resolution
    with ioutil.TmpDir() as tdir:
        for idom in range(idom0,idom1):
#            for jdom in range(jdom0,jdom1):
            for jdom in range(jdom0,jdom0+1):

                print('ijdom ', idom, jdom)

                subgrid = exp.gridD.sub(idom, jdom, xyres, xyres, margin=True)

                dem_tif = exp.dir / 'dem' / f'ak_dem_{idom:03d}_{jdom:03d}.tif'
                snow_tif = exp.dir / 'snow' / f'ak_ccsm_1981_2010_lapse_{idom:03d}_{jdom:03d}.tif'

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
                dem_data[dem_data <= 0] = np.nan


                # Get mask for plotting
                sg = exp.gridD.sub(idom, jdom, xyres, xyres, margin=False)
                xt = sg.extent('xxyy')
                x0,x1,y0,y1 = xt
                # https://matplotlib.org/stable/gallery/shapes_and_collections/path_patch.html
                pth = matplotlib.path.Path
                path_data = [
                    (pth.MOVETO, (x0,y0)),
                    (pth.LINETO, (x0,y1)),
                    (pth.LINETO, (x1,y1)),
                    (pth.LINETO, (x1,y0)),
                    (pth.CLOSEPOLY, (x0,y0))]
                codes,verts = zip(*path_data)
                path = matplotlib.path.Path(verts,codes)
                # https://github.com/SciTools/cartopy/issues/1603
#                patch = matplotlib.patches.PathPatch(path, transform=ax.transData)


                path = cartopy.mpl.patch.geos_to_path(exp.gridD.poly(idom, jdom, margin=False))[0]
                print('path ', path)
                bbox = matplotlib.transforms.Bbox([[x0,y0],[x1,y1]])



                # https://matplotlib-users.narkive.com/Kmgvq1hY/clipping-a-plot-inside-a-polygon
**** SEE HERE...
https://matplotlib-users.narkive.com/Kmgvq1hY/clipping-a-plot-inside-a-polygon
                patch = matplotlib.patches.Rectangle((x0,y1), x1-x0, y0-y1)


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
                print('vmin vmax ', vmin, vmax)
                # https://stackoverflow.com/questions/56649160/clip-off-pcolormesh-outside-of-circular-set-boundary-in-cartopy
                pcm_snow = ax.pcolormesh(
                    subgrid.centersx, subgrid.centersy, snow_data,
                    alpha=0.5, rasterized=True,
                    transform=map_crs, cmap=cmap, vmin=0, vmax=700)
#                    clip_box=bbox)
#                    clip_path=(path, ax.transAxes))
#                pcm_snow.set_clip_path((path, ax.transAxes))
#                ax.clip_to_bbox(bbox)    # https://scitools.org.uk/cartopy/docs/v0.17/whats_new.html
#                pcm_snow.set_clip_on(True)

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




main()
