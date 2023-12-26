import os,pathlib
import numpy as np
import pandas as pd
from osgeo import gdal
import zipfile,netCDF4
from uafgi.util import gdalutil,cfutil,shputil
from akramms import experiment,archive
import _mosaic

# python -m cProfile -o prof -s cumtime `which akramms` mosaic juneau1-1981-1990.qy 


# ===================================================================

# ----------------------------------------------------------
def read_reldom(akdf0, tdir):
    """
    akdf0:
        Avalanches (in scenetype='arc') to mosiac
        Resolved to the id level
        Must contain columns: releasefile (actually arcdir), avalfile, id
    returns: reldf, domdf
        Dataframes with columns as read from _rel and _dom shapefiles.
        Rows same as akdf0
    """
    reldfs = list()
    domdfs = list()
    for arcdir,akdf1 in akdf0.groupby('releasefile'):
        # Read all _rel / _dom data in the archive dir
        reldf = archive.read_reldom(arcdir/'RELEASE.zip', 'rel', tdir, shape='pra')
        domdf = archive.read_reldom(arcdir/'DOMAIN.zip', 'dom', tdir, shape='dom')

        # Filter down to just what we need
        df = akdf1[['id']]

        reldf = df.merge(reldf, how='left', left_on='id', right_on='Id')
        reldf = reldf.drop('id', axis=1)
        reldfs.append(reldf)

        domdf = df.merge(domdf, how='left', left_on='id', right_on='Id')
        domdf = domdf.drop('id', axis=1)
        domdfs.append(domdf)

    reldf = pd.concat(reldfs)
    domdf = pd.concat(domdfs)

    return reldf, domdf
# ----------------------------------------------------------
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

def mosaic_avals(gridM, akdf, ofname_zip, tdir,
    rho=300, vars=_mosaic_keys,
    dem_fn=None, landcover_fn=None):

    """General mosaic function for a bunch of avalanches and a domain

    gridM:
        Sub-grid (of global gridG) defining the extent of our mosaic domain
    avals:
        Generator of NetDCDF avalanche filenames to mosaic
    akdf:
        Avalanches (in scenetype='arc') to mosiac
        Resolved to the id level
        Must contain columns: releasefile (actually arcdir), avalfile, id
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
    dir = pathlib.Path(tdir.location)
    vars_set = set(vars)

    shapeM = (gridM.ny, gridM.nx)
    vals = dict(
        deposition=np.zeros(shapeM, dtype='f4'),
        max_height=np.zeros(shapeM, dtype='f4'),
        max_velocity=np.zeros(shapeM, dtype='f4'),
        max_pressure=np.zeros(shapeM, dtype='f4'),
        domain_count=np.zeros(shapeM, dtype='i2'),
        avalanche_count=np.zeros(shapeM, dtype='i2'))

#    for aval_i,fname in enumerate(avals):
    for tup in akdf.itertuples(index=False):
        arcdir = tup.releasefile
        if not os.path.isfile(tup.avalfile):
            print(f'Missing avalanche file: {tup.avalfile}')
            continue

        print(f'mosaic: {tup.avalfile}')
        with netCDF4.Dataset(tup.avalfile) as nc:
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



        # Shapefiles
        reldf, domdf = read_reldom(akdf, tdir)
        #reldf = read_reldom(arcdir, 'rel')
        shputil.write_df(reldf, 'pra', 'Polygon', dir / 'rel.shp', wkt=gridM.wkt)
        ozip_write(ozip, dir / 'rel.shp')

        #reldf = archive.read_reldom(arcdir, 'dom')
        shputil.write_df(domdf, 'dom', 'Polygon', dir / 'dom.shp', wkt=gridM.wkt)
        ozip_write(ozip, dir / 'dom.shp')


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
        if landcover_fn is not None:
            ofn = os.path.join(tdir.location, 'landcover.tif')
            landcover_fn(box_poly, ofn)
            ozip_write(ozip, ofn)
            ozip_write(ozip, os.path.join(tdir.location, 'landcover.tif.aux.xml'))
            ozip_write(ozip, os.path.join(tdir.location, 'landcover.tfw'))

        # DEM
        if dem_fn is not None:
            dem_fn(box_poly, dir / 'dem0.tif')
            gdal.Warp(str(dir / 'dem.tif'), str(dir / 'dem0.tif'), xRes=30, yRes=30)
            ozip_write(ozip, dir / 'dem.tif')
            ozip_write(ozip, os.path.join(dir, 'dem.tfw'))

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

