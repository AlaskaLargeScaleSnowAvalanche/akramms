import os,sys,shutil,multiprocessing,pickle,zipfile,re,pathlib,time,glob,subprocess
import multiprocessing.pool
import setuptools.sandbox
import pandas as pd
from uafgi.util import make,shputil,gdalutil,ioutil
from akramms import config,params,process_tree,joblib,parse,file_info,parse,resolve,complete,level
from akramms.util import paramutil,harnutil,rammsutil
import ramms_lshm

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
    dir = dom_file[:dom_file.rindex('/')+1]

    # Blank out all occurrences of that dir
    av3_str = av2_str.replace(dir, '')

    # Go one dir up
    dir = dir[:-1]    # Remove trailing slash
    dir = dir[:dir.rindex('/')]
#    print(f'dir "{dir}"')
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
        zip_file_tmp = crf.avalanche_dir / f'{base}.in.zip.tmp'

        files = [crf.avalanche_dir / f'{base}{ext}' for ext in _izip_exts]
        arcnames = [f'{base}{ext}' for ext in _izip_exts]
#        arcnames[-1] = f'{base}.v1.dom'    # First of many .dom files

        if (not os.path.exists(crf.avalanche_dir / f'{base}.in.zip')) and \
            all(file_info.is_file_good(x) for x in files):

#            print(f'Compressing {zip_file}')

            # Compress Avalanche intput files into a Zipfile
            with zipfile.ZipFile(
                zip_file_tmp, 'w', compression=zipfile.ZIP_DEFLATED) \
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

            # Atomic create
            os.rename(zip_file_tmp, zip_file)

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
#def run_if_remote(control_file, *args, **kwargs):
#    """Runs remotely, but ONLY if a control file does not yet exist"""
#    if not os.path.exists(control_file):
#        harnutil.run_remote(*args, **kwargs)

def _av2_to_xycoord(hconfig, av2, xycoord):
    """Job to run in parallel, to generate an xycoord file"""
    cmd = [str(hconfig.rammscore_exe), str(av2), '/', 'write_xy']
#    print(' '.join(str(x) for x in cmd))
    if False:
        time.sleep(3)    # DEBUG
    else:
        try:
            subprocess.run(cmd, check=True)
        except Exception:
            # Remove the output file if something went wrong, for example user pressed Ctrl-C
            try:
                os.remove(xycoord)
            except FileNotFoundError:
                pass

    print('.', end='')
    sys.stdout.flush()

_av2RE = re.compile(r'(.*_(\d+))\.av2')
def write_xycoords(hconfig, chunkdir, ncpu=1, check_timestamps=True):
    """
    ncpu:
        Degree of (threaded) parallelism to use
    """

    # Generate xy-coord files
    t0 = time.time()
    print('    XY-COORD FILES (Python):')
    print('    ', end='')

    # Determine the .av2 files that need to be turned into .xycoord
    av2s = list()
    for _av2 in glob.glob(str(chunkdir / 'RESULTS/*/*/*.av2')):
        av2 = pathlib.Path(_av2)
        leaf = av2.parts[-1]

        # Filter out bogus .av2 file like: c-T-00089For_10m_10T_0.av2
        # TODO: It would be more "correct" to read the _rel.shp file instead.
        match = _av2RE.match(leaf)
        if not match:
            continue
        if int(match.group(2)) == 0:
            file_xyz = av2.parents[0] / (match.group(1) + '.xyz')
            if not os.path.isfile(file_xyz):
                continue

        xycoord = av2.parents[0] / (leaf.split('.',1)[0] + '.xy-coord')

        if ioutil.needs_regen([xycoord], [av2], check_timestamps=check_timestamps):
            av2s.append((av2,xycoord))

    # Run the jobs in parallel, and collect errors
    pool = multiprocessing.pool.ThreadPool(processes=ncpu)

    errs = list()
    jobs=[pool.apply_async(_av2_to_xycoord, args=(hconfig, av2, xycoord)) for av2,xycoords in av2s]
    for (av2,xycoord),job in zip(av2s,jobs):
        try:
            job.get()    # Get return value, we throw it away
        except Exception as exp:
            errs.append(f"Error for file {av2}: {str(exp)}")
    t1 = time.time()
    print('DONE')
    print(f'    - Elapsed time (xy-coord files): {(t1-t0):0.1f} s')
    if len(errs) > 0:
        for err in errs:
            print(err, file=sys.stderr)
#        raise exp
        raise ValueError('At least one process failed')




def run_chunk(release_file, crf, gridI, at_front=False, submit=False, condor_priority=0):
    done_output = chunk_control_file(crf)

    # Copy files from previous RAMMS Stage 1, to speed things up
    tmap = tiffmap(crf)
    for fname0,fname1 in tmap:
        if (not os.path.exists(fname0)) and os.path.exists(fname1):
            dir0 = os.path.dirname(fname0)
            os.makedirs(dir0, exist_ok=True)
            shutil.copy(fname1, fname0)

