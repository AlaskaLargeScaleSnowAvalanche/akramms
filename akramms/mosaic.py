import os,pathlib,subprocess,sys,typing,contextlib
import numpy as np
import pandas as pd
import zipfile,netCDF4
from osgeo import gdal,ogr
from uafgi.util import gdalutil,ogrutil
from uafgi.util import cfutil,ioutil,gisutil,rasterize
from akramms import experiment,archive,file_info,avalquery,downscale_snow,extent
import akramms.parse
import _mosaic
import geopandas
from akramms.plot import p_mosaic

# python -m cProfile -o prof -s cumtime `which akramms` mosaic juneau1-1981-1990.qy 

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
    'pra_count': (gdal.GDT_Int16, {
        'description': 'Number of PRAs hitting this gridcell',
    }),
    'pra_centroid_count': (gdal.GDT_Int16, {
        'description': 'Number of PRAs centered on this gridcell',
    }),
}
_avoid = ('dem', 'landcover')    # Only include these if user provides fetch fn
_mosaic_keys = list(x for x in _mosaic_metadata.keys() if x not in _avoid)


class Mosaic(typing.NamedTuple):
    """Mosaic Data Structure, ready to write out to disk."""
    rasters: dict    # {'deposition': (meta, np.array), ...}
    vectors: dict    # {'release': df, 'domain': df, 'extent': df}

# ---------------------------------------------------------------------------
def _subset_poly_df(ids, idom, jdom, df):
    # Select out only polygons pertaining to this combo (whether For or NoFor)
    subdf = df[df.Id.isin(ids)]
    # Add idom / jdom to the dataframes read via read_reldom
    subdf['idom'] = idom
    subdf['jdom'] = jdom
    return subdf


