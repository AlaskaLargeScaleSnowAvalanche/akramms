import shutil,os,re,zipfile,glob
from uafgi.util import shputil
from akramms import ncaval,r_ramms
import traceback

_relRE = re.compile(r'^(.*)_rel\.shp$')
_out_zipRE = re.compile(r'^(.*)_(\d+)\.out\.zip$')
# Status of each avalanche found on disk
OK = 0
NO_IN_ZIP = 1
OVERRUN = 2
NO_OUT_ZIP = 3
UNKNOWN_ERROR = 4
MAX_STATUS = 4

error_msgs = {
    NO_IN_ZIP: 'ERROR: No .in.zip for Avalanche IDs: {ids}',
    OVERRUN: 'ERROR: Domain overruns for Avalanche IDs: {ids}',
    NO_OUT_ZIP: 'ERROR: No .out.zip for Avalanche IDs {ids}',
    UNKNOWN_ERROR: 'Unknown error archiving: {ids}',
}


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
    out_zips = dict()
    for out_zip in glob.iglob(os.path.join(scene_dir, 'CHUNKS', '*', '*', '*', '*', '*.out.zip')):

        # If HTCondor is in the middle of writing the .out.zip file,
        # it will have zero length.
        if not r_ramms.file_is_good(out_zip):
            continue

        # Get the avalanche ID
        out_zip_leaf = os.path.split(out_zip)[1]
        match = _out_zipRE.match(out_zip_leaf)
        id = int(match.group(2))

        # Make sure .in.zip exists
        in_zip = out_zip[:-8] + '.in.zip'
        if not os.path.exists(in_zip):
            out_zips[id] = (NO_IN_ZIP, out_zip)
            continue

        # Make sure the avalanche didn't overrun the domain.
        with zipfile.ZipFile(out_zip, 'r') as in_zip:
            arcnames = [os.path.split(x)[1] for x in in_zip.namelist()]
        if any(x.endswith('.out.overrun') for x in arcnames):
            out_zips[id] = (OVERRUN, out_zip)
            continue

        # Add as archivable ID
        out_zips[id] = (OK, out_zip)

    todels = list()

    # Go through our avalanches by ID
    errors_by_status = dict((i,list()) for i in range(MAX_STATUS+1))
    for id in shp_ids:
        out_nc = os.path.join(archive_dir, 'aval-{:d}.nc'.format(id))

        # Only rewrite out_nc if it doesn't exist
#TODO: Check file timestamps
        status,out_zip = out_zips.get(id, (NO_OUT_ZIP, None))
        print('yyy ', id, status, out_zip)
        basepath = None if out_zip is None else out_zip[:-8]

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
