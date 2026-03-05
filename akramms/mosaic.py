import os,pathlib,subprocess,sys,typing,contextlib
import numpy as np
import pandas as pd
import zipfile,netCDF4
from osgeo import gdal,ogr
from uafgi.util import gdalutil,ogrutil,make
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
    dfss = {'release': list(), 'domain': list(), 'extent_christen': list(), 'extent_tetra30': list(), 'extent_full': list()}
    shapedfs = list()
    for (combo,arcdir),akdf1 in akdf0.groupby(['combo', 'releasefile']):

        # Figure out where we will write extent files
        arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')
        swcombo = arcdir.parts[-2]    # Eg: 'ak-ccsm-1981-2010-lapse-For-30'
        sijdom = arcdir.parts[-1][4:]    # Eg: 111-044
        expdir_ext = expmod.dir.parents[0] / 'ext'
        extent_dir = expdir_ext / swcombo / 'extent'

        # Initial list of IDs based on query
        akdf1 = akdf1.sort_values('id')
        ids = set(akdf1.id)

        # Read extents, and further filter low-elevation avalanches
        try:
            df = extent.read_annotated_extent(expmod, combo, 'christen')  # >1 polygon per ID
        except FileNotFoundError as err:
            # Assume that if the extent file is not found, it does not exist.
            # `akramms extent` should have been run first!
            print('mosaic_avals_id(): ', err)
            continue

        df = _subset_poly_df(ids, combo.idom, combo.jdom, df)
        df,_ = expmod.mosaic_filter(df)    # Filter out bogus low-elevation avalanches
        dfss['extent_christen'].append(df)

        # Create new master list of IDs based on filtered
        # extent_christen (created just above)
        ids = set(dfss['extent_christen'][-1].Id)
        akdf1 = akdf1[akdf1.id.isin(ids)]

        # Filter the tetra30 avalanches accordig to the same list
        df = extent.read_annotated_extent(expmod, combo, 'tetra30')  # >1 polygon per ID
        df = _subset_poly_df(ids, combo.idom, combo.jdom, df)
        dfss['extent_tetra30'].append(df)

        # Filter the full avalanches accordig to the same list
        df = extent.read_annotated_extent(expmod, combo, 'full')  # >1 polygon per ID
        df = _subset_poly_df(ids, combo.idom, combo.jdom, df)
        dfss['extent_full'].append(df)

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
            ixs = rasterize.rasterize_polygon_compressed(pra, gridM)
            pra_count_1d[ixs] += 1

            # -------------- pra_centroid_count: Just one point per PRA
            centroid = pra.centroid
            x,y = centroid.x, centroid.y
            i,j = gridM.to_ij(x,y)
            if (i >= 0) and (j >= 0) and (i < gridM.nx) and (j < gridM.ny):
                pra_centroid_count[j,i] += 1

        # -------------- Update the mosaic (in memory)
        with contextlib.ExitStack() as stack:

            count = 0
            print(f'akdf1 = {len(akdf1)}')
            print(akdf1)
            print('Adding to raster mosaic:')
            for tup in akdf1.itertuples(index=False):    # Iterate through each avalanche (tup.avalfile)
                count += 1
                if count%100 == 0:
                    print('.', end='')
                    sys.stdout.flush()

                if not os.path.isfile(tup.avalfile):
                    print(f'Missing avalanche file: {tup.avalfile}')
                    continue
                if os.path.getsize(tup.avalfile) == 0:    # Avoid dummy placeholder avalanches
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

    # ========== Write output GeoTIFF and Zip it up
    # --------------------- Write shape dataframes to shapefiles
    for vname, dfs in dfss.items():
        if len(dfs) > 0:
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
    # NOTE: This could add some tiles that are outside of a domain like aksc5.central
    #       Further down, we will pass if things are not found.
    expmod = akramms.parse.load_expmod(row0.exp)
    geom,akdf = avalquery.query(akdf, sextent, statuses=statuses, scenetypes='arc', force=force)

    # No avalanches, so nothing to write
    if len(akdf) == 0:
        print('Mosaic: No avalanches, so nothing to write')
        return None    # A dummy file will be written based on this.

    print(f'geom = {geom}')

    # Prepare snow virtual raster for query
    if snow:
        snowfile_vrt = downscale_snow.snowfile_vrt(expmod, akdf['combo'])
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

    def __init__(self, exp, name):
        """
        name:
            Name of output thing to write (typically scombo)
        """
        self.exp = exp
        self.name = name

def _ozip_write(ozip, fname):
    """Writes with truncated arcname"""
    ozip.write(fname, arcname=os.path.split(fname)[1])

