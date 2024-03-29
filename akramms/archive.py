import os,re,itertools,struct,pickle,zipfile,io,shutil,typing
from osgeo import gdal,ogr
import contextlib,sys,datetime,subprocess
import concurrent.futures
import numpy as np
import pandas as pd
import netCDF4
import pyproj
from uafgi.util import gdalutil,shputil,ncutil,ioutil,ogrutil,gdalutil
from akramms import config,parse,file_info,resolve,overrun
import xyedge

# Convert Avalanche outputs to NetCDF

__all__ = ('archive',)

# ------------------------------------------------------------------
# ------------------------------------------------------------------
# NOTE: Similar to rammsutil.read_polygon_from_zip()
_all_spaceRE = re.compile(r'$\s*^')
def _read_polygon(izip, poly_file):
    """Reads RAMMS text format polygon files and returns them as a shapely.geometry.Polygon"""

#    with open(poly_file) as fin:
    with io.TextIOWrapper(izip.open(poly_file, 'r'), encoding='utf-8') as fin:
        line = next(fin).split(' ')
        # Get repeated coordinate at the end
        #print('line ', line)
        return np.array([float(x) for x in line[1:] if not _all_spaceRE.match(x)])
        ###### Get just the x,y coordinates, no count at beginning, no repeat at end
        ###### coords = [float(x) for x in line[1:-2]]

    return shapely.geometry.Polygon(list(zip(coords[::2], coords[1::2])))