def mosaic_avals_id(expmod, gridM, akdf0, tifdir,
    vars=_mosaic_keys,
    dem_fn=None, landcover_fn=None, rho=300, snow_fn=None, ijdom=None):

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
        Data structure to write    """

    mos = Mosaic(dict(), dict())

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
        avalanche_count=np.zeros(shapeM, dtype='i2'),
        pra_centroid_count=np.zeros(shapeM, dtype='i2'),
        pra_count=np.zeros(shapeM, dtype='i2'))
    for vname,val in vals.items():
        if vname in vars:
            mos.rasters[vname] = val

    # Collect extent polygons
    dfss = {'release': list(), 'domain': list(), 'extent_christen': list(), 'extent_tetra30': list()}
    shapedfs = list()
    for (combo,arcdir),akdf1 in akdf0.groupby(['combo', 'releasefile']):

        # Figure out where we will write extent files
        arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')
        swcombo = arcdir.parts[-2]    # Eg: 'ak-ccsm-1981-2010-lapse-For-30'
        sijdom = arcdir.parts[-1][4:]    # Eg: 111-044
        expdir_ext = expmod.dir.parents[0] / 'ext'
        extent_dir = expdir_ext / swcombo / 'extent'

        akdf1 = akdf1.sort_values('id')
        ids = set(akdf1.id)

        # --------------- Read polygon files: PRAs, domains
        # (All using geopandas, with .Id and .geometry columns)
        dfss['release'].append(_subset_poly_df(ids, combo.idom, combo.jdom,
                archive.read_reldom(arcdir/'RELEASE.zip', 'rel')))
        dfss['domain'].append(_subset_poly_df(ids, combo.idom, combo.jdom,
                archive.read_reldom(arcdir/'DOMAIN.zip', 'dom')))

        # -------------- Rasterize ("burn") the release polygons
        pra_count_1d = vals['pra_count'].reshape(-1)
        pra_centroid_count = vals['pra_centroid_count']
        reldf = dfss['release'][-1]    # Most recent relase polygons read, and cut down by IDs
        for pra in reldf.geometry:

            # -------------- pra_count: burn area of PRA into the raster
            # TODO: It might be faster to rasterize directly onto the grids.
            # But that's more code to write.
#            print('ssssssshape ', gridM.nx, gridM.ny, vals['pra_count'].shape, pra_count_1d.shape)
            ixs = rasterize.rasterize_polygon_compressed(pra, gridM)
#            ixs = ixs[(ixs >= 0) & (ixs < len(pra_count_1d))]    # Elimate out-of-range indices from polygon that extended beyond our domain
            pra_count_1d[ixs] += 1

            # -------------- pra_centroid_count: Just one point per PRA
            centroid = pra.centroid
            x,y = centroid.x, centroid.y
            i,j = gridM.to_ij(x,y)
            if (i >= 0) and (j >= 0) and (i < gridM.nx) and (j < gridM.ny):
                pra_centroid_count[j,i] += 1

        # -------------- Update the mosaic (in memory)
        extent_types = ('christen', 'full', 'tetra30')
        with contextlib.ExitStack() as stack:

            # Not to write, just use filename.  Therefore, landcover=None is OK.
            extent_writers = {
                extent_type: extent.WriteGpkg(expmod, combo, extent_type, None)
                for extent_type in extent_types}

            count = 0
            print(f'akdf1 = {len(akdf1)}')
            print(akdf1)
            for tup in akdf1.itertuples(index=False):    # Iterate through each avalanche (tup.avalfile)
                count += 1
                if count%100 == 0:
                    print('.', end='')
                    sys.stdout.flush()

                if not os.path.isfile(tup.avalfile):
                    print(f'Missing avalanche file: {tup.avalfile}')
                    continue
                aval = archive.read_nc(tup.avalfile)

                # ---------- Copy raster into the overall mosaic
                # C++ extension does the real work
                args = (
                    aval.iiA, aval.jjA,
                    aval.gridA_gt[0], aval.gridA_gt[3],
                    aval.max_vel, aval.max_height, aval.depo,
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

#                extent_writers['christen'].polygonize(combo, aval, tup.id)
#                extent_writers['full'].polygonize(combo, aval, tup.id)
#                max_pressure = rho * aval.max_vel * aval.max_vel
#                extent_writers['tetra30'].polygonize(combo, aval, tup.id,
#                    mask_kwargs=dict(max_pressure=max_pressure))


        dfss['extent_christen'].append(_subset_poly_df(ids, combo.idom, combo.jdom,
            geopandas.read_file(str(extent_writers['christen'].extent_gpkg))))    # >1 polygon per ID
        dfss['extent_tetra30'].append(_subset_poly_df(ids, combo.idom, combo.jdom,
            geopandas.read_file(str(extent_writers['tetra30'].extent_gpkg))))    # >1 polygon per ID


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

    # No avalanches, so nothing to write
    if len(akdf) == 0:
        print('Mosaic: No avalanches, so nothing to write')
        return None

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

    print('=== BEGIN mosaic_avals_id')
    ret = mosaic_avals_id(expmod, gridM, akdf, tifdir, **kwargs)
    print('=== END mosaic_aval_combo')
    return ret
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
#                if ijdom is not None:
#                    df['idom'] = ijdom[0]
#                    df['jdom'] = ijdom[1]
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
    'pra_count.tfw',
    'pra_count.tif',
    'pra_centroid_count.tfw',
    'pra_centroid_count.tif',
    'extent_christen.cpg',
    'extent_christen.dbf',
    'extent_christen.prj',
    'extent_christen.shp',
    'extent_christen.shx',
    'extent_tetra30.cpg',
    'extent_tetra30.dbf',
    'extent_tetra30.prj',
    'extent_tetra30.shp',
    'extent_tetra30.shx',
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
        # ...publish/
        #    ak-ccsm-1981-2010-lapse-For-30/   ('-'.join(lcombo[:-3]))
        #    release/ak-ccsm-1981-2010-lapse-For-30-91-42-F-release.dbf

        return \
            self.expmod.dir.parents[0] / 'publish' / \
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
#            if ijdom is not None:
#                df['idom'] = ijdom[0]
#                df['jdom'] = ijdom[1]
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
def fnames(expmod, combo, section_exts = [('release', '.shp')]):
    scombo = str(combo).replace('NoFor', 'All').replace('For', 'All')
    pieces = scombo.rsplit('-', 2)
    swcombo = pieces[0]
    sijdom = f'{pieces[1]}-{pieces[2]}'

    rets = list()
#    for section in sections:
#        for ext in exts:
    for section,ext in section_exts:
            yield expmod.root_dir / 'publish' / f'{expmod.name}-{swcombo}' / section / f'{expmod.name}-{scombo}-F-{section}{ext}'

# ---------------------------------------------------------------------------------
# ---------------------------------------------------------------------------------