#    chunk_dir_rel = config.roots.relpath(crf.chunk_dir)
#    chunk_dir_path = config.roots_w.syspath(chunk_dir_rel, bash=True)
#    cmd = ['sh', 
#        config.roots_w.join('HARNESS', 'akramms', 'sh', 'run_ramms.sh', bash=True),
#        '--ramms-version', config.ramms_version,
#        chunk_dir_path, '1']    # '1'=stage 1
#
#    # RAMMS Stage 1 accepts inputs on stdin
#    # rammsdist.run_on_windows_stage() calls read_inputs()
#    dynamic_outputs = list()
#
#    # We don't need inputs anymore for run_remote; (but there MUST be
#    # at least one input for RAMMS Windows interface to work)
#    inputs = [release_file]
#
    EXE_EXT = '.exe' if os.name=='nt' else ''
    hconfig = ramms_lshm.Config(
        idl_exe=pathlib.Path(os.environ['IDL_DIR']) / 'bin' / f'idl{EXE_EXT}',
        ramms_lshm_sav = config.roots['HARNESS'] / 'lshm' / 'build/ramms_lshm.sav',
        rammscore_exe = config.roots['HARNESS'] / 'rammscore' / f'build/ramms_aval_LHM{EXE_EXT}')


    print(f'------------- RAMMS Phase 0: {crf.chunk_dir}')
#    harnutil.run_queued('idl',
#        ramms_lshm.run_phase,
#        hconfig, crf.chunk_dir, 0,
#        at_front=False)
    ramms_lshm.run_phase(
        hconfig, crf.chunk_dir, 0)
#        at_front=False)


    print(f'------------- XY-COORD Files: {crf.chunk_dir}')
    write_xycoords(hconfig, crf.chunk_dir, ncpu=config.ramms_ncpu, check_timestamps=True)

    print(f'------------- RAMMS Phase 1: {crf.chunk_dir}')
#    harnutil.run_queued('idl',
#        ramms_lshm.run_phase,
#        hconfig, crf.chunk_dir, 1,
#        at_front=False)

    ramms_lshm.run_phase(
        hconfig, crf.chunk_dir, 1)
#        at_front=False)

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
    df = shputil.read_df_noshapes(release_file)
    #df = shputil.read_df(release_file, read_shapes=False)
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

        # Don't stop the show here.  We can figure out later on that things are missing and act appropriately.
        # raise ValueError('Missing avalanche input files')


    # Submit the individual avalanche runs immediately so we can
    # get going while preparing more RAMMS directories.
    if submit:

        parseds = [parse._parse_chunk_releasefile(release_file)]
        akdf = resolve.resolve_to(parseds, 'id', stage='in', realized=True)
        joblib.submit_jobs(akdf, condor_priority=condor_priority)

    # Write output files
    done_output = chunk_control_file(crf)
    os.makedirs(os.path.dirname(done_output), exist_ok=True)
    with open(done_output, 'w') as out:
        out.write('Finished RAMMS Stage 1\n')


#    return dynamic_outputs

# -----------------------------------------------------------------
def run_combo(scene_dir, dem_file, submit=True):
    
    df = level.scenedir_to_chunknames(scene_dir)    # pra_size, chunkid, name
    df = df.sort_values('name')

    gridI = gdalutil.read_grid(dem_file)
    for tup in df.itertuples(index=False):
#        print('xxxxxxxxxx ', tup)
#        continue

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
        run_chunk(release_file, crf, gridI, submit=submit)

    # Don't do this because there might be overruns.
    # Finished with all chunks, mark it!
    with open(combo_control_file(scene_dir), 'w') as out:
        out.write('Done running initial RAMMS Stage 1 for all chunks in the combo (not including overruns).\n')
# -----------------------------------------------------------------
def releasefile_rule(release_file, dem_file, inputs, dry_run=False, at_front=False, submit=False, condor_priority=0):
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
    condor_priority:
        Priority to assign to HTCondor jobs
    """

#    done_output = crf.scene_dir / 'ramms_stage1' / f'{crf.chunk_name}.txt'
    crf = file_info.parse_chunk_release_file(release_file)
    done_output = chunk_control_file(crf)

    def action(tdir):
        crf = file_info.parse_chunk_release_file(release_file)
        gridI = gdalutil.read_grid(dem_file)

        # Avoid recomputing unnecessarily
        if not os.path.exists(chunk_control_file(crf)):
            run_chunk(release_file, crf, gridI, at_front=at_front, submit=submit, condor_priority=condor_priority)

    return make.Rule(action, inputs, [done_output])

# --------------------------------------------------------
def combo_rule(scene_dir, dem_file, inputs, dry_run=False, submit=False):

    done_output = combo_control_file(scene_dir)

    def action(tdir):
        run_combo(scene_dir, dem_file, submit=config.auto_submit)

    return make.Rule(action, inputs, [done_output])

# --------------------------------------------------------
