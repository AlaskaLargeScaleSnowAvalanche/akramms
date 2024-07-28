import os,pathlib,subprocess,sys,typing
import numpy as np
import pandas as pd
import zipfile,netCDF4
from osgeo import gdal,ogr
from uafgi.util import gdalutil,ogrutil
from uafgi.util import cfutil,shputil,ioutil,gisutil
from akramms import experiment,archive,file_info,avalquery,downscale_snow
import akramms.parse
import _mosaic
import geopandas
from akramms.plot import p_mosaic

# python -m cProfile -o prof -s cumtime `which akramms` mosaic juneau1-1981-1990.qy 


# ===================================================================

# ----------------------------------------------------------
def read_reldom(akdf0):
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
    for (combo,arcdir),akdf1 in akdf0.groupby(['combo', 'releasefile']):
        scombo = '-'.join(str(x) for x in combo)

        # Read all _rel / _dom data in the archive dir
        reldf = archive.read_reldom(arcdir/'RELEASE.zip', 'rel')#, shape='pra')
        reldf = reldf.rename(columns={'geometry': 'pra'})
        domdf = archive.read_reldom(arcdir/'DOMAIN.zip', 'dom')#, shape='dom')
        domdf = domdf.rename(columns={'geometry': 'dom'})

        # Filter down to just what we need
        df = akdf1[['id']]

        reldf = df.merge(reldf, how='left', left_on='id', right_on='Id')
        reldf = reldf.drop('id', axis=1)
        reldf['pra_size'] = reldf['pra_size'].astype('string')
        reldf['combo'] = scombo
        reldf['combo'] = reldf['combo'].astype('string')
        
        reldfs.append(reldf)

        domdf = df.merge(domdf, how='left', left_on='id', right_on='Id')
        domdf = domdf.drop('id', axis=1)
        domdf['combo'] = scombo
        domdf['combo'] = domdf['combo'].astype('string')
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

class _ExtentShp(typing.NamedTuple):
    scombo: str
    shp: str
    ds: object
    layer: object
    Id: object

def new_extent_shp(dir, gridM, combo):
    scombo = '-'.join(str(x) for x in combo)
    extent_shp = str(dir / f'extent-{scombo}.shp')
    print('Writing extent_shp ', extent_shp)
    if os.path.exists(extent_shp):
        os.remove(extent_shp)
    extent_ds = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(extent_shp)
    extent_layer = extent_ds.CreateLayer(extent_shp, ogrutil.to_srs(gridM.wkt), geom_type=ogr.wkbMultiPolygon )
    # https://gis.stackexchange.com/questions/392515/create-a-shapefile-from-geometry-with-ogr
    extent_Id = extent_layer.CreateField(ogr.FieldDefn('Id', ogr.OFTInteger))
    return _ExtentShp(scombo, extent_shp, extent_ds, extent_layer, extent_Id)



class Mosaic(typing.NamedTuple):
    """Mosaic Data Structure, ready to write out to disk."""
    rasters: dict    # {'deposition': (meta, np.array), ...}
    vectors: dict    # {'release': df, 'domain': df, 'extent': df}

#    def __init__(self, name, rasters, vectors):
#        self.name = name
#        self.rasters = rasters
#        self.vectors = vectors
#        self._tdir = 
#        self.tifdir = tifdir

