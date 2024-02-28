import os,pathlib,subprocess,sys
import numpy as np
import pandas as pd
import zipfile,netCDF4
from osgeo import gdal,ogr
from uafgi.util import gdalutil,ogrutil
from uafgi.util import cfutil,shputil,ioutil,gisutil
from akramms import experiment,archive,file_info,avalquery,downscale_snow
import akramms.parse
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
    eturns: reldf, domdf
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
        reldf['pra_size'] = reldf['pra_size'].astype('string')
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

def mosaic_avals_id(gridM, akdf, ofname_zip, tdir,
    rho=300, vars=_mosaic_keys,
    dem_fn=None, landcover_fn=None, snow_fn=None):

    """General mosaic function for a bunch of avalanches and a domain

    gridM:
        Sub-grid (of global gridG) defining the extent of our mosaic domain
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


    # Use OGR to create shapefile for avalanche outlines
    extent_shp = str(dir / 'extent.shp')
    if os.path.exists(extent_shp):
        os.remove(extent_shp)
    extent_ds = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(extent_shp)
    extent_layer = extent_ds.CreateLayer(extent_shp, ogrutil.to_srs(gridM.wkt), geom_type=ogr.wkbMultiPolygon )

#    for aval_i,fname in enumerate(avals):
    print(akdf.columns)
    akdf = akdf.sort_values('id')
    for tup in akdf.itertuples(index=False):
        arcdir = tup.releasefile
        if not os.path.isfile(tup.avalfile):
            print(f'Missing avalanche file: {tup.avalfile}')
            continue

        print(f'mosaic: {tup.avalfile}')
        with netCDF4.Dataset(tup.avalfile) as nc:
            nc.set_always_mask(False)

            # --------------- gridA is overall scene grid, WITH MARGIN
            # Geotransform of this avalanche's local grid
            # TODO: Store Geotransform as machine-precision doubles in the file
            gridA_gt = np.array([float(x) for x in nc.variables['grid_mapping'].GeoTransform.split(' ')])
            gridA_wkt = nc.variables['grid_mapping'].crs_wkt

            # --------------- Determine gridL, an x/y oriented grid (subgrid of the tile) containing the avalanche.
            i_diff = nc.variables['i_diff'][:]
            j_diff = nc.variables['j_diff'][:]
            iA = np.cumsum(i_diff)
            jA = np.cumsum(j_diff)

            # ------------ Polygonize the extent
            # Create a sub-grid gridL around just the avalanche (fast polygonize)
            iL_min = np.min(iA) - 2
            iL_max = np.max(iA) + 3
            jL_min = np.min(jA) - 2
            jL_max = np.max(jA) + 3
            iL = iA - iL_min
            jL = jA - jL_min
            gridL_gt = np.array(gridA_gt, dtype='i8')
            gridL_gt[0] += gridL_gt[1] * iL_min
            gridL_gt[3] += gridL_gt[4] * jL_min
            gridL = gisutil.RasterInfo(
                nc.variables['grid_mapping'].crs_wkt,
                iL_max - iL_min,
                jL_max - jL_min,
                gridL_gt)

            # Burn the gridcells that are part of our grid
            # (already pared down)
            nzmaskL = np.zeros((gridL.ny, gridL.nx))
            nzmaskL[jL,iL] = 1

            max_vel = nc.variables['max_vel'][:].astype('f4')
            max_height = nc.variables['max_height'][:].astype('f4')
            depo = nc.variables['depo'][:].astype('f4')
#
#            nzmask = np.logical_or(np.logical_or(
#                max_vel>0, max_height>0), depo>0).astype('i8')

            nzmask_ds = gdalutil.raster_ds((gridL, nzmaskL, 0))
            nzmask_band = nzmask_ds.GetRasterBand(1)
            gdal.Polygonize(nzmask_band, nzmask_band, extent_layer, -1)

            # ---------- Copy raster into the overall mosaic
            # C++ extension does the real work
            args = (
                i_diff, j_diff,
#                nc.variables['i_diff'][:],
#                nc.variables['j_diff'][:],
                gridA_gt[0], gridA_gt[3],
                max_vel, max_height, depo,
#                nc.variables['max_vel'][:].astype('f4'),
#                nc.variables['max_height'][:].astype('f4'),
#                nc.variables['depo'][:].astype('f4'),
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

        # Close extent.shp and store in the mosaic zip file
        extent_layer = None
        extent_ds = None
        for ext in ('shp','dbf','shx','prj'):
            ozip_write(ozip, dir / f'extent.{ext}')


    # Write output GeoTIFF and Zip it up
    os.makedirs(ofname_zip.parents[0], exist_ok=True)
    with zipfile.ZipFile(ofname_zip, mode='w', compression=zipfile.ZIP_STORED) as ozip:

        box_poly = gridM.bounding_box

        # Shapefiles
        reldf, domdf = read_reldom(akdf, tdir)
        for cname in reldf.columns:
            print(f"{cname}: {reldf[cname].dtype}")
        shputil.write_df(reldf, 'pra', 'Polygon', dir / 'rel.shp', wkt=gridM.wkt)
        for ext in ('shp','dbf','shx','prj'):
            ozip_write(ozip, dir / f'rel.{ext}')

        #reldf = archive.read_reldom(arcdir, 'dom')
        shputil.write_df(domdf, 'dom', 'Polygon', dir / 'dom.shp', wkt=gridM.wkt)
        for ext in ('shp','dbf','shx','prj'):
            ozip_write(ozip, dir / f'dom.{ext}')


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

            # gdal.Warp() does not create TFW files, but gdalwarp command does.
#            options = ['COMPRESS=LZW', 'TFW=YES']
#            gdal.Warp(str(dir / 'dem.tif'), str(dir / 'dem0.tif'), xRes=30, yRes=30, options=options)
#gdal_translate -co TFW=YES -co PROFILE=BASELINE dem.tif demx.tif
#gdalwarp -tr 30 30 -co TFW=UES -co PROFILE=BASE dem.tif x.tif

            cmd = ['gdalwarp', '-tr', '30', '30', '-co', 'TFW=YES', '-co', 'PROFILE=BASE',
                str(dir / 'dem0.tif'), str(dir / 'dem.tif')]
            subprocess.run(cmd, check=True)

            ozip_write(ozip, dir / 'dem.tif')
            ozip_write(ozip, os.path.join(dir, 'dem.tfw'))

        # Snowfile
        if snow_fn is not None:
            snow_fn(box_poly, dir / 'snow.tif')

            # No need to reduce resolution for such a smooth file, only negligable space savings
            #options = ['COMPRESS=LZW', 'TFW=YES']
            #gdal.Warp(str(dir / 'snow.tif'), str(dir / 'snow0.tif'), xRes=30, yRes=30, options=options)
            ozip_write(ozip, dir / 'snow.tif')
            ozip_write(ozip, os.path.join(dir, 'snow.tfw'))


def mosaic_avals_combo(akdf, sextent, ofname,
    statuses=[file_info.JobStatus.FINISHED],
    margin=None, snow=False, dem=False, landcover=False,
    dry_run=False):

    """General mosaic function for a bunch of avalanches and a domain

    akdf:
        Avalanches (in scenetype='arc') to mosiac
        Resolved to the id level
        Must contain columns: releasefile (actually arcdir), avalfile, id

    sextent: One of...
        (x0,y0,x1,y1)
            or
        experiment-specific extent label
            or
        'tile': Use the extent of an (idom,jdom) subdomain tile
            or
        'avalanche': Use avalanches to determine overall extent

    ofname:
        Name of output filename
    """

    # Make sure they all use the same experiment
    # (Because extents are queried from the experiment definition file)
    row0 = akdf.iloc[0]
    assert all(x == row0.exp for x in akdf.exp)

    # Query down to the id level
    expmod = akramms.parse.load_expmod(row0.exp)
    extent,akdf = avalquery.query(akdf, sextent, statuses=statuses, scenetypes='arc', margin=margin)

    # Prepare snow virtual raster for query
    if snow:
        # Ensure all avalanches use the same snow input
        snowfile_argss = sorted(set(akdf['combo'].map(expmod.combo_to_snowfile_args)))
        assert all(x[:-2] == snowfile_argss[0][:-2] for x in snowfile_argss)

        # Create virtual raster to query
        print('xxxxxxxxxxxx ', snowfile_argss)
        snowfile_vrt = downscale_snow.snowfile_vrt(snowfile_argss)

    if not ofname.parts[-1].endswith('.zip'):
        raise ValueError('--output must specify a .zip file')

    # Do mosaic
    res = expmod.resolution
    gridG = expmod.gridD.global_grid(res, res)
    gridM = expmod.gridD.subgrid(extent[0], extent[1], extent[2], extent[3], res, res)

    print(akdf[['exp', 'combo','id']])
    print(f'Extent: {extent}')

    if dry_run:
        print('Dry Run, not going further')
        return


    kwargs = dict()
    if dem:
        kwargs['dem_fn'] = expmod.extract_dem
    if landcover:
        kwargs['landcover_fn'] = expmod.extract_landcover
    if snow:
        kwargs['snow_fn'] = lambda box_poly,ofname: downscale_snow.extract_snow(snowfile_vrt, box_poly, ofname)

#    with ioutil.TmpDir(tdir='tmp', remove=False) as tdir:
#    with ioutil.TmpDir(ofname.parents[0]) as tdir:
    with ioutil.TmpDir() as tdir:
        mosaic_avals_id(gridM, akdf, ofname, tdir, **kwargs)

# ---------------------------------------------------------------------------------
def consolidate_by_forest(expmod, akdf0):
    """Combines For / NoFor pairs for stdmosaic operations.
    Raises an error if any unmatched rows are found in the input.

    akdf0:
        Resolved by combo.  (Single exp only)
    Returns: [akdf1, akdf1, ...]
        Each akdf1 contains two rows of akdf0 with matching For/NoFor pairs.
    """

    # This should ALWAYS work.  'forest' is a REQUIRED key in Combos
    # If it fails it will throw a ValueError.
    forest_ix = expmod.combo_keys.index('forest')

    akdf0['combo_noforest'] = akdf0.combo.map( lambda combo: tuple((combo[:forest_ix],)+combo[forest_ix+1:]) )
#    akdf0['forest'] = akdf0.combo.map(lambda combo: combo[forest_ix])

    akdf1s = list()
    for combo_noforest,akdf1 in akdf0.groupby('combo_noforest'):
        if len(akdf1) != 2:
            raise ValueError(f'ERROR: Need both For and NoFor pair to proceed further, we have only: {akdf1.combo.tolist()}')

        akdf1s.append(akdf1)
    return akdf1s
