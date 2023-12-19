import os,sys,shutil,multiprocessing,pickle,zipfile,re
import setuptools.sandbox
import pandas as pd
from uafgi.util import make,shputil,gdalutil
from akramms import config,params,process_tree,joblib,parse,file_info,parse,resolve,complete,level
from akramms.util import paramutil,harnutil,rammsutil

"""Rules for RAMMS Stage 1 (with auto submit to Stage 2)"""

__all__ = ('rule',)

# -------------------------------------------------------------
def tiffmap(crf):

    """Returns a mapping between a parsed RAMMS dir vs. "permanent"
    names for .tif files that can be reused for different chunks in
    RAMMS Stage 1.  After RAMMS stage 1, files will be copied from the
    chunk to their general location, as appropriate.

    crf:
        Parsed release file name of one chunk
    Returns: [(fname_chunk, fname_general), ...]

    """

    # Parsed release file name of the dummy overall run used to create
    # reusable names for the TIF files.
    scene_args = params.load(crf.scene_dir)

    # Used to determine which chunks should re-use with files
    sceneslope = f'{crf.scene_name}-{crf.For}-{crf.resolution}m'

    map = [
        # -------------- Items for all sub-directories of the slope_dir
        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/slope.tif
        (crf.slope_dir / 'slope.tif',
            crf.scene_dir / 'SLOPE_TIF' / sceneslope / 'slope.tif'),

        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/curvidl.tif
        (crf.slope_dir / 'curvidl.tif',
            crf.scene_dir / 'SLOPE_TIF' / sceneslope / 'curvidl.tif'),

        # -------------- Items for each subdir
        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/juneau100000For_5m_M30_xi.tif
        (crf.slope_dir / f'{crf.slope_name}_{crf.pra_size}{crf.return_period}_xi.tif',
            crf.scene_dir / 'SLOPE_TIF' / sceneslope / f'{sceneslope}_{crf.pra_size}{crf.return_period}_xi.tif'),

        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/juneau100000For_5m_M30_mu.tif
        (crf.slope_dir / f'{crf.slope_name}_{crf.pra_size}{crf.return_period}_mu.tif',
            crf.scene_dir / 'SLOPE_TIF' / sceneslope / f'{sceneslope}_{crf.pra_size}{crf.return_period}_mu.tif'),
    ]

    return map

# ----------------------------------------
pathRE = re.compile(r'Domain\s+[^\s]*\s+([^\s]*)\s*', re.MULTILINE)
def av2_to_av3(av2_str):
    """Rewrite .av2 file to avoid absolute paths, and convert to
    forward slash.  This prepares it to run in a Docker container."""

    # Figure out directory to blank out (as a string)
    match = pathRE.search(av2_str)
    dom_file = match.group(1)
    dir = dom_file[:dom_file.rindex('\\')+1]

    # Blank out all occurrences of that dir
    av3_str = av2_str.replace(dir, '')

    # Go one dir up
    dir = dir[:-1]    # Remove trailing backslash
    dir = dir[:dir.rindex('\\')]
    print(f'dir "{dir}"')
    av3_str = av3_str.replace(dir, '..')

    return av3_str
# ----------------------------------------

_izip_exts = ['.xyz', '.xy-coord', '.var', '.rel', '.dom']  # .dom MUST be last
def compress_avalanche_inputs(crf, gridI, ids):
    """Puts all avalanche inputs into a single Zip file."""
    gridI_pik = pickle.dumps(gridI)
    for id in ids:
#        base = os.path.join(crf.avalanche_dir, f'{crf.ramms_name}')
        base = f'{crf.slope_name}_{crf.avalanche_name}_{id}'

        zip_file = crf.avalanche_dir / f'{base}.in.zip'

        files = [crf.avalanche_dir / f'{base}{ext}' for ext in _izip_exts]
        arcnames = [f'{base}{ext}' for ext in _izip_exts]
        arcnames[-1] = f'{base}.v1.dom'    # First of many .dom files

        if (not os.path.exists(crf.avalanche_dir / f'{base}.in.zip')) and \
            all(file_info.is_file_good(x) for x in files):

            print(f'Compressing {zip_file}')

            # Compress Avalanche intput files into a Zipfile
            with zipfile.ZipFile(
                zip_file, 'w', compression=zipfile.ZIP_DEFLATED) \
                as izip:

                # Write the grid info
                izip.writestr('grid.pik', gridI_pik)

                # Copy files
                for file,arcname in zip(files,arcnames):
                    izip.write(file, arcname=arcname)

                # Write the .av3 files based on the .av2 file
                arcname = f'{base}.av3'
                av2_file = crf.avalanche_dir / f'{base}.av2'
                files.append(av2_file)
                with open(av2_file, 'r') as fin:
                    av3_str = av2_to_av3(fin.read())
                izip.writestr(arcname, av3_str)

            # Remove old files
            for file in files:
                os.remove(file)

def striped_chunks(l, n):
    """Yield n number of striped chunks from l."""
    # https://stackoverflow.com/questions/24483182/python-split-list-into-n-chunks
    for i in range(0, n):
        yield l[i::n]
# -----------------------------------------------------------------
def chunk_control_file(crf):
    return crf.scene_dir / 'ramms_stage1' / f'{crf.chunk_name}.txt'

def combo_control_file(scene_dir):
    return scene_dir / 'ramms_stage1.txt'

# -----------------------------------------------------------------
def run_chunk(crf, gridI, submit=False):
    done_output = chunk_control_file(crf)