# ------------------------------------------------------------------
def nc_poly(ncout, izip, arcname, vname, coord_attrs, attrs={}, required=True):
    """
    izip: zip.ZipFile
        Open zip file to read from
    arcname:
        Name of file to read out of izip
    """

    try:
        info = izip.getinfo(arcname)
    except KeyError:
        info = None


    if (not required) and (info is None):
        return None

    poly = _read_polygon(izip, arcname)
    ncout.createDimension(vname, len(poly)//2)
    ncv = ncout.createVariable(vname, 'd', (vname, 'two'), compression='zlib')
    for attr,val in attrs.items():
        setattr(ncv, attr, val)

    for vname in coord_attrs['X'].keys():
        attrval = (coord_attrs['X'][vname], coord_attrs['Y'][vname])
        setattr(ncv, vname, attrval)

    ncv[:] = poly.reshape((len(poly)//2, 2))
    return ncv
# ------------------------------------------------------------------
def difference_encode(ivec):
    """Encode a 1D Numpy vector by computing for compression by computing successive differences.
       Eg: [1, 5, 2] -> [1, 4, -3]
    """
    ret = np.full_like(ivec, ivec[0])
    ret[1:] = ivec[1:] - ivec[:-1]
    return ret

difference_decode = np.cumsum
# ------------------------------------------------------------------
# These are both binary files. The formats are the following:
#  
# File: *.out
#  
# nCells                                   Long
# MaxVelocityValues         fltarr(nCells)
# MaxHeightValues           fltarr(nCells)
# DepoValues                       fltarr(nCells)
#  
#  
# File: *.xy-coord
#  
# nCells                                   Long
# x_vector                              dblarr( NrCells )
# y_vector                              dblarr( NrCells )
#  
#  
# the File *.xy-coord contains the cell-center coordinate points of the result arrays. With this information, you should be able to mosaic the results, and then you have to output them as GeoTiff’s……
#  
# In case this information helps you enough to continue for the moment, we can also postpone the meeting, until you run into problems 😊, and we can discuss it then?
#  
# All the best
#  
# Marc

def parse_xy_coord(gridI, fin):
    """Read the .xy-coord file"""

    # https://docs.python.org/3/library/struct.html
    # < = little-endian
    # L = unsigned long

    # Read the .xy-coord file
    # ncells: long
    fmt = '<L'
    buf = fin.read(struct.calcsize(fmt))
    ncells = struct.unpack(fmt, buf)[0]

    # xvec: double64[ncells]
    buf = fin.read(ncells * 8)
    xvec = np.frombuffer(buf, dtype='<f8')
    buf = fin.read(ncells * 8)
    yvec = np.frombuffer(buf, dtype='<f8')

    # Convert (double precision) x/y coordinates to (int) i/j
    ivec, jvec = gridI.to_ij(xvec, yvec)
    return ivec, jvec


def nc_xy_coord(ncout, gridI, coord_attrs, ivec, jvec):
    """
    izip, arcname:
        File .xy-coord file to read (from inside a zip)
    Returns: ivec,jvec
        Coordinates of gridcells in the local subdomain grid
    """

    # Read the original file
##    with open(fname,'rb') as fin:
#    with izip.open(arcname, 'r') as fin:
#        ivec, jvec = parse_xy_coord(gridI, fin)

    # Difference-encode i/j to increase compression
    i_diff = difference_encode(ivec)
    j_diff = difference_encode(jvec)

    ncout.createDimension('ncells', len(i_diff))
    ncvi = ncout.createVariable('i_diff', 'i', ('ncells',), compression='zlib')
    ncvi.description = "Difference-compressed X index of gridcells, uncompress using np.cumsum().  Use geotransform to convert to X in projected space"

    for k,v in coord_attrs['X'].items():
        setattr(ncvi, k, v)

    ncvj = ncout.createVariable('j_diff', 'i', ('ncells',), compression='zlib')
    ncvj.description = "Difference-compressed Y index of gridcells, uncompress using np.cumsum().  Use geotransform to convert to Y in projected space"
    for k,v in coord_attrs['Y'].items():
        setattr(ncvj, k, v)

    ncvi[:] = i_diff
    ncvj[:] = j_diff

    return ivec,jvec

# --------------------------------------------------------------
def parse_out(fin):
    """Read the .out file"""

    # ncells: long
    fmt = '<L'
    buf = fin.read(struct.calcsize(fmt))
    ncells = struct.unpack(fmt, buf)[0]
#    print('ncells ', ncells)

    buf = fin.read(ncells * 4)
    max_vel = np.frombuffer(buf, dtype='<f4')
    buf = fin.read(ncells * 4)
    max_height = np.frombuffer(buf, dtype='<f4')
    buf = fin.read(ncells * 4)
    depo = np.frombuffer(buf, dtype='<f4')


    return (
        ('max_vel', max_vel, {'units': 'm s-1'}),
        ('max_height', max_height, {'units': 'm'}),
        ('depo', depo,  {'units': 'm'}))

def nc_out(ncout, namevals, attrs={}):
    """
    Returns: {name: val}
        Value of variables read
        (max_vel, max_height, depo)
    """
#    # Read the values from the .out file
##    with open(fname, 'rb') as fin:
#    with izip.open(arcname, 'r') as fin:
#        namevals = parse_out(fin)

    # Create and populate the variables
    ncvs = list()
    for vname, val, vattrs in namevals:
        ncv = ncout.createVariable(vname, 'd', ('ncells',), compression='zlib')
        for k,v in attrs.items():
            setattr(ncv, k, v)
        for k,v in vattrs.items():
            setattr(ncv, k, v)
        ncvs.append(ncv)
    ret = dict()
    for (name, val,_),ncv in zip(namevals, ncvs):
        ncv[:] = val
        ret[name] = val

    return ret


# ----------------------------------------------------------
def names_by_ext(izip):
    names = izip.namelist()
    exts = (name.split('.',1)[1] for name in names)
    return dict(zip(exts,names))

class OverrunChecker:

    def __init__(self, dem_mask_tif):
        if os.path.exists(dem_mask_tif):
            self.gridI,dem_mask,_ = gdalutil.read_raster(dem_mask_tif)
            self.dem_mask = dem_mask.astype(np.byte)

    def is_overrun(self, in_zip, out_zip):
        """Determines whether a RAMMS result is overrun

        in_zip, out_zip:
            Already-open zip files
        """

        with contextlib.ExitStack() as stack:

            # Open .in.zip and .out.zip files if not already open
            if not isinstance(in_zip, zipfile.ZipFile):
                in_zip = zipfile.ZipFile(in_zip, 'r')
                stack.enter_context(in_zip)

            if not isinstance(out_zip, zipfile.ZipFile):
                out_zip = zipfile.ZipFile(out_zip, 'r')
                stack.enter_context(out_zip)


            out_names = names_by_ext(out_zip)

            # If RAMMS did not detect an overrun, we are fine.
            if 'out.overrun' not in out_names:
                return False

            # If no mask file, we are done, just rely on C++ RAMMS
            # assessment that an overrun HAS occurred.
            if not hasattr(self, 'dem_mask'):
                return True

            in_names = names_by_ext(in_zip)

            # RAMMS thinks it overran.  Inspect the domain mask further to
            # determine whether it in fact overran.



            # Identify oedge, the set of gridcells that, if the avalanche hits them,
            # constitute an overrun.
            with in_zip.open(in_names['xy-coord'], 'r') as fin:
                ivec, jvec = parse_xy_coord(self.gridI, fin)
                oedge = xyedge.oedge(ivec, jvec, self.gridI.nx, self.gridI.ny, self.dem_mask)

            # See if we hit any of the oedge gridcells
            with out_zip.open(out_names['out'], 'r') as fin:
                namevals = parse_out(fin)
                vals = {name:val for name,val,_ in namevals}

            return \
                   np.any(np.logical_and(oedge != 0, vals['max_height'] > 0)) \
                or np.any(np.logical_and(oedge != 0, vals['max_vel'] > 0)) \
                or np.any(np.logical_and(oedge != 0, vals['depo'] > 0))
# -------------------------------------------------------------
def ramms_to_nc0(out_zip, id_status, ncout):
    """
    base:
        Base name of avalanche, including full pathname.
        Eg: ../mypath/juneauA00000For_5m_30L_4981

        The following files are expected to be present:

        $ ls -ltrah
        total 123720
        -rw-rw-r-- 2.4K Jul 10 14:15 juneauA00000For_5m_30L_4981.relp
        -rw-rw-r-- 186B Jul 10 14:15 juneauA00000For_5m_30L_4981.domp
        -rw-rw---- 104B Jul 11 03:12 juneauA00000For_5m_30L_4981.v1.dom
        -rw-rw---- 1.3K Jul 11 03:12 juneauA00000For_5m_30L_4981.rel
        -rw-rw----  15M Jul 11 03:12 juneauA00000For_5m_30L_4981.xyz
        -rw-rw----  14M Jul 11 03:13 juneauA00000For_5m_30L_4981.xy-coord
        -rw-rw----  14M Jul 11 03:13 juneauA00000For_5m_30L_4981.var
        -rw------- 1.1K Jul 11 03:13 juneauA00000For_5m_30L_4981.av3
        -rw-r--r--  10K Jul 12 03:55 juneauA00000For_5m_30L_4981.out.log
        -rw-r--r--  11M Jul 12 03:55 juneauA00000For_5m_30L_4981.out


    """
#    check_overruns = OverrunChecker(dem_mask_tif)

    base = str(out_zip)[:-8]    # Remove .out.zip
    leaf = os.path.split(base)[1]
    with zipfile.ZipFile(f'{base}.in.zip', 'r') as in_zip:
      with zipfile.ZipFile(f'{base}.out.zip', 'r') as out_zip:

        in_infos = in_zip.infolist()
        out_infos = out_zip.infolist()

        # See if this avalanche overran its domain
        overrun = (id_status == file_info.JobStatus.OVERRUN)

        if 'status' not in ncout.variables:
            ncv = ncout.createVariable('status', 'i')
        ncout.variables['status'].overrun = 1 if overrun else 0

        # Get the grid
        gridI = pickle.loads(in_zip.read('grid.pik'))

        # http://cfconventions.org/cf-conventions/cf-conventions.html#coordinate-system
        # Write the CRS
        # (TODO: Move this to uafgi/gisutil.py)
        # https://pyproj4.github.io/pyproj/latest/build_crs_cf.html
        crs = pyproj.CRS(gridI.wkt)
        cf_grid_mapping = crs.to_cf()
        ncv = ncout.createVariable('grid_mapping', 'i')
        for k,v in cf_grid_mapping.items():
            setattr(ncv, k, v)
        ncv.crs_wkt = gridI.wkt
        ncv.GeoTransform = ' '.join(str(x) for x in gridI.geotransform)

        cf_coordinate_system = crs.cs_to_cf()
        coord_attrs = {x['axis']: x for x in cf_coordinate_system}
        #print(cf_coordinate_system)


        # The .relp and .domp files
        ncout.createDimension('two', 2)
        nc_poly(ncout, in_zip, f'{leaf}.relp', 'relp', coord_attrs,
            {'description': 'UNOFFICIAL release area polygon written by AKRAMMS Python code.',
            'grid_mapping': 'grid_mapping'},
            required=False)
        nc_poly(ncout, in_zip, f'{leaf}.domp', 'domp', coord_attrs,
            {'description': 'UNOFFICIAL domain polygon written by AKRAMMS Python code.',
            'grid_mapping': 'grid_mapping'},
            required=False)

        # The .rel file
        nc_poly(ncout, in_zip, f'{leaf}.rel', 'rel', coord_attrs,
            {'description': 'OFFICIAL release area polygon written by RAMMS IDL code.',
            'grid_mapping': 'grid_mapping'},
            required=False)

        # The .v?.dom files
        # There will only be one: having more than one in the zip file is vestigal from when
        # we thought we could process overruns without re-running RAMMS.
        ret = nc_poly(ncout, in_zip, f'{leaf}.v1.dom', f'dom', coord_attrs,
            {'description': f'OFFICIAL release area polygon written by RAMMS IDL code.',
            'grid_mapping': 'grid_mapping'},
#            'nx': gridI.nx, 'ny': gridI.ny},    # Make sure we capture the original grid dimensions so we can re-create raster later.  (NO: This turned out to be the original tile, we need the local grid, which is not stored anywhere other than the domain outline itself).
            required=False)

        # The .xyz file (SKIP)

        # -----------------------------------------------------------------
        # Read the xy-coordinates, and also values on that grid
        with in_zip.open(f'{leaf}.xy-coord', 'r') as fin:
            ivec, jvec = parse_xy_coord(gridI, fin)
        with out_zip.open(f'{leaf}.out', 'r') as fin:
            namevals = parse_out(fin)

        # Determine gridcells that are ACTUALLY used
        nzmask = namevals[0][1]>0
        for _,val,_ in namevals[1:]:
            nzmask = np.logical_or(nzmask, val>0)
#        nzmask = np.logical_or(*(val>0 for _,val,_ in namevals))

        # Cut out the fat!
        ivec = ivec[nzmask]
        jvec = jvec[nzmask]
        namevals = [(name,val[nzmask],attrs) for name,val,attrs in namevals]


        # --------------------------------- Write the stuff we just read
        # The .xy-coord file
        ivec,jvec = nc_xy_coord(ncout, gridI, coord_attrs, ivec, jvec)

        # The .out file
        vars = nc_out(ncout, namevals,
            attrs={'grid_mapping': 'grid_mapping'})
            
        max_height = vars['max_height']

        # -----------------------------------

        # Store the bounding box
        ncout.createDimension('lowhigh', 2)
        ncv = ncout.createVariable('bounding_box', 'd', ('lowhigh', 'two'))
        ncv.description = 'Oriented bounding box of region occupied by avalanche.'
        ncv.grid_mapping = 'grid_mapping'

        if len(ivec) > 0:
            i0 = np.min(ivec)
            i1 = np.max(ivec)
            j0 = np.min(jvec)
            j1 = np.max(jvec)

            x0,y0 = gridI.to_xy(i0,j0)
            x1,y1 = gridI.to_xy(i1,j1)

            ncv[:] = np.array([
                [min(x0,x1), min(y0,y1)],
                [max(x0,x1) + gridI.dx*np.sign(gridI.dx), max(y0,y1) + gridI.dy*np.sign(gridI.dy) ]])
        else:
            # Degenerate avalanche covered 0 gridcells.
            # Make a dummy degenerate bounding box
            ncv[:] = np.array([[0.,0.],[0.,0.]])


#        for attr,val in coord_attrs.items():
#            setattr(ncv, attr, val)
    return overrun


# ----------------------------------------------------------
def _archive_single_threaded(akdf0, status_attrs, print_output=False, dry_run=False):
    """Archives a bunch of work on a single thread
    akdf0:
        Must contain cols: exp, combo, releasefile, chunkid, ic
    """

    out_zips = list()
    for (exp, combo,releasefile),akdf1 in akdf0.groupby(['exp', 'combo', 'releasefile']):
        releasefile_mtime = os.path.getmtime(releasefile)
        releasefile_timestamp = datetime.datetime.fromtimestamp(releasefile_mtime).isoformat()
        scombo = '-'.join((str(x) for x in combo))

        expmod = parse.load_expmod(exp)
        arc_dir = expmod.combo_to_scenedir(combo, scenetype='arc')
#        print('arc-dir ', arc_dir)
        x_dir = expmod.combo_to_scenedir(combo, scenetype='x')

#        # Load up dem_mask to help us check for overruns
#        scene_args = params.load(x_dir)
#        dem_tif = pathlib.Path(scene_args['dem_file'])
#        dem_mask_tif = dem_tif.parents[0] / (dem_tif.parts[-1][:-4] + '_mask.tif')
#        check_overruns = archive.OverrunChecker(dem_mask_tif)

        jb = file_info.parse_chunk_release_file(releasefile)
#        arc_dir = jb.scene_dir

        # Read the shapefile this avalanche came from, so we can copy
        # info into the NetCDF file.
        rdf = shputil.read_df(releasefile, read_shapes=False)
        rdf = rdf.set_index('Id')

        for tup in akdf1.reset_index(drop=True).itertuples(index=False):
#            if tup.id == 6570:
#                print(f'archive ', tup)
            inout = file_info.inout_name(jb, tup.chunkid, tup.id)
            out_zip = jb.avalanche_dir / f'{inout}.out.zip'
            out_zip_mtime = os.path.getmtime(out_zip)
            out_zip_dtime = datetime.datetime.fromtimestamp(out_zip_mtime)
            arc_leafbase = f'aval-{jb.pra_size}-{tup.id:05d}'

            # Avoid archiving bad files
            if not file_info.is_file_good(out_zip):
                continue

            # Determine if the avalanche was already archived
            Overrun = 'overrun' if (tup.id_status == file_info.JobStatus.OVERRUN) else ''
            arc_fname = arc_dir / f'{arc_leafbase}-{Overrun}.nc'
            if os.path.exists(arc_fname):
                with netCDF4.Dataset(arc_fname) as nc:
                    ncv = nc.variables['status']
                    ncv_dtime = datetime.datetime.fromisoformat(ncv.avalanche_timestamp)

                    if out_zip_dtime <= ncv_dtime:
                        # print(f'Not archiving based on timestamp: {out_zip}')
                        continue

#                arc_mtime = os.path.getmtime(arc_fname)


            out_zips.append(str(out_zip))
            if dry_run:
                print(f'Except for dry_run, archive {out_zip} -> {arc_leafbase}')
                continue

            # -------- Convert to NetCDF

            # .out.zip file is OK, so let's regenerate
            if print_output:
                print('.', end='')
                sys.stdout.flush()

            os.makedirs(arc_dir, exist_ok=True)

            # Write the full NetCDF file
            tmp_fname = arc_dir / (arc_leafbase + '-tmp.nc')  # Write atomically
            try:
                with netCDF4.Dataset(tmp_fname, 'w') as ncout:
                    # Add info from the RELEASE file
                    ncv = ncout.createVariable('releasefile_attrs', 'i')
                    ncv.description = 'Attributes from the RELEASE shapefile used to set up this avalanche'
                    ncv.Id = tup.id    # The ID we use to identify avalanches
                    # Copy info from the RELEASE file into the NetCDF output.
                    row = rdf.loc[tup.id]
                    for aname,val in row.items():   # Does not include Id because tup.id is the index now
                        setattr(ncv, aname, val)

                    # Add provenance info
                    ncv = ncout.createVariable('status', 'i')
                    for k,v in status_attrs.items():
                        setattr(ncv, k, v)

                    ncv.combo = '{exp}-{scombo}'
                    ncv.releasefile_timestamp = releasefile_timestamp
                    ncv.avalanche_timestamp = out_zip_dtime.isoformat()
                    try:
                        ramms_to_nc0(out_zip, tup.id_status, ncout)
                    except Exception:
                        print('**** ramms_to_nc0: error on tuple ', tup)
                        raise

                    # Add info from scene that created this avalanche
                    with netCDF4.Dataset(os.path.join(x_dir, 'scene.nc')) as ncin:
                        schema = ncutil.Schema(ncin)
                        grp = ncout.createGroup('scene_nc')
                        schema.create(grp)
                        schema.copy(ncin, grp)
#                print(f'Archive {out_zip} -> {arc_fname}')
                os.rename(tmp_fname, arc_fname)
            except Exception:
                # Remove candidate output file, if it exists
                try:
                    os.remove(tmp_fname)
                except FileNotFoundError:
                    pass
                raise

    return out_zips

# ----------------------------------------------------------
def _git_commit(dir):
    cmd = ['git', 'log']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, cwd=dir)
    return proc.stdout.readline().strip()    # We just want head -1

# -----------------------------------------------------------------
def archive_ids(akdf0, debug=False, dry_run=False):
    """Archives in multi-thread
    akdf:
        Resolved to id level.  Also must have id_status set (at least for id_status=OVERRUN)
    """

    print('BEGIN archive_ids')
#    raise ValueError(17)

    archived_out_zips = list()

    # Only archive avalanches that have finished running
    mask = akdf0.id_status.isin([file_info.JobStatus.FINISHED, file_info.JobStatus.OVERRUN])
    akdf0 = akdf0[mask]

    # Don't need this column, and it breaks pickle / multiprocessing...
    if 'parsed' in akdf0.columns:
        akdf0 = akdf0.drop('parsed', axis=1)


    # Status attributes to write into all the NetCDF files
    status_attrs = dict(
        created_by = os.getlogin(),
        archive_timestamp = datetime.datetime.now().isoformat(),
        akramms_commit = _git_commit(os.path.join(config.HARNESS, 'akramms')),
        uafgi_commit = _git_commit(os.path.join(config.HARNESS, 'uafgi')))

    akdfs = np.array_split(akdf0, config.ncpu_archive)

    with contextlib.ExitStack() as stack:
        ex = stack.enter_context(concurrent.futures.ThreadPoolExecutor(1)) if debug \
            else concurrent.futures.ProcessPoolExecutor(config.ncpu_archive)

        futures = [ex.submit(_archive_single_threaded,
            akdfs[0], status_attrs,
            print_output=True, dry_run=dry_run)]

        futures += [ex.submit(_archive_single_threaded,
            akdfx, status_attrs,
            print_output=False, dry_run=dry_run)
            for akdfx in akdfs[1:]]

        for future in futures:
            archived_out_zips += future.result()

    return archived_out_zips
# ----------------------------------------------------------
def _zip_dir(idir, ofname):
    with zipfile.ZipFile(ofname, 'w', compression=zipfile.ZIP_DEFLATED) as ozip:
        for leaf in os.listdir(idir):
            ozip.write(idir / leaf, arcname=leaf) #, compress_type=zipfile.ZIP_DEFLATD)

def copy_shapefiles(expmod, combo, dry_run=False):
    xdir = expmod.combo_to_scenedir(combo, scenetype='x')
    arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')

    # Only copy shapefile is the source and destination diretories
    # already exist. i.e. there has been real work done so far
    if not os.path.exists(xdir) or not os.path.exists(arcdir):
        return

    # Copy relevant Combo-related metadata
    for leaf in ('RELEASE', 'DOMAIN'):
        with ioutil.WriteIfDifferent(arcdir / f'{leaf}.zip') as owid:
            _zip_dir(xdir / leaf, owid.tmpfile)
#        shutil.rmtree(arcdir / leaf, ignore_errors=True)
#        shutil.copytree(xdir / leaf, arcdir / leaf)

    for leaf in ('scene.nc', 'scene.cdl'):
        with ioutil.WriteIfDifferent(arcdir / leaf) as owid:
            shutil.copy2(xdir / leaf, owid.tmpfile)

class ArchiveContents(typing.NamedTuple):
    """
    gridA_gt:
        Geotransform of gridA (eg: gridA.geotransform)
    gridA_wkt:
        CRS used in gridA
    iA, jA: np.array[n]
        i/j location of each gridcell, in gridA (the subdomain tile WITH MARGIN)
    max_vel, max_height, depo: np.array[n]
        Data values output by RAMMS C++
    """
    gridA_gt: object
    gridA_wkt: str
    iA: object
    jA: object
    max_vel: object
    max_height: object
    depo: object

def read_nc(avalfile):
    with netCDF4.Dataset(tup.avalfile) as nc:
        # --------------- gridA is the subdomain tile, WITH MARGIN
        # Geotransform of this avalanche's local grid
        # TODO: Store Geotransform as machine-precision doubles in the file
        gridA_gt = np.array([float(x) for x in nc.variables['grid_mapping'].GeoTransform.split(' ')])
        gridA_wkt = nc.variables['grid_mapping'].crs_wkt

        # --------------- Determine gridL, an x/y oriented grid (subgrid of the tile) containing the avalanche.
        i_diff = nc.variables['i_diff'][:]
        j_diff = nc.variables['j_diff'][:]

        return ArchiveContents(
            gridA_gt=gridA_gt, gridA_wkt=gridA_wkt,
            iA=np.cumsum(i_diff),
            jA=np.cumsum(j_diff),
            max_vel=nc.variables['max_vel'][:].astype('f4'),
            max_height=nc.variables['max_height'][:].astype('f4'),
            depo=nc.variables['depo'][:].astype('f4'))




def finish_combo(expmod, combo, dry_run=False):

    xdir = expmod.combo_to_scenedir(combo, scenetype='x')
    arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')

    control_fname = arcdir / 'archived.txt'
    extent_zip = arcdir / 'EXTENT.zip'
    if dry_run:
        print(f'If not for dry_run, I would be writing the file {extent_zip}')
        return



    # ---------------- Write the control file
    if not os.path.isfile(control_fname):
        with open(control_fname, 'w') as out:
            out.write('Combo archived\n')
 
    # ----------------- Write /vsizip/EXTENT.zip/extent.shp
    # (which is also the control file)
    # Get a list of all the Avalanches in this (archived) combo
    scombo = expmod.name + '-' + '-'.join(str(x) for x in combo)
    parseds = parse.parse_args([scombo])
    akdf = resolve.resolve_to(parseds, 'id', realized=True, scenetypes={'arc'})
    # TODO: Look at this dataframe

    # Open the extent file (Shapefile within a Zip archive)
#    extent_vsif = gdal.VSIFOpenL('/vsizip/{}.tmp'.format(extent_zip), 'wb')
    # https://gis.stackexchange.com/questions/306299/how-can-i-write-a-zipped-shapefile-with-ogr2ogr-and-vsizip
    extent_shp = f'/vsizip/{extent_zip}.tmp/extent.shz'

    extent_ds = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(extent_shp)
    try:
        extent_layer = extent_ds.CreateLayer(extent_shp, ogrutil.to_srs(expmod.wkt), geom_type=ogr.wkbMultiPolygon )

        # https://gis.stackexchange.com/questions/392515/create-a-shapefile-from-geometry-with-ogr
        extent_Id = extent_layer.CreateField(ogr.FieldDefn('Id', ogr.OFTInteger))

        # Read avalanches, compute extent, and write into extent file
        for tup in akdf.itertuples(index=False):
            if not os.path.isfile(tup.avalfile):
                raise ValueError(f'Missing avalanche file: {tup.avalfile}')

            aval = read_nc(tup.avalfile)
            polygonize_extent(aval, extent_layer, extent_Id)
    finally:
        extent_ds = None
        extent_vsif = None

    os.rename(f'{extent_zip}.tmp', extent_zip)

    # --------------- (Very conservatively)
    # Delete the xdir by moving it to a todel directory.
    if os.path.exists(xdir):
        todel = xdir.parents[0] / 'todel'
        os.makedirs(todel, exist_ok=True)
        odir = todel / xdir.parts[-1]
        if os.path.exists(odir):
            shutil.rmtree(odir)
        shutil.move(xdir, odir)


# ----------------------------------------------------------
def read_reldom(arcdir_zip, ext, **kwargs):
    """Reads all _rel/_dom files in an archive directory
    Uses ogrutil; reads into OGR-type geometries

    NOTE: This is similar but different from chunk.read_reldom()

    ext: 'rel' or 'dom' or 'chull'

    read_shapes:
        Should the acutal shapes be read?  Or just the metadata?
    wkt:
        Projection (CRS) to use, overrides one in shapefile
    shape0:
        Name to call the "shape0" columns when all is said and done
        (i.e. the original shape, before it was reprojected)
    shape:
        Name to call final shape column
    """

    # Unzip required file(s)
    #restr = rf'^(.*)_{ext}\.(...)$'
    restr = rf'^(.*)_{ext}\.shp$'
    fnames = list()     # *.shp files to read
    fileRE = re.compile(restr)
    with zipfile.ZipFile(arcdir_zip) as izip:
        for info in izip.infolist():
            match = fileRE.match(info.filename)
            if match is not None:
                fnames.append(f'/vsizip//{arcdir_zip}/{info.filename}')

    dfs = list()
    for fname in fnames:
        dfs.append(ogrutil.read_df(fname, **kwargs))

    return pd.concat(dfs)
# ----------------------------------------------------------
def polygonize_extent(aval,
    extent_layer, extent_Id):
#    iA, jA, gridA_gt, crs_wkt, max_vel, max_height, depo,

    """Creates a polygon for the extent of an avalanche, and writes it
    into an open OGR datasource.

    aval: Result of read_nc()

    extent_layer: OUTPUT
        OGR layer to write into
    extent_Id: OUTPUT
        Reference to the OGR shapefile field called "Id", where
        Avalanche Id is to be stored.

    Example creating extent inputs:
      extent_ds = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(extent_shp)
      extent_layer = extent_ds.CreateLayer(extent_shp, ogrutil.to_srs(gridM.wkt), geom_type=ogr.wkbMultiPolygon )
      # https://gis.stackexchange.com/questions/392515/create-a-shapefile-from-geometry-with-ogr
      extent_Id = extent_layer.CreateField(ogr.FieldDefn('Id', ogr.OFTInteger))

    """

    # Create a sub-grid gridL around just the avalanche (fast polygonize)
    iL_min = np.min(iA) - 2
    iL_max = np.max(iA) + 3
    jL_min = np.min(jA) - 2
    jL_max = np.max(jA) + 3

    iL = iA - iL_min    # Vector operation
    jL = jA - jL_min
    gridL_gt = np.array(gridA_gt, dtype='i8')
    gridL_gt[0] += gridL_gt[1] * iL_min
    gridL_gt[3] += gridL_gt[5] * jL_min
    gridL = gisutil.RasterInfo(
        crs_wkt, #nc.variables['grid_mapping'].crs_wkt,
        iL_max - iL_min,
        jL_max - jL_min,
        gridL_gt)

#    # Read avalanche output as values on list-of-gridcells
#    max_vel = nc.variables['max_vel'][:].astype('f4')
#    max_height = nc.variables['max_height'][:].astype('f4')
#    depo = nc.variables['depo'][:].astype('f4')

    # On March 5, 2024 Marc Christen wrote:
    # > These outlines are defined as an envelope of grid cells
    # > of an avalanche, where
    # >   Flow-depth > 0.25m AND
    # >   velocity > 1m/s
    nzmask_val = np.zeros(max_vel.shape, dtype=np.int32)
    nzmask_val[np.logical_and(max_height > 0.25, max_vel > 1.0)] = tup_id

    # Burn the gridcells that are part of our grid
    # (already pared down)
    nzmaskL = np.zeros((gridL.ny, gridL.nx), dtype=np.int32)
    nzmaskL[jL,iL] = nzmask_val    # This will get written into the attribute table

    nzmask_ds = gdalutil.raster_ds((gridL, nzmaskL, 0))
    nzmask_band = nzmask_ds.GetRasterBand(1)

    # Produces a separate polygon for each different (non-zero) value in nzmaskL
    # Since we've only set things to tup_id, we will only get Polygon(s) for that.
    # The pixel value is placed in the Id attribute
    # Polygonize docs: https://gdal.org/api/gdal_alg.html (search for GDALPolygonize)
    gdal.Polygonize(nzmask_band, nzmask_band,
        extent_shps[tup_combo].layer, extent_shps[tup_combo].Id)


# ----------------------------------------------------------


#TODO: Add T/S/M/L categorization to netCDF file
#Add authorship metadata to netCDF file
