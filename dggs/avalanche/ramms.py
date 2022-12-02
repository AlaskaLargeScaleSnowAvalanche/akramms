import os,subprocess,re,sys,itertools,gzip,collections
import datetime,time,zipfile
import contextlib
import itertools, functools,shutil
import numpy as np
import shapely
import htcondor
from dggs.avalanche import avalanche
from dggs.util import harnutil
import dggs.data
from uafgi.util import make,ioutil,shputil
import pandas as pd

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
                # --ramms-version 221101
                HARNESS_REMOTE, bash=True)

        cmd = ['ssh', hostname, 'sh', remote_run_ramms_sh,
            harnutil.remote_windows_name(ramms_dir, HARNESS_REMOTE, bash=True)]
        print(' '.join(cmd))
        if not dry_run:
            subprocess.run(cmd, check=True)


        # Get results back
        err = None
        for release_file in release_files:
            jb = parse_release_file(release_file)

            os.makedirs(jb.run_dir, exist_ok=True)
            print('Retrieving dir ', jb.run_dir)
            cmd = ['rsync', '-avz',
                '{}:{}/'.format(hostname, harnutil.remote_windows_name(jb.run_dir, HARNESS_REMOTE, bash=True)),
                jb.run_dir]
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
# # https://dev.to/teckert/changing-directory-with-a-python-context-manager-2bj8
# @contextlib.contextmanager
# def set_directory(path):
#     """Sets the cwd within the context
# 
#     Args:
#         path (Path): The path to the cwd
# 
#     Yields:
#         None
# 
#     """
# 
#     origin = Path().absolute()
#     try:
#         os.chdir(path)
#         yield
#     finally:
#         os.chdir(origin)



# ---------------------------------------------------------------
ParsedJobBase = collections.namedtuple('JobSpec', ('run_dir', 'base', 'prefix', 'suffix'))
_job_baseRE = re.compile(r'^(.+_.+)_(.+_.+)$')
@functools.lru_cache()
def parse_job_base(ramms_dir, job_base):
    """
    base:
        String of base of job names, with an avalanche ID.
        Eg: juneau1_For_5m_30L
    """
    print('job_base ',job_base)
    match = _job_baseRE.match(job_base)
    prefix = match.group(1)
    suffix = match.group(2)
    run_dir = os.path.join(ramms_dir, 'RESULTS', prefix, suffix)
    return ParsedJobBase(run_dir, job_base, prefix, suffix)

@functools.lru_cache()
def parse_release_file(release_file):
    """Parses the full name of a release file into a ParsedJobBase named tuple."""

    RELEASE_dir,shapefile = os.path.split(release_file)
    ramms_dir = os.path.split(RELEASE_dir)[0]
    print('shapefile ',shapefile)
    base = shapefile[:-8]    # remove _rel.shp
    return parse_job_base(ramms_dir, base)

def get_job_ids(release_file):
    """Reads a release file, and returns a (sorted) list of PRA IDs in that file."""
    release_df = shputil.read_df(release_file, read_shapes=False)
    return sorted(list(release_df['Id']))
# ---------------------------------------------------------------
DOCKER_IMAGE = 'localhost:5000/ramms'

submit_tpl = \
"""universe                = docker
docker_image            = localhost:5000/ramms
executable              = /usr/bin/python
arguments               = /opt/runaval.py {job_name}

initialdir              = {run_dir}
transfer_input_files    = {job_name}.av2,{job_name}.dom,{job_name}.rel,{job_name}.xyz.gz,{job_name}.xy-coord.gz,{job_name}.var.gz
transfer_output_files   = {job_name}.out.zip
should_transfer_files   = YES
when_to_transfer_output = ON_EXIT
on_exit_hold            = False
on_exit_remove          = True

output                  = {job_name}.job.out
error                   = {job_name}.job.err
log                     = {job_name}.job.log
request_cpus            = 1
request_memory          = 1000M
queue 1
"""

