import os
import numpy as np
from osgeo import gdal
import zipfile,netCDF4
from uafgi.util import gdalutil,cfutil
from akramms import experiment
import _mosaic

# python -m cProfile -o prof -s cumtime `which akramms` mosaic juneau1-1981-1990.qy 

# =======================================================================
# ====== Extent Processing

def union_extents(extents):
    """Finds an extent enclosing all the given extents
    extents: [(x0,y0, x1,y1), ...]
    """
    iext = iter(extents)

    z0 = next(iext)
    assert z0[2] >= z0[0]    # Check for correct sign
    assert z0[3] >= z0[1]
    for z1 in iext:
        assert z1[2] >= z1[0]
        assert z1[3] >= z1[1]
        z0 = (
            min(z0[0], z1[0]),
            min(z0[1], z1[1]),
            max(z0[0], z1[0]),
            max(z0[1], z1[1]))

    return z0
# -----------------------------------------------------------------
def extents_intersect(extent0, extent1):
    """Intersects to extents.
    ext0, ext1: [x0,y0, x1,y1]

    See: https://saturncloud.io/blog/algorithm-to-check-if-two-boxes-overlap/
    """
    x1_1, y1_1, x2_1, y2_1 = extent0
    x1_2, y1_2, x2_2, y2_2 = extent1

    if x2_1 < x1_2 or x2_2 < x1_1:
        return False

    if y2_1 < y1_2 or y2_2 < y1_1:
        return False

    return True

# -----------------------------------------------------------------
def nc_extent(nc_fname):
    """Determines the extent of an archived NetCDF file"""
    with netCDF4.Dataset(nc_fname) as nc:
        bbox = nc.variables['bounding_box'][:].reshape(-1)    # [x0,y0,x1,y1]
    return bbox
# -----------------------------------------------------------------
def add_margin(extent, margin):
    """Adds margin to an extent
    extent: [x1,y1,x2,y2]
    margin: (x-margin, y-margin)
        Amount of margin to add
    """
    return [extent[0]-margin[0], extent[1]-margin[1], extent[2]+margin[0], extent[3]+margin[1]]
# -----------------------------------------------------------------
@functools.lru_cache()
def domain_extents(exp_mod):
    """Loads the extents of the sub-domains defined for an experiment.
    (RAMMS is run separately on each subdomain)
    Yields: (idom, jdom, (x0y0,x1,y1))"""

    # Load set of extents
    domains_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains.shp')
    df = shputil.read_df(domains_shp, read_shapes=True)
    for _,row in df.iterrows():
        xx,yy = row['shape'].exterior.coords.xy
#        yield row.idom,row.jdom,(xx[0],yy[0], xx[2],yy[2])    # Convert to an Extent-type list of (x0,y0,x1,y1)
        # TODO: This version is just until we rewrite the domains file
        yield row.ix,row.iy,(
            min(xx[0],xx[2]),
            min(yy[0],yy[2]),
            max(xx[0],xx[2]),
            max(yy[0],yy[2]))    # Convert to an Extent-type list of (x0,y0,x1,y1)


# -----------------------------------------------------------------
# ---------------------------------------------------------------------
# Make sure that extents are in (xmin,ymin, xmax,ymax) format
def check_extent_sign(extent):
    x0,y0,x1,y1 = extent
    assert x1>=x0
    assert y1>=y0

# ===================================================================

_mosaic_metadata = {
    'dem': (gdal.GDT_Float32, {
        'description': 'IFSAR Digital elevation model',
        'units': 'm'
    }),

    'landcover': (gdal.GDT_Int16, {
        'description': 'USGS Land cover types',
        'units': 'm'
    }),

    'deposition': (gdal.GDT_Float32, {
        'description': 'Maximum deposition from any avalanche',
        'units': 'm'
    }),
    'max_height': (gdal.GDT_Float32, {
        'description': 'Maximum depth of snow attained',
        'units': 'm',
    }),
    'max_velocity': (gdal.GDT_Float32, {
        'description': 'Maximum snow speed from any avalanche',
        'units': 'm s-1',
    }),
    'max_pressure': (gdal.GDT_Float32, {
        'description': 'Maximum pressure from any avalanche',
        'source_units': 'Pa',    # Convert Pa to kPa
        'units': 'kPa',
    }),
    'avalanche_count': (gdal.GDT_Int16, {
        'description': 'Number of avalanches hitting this gridcell',
    }),
    'domain_count': (gdal.GDT_Int16, {
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

    shapeM = (gridM.ny, gridM.nx)
    vals = dict(
        deposition=np.zeros(shapeM, dtype='f4'),
        max_height=np.zeros(shapeM, dtype='f4'),
        max_velocity=np.zeros(shapeM, dtype='f4'),
        max_pressure=np.zeros(shapeM, dtype='f4'),
        domain_count=np.zeros(shapeM, dtype='i2'),
        avalanche_count=np.zeros(shapeM, dtype='i2'))

    for aval_i,fname in enumerate(avals):
        if not os.path.isfile(fname):
            print(f'Missing avalanche file: {fname}')
            continue

        print(f'mosaic: {fname}')
        with netCDF4.Dataset(fname) as nc:
            nc.set_always_mask(False)

            # "gridA" = Avalanche's local grid (it will be one of the subdomains), WITH MARGIN
            # Geotransform of this avalanche's local grid
            # TODO: Store Geotransform as machine-precision doubles in the file
            gridA_gt = np.array([float(x) for x in nc.variables['grid_mapping'].GeoTransform.split(' ')])

            # C++ extension does the real work
            args = (
                nc.variables['i_diff'][:],
                nc.variables['j_diff'][:],
                gridA_gt[0], gridA_gt[3],
                nc.variables['max_vel'][:].astype('f4'),
                nc.variables['max_height'][:].astype('f4'),
                nc.variables['depo'][:].astype('f4'),
                rho,
                gridM.nx, gridM.x0, gridM.dx,
                gridM.ny, gridM.y0, gridM.dy,
                vals['deposition'],
                vals['max_height'],
                vals['max_velocity'],
                vals['max_pressure'],
                vals['domain_count'],
                vals['avalanche_count'])
            _mosaic.mosaic(*args)

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
            if 'source_units' in meta:
                val = cfutil.convert(val, meta['source_units'], meta['units'])
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

    # TODO: Create a RELEASE file, for avalanches with aspecs





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