def mosaic_avals_id(gridM, akdf0, tifdir,
    rho=300, vars=_mosaic_keys,
    dem_fn=None, landcover_fn=None, snow_fn=None, ijdom=None):

    """General mosaic function for a bunch of avalanches and a domain

    gridM:
        Sub-grid (of global gridG) defining the extent of our mosaic domain
        When doing stdmosaic, this will be the subdomain tile WITHOUT MARGINS
        (Note that gridA is WITH MARGINS)
    akdf0:
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
    Returns: Mosaic
        Data structure to write
    """

    mos = Mosaic(dict(), dict())

    print('=== BEGIN mosaic_aval_combo')
    print(akdf0)
    for vname in ('gridM', 'tifdir', 'rho', 'vars', 'dem_fn', 'landcover_fn', 'snow_fn'):
        val = locals()[vname]
        print(f'{vname}: {val}')


    #tifdirdir = pathlib.Path(tdir.location)
    vars_set = set(vars)

    # Prepare variables for output
    shapeM = (gridM.ny, gridM.nx)
    vals = dict(
        deposition=np.zeros(shapeM, dtype='f4'),
        max_height=np.zeros(shapeM, dtype='f4'),
        max_velocity=np.zeros(shapeM, dtype='f4'),
        max_pressure=np.zeros(shapeM, dtype='f4'),
        domain_count=np.zeros(shapeM, dtype='i2'),
        avalanche_count=np.zeros(shapeM, dtype='i2'))
    for vname,val in vals.items():
        if vname in vars:
            mos.rasters[vname] = val

    # Collect extent polygons
    dfss = {'release': list(), 'domain': list(), 'extent': list()}
    shapedfs = list()
    for (combo,arcdir),akdf1 in akdf0.groupby(['combo', 'releasefile']):
        akdf1 = akdf1.sort_values('id')

        # --------------- Read polygon files: PRAs, domains and extents
        # (All using geopandas, with .Id and .geometry columns)
        dfs = (
            ('release', archive.read_reldom(arcdir/'RELEASE.zip', 'rel')),
            ('domain', archive.read_reldom(arcdir/'DOMAIN.zip', 'dom')),
            ('extent', geopandas.read_file(str(arcdir/'extent.gpkg'))))
        ids = set(akdf1.id)
        for vname,val in dfs:
            dfss[vname].append(val[val.Id.isin(ids)])

        # -------------- Update the mosaic (in memory)
        count = 0
        for tup in akdf1.itertuples(index=False):
            # DEBUGGING
            count += 1
#            if count > 100:
#                break

            if not os.path.isfile(tup.avalfile):
                print(f'Missing avalanche file: {tup.avalfile}')
                continue

            print(f'mosaic: {tup.avalfile}')
            with netCDF4.Dataset(tup.avalfile) as nc:
                nc.set_always_mask(False)

                # --------------- gridA is the subdomain tile, WITH MARGIN
                # Geotransform of this avalanche's local grid
                # TODO: Store Geotransform as machine-precision doubles in the file
                gridA_gt = np.array([float(x) for x in nc.variables['grid_mapping'].GeoTransform.split(' ')])

                # ---------- Copy raster into the overall mosaic
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

    # ========== Write output GeoTIFF and Zip it up
    # --------------------- Write shape dataframes to shapefiles
    for vname, dfs in dfss.items():
        mos.vectors[vname] = pd.concat(dfs)

    # ------------------- Other TIFF variables (written  directly into tifdir)
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
        gdalutil.write_raster(tifdir / f'{vname}.tif', gridM, val, 0, type=gdal_type, metadata=meta)

    # These are last so they appear as lower layers in QGIS
    # Land Cover
    if landcover_fn is not None:
        landcover_fn(gridM.bounding_box(), tifdir / 'landcover.tif')

    # DEM
    if dem_fn is not None:
        dem_fn(gridM.bounding_box(), tifdir / 'dem0.tif')

        cmd = ['gdalwarp', '-tr', '30', '30', '-co', 'TFW=YES', '-co', 'PROFILE=BASE',
            str(tifdir / 'dem0.tif'), str(tifdir / 'dem.tif')]
        subprocess.run(cmd, check=True)
        try:
            os.remove(tifdir / 'dem0.tif')
            os.remove(tifdir / 'dem0.tfw')
        except OSError:
            pass

    # Snowfile
    if snow_fn is not None:
        snow_fn(gridM.bounding_box(), tifdir / 'snow.tif')

    return mos


