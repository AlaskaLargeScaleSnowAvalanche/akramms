import os
import numpy as np
from osgeo import gdal
import zipfile,netCDF4
from uafgi.util import gdalutil
from akramms import experiment


_mosaic_metadata = {
    'dem': (gdal.GDT_Float32, {
        'description': 'IFSAR Digital elevation model',
        'units': 'm'
    }),

    'landcover': (gdal.GDT_Int16, {
        'description': 'USGS Land cover types',
        'units': 'm'
    }),

    'deposition': (gdal.GDT_Float64, {
        'description': 'Maximum deposition from any avalanche',
        'units': 'm'
    }),
    'max_velocity': (gdal.GDT_Float64, {
        'description': 'Maximum snow speed from any avalanche',
        'units': 'm s-1',
    }),
    'max_pressure': (gdal.GDT_Float64, {
        'description': 'Maximum pressure from any avalanche',
        'units': 'Pa',
    }),
    'avalanche_count': (gdal.GDT_Int16, {
        'description': 'Number of avalanches hitting this gridcell',
    }),
    'domain_count': (gdal.GDT_Byte, {
        'description': 'Number of avalanches hitting this gridcell',
    }),
}
_avoid = ('dem', 'landcover')    # Only include these if user provides fetch fn
_mosaic_keys = list(x for x in _mosaic_metadata.keys() if x not in _avoid)

def ozip_write(ozip, fname):
    """Writes with truncated arcname"""
    ozip.write(fname, arcname=os.path.split(fname)[1])

def mosaic_avals(gridM, avals, ofname_zip, tdir,
    rho=300, vars=_mosaic_keys,
    dem_fn=None, landcover_fn=None):

    """General mosaic function for a bunch of avalanches and a domain

    gridM:
        Sub-grid (of global gridG) defining the extent of our mosaic domain
    avals:
        Generator of NetDCDF avalanche filenames to mosaic
    ofname_zip:
        Name of output .zip filename where mutlipe geoTIFFs will be stored
    tdir:
        Put temporary stuff here

    rho: [kg m-3]
        Density of snow to use in obtaining max_pressure
    vars: [vname, ...]
        Variables to include in final output.  See _mosaic_metadata for legal keys:
        deposition, max_velocity, max_pressure, avalanche_count, domain_count
    dem_fn, landcover_fn:
        Functions to extract the DEM and landcover defs, respectively.
        Typically taken from exp_mod
        Include these if you want DEM and landcover files added to the output.
    """
    vars_set = set(vars)

    vals = dict(
        deposition=np.zeros((gridM.ny, gridM.nx), dtype='d'),
        max_velocity=np.zeros((gridM.ny, gridM.nx), dtype='d'),
        max_pressure=np.zeros((gridM.ny, gridM.nx), dtype='d'),
        avalanche_count=np.zeros((gridM.ny, gridM.nx), dtype='i'),
        domain_count=np.zeros((gridM.ny, gridM.nx), dtype='i'))

    deposition = vals['deposition']
    max_velocity = vals['max_velocity']
    max_pressure = vals['max_pressure']
    avalanche_count = vals['avalanche_count']
    domain_count = vals['domain_count']

#    print('gridD ', exp_mod.gridD)
#    print('gridM ', gridM)

    for aval_i,fname in enumerate(avals):
#        if aval_i > 3:
#            break    # DEBUGGING

        with netCDF4.Dataset(fname) as nc:

            print('Processing {}: ({} of {}): {} gridcells'.format(
                os.path.basename(fname),
                aval_i, len(avals),
                nc.variables['i_diff'].shape))

            # "gridA" = Avalanche's local grid (it will be one of the subdomains), WITH MARGIN
            # Geotransform of this avalanche's local grid
            # TODO: Store Geotransform as machine-precision doubles in the file
            gridA_gt = np.array([float(x) for x in nc.variables['grid_mapping'].GeoTransform.split(' ')])
#            print('gridA_gt ', gridA_gt)

            deltai = int(-(gridM.x0 - gridA_gt[0]) / gridM.dx + 0.5)
            deltaj = int(-(gridM.y0 - gridA_gt[3]) / gridM.dy + 0.5)

#            print('deltaxxxxx ', gridM.x0, gridA_gt[0], gridM.dx)
#            print('deltayyyyy ', gridM.y0, gridA_gt[3], gridM.dy)
#            print('delta i/j ', deltai, deltaj)

            # Load (i,j) of each avalanche and convert to local mosaic-box coordinates
            iis = np.cumsum(nc.variables['i_diff'][:]) + deltai
            jjs = np.cumsum(nc.variables['j_diff'][:]) + deltaj
#            print(jjs), gridM.ny
#            print(iis), gridM.nx
            good_ixs = np.where(np.logical_and.reduce((iis >= 0, iis < gridM.nx, jjs >= 0, jjs < gridM.ny)))
