# =========================================================================================
# ===== RAMMS Stage 2: Manage avalanche jobs

# ---------------------------------------------------------------
#DOCKER_IMAGE = 'localhost:5000/ramms'
#DOCKER_IMAGE = 'git.akdggs.com/efischer/ramms:230210.2'

DOCKER_TAG = config.docker_tag()

#requirements = opsys == 'WINDOWS'
submit_tpl = \
"""universe                = docker
docker_image            = {DOCKER_TAG}
executable              = /usr/bin/python
arguments               = /opt/runaval.py {job_name}

initialdir              = {run_dir}
transfer_input_files    = {job_name}.in.zip
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

#def analyze_rundir(run_dir, job_base):
#    """Find all avalanche files in the run_dir related to this shapefile
#    Returns: {id: [suffix, ...], ...}
#        For each avalanche ID in run_dir, a list of the related files
#        that exist, identified by filename suffix.
#
#        Eg: if avalanche ID 8733 exists in run_dir, an entry might look like:
#            8733: {'av2', 'xyz.gz', 'xy-coord.gz', 'var.gz', 'dom', 'rel', ...}
#
#    """
#    job_fileRE = re.compile(r'^{}_(\d+)\.(.*)$'.format(job_base))
#    id_suffixes = list()    # [(id,suffix), ...]
#    if os.path.isdir(run_dir):
#        for leaf in os.listdir(run_dir):
#            match = job_fileRE.match(leaf)
#            if match is None:
#                continue
#            id_suffixes.append((int(match.group(1)), match.group(2)))
#    id_suffixes.sort()
#
#    # Create: suffixes = {id0: {suffixes}, id1: {suffixes}, ...}
#    return ((id,set(x[1] for x in tuples)) \
#        for id,tuples in itertools.groupby(id_suffixes, lambda x: x[0]))


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


def get_mtime(fname):
    if os.path.exists(fname):
        return os.path.getmtime(fname)
    else:
        return -1

@functools.lru_cache()
def query_condor():
    # TODO: Make sure this distinguishes by experiment!!!

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

    return condor_statuses



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

_subsceneRE = re.compile(r'x-(\d+-\d+)')
def add_combo_job_status(xdir, akdf0):
    """Determines status of ALL Condor jobs for a RAMMS run.
    akdf0:
        Avalanche dataframe, resolved to the ID level with scenetype='x' and index='id'
        Must all ahve the same combo (scenedir)
    """


    # Corresponding archive location
    arcdir = xdir.parents[0] / 'arc'+xdir.parts[-1][1:]
    condor_statuses = query_condor()


    for releasefile,akdf1 in akdf0.groupby('releasefile'):
        jb = rammsutil.parse_release_file(release_file)

        # Consider each job in turn from our master list
        for tup in akdf1.itertuples():
            id = tup.id

            for id in ids:
                key = (jb.avalanche_dir, id)
                job_name = f'{jb.ramms_name}_{id}'

                # Mark as NOINPUT if the .in.zip file is not there.
                if not os.path.exists(os.path.join(jb.avalanche_dir, f'{job_name}.in.zip')):
                    statuses.append((release_file, jb, id, JobStatus.NOINPUT))
                    continue

                # See if Condor knows is what's going on with the job
                if job_name in condor_statuses:
                    statuses.append((release_file, jb, id, condor_statuses[job_name]))
                continue

                # Not in Condor?  Either it hasn't launched, or it's finished / failed
                # Let's look at the files on disk to decide.

                in_zip = os.path.join(jb.avalanche_dir, f'{job_name}.in.zip')
                in_zip_tm = get_mtime(in_zip)
                out_zip = os.path.join(jb.avalanche_dir, f'{job_name}.out.zip')
                out_zip_tm = get_mtime(out_zip)

                # If an archive NetCDF file exists, then this avalanche is FINISHED.
                if archive_dir is not None:
                    aval_nc = os.path.join(archive_dir, f'aval-{id}.nc')
                    if os.path.exists(aval_nc):
                        aval_nc_tm = os.path.getmtime(aval_nc)
                        if (aval_nc_tm > out_zip_tm) and (out_zip_tm > in_zip_tm):
                            # .nc files only "count" if they are newer than raw files
                            # (or those raw files don't exist)
                            statuses.append((release_file, jb, id, JobStatus.FINISHED))
                            continue

                # Identify avalanches that have finished: .out.zip exists and has non-zero size
                # (User can reset jobs by removing *.out.zip)
                if os.path.exists(out_zip):

                    # Check for abandoned job
                    # TODO: Use file_is_good() instead!
                    statinfo = os.stat(out_zip)
                    if (statinfo.st_size==0):
                        # The HTCondor output file has been created, but
                        # no sign of the HTCondor job to write it at the
                        # end.  Sounds like things were killed, send
                        # status back to TODO.
                        statuses.append((release_file, jb, id, JobStatus.TODO))
                        continue

                    # We tentatively think the job is finished.  But let's
                    # look inside the zip file to make sure the domain
                    # wasn't overrun.
                    with zipfile.ZipFile(out_zip, 'r') as ozip:
                        arcnames = [os.path.split(x)[1] for x in ozip.namelist()]
                    if any(x.endswith('.out.overrun') for x in arcnames):
                        statuses.append((release_file, jb, id, JobStatus.OVERRUN))
                    else:
                        statuses.append((release_file, jb, id, JobStatus.FINISHED))
                    continue

                # Default to TODO
                statuses.append((release_file, jb, id, JobStatus.TODO))

    statuses = [(id, status, jb.key())] for release_file,jb,id,status in statuses]
    df = pd.DataFrame(statuses, columns=('id', 'jobstatus', 'jbkey')
    return akdf1.merge(df, left_index=True, right_on='id').
# --------------------------------------------------------
_include_statuses = {JobStatus.NOINPUT, JobStatus.INCOMPLETE, JobStatus.TODO, JobStatus.INPROCESS, JobStatus.OVERRUN, JobStatus.FAILED}
def print_job_statuses(df):
#    for (run_dir, job_status), group in df.groupby(['run_dir', 'job_status']):
    for (jb_key, job_status), group in df.groupby(['jb_key', 'job_status']):
        if job_status not in _include_statuses:
            continue
        jb = jb_key[-1]

        print('=========== {} {}:'.format(job_status_labels[job_status], jb.avalanche_dir))
        print(sorted(group.index.tolist()))
#        print(sorted(group['id'].tolist()))


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
    df = df[df.job_status.isin({JobStatus.TODO, JobStatus.OVERRUN})]
#    print('df = ',df)
    for _,row in df.iterrows():
        if ids is None or row['id'] in ids:
            run_dir = row['jb'].avalanche_dir
            parts = run_dir.split(os.sep)
            job_name = '{}_{}_{}'.format(parts[-2], parts[-1], row['id'])
            print('submit ', run_dir, job_name)
            submit_job(run_dir, job_name)

    return df
