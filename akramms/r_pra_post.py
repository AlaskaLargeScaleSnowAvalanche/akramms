import scipy.spatial
import pandas as pd
import shapely
from osgeo import gdal
from akramms import params,process_tree,chunk
from akramms.util import rammsutil
from uafgi.util import shputil,gdalutil,wrfutil,make,cfutil,ioutil,rasterize
import os,sys
import subprocess
import json
from akramms import config
import pyproj
import netCDF4
import numpy as np
import d8graph


# ---------------------------------------------------------------------------------


def rule(scene_dir, dem_filled_file, return_period, For, snowI_tif, **kwargs):
    """
    scene_dir:
        Uses params: name ("site"), resample_cell_size ("res")

    dem_filled_file: filename
        DEM that with sinks filled (while computing neighbor1)

    return_period:
        Return period we are calculating for.
        Must be included in scene_args['return_periods']

    forest: bool
        Whether we are doing with / without forest
    snowI_tif: str
        Name of the snowdepth file, in local scene coordinates, that we will use.

    kwargs forwarded to d8graph.find_domain():
        min_alpha: [deg]
            Minimum slope that "avalanche" can continue in domain finder
        max_runout:
            Maximum distance avalanche can go
       margin: [m]
           Margin to add around convex hull to minimum bounding rectangle.
    """

    scene_args = params.load(scene_dir)

    # Main input and output files: THESE MUST BE FIRST
    inputs = list()
    resolution = scene_args['resolution']
    scene_name = scene_args['name']
#    For = 'For' if forest else 'NoFor'

    # eCognition filename conventions
    pra_file = process_tree.pra_file(scene_args, return_period, For)
    inputs.append(pra_file)    # This rule does NOT use the burn files for domains...

    # Full pathnames of initial release files generated from this (scene_name, return_period, forest) combo
    # Initial release files are in the top-level RELEASE/ directory, before chopping into chunks.
    ramms_names = list()
    outputs = list()
    rn = f'{For}_{resolution}m{return_period}'
    for pra_size in config.allowed_pra_sizes:
        # Copied from rammsutil.RammsName
        ramms_name = (scene_name, rn, pra_size)
        ramms_names.append(ramms_name)
        for ext in ('_rel.shp', '_chull.shp', '_dom.shp'):
            outputs.append(scene_dir / 'RELEASE' / f'{scene_name}{rn}{pra_size}{ext}')

    # Add one-off input files
    inputs.append(snowI_tif)

    def action(tdir):

        degree = np.pi / 180.
        name = scene_args['name']
        resolution = scene_args['resolution']

        # Load the polygons (output of eCognition)
        # Reads columns: area_m2 Mean_DEM Mean_Slope Scene_reso
        print('======== Reading {}'.format(inputs[0]))
        df = shputil.read_df(inputs[0], shape='pra')
        df = df.rename(columns={'fid': 'Id'})    # RAMMS etc. want it named "Id"
        print('aa1 ', df)

        # Adds columns: j,i,sx3
        df = chunk.add_snow(df, snowI_tif, snow_density=200.)

        # Adds columns: d0star, slopecorr, Wind, d0_{return_period}, VOL_{return_period}
        df = chunk.add_corrections(df, return_period)

        # (grind_info includes the domain margin)
        grid_info, dem_filled, dem_nodata = gdalutil.read_raster(dem_filled_file)

        # ---------------------------------------------------------------
        # Split into segments based on PRA size, and save

        # Remove PRAs of elevation <150m
        df =  df[df['Mean_DEM'] >= 150.]            

        # Clip to the non-margin part of the local grid (subdomain)
        df = chunk.clip(df, scene_args['domain'])

        # Compute the avalanche domains (domain finder algo)
        # Adds columns: chull, dom
        df = chunk.add_dom(df, dem_filled, dem_nodata, grid_info, **kwargs)


        # Add PRA size designation of T,S,M,L
        # Adds column: pra_size
        df = chunk.add_pra_size(df)

        # Write out one top-level shapefile per pra_size
        wkt = scene_args['coordinate_system']
        for pra_size,cat_df in df.groupby('pra_size'):
            root = f'{scene_name}{For}_{resolution}m{return_period}{pra_size}'
            chunk.write_rel(
                cat_df, wkt, return_period,
                scene_dir / 'RELEASE' / f'{root}_rel.shp')

            chunk.write_chull(
                cat_df, wkt,
                scene_dir / 'RELEASE' / f'{root}_chull.shp')

            chunk.write_dom(
                cat_df, wkt,
                scene_dir / 'RELEASE' / f'{root}_dom.shp')


    rule = make.Rule(action, inputs, outputs)
    return rule, ramms_names



# -------------------------------------------------------
#            # Split df for this category (size) PRAs into bite-size chunks
#            df_chunks = [df_cat[i:i+config.max_ramms_pras] for i in range(0,df_cat.shape[0],config.max_ramms_pras)]
#            ofnames = list()
#            for segment,dfc in enumerate(df_chunks):
#                jb.set(segment=segment)
#                ofname = os.path.join(jb.ramms_dir, 'RELEASE', f'{jb.ramms_name}_rel.shp')
#                ofnames.append(ofname)
#                os.makedirs(os.path.split(ofname)[0], exist_ok=True)
#                shputil.write_df(dfc, 'pra', 'Polygon', ofname, wkt=scene_args['coordinate_system'])

#            # Write names of our PRA files into the final output file.
#            with open(output, 'w') as out:
#                for ofname in ofnames:
#                    out.write('{}\n'.format(config.roots.relpath(ofname)))
#
#                
#    return make.Rule(action, inputs, outputs)
# --------------------------------------------------------------------
#
#
#
#
#    # Full pathnames of release files generated from this (scene_name, return_period, forest) combo
#    outputs = list()
#    ramms_names = list()
#    for pra_size in rammsutil.PRA_SIZES.keys():    # T,S,M,L
#        # DEBUG: Only do 'L' for now
#        if pra_size not in config.allowed_pra_sizes:
#            continue
#        jb = rammsutil.RammsName(os.path.join(scene_dir, 'CHUNKS'), scene_name, None, forest, resolution, return_period, pra_size, None)
#        ramms_names.append((jb,pra_size))
#        # This filename does NOT have any segment numbers.
#        outputs.append(os.path.join(scene_dir, 'CHUNKS', f'{jb.ramms_name}_rel.shplist'))
#