#            print('good_ixs ', good_ixs, gridM.nx, gridM.ny)

            # Clip out-of-query-range gridcells
            _iis = iis[good_ixs]
            _jjs = jjs[good_ixs]

            # Load original variables
            _max_vel = nc.variables['max_vel'][good_ixs]
            _max_height = nc.variables['max_height'][good_ixs]
            _depo = nc.variables['depo'][good_ixs]

            domain_count[_jjs,_iis] += 1    # 1 if any domain touches this

            # Narrow down to ONLY cells that avalanche touched
            nz_ixs = np.where(_max_vel > 0)
            _iis = _iis[nz_ixs]
            _jjs = _jjs[nz_ixs]
            _max_vel = _max_vel[nz_ixs]
            _max_height = _max_height[nz_ixs]
            _depo = _depo[nz_ixs]

            # Mosaic into final variables
#            print('jjs ', _jjs)
#            print('iis ', _iis)
#            print('deposition ', deposition[_jjs,_iis])
#            print('_depo ', _depo)
            deposition[_jjs,_iis] = np.maximum(deposition[_jjs,_iis], _depo)
            max_velocity[_jjs,_iis] = np.maximum(max_velocity[_jjs,_iis], _max_vel)
            max_pressure[_jjs,_iis] = np.maximum(max_pressure[_jjs,_iis], rho * _max_vel*_max_vel)
            avalanche_count[_jjs,_iis] += 1    # 1 if it touches cell, otherwise 0

    # Write output GeoTIFF and Zip it up
    with zipfile.ZipFile(ofname_zip, mode='w', compression=zipfile.ZIP_STORED) as ozip:

        box_poly = gridM.bounding_box


        # Other variables
#        print('vars ', vars)
#        for vname, val in vars.items():
        for vname in vars:
            if vname in {'dem', 'landcover'}:
                continue    # Already handled above
            val = vals[vname]
            gdal_type,_meta = _mosaic_metadata[vname]
            meta = dict(_meta)
            if vname == 'max_pressure':
                meta['rho'] = f'{rho} [kg m-3]'
            ofn = os.path.join(tdir.location, f'{vname}.tif')
            gdalutil.write_raster(ofn, gridM, val, 0, type=gdal_type, metadata=meta)
            ozip_write(ozip, ofn)
            ozip_write(ozip, os.path.join(tdir.location, f'{vname}.tfw'))

        # These are last so they appear as lower layers in QGIS
        # Land Cover
        if 'landcover' in vars_set:
            ofn = os.path.join(tdir.location, 'landcover.tif')
            landcover_fn(box_poly, os.path.join(tdir.location, 'landcover.tif'))
            ozip_write(ozip, ofn)
            ozip_write(ozip, os.path.join(tdir.location, 'landcover.tif.aux.xml'))
            ozip_write(ozip, os.path.join(tdir.location, 'landcover.tfw'))

        # DEM
        if 'dem' in vars_set:
            ofn = os.path.join(tdir.location, 'dem.tif')
            dem_fn(box_poly, ofn)
            ozip_write(ozip, ofn)
            ozip_write(ozip, os.path.join(tdir.location, 'dem.tfw'))







#
#def main():
#    from uafgi.util import ioutil
#    from akramms import experiment
#
#    import akramms.e_alaska as exp_mod
#
#    res = exp_mod.resolution
#    gridG = exp_mod.gridD.global_grid(res, res)
##    gridM = exp_mod.gridD.sub(113,45, res, res)    # Could be arbitrary rectangle
#    gridM = exp_mod.gridD.subgrid(
#        1109800, 1107000,
#        1111300, 1108000,
#        res, res)
#
#    avals = ['/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/arc-113-045/aval-1762.nc']
#    with ioutil.TmpDir(tdir='tmp', remove=False) as tdir:
#        mosaic_avals(exp_mod, gridM, avals, 'avals2.zip', tdir=tdir)
#
#main()

# 
# 
# # Ways to select avalanches:
# # 1. By bouding box
# # 2. By scene (just use bounding box of scene)
# 
# 
# ** Add scene info to NetCDF avalanches
# 
# ** In PRA_post: only include avalanches whose PRA is >50% in the main part of the domain.
# 
# 
# 
# def select_aval(exp_mod, x0,y0,x1,y1):
# 
# * Determine (i0,j0,i1,j1) of mosiac rectangle in master coordinate system
# * Determine which domains we overlap with
# * for each overlapping domain:
#   * Determine (i,j) offset of domain from master coordinate system (relative to 0,0)
#   * Determine (i,j) delta offset to apply to (i,j) coordinates in this domain
#   * for each avalanche:
#     * Read data from NetCDF
#     * Convert to (i,j) coordinates of mosiac rectangle
#     * Get rid of any coordinates outside of mosaic rectangle (eg: negative, or >= x1/y1)
#     * Mosaic it in!
# 
# # 2. 
#     def ijbox_indexgrid(self, ix, iy, margin=False):
#         """Returns (i0,j0,i1,j1) of the given domain *index grid* J.
#         The index grid is the (i,j) gridcell coordinate system defined
#         by the (0,0) ("origin") domain."""
# 
# TODO: See 300 return period, test on two domains

