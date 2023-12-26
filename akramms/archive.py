import os,re,itertools,struct,pickle,zipfile,io,shutil
import contextlib,sys,datetime,subprocess
import concurrent.futures
import numpy as np
import pandas as pd
import netCDF4
import pyproj
from uafgi.util import gdalutil,shputil,ncutil
from akramms import config,parse,file_info,resolve,overrun

# Convert Avalanche outputs to NetCDF

__all__ = ('archive',)

# ------------------------------------------------------------------
# NOTE: Similar to rammsutil.read_polygon_from_zip()
_all_spaceRE = re.compile(r'$\s*^')
def _read_polygon(izip, poly_file):

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


def nc_xy_coord(ncout, gridI, coord_attrs, izip, arcname):
    """
    izip, arcname:
        File .xy-coord file to read (from inside a zip)
    Returns: ivec,jvec
        Coordinates of gridcells in the local subdomain grid
    """

    # Read the original file
#    with open(fname,'rb') as fin:
    with izip.open(arcname, 'r') as fin:
        ivec, jvec = parse_xy_coord(gridI, fin)

    # Difference-encode i/j to increase compression
    divec = difference_encode(ivec)
    djvec = difference_encode(jvec)

    ncout.createDimension('ncells', len(divec))
    ncvi = ncout.createVariable('i_diff', 'i', ('ncells',), compression='zlib')
    ncvi.description = "Difference-compressed X index of gridcells, uncompress using np.cumsum().  Use geotransform to convert to X in projected space"

    for k,v in coord_attrs['X'].items():
        setattr(ncvi, k, v)

    ncvj = ncout.createVariable('j_diff', 'i', ('ncells',), compression='zlib')
    ncvj.description = "Difference-compressed Y index of gridcells, uncompress using np.cumsum().  Use geotransform to convert to Y in projected space"
    for k,v in coord_attrs['Y'].items():
        setattr(ncvj, k, v)

    ncvi[:] = divec
    ncvj[:] = djvec

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

def nc_out(ncout, izip, arcname, attrs={}):
    """
    Returns: {name: val}
        Value of variables read
        (max_vel, max_height, depo)
    """
    # Read the values from the .out file
#    with open(fname, 'rb') as fin:
    with izip.open(arcname, 'r') as fin:
        namevals = parse_out(fin)

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
def is_overrun(ozip):
    """See if this avalanche overran its domain

    ozip: zipfile.ZipFile
        Open zipfile of <xyz>.out.zip
    """
    arcnames = [os.path.split(x)[1] for x in ozip.namelist()]
    print(f'is_overrun {arcnames}')
    overrun = any(x.endswith('.out.overrun') for x in arcnames)

    return overrun
# ----------------------------------------------------------
def ramms_to_nc0(out_zip, ncout):
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
    base = str(out_zip)[:-8]    # Remove .out.zip
    leaf = os.path.split(base)[1]
    with zipfile.ZipFile(f'{base}.in.zip', 'r') as in_zip:
      with zipfile.ZipFile(f'{base}.out.zip', 'r') as out_zip:

        in_infos = in_zip.infolist()
        out_infos = out_zip.infolist()

        # See if this avalanche overran its domain
        overrun = is_overrun(out_zip)

        if 'status' not in ncout.variables:
            ncv = ncout.createVariable('status', 'i')
        ncout.variables['status'].overrun = 1 if overrun else 0
#        ncout.variables['status'].overrun = 'True' if overrun else 'False'

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
        vdoms = list()
        for i in itertools.count(1):
            ifname = f'{base}.v{i}.dom'
            ret = nc_poly(ncout, in_zip, f'{leaf}.v{i}.dom', f'dom_v{i}', coord_attrs,
                {'description': f'OFFICIAL release area polygon written by RAMMS IDL code (enlargement try #{i}).'},
                required=False)
            if ret is None:
                break

        # The .xyz file (SKIP)

        # The .xy-coord file
        ivec,jvec = nc_xy_coord(ncout, gridI, coord_attrs, in_zip, f'{leaf}.xy-coord')

        # The .out file
        vars = nc_out(ncout, out_zip, f'{leaf}.out',
            attrs={'grid_mapping': 'grid_mapping'})
            
        max_height = vars['max_height']

        # -----------------------------------
        # Determine bounding box
        nz = (max_height != 0)
        ivec_nz = ivec[nz]
        jvec_nz = jvec[nz]

        i0 = np.min(ivec_nz)
        i1 = np.max(ivec_nz)
        j0 = np.min(jvec_nz)
        j1 = np.max(jvec_nz)

        x0,y0 = gridI.to_xy(i0,j0)
        x1,y1 = gridI.to_xy(i1,j1)

        # Store the bounding box
        ncout.createDimension('lowhigh', 2)
        ncv = ncout.createVariable('bounding_box', 'd', ('lowhigh', 'two'))
        ncv.description = 'Oriented bounding box of region occupied by avalanche.'
        ncv.grid_mapping = 'grid_mapping'
#        for attr,val in coord_attrs.items():
#            setattr(ncv, attr, val)
        ncv[:] = np.array([
            [min(x0,x1), min(y0,y1)],
            [max(x0,x1) + gridI.dx*np.sign(gridI.dx), max(y0,y1) + gridI.dy*np.sign(gridI.dy) ]])
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

        jb = file_info.parse_chunk_release_file(releasefile)