class ZipMosaicWriter(MosaicWriter):

    def ofnames(self):
        """Returns a dict of files written for a combo"""
#        name = self.name(combo)
        expmod = akramms.parse.load_expmod(self.exp)
        return {
            'zip': expmod.dir / 'mosaic' / f'{self.nae}.zip',
            'pdf': expmod.dir / 'plot' / f'{self.nae}.pdf'}

    def outputs(self):
        """List of all output names"""
        return self.ofnames().values()

    def needs_regen(self, combo_mtime):
        """
        combo_mtime:
            Last time the underlying data for this combo(s) was regenerated.
        """
        ofnames = self.ofnames(self.nae)
        for ofname in ofnames.values():
            if (not os.path.isfile(ofname)) or (os.path.getmtime(ofname) < combo_mtime):
                return True
        return False

    def write(self, mos, tifdir, ijdom=None):
        """Writes to file(s)
        name:
            Name used to create output file(s)
        mos: Mosaic
            Data structure containing stuff to write
        tifdir:
            Temporary directory where intermediate outputs are stored
        """
        # ========== Write output GeoTIFF and Zip it up
        ofnames = self.ofnames(self.nae)
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
    'extent_full.cpg',
    'extent_full.dbf',
    'extent_full.prj',
    'extent_full.shp',
    'extent_full.shx',
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

    def ofname(self, tifdir_name):
        """Determines the final filename for a file in the tifdir
        name:
            Name of the overall output (eg combo)
        tifdir_name:
            Filename inside of tifdir"""

        scombo = self.name

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

        expmod = akramms.parse.load_expmod(self.exp)
        return \
            expmod.dir.parents[0] / 'publish' / \
            ('-'.join(lcombo[:-3])) / base / f'{scombo}-{tifdir_name}'

    def outputs(self):
        return [self.ofname(tifdir_name) for tifdir_name in _tifdir_names]

    def needs_regen(self, combo_mtime):
        """
        combo_mtime:
            Last time the underlying data for this combo(s) was regenerated.
        """
        for ofname in self.outputs():
            print('Checking ', ofname)
            if (not os.path.isfile(ofname)) or (os.path.getmtime(ofname) < combo_mtime):
                return True
        return False

    def write(self, mos, tifdir, ijdom=None):
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

            ofname = self.ofname(tifdir_name)
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
class stdmosaic_action:
    def __init__(self, exp, akdf1, statuses, dry_run, force):
        """
        akdf1: (combo level)
            Dataframe with two rows, a For / NoFor matching pair.
        """
        self.akdf1 = akdf1
        self.exp = exp
        expmod = akramms.parse.load_expmod(exp)
        self.statuses = statuses
        self.dry_run = dry_run
        self.force = force

        # Determine output Combo name (replace For/NoFor with AllFor)
        forest_ix = expmod.combo_keys.index('forest')
        combo = akdf1.combo.tolist()[0]
        lcombo = list(combo[:forest_ix]) + ['All'] + list(combo[forest_ix+1:])
        self.ocombo = expmod.Combo(*lcombo)

        self.scombo = str(combo)
        sstatus = ''.join(file_info.JobStatus._member_names_[x][0] for x in sorted(statuses))
        name = f'{expmod.name}-{self.scombo}-{sstatus}'
        self.mwriter = PublishMosaicWriter(exp, name)


    def __call__(self, tdir):
        expmod = akramms.parse.load_expmod(self.exp)
        tifdir = pathlib.Path(tdir.location)
        mos = mosaic_avals_combo(
            self.akdf1, 'tile', tifdir, statuses=self.statuses,
            snow=True, dem=True, landcover=True,
            dry_run=self.dry_run, force=self.force)
        if mos is None:    # There were no avalanches found
            ofname = expmod.root_dir / 'publish' / f'{self.exp}-{self.scombo}' / 'blank' / f'{self.exp}-{self.scombo}-F-blank.txt'
            os.makedirs(ofname.parents[0], exist_ok=True)
            with open(ofname, 'w') as out:
                pass
            print('Nothing to mosaic, wrote ', ofname)

        else:   # There were some avalanches to plot...
            self.mwriter.write(mos, tifdir, ijdom=(self.ocombo.idom, self.ocombo.jdom))


def stdmosaic_rule(*args, **kwargs):
    action_fn = stdmosaic_action(*args, **kwargs)
    rule = make.Rule(action_fn, [], action_fn.mwriter.outputs())
    return rule
# ---------------------------------------------------------------------------------
