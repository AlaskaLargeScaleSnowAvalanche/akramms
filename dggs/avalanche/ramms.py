import os,subprocess,re,sys,time,itertools,gzip
import contextlib
import itertools, functools,shutil
import numpy as np
import shapely
import htcondor
from dggs.avalanche import avalanche
from dggs.util import harnutil
import dggs.data
from uafgi.util import make,ioutil,shputil

@functools.lru_cache()
def scenario_name(scene_dir, return_period, forest):
    scene_args = avalanche.params.load(scene_dir)
    name = scene_args['name']
    For = 'For' if forest else 'NoFor'
    return f"{name}{return_period}y{For}"


def ramms_dir(scene_dir, *args):
    if len(args) == 1:
        sn = args[0]
    else:
        sn = scenario_name(scene_dir, *args)

    return os.path.join(scene_dir, 'RAMMS', sn)

# --------------------------------------------------------------------
scenario_tpl = \
r"""LSHM    {scenario_name}
MODULE  AVAL
MUXI    VARIABLE
DIR     {remote_ramms_dir}\
DEM     DEM\
SLOPE   SLOPE\
RELEASE RELEASE\
DOMAIN  DOMAIN\
FOREST  FOREST\
NRCPUS  {ncpu}
COHESION {cohesion}
DEBUG   {debug}
CPUS_PRE {ncpu_preprocess}
{test_nr_tpl}KEEP_DATA {keep_data}
ALT_LIM_TOP  {alt_lim_top}
ALT_LIM_LOW  {alt_lim_low}
END
"""

def rammsdir_rule(xramms_dir, xscenario_name, scene_dir, return_period, forest, HARNESS_REMOTE,
    debug=False, alt_lim_top=1500, alt_lim_low=1000, ncpu=8, ncpu_preprocess=4, cohesion=50):

    """Generates the scenario file, which becomes key to running RAMMS.
    HARNESS_REMOTE:
        Location of ~/git on remote Windows machine (parent of akramms/ repo)
    """

    scene_args = avalanche.params.load(scene_dir)
    resolution = scene_args['resolution']
    name = scene_args['name']
    For = 'For' if forest else 'NoFor'

#    xscenario_name = scenario_name(scene_dir, return_period, forest)
#    xramms_dir = ramms_dir(scene_dir, xscenario_name)
    scenario_file = os.path.join(xramms_dir, 'scenario.txt')


    # ---- DEM File
    idem_dir,idem_tif = os.path.split(scene_args['dem_file'])
    idem_stub = idem_tif[:-4]
    links = [
        (os.path.join(idem_dir, f'{idem_stub}.tif'), os.path.join(xramms_dir, 'DEM', f'{name}_{For}_{resolution}m_DEM.tif')),
        (os.path.join(idem_dir, f'{idem_stub}.tfw'), os.path.join(xramms_dir, 'DEM', f'{name}_{For}_{resolution}m_DEM.tfw')),
    ]


    # ---- Forest File
    if forest:
        iforest_dir,iforest_tif = os.path.split(scene_args['forest_file'])
        iforest_stub = iforest_tif[:-4]
        links += [
            (os.path.join(iforest_dir, f'{iforest_stub}.tif'), os.path.join(xramms_dir, 'FOREST', f'{name}_{For}_{resolution}m_forest.tif')),
            (os.path.join(iforest_dir, f'{iforest_stub}.tfw'), os.path.join(xramms_dir, 'FOREST', f'{name}_{For}_{resolution}m_forest.tfw')),
        ]

    def action(tdir):
        # Make symlinks for DEM file, etc.
        for ifile,ofile in links:
            ioutil.setlink(ifile, ofile)
