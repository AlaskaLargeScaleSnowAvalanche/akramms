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

# ------------------------------------------------
def regrid_wrf(idir, ileaf, vname, odir, scene_name, wrf_grid_info, scene_grid_info):
    """Regrids a WRF file"""
    ifname = os.path.join(idir, ileaf)
    ileaf_base = os.path.splitext(ileaf)[0]
    ofname = os.path.join(odir, f'{ileaf_base}_{scene_name}.tif')
    if os.path.exists(ofname):
        _,lwrf_val = gdalutil.read_raster(ofname)
    else:
        #wrf_grid_info = wrfutil.wrf_info(wrf_geo_nc)
        print('Reading ', ifname, vname)
        wrf_val = wrfutil.read_raw(ifname, vname)
        lwrf_val = gdalutil.regrid(
            wrf_val, wrf_grid_info, scene_grid_info,
            resample_algo=gdalconst.GRA_NearestNeighbour)
        gdalutil.write_raster(ofname, scene_grid_info, lwrf_val, np.nan)

    return lwrf_val

# ------------------------------------------------

def main():
    # Read regridded WRF files: DEM and sx3 (snow depth)
    scene_args = params.load(scene_dir)
    scene_grid_info, scene_dem, dem_nodata = gdalutil.read_raster(scene_args['dem_file'])
    print('dem_nodata = ', dem_nodata)
    wrf_grid_info = wrfutil.wrf_info(wrf_geo_nc)
    lwrf_dem = regrid_wrf(
        sx3_dir, 'geo_southeast.nc', 'HGT_M', '.', scene_args['name'],
        wrf_grid_info, scene_grid_info)

    lwrf_sx3 = regrid_wrf(
        sx3_dir, 'ccsm_sx3_2010.nc', 'sx3', '.', scene_args['name'],
        wrf_grid_info, scene_grid_info)


    # Compute something
    demdiff = scene_dem - lwrf_dem

    # Store in GeoTIFF
    gdalutil.write_raster('demdiff.tif', scene_grid_info, demdiff, np.nan)

main()
