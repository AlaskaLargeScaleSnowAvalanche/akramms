import shutil,os,re,zipfile,glob,datetime,time,subprocess,sys
import netCDF4
from uafgi.util import ncutil
from akramms import ncaval,r_ramms,config
from akramms import avalparse
from akramms.util import exputil
import concurrent.futures
import traceback

#_out_zipRE = re.compile(r'^(.*)_(\d+)\.out\.zip$')
# Status of each avalanche found on disk
OK = 0                # Implies .out.zip
NO_IN_ZIP = 1
NO_OUT_ZIP = 3
UNKNOWN_ERROR = 4
ARCHIVED = 5        # It's a .nc file
MAX_STATUS = 5

error_msgs = {
    NO_IN_ZIP: 'ERROR: No .in.zip for Avalanche IDs: {ids}',
    NO_OUT_ZIP: 'ERROR: No .out.zip for Avalanche IDs {ids}',
    UNKNOWN_ERROR: 'Unknown error archiving: {ids}',
}


#TODO: Put avalanche bounding box into NetCDF file.  (Or a related database file)

# -----------------------------------------------------------------
def out_zip_status(out_zip):
    """Examines an .out.zip file to determine whether it is OK, or if
    there is a problem with it that might affect mosaic."""

    basename = out_zip[:-8]    # Remove .out.zip

    # Make sure .in.zip exists
    in_zip = basename + '.in.zip'
    if not os.path.exists(in_zip):
        return NO_IN_ZIP

#    # Make sure the avalanche didn't overrun the domain.
#    with zipfile.ZipFile(basename+'.out.zip', 'r') as in_zip:
#        arcnames = [os.path.split(x)[1] for x in in_zip.namelist()]
#    if any(x.endswith('.out.overrun') for x in arcnames):
#        return OVERRUN

    # Add as archivable ID
    return OK
# -----------------------------------------------------------------
def getmtime(fname):
    """Returns modification time of a file; or -1 if it doesn't exist."""
    if os.path.exists(fname):
        return os.path.getmtime(fname)
    else:
       return -1.0

# -----------------------------------------------------------------
def _git_commit(dir):
    cmd = ['git', 'log']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, cwd=dir)
    return proc.stdout.readline().strip()    # We just want head -1

# -----------------------------------------------------------------

class ArchiveFiles:
    def __init__(self, ithread, exp, release_df, x_dir, status_attrs):
        self.ithread = ithread
        self.exp = exp    # Must be picklable
        self.akdf = akdf
        self.x_dir = x_dir
        self.status_attrs = status_attrs

    def __call__(self, to_archive):
        """
        to_archive: [(id,arc_fname,out_zip), ...]
        """

        from akramms.util import exputil
        ithread = self.ithread
        exp_mod = exputil.load(self.exp)
        akdf = self.akdf
        x_dir = self.x_dir

        archived_out_zips = list()
        if ithread == 0:
            print(f'Thread Archiving {len(to_archive)} avalanches')
        for ix,(id,arc_fname,out_zip) in enumerate(to_archive):

            if ithread == 0 and ix % 50 == 0:
                print(f'\n{ix:5} ', end='')

            ncaval.archive_avalanche(out_zip, arc_fname, debug=(ithread==0))
            #arc_fnames.append(arc_fname)
            try:
                archived_out_zips.append(out_zip)
            except ValueError as err:
                if 'shape mismatch' in str(err):
                    print(f'SKIPPING NetCDF: Shape mismatch between .in.zip and .out.zip files for: {out_zip}')
                else:
                    raise

            # ----------------------------------------



        if ithread == 0:
            print('\nDone!')
            sys.stdout.flush()
        return archived_out_zips


# -----------------------------------------------------------------


# -----------------------------------------------------------------
def fetch(exp_mod, combo, ids):
    """Returns the names of archive files, based on a particular combo
    and list of IDs within that combo.  Archives the avalanches if needed.

    exp_mod:
        Main experiment info
    combo:
        Describes which RAMMS run within the experiment
    id:
        Which avalanche within the RAMMS run we wish to fetch
    returns: [(id, nc_fname, out_zip), ...]
        NetCDF files matching the query.
        if out_zip is None:
            The .out.zip file didn't exist  but NetCDF was already done.
    """

    x_dir = exp_mod.combo_to_scene_dir(combo, type='x')
    arc_dir = exp_mod.combo_to_scene_dir(combo, type='arc')

    out_zips = exputil.out_zips(exp_mod, combo)
    ncs = exputil.list_archive_ncs(exp_mod, combo)

    # Information from the RELEASE shpaefile
    release_files,release_df = exputil.release_df(exp_mod, combo, type='x')

    nc_fnames = list()
    to_archive = list()
    archived_out_zips = list()
    for id in ids:
        # -------- Get name and modification time of original .out.zip file
        try:
            out_zip,ozip_sizecat = out_zips[id]
            # Make sure the out.zip file is complete / ready to archive
            status = out_zip_status(out_zip)
            if status == OK:
                out_zip_mtime = os.path.getmtime(out_zip)
            else:
                # Act like the .out.zip file does not exist
                out_zip_mtime = -1.0
        except KeyError:
            out_zip_mtime = -1.0

        # ------- Get name and modification time of archive .nc file
        if id in ncs:
            name,arc_sizecat = ncs[id]
            arc_fname = os.path.join(arc_dir, name)
            arc_mtime = os.path.getmtime(arc_fname)

            # Reported sizecats must be the same
            assert arc_sizecat == ozip_sizecat
        else:
            arc_mtime = -1.0


        # -------- Decide whether we need to regenerate
