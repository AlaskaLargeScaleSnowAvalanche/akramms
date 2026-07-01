import os,pathlib,subprocess,copy
import numpy as np
import cartopy
import cartopy.io.img_tiles
import geopandas
from osgeo import gdal
from akramms import config,archive
import matplotlib.pyplot as plt
import matplotlib
import akfigs
from uafgi.util import gdalutil,cptutil,ioutil,cartopyutil,nlcdcodes
import akramms.experiment.aksc5 as expmod    # Using old simulations for now
# \caption{Elevation data from Juneau area}

# Line2D Properties: https://matplotlib.org/stable/api/_as_gen/matplotlib.lines.Line2D.html#matplotlib.lines.Line2D

def fig3():
    map_crs = cartopy.crs.epsg(3338)    # Alaska Albers

    with ioutil.TmpDir() as tdir:

        dem_tif_lr, landcover_tif_lr = akfigs.resample_lr(
            expmod, expmod.anchorage_tiles(), tdir,
            vars=['dem', 'landcover'])

        map_extent = akfigs.anchorage_map_extent

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
        # -------------------------------


        # Add graticules
        gl = ax.gridlines(draw_labels=True,
              linewidth=0.3, color='white', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
        gl.xlocator = matplotlib.ticker.MultipleLocator(0.5)    # lon gridlines every 0.5 deg
        gl.xlabel_style = {'size': 8}
        gl.ylabel_style = {'size': 8}
        gl.xlabels_top = False
        gl.ylabels_right = False

        # Write output
        ofname = pathlib.Path('./fig03.pdf')
        with akfigs.TrimmedPdf(ofname) as tname:
            fig.savefig(tname, bbox_inches='tight', pad_inches=0.5, dpi=200)   # Hi-res version; add margin so text is not cut off


    # ====================== NLCD Table
    ofname = pathlib.Path('./fig03-nlcd.tex')
    with open(ofname, 'w') as out:
        for x in nlcdcodes.codes:
            if x.code in nlcds:
                out.write(f"\\colorpatch{{{x.R}}}{{{x.G}}}{{{x.B}}} & {x.label} \\\\\n")
#            if len(x.label) == 0:
#                continue

def main():
    fig3()
#l    fig3b()

main()

