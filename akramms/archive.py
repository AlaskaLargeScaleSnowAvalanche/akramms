import shutil,os,re,zipfile
from uafgi.util import shputil

_relRE = re.compile(r'^(.*)_rel\.shp$')
_out_zipRE = re.compile(r'^(.*)_(\d+)\.out\.zip$')
# Status of each avalanche found on disk
OK = 0
NO_IN_ZIP = 1
OVERRUN = 2
NO_OUT_ZIP = 3

error_msgs = {
    NO_IN_ZIP: 'ERROR: No .in.zip for {out_zip}',
    OVERRUN: 'ERROR: Domain overrun in {out_zip}',
    NO_OUT_ZIP: 'ERROR: No .out.zip for Avalanche ID {id}',
}


def archive_scene(scene_dir, archive_dir):
    """Copies everything except the avalanches from a raw scene_dir to an archived archive_dir
    scene_dir:
        Raw scene directory.  Eg:
            ~/prj/ak/ak_ccsm_1981_1990_lapse_For_30/x-113-026
    archive_dir:
        Directory where to archive. Eg:
            ~/prj/ak/ak_ccsm_1981_1990_lapse_For_30/a-113-026
    """

    print('xxxxx ', archive_dir)
    os.makedirs(archive_dir, exist_ok=True)

    # Copy a few top-level files
    for leaf in ('scene.nc', 'scene.cdl', 'crs.prj'):
        shutil.copy2(os.path.join(scene_dir, leaf), archive_dir)

    # Copy the lists PRA polygons
    shutil.copytree(os.path.join(scene_dir, 'RELEASE'), os.path.join(archive_dir, 'RELEASE'))

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
    # IDs.  If all avalnches have completed successfully, and there is
    # now "pollution" of other runs in this directory, the list should
    # be the same as shp_ids
    out_zips = dict()
    for out_zip in glob.iglob(os.path.join(scene_dir, 'CHUNKS', '*', '*', '*', '*', '*.out.zip')):

        # Get the avalanche ID
        out_zip_leaf = os.path.split(out_zip)[1]
        match = _out_zipRE.match(out_zip_leaf)
        id = int(match(2))

        # Make sure .in.zip exists
        in_zip = out_zip[:-8] + '.in.zip'
        if not os.path.exists(in_zip):
            out_zips[id] = (NO_IN_ZIP, out_zip)
            continue

        # Make sure the avalanche didn't overrun the domain.
        with zipfile.ZipFile(out_zip, 'r') as in_zip:
            arcnames = [os.path.split(x)[1] for x in in_zip.namelist()]
        if any(x.endswith('.out.overrun') for x in arcnames):
            out_zips[od] = (OVERRUN, out_zip)
            continue

        # Add as archivable ID
        aval_ids[id] = (OK, out_zip)

    # Go through our avalanches by ID
    for id in shp_ids:
        status,out_zip = aval_ids.get(id, (NO_OUT_ZIP, None))
        if status == OK:
            out_nc = os.path.join(archive_dir, 'a-{:05d}.nc'.format(id))
            print(f'archive {out_zip} -> {out_nc}')
        else:
            print(error_msgs[status].format(id=id, out_zip=out_zip))


def main():
    scene_dir = '/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/x-113-026'
    archive_dir = '/home/efischer/prj/ak/ak_ccsm_1981_1990_lapse_For_30/a-113-026'
    archive_scene(scene_dir, archive_dir)
main()
