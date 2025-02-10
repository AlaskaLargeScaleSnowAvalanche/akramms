import matplotlib.pyplot as plt
import numpy as np
from akramms import config,archive
import os,pathlib
import pandas as pd
import geopandas
import fiona
import shapely.ops
import shapely.geometry
import akramms.experiment.akse as expmod
from uafgi.util import gdalutil,cartopyutil
import akfigs
import cartopy.feature

combos_fn = expmod.urban
googlemaps_dir = config.HARNESS / 'data' / 'googlemaps'
extents30_gpkg = pathlib.Path('extent_dissolved') / 'ccsm-1981-2010-lapse-All-30-dissolved.gpkg'
extents300_gpkg = pathlib.Path('extent_dissolved') / 'ccsm-1981-2010-lapse-All-300-dissolved.gpkg'

def load_dissolved(fnames):

    # See: https://stackoverflow.com/questions/47038407/dissolve-overlapping-polygons-with-gdal-ogr-while-keeping-non-connected-result

#    # Read all shapes into one dataframe
#    dfs = list()
#    for fname in fnames:
#        dfs.append(geopandas.read_file(str(fname)))
#    df = geopandas.GeoDataFrame(pd.concat(dfs, ignore_index=True), crs=dfs[0].crs)

    geoms = list()
    for fname in fnames:
        print('Reading ', fname)
        with fiona.open(str(fname), 'r') as ds:
            crs = ds.crs
            drv = ds.driver

            # Filter only needed if there are invalid polygons
            # filtered = filter(lambda x: shapely.geometry.shape(x["geometry"]).is_valid, list(ds_in))
            filtered = list(ds)
            geoms += [shapely.geometry.shape(x["geometry"]) for x in filtered]
#        break

#    geoms = geoms[:10]
#    print('geoms ', geoms)

    dissolved = shapely.ops.cascaded_union(geoms)    # Multipolygon
    dissolved = list(dissolved.geoms)    # Convert to list of simple Polygons
#    print('dissolved ', dissolved)
    return geopandas.GeoDataFrame({'geometry': dissolved}, crs=crs)


def make_dissolveds():
    combos = sorted(set(combo._replace(forest='All') for combo in combos_fn()))
    df = pd.DataFrame([(combo.base_str(), combo) for combo in combos], columns=['base_str', 'combo'])

    odir = pathlib.Path('extent_dissolved')
    os.makedirs(odir, exist_ok=True)

    for base_str,df1 in df.groupby('base_str'):
        print('-------------- ', base_str)
        ofname = odir / f'{base_str}-dissolved.gpkg'
        if os.path.isfile(ofname):
            continue

        fnames = [
            expmod.root_dir / 'publish' / f'{expmod.name}-{base_str}' / 'extent' / f'{expmod.name}-{str(combo)}-F-extent.shp'
            for combo in df1.combo]
        existss = [os.path.exists(fname) for fname in fnames]

        if not all(existss):
            continue

        # Dissolve
        # https://stackoverflow.com/questions/47038407/dissolve-overlapping-polygons-with-gdal-ogr-while-keeping-non-connected-result
        df = load_dissolved(fnames)
        print(f'{base_str}: {len(df)}')

        print('------> ', ofname)
        df.to_file(ofname, driver='GPKG')

#def make_plot(img_tif, ofname_png):
#    ofname_png = pathlib.Path(ofname_png)
#
#    make_dissolveds()    # Cached
#
##    img_tif = googlemaps_dir / 'Cordova_BearCountryLodge.tif'
##    img_tif = googlemaps_dir / 'Juneau_SnowslideCreek.tif'
#    grid = gdalutil.grid_info(img_tif)
#
#
#    map_crs = cartopyutil.crs(grid.wkt)
#
#    fig,ax = plt.subplots(
#        nrows=1,ncols=1,
#        subplot_kw={'projection': map_crs},
#        figsize=(8.5,5.5))
#    map_extent = grid.extent()
#    ax.set_extent(map_extent, map_crs)
#    ax.set_facecolor((20./255, 30./255, 53./255))
#
#
#
#    # Plot the satellite image
#    img = plt.imread(img_tif)
#    print(type(img), img.shape)
#    img = ax.imshow(
#        img, origin='upper', transform=map_crs, extent=map_extent, alpha=0.8)
#
#    # Add extent outlines
#    for extents_gpkg,color in ((extents300_gpkg, 'red'), (extents30_gpkg, 'yellow')):
#        shape_feature = cartopy.feature.ShapelyFeature(
#            cartopy.io.shapereader.Reader(extents_gpkg).geometries(),
#            map_crs)
#    #    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)
#        ax.add_feature(shape_feature, facecolor='none', alpha=1, edgecolor=color, lw=1)
#
#
#    with akfigs.TrimmedPng(ofname_png) as tname:
#        fig.savefig(tname, dpi=96, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off


