import shutil,os,re,zipfile,glob
from uafgi.util import shputil
from akramms import ncaval,r_ramms
import traceback

_relRE = re.compile(r'^(.*)_rel\.shp$')
_out_zipRE = re.compile(r'^(.*)_(\d+)\.out\.zip$')
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
def getmtime(fname):
    """Returns modification time of a file; or -1 if it doesn't exist."""
    if os.path.exists(fname):
        return os.path.getmtime(fname)
    else:
       return -1.0

idRE = re.compile(r'.*_(\d+)\.out\.zip$')
def extract_id(out_zip):
    """Returns the avalanche ID from a .out.zip filename"""
    return int(idRE.match(out_zip).group(1))

# -----------------------------------------------------------------
def arc_files(exp_mod, combo, ids, ok_statuses={OK,OVERRUN}):
    """Returns the names of archive files, based on a particular combo
    and list of IDs within that combo.

    exp_mod:
        Main experiment info
    combo:
        Describes which RAMMS run within the experiment
    id:
        Which avalanche within the RAMMS run

    """


    # List all the output files in an experiment
    x_dir = exp_mod.combo_to_scene_subdir(combo, type='x')
    out_zips = {extract_id(x) : x
        for x in glob.iglob(os.path.join(x_dir, 'CHUNKS', '*', '*', '*', '*', '*.out.zip'))}

    arc_fnames = list()
    for id in ids:
        # ------- Get name and modification time of archive .nc file
        arc_fname = os.path.join(
            exp_mod.combo_to_scene_subdir(combo, type='arc'),
            f'aval-{id}.nc')
        if os.path.exists(arc_fname):
            arc_mtime = os.path.getmtime(arc_fname)
        else:
            arc_mtime = -1.0

        # -------- Get name and modification time of original .out.zip file
        try:
            out_zip = out_zips[id]
            # Make sure the out.zip file is complete / ready to archive
            status = out_zip_status(out_zip)
            if status in ok_statuses:
                out_zip_mtime = os.path.getmtime(out_zip)
            else:
                # Act like the .out.zip file does not exist
                out_zip_mtime = -1.0
        except KeyError:
            out_zip_mtime = -1.0

        # -------- Decide whether we need to regenerate
        if arc_mtime > out_zip_mtime:
            # Arc file exists and is up-to-date, DO NOT regenerate
            arc_fnames.append(arc_fname)
        elif out_zip_mtime > 0:
            # .out.zip file is OK, so let's regenerate
           ramms_to_nc0(basename, arc_fname)
            arc_fnames.append(arc_fname)
        else:
            # Neither file exists, that's an error.
            arc_fnames.append(None)

    return arc_fnames




# -----------------------------------------------------------------


def archive_scene(scene_dir, archive_dir):
    """Copies everything except the avalanches from a raw scene_dir to an archived archive_dir
    scene_dir:
        Raw scene directory.  Eg:
            ~/prj/ak/ak_ccsm_1981_1990_lapse_For_30/x-113-026
    archive_dir:
        Directory where to archive. Eg:
            ~/prj/ak/ak_ccsm_1981_1990_lapse_For_30/arc-113-026
    """

    os.makedirs(archive_dir, exist_ok=True)

    # Copy a few top-level files
    for leaf in ('scene.nc', 'scene.cdl', 'crs.prj'):
        shutil.copy2(os.path.join(scene_dir, leaf), archive_dir)

    # Copy the lists PRA polygons
    shutil.copytree(
        os.path.join(scene_dir, 'RELEASE'),
        os.path.join(archive_dir, 'RELEASE'),
        dirs_exist_ok=True)

    # Look in RELEASE-dir shapefiles to determine theoretical set Avalanche IDs
    # (By looking here, we avoid picking up random junk)
    shp_ids = list()
    for leaf in os.listdir(os.path.join(scene_dir, 'RELEASE')):
        match = _relRE.match(leaf)
        if match is not None:
            df = shputil.read_df(
                os.path.join(scene_dir, 'RELEASE', leaf), read_shapes=False)
            shp_ids += df['Id'].tolist()

    # list of errors
    no_in_zips = dict()
    overruns = ()

    # Look for .out.zip files for list of actual available Avalanche
    # IDs.  If all avalanches have completed successfully, and there is
    # now "pollution" of other runs in this directory, the list should
    # be the same as shp_ids
    out_zips = {x.id: (x.status, x.fname) for x in avquery.list_unarchived(scene_dir)}

    todels = list()

    # Go through our avalanches by ID
    errors_by_status = dict((i,list()) for i in range(MAX_STATUS+1))
    for id in shp_ids:
        out_nc = os.path.join(archive_dir, 'aval-{:d}.nc'.format(id))

        # Only rewrite out_nc if it doesn't exist
#TODO: Check file timestamps
        status,out_zip = out_zips.get(id, (NO_OUT_ZIP, None))
        print('yyy ', id, status, out_zip)
        basepath = None if out_zip is None else out_zip[:-8]   # ..../.../.../.../xxxxx.out.zip

        if os.path.exists(out_nc):
            # If the archive already exists, we can just delete the old
            # files (if they are there) and move on.
            if basepath is not None:
                todels.append(basepath)
        elif status == OK:
            # The archive does not exist, we will have to create it if we can.
            print(f'... {out_nc}')
            try:
                ncaval.ramms_to_nc0(basepath, out_nc)
                todels.append(basepath)
            except Exception as e:
                traceback.print_exception(e)
                errors_by_status[UNKNOWN_ERROR].append(id)
        else:
            errors_by_status[status].append(id)

    # We've successfully written the netCDF files.
    # Delete the originals (if they exist to begin with)
    for basepath in todels:
        if basepath is not None:
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


def main():
    scene_dir = '/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/x-113-045'
    archive_dir = '/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/arc-113-045'
    archive_scene(scene_dir, archive_dir)
main()
