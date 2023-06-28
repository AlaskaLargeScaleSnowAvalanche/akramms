import os,argparse
import numpy as np
from akramms import config,params
from uafgi.util import gdalutil,wrfutil
from osgeo import gdalconst



parser = argparse.ArgumentParser(prog='run_ramms',
    description="""Prepare a snow input file for RAMMS by selecting values for the hi-res
        grid out of the WRF sx3 grid.""")

parser.add_argument('input',
    help='Config-style pathname of input NetCDF file to select from.')
parser.add_argument('--output', '-o', default=None,
    help='Config-style pathname of output NetCDF file.')
# ----------------------------------------------------------------


def main():
    args = parser.parse_args()
    ifname = config.roots.syspath(args.input)
    ofname = config.roots.syspath(args.output)
    print(ifname)
    print(ofname)

main()





#
## wrf-format files
#sx3_dir = config.roots.syspath('{DATA}/lader/sx3')
#wrf_geo_nc = os.path.join(sx3_dir, 'geo_southeast.nc')
#
#wrf_sx3_nc = os.path.join(sx3_dir, 'ccsm_sx3_2010.nc')
#
## regridded-files
#lwrf_dem_tif = 'geo_southeast_4km_HGT_local.tif'
#lwrf_sx3_tif = 'ccsm_sx3_2010_local.tif'
#
## Scene definition
#scene_dir = config.roots.syspath('{PRJ}/juneau1')

 
def slope_file(scene_args, forest, *args):
    """Returns name of a file in the slope directory"""
    For = 'For' if forest else 'NoFor'
    name = scene_args['name']
    resolution = scene_args['resolution']
    return os.path.join(scene_args['scene_dir'], 'SLOPE_TIF', f'{name}{For}_{resolution}m', *args)

# ------------------------------------------------
def regrid_wrf(idir, ileaf, vname, odir, scene_name, wrf_grid, scene_grid):
    """Loads and regrids a WRF file (memoized)"""
    ifname = os.path.join(idir, ileaf)
    ileaf_base = os.path.splitext(ileaf)[0]
    ofname = os.path.join(odir, f'{ileaf_base}_{scene_name}.tif')
    if os.path.exists(ofname):
        print('Reading regridded file: {}'.format(ofname))
        _,lwrf_val,nodata_value = gdalutil.read_raster(ofname)
    else:
        #wrf_grid = wrfutil.wrf_info(wrf_geo_nc)
        print('Reading ', ifname, vname)
        wrf_val,nodata_value = wrfutil.read_raw(ifname, vname)
        if len(wrf_val.shape) == 3:
            wrf_val = wrf_val[0,:]    # Get rid of Time dimension

        print(f'nodata_value({vname}) = {nodata_value}')
        lwrf_val = gdalutil.regrid(
            wrf_val, wrf_grid, nodata_value,
            scene_grid, nodata_value,
            resample_algo=gdalconst.GRA_NearestNeighbour)
        gdalutil.write_raster(ofname, scene_grid, lwrf_val, nodata_value)

    return lwrf_val,nodata_value

# ------------------------------------------------
#def read_slope_tif(scene_args):

def xmain():

    scene_args = params.load(scene_dir)

    # Read hi-res DEM
    print('Reading: ', scene_args['dem_file'])
    gridI, demI, demI_nodata = gdalutil.read_raster(scene_args['dem_file'])

    # Read slope --- and regrid to larger bounds used by the DEM
    sf = slope_file(scene_args, True, 'slope.tif')
    print('Reading: ', sf)
    xslope_grid_info, xslope, slope_nodata = gdalutil.read_raster(sf)

    slope = gdalutil.regrid(
        xslope, xslope_grid_info, slope_nodata,
        gridI, slope_nodata,
        resample_algo=gdalconst.GRA_NearestNeighbour)
    xslope = None

    print('    slope: ', slope.shape)
    print('demI: ', demI.shape)

    # Read regridded WRF files: DEM and sx3 (snow depth)
    print('demI_nodata = ', demI_nodata)
    gridA = wrfutil.wrf_info(wrf_geo_nc)
    wrfdemI,wrfdemI_nodata = regrid_wrf(
        sx3_dir, 'geo_southeast.nc', 'HGT_M', '.', scene_args['name'],
        gridA, gridI)
    sx3I,sx3I_nodata = regrid_wrf(
        sx3_dir, 'ccsm_sx3_2010.nc', 'sx3', '.', scene_args['name'],
        gridA, gridI)

    # Figure where we are masked
    mask_out = (sx3I == sx3I_nodata)

    print('    demI: ', demI.shape)
    print(' wrfdemI: ', wrfdemI.shape)
    print('    sx3I: ', sx3I.shape)

    sx3 = sx3I
    dem = wrfdemI

    # ---------------------------------------------------------------------

    gradient_snowdepth_si_units = .01 * scene_args['gradient_snowdepth'] # gradient_snowdepth parameter is in m/100m, translate to unitless

    snowdepth_correction = \
        (lwrf_dem - scene_args['reference_elevation']) \
            * gradient_snowdepth_si_units
    sx3_corrected = (sx3 + snowdepth_correction)

    # TODO: Why are we multiplying by cos(28) = .883?

    # Very old rule developed 30-40 years ago: the steeper the
    # slope, the less snow that can accumulate.  Very
    # traditional from SLF.  DO NOT use for Alaska.

    # (BUT... the steeper a release point is, the less snow it
    # has, MIGHT be useful for Alaska.  TODO: Discuss with
    # Gabe).  If snow is very moist...???
    degree = np.pi / 180.
    if False:
        d0star = sx3_corrected * np.cos(28. * degree)
    else:
        d0star = sx3_corrected


    # --- Slope angle correction (slopecorr)
    # TODO: Discuss with Gabe.  Do we want to apply slope angle correction?
    # If yes, we can make it much simpler than what we have here.
    mean_slope_rad = slope * degree
    slopecorr = 0.219 / np.sin(mean_slope_rad) - 0.202 * np.cos(mean_slope_rad)

#    # Store in GeoTIFF
#    gdalutil.write_raster('slopecorr.tif', gridI, sx3_corrected, final_nodata)
#    return

    # Wind load interpolation between 100 (0) and 200 (full wind load) elevation
    # Change max wind load dependent on scenario!!
    # TODO: Discuss with Gabe, how we do the wind load.
    wind = np.clip((wrfdemI - 1000.) * .0001, 0., 0.1)

    # Calculate final d0: d0_10, d0_30, d0_100, d0_300
    d0 = (d0star + wind) * slopecorr
    #d0 = 0.5    # DEBUG: d0_30 is unrealistically low.



    # Calculate volume per unit horizontal area (VOL_returnperiod)
    # df[VOL_vname] = df['area_m2'] / np.cos(df['Mean_Slope']*degree) * df[d0_vname]
    volume = d0 / np.cos(slope*degree)

    # --------------------------------------------------------------------------------------

#    # Compute something
#    demdiff = demI - lwrf_dem
#    final_nodata = -1e30
#    demdiff[mask_out] = final_nodata


#main()
