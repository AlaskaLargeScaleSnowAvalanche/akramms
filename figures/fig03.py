import os,pathlib,subprocess,copy
import numpy as np
import cartopy
import cartopy.io.img_tiles
import geopandas
from osgeo import gdal
from akramms import config,archive
import matplotlib.pyplot as plt
from akfigs import *
from uafgi.util import gdalutil,cptutil,ioutil,cartopyutil,nlcdcodes
import akramms.experiment.ak as expmod    # Using old simulations for now
# \caption{Elevation data from Juneau area}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def fig3():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

    idom,jdom = (113,45)    # Juneau tile

    # Resample DEM to 100m resolution
    dem_tif = expmod.dir / 'dem' / f'ak_dem_{idom:03d}_{jdom:03d}.tif'
    landcover_tif = expmod.dir / 'landcover' / f'ak_landcover_{idom:03d}_{jdom:03d}.tif'
    print('dem_tif ', dem_tif)
    with ioutil.TmpDir() as tdir:
        xyres = 60    # Resample to 100m

        dem_tif_lr = tdir.location / dem_tif.parts[-1]
        ds = gdal.Warp(dem_tif_lr, dem_tif,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None

        landcover_tif_lr = tdir.location / landcover_tif.parts[-1]
        ds = gdal.Warp(landcover_tif_lr, landcover_tif,
            xRes=xyres, yRes=xyres, resampleAlg='near')
        ds = None

        subgrid = expmod.gridD.sub(idom, jdom, xyres, xyres, margin=True)
        map_extent = subgrid.extent(order='xxyy')

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(8.5,5.5))
        ax.set_extent(map_extent, map_crs)
        ax.set_facecolor((20./255, 30./255, 53./255))


        dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif_lr)
        dem_data[dem_data <= 0] = np.nan

#        landcover_grid, landcover_data, landcover_nd = gdalutil.read_raster(landcover_tif_lr)

        # ------- Plot bed elevations EVERYWHERE
#        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=map_extent)

        img = plt.imread(landcover_tif_lr)
        print(type(img), img.shape)
        img_landcover = ax.imshow(
            img, origin='upper', transform=map_crs, extent=map_extent, alpha=0.8)


        # Add graticules
        gl = ax.gridlines(draw_labels=True,
              linewidth=0.3, color='white', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
        gl.xlabel_style = {'size': 9}
        gl.ylabel_style = {'size': 9}
        gl.xlabels_top = False
        gl.ylabels_right = False

        # Write output
        ofname = pathlib.Path('./fig03.png')
        with TrimmedPng(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off



googlemaps_dir = config.HARNESS / 'data' / 'googlemaps'
snowslide_creek = googlemaps_dir / 'Juneau_SnowslideCreek.tif'

def fig3b():        # Closeup of Juneau
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

    idom,jdom = (113,45)    # Juneau tile

#    release_zip = expmod.dir / 'ak-ccsm-1981-2010-lapse-For-300/arc-113-045' / 'RELEASE.zip'

    # Resample DEM to 100m resolution
    dem_tif = expmod.dir / 'dem' / f'ak_dem_{idom:03d}_{jdom:03d}.tif'
    landcover_tif = expmod.dir / 'landcover' / f'ak_landcover_{idom:03d}_{jdom:03d}.tif'
    print('dem_tif ', dem_tif)
    with ioutil.TmpDir() as tdir:
#        xyres = 60    # Resample to 100m

#        subgrid = exp.gridD.sub(idom, jdom, xyres, xyres, margin=True)
#        print('extent0 ', subgrid.extent())

        img_grid = gdalutil.grid_info(snowslide_creek)
        map_extent = img_grid.extent(order='xxyy')
        print('extent1 ', map_extent)
        map_extent[1] -= 2600.
        map_extent[2] += 1500
        map_extent[3] -= 500

        fig,ax = plt.subplots(
            nrows=1,ncols=1,
            subplot_kw={'projection': map_crs},
            figsize=(8.5,5.5))
        ax.set_extent(map_extent, map_crs)
#        ax.set_facecolor((20./255, 30./255, 53./255))
        ax.set_facecolor((1.,1.,1.))


        # Plot the satellite image
        img = plt.imread(snowslide_creek)
        print(type(img), img.shape)
        img = ax.imshow(
            img, origin='upper', transform=map_crs, extent=img_grid.extent(), alpha=1.0)


        # ------- Plot bed elevations EVERYWHERE
        dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif)
        dem_extent = dem_grid.extent()
        dem_data[dem_data <= 0] = np.nan

#        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=dem_extent, alpha=0.3)

        # ---------------- Plot landcover
        img = plt.imread(str(landcover_tif))    # RGBA image
        img = np.array(img)
        print('landcover_tif type ', type(img), img.shape, img.dtype)

        _,img_data,img_nd = gdalutil.read_raster(landcover_tif)    # Indexes
        mask_in = (np.isin(img_data, [41,42,43]))
        img_alpha = img[:,:,3]    # Alpha channel 0-255
        img_alpha[~mask_in] = 0
        img_landcover = ax.imshow(
            img, origin='upper', transform=map_crs, extent=dem_extent, alpha=0.5)
        # -------------------------------

        # Get unique set of RGB values in img
        # https://stackoverflow.com/questions/40936160/how-to-efficiently-convert-2d-numpy-array-into-1d-numpy-array-of-tuples
        shp = img.shape
        imgT = img.reshape((shp[0]*shp[1],shp[2])).T
        rgbs = set(zip(imgT[0], imgT[1], imgT[2]))

        # Figure out which NLCD codes are used
        rgb2nlcd = {(x.R,x.G,x.B): x for x in nlcdcodes.codes if len(x.label) > 0}
        nlcds = set(rgb2nlcd[rgb].code for rgb in rgbs)
        print('nlcds ', nlcds)

        # ----------- Plot release and extent outlines
        arc_dir = pathlib.Path('/mnt/avalanche_sim/prj/akse.v1/db/akse-ccsm-1981-2010-lapse-NoFor-300/arc-113-045')


        reldf = archive.read_reldom(arc_dir / 'RELEASE.zip', 'rel')
        extdf = geopandas.read_file(arc_dir / 'extent.gpkg')

        keep_ids = [4732]
        reldf = reldf[reldf.Id.isin(keep_ids)]
        extdf = extdf[extdf.Id.isin(keep_ids)]

        print(reldf.columns)
        print(extdf.columns)

        for (df,color) in ((extdf, 'red'), (reldf, 'orange')):
            for poly in df.geometry:
                feature = cartopy.feature.ShapelyFeature(poly, map_crs)
                ax.add_feature(feature, facecolor='none', edgecolor=color, lw=1)

        # ---------------- Add graticules
        gl = ax.gridlines(draw_labels=True,
              linewidth=0.3, color='white', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
        gl.xlabel_style = {'size': 9}
        gl.ylabel_style = {'size': 9}
        gl.xlabels_top = False
        gl.ylabels_right = False

        # Write output
        ofname = pathlib.Path('./fig03_Downtown.png')
        with TrimmedPng(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off

    # ====================== NLCD Table
    ofname = pathlib.Path('./fig03_Downtown-nlcd.tex')
    with open(ofname, 'w') as out:
        for x in nlcdcodes.codes:
            if x.code in nlcds:
                out.write(f"\\colorpatch{{{x.R}}}{{{x.G}}}{{{x.B}}} & {x.label} \\\\\n")
#            if len(x.label) == 0:
#                continue

def main():
    fig3()
    fig3b()

main()