#            if not os.path.exists(ofile):
#                odir = os.path.split(ofile)[0]
#                os.makedirs(odir, exist_ok=True)
#                print('***symlink ifile: {}'.format(ifile))
#                print('***symlink ofile: {}'.format(ofile))
#                os.symlink(ifile, ofile)

        # Create the scenario file
        kwargs = dict()
        kwargs['scenario_name'] = xscenario_name
        kwargs['remote_ramms_dir'] = harnutil.remote_windows_name(xramms_dir, HARNESS_REMOTE)
        kwargs['ncpu'] = str(ncpu)
        kwargs['ncpu_preprocess'] = str(ncpu_preprocess)
        kwargs['cohesion'] = str(cohesion)
        if debug:
            kwargs['debug'] = '1'
            kwargs['keep_data'] = '1'
            kwargs['test_nr_tpl'] = "TEST_NR    20\n"
        else:
            kwargs['debug'] = '0'
            kwargs['keep_data'] = '1'
            kwargs['test_nr_tpl'] = ""
        kwargs['alt_lim_top'] = str(alt_lim_top)
        kwargs['alt_lim_low'] = str(alt_lim_low)

        with open(scenario_file, 'w') as out:
            out.write(scenario_tpl.format(**kwargs))

    inputs = [d[0] for d in links]
    linked_files = [d[1] for d in links]
    outputs = [scenario_file] + linked_files
    print('rammsdir ',outputs)
    return make.Rule(action, inputs, outputs)
# --------------------------------------------------------------------
# sh ~/av/akramms/sh/run_ramms.sh 'c:\Users\efischer\av\prj\juneau1\RAMMS\juneau130yFor'
def ramms_prep_rule(hostname, ramms_dir, release_files, input_files, HARNESS_REMOTE, dry_run=False):
    """
    input_files:
        All input files for the RAMMS run (superset of release_files)
    """

    logfile = os.path.join(ramms_dir, 'RESULTS', 'lshm_rock.log')

    def action(tdir):
        print('Running RAMMS ', ramms_dir)

        # Create remote dir
        cmd = ['ssh', hostname, 'mkdir', '-p', harnutil.remote_windows_name(ramms_dir, HARNESS_REMOTE, bash=True)]
        subprocess.run(cmd, check=True)

        # Sync RAMMS files to remote dir
        harnutil.rsync_files(input_files, hostname, HARNESS_REMOTE, tdir)

        # Run RAMMS
        remote_run_ramms_sh = harnutil.remote_windows_name(
                os.path.join(harnutil.HARNESS, 'akramms', 'sh', 'run_ramms.sh'),
                HARNESS_REMOTE, bash=True)

        cmd = ['ssh', hostname, 'sh', remote_run_ramms_sh,
            harnutil.remote_windows_name(ramms_dir, HARNESS_REMOTE, bash=True)]
        print(' '.join(cmd))
        if not dry_run:
            subprocess.run(cmd, check=True)


        # Get results back
        err = None
        for info in run_infos(release_files):
            run_dir = info['run_dir']

            os.makedirs(run_dir, exist_ok=True)
            print('Retrieving dir ', run_dir)
            cmd = ['rsync', '-avz',
                '{}:{}/'.format(hostname, harnutil.remote_windows_name(run_dir, HARNESS_REMOTE, bash=True)),
                run_dir]
            print(' '.join(cmd))
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as exp:
                err = exp
        if err is not None:
            raise err

        # Get logfile back
        cmd = ['rsync',
            '{}:{}'.format(hostname, harnutil.remote_windows_name(logfile, HARNESS_REMOTE, bash=True)),
            logfile]
        print(' '.join(cmd))
        subprocess.run(cmd, check=True)


    return make.Rule(action,
        input_files,
        [logfile])    # We don't really know the output files yet


# ----------------------------------------------------------
# https://dev.to/teckert/changing-directory-with-a-python-context-manager-2bj8
@contextlib.contextmanager
def set_directory(path):
    """Sets the cwd within the context

    Args:
        path (Path): The path to the cwd

    Yields:
        None

    """

    origin = Path().absolute()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)

def configure_ramms_distro(ramms_distro):
    """Make sure the RAMMS distribution has been fiddled properly"""

    bin = os.path.join(ramms_distro, 'bin')
    with set_directory(bin):
        if not os.path.exists('ramms_aval_LHM_orig.exe'):
            # Need to move
            print('Moving to ramms_aval_LHM_orig.exe')
            os.rename('ramms_aval_LHM.exe', 'ramms_aval_LHM_orig.exe')

        if not os.path.exists('ramms_aval_LHM.exe'):
            # Need to build
            src = os.path.join(harnutil.HARNESS, 'akramms', 'ramms_aval_LHM_stub.cpp')
            cmd = ['g++', src, '-o', 'ramms_aval_LHM.exe']
            print(' '.join(cmd))
            subprocess.run(cmd, check=True)

