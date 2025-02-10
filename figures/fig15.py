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

def make_plot(img_tif, ofname_png, gpkg_kwargs, plot_landcover=False, ijdoms=None):
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

        shape_feature = cartopy.feature.ShapelyFeature(
            cartopy.io.shapereader.Reader(extents_gpkg).geometries(),
            map_crs)
    #    ax.add_feature(shape_feature, facecolor='pink', alpha=.3, edgecolor='black', lw=0.3)
#        ax.add_feature(shape_feature, facecolor='none', alpha=1, edgecolor=color, lw=.5)
        ax.add_feature(shape_feature, **feature_kwargs)


    with akfigs.TrimmedPng(ofname_png) as tname:
        fig.savefig(tname, dpi=192, bbox_inches='tight', pad_inches=0.5)   # Hi-res version; add margin so text is not cut off



def main():
    make_include_exclude()
    return

    ih_include = dict(facecolor='gold', alpha=.4, edgecolor='brown', lw=.5)
    ih_high = dict(facecolor='none', alpha=1, edgecolor='blue', lw=.5)

    ie_exclude = dict(facecolor='none', alpha=1, edgecolor='purple', lw=.5)
    ie_include = dict(facecolor='none', alpha=1, edgecolor='pink', lw=.5)

    # ------------- Juneau Rock Dump: Include & High
    gpkg_kwargs = [
        (odir / f'juneau_include.gpkg', ih_include),
        (odir / f'juneau_high.gpkg', ih_high),
    ]
    make_plot(
        googlemaps_dir / 'Juneau_RockDump.tif', './fig15_Juneau_RockDump.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(113,45)])

    # ---------------- Juneau1 (Downtown): Include & Exclude
    gpkg_kwargs = [
        (odir / f'juneau_exclude.gpkg', ie_exclude),
        (odir / f'juneau_include.gpkg', ie_include),
    ]

    make_plot(
        googlemaps_dir / 'Juneau1.tif', './fig15_Juneau1.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(113,45)])

    # ----------------- Valdez : Include & Exclude
    gpkg_kwargs = [
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
        (odir / f'valdez_include.gpkg', ih_include),
        (odir / f'valdez_high.gpkg', ih_high),
    ]

    make_plot(
        googlemaps_dir / 'Valdez_HighSchool.tif', './fig15_Valdez_HighSchool_IH.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(89,39)])

    # ----------------- Cordova : Include & Exclude
    gpkg_kwargs = [
        (odir / f'cordova_exclude.gpkg', ie_exclude),
        (odir / f'cordova_include.gpkg', ie_include),
    ]

    make_plot(
        googlemaps_dir / 'Cordova1.tif', './fig15_Cordova1.png', gpkg_kwargs,
        plot_landcover=True, ijdoms=[(91,41)])

 

#(include_gpkg, 'pink'), (exclude_gpkg, 'deepskyblue')
#    make_plot(googlemaps_dir / 'Juneau1.tif', './fig15_Juneau.png', odir / f'juneau_include.gpkg', odir / f'juneau_exclude.gpkg', plot_landcover=True, ijdoms=[(113,45)])
main()