def submit_job(run_dir, job_name):#, local=False):
    """Submits an individual avalanche simulation to HTCondor, after
    RAMMS top-level IDL has run.

    run_dir:
        Directory of the avalanche run (see run_dirs() above; underneath ramms_dir)
        Eg: ...RAMMS/juneau130yFor/RESULTS/juneau1_For/5m_30L
    job_name:
        Full name of job, including ID
            Eg: juneau1_For_5m_30L_1833
    local:
        If True, run immediately on local machine, do not use HTCondor.
    """

#    if local:
#        print('Running: {}'.format(job_name))
#        cmd = ['docker', 'run', DOCKER_IMAGE, '/usr/bin/python', '/opt/runaval.py', job_name]
#        subprocess.run(cmd, cwd=run_dir, check=True)
#        return


    print('Submitting job: {}'.format(job_name))
    submit_txt = submit_tpl.format(job_name=job_name, run_dir=run_dir)

    cmd = ['condor_submit', '-batch-name', job_name]
    proc = subprocess.Popen(cmd, cwd=run_dir, stdin=subprocess.PIPE)
    proc.communicate(input=submit_txt.encode('utf-8'))
    proc.wait()
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd)

def analyze_rundir(run_dir, job_base):
    """Find all avalanche files in the run_dir related to this shapefile
    Returns: {id: [suffix, ...], ...}
        For each avalanche ID in run_dir, a list of the related files
        that exist, identified by filename suffix.

        Eg: if avalanche ID 8733 exists in run_dir, an entry might look like:
            8733: {'av2', 'xyz.gz', 'xy-coord.gz', 'var.gz', 'dom', 'rel', ...}

    """
    job_fileRE = re.compile(r'^{}_(\d+)\.(.*)$'.format(job_base))
    id_suffixes = list()    # [(id,suffix), ...]
    if os.path.isdir(run_dir):
        for leaf in os.listdir(run_dir):
            match = job_fileRE.match(leaf)
            if match is None:
                continue
            id_suffixes.append((int(match.group(1)), match.group(2)))
    id_suffixes.sort()

    # Create: suffixes = {id0: {suffixes}, id1: {suffixes}, ...}
    return ((id,set(x[1] for x in tuples)) \
        for id,tuples in itertools.groupby(id_suffixes, lambda x: x[0]))


def query_condor(job_base):
    """
    job_base:
        Base name of jobs we are querying for.
    Returns: {job_name: status}
        status: int
            Status of job.  See enumeration htcondor.JobStatus:
                https://htcondor.readthedocs.io/en/latest/apis/python-bindings/api/htcondor.html?highlight=jobstatus#htcondor.JobStatus
            JobStatus codes:
                 1 I IDLE
                 2 R RUNNING
                 3 X REMOVED
                 4 C COMPLETED
                 5 H HELD
                 6 > TRANSFERRING_OUTPUT
                 7 S SUSPENDED

    """
    # Query Condor
    schedd = htcondor.Schedd()   # get the Python representation of the scheduler
    jobRE_str = r'^{}_([0-9]+)$'.format(jb.base)
    jobRE = re.compile(jobRE_str)
    ads = schedd.query(    # One Ad per job
        constraint=f'regexp("{jobRE_str}", JobBatchName)',
        projection=['ClusterId', 'ProcId', 'JobBatchName', 'JobPartition'])
    condor_statuses = {ad['JobBatchName']: ad['JobPartition'] for ad in ads}


# Categorize each job int one of four sets
job_status_labels = ('noinput', 'incomplete', 'todo', 'inprocess', 'finished', 'overrun', 'failed')
class JobStatus:
    NOINPUT = 0         # No RAMMS input files exist
    INCOMPLETE = 1   # Some but not all RAMMS input files exist
    TODO = 2         # Ready to submit to HTCondor but no evidence that has been done
    INPROCESS = 3    # HTCondor is dealing with it
    FINISHED = 4     # The avalanche has finished, and it's successful
    OVERRUN = 5      # Avalanche overran the boundary; auto-resubmit
    FAILED = 6       # The job finished but did not produce full / correct output

