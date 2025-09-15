import os,pathlib
import numpy as np
import pandas as pd
import geopandas
import akramms.experiment.akse as expmod
from akramms import archive,extent

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


#odir = pathlib.Path(os.environ['HOME']) / 'tmp' / 'filter'
odir = pathlib.Path('low_avals')
os.makedirs(odir, exist_ok=True)


comboss = [
    ('juneau', (
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, 113, 45),
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 30, 113, 45))),
    ('cordova', (
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, 91, 41),
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 30, 91, 41))),
    ('valdez', (
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, 89, 39),
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 30, 89, 39))),
    ('haines', (
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, 110, 42),
        expmod.Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 30, 110, 42))),
]


def make_include_exclude():
    for name,combos in comboss:
        high_fname = odir / f'{name}_high.gpkg'
        include_fname = odir / f'{name}_include.gpkg'
        exclude_fname = odir / f'{name}_exclude.gpkg'

        if os.path.isfile(include_fname) and os.path.isfile(exclude_fname) and os.path.isfile(high_fname):
            continue

        print(f'================== {name}')
        reldfs = list()
        extdfs = list()
        for combo in combos:
            arcdir = expmod.combo_to_scenedir(combo, 'arc')
            reldfs.append(archive.read_reldom(arcdir / 'RELEASE.zip', 'rel', read_shapes=False))
            extent_gpkg = extent.extent_fname(expmod, combo, 'christen')
            extent_gpkg = pathlib.Path(str(extent_gpkg).replace('/ext/', '/ext.v1/'))    # DEBUG
            extdfs.append(geopandas.read_file(str(extent_gpkg)))
        reldf = pd.concat(reldfs)
        extdf = pd.concat(extdfs)


        # Merge the two
        df = geopandas.GeoDataFrame(extdf.drop('Mean_DEM', axis=1).merge(reldf.drop('geometry',axis=1), on='Id'))

        # Separate low from high
        mask_low = df['Mean_DEM'] < 300
        df_low = df[mask_low]
        df_high = df[~mask_low]

        # Among low, Separte include from exclude
        keep = np.logical_and(
            (((df_low.rel_n41 + df_low.rel_n43) / df_low.rel_n) < 0.3),
            (((df_low.ext_n42 + df_low.ext_n43) / df_low.ext_n) < 0.3))

        df_include = df_low[keep]
        df_exclude = df_low[~keep]

        # Show it...
        cols = ['Id', 'rel_n', 'rel_n41', 'rel_n43', 'ext_n', 'ext_n41', 'ext_n43']
        print(f'================== {name}')
        print('-------- include')
        print(df_include[cols])
        print('-------- exclude')
        print(df_exclude[cols])

        df_high.to_file(high_fname, driver='GPKG')
        df_include.to_file(include_fname, driver='GPKG')
        df_exclude.to_file(exclude_fname, driver='GPKG')

# ---------------------------------------------------------------

def make_plot(img_tif, ofname_png, gpkg_kwargs, plot_landcover=False, ijdoms=None, points_fname=None, ids=None):
    ofname_png = pathlib.Path(ofname_png)
    if os.path.isfile(ofname_png):
        return
    print(f'--------------- Plotting {ofname_png}')

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


#    ijdoms = [(91,41),(91,42)]
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
            mask_in = (np.isin(img_data, [42,43]))        # Deciduous, Evergreen, Mixed
            img_alpha = img[:,:,3]    # Alpha channel 0-255
            img_alpha[~mask_in] = 0
            img_landcover = ax.imshow(
                img, origin='upper', transform=map_crs, extent=img_grid.extent(), alpha=0.8)
            # -------------------------------

    # Add graticules
    gl = ax.gridlines(draw_labels=True,
          linewidth=0.3, color='white', alpha=0.5, x_inline=False, y_inline=False, dms=False, linestyle='-')
    gl.xlabel_style = {'size': 9}
    gl.ylabel_style = {'size': 9}
    gl.xlabels_top = False
    gl.ylabels_right = False
