import os
import numpy as np
from akramms import config,params
from uafgi.util import gdalutil,wrfutil
from osgeo import gdalconst

# wrf-format files
sx3_dir = config.roots.syspath('{DATA}/lader/sx3')
wrf_geo_nc = os.path.join(sx3_dir, 'geo_southeast.nc')

wrf_sx3_nc = os.path.join(sx3_dir, 'ccsm_sx3_2010.nc')

# regridded-files
lwrf_dem_tif = 'geo_southeast_4km_HGT_local.tif'
lwrf_sx3_tif = 'ccsm_sx3_2010_local.tif'

# Scene definition
scene_dir = config.roots.syspath('{PRJ}/juneau1')


def slope_file(scene_args, forest, *args):
    """Returns name of a file in the slope directory"""
    For = 'For' if forest else 'NoFor'
    name = scene_args['name']
    resolution = scene_args['resolution']
    return os.path.join(scene_args['dir'], 'SLOPE_TIF', f'{name}{For}_{resolution}m', *args)

# ------------------------------------------------
def regrid_wrf(idir, ileaf, vname, odir, scene_name, wrf_grid_info, scene_grid_info):
    """Regrids a WRF file"""
    ifname = os.path.join(idir, ileaf)
    ileaf_base = os.path.splitext(ileaf)[0]
    ofname = os.path.join(odir, f'{ileaf_base}_{scene_name}.tif')
    if os.path.exists(ofname):
        print('Reading regridded file: {}'.format(ofname))
        _,lwrf_val,nodata_value = gdalutil.read_raster(ofname)
    else:
        #wrf_grid_info = wrfutil.wrf_info(wrf_geo_nc)
        print('Reading ', ifname, vname)
        wrf_val,nodata_value = wrfutil.read_raw(ifname, vname)
        if len(wrf_val.shape) == 3:
            wrf_val = wrf_val[0,:]    # Get rid of Time dimension

        print(f'nodata_value({vname}) = {nodata_value}')
        lwrf_val = gdalutil.regrid(
            wrf_val, wrf_grid_info, nodata_value,
            scene_grid_info, nodata_value,
            resample_algo=gdalconst.GRA_NearestNeighbour)
        gdalutil.write_raster(ofname, scene_grid_info, lwrf_val, nodata_value)

    return lwrf_val,nodata_value

# ------------------------------------------------

def main():
    # Read regridded WRF files: DEM and sx3 (snow depth)
    scene_args = params.load(scene_dir)
    scene_grid_info, scene_dem, dem_nodata = gdalutil.read_raster(scene_args['dem_file'])
    print('dem_nodata = ', dem_nodata)
    wrf_grid_info = wrfutil.wrf_info(wrf_geo_nc)
    lwrf_dem,lwrf_dem_nodata = regrid_wrf(
        sx3_dir, 'geo_southeast.nc', 'HGT_M', '.', scene_args['name'],
        wrf_grid_info, scene_grid_info)

    lwrf_sx3,lwrf_sx3_nodata = regrid_wrf(
        sx3_dir, 'ccsm_sx3_2010.nc', 'sx3', '.', scene_args['name'],
        wrf_grid_info, scene_grid_info)

    # Figure where we are masked
    mask_out = (lwrf_sx3 == lwrf_sx3_nodata)

    # Read slope
    slope_grid_info, slope, slope_nodata = gdal.read_raster(slope_file(scene_args, True, 'slope.tif'))


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
    slopecorr =  0.291 / \
        (np.sin(mean_slope_rad) - 0.202 * np.cos(mean_slope_rad))

    # Wind load interpolation between 100 (0) and 200 (full wind load) elevation
    # Change max wind load dependent on scenario!!
    # TODO: Discuss with Gabe, how we do the wind load.
    wind = np.clip((dem - 1000.) * .0001, 0., 0.1)

    # Calculate final d0: d0_10, d0_30, d0_100, d0_300
    d0 = (d0star + wind) * slopecorr
    #d0 = 0.5    # DEBUG: d0_30 is unrealistically low.

    # Calculate volume per unit horizontal area (VOL_returnperiod)
    # df[VOL_vname] = df['area_m2'] / np.cos(df['Mean_Slope']*degree) * df[d0_vname]
    volume = df[d0_vname]) / np.cos(slope*degree)

    # --------------------------------------------------------------------------------------

#    # Compute something
#    demdiff = scene_dem - lwrf_dem
#    final_nodata = -1e30
#    demdiff[mask_out] = final_nodata
#
#    # Store in GeoTIFF
#    gdalutil.write_raster('demdiff.tif', scene_grid_info, demdiff, final_nodata)

main()
