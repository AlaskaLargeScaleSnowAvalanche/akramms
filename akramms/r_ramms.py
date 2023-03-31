import os,subprocess,re,sys,itertools,gzip,collections,io,typing,codecs
import numpy as np
import datetime,time,zipfile
import contextlib
import itertools, functools,shutil
import numpy as np
import htcondor
from akramms import config,params
from akramms.util import harnutil,rammsutil
from uafgi.util import make,ioutil,shputil
import pandas as pd


def setlink_or_copy(ifile, ofile):
    if config.shared_filesystem:    # No symlinks for Windows
        if os.path.islink(ofile) or not os.path.exists(ofile):
            os.makedirs(os.path.dirname(ofile), exist_ok=True)
            shutil.copy(ifile, ofile)
    else:
        ioutil.setlink(ifile, ofile)

# --------------------------------------------------------------------
scenario_tpl = \
r"""LSHM    {scenario_name}
MODULE  AVAL
MUXI    VARIABLE
DIR     {remote_ramms_dir}\
DEM     DEM\
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

def dem_forest_links(scene_args, ramms_dir, oslope_name, forest=False):
    """
    ramms_dir:
        RAMMS directory where FOREST and DEM files are being created
    """

    # ---- DEM File
    idem_dir,idem_tif = os.path.split(scene_args['dem_file'])
    idem_stub = idem_tif[:-4]
    links = [
        (os.path.join(idem_dir, f'{idem_stub}.tif'),
            os.path.join(ramms_dir, 'DEM', f'{oslope_name}_DEM.tif')),
        (os.path.join(idem_dir, f'{idem_stub}.tfw'),
            os.path.join(ramms_dir, 'DEM', f'{oslope_name}_DEM.tfw')),
    ]


    # ---- Forest File
    if forest:
        iforest_dir,iforest_tif = os.path.split(scene_args['forest_file'])
        iforest_stub = iforest_tif[:-4]
        links += [
            (os.path.join(iforest_dir, f'{iforest_stub}.tif'),
                os.path.join(ramms_dir, 'FOREST', f'{oslope_name}_forest.tif')),
            (os.path.join(iforest_dir, f'{iforest_stub}.tfw'),
                os.path.join(ramms_dir, 'FOREST', f'{oslope_name}_forest.tfw')),
        ]

    return links

def write_scenario_txt(jb, alt_lim_top=1500, alt_lim_low=1000, ncpu=config.ramms_ncpu, ncpu_preprocess=config.ramms_ncpu_preprocess, cohesion=50):
        # Create the scenario file
        kwargs = dict()
        kwargs['scenario_name'] = jb.ramms_name
        kwargs['remote_ramms_dir'] = config.roots.convert_to(jb.ramms_dir, config.roots_w)
        kwargs['ncpu'] = str(ncpu)
        kwargs['ncpu_preprocess'] = str(ncpu_preprocess)
        kwargs['cohesion'] = str(cohesion)
        if config.debug:
            kwargs['debug'] = '1'
            kwargs['keep_data'] = '1'
            kwargs['test_nr_tpl'] = "TEST_NR    20\n"
        else:
            kwargs['debug'] = '0'
            kwargs['keep_data'] = '1'
            kwargs['test_nr_tpl'] = ""
        kwargs['alt_lim_top'] = str(alt_lim_top)
        kwargs['alt_lim_low'] = str(alt_lim_low)

        scenario_txt = os.path.join(jb.ramms_dir, 'scenario.txt')
        os.makedirs(jb.ramms_dir, exist_ok=True)
        with open(scenario_txt, 'w') as out:
            out.write(scenario_tpl.format(**kwargs))


def rammsdir_rule(scene_dir, release_file, oramms_name=None, **scenario_kwargs):

    """Generates the scenario file, which becomes key to running RAMMS.
    release:
        Release file to process
    oramms_name:
        Output RAMMS directory to create
    """
    jb = rammsutil.parse_release_file(release_file)
    if oramms_name is None:
        oramms_name = jb

    scene_args = params.load(scene_dir)
    resolution = scene_args['resolution']
    name = scene_args['name']
    scenario_txt = os.path.join(jb.ramms_dir, 'scenario.txt')

    links = dem_forest_links(scene_args, jb.ramms_dir, oramms_name.slope_name, forest=jb.forest)

    def action(tdir):
        # Make symlinks for DEM file, etc.
        for ifile,ofile in links:
            setlink_or_copy(ifile, ofile)

        # Write scenario.txt
        write_scenario_txt(jb, **scenario_kwargs)

        # Generate .rel and .dom files

    inputs = [d[0] for d in links]
    linked_files = [d[1] for d in links]
    outputs = [scenario_txt] + linked_files
    return make.Rule(action, inputs, outputs)
# --------------------------------------------------------------------
def ramms_stage1_rule(release_file, inputs, dry_run=False, submit=False):
    """Runs Stage 1 of RAMMS (IDL code prepares individual avalanche runs)

    inputs:
        All input files for the RAMMS run (superset of release_files)
    """

    jb = rammsutil.parse_release_file(release_file)
    #logfile = os.path.join(jb.ramms_dir, 'RESULTS', 'lshm_rock.log')

    # Write extra output files to show we finished stage1 for a particular release file
    done_output = os.path.join(jb.ramms_dir, 'RESULTS', f'{jb.ramms_name}_stage1.txt')

    def action(tdir):

        ramms_dir_rel = config.roots.relpath(jb.ramms_dir)
        cmd = ['sh', 
            config.roots_w.join('HARNESS', 'akramms', 'sh', 'run_ramms.sh', bash=True),
            '--ramms-version', config.ramms_version,
            config.roots_w.syspath(ramms_dir_rel, bash=True), '1']    # '1'=stage 1

        # RAMMS Stage 1 accepts inputs on stdin
        # rammsdist.run_on_windows_stage() calls read_inputs()
        dynamic_outputs = harnutil.run_remote(inputs, cmd, tdir, write_inputs=True)

        # Write output files
        with open(done_output, 'w') as out:
            out.write('Finished RAMMS Stage 1\n')

        # Submit the individual avalanche runs immediately so we can
        # get going while preparing more RAMMS directories.
        if submit:
            submit_jobs([release_file])

        return dynamic_outputs

    return make.Rule(action, inputs, [done_output])

# =========================================================================================
# ===== RAMMS Stage 2: Manage avalanche jobs

# ---------------------------------------------------------------
#DOCKER_IMAGE = 'localhost:5000/ramms'
#DOCKER_IMAGE = 'git.akdggs.com/efischer/ramms:230210.2'

DOCKER_TAG = config.docker_tag()

submit_tpl = \
"""universe                = docker
docker_image            = {DOCKER_TAG}
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
#        cmd = ['docker', 'run', DOCKER_TAG, '/usr/bin/python', '/opt/runaval.py', job_name]
#        subprocess.run(cmd, cwd=run_dir, check=True)
#        return



    print('Submitting job: {}'.format(job_name))
    submit_txt = submit_tpl.format(job_name=job_name, run_dir=run_dir, DOCKER_TAG=DOCKER_TAG)

    cmd = ['condor_submit', '-batch-name', job_name]
    print(' '.join(cmd) + '<<EOF')
    print(submit_txt)
    print('EOF')
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
    jobRE_str = r'^{}_([0-9]+)$'.format(jb.ramms_name)
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
        jobRE_str = r'^{}_([0-9]+)$'.format(jb.ramms_name)
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
        job_suffixes = dict(analyze_rundir(jb.avalanche_dir, jb.ramms_name))

        # --------------------------------------------------

        # Consider each job in turn from our master list
        for id in ids:
            key = (jb.avalanche_dir, id)

            job_name = f'{jb.ramms_name}_{id}'

            # If nothing for this key exists, then probably top-level
            # RAMMS has not been run yet for this run_dir
            if id not in job_suffixes:
                statuses.append((jb.avalanche_dir, id, JobStatus.NOINPUT))
                continue
            suffixes = job_suffixes[id]

            # Mark as INCOMPLETE if not all input files are there
            input_suffixes = ('rel', 'dom', 'av2', 'var.gz', 'xy-coord.gz', 'xyz.gz')
            ninputs = sum(x in suffixes for x in input_suffixes)

            if ninputs == 0:
                statuses.append((jb.avalanche_dir, id, JobStatus.NOINPUT))
                continue

            if ninputs < len(input_suffixes):
                statuses.append((jb.avalanche_dir, id, JobStatus.INCOMPLETE))
                continue


            # See if Condor tells is what's going on with the job
            if job_name in condor_statuses:
                statuses.append((jb.avalanche_dir, id, condor_statuses[job_name]))
                continue

            # Not in Condor?  Either it hasn't launched, or it's finished / failed
            # Let's look at the files on disk to decide.

            # Identify avalanches that have finished: .out.gz exists and has non-zero size
            # (User can reset jobs by removing *.job.log)
            if ('log.zip' in suffixes) and ('out.gz' in suffixes):
                log_zip = os.path.join(jb.avalanche_dir, '{}_{}.log.zip'.format(jb.ramms_name, id))

                # Check for abandoned job
                statinfo = os.stat(log_zip)
                if (statinfo.st_size==0):
                    # The HTCondor output file has been created, but
                    # no sign of the HTCondor job to write it at the
                    # end.  Sounds like things were killed, send
                    # status back to TODO.
                    statuses.append((jb.avalanche_dir, id, JobStatus.TODO))
                    continue

                # We tentatively think the job is finished.  But let's
                # look inside the zip file to make sure the domain
                # wasn't overrun.
                with zipfile.ZipFile(log_zip, 'r') as in_zip:
                    arcnames = [os.path.split(x)[1] for x in in_zip.namelist()]
                if any(x.endswith('.out.overrun') for x in arcnames):
                    statuses.append((jb.avalanche_dir, id, JobStatus.OVERRUN))
                else:
                    statuses.append((jb.avalanche_dir, id, JobStatus.FINISHED))
                continue

            # Default to TODO
            statuses.append((jb.avalanche_dir, id, JobStatus.TODO))


    df = pd.DataFrame(statuses, columns=('run_dir', 'id', 'job_status'))
    df = df.sort_values(by=['run_dir', 'job_status', 'id'])
    return df