# -----------------------------------------------------------------------------
def mosaic_avals_combo(akdf, sextent, tifdir,
    statuses=[file_info.JobStatus.FINISHED],
    snow=False, dem=False, landcover=False,
    dry_run=False, force=False):

    """General mosaic function for a bunch of avalanches and a domain

    akdf:
        Avalanches (in scenetype='arc') to mosiac
        Resolved to the combo level
        Must contain columns: releasefile (actually arcdir), avalfile, id

    sextent: One of...
        (x0,y0,x1,y1)
            or
        experiment-specific extent label
            or
        'tile': Use the extent of an (idom,jdom) subdomain tile
            or
        'avalanche': Use avalanches to determine overall extent

    """



    print('=== BEGIN mosaic_aval_combo')
    print(akdf)
    for vname in ('sextent', 'statuses', 'snow', 'dem', 'landcover', 'dry_run', 'force'):
        val = locals()[vname]
        print(f'{vname}: {val}')

    # Make sure they all use the same experiment
    # (Because extents are queried from the experiment definition file)
    row0 = akdf.iloc[0]
    assert all(x == row0.exp for x in akdf.exp)

    # Query down to the id level (expands to neigbhoring tiles as well)
    expmod = akramms.parse.load_expmod(row0.exp)
    geom,akdf = avalquery.query(akdf, sextent, statuses=statuses, scenetypes='arc', force=force)

    print(f'geom = {geom}')

    # Prepare snow virtual raster for query
    if snow:
        # Ensure all avalanches use the same snow input
        snowfile_argss = sorted(set(akdf['combo'].map(expmod.combo_to_snowfile_args)))
        assert all(x[:-2] == snowfile_argss[0][:-2] for x in snowfile_argss)

        # Create virtual raster to query
        snowfile_vrt = downscale_snow.snowfile_vrt(snowfile_argss)
        print('snowfile_vrt = ', snowfile_vrt)

#    if not ofname.parts[-1].endswith('.zip'):
#        raise ValueError('--output must specify a .zip file')

    # Do mosaic
    res = expmod.resolution
    gridG = expmod.gridD.global_grid(res, res)
    extent = geom.bounds    # (x0,y0, x1,y1)
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

    ret = mosaic_avals_id(gridM, akdf, tifdir, **kwargs)
    print('=== END mosaic_aval_combo')
    return ret

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
#        # This error check isn't actually correct, there are some degenerate cases...
#        if len(akdf1) != 2:
#            raise ValueError(f'ERROR: Need both For and NoFor pair to proceed further, we have only: {akdf1.combo.tolist()}')

        akdf1s.append(akdf1)
    return akdf1s
# ---------------------------------------------------------------------------------
class MosaicWriter:

    def __init__(self, expmod):
        """statuss: [status, ...]
            Which stauses of avalanches are bieng plotted
        """
        self.expmod = expmod

#    def name(self, combo):
#        """Determines a generic name for a combo"""
#        scombo = str(combo)
#        return f'{self.expmod.name}-{scombo}-{self.sstatus}'


def _ozip_write(ozip, fname):
    """Writes with truncated arcname"""
    ozip.write(fname, arcname=os.path.split(fname)[1])

class ZipMosaicWriter(MosaicWriter):

    def ofnames(self, name):
        """Returns a dict of files written for a combo"""
#        name = self.name(combo)
        return {
            'zip': self.expmod.dir / 'mosaic' / f'{name}.zip',
            'pdf': self.expmod.dir / 'plot' / f'{name}.pdf'}

    def needs_regen(self, name, combo_mtime):
        """
        combo_mtime:
            Last time the underlying data for this combo(s) was regenerated.
        """
        ofnames = self.ofnames(name)
        for ofname in ofnames.values():
            if (not os.path.isfile(ofname)) or (os.path.getmtime(ofname) < combo_mtime):
                return True
        return False

    def write(self, name, mos, tifdir, ijdom=None):
        """Writes to file(s)
        name:
            Name used to create output file(s)
        mos: Mosaic
            Data structure containing stuff to write
        tifdir:
            Temporary directory where intermediate outputs are stored
        """
        # ========== Write output GeoTIFF and Zip it up
        ofnames = self.ofnames(name)
        print(f"Writing {ofnames['zip']}")
        os.makedirs(ofnames['zip'].parents[0], exist_ok=True)
        with zipfile.ZipFile(ofnames['zip'], mode='w', compression=zipfile.ZIP_STORED) as ozip:

            # --------------------- Write shape dataframes to shapefiles
            for vname, df in mos.vectors.items():
                # Add idom/jdom to the shapefile before writing
                if ijdom is not None:
                    df['idom'] = ijdom[0]
                    df['jdom'] = ijdom[1]
                df.to_file(tifdir / f'{vname}.shp')

            # ------------------- Landcover, etc. files
            for name in sorted(os.listdir(tifdir)):
                print(f'Adding to zip: {name}')
                _ozip_write(ozip, tifdir / name)


        # ================ Plot to reference PDF
        p_mosaic.plot_pdf(ofnames['zip'], ofnames['pdf'])