# -----------------------------------------------------
def kill_idl():
    sleep=False

    for cmd in (
        ['taskkill.exe', '/F', '/IM', 'idlrt.exe'],
        ['taskkill.exe', '/F', '/IM', 'idl_opserver.exe']):

        try:
            subprocess.run(cmd, check=True)
            sleep=True
        except subprocess.CalledProcessError:
            pass

    # Wait around for NTFS to unlock files used by tasks
    if sleep:
        print('Sleeping because tasks were killed')
        time.sleep(1)

#_doneRE = re.compile(r"\s*Creating MUXI-Files...")    # Demo
_doneRE = re.compile(r'\s*Starting LSHM SIMULATIONS')
#_doneRE = re.compile(r"\s*Finsihed writing GEOTIFF files!")    # Prod

def run_on_windows(idlrt_exe, ramms_distro, ramms_dir):
    """Call this to run top-level RAMMS locally on Windows.
    idlrt_exe:
        Windows path to idlrt.exe IDL runtime
    ramms_distro:
        Top-level directory of RAMMS distribution
    ramms_dir:
        RAMMS directory to run
    Returns:
        Nothing if OK.
        Raises Exception if it did not complete.
    """
    print(f'***** Running Top-Level RAMMS on {ramms_dir}')

    # Make sure we've added our stub properly
    configure_ramms_distro(ramms_distro)

    # Avoid extra IDL's lying around that would eat our license
    kill_idl()

    # Remove logfile (if it exists)
    # (must come after kill_idl())
    logfile = os.path.join(ramms_dir, 'RESULTS', 'lshm_rock.log')
    try:
        os.remove(logfile)
    except FileNotFoundError:
        pass

    # Create batch file to run
    ramms_sav = os.path.join(ramms_distro, 'ramms_lshm.sav')
    scenario_txt = os.path.join(ramms_dir, 'scenario.txt')
    batfile = os.path.join(ramms_dir, 'run_ramms.bat')
    with open(batfile, 'w') as out:
        out.write(f'"{idlrt_exe}" "{ramms_sav}" -args "{scenario_txt}"\n')

    # Run RAMMS
    try:
        fin = None
        proc1 = subprocess.Popen(batfile)

        timeout = 0.5
        state = 0
        while True:
            time.sleep(0.5)

            # See if RAMMS exited unexpectedly
            retcode = proc1.poll()
            if (retcode != None):
                print('IDL RAMMS exited with status code {}'.format(retcode))
                raise subprocess.CalledProcessError(retcode, cmd1)

            # Open logfile if it has appeared
            if fin is None:
                print('.', end='')
                sys.stdout.flush()
                if os.path.exists(logfile):
                    print('Opening logfile')
                    fin = open(logfile)
                    fin.seek(0, os.SEEK_END) 
                    print()
                continue

            # Read out everything in logfile since last time we looked
            while True:
                line = fin.readline()
                if not line:
                    break    # Nothing more to read for now

                # Process the line we read
                print(line+'*', end='')
                if _doneRE.match(line) is not None:
                    raise EOFError()   # Break out of double loop

            sys.stdout.flush()

    except EOFError:
        # Proper signal of end of IDL output; exit gracefully
        pass

    finally:
        if fin is not None:
            fin.close()

        if proc1 is not None:
            # Kill the remaining process
            kill_idl()

            # Just in case, wait for it to exit.
            proc1.communicate()
            print('************ ALL DONE!!! ****************')

    # gzip all .var, .xy-coord and .xyz files
    gzipRE = re.compile(r'[^.]*\.var$|[^.]*\.xy-coord$|[^.]*\.xyz$')
    for path,dirs,files in os.walk(os.path.join(ramms_dir, 'RESULTS')):
        for f in files:
            if gzipRE.match(f) is not None:
                # Gzip the file
                ifname = os.path.join(path, f)
                ofname = os.path.join(path, f+'.gz')
                print(f'Gzipping {ifname}')
                with open(ifname, 'rb') as fin:
                    with gzip.open(ofname, 'wb') as out:
                        shutil.copyfileobj(fin, out)

                # Delete the original
                try:
                    os.remove(ifname)
                except FileNotFoundError:
                    pass
                    

