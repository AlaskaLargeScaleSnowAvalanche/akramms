import pathlib
import scipy.spatial
import pandas as pd
import shapely
from osgeo import gdal
from akramms import params,process_tree,chunk,level,file_info
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

"""Rules from just-after-eCognition to just-before-RAMMS Stage 1"""

__all__ = ('pra_post_rule', 'chunk_rule')

# ---------------------------------------------------------------------------------


def pra_post_rule(scene_dir, scene_args, dem_filled_file, return_period, For, snowI_tif, **kwargs):
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

#    scene_args = params.load(scene_dir)

    # Main input and output files: THESE MUST BE FIRST
    inputs = list()
    resolution = scene_args['resolution']
    scene_name = scene_args['name']
#    For = 'For' if forest else 'NoFor'

    # eCognition filename conventions
    pra_file = process_tree.pra_file(scene_args, return_period, For)
    inputs.append(pra_file)    # This rule does NOT use the burn files for domains...

    # Use the DEM mask
    dem_tif = pathlib.Path(scene_args['dem_file'])
    dem_mask_tif = dem_tif.parents[0] / (dem_tif.parts[-1][:-4] + '_mask.tif')
    inputs.append(dem_mask_tif)

    # Full pathnames of initial release files generated from this (scene_name, return_period, forest) combo
    # Initial release files are in the top-level RELEASE/ directory, before chopping into chunks.
#    ramms_names = list()
    outputs = list()
    # See email from Marc Christen 2023-01-23
#    rn = f'{For}_{resolution}m_{return_period}'
    for pra_size in config.allowed_pra_sizes:
        # Copied from rammsutil.RammsName
#        ramms_name = (scene_name, rn, pra_size)
#        ramms_names.append(ramms_name)

        root = f'{scene_name}{For}_{resolution}m_{return_period}{pra_size}'
        outputs.append(scene_dir / 'RELEASE' / f'{root}_rel.shp')
        outputs.append(scene_dir / 'RELEASE' / f'{root}_chull.shp')
        outputs.append(scene_dir / 'DOMAIN' / f'{root}_dom.shp')

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

        # Adds columns: j,i,sx3
        df = chunk.add_snow(df, snowI_tif, snow_density=200.)

        # Adds columns: d0star, slopecorr, Wind, d0_{return_period}, VOL_{return_period}
        df = chunk.add_corrections(df, return_period)

        # (grid_info includes the domain margin)
        grid_info, dem_filled, dem_nodata = gdalutil.read_raster(dem_filled_file)

        # ---------------------------------------------------------------
        # Split into segments based on PRA size, and save

        # Remove PRAs of elevation <150m and area < 100 m^2
        keep = ((df['Mean_DEM'] >= 150.) & (df['area_m2'] >= 1000.))
        df =  df[keep]

        # Clip to the non-margin part of the local grid (subdomain)
        gridI,dem_mask,_ = gdalutil.read_grid(dem_mask_tif)
        df = chunk.clip(df, gridI,dem_mask, scene_args['domain'])

        # Add PRA size designation of T,S,M,L
        # Adds column: pra_size
#        print('AA1 ', df.columns)
        df = chunk.add_pra_size(df)
#        print('AA2 ', df.columns)

        # Compute the avalanche domains (domain builder algo)
        # Adds columns: chull, dom
        df = chunk.add_dom(
            df, dem_filled, dem_nodata, grid_info,
            margins=config.initial_margins,
            **kwargs)
#        print('AA3 ', df.columns)

        # Write out one top-level shapefile per pra_size
        os.makedirs(scene_dir / 'RELEASE', exist_ok=True)
        os.makedirs(scene_dir / 'DOMAIN', exist_ok=True)

        wkt = scene_args['coordinate_system']
        for pra_size,cat_df in df.groupby('pra_size'):
#            print('AA4 ', cat_df.columns)
            root = f'{scene_name}{For}_{resolution}m_{return_period}{pra_size}'
            chunk.write_rel(
                cat_df, wkt, return_period,
                scene_dir / 'RELEASE' / f'{root}_rel.shp')

            chunk.write_chull(
                cat_df, wkt,
                scene_dir / 'RELEASE' / f'{root}_chull.shp')

            chunk.write_dom(
                cat_df, wkt,
                scene_dir / 'DOMAIN' / f'{root}_dom.shp')


    rule = make.Rule(action, inputs, outputs)
#    rule.ramms_names = ramms_names
#    rule.release_files = release_files
    return rule


# -----------------------------------------------------------------
def chunk_rule(scene_dir, scene_args, For, resolution, return_period, pra_size):
    """Generates the scenario file, which becomes key to running RAMMS.
    Also split into chunks.

    rn = f'{For}_{resolution}m{return_period}'

    release_file:
        Name of a release file after pra_post rule above (but before
        being split into chunks)
    """

#    scene_args = params.load(scene_dir)
    scene_name = scene_dir.parts[-1]    # Eg: x-113-045

    # Just include overall output files

    # See email from Marc Christen 2023-01-23
    base = f'{scene_name}{For}_{resolution}m_{return_period}{pra_size}'
#    base = f'r-{pra_size}'
    inputs = [
        scene_dir / 'RELEASE' / f'{base}_rel.shp',
        scene_dir / 'DOMAIN' / f'{base}_dom.shp',
        scene_args['dem_file'],
        scene_args['forest_file']]
    outputs = [
        scene_dir / 'RELEASE' / f'{base}_chunks.csv']

    def action(tdir):

        # Read the output from r_pra_post (above)
#        rdf = shputil.read_df(inputs[0], shape='pra').set_index('Id')
        rdf = chunk.read_reldom(inputs[0])

        # Assign a chunkid to each avalanche
        rdf['combo'] = [level.theory_scenedir_to_combo(scene_dir)] * len(rdf.index)
        rdf['pra_size'] = pra_size
        rdf = chunk.set_new_chunkinfo(rdf, scene_args)
        rdf = chunk.add_chunkid(rdf, scene_dir, append=False)

        # Create the chunks
        for chunkid,dfc in rdf.groupby('chunkid'):
            chunk_info = file_info.ChunkInfo(scene_dir, scene_name, chunkid, For, resolution, return_period, pra_size)
            chunk.write_chunk(scene_args, chunk_info, dfc, {})

        # Create the _chunks.csv control file showing the chunks have all been created
        rdf.to_csv(outputs[0])

    return make.Rule(action, inputs, outputs)
# -----------------------------------------------------------------
