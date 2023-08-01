import subprocess
import os,pathlib,shutil
import netCDF4
import numpy as np
from osgeo import gdalconst
from uafgi.util import wrfutil,gdalutil
from akramms import config,process_tree
from akramms.util import paramutil,harnutil,arcgisutil
from uafgi.util import make
from akramms import params

"""Rules to prepare the snow field for direct use in determining snow depth for PRAs."""

def select_sx3_rule(scene_dir, sx3_file, geo_nc):
    """Regrids Lader's SX3 to the scene grid, and selects the nearest neighbor.
    sx3_file:
        Name of the input WRF NetCDF file to use.
        Eg: 555config.syspath('{DATA}/lader/sx3/cfsr_2010_sx3.nc')
                  cfsr: reanalysis
            ccsm, gfdl: climate models
    geo_nc:
        Name of the WRF geometry file that describes input.
        Eg: config.syspath('{DATA}/lader/sx3/geo_southeast.nc')
    """

    scene_args = params.load(scene_dir)
    scene_name = scene_args['name']

    inputs = [sx3_file]
    leaf = os.path.split(sx3_file)[1]
    base = os.path.splitext(leaf)[0]
    outputs = [os.path.join(scene_dir, f'{base}_{scene_name}_select.tif')]

    def action(tdir):
        # Read input from WRF
        gridA = wrfutil.wrf_info(geo_nc)
        sx3A,sx3A_nd = wrfutil.read_raw(sx3_file, 'sx3', fill_holes=True)    # NOTE: All gridcells are expected to have data
        if len(sx3A.shape) == 3:
            sx3A = sx3A[0,:]    # Get rid of Time dimension

        # Construct output grid (and also read the DEM, which might be useful elsewhere)
        gridI, elevI, elevI_nd = gdalutil.read_raster(scene_args['dem_file'])

        # Regrid sx3
        sx3I = gdalutil.regrid(
            sx3A, gridA, float(sx3A_nd),
            gridI, float(sx3A_nd),
            resample_algo=gdalconst.GRA_NearestNeighbour)

        # Write output
        gdalutil.write_raster(outputs[0], gridI, sx3I, sx3A_nd)
 
    return make.Rule(action, inputs, outputs)


#rule = select_sx3_rule(
#    '/home/efischer/prj/juneau1',
#    '/home/efischer/av/data/outputs/sx3/ccsm_sx3_1981_2010.nc',
#    '/home/efischer/av/data/lader/sx3/geo_southeast.nc')
#rule.action(None)

