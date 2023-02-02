import os,subprocess,re,sys,itertools,gzip,collections,io,typing
import numpy as np
import datetime,time,zipfile
import contextlib
import itertools, functools,shutil
import numpy as np
import shapely
import htcondor
from dggs.avalanche import avalanche,akramms,rammsutil
from dggs.util import harnutil
import dggs.data
from uafgi.util import make,ioutil
import pandas as pd


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

def rammsdir_rule(scene_dir, release_file, HARNESS_REMOTE,
    debug=False, alt_lim_top=1500, alt_lim_low=1000, ncpu=8, ncpu_preprocess=4, cohesion=50):

    """Generates the scenario file, which becomes key to running RAMMS.
    HARNESS_REMOTE:
        Location of ~/git on remote Windows machine (parent of akramms/ repo)
    """
    jb = rammsutil.parse_release_file(release_file)

    scene_args = avalanche.params.load(scene_dir)
    resolution = scene_args['resolution']
    name = scene_args['name']
    For = 'For' if jb.forest else 'NoFor'
    scenario_file = os.path.join(jb.ramms_dir, 'scenario.txt')

    # ---- DEM File
    idem_dir,idem_tif = os.path.split(scene_args['dem_file'])
    idem_stub = idem_tif[:-4]
    links = [
        (os.path.join(idem_dir, f'{idem_stub}.tif'), os.path.join(jb.ramms_dir, 'DEM', f'{name}{For}_{resolution}m_DEM.tif')),
        (os.path.join(idem_dir, f'{idem_stub}.tfw'), os.path.join(jb.ramms_dir, 'DEM', f'{name}{For}_{resolution}m_DEM.tfw')),
    ]


    # ---- Forest File
    if jb.forest:
        iforest_dir,iforest_tif = os.path.split(scene_args['forest_file'])
        iforest_stub = iforest_tif[:-4]
        links += [
            (os.path.join(iforest_dir, f'{iforest_stub}.tif'), os.path.join(jb.ramms_dir, 'FOREST', f'{name}{For}_{resolution}m_forest.tif')),
            (os.path.join(iforest_dir, f'{iforest_stub}.tfw'), os.path.join(jb.ramms_dir, 'FOREST', f'{name}{For}_{resolution}m_forest.tfw')),
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
        kwargs['scenario_name'] = jb.scenario_name
        kwargs['remote_ramms_dir'] = harnutil.remote_windows_name(jb.ramms_dir, HARNESS_REMOTE)
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
def run_ramms(hostname, ramms_dir, stage, inputs, HARNESS_REMOTE, tdir, dry_run=False):
    """
    hostname:
        Remote windows host to run on
    ramms_dir:
        Local directory containing RAMMS setup
    stage: 1 or 3
        stage=1:
            Prepare avlanche simulations for RAMMS Core
        stage=3:
            Merge avalanche outputs from RAMMS Core
    inputs:
        Input files in local harness; to be copied to remote host before running RAMMS.
        This list is also provided to the remote RAMMS via stdin
    tdir: ioutil.TmpDir
        Location for temporary directories
    Returns: [filename, ...]
        Local filenames of output files, which were generated on the remote
        Windows machine and then copied to Linux.
    """

# Not needed, harnutil does this
#    # Create remote dir
#    cmd = ['ssh', hostname, 'mkdir', '-p', harnutil.remote_windows_name(ramms_dir, HARNESS_REMOTE, bash=True)]
    subprocess.run(cmd, check=True)

    # Sync RAMMS input files to remote dir
    harnutil.rsync_files(inputs, hostname, HARNESS_REMOTE, tdir, direction='up')

    # Run RAMMS
    remote_run_ramms_sh = harnutil.remote_windows_name(
            os.path.join(harnutil.HARNESS, 'akramms', 'sh', 'run_ramms.sh'),
            # --ramms-version 221101
            HARNESS_REMOTE, bash=True)

    cmd = ['ssh', hostname, 'sh', remote_run_ramms_sh,
        harnutil.remote_windows_name(ramms_dir, HARNESS_REMOTE, bash=True),
        str(stage)]    # Stage 1 to 1
    print(' '.join(cmd))
    if not dry_run:
        # Start the remote process
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        # Write to processes stdin
        inputs_w = [
            harnutil.remote_windows_name(input, HARNESS_REMOTE, bash=False)
            for input in inputs]
        inputs_txt = ''.join(f'INPUT: {input_w}\r\n' for input_w in inputs_w) + 'END INPUTS\r\n'
        for input in inputs:
            proc.stdin.write(inputs_txt.encode('UTF-8'))
        proc.stdin.flush()

        outputs = list()
        outputRE = re.compile(r'OUTPUT:\s([^\s]*)\s*$')
        while True:
            line = proc.stdout.readline().decode('UTF-8')
            if not line:
                break
            print(line, end='')

            # Collect list of output files as declared by Windows-side RAMMS
            match = outputRE.match(line)
            if match is not None:
                outputs.append(match.group(1))

        proc.wait()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

        # outputs contains Windows names of output files.
        # Transfer over to local Linux, and conver to Linux filenames.
        outputs_b = [harnutil.bash_name(x) for x in outputs]
        # _rel = Bash-style filenames relative to the harness
        outputs_rel = harnutil.rsync_files(outputs_b, hostname, HARNESS_REMOTE, tdir, direction='down')
        # Outputs as local filenames
        outputs = [os.path.join(harnutil.HARNESS, x) for x in outputs_rel]
        return outputs
# ----------------------------------------------------------------------
def ramms_stage1_rule(hostname, ramms_dir, release_files, inputs, HARNESS_REMOTE, dry_run=False, submit=True):
    """Runs Stage 1 of RAMMS (IDL code prepares individual avalanche runs)

    inputs:
        All input files for the RAMMS run (superset of release_files)
    """

    logfile = os.path.join(ramms_dir, 'RESULTS', 'lshm_rock.log')

    # Write extra output files to show we finished stage1 for a particular release file
    done_outputs = list()
    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)
        output = os.path.join(ramms_dir, 'RESULTS', '{}_{}_stage1.txt'.format(jb.prefix, jb.suffix))
        done_outputs.append(output)

    def action(tdir):

        # Sync RAMMS files to remote dir
        harnutil.rsync_files(inputs, hostname, HARNESS_REMOTE, tdir)

        # Run RAMMS
        outputs = run_ramms(hostname, ramms_dir, 1, inputs, HARNESS_REMOTE, tdir, dry_run=dry_run)

        # Get logfile back
        cmd = ['rsync',
            '{}:{}'.format(hostname, harnutil.remote_windows_name(logfile, HARNESS_REMOTE, bash=True)),
            logfile]
        print(' '.join(cmd))
        subprocess.run(cmd, check=True)

        # Write output files
        for output in done_outputs:
            with open(output, 'w') as out:
                out.write('Finished RAMMS Stage 1\n')

        # Submit the individual avalanche runs immediately so we can
        # get going while preparing more RAMMS directories.
        if submit:
            submit_jobs(release_files)

    return make.Rule(action,
        inputs,
        done_outputs)