#    crf = file_info.parse_chunk_release_file(release_file)
    # ---------------------------------------------------------
    # From former rammsdir rule

    # ---------------------------------------------------------

    # Copy files from previous RAMMS Stage 1, to speed things up
    tmap = tiffmap(crf)
    for fname0,fname1 in tmap:
        if (not os.path.exists(fname0)) and os.path.exists(fname1):
            dir0 = os.path.dirname(fname0)
            os.makedirs(dir0, exist_ok=True)
            shutil.copy(fname1, fname0)

    chunk_dir_rel = config.roots.relpath(crf.chunk_dir)
    cmd = ['sh', 
        config.roots_w.join('HARNESS', 'akramms', 'sh', 'run_ramms.sh', bash=True),
        '--ramms-version', config.ramms_version,
        config.roots_w.syspath(chunk_dir_rel, bash=True), '1']    # '1'=stage 1

    # RAMMS Stage 1 accepts inputs on stdin
    # rammsdist.run_on_windows_stage() calls read_inputs()
    dynamic_outputs = list()
    harnutil.run_queued('idl',
        harnutil.run_remote, inputs, cmd, tdir, write_inputs=True)

    # Copy .tif files to be reused by later RAMMS Stage 1
    for fname0,fname1 in tmap:
        dir1 = os.path.dirname(fname1)
        os.makedirs(dir1, exist_ok=True)
        if not os.path.exists(fname1):
            shutil.copy(fname0, fname1)

        # Do NOT remove, we will need for Stage 2 (the .exe file).
        # os.remove(fname0)

    # Obtain raster grid and geotransform info
#    gridI = gdalutil.read_grid(dem_file)

    # Compress Avalanche inputs, ready for Docker container
    df = shputil.read_df(release_file, read_shapes=False)
    all_ids = list(df['Id'])
    procs = list()
    for ids in striped_chunks(all_ids, config.ncpu_compress):
        proc = multiprocessing.Process(
            target=lambda: compress_avalanche_inputs(crf, gridI, ids))
        proc.start()
        procs.append(proc)
    for proc in procs:
        proc.join()

    # Check final outputs
    missing = list()
    avalanche_dir = crf.avalanche_dir
    for id in all_ids:    # Avalanche ID
        in_zip = crf.avalanche_dir / f'{crf.slope_name}_{crf.avalanche_name}_{id}.in.zip'

        if not os.path.exists(in_zip):
            missing.append(in_zip)
    if len(missing) > 0:
        for x in missing:
            print('Missing: ', x)
        raise ValueError('Missing avalanche input files')


    # Submit the individual avalanche runs immediately so we can
    # get going while preparing more RAMMS directories.
    if submit:

        parseds = [parse.parse_chunk_releasefile(release_file)]
        akdf = resolve.resolve_to(parseds, 'id', stage='in', realized=True)
        joblib.submit_jobs(akdf)

    # Write output files
    done_output = chunk_control_file(crf)
    os.makedirs(os.path.dirname(done_output), exist_ok=True)
    with open(done_output, 'w') as out:
        out.write('Finished RAMMS Stage 1\n')


    return dynamic_outputs

# -----------------------------------------------------------------
def run_combo(scene_dir, dem_file):
    
    df = level.scenedir_to_chunknames(scene_dir)    # pra_size, chunkid, name
    gridI = gdalutil.read_grid(dem_file)
    for tup in df.itertuples(index=False):
        chunkdir = scene_dir / 'CHUNKS' / tup.name
        release_file = level.chunkdir_to_releasefile(chunkdir)
        crf = file_info.parse_chunk_release_file(release_file)

        # For debugging
        if crf.pra_size not in config.allowed_pra_sizes:
            continue

        # Avoid recomputing unnecessarily
        if os.path.exists(chunk_control_file(crf)):
            continue

        # OK do it.
        run_chunk(crf, gridI, submit=submit)

    # Don't do this because there might be overruns.
    # Finished with all chunks, mark it!
    with open(combo_control_file(scene_dir)) as out:
        out.write('Done running initial RAMMS Stage 1 for all chunks in the combo (not including overruns).\n')
# -----------------------------------------------------------------
def releasefile_rule(release_file, dem_file, inputs, dry_run=False, submit=False):
    """Runs Stage 1 of RAMMS for one chunk
    (IDL code prepares individual avalanche runs)

    dem_file:
        The name of ANY DEM file pertaining to this chunk.
        It could be the copy (or symlink) of the DEM file inside the chunk dir.
        Alternately, it can just be the DEM file for the AKRAMMS scene overall.
    release_file:
        Name of a release file for the CHUNK you wish to run

    inputs:
        All input files for the RAMMS run (superset of release_files)
    """

#    done_output = crf.scene_dir / 'ramms_stage1' / f'{crf.chunk_name}.txt'
    done_output = chunk_control_file(crf)

    def action(tdir):
        crf = file_info.parse_chunk_release_file(release_file)
        gridI = gdalutil.read_grid(dem_file)

        # Avoid recomputing unnecessarily
        if not os.path.exists(chunk_control_file(crf)):
            run_chunk(crf, gridI, submit=submit)

    return make.Rule(action, inputs, [done_output])

# --------------------------------------------------------
def combo_rule(scene_dir, dem_file, inputs, dry_run=False, submit=False):

    done_output = combo_control_file(scene_dir)

    def action(tdir):
        run_combo(scene_dir, dem_file)

    return make.Rule(action, inputs, [done_output])

# --------------------------------------------------------
