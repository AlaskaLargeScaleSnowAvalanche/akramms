import shutil,os,re,zipfile,glob
from uafgi.util import shputil
from akramms import ncaval,r_ramms
import traceback

_relRE = re.compile(r'^(.*)_rel\.shp$')
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
def fetch(exp_mod, combo, ids, ok_statuses={OK,OVERRUN}):
    """Returns the names of archive files, based on a particular combo
    and list of IDs within that combo.  Archives the avalanches if needed.

    exp_mod:
        Main experiment info
    combo:
        Describes which RAMMS run within the experiment
    id:
        Which avalanche within the RAMMS run
    """

    # List all the output .out.zip files in an experiment
    x_dir = exp_mod.combo_to_scene_subdir(combo, type='x')
    out_zips = dict()    
    for out_zip in glob.iglob(os.path.join(x_dir, 'CHUNKS', '*', '*', '*', '*', '*.out.zip')):
        match = exputil.out_zipRE.match(out_zip)
        sizecat = match.group(1)
        id = int(match.group(2))
        out_zips[id] = (out_zip, sizecat)    # full-pathname, sizecat


    # List all the existing archive .nc files
    arc_dir = exp_mod.combo_to_scene_subdir(combo, type='arc')
    ncs = dict()
    for name in os.listdir(arc_dir):
        match = exputil.avalRE.match(name)
        if match is not None:
            ncs[int(match.group(2))] = (name, match.group(1))    # leaf-name, sizecat


    arc_fnames = list()
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
        else:
            arc_mtime = -1.0

        # ------- Reported sizecats must be the same
        assert arc_sizecat == ozip_sizecat

        # -------- Decide whether we need to regenerate
        if arc_mtime > out_zip_mtime:
            # Arc file exists and is up-to-date, DO NOT regenerate
            arc_fnames.append(arc_fname)
            if id in out_zips:
                # Add to our delete list...
                archived_out_zips.append(out_zip)
        elif out_zip_mtime > 0:
            # .out.zip file is OK, so let's regenerate

            arc_fname = os.path.join(
                exp_mod.combo_to_scene_subdir(combo, type='arc'),
                f'aval-{ozip_sizecat}-{id}.nc')

            if first:
                os.makedirs(archive_dir, exist_ok=True)
                first = False
            ramms_to_nc0(out_zip, arc_fname)
            arc_fnames.append(arc_fname)
            archived_out_zips.append(out_zip)
        else:
            # Neither file exists, that's an error.
            arc_fnames.append(None)

    return arc_fnames, archived_out_zips

# -----------------------------------------------------------------
def ids_in_combo(exp_mod, combo):
    """Read the RELEASE files to determine which avalanche IDs are
    involved in a combo."""

    # Look in RELEASE-dir shapefiles to determine theoretical set Avalanche IDs
    # (By looking here, we avoid picking up random junk)
    shp_ids = list()
    for leaf in os.listdir(os.path.join(scene_dir, 'RELEASE')):
        match = _relRE.match(leaf)
        if match is not None:
            df = shputil.read_df(
                os.path.join(scene_dir, 'RELEASE', leaf), read_shapes=False)
            shp_ids += df['Id'].tolist()

    return shp_ids
# -----------------------------------------------------------------
def archive_combo(exp_mod, combo, ok_statuses={OK,OVERRUN}):
    """Archives all IDs in a combo.
    Returns: {id: arc_fname}
    """

    scene_dir = exp_mod.combo_to_scene_subdir(combo, type='x')
    archive_dir = exp_mod.combo_to_scene_subdir(combo, type='arc')

    # Copy a few top-level files
    os.makedirs(archive_dir, exist_ok=True)
    for leaf in ('scene.nc', 'scene.cdl', 'crs.prj'):
        shutil.copy2(os.path.join(scene_dir, leaf), archive_dir)

    # Copy the lists PRA polygons
    shutil.copytree(
        os.path.join(scene_dir, 'RELEASE'),
        os.path.join(archive_dir, 'RELEASE'),
        dirs_exist_ok=True)

    # Make sure everything in this combo is archived.
    shp_ids = ids_in_combo(exp_mod, combo)
    arc_fnames, archived_out_zips = fetch(exp_mod, combo, shp_ids, ok_statuses=ok_statuses)

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

    # Print the errors
    for status,ids in errors_by_status.items():
        if len(ids) > 0:
            print(error_msgs[status].format(ids=ids))


#def main():
#    scene_dir = '/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/x-113-045'
#    archive_dir = '/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/arc-113-045'
#    archive_scene(scene_dir, archive_dir)


def main():
    from akramms import e_alaska
    
    combo = e_alaska.Combo('ccsm', 1981, 1990, 'lapse', 'For', 30, 113, 45)
    fetch(e_alaska, combo, [2058])

main()