#    if plot_landcover:
 #       gl.ylabels_left = False


    # Add extent outlines
    for extents_gpkg,feature_kwargs in gpkg_kwargs:
        if isinstance(extents_gpkg, pathlib.Path):
            # https://scitools.org.uk/cartopy/docs/v0.15/tutorials/using_the_shapereader.html
            geometries = [rec.geometry for rec in cartopy.io.shapereader.Reader(extents_gpkg).records() \
                if ids is None or rec.attributes['Id'] in ids]
        else:
            geometries = extents_gpkg

        shape_feature = cartopy.feature.ShapelyFeature(
            geometries,
#            cartopy.io.shapereader.Reader(extents_gpkg).geometries(),
            map_crs)
    #    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)
#        ax.add_feature(shape_feature, facecolor='none', alpha=1, edgecolor=color, lw=.5)
        ax.add_feature(shape_feature, **feature_kwargs)


    # Add numbered points
    print('points_fname ', points_fname)
    if points_fname is not None:
#        df = geopandas.read_file(points_fname)
        df = geopandas.read_file(points_fname)
        print('len ', len(df))
        for tup in df.itertuples(index=True):
            x = tup.geometry.x
            y = tup.geometry.y
            ax.plot(x,y, marker='.', color='orange', alpha=0.5, markersize=23, transform=map_crs)    # s = marker size
            ax.annotate(chr(ord('A')+tup.Index), (x,y), xycoords=map_crs, ha='center', va='center', color='black')