# --------------------------------------------------------
def print_job_statuses(df):
    for (run_dir, job_status), group in df.groupby(['run_dir', 'job_status']):

        print('=========== {} {}:'.format(job_status_labels[job_status], run_dir))
        print(sorted(group['id'].tolist()))


# --------------------------------------------------------------------
def submit_jobs(release_files, ids=None):
    """Does an initial (or subsequent) submit of jobs for a set of
    release files.  Submits jobs that can be submitted, and that have
    not yet been.

    Returns:
        df:
            Job statuses BEFORE submissions were made
    """

    print('release_files = ',release_files)
    df = job_statuses(release_files)
    df = df[df.job_status.isin({JobStatus.TODO, JobStatus.OVERRUN})]
#    print('df = ',df)
    for _,row in df.iterrows():
        if ids is None or row['id'] in ids:
            parts = row['run_dir'].split(os.sep)
            job_name = '{}_{}_{}'.format(parts[-2], parts[-1], row['id'])
            print('submit ', row['run_dir'], job_name)
            submit_job(row['run_dir'], job_name)

    return df

# -------------------------------------------------------
# ======================================================================
# ============= RAMMS Stage 2: Enlarge and re-submit domains that overran

# -----------------------------------------------------------
def enlarge_domain(run_dir, job_name, enlarge_increment=5000.):

    # Read the .dom file and make it bigger by 1000m
    dom_file = os.path.join(run_dir, f'{job_name}.dom')
    log_zip_file = os.path.join(run_dir, f'{job_name}.log.zip')
    dom0 = rammsutil.read_polygon(dom_file)
    dom1 = rammsutil.add_margin(dom0, enlarge_increment)
    with np.printoptions(precision=0, suppress=True):
        print('{}:\n  {} -> {}'.format(job_name, rammsutil.edge_lengths(dom0), rammsutil.edge_lengths(dom1)))

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
        rammsutil.write_polygon(dom1, dom_file)    # New timestamp


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
#            submit_job(run_dir, job_name)

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
    ramms_spec:
        Spec indicating the release file(s) to include in the iteration
    ids: [int, ...]
        Avalanche IDs to include.
        If empty list, that means include all of them.
    """

    release_files = rammsutil.get_release_files(ramms_spec)

    rf_by_id = dict()
    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)
        for id in get_job_ids(release_file):
            rf_by_id[id] = jb

    for id in ids:
        yield rf_by_id[id],id


# https://stackoverflow.com/questions/34447623/wrap-an-open-stream-with-io-textiowrapper
def cat(ramms_spec, ids=list(), out_bytes=sys.stdout.buffer):
    out_text = codecs.getwriter('utf-8')(out_bytes)
    for jb,id in ramms_iter(ramms_spec, ids=ids):
        log_zip = jb.log_zip(id)
        with zipfile.ZipFile( log_zip, 'r') as izip:
            print('======== {}'.format(log_zip), file=out_text)
            sys.stdout.flush()
            bytes = izip.read(jb.arcname(id, '.out.log'))
            out_bytes.write(bytes)

            #os.write(1, bytes)    # 1 = STDOUT
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
            job_name = f'{jb.ramms_name}_{id}'
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



def assemble_stage3(oramms_name, release_files):
    """Iterates through a set of avalanches by spec
    ramms_spec:
        Spec indicating the release file(s) to include in the iteration
    """

#    oramms_dir = oramms_name.ramms_dir
#    print('oramms_dir ', oramms_dir)


# ADDITIONAL STUFF NEEDED IN ORAMMS DIRECTORY
# 
# * ORAMMS/juneau100030LFor_5m does not match ORAMMS/juneau100030LFor_5m/RESULTS/juneau1For_5m
#  (both should be called juneau130LFor_5m???)
# 
# * scenario.txt file (and must edit its name as well)
# 
# * DEM and FOREST files
#  2021  cp -r ../../RAMMS/juneau100030LFor_5m/FOREST .
#  2022  cp -r ../../RAMMS/juneau100030LFor_5m/DEM .
# 
# * DOMAIN and RELEASE files
#  2029  cp ../../RAMMS/juneau100030LFor_5m/RELEASE/*_rel.??? RELEASE/
#  2030  mkdir DOMAIN
#  2031  cp ../../RAMMS/juneau100030LFor_5m/DOMAIN/*_dom.??? DOMAIN/
#  2032  history
# (base) efischer@antevorta:~/prj/juneau1/ORAMMS/juneau100030LFor_5m$ 



#    # Construct a fresh output directory...
#    try:
#        shutil.rmtree(oramms_dir)
#    except FileNotFoundError:
#        pass

    # Write scenario.txt
    write_scenario_txt(oramms_name)

    # Copy / Symlink DEM and FOREST files
    jb = rammsutil.parse_release_file(release_files[0])
    scene_args = params.load(oramms_name.scene_dir)
    links = dem_forest_links(scene_args, oramms_name.ramms_dir, oramms_name.slope_name, forest=jb.forest)
    links.append((
        os.path.join(jb.scene_dir, 'scene.nc'),
        os.path.join(oramms_name.scene_dir, 'scene.nc')))

    # Do the copies!
    for ifile,ofile in links:
        setlink_or_copy(ifile, ofile)

    # Decide on what the _rel.shp and _dom.shp files should be called
    orel_base = os.path.join(oramms_name.ramms_dir, 'RELEASE', oramms_name.reldom_name+'_rel')
    odom_base = os.path.join(oramms_name.ramms_dir, 'DOMAIN', oramms_name.reldom_name+'_dom')

    # Find all available individual runs
    for ix,release_file in enumerate(release_files):
        jb = rammsutil.parse_release_file(release_file)
        ids = get_job_ids(release_file)

        # Copy _rel.shp and _dom.shp files
        irel_base = os.path.join(jb.ramms_dir, 'RELEASE', jb.reldom_name+'_rel')
        idom_base = os.path.join(jb.ramms_dir, 'DOMAIN', jb.reldom_name+'_dom')

#        irel_base = os.path.splitext(release_file)[0]
#        irel_baseleaf = os.path.split(irel_base)[1]
#        idom_base = (irel_base[:-4] + '_dom').replace('RELEASE', 'DOMAIN')
#
#        orel_base = os.path.join(oramms_name.ramms_dir, 'RELEASE', irel_baseleaf)
#        odom_base = os.path.join(oramms_name.ramms_dir, 'DOMAIN', irel_baseleaf)

        # Merge shapefiles
        links = list()
#        for ext in ('.dbf', '.prj', '.shp', '.shx'):
#            links.append((f'{irel_base}{ext}', f'{orel_base}{ext}'))
#            links.append((f'{idom_base}{ext}', f'{odom_base}{ext}'))
        links.append((f'{irel_base}.shp', f'{orel_base}.shp'))
        links.append((f'{idom_base}.shp', f'{odom_base}.shp'))

        for ifile,ofile in links:
            print('MERGE: {} -> {}'.format(ifile, ofile))
#            setlink_or_copy(ifile, ofile)
            os.makedirs(os.path.dirname(ofile), exist_ok=True)
            if ix == 0:
                # https://gis.stackexchange.com/questions/223183/ogr2ogr-merge-multiple-shapefiles-what-is-the-purpose-of-nln-tag
                cmd = ['ogr2ogr', '-f', 'gpkg', ofile, ifile]
            else:
                cmd = ['ogr2ogr', '-f', 'gpkg', '-append', '-update', ofile, ifile]
            subprocess.run(cmd, check=True)

#        oslope_dir = os.path.join(oramms_dir, 'RESULTS',
#            f'{jb.scene_name}{jb.For}_{jb.resolution}m')
#        oavalanche_dir = os.path.join(oslope_dir,
#            f'{jb.return_period}{jb.pra_size}')
        oslope_dir = oramms_name.slope_dir
        oavalanche_dir = oramms_name.avalanche_dir
            
        ireleasefile_dir = os.path.split(release_file)[0]

#        ibase = f'{jb.scene_name}{jb.ssegment}{jb.For}_{jb.resolution}m_{jb.return_period}{jb.pra_size}'
#        obase = f'{jb.scene_name}{jb.For}_{jb.resolution}m_{jb.return_period}{jb.pra_size}'

        # Figure out which avalanches have been run
        required_exts = {'.dom', '.rel', '.out.gz', '.xy-coord.gz'}
        id_exts = dict()
        ifileRE = re.compile(r'{}_(\d+)(\..+)'.format(jb.ramms_name))
        for leaf in os.listdir(jb.avalanche_dir):
            # Make sure file exists in non-zero length
            ifile = os.path.join(jb.avalanche_dir, leaf)
            if os.path.getsize(ifile) == 0:
                continue

            match = ifileRE.match(leaf)
            if match is not None:
                id = int(match.group(1))
                ext = match.group(2)
                if ext in required_exts:
                    if id in id_exts:
                        id_exts[id].add(ext)
                    else:
                        id_exts[id] = {ext}

        # Copy files that have complete outputs
        os.makedirs(oavalanche_dir, exist_ok=True)
        for id,exts in id_exts.items():
            print(id,exts)
            if len(exts) < len(required_exts):
                continue
            for ext in exts:
                ifname = os.path.join(jb.avalanche_dir, f'{jb.ramms_name}_{id}{ext}')
                ofname = os.path.join(oavalanche_dir, f'{oramms_name.ramms_name}_{id}{ext}')
                shutil.copy(ifname, ofname)


def run_ramms_stage3(oramms_name):
    oramms_dir = oramms_name.ramms_dir
    oramms_dir_rel = config.roots.relpath(oramms_dir)
    cmd = ['sh', 
        config.roots_w.join('HARNESS', 'akramms', 'sh', 'run_ramms.sh', bash=True),
        '--ramms-version', config.ramms_version,
        config.roots_w.syspath(oramms_dir_rel, bash=True), '3']    # '3'=stage 3
    with ioutil.TmpDir() as tdir:
        dynamic_outputs = harnutil.run_remote([], cmd, tdir, write_inputs=False)

    return dynamic_outputs



def ramms_stage3_rule(ramms_dir, release_files):
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
        input = os.path.join(ramms_dir, 'RESULTS', f'{jb.ramms_name}_stage2.txt')
        inputs.append(input)

        # -----------------------------------------------------------
        # Outputs are the end-user GeoTIFF files that RAMMS Stage 3 writes.

        # Misc. Files
        for leaf in ('curvidl.tif', 'slope.tif', 'logfiles/muxi_altlimits.log', 'logfiles/muxi_class.tif'):
            outputs.append(os.path.join(jb.slope_dir, leaf))

        # The main GeoTIFF Files
        base = os.path.join(dir, '{}_{}'.format(jb.prefix, jb.suffix))    # Eg: juneau1_For_5m_30L
        for ext in (
            '.dbf', '.shp', '.shx',
            '_AblagerungStef.tif', '_COUNT.tif', '_ID.tif', '_Xi.tif',
            '_maxHeight.tif', '_maxPRESSURE.tif', '_maxVelocity.tif'):
            outputs.append(os.path.join(jb.ramms_dir, f'{jb.ramms_name}{ext}'))

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
        #dynamic_outputs = run_ramms(ramms_dir, 3, inputs)

        cmd = ['sh', 
            config.roots_w.join('HARNESS', 'akramms', 'sh', 'run_ramms.sh', bash=True),
            '--ramms-version', config.ramms_version,
            config.roots_w.syspath(ramms_dir_rel, bash=True), '3']    # '3'=stage 3
        # rammsdist.run_on_windows_stage() does not call read_inputs()
        dynamic_outputs = harnutil.run_remote(inputs, cmd, tdir, write_inputs=False)

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