def job_statuses(release_files):
    """Determines status of ALL Condor jobs for a RAMMS run."""

    # Info on each release file of the RAMMS run
#    infos = run_infos(release_files, fetch_ids=True)

    # Initialize set of IDs that we need to regenerate, and that we know are finished
#    partition = {x:list() for x in _job_partition_labels}

    # Collect together statuses based on info from directory
    statuses = list()
    for release_file in release_files:
        jb = parse_release_file(release_file)
        ids = get_job_ids(release_file)

        # Query Condor
        schedd = htcondor.Schedd()   # get the Python representation of the scheduler
        jobRE_str = r'^{}_([0-9]+)$'.format(jb.base)
        jobRE = re.compile(jobRE_str)
        ads = schedd.query(    # One Ad per job
            constraint=f'regexp("{jobRE_str}", JobBatchName)',
            projection=['ClusterId', 'ProcId', 'JobBatchName', 'JobPartition'])

        # IDentify status coming from Condor
        op_by_status = {
            htcondor.JobStatus.IDLE: JobStatus.INPROCESS,
            htcondor.JobStatus.RUNNING: JobStatus.INPROCESS,
            htcondor.JobStatus.TRANSFERRING_OUTPUT: JobStatus.INPROCESS,
            htcondor.JobStatus.SUSPENDED: JobStatus.FAILED,
        }
        condor_statuses = dict()
        for ad in ads:
            job_name = ad['JobBatchName']
            if 'JobPartition' in ad:
                jp = ad['JobPartition']
                try:
                    condor_statuses[job_name] = op_by_status[jp]
                except:
                    pass
            else:
                # It's been submitted but not yet run
                condor_statuses[job_name] = JobStatus.INPROCESS

        # Identify avalanches that have been submitted / are still running

        # List files on disk
#        ard = analyze_rundir(jb.run_dir, jb.base)
#        print('run_dir ',jb.run_dir)
#        print('ard ',ard)
        job_suffixes = dict(analyze_rundir(jb.run_dir, jb.base))

        # --------------------------------------------------

        # Consider each job in turn from our master list
        for id in ids:
            key = (jb.run_dir, id)

            job_name = f'{jb.base}_{id}'

            # If nothing for this key exists, then probably top-level
            # RAMMS has not been run yet for this run_dir
            if id not in job_suffixes:
                statuses.append((jb.run_dir, id, JobStatus.NOINPUT))
                continue
            suffixes = job_suffixes[id]

            # Mark as INCOMPLETE if not all input files are there
            input_suffixes = ('rel', 'dom', 'av2', 'var.gz', 'xy-coord.gz', 'xyz.gz')
            ninputs = sum(x in suffixes for x in input_suffixes)

            if ninputs == 0:
                statuses.append((jb.run_dir, id, JobStatus.NOINPUT))
                continue

            if ninputs < len(input_suffixes):
                statuses.append((jb.run_dir, id, JobStatus.INCOMPLETE))
                continue


            # See if Condor tells is what's going on with the job
            if job_name in condor_statuses:
                statuses.append((jb.run_dir, id, condor_statuses[job_name]))
                continue

            # Not in Condor?  Either it hasn't launched, or it's finished / failed
            # Let's look at the files on disk to decide.

            # Identify avalanches that have finished: .out.gz exists and has non-zero size
            # (User can reset jobs by removing *.job.log)
            if ('out.zip' in suffixes):
                out_zip = os.path.join(jb.run_dir, '{}_{}.out.zip'.format(jb.base, id))

                # Check for abandoned job
                statinfo = os.stat(out_zip)
                if (statinfo.st_size==0):
                    # The HTCondor output file has been created, but
                    # no sign of the HTCondor job to write it at the
                    # end.  Sounds like things were killed, send
                    # status back to TODO.
                    statuses.append((jb.run_dir, id, JobStatus.TODO))
                    continue

                # We tentatively think the job is finished.  But let's
                # look inside the zip file to make sure the domain
                # wasn't overrun.
                with zipfile.ZipFile(out_zip, 'r') as in_zip:
                    arcnames = [os.path.split(x)[1] for x in in_zip.namelist()]
                if any(x.endswith('.out.overrun') for x in arcnames):
                    statuses.append((jb.run_dir, id, JobStatus.OVERRUN))
                else:
                    statuses.append((jb.run_dir, id, JobStatus.FINISHED))
                continue

            # Default to TODO
            statuses.append((jb.run_dir, id, JobStatus.TODO))


    df = pd.DataFrame(statuses, columns=('run_dir', 'id', 'job_status'))
    df = df.sort_values(by=['run_dir', 'job_status', 'id'])
    return df