def make_plot(img_tif, ofname_png, plot_landcover=False):
    ofname_png = pathlib.Path(ofname_png)

    make_dissolveds()    # Cached

#    img_tif = googlemaps_dir / 'Cordova_BearCountryLodge.tif'
#    img_tif = googlemaps_dir / 'Juneau_SnowslideCreek.tif'
    grid = gdalutil.grid_info(img_tif)


    map_crs = cartopyutil.crs(grid.wkt)

    fig,ax = plt.subplots(
        nrows=1,ncols=1,
        subplot_kw={'projection': map_crs},
        figsize=(5.5,8.5))
    map_extent = grid.extent()
    ax.set_extent(map_extent, map_crs)
    ax.set_facecolor((20./255, 30./255, 53./255))


    ijdoms = [(91,41),(91,42)]
    # ------- Plot bed elevations EVERYWHERE
    for idom,jdom in ijdoms:

        dem_tif = expmod.dir / 'dem' / f'{expmod.name}_dem_{idom:03d}_{jdom:03d}.tif'
        dem_grid, dem_data, dem_nd = gdalutil.read_raster(dem_tif)
        dem_extent = dem_grid.extent()
        dem_data[dem_data <= 0] = np.nan

#        cmap,_,_ = cptutil.read_cpt('palettes/geo_0_2000.cpt', scale=4000)    # Convert to m

        shade = cartopyutil.plot_hillshade(
            ax, dem_data,
            transform=map_crs, extent=dem_extent, alpha=1.0)

    # Plot the satellite image
    img = plt.imread(img_tif)
    print(type(img), img.shape)
    img = ax.imshow(img, origin='upper', transform=map_crs, extent=map_extent, alpha=0.8)

    # ---------------- Plot landcover
    if plot_landcover:
        for idom,jdom in ijdoms:
            landcover_tif = expmod.root_dir / 'db' / 'landcover' / f'{expmod.name}_landcover_{idom:03d}_{jdom:03d}.tif'
            img = plt.imread(str(landcover_tif))    # RGBA image
            img = np.array(img)
            print('landcover_tif type ', type(img), img.shape, img.dtype)

            img_grid,img_data,img_nd = gdalutil.read_raster(landcover_tif)    # Indexes
    #        mask_in = (np.isin(img_data, [41,42,43]))        # Deciduous, Evergreen, Mixed
            mask_in = (np.isin(img_data, [42]))        # Deciduous, Evergreen, Mixed
            img_alpha = img[:,:,3]    # Alpha channel 0-255
            img_alpha[~mask_in] = 0
            img_landcover = ax.imshow(
                img, origin='upper', transform=map_crs, extent=img_grid.extent(), alpha=0.5)
            # -------------------------------

    # Add graticules
    gl = ax.gridlines(draw_labels=True,
          linewidth=0.3, color='white', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
    gl.xlabel_style = {'size': 9}
    gl.ylabel_style = {'size': 9}
    gl.xlabels_top = False
    gl.ylabels_right = False
    if plot_landcover:
        gl.ylabels_left = False


    # Add extent outlines
    for extents_gpkg,color in ((extents300_gpkg, 'red'), (extents30_gpkg, 'yellow')):
        shape_feature = cartopy.feature.ShapelyFeature(
            cartopy.io.shapereader.Reader(extents_gpkg).geometries(),
            map_crs)
    #    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)
        ax.add_feature(shape_feature, facecolor='none', alpha=1, edgecolor=color, lw=1)


    with akfigs.TrimmedPng(ofname_png) as tname:
        fig.savefig(tname, dpi=96, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off



def main():
    make_plot(googlemaps_dir / 'Cordova_BearCountryLodge.tif', './fig14_Cordova_BearCountryLodge.png')
    make_plot(googlemaps_dir / 'Cordova_BearCountryLodge.tif', './fig14_Cordova_BearCountryLodge_forest.png',
        plot_landcover=True)    # This plot straddles two tiles
    make_plot(googlemaps_dir / 'Juneau_SnowslideCreek.tif', './fig14_Juneau_SnowslideCreek.png')



main()