# ---------------------------------------------------------------------------------


_tifdir_names = [
    'avalanche_count.tfw',
    'avalanche_count.tif',
    'dem.tfw',
    'dem.tif',
    'deposition.tfw',
    'deposition.tif',
#    'domain.cpg',
#    'domain.dbf',
#    'domain.prj',
#    'domain.shp',
#    'domain.shx',
#    'domain_count.tfw',
#    'domain_count.tif',
    'extent.cpg',
    'extent.dbf',
    'extent.prj',
    'extent.shp',
    'extent.shx',
    'landcover.tfw',
    'landcover.tif',
    'landcover.tif.aux.xml',
    'max_height.tfw',
    'max_height.tif',
    'max_pressure.tfw',
    'max_pressure.tif',
    'max_velocity.tfw',
    'max_velocity.tif',
    'release.cpg',
    'release.dbf',
    'release.prj',
    'release.shp',
    'release.shx',
    'snow.tfw',
    'snow.tif']

        
class PublishMosaicWriter(MosaicWriter):

    def ofname(self, scombo, tifdir_name):
        """Determines the final filename for a file in the tifdir
        name:
            Name of the overall output (eg combo)
        tifdir_name:
            Filename inside of tifdir"""

        # Make sure things are named All; and not NoFor or For.
        # Because mosaics include both For and NoFor elements,
        # depending on PRA size.
        scombo = scombo.replace('NoFor', 'All').replace('For', 'All')
        lcombo = scombo.split('-')
        base = tifdir_name.split('.',1)[0]


        # Eg:
        # ...ak_publish/
        #    ak-ccsm-1981-2010-lapse-For-30/   ('-'.join(lcombo[:-3]))
        #    release/ak-ccsm-1981-2010-lapse-For-30-91-42-F-release.dbf

        return \
            self.expmod.dir.parents[0] / (self.expmod.dir.parts[-1] + '_publish') / \
            ('-'.join(lcombo[:-3])) / base / f'{scombo}-{tifdir_name}'


    def needs_regen(self, name, combo_mtime):
        """
        combo_mtime:
            Last time the underlying data for this combo(s) was regenerated.
        """
        for ofname in (self.ofname(name, tifdir_name) for tifdir_name in _tifdir_names):
            print('Checking ', ofname)
            if (not os.path.isfile(ofname)) or (os.path.getmtime(ofname) < combo_mtime):
                return True
        return False

    def write(self, name, mos, tifdir, ijdom=None):
        """Writes to file(s)
        name:
            Name used to create output file(s)
        mos: Mosaic
            Data structure containing stuff to write
        tifdir:
            Temporary directory where intermediate outputs are stored
        """
        # ========== Write output GeoTIFF and Zip it up

        # --------------------- Write shape dataframes to shapefiles
        for vname, df in mos.vectors.items():

            # Don't publish domain or domain_count files
            if vname in {'domain'}:
                continue

            # Add idom/jdom to the shapefile before writing
            if ijdom is not None:
                df['idom'] = ijdom[0]
                df['jdom'] = ijdom[1]
            df.to_file(tifdir / f'{vname}.shp')

        for tifdir_name in sorted(os.listdir(tifdir)):
            # Don't publish domain or domain_count files
            if tifdir_name.startswith('domain_count'):
                continue

            ofname = self.ofname(name, tifdir_name)
            print(f'Writing file {tifdir_name}: {ofname}')
            os.makedirs(ofname.parents[0], exist_ok=True)
            os.rename(tifdir / tifdir_name, ofname)


# ---------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------
