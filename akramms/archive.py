import shutil,os,re,zipfile,glob,datetime,time,subprocess
import netCDF4
from uafgi.util import shputil,ncutil
from akramms import ncaval,r_ramms,config
from akramms import avalparse
from akramms.util import exputil
import traceback

#_out_zipRE = re.compile(r'^(.*)_(\d+)\.out\.zip$')
# Status of each avalanche found on disk
OK = 0                # Implies .out.zip
NO_IN_ZIP = 1
OVERRUN = 2
NO_OUT_ZIP = 3
UNKNOWN_ERROR = 4
ARCHIVED = 5        # It's a .nc file
MAX_STATUS = 5

error_msgs = {
    NO_IN_ZIP: 'ERROR: No .in.zip for Avalanche IDs: {ids}',
    OVERRUN: 'ERROR: Domain overruns for Avalanche IDs: {ids}',
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

    # Make sure the avalanche didn't overrun the domain.
    with zipfile.ZipFile(basename+'.out.zip', 'r') as in_zip:
        arcnames = [os.path.split(x)[1] for x in in_zip.namelist()]
    if any(x.endswith('.out.overrun') for x in arcnames):
        return OVERRUN

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
def fetch(exp_mod, combo, ids, ok_statuses={OK,OVERRUN}):
    """Returns the names of archive files, based on a particular combo
    and list of IDs within that combo.  Archives the avalanches if needed.

    exp_mod:
        Main experiment info
    combo:
        Describes which RAMMS run within the experiment
    id:
        Which avalanche within the RAMMS run we wish to fetch
    returns: arc_fnames, archived_out_zips
        arc_fnames: [arc_fname, ...]
            Names of files found
        archived_out_zips: [xxx.out.zip, ...]
            Original files that can be deleted now.
    """

    # List all the output .out.zip files in an experiment
    x_dir = exp_mod.combo_to_scene_subdir(combo, type='x')
    out_zips = dict()    
    for out_zip in glob.iglob(os.path.join(x_dir, 'CHUNKS', '*', '*', '*', '*', '*.out.zip')):
        match = avalparse.out_zipRE.match(os.path.basename(out_zip))
        sizecat = match.group(1)
        id = int(match.group(2))
        out_zips[id] = (out_zip, sizecat)    # full-pathname, sizecat


    # List all the existing archive .nc files
    arc_dir = exp_mod.combo_to_scene_subdir(combo, type='arc')
    ncs = dict()
    if os.path.isdir(arc_dir):
        for name in os.listdir(arc_dir):
            match = avalparse.avalRE.match(name)
            if match is not None:
                ncs[int(match.group(2))] = (name, match.group(1))    # leaf-name, sizecat


    # Information from the RELEASE shpaefile
    release_file,release_df = exputil.release_df(exp_mod, combo)

    arc_fnames = list()
    archived_out_zips = list()
    first = True
    for id in ids:
        # -------- Get name and modification time of original .out.zip file
        try:
            out_zip,ozip_sizecat = out_zips[id]
            # Make sure the out.zip file is complete / ready to archive
            status = out_zip_status(out_zip)
            if status in ok_statuses:
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
        if arc_mtime > out_zip_mtime:
            # Arc file exists and is up-to-date, DO NOT regenerate
            arc_fnames.append(arc_fname)
            if id in out_zips:
                # Add to our delete list...
                archived_out_zips.append(out_zip)
        elif out_zip_mtime > 0:
            # .out.zip file is OK, so let's regenerate

            arc_dir = exp_mod.combo_to_scene_subdir(combo, type='arc')
            arc_fname = os.path.join(
                arc_dir,
                f'aval-{ozip_sizecat}-{id}.nc')

            if first:
                os.makedirs(arc_dir, exist_ok=True)
                first = False

            # --------- Write the full NetCDF file
            with netCDF4.Dataset(arc_fname, 'w') as ncout:
                ncaval.ramms_to_nc0(out_zip, ncout)

                # Add info from the RELEASE file
                ncv = ncout.createVariable('release_shp', 'i')
                ncv.description = 'Attributes from the RELEASE shapefile used to set up this avalanche'
                row = release_df.loc[id]
                for aname,val in row.items():
                    setattr(ncv, aname, val)

                # Add provenance info
                ncv = ncout.createVariable('provenance', 'i')
                ncv.exp_mod = exp_mod.name
                ncv.created_by = os.getlogin()
                ncv.release_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime(release_file)).isoformat()
                ncv.avalanche_timestamp = datetime.datetime.fromtimestamp(out_zip_mtime).isoformat()
                ncv.archive_timestamp = datetime.datetime.now().isoformat()
                ncv.akramms_commit = _git_commit(os.path.join(config.HARNESS, 'akramms'))
                ncv.uafgi_commit = _git_commit(os.path.join(config.HARNESS, 'uafgi'))

                # Add info from scene that created this avalanche
                with netCDF4.Dataset(os.path.join(x_dir, 'scene.nc')) as ncin:
                    schema = ncutil.Schema(ncin)
                    grp = ncout.createGroup('scene_nc')
                    schema.create(grp)
                    schema.copy(ncin, grp)

    


            # ----------------------------------------


            arc_fnames.append(arc_fname)
            archived_out_zips.append(out_zip)
        else:
            # Neither file exists, that's an error.
            arc_fnames.append(None)

    return arc_fnames, archived_out_zips

# -----------------------------------------------------------------
def archive_combo(exp_mod, combo, ids=None, ok_statuses={OK,OVERRUN}):
    """Archives all IDs in a combo.
    Returns: {id: arc_fname}
    """

    scene_dir = exp_mod.combo_to_scene_subdir(combo, type='x')
    archive_dir = exp_mod.combo_to_scene_subdir(combo, type='arc')

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
    arc_fnames, archived_out_zips = fetch(exp_mod, combo, ids, ok_statuses=ok_statuses)

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

#    # Print the errors
#    for status,ids in errors_by_status.items():
#        if len(ids) > 0:
#            print(error_msgs[status].format(ids=ids))


#def main():
#    scene_dir = '/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/x-113-045'
#    archive_dir = '/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/arc-113-045'
#    archive_scene(scene_dir, archive_dir)


def main():
    from akramms.experiment import ak
    
    combo = ak.Combo('ccsm', 1981, 1990, 'lapse', 'For', 30, 113, 45)
    fetch(ak, combo, [2058])

#main()