# ---------------------------------------------------------------
_shpRE = re.compile(r'(.+_.+)_(.+_.+)_.*\.shp')
def run_infos(release_files, fetch_ids=False):
    """fetch_ids:
        Should we fetch the individual avalanche IDs?
    """

    infos = list()
    for release_file in release_files:

        RELEASE_dir,shapefile = os.path.split(release_file)
        ramms_dir,_ = os.path.split(RELEASE_dir)

        match = _shpRE.match(shapefile)

        prefix = match.group(1)
        suffix = match.group(2)
        run_dir = os.path.join(ramms_dir, 'RESULTS', prefix, suffix)

        info = {
            'prefix': prefix,
            'suffix': suffix,
            'stem': f'{prefix}_{suffix}',
            'run_dir': run_dir,
        }

        # Read columns of the release dataframe
        if fetch_ids:
            release_df = shputil.read_df(release_file, read_shapes=False)
            info['ids'] = sorted(list(release_df['Id']))

        infos.append(info)

    return infos

#def run_dirs(release_files):
#    """Gets the directories containing the individual RAMMS runs.
#    One top-level RAMMS runs involves many release files and many run_dirs.
#
#    release_files:
#        Names of the release files processed in a RAMMS run"""
#    run_dirs = list()
#    for release_file in release_files:
#        RELEASE_dir,shapefile = os.path.split(release_file)
#        ramms_dir,_ = os.path.split(RELEASE_dir)
#
#        match = _shpRE.match(shapefile)
#        prefix = match.group(1)
#        suffix = match.group(2)
#        run_dirs.append(os.path.join(ramms_dir, 'RESULTS', prefix, suffix))
#
#    return run_dirs

# ---------------------------------------------------------------
# ---------------------------------------------------------------
submit_tpl = \
"""universe                = docker
docker_image            = localhost:5000/ramms
executable              = /usr/bin/python
arguments               = /opt/runaval.py {base}

initialdir              = {dir}
transfer_input_files    = {base}.av2,{base}.dom,{base}.rel,{base}.xyz.gz,{base}.xy-coord.gz,{base}.var.gz
transfer_output_files   = {base}.out.log,{base}.out.gz
should_transfer_files   = YES
when_to_transfer_output = ON_EXIT
on_exit_hold            = False
on_exit_remove          = True

output                  = {base}.job.out
error                   = {base}.job.err
log                     = {base}.job.log
request_cpus            = 1
request_memory          = 1000M
queue 1
"""

def submit_job(run_dir, prefix, suffix, id):
    """Submits an individual avalanche simulation to HTCondor, after
    RAMMS top-level IDL has run.

    run_dir:
        Directory of the avalanche run (see run_dirs() above)
    id:
        ID of the release polygon associated with the avalance.
    """

    prefix, suffix = os.path.normpath(path).split(os.sep)[-2:]
    base = f'{prefix}_{suffix}_{id}'
    submit_txt = submit_tpl.format(base=base, dir=run_dir)

    cmd = ['condor_submit', '-batch-name', base]
    proc = subprocess.Popen(cmd, cwd=run_dir, stdin=subprocess.PIPE)
    proc.communicate(input=submit_txt.encode('utf-8'))
    proc.wait()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)

def analyze_rundir(run_dir, stem):
    # Find all avalanche files in the run_dir related to this shapefile
    job_fileRE = re.compile(r'^{}_(\d+)\.(.*)$'.format(stem))
    id_suffixes = list()    # [(id,suffix), ...]
    for leaf in os.listdir(run_dir):
        match = job_fileRE.match(leaf)
        if match is None:
            continue
        id_suffixes.append((int(match.group(1)), match.group(2)))
    id_suffixes.sort()

    # Create: suffixes = {id0: {suffixes}, id1: {suffixes}, ...}
    return ((id,set(x[1] for x in tuples)) \
        for id,tuples in itertools.groupby(id_suffixes, lambda x: x[0]))