#        print(f'{id}: {out_zip_mtime} -> {arc_mtime}')
        if arc_mtime > out_zip_mtime:
            # Arc file exists and is up-to-date, DO NOT regenerate
            nc_fnames.append((id,arc_fname, out_zip))
        elif out_zip_mtime >= 0:
            # out.zip exists but arc is not up-to-date, regenerate.
            arc_dir = exp_mod.combo_to_scene_dir(combo, type='arc')
            arc_fname = os.path.join(
                arc_dir,
                f'aval-{ozip_sizecat}-{id}.nc')
            to_archive.append((id, arc_fname, out_zip))
            nc_fnames.append((id, arc_fname, out_zip))

    # -------------------------------
    # -------------------------------


    # Status attributes
    status_attrs = dict(
        exp_mod = exp_mod.name,
        created_by = os.getlogin(),
        # TODO: Determine which release file this is associated with and get appropriate timestamp
        #release_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(release_file)).isoformat(),
        archive_timestamp = datetime.datetime.now().isoformat(),
        akramms_commit = _git_commit(os.path.join(config.HARNESS, 'akramms')),
        uafgi_commit = _git_commit(os.path.join(config.HARNESS, 'uafgi')))

    # Archive the files
    nz = [x for x in to_archive if x[1] is not None]    # x[1] == arc_fname
    ncpu = config.ncpu_compress
    nzs = [nz[i::ncpu] for i in range(ncpu)]    # https://stackoverflow.com/questions/24483182/python-split-list-into-n-chunks
    print(f'Archiving {len(nz)} avalanches with {ncpu}-way parallelism')
    with concurrent.futures.ProcessPoolExecutor(ncpu) as ex:
#    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        archive_files0 = ArchiveFiles(0, exp_mod, release_df, x_dir, status_attrs)
        archive_files1 = ArchiveFiles(1, exp_mod, release_df, x_dir, status_attrs)
        futures = [ex.submit(archive_files0, nzs[0])]
        futures += [ex.submit(archive_files1, nz) for nz in nzs[1:]]
        for future in futures:
            archived_out_zips += future.result()

    # =======================================================
    # Pare down nc_fnames
    nc_fnames = [(id, nc_fname, out_zip) for id,nc_fname,out_zip in nc_fnames if os.path.exists(nc_fname)]
    return \
        [(id,nc_fname) for id,nc_fname,_ in nc_fnames], \
        [out_zip for _,_,out_zip in nc_fnames if out_zip is not None]

# -----------------------------------------------------------------
def archive_combo(exp_mod, combo, ids=None):
    """Archives all IDs in a combo.
    Returns: {id: arc_fname}
    """

    scene_dir = exp_mod.combo_to_scene_dir(combo, type='x')
    archive_dir = exp_mod.combo_to_scene_dir(combo, type='arc')

    # Copy a few top-level files
    os.makedirs(archive_dir, exist_ok=True)
    for leaf in ('scene.nc', 'scene.cdl', 'crs.prj'):
        src = os.path.join(scene_dir, leaf)
        shutil.copy2(src, archive_dir)

    # Copy the lists PRA polygons
    shutil.copytree(
        os.path.join(scene_dir, 'RELEASE'),
        os.path.join(archive_dir, 'RELEASE'),
        dirs_exist_ok=True)

    # Make sure everything in this combo is archived.
    if (ids is None) or (len(ids) == 0):
        _,release_df = exputil.release_df(exp_mod, combo, type='x')
        ids = release_df.index.tolist()
    arc_fnames, archived_out_zips = fetch(exp_mod, combo, ids)

    # We've successfully written the netCDF files.
    # Delete the originals (if they exist to begin with)
    for out_zip in archived_out_zips:
        basepath = out_zip[:-8]
        for suffix in ('.job.err', '.job.log', '.job.out', '.in.zip', '.out.zip'):
            fname = f'{basepath}{suffix}'
            if os.path.exists(fname):
                try:
                    print('Remove ', fname)
                    #os.remove(fname)
                except FileNotFoundError:
                    pass

