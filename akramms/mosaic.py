from osgeo import gdal
import zipfile,netCDF4
from uafgi.util import gdalutil
from akramms import experiment
import numpy as np


_mosaic_metadata = {
    'elevation': (gdal.GDT_Float32, {
        'units': 'm'
    }),
    'elevation': (gdal.GDT_Int16, {
        'description': 'Digital elevation model',
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
    'count': (gdal.GDT_Int16, {
        'description': 'Number of avalanches hitting this gridcell',
    }),
}
_mosaic_keys = list(_mosaic_metadata.keys())

def mosaic_aval(exp_mod, gridM, avals, ofname_zip, rho=300, tdir=None, vars=_mosaic_keys):

    """
    exp_mod:
        Experiment definition
    gridM:
        Sub-grid (of global gridG) defining the extent of our mosaic domain
    rho: [kg m-3]
        Density of snow to use in obtaining max_pressure
    avals:
        Generator of avalanche filenames to mosaic
    ofname_zip:
        Name of output .zip filename where mutlipe geoTIFFs will be stored
    vars: [vname, ...]
        Variables to include in final output
    tdir:
        Put temporary stuff here
    """
    vars_set = set(vars)

    _vars = dict(
        deposition=np.zeros((gridM.ny, gridM.nx), dtype='d'),
        max_velocity=np.zeros((gridM.ny, gridM.nx), dtype='d'),
        max_pressure=np.zeros((gridM.ny, gridM.nx), dtype='d'),
        count=np.zeros((gridM.ny, gridM.nx), dtype='i'))

    deposition = _vars['deposition']
    max_velocity = _vars['max_velocity']
    max_pressure = _vars['max_pressure']
    count = _vars['count']

    print('gridD ', exp_mod.gridD)
    print('gridM ', gridM)

    for fname in avals:
        with netCDF4.Dataset(fname) as nc:

            # "gridA" = Avalanche's local grid (it will be one of the subdomains), WITH MARGIN
            # Geotransform of this avalanche's local grid
            # TODO: Store Geotransform as machine-precision doubles in the file
            gridA_gt = np.array([float(x) for x in nc.variables['grid_mapping'].GeoTransform.split(' ')])
            print('gridA_gt ', gridA_gt)

            deltai = int((gridM.x0 - gridA_gt[0]) / gridM.dx + 0.5)
            deltaj = int((gridM.y0 - gridA_gt[3]) / gridM.dy + 0.5)

            # Load (i,j) of each avalanche and convert to local mosaic-box coordinates
            iis = np.cumsum(nc.variables['i_diff'][:]) + deltai
            jjs = np.cumsum(nc.variables['j_diff'][:]) + deltaj
            print(jjs), gridM.ny
            print(iis), gridM.nx
            good_ixs = np.where(
                np.logical_and.reduce((iis >= 0, iis < gridM.nx, jjs >= 0, jjs < gridM.ny)))

            # Load original variables, and clip out-of-range gridcells
            _iis = iis[good_ixs]
            _jjs = jjs[good_ixs]
            _max_vel = nc.variables['max_vel'][good_ixs]
            _max_height = nc.variables['max_height'][good_ixs]
            _depo = nc.variables['depo'][good_ixs]

            # Mosaic into final variables
            deposition[_jjs,_iis] = np.max(deposition[_jjs,_iis], _depo)
            max_velocity[_jjs,_iis] = np.max(max_velocity[_jjs,_iis], _max_vel)
            max_pressure[_jjs,_iis] = np.max(max_pressure[_jjs,_iis], rho * _max_vel*_max_vel)
            count[_jjs,_iis] += 1

    # Write output GeoTIFF and Zip it up
    with zipfile.ZipFile(ofname_zip, mode='w', compression=zipfile.ZIP_STORED) as ozip:

        # DEM
        if 'dem' in vars_set:
            ofn = os.path.join(tdir.location, 'dem.tif')
            exp_mod.extract_dem(box_poly, ofn)
            ozip.write(ofn)

        # Land Cover
        if 'landcover' in vars_set:
            ofn = os.path.join(tdir.location, 'landcover.tif')
            exp_mod.extract_dem(box_poly, ofn)
            ozip.write(ofn)

        exp_mod.extract_landcover(box_poly, os.path.join(tdir.location, 'landcover.tif'))

        # Other variables
        for vname, val in vars:
            if vname in {'dem', 'landcover'}:
                continue    # Already handled above
            gdal_type,_meta = _mosaic_metadata[vname]
            meta = dict(_meta)
            if vname == 'max_pressure':
                meta['rho'] = f'{rho} [kg m-3]'
            ofn = os.path.join(tdir.location, f'{vname}.tif')
            gdalutil.write_raster(ofn, gridM, val, type=gdal_type, metadata=meta)
            ozip.write(ofn)

def main():
    from uafgi.util import ioutil
    from akramms import experiment

    import akramms.e_alaska as exp_mod

    res = exp_mod.resolution
    gridG = exp_mod.gridD.global_grid(res, res)
    gridM = exp_mod.gridD.sub(113,45, res, res)    # Could be arbitrary rectangle
    avals = ['/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/arc-113-045/aval-524.nc']
    with ioutil.TmpDir(tdir='tmp', remove=False) as tdir:
        mosaic_aval(exp_mod, gridM, avals, 'avals.zip', tdir=tdir)

main()

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