# --------------------------------------------------------
def read_polygon(poly_file):
    """Reads a RAMMS polygon file (eg: .dom) into a Shapely Polygon."""
    print(f'Reading {poly_file}')
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
    edges = np.diff(pts, axis=0)
    print('edge lengths: ', np.linalg.norm(edges,axis=1))
    margin2 = .5*margin
    pts[0,:] += (_scale_vec(edges[3,:],margin2) - _scale_vec(edges[0,:],margin2))
    pts[1,:] += (_scale_vec(edges[0,:],margin2) - _scale_vec(edges[1,:],margin2))
    pts[2,:] += (_scale_vec(edges[1,:],margin2) - _scale_vec(edges[2,:],margin2))
    pts[3,:] += (_scale_vec(edges[2,:],margin2) - _scale_vec(edges[3,:],margin2))

    p = shapely.geometry.Polygon(list(zip(pts[:-1,0], pts[:-1,1])))
    return p
# --------------------------------------------------------
def print_job_statuses(df):
    for (run_dir, job_status), group in df.groupby(['run_dir', 'job_status']):

        print('=========== {} {}:'.format(job_status_labels[job_status], run_dir))
        print(sorted(group['id'].tolist()))

def run_simulations0(ramms_dir, release_files, sleep=10*60):
    """Submits simulations and babysits them, polling periodically until they are done.
    ramms_dir:
        Eg: /home/efischer/av/prj/juneau1/RAMMS/juneau130yFor
    Returns:
        JobPartition
    """

    while True:
        st = job_statuses(release_files)
        print_job_statuses(st)

        # Write out latest status in user-readable format
        now = datetime.datetime.now()
        with open(os.path.join(ramms_dir, 'status_summary.txt'), 'w') as out:
            out.write(f'RAMMS Avalanche Job Status as of: {now:%Y-%m-%d %H:%M:%S}\n')
            for lab in _job_partition_labels:
                out.write(f'================= {lab}\n')
                jobs = getattr(st, lab)
                out.write('\n'.join('    '+job_name for run_dir,job_name in jobs))
                out.write('\n')

        # Nothing more to do: everything is either finished or failed.
        if len(st['todo']) == 0 and len(st['inprocess']) == 0:
            break

        # Submit all the jobs that need to be submitted
        for run_dir,job_name in st['todo']:
            submit_job(run_dir, job_name)
        
        # Come back later
        print('Sleeping...')
        time.sleep(10)

    return st

# -------------------------------------------------------
def expand_domain(run_dir, job_name, enlarge_increment=1000.):
    print('Expanding domain for {}'.format(job_name))

    dom_file = os.path.join(run_dir, f'{job_name}.dom')
    domRE = re.compile(r'^{}.dom.v(\d+)$'.format(dom_file))

    # Figure out largest .dom.vXXX file that exists
    max_version = 0
    for file in os.listdir(run_dir):
        match = domRE.match(file)
        if match is None:
            continue
        max_verison = max(max_version, int(match.group(1)))

    # Copy to one bigger
    shutil.copy2(dom_file, dom_file + '.v{}'.format(max_version+1))

    # Read the .dom file, make it bigger by 1000m, and write it back
    dom = read_polygon(dom_file)
    dom = add_margin(dom, enlarge_increment)
    write_polygon(dom, dom_file)    # New timestamp


