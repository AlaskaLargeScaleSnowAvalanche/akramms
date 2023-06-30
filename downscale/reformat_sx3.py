import numpy as np
import os,re,functools
#import matplotlib.pyplot as plt
from uafgi.util import gdalutil,wrfutil,gisutil,ncutil
from akramms import config,params
#import findiff
#import scipy.ndimage
#import scipy.signal
import pyproj
import netCDF4
from osgeo import gdal

"""Does the following transformations to the WRF ccsm data:

1. Convert all files to .tif
2. Aggregate together the following values by maximum; and write out as tif and nc:
   Baseline: 1981 -- 2020
   Decades: 2031 -- 2040, etc.
"""

sx3_dir = config.roots.syspath('{DATA}/lader/sx3')
odir = config.roots.syspath('{DATA}/outputs/sx3')

aggs = (
    (1981, 2010),
    (1981, 1990),
    (1991, 2000),
    (2001, 2010
    (2031, 2040),
    (2041, 2050),
    (2051, 2060))

ccsmRE = re.compile(r'(ccsm_sx3_\d\d\d\d)\.nc$')


@functools.lru_cache()
def ccsm_schema():
    with netCDF4.Dataset(os.path.join(sx3_dir, 'ccsm_sx3_1981.nc')) as ncin:
        return ncutil.Schema(ncin)


def write_file(grid, sx3, ofbase, types={'tif', 'nc'}):
    """Writes a result to both .tif and NetCDF"""

    schema = ccsm_schema()

    # Write as GeoTIFF
    if 'tif' in types:
        gdalutil.write_raster(
            ofbase+'.tif', grid, sx3,
            schema.vars['sx3'].attrs['_FillValue'], type=gdal.GDT_Float32)

    # Write as NetCDF
    if 'nc' in types:
        with netCDF4.Dataset(ofbase+'.nc', 'w') as ncout:
            schema.create(ncout)
            ncout.variables['sx3'][:] = sx3[:]

def main():
    os.makedirs(odir, exist_ok=True)

    # Get WRF grid info
    wrf_geo_nc = os.path.join(sx3_dir, 'geo_southeast.nc')
    gridA = wrfutil.wrf_info(wrf_geo_nc)

    # Convert individual files
    names = list()
    for name in os.listdir(sx3_dir):
        match = ccsmRE.match(name)
        if match is None:
            continue
        names.append((name, match.group(1)))

    for name,base in sorted(names):
        ifname = os.path.join(sx3_dir, name)
        ofbase = os.path.join(odir, base)

        print(f'------- {ifname}')
        sx3, sx3_nd = wrfutil.read_raw(ifname, 'sx3', fill_holes=True)
        print(ofbase)
        write_file(gridA, sx3, ofbase, types={'tif'})

    # Compute range maximums
    for year0, year1 in aggs:
        olabel = f'{year0}_{year1}'

        # Read all the given years and accumulate into maximum
        sx3,_ = wrfutil.read_raw(os.path.join(sx3_dir, f'ccsm_sx3_{year0:04d}.nc'), 'sx3')
        for year in range(year0+1, year1+1):    # year1 is inclusive
            sx3x,_ = wrfutil.read_raw(os.path.join(sx3_dir, f'ccsm_sx3_{year:04d}.nc'), 'sx3')
            sx3 = np.maximum(sx3, sx3x)

        # write it out
        write_file(gridA, sx3, os.path.join(odir, f'ccsm_sx3_{olabel}'))

main()