# =========================================================================================
# ===== RAMMS Stage 2: Manage avalanche jobs

# ---------------------------------------------------------------
#DOCKER_IMAGE = 'localhost:5000/ramms'
DOCKER_IMAGE = 'git.akdggs.com/efischer/ramms'

submit_tpl = \
"""universe                = docker
docker_image            = {DOCKER_IMAGE}
executable              = /usr/bin/python
arguments               = /opt/runaval.py {job_name}

initialdir              = {run_dir}
transfer_input_files    = {job_name}.av2,{job_name}.dom,{job_name}.rel,{job_name}.xyz.gz,{job_name}.xy-coord.gz,{job_name}.var.gz
transfer_output_files   = {job_name}.log.zip,{job_name}.out.gz
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
    submit_txt = submit_tpl.format(job_name=job_name, run_dir=run_dir, DOCKER_IMAGE=DOCKER_IMAGE)

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

def get_job_ids(release_file):
    """Reads a release file, and returns a (sorted) list of PRA IDs in that file."""
    release_df = shputil.read_df(release_file, read_shapes=False)
    return sorted(list(release_df['Id']))

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
        jb = rammsutil.parse_release_file(release_file)
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
            if ('log.zip' in suffixes) and ('out.gz' in suffixes):
                log_zip = os.path.join(jb.run_dir, '{}_{}.log.zip'.format(jb.base, id))

                # Check for abandoned job
                statinfo = os.stat(log_zip)
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
                with zipfile.ZipFile(log_zip, 'r') as in_zip:
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
def print_job_statuses(df):
    for (run_dir, job_status), group in df.groupby(['run_dir', 'job_status']):

        print('=========== {} {}:'.format(job_status_labels[job_status], run_dir))
        print(sorted(group['id'].tolist()))

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

# --------------------------------------------------------------------
def submit_jobs(release_files, ids=None):
    """Does an initial (or subsequent) submit of jobs for a set of
    release files.  Submits jobs that can be submitted, and that have
    not yet been.

    Returns:
        df:
            Job statuses BEFORE submissions were made
    """

    df = job_statuses(release_files)
    df = df[df.job_status == JobStatus.TODO]
    for _,row in df.iterrows():
        if ids is None or row['id'] in ids:
            parts = row['run_dir'].split(os.sep)
            job_name = '{}_{}_{}'.format(parts[-2], parts[-1], row['id'])
#            print('submit ', row['run_dir'], job_name)
            submit_job(row['run_dir'], job_name)

    return df

# -------------------------------------------------------
# ======================================================================
# ============= RAMMS Stage 2: Enlarge and re-submit domains that overran

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
    edges = np.diff(pts, axis=0)
    margin2 = .5*margin
    pts[0,:] += (_scale_vec(edges[3,:],margin2) - _scale_vec(edges[0,:],margin2))
    pts[1,:] += (_scale_vec(edges[0,:],margin2) - _scale_vec(edges[1,:],margin2))
    pts[2,:] += (_scale_vec(edges[1,:],margin2) - _scale_vec(edges[2,:],margin2))
    pts[3,:] += (_scale_vec(edges[2,:],margin2) - _scale_vec(edges[3,:],margin2))

    p = shapely.geometry.Polygon(list(zip(pts[:-1,0], pts[:-1,1])))
    return p
# -----------------------------------------------------------
def enlarge_domain(run_dir, job_name, enlarge_increment=5000.):

    # Read the .dom file and make it bigger by 1000m
    dom_file = os.path.join(run_dir, f'{job_name}.dom')
    log_zip_file = os.path.join(run_dir, f'{job_name}.log.zip')
    dom0 = read_polygon(dom_file)
    dom1 = add_margin(dom0, enlarge_increment)
    with np.printoptions(precision=0, suppress=True):
        print('{}:\n  {} -> {}'.format(job_name, edge_lengths(dom0), edge_lengths(dom1)))

    # ----Rename old .dom file and write new one
    if True:
        domRE = re.compile(r'^{}.dom.v(\d+)$'.format(dom_file))

        # Figure out largest .dom.vXXX file that exists
        max_version = 0
        for file in os.listdir(run_dir):
            match = domRE.match(file)
            if match is None:
                continue
            max_verison = max(max_version, int(match.group(1)))

        # Copy to one bigger, then overwrite
        shutil.copy2(dom_file, dom_file + '.v{}'.format(max_version+1))
        shutil.copy2(log_zip_file, log_zip_file + '.v{}'.format(max_version+1))
        write_polygon(dom1, dom_file)    # New timestamp


def enlarge_domains(release_files, ids=None):
    df = job_statuses(release_files)
    df = df[df.job_status == JobStatus.OVERRUN]
    for _,row in df.iterrows():
        run_dir = row.run_dir
        parts = run_dir.split(os.sep)
        job_name = '{}_{}_{}'.format(parts[-2], parts[-1], row['id'])
        if ids is None or row['id'] in ids:

            # ONLY enlarge if the .log.zip file is newer than the .dom file
            # (Otherwise, we apparently already enlarged but have not yet re-run)
            log_file = os.path.join(run_dir, f'{job_name}.log.zip')
            dom_file = os.path.join(run_dir, f'{job_name}.dom')
            log_tm = os.path.getmtime(log_file)
            try:
                dom_tm = os.path.getmtime(dom_file)
            except OSError:    # File not exist
                dom_tm = -1
            if log_tm > dom_tm:
                enlarge_domain(run_dir, job_name)
            submit_job(run_dir, job_name)

    return df

# -------------------------------------------------------
_parseRE = re.compile(
    r'(^\s*FINAL OUTFLOW VOLUME:\s+(?P<final_outflow_volume>[^\s]+)\s+m3)' +
    '|' +
    r'(^\s*INITIAL FLOW VOLUME:\s+(?P<initial_outflow_volume>[^\s]+)\s+m3)')


def _parse_aval_log(log_in):

    ret = dict()    # Key values pulled out of the file
    for line in log_in:
        match = _parseRE.match(line)
        if match is not None:
            match_names = [name for name, value in match.groupdict().items() if value is not None]
            # Remember first of each match value
            for name in match_names:
                if name not in ret:
                    ret[name] = match.group(name)

    return ret

def parse_aval_log(log_in):
    if isinstance(log_in, str):    # Open zip file
        with zipfile.ZipFile(log_in, 'r') as izip:
            arcnames = [os.path.split(x)[1] for x in izip.namelist()]
            lognames = [x for x in arcnames if x.endswith('.out.log')]
            bytes = izip.read(lognames[0])
            fin = io.TextIOWrapper(io.BytesIO(bytes))
            return _parse_aval_log(fin)
    else:
        return _parse_aval_log(fin)

# -------------------------------------------------------

def ramms_iter(ramms_spec, ids=list()):
    """Iterates through a set of avalanches by spec
    spec:
        Spec indicating the release file(s) to include in the iteration
    ids: [int, ...]
        Avalanche IDs to include.
        If empty list, that means include all of them.
    """

    release_files = get_release_files(ramms_spec)
    ids = set(ids)

    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)
        exist_ids = get_job_ids(release_file)

        # Get list of ids to inspect
        if len(ids) == 0:
            process_ids = exist_ids
        else:
            process_ids = {x for x in exist_ids if x in ids}


        for id in process_ids:
            yield jb,id


def cat(ramms_spec, ids=list()):
    for jb,id in ramms_iter(ramms_spec, ids=ids):
        log_zip = jb.log_zip(id)
        with zipfile.ZipFile(log_zip, 'r') as izip:
            print('======== {}'.format(log_zip))
            sys.stdout.flush()
            bytes = izip.read(jb.arcname(id, '.out.log'))
            os.write(1, bytes)    # 1 = STDOUT
            #with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
            #    stdout.write(bytes)
            #    stdout.flush()



def infos(release_files, ids=None):
    """Provide summary info on one or more completed avalanches"""
    if ids is None:
        ids = set([])
    else:
        ids = set(ids)

    infos = list()
    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)
        exist_ids = get_job_ids(release_file)

        # Get list of ids to inspect
        if len(ids) == 0:
            process_ids = exist_ids
        else:
            process_ids = {x for x in exist_ids if x in ids}


        # Inspect them
        for id in process_ids:
            job_name = f'{jb.base}_{id}'
            info = {'job_name': job_name, 'id': id}

            # Add info from the logfile (if it exists)
            job_log_zip = f'{job_name}.log.zip'
            try:
                for k,v in parse_aval_log(job_log_zip).items():
                    info[k] = float(v)
#                info = {**info, **parse_aval_log(job_log_zip)}
            except FileNotFoundError:
                pass
            except zipfile.BadZipFile:
                pass

            # Add info from the release file
            rel_file = f'{job_name}.rel'
            try:
                rel = read_polygon(rel_file)
                info['release_area'] = rel.area
            except FileNotFoundError:
                pass

            # Add info from the domain file
            dom_file = f'{job_name}.dom'
            try:
                dom = read_polygon(dom_file)
                info['domain_area'] = dom.area
            except FileNotFoundError:
                pass

            # Find out how much domain and release intersect
            if 'domain_area' in info and 'release_area' in info:
                info['intersect_area'] = dom.intersection(rel).area

            infos.append(info)

    return pd.DataFrame(infos)

# =============================================================================
# ===== RAMMS Stage 3

def ramms_stage3_rule(hostname, ramms_dir, release_files, HARNESS_REMOTE, dry_run=False, submit=True):
    """Runs Stage 1 of RAMMS (IDL code prepares individual avalanche runs)
    For now, do no inputs to stage3.  It's hard to predict exactly
    what the input files should be.

    release_files:
        Must be ALL the (active) release files for ramms_dir.
    """

    # Leave these out for now:
    # (See email from Marc, they have a wrong name...)
    #     juneau130yFor\RESULTS\juneau1_For\juneau1_For_L300_mu.tif
    #     juneau130yFor\RESULTS\juneau1_For\juneau1_For_L300_xi.tif

    inputs = list()
    outputs = list()
    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)

        # -----------------------------------------------------------
        # Inputs are the "declaration" files from RAMMS Stage 2 that
        # avalanches from each release file have been completed.
        # (Sometimes not all individual avalanches can complete, for
        # various reasons).
        input = os.path.join(ramms_dir, 'RESULTS', '{}_{}_stage2.txt'.format(jb.prefix, jb.suffix))
        inputs.append(input)

        # -----------------------------------------------------------
        # Outputs are the end-user GeoTIFF files that RAMMS Stage 3 writes.

        # Misc. Files
        dir = os.path.join(ramms_dir, 'RESULTS', jb.prefix)
        for leaf in ('curvidl.tif', 'slope.tif', 'logfiles/muxi_altlimits.log', 'logfiles/muxi_class.tif'):
            outputs.append(os.path.join(dir, leaf))

        # The main GeoTIFF Files
        base = os.path.join(dir, '{}_{}'.format(jb.prefix, jb.suffix))    # Eg: juneau1_For_5m_30L
        for ext in (
            '.dbf', '.shp', '.shx',
            '_AblagerungStef.tif', '_COUNT.tif', '_ID.tif', '_Xi.tif',
            '_maxHeight.tif', '_maxPRESSURE.tif', '_maxVelocity.tif'):
            outputs.append(f'{base}{ext}')

    # ----------------------------------------------------
    def action(tdir):
        # Dynamic input files for RAMMS Stage 3 are the result file of each
        # RAMMS Core avalanche.  Each avalanche produced a .dom,
        # .log.zip, .out.gz and .xy-coord.gz file.  If there are
        # missing files, they will not be included.  We must account
        # for The possibility that not all intended avalanche
        # simulations were able to run.
        xferRE = re.compile('|'.join(r'^[^.]*{}$'.format(ext)
            for ext in (r'\.dom', r'\.log\.zip', r'\.out\.gz', r'\.xy-coord\.gz')))

        inputs = list()
        for path,dirs,files in os.walk(os.path.join(ramms_dir, 'RESULTS')):
            for f in files:
                if xferRE.match(f) is not None:
                    inputs.append(os.path.join(path, f))

        
        # Run RAMMS and sync files back
        dynamic_outputs = run_ramms(hostname, ramms_dir, 3, inputs, HARNESS_REMOTE)    # Bash-style names on remote Windows
        return dynamic_outputs

    return make.Rule(action, inputs, outputs)
# --------------------------------------------------------------------
#    # Unpack / gzip individual avalanche .zip files
#
#    # rsync to 
#
#Send: .dom, .log.zip, .out.gz, .xy-coord.gz
#
#
#-rw-r--r-- 1 efischer Domain Users     104 Jan 17 18:58 juneau1_For_5m_30L_3743.dom
#-rw-r--r-- 1 efischer Domain Users   57858 Jan 18 08:17 juneau1_For_5m_30L_3743.out.gz
#-rw-r--r-- 1 efischer Domain Users    6180 Jan 18  2023 juneau1_For_5m_30L_3743.out.log
#-rw-r--r-- 1 efischer Domain Users 5392660 Jan 17 19:02 juneau1_For_5m_30L_3743.xy-coord
#
#
## Gunzip files; leave original .gz in scratch dir
#for ext in ('var', 'xy-coord', 'xyz'):
#    ifname = os.path.join(RAMMS_DIR, f'{base}.{ext}.gz')
#    ofname = os.path.join(RAMMS_DIR, f'{base}.{ext}')
#    with gzip.open(ifname, 'rb') as fin:
#        with open(ofname, 'wb') as out:
#            shutil.copyfileobj(fin, out)
#
#
#
#    pass





# =============================================================================
# =============================================================================
# Code not currently being used; but will need it for domain enlarging

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




# Operations for command line program:
# 1. show status of overall RAMMS run / single release shapefile / single avalanche
# 2. Inspect single run: show domain size, and other stuff
# 3. Mark a shapefile complete IN SPITE OF outstanding failed avlanches
#
# Try grepping the out.log file as soon as the run completes, mark it as bad immediately somehow

# -------------------------------------------------------
#def inspect_job(ramms_dir, job_name):
#    prefix,suffix = parse_job_name(job_name)