def run_simulations(ramms_dir, release_files, sleep=10*60, enlarge_increment=1000.):
#    while True:
    if True:
        # Run all simulations
#        st = run_simulations0(ramms_dir, release_files, sleep=sleep)
        st = job_statuses(release_files)
        print_job_statuses(st)
        return

        # If nothing failed, we're done!
        if len(st['failed']) == 0:
            return st

        found_problem = False
        for run_dir,job_name in st['finished']:

            # Identify simulations that overran the domain
            # (but otherwise look like they finished)
            out_log = os.path.join(run_dir, f'{job_name}.out.log')
            with open(out_log) as fin:
                for line in fin:
                    if line.startswith(' FINAL OUTFLOW VOLUME:'):

                        # This job overran its domain
                        expand_domain(run_dir, job_name, enlarge_increment=enlarge_increment)

                        # Reset status
                        try:
                            os.remove(os.path.join(run_dir, f'{job_name}.out.gz'))
                        except FileNotFoundError:
                            pass

                        try:
                            os.remove(os.path.join(run_dir, f'{job_name}.job.log'))
                        except FileNotFoundError:
                            pass

                        # Mark for another goaround
                        found_problem = True

                        # No more digging into this log file
                        break

        # If we didn't find / fix any errors, return status
        # Any further errors will have to be dealt with manually.
        if not found_problem:
            return st


# Operations for command line program:
# 1. show status of overall RAMMS run / single release shapefile / single avalanche
# 2. Inspect single run: show domain size, and other stuff
# 3. Mark a shapefile complete IN SPITE OF outstanding failed avlanches
#
# Try grepping the out.log file as soon as the run completes, mark it as bad immediately somehow

# -------------------------------------------------------
def inspect_job(ramms_dir, job_name):
    prefix,suffix = parse_job_name(job_name)

def _ramms_to_release(ramms_dirs):
    """Given a bunch of RAMMS directories, returns the release files in them."""
    release_files = list()
    for ramms_dir in ramms_dirs:
        RELEASE_dir = os.path.join(ramms_dir, 'RELEASE')
        for file in os.listdir(RELEASE_dir):
            if file.endswith('_rel.shp'):
                release_files.append(os.path.join(RELEASE_dir, file))

    return release_files

def get_release_files(spec):
    """Given a directory above or below the RAMMS directory, finds a
    "ramms dir," which is one level below RAMMS/."""

    # *** The spec is a directory corresponding to a SINGLE shapefile
    # ** The spec is a SINGLE shapefile
    if spec.endswith('.shp'):
        return [spec]

    dir = os.path.abspath(spec)
    parts = dir.split(os.sep)

    # See if we're in, eg:
    #   RAMMS/juneau130yFor/RESULTS/juneau1_For/5m_30L$ 
    # Return just the shapefile
    if len(parts) >=3 and parts[-3] == 'RESULTS':
        parts2 = parts[:-3] + ['RELEASE', '{}_{}_rel.shp'.format(parts[-2], parts[-1])]
        return [os.sep.join(parts2)]


    # See if we're in a subdirectory
    for i in range(len(parts)):
        if parts[i] == 'RAMMS':
            # RAMMS/ is the last part of the path, we have multiple dirs.
            if len(parts) == i:
                ramms_dirs = [os.path.join(x) for x in os.listdir(dir)]
                return _ramms_to_release(ramms_dirs)
            else:
                # We have a path one lower than RAMMS, use it.
                return _ramms_to_release([os.sep.join(parts[:i+2])])

    raise ValueError('Could not interpret spec {} as one or more RAMMS dirs'.format(spec))