#        arc_dir = jb.scene_dir

        # Read the shapefile this avalanche came from, so we can copy
        # info into the NetCDF file.
        rdf = shputil.read_df(releasefile, read_shapes=False)
        rdf = rdf.set_index('Id')

        for tup in akdf1.reset_index(drop=True).itertuples(index=False):
            if tup.id == 6570:
                print(f'archive ', tup)
            inout = file_info.inout_name(jb, tup.chunkid, tup.id)
            out_zip = jb.avalanche_dir / f'{inout}.out.zip'
            out_zip_mtime = os.path.getmtime(out_zip)
            out_zip_dtime = datetime.datetime.fromtimestamp(out_zip_mtime)
            arc_leafbase = f'aval-{jb.pra_size}-{tup.id:05d}'

            # Avoid archiving bad files
            if not file_info.is_file_good(out_zip):
                continue

            # Avoid archiving overrun files
#            with zipfile.ZipFile(out_zip, 'r') as ozip:
#                overrun = is_overrun(ozip)
            overrun = (tup.id_status == file_info.JobStatus.OVERRUN)
#            if overrun:
#                print(f'overrun: {out_zip}')

            # Determine if the avalanche was already archived
            Overrun = 'overrun' if overrun else ''
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
                    # Copy info from the RELEASE file into the NetCDF output.
                    row = rdf.loc[tup.id]
                    for aname,val in row.items():
                        setattr(ncv, aname, val)

                    # Add provenance info
                    ncv = ncout.createVariable('status', 'i')
                    for k,v in status_attrs.items():
                        setattr(ncv, k, v)

                    ncv.combo = '{exp}-{scombo}'
                    ncv.releasefile_timestamp = releasefile_timestamp
                    ncv.avalanche_timestamp = out_zip_dtime.isoformat()
                    ramms_to_nc0(out_zip, ncout)

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

def finish_combo(expmod, combo, dry_run=False):
    xdir = expmod.combo_to_scenedir(combo, scenetype='x')
    arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')

    
    ofname = arcdir / 'archived.txt'
    if dry_run:
        print(f'If not for dry_run, I would be writing the file {ofname}')
        return

    # Copy relevant Combo-related metadata
    for leaf in ('RELEASE', 'DOMAIN'):
        _zip_dir(xdir / leaf, arcdir / f'{leaf}.zip')
#        shutil.rmtree(arcdir / leaf, ignore_errors=True)
#        shutil.copytree(xdir / leaf, arcdir / leaf)

    for leaf in ('scene.nc', 'scene.cdl'):
        shutil.copy2(xdir / leaf, arcdir / leaf)

    # Write the control file
    with open(ofname, 'w') as out:
        out.write('Combo archived\n')



# ----------------------------------------------------------
def read_reldom(arcdir_zip, ext, tdir, **kwargs):
    """Reads all _rel/_dom files in an archive directory
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
    restr = rf'^(.*)_{ext}\.(...)$'
    fnames = list()     # *.shp files to read
    fileRE = re.compile(restr)
    with zipfile.ZipFile(arcdir_zip) as izip:
        for info in izip.infolist():
            match = fileRE.match(info.filename)
            if match is not None:
                izip.extract(info, path=tdir.location)
                fname = os.path.join(tdir.location, info.filename)
                if fname.endswith('.shp'):
                    fnames.append(fname)

    # Read the shapefile
    dfs = list()
    for fname in fnames:
        print('fname ', fname)
        df = shputil.read_df(fname, **kwargs)
        df['pra_size'] = df['pra_size'].astype(str)
        dfs.append(df)

    return pd.concat(dfs)


#            print('xxxxxxxxx ', info.filename, match)
#            if match is not None:
#                # Doesn't work because shputil.read() doesn't use GDAL
#                # fname = f'/vsizip/{arcdir}/RELEASE.zip/{info.filename}'
# ----------------------------------------------------------
#def archive_combos(akdf_combo, debug=False, dry_run=False, archive_overruns=False):
#    """
#    akdf:
#        Resolved to combo level
#    """
#    akdf = resolve.resolve_chunk(akdf_combo, scenetypes='x')
#    akdf = resolve.resolve_id(akdf, realized=True, stage='out', include_overruns=False)
#    akdf = overrun.drop_duplicates(akdf)    # Remove overruns that were re-done
#
#    archive_ids(akdf, debug=debug, dry_run=dry_run)
#
#    for tup in akdf_combo.reset_index(drop=True).itertuples(index=False):
#        arcdir = expmod.combo_to_scenedir(scenetype='arc')
#        with open(arcdir / 'archived.txt', 'w') as out:
#            out.write('Combo archived\n')
#
## ----------------------------------------------------------
#def main():
#    out_zip = '/home/efischer/prj/ak/ak-ccsm-1981-1990-lapse-For-30/x-113-045/CHUNKS/x-113-0450000230MFor_10m/RESULTS/x-113-04500002For_10m/30M/x-113-04500002For_10m_30M_3200.out.zip'
#    with netCDF4.Dataset('x.nc', 'w') as ncout:
#        ncv = ncout.createVariable('status', 'i')
#        ramms_to_nc0(out_zip, ncout)

#main()


#TODO: Add T/S/M/L categorization to netCDF file
#Add authorship metadata to netCDF file