def job_status(release_files):
    """Determines status of ALL Condor jobs for a RAMMS run."""

    # Info on each release file of the RAMMS run
    infos = run_infos(release_files, fetch_ids=True)

    # Initialize set of IDs that we need to regenerate, and that we know are finished
    partition = {'todo': list(), 'inprocess': list(), 'finished': list(), 'failed': list()}

    # Collect together statuses based on info from directory
    for info in infos:
        partition_ids = {'inprocess': set(), 'finished': set(), 'failed': set()}
        stem = info['stem']

        # List of polygon IDs from the shapefile
        partition_ids['todo'] = set(info['ids']) 
        todo_ids = partition_ids['todo']    # alias
        finished_ids = partition_ids['finished']
        inprocess_ids = partition_ids['inprocess']
        failed_ids = partition_ids['failed']

        for id,suffixes in analyze_rundir(info['run_dir'], stem):
            # Identify avalanches that have finished: .out.gz exists and has non-zero size
            if (id in todo_ids):
                if 'out.gz' in suffixes:
                    statinfo = os.stat(os.path.join(info['run_dir'], '{}_{}.out.gz'.format(stem, id)))
                    todo_ids.remove(id)
                    (failed_ids if statinfo.st_size == 0 else finished_ids).add(id)
                elif 'job.log' in suffixes:
                    # The job ran but produced no output; mark as failed.
                    todo_ids.remove(id)
                    failed_ids.add(id)

        # Identify avalanches that have been submitted / are still running
        schedd = htcondor.Schedd()   # get the Python representation of the scheduler
        jobRE_str = r'^{}_([0-9]+)$'.format(stem)
        jobRE = re.compile(jobRE_str)
        ads = schedd.query(    # One Ad per job
            constraint=f'regexp("{jobRE_str}", JobBatchName)',
            projection=['ClusterId', 'ProcId', 'JobBatchName', 'JobStatus'])

        ok_statuses = {htcondor.JobStatus.IDLE, htcondor.JobStatus.RUNNING, htcondor.JobStatus.TRANSFERRING_OUTPUT, htcondor.JobStatus.SUSPENDED}
        for ad in ads:
            match = jobRE.match(ad['JobBatchName'])
            id = int(match.group(1))

            if ad['JobStatus'] in ok_statuses:
                todo_ids.remove(id)
                inprocess_ids.add(id)

        # Turn IDs into full-fledged job names
        for key,names in partition.items():
            names.extend(f'{stem}_{id}' for id in sorted(list(partition_ids[key])))

    return partition

# --------------------------------------------------------
def read_polygon(poly_file):
    """Reads a RAMMS polygon file (eg: .dom) into a Shapely Polygon."""

    with open(poly_file) as fin:
        line = next(fin).split(' ')
        # Get just the x,y coordinates, no count at beginning, no repeat at end
        coords = [float(x) for x in line[1:-2]]

    return shapely.geometry.Polygon(list(zip(coords[::2], coords[1::2])))

def write_polygon(p, poly_file):
    with open(poly_file, 'w') as out:
        coords = list(p.boundary.coords)
        out.write('{}'.format(len(coords)))
        for x,y in coords:
            out.write(f' {x} {y}')
        out.write('\n')
# --------------------------------------------------------
def _scale_vec(vec,margin):
    """Adds a certain length to a vector.  Helper function."""
    veclen = np.linalg.norm(vec)
    if (veclen+margin) < 0:
        raise ValueError('Margin is larger than side')
    factor = margin / veclen
    return factor*vec

def edge_lengths(p):
    pts = np.array(p.boundary.coords)
    edges = np.diff(pts, axis=0)
    return np.linalg.norm(edges,axis=1)

def add_margin(p,margin):
    """Adds a margin to a (rotated) rectangle, i.e. a domain rectangle.
    p: shapely.geometry.Polygon
        The rectangle
    margin:
        Absolute amount to add to length and width.
        If negative, subtract this amount; cannot subtract more than original length
    """
    pts = np.array(p.boundary.coords)
    print('pts0:\n',pts)
    edges = np.diff(pts, axis=0)
    print('edge lengths: ', np.linalg.norm(edges,axis=1))
    margin2 = .5*margin
    pts[0,:] += (_scale_vec(edges[3,:],margin2) - _scale_vec(edges[0,:],margin2))
    pts[1,:] += (_scale_vec(edges[0,:],margin2) - _scale_vec(edges[1,:],margin2))
    pts[2,:] += (_scale_vec(edges[1,:],margin2) - _scale_vec(edges[2,:],margin2))
    pts[3,:] += (_scale_vec(edges[2,:],margin2) - _scale_vec(edges[3,:],margin2))

    print('pts1:\n',pts)
    p = shapely.geometry.Polygon(list(zip(pts[:-1,0], pts[:-1,1])))
    print('p: ',p)
    return p
# --------------------------------------------------------