#            ax.annotate(str(tup.Index), (x,y), xytext=(5, 5), textcoords='offset points')


    with akfigs.TrimmedPng(ofname_png) as tname:
        fig.savefig(tname, dpi=192, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off



def main():
    make_include_exclude()

    ih_include = dict(facecolor='gold', alpha=.4, edgecolor='brown', lw=.5)
    ih_high = dict(facecolor='none', alpha=1, edgecolor='blue', lw=.5)

    ie_exclude = dict(facecolor='none', alpha=1, edgecolor='purple', lw=.5)
    ie_include = dict(facecolor='none', alpha=1, edgecolor='pink', lw=.5)

    inset_bounds = dict(facecolor='none', alpha=1, edgecolor='fuchsia', lw=1)
    release_style = dict(facecolor='pink', alpha=.4, edgecolor='brown', lw=.5)


    one_style = dict(facecolor='none', alpha=.8, edgecolor='brown')

    # ------------- Juneau Rock Dump: Include & High
    gpkg_kwargs = [
        (odir / f'juneau_include.gpkg', ih_include),
        (odir / f'juneau_high.gpkg', ih_high),
    ]
    make_plot(
        googlemaps_dir / 'Juneau_RockDump.tif', './fig15_Juneau_RockDump.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(113,45)])

    # ------------- Juneau Rock Dump: Include & High
    gpkg_kwargs = [
        (odir / f'juneau_include.gpkg', ih_include),
        (odir / f'juneau_high.gpkg', ih_high),
    ]
    make_plot(
        googlemaps_dir / 'Juneau_BehrendsAve.tif', './fig15_Juneau_BehrendsAve.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(113,45)])

    # ---------------- Juneau1 (Downtown): Include & Exclude
    gpkg_kwargs = [
        (odir / f'juneau_exclude.gpkg', ie_exclude),
        (odir / f'juneau_include.gpkg', ie_include),
    ]

    make_plot(
        googlemaps_dir / 'Juneau1.tif', './fig15_Juneau1_IE.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(113,45)], points_fname='/vsizip/juneau_points.zip/juneau_points.shp')

    # ---------------- Juneau1 (Downtown): Include & High
    gpkg_kwargs = [
        (odir / f'juneau_include.gpkg', ih_include),
        (odir / f'juneau_high.gpkg', ih_high),
    ]

    make_plot(
        googlemaps_dir / 'Juneau1.tif', './fig15_Juneau1_IH.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(113,45)], points_fname='/vsizip/juneau_points.zip/juneau_points.shp')

    # ---------------- Juneau1 (Downtown): PRAs
    stub = 'akse-ccsm-1981-2010-lapse-All-30'
    gpkg_kwargs = [
        (pathlib.Path(expmod.root_dir / 'publish' / stub / 'release' / f'{stub}-113-045-F-release.shp'), release_style),
    ]

    make_plot(
        googlemaps_dir / 'Juneau1.tif', './fig15_Juneau1_PRA.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(113,45)])

    # ----------------- Juneau: Snowslide Creek
    gpkg_kwargs = [
        (odir / f'juneau_include.gpkg', one_style),
        (odir / f'juneau_high.gpkg', one_style),
    ]

    make_plot(
        'Juneau_SnowslideCreek.tif', './fig15_Juneau_SnowslideCreek_IH.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(113,45)],
        ids={10635, 8871, 8878, 8879, 10626, 10636, 10638, 10644, 10648},
        points_fname='/vsizip/SnowslideCreek_Points.zip/SnowslideCreek_Points.shp')

    # ----------------- Valdez : Include & High
    gpkg_kwargs = [
        (odir / f'valdez_high.gpkg', ih_high),
        (odir / f'valdez_exclude.gpkg', ie_exclude),
        (odir / f'valdez_include.gpkg', ie_include),
    ]

    make_plot(
        googlemaps_dir / 'Valdez1.tif', './fig15_Valdez1.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(89,39)])

    # ----------------- Valdez High School: Include & Exclude
    gpkg_kwargs = [
        (odir / f'valdez_exclude.gpkg', ie_exclude),
        (odir / f'valdez_include.gpkg', ie_include),
    ]

    make_plot(
        googlemaps_dir / 'Valdez_HighSchool.tif', './fig15_Valdez_HighSchool_IE.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(89,39)])

    # ----------------- Valdez High School: Include & High
    gpkg_kwargs = [
        (odir / f'valdez_include.gpkg', ie_include),
        (odir / f'valdez_high.gpkg', ih_high),
        ('/vsizip/Valdez_MountainSafety.zip/Valdez_MountainSafety.shp', inset_bounds),
    ]

    make_plot(
        googlemaps_dir / 'Valdez_HighSchool.tif', './fig15_Valdez_HighSchool_IH.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(89,39)])

    # ----------------- Valdez High School: Include & High
    gpkg_kwargs = [
        (odir / f'valdez_include.gpkg', ih_include),
        (odir / f'valdez_high.gpkg', ih_high),
    ]

    make_plot(
        'Valdez_PorcupineSt.tif', './fig15_Valdez_PorcupineSt_IH.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(89,39)], points_fname='/vsizip/ValdezPoints.zip/ValdezPoints.shp')

    # ----------------- Cordova : Include & Exclude
    bear_tif = googlemaps_dir / 'Cordova_BearCountryLodge.tif'
    bear_grid = gdalutil.read_grid(bear_tif)
    bear_bbox = bear_grid.bounding_box()

    gpkg_kwargs = [
        (odir / f'cordova_high.gpkg', ih_high),
        (odir / f'cordova_exclude.gpkg', ie_exclude),
        (odir / f'cordova_include.gpkg', ie_include),
        ([bear_bbox], inset_bounds),
    ]

    make_plot(
        googlemaps_dir / 'Cordova1.tif', './fig15_Cordova1.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(91,41)])

 

#(include_gpkg, 'pink'), (exclude_gpkg, 'deepskyblue')
#    make_plot(googlemaps_dir / 'Juneau1.tif', './fig15_Juneau.png', odir / f'juneau_include.gpkg', odir / f'juneau_exclude.gpkg', plot_landcover=True, ijdoms=[(113,45)])
main()

