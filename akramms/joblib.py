import os,subprocess,functools,re,typing,zipfile,enum,sys
import htcondor
import pandas as pd
from akramms import config,file_info,parse,level,complete,resolve

# Categorize each job int one of four sets
#job_status_labels = ('noinput', 'incomplete', 'todo', 'inprocess', 'finished', 'overrun', 'failed')
class JobStatus(enum.IntEnum):
    TODO = 0         # Ready to submit to HTCondor but no evidence that has been done
    INPROCESS = 1    # HTCondor is dealing with it
    NOINPUT = 2         # No RAMMS input files exist
    INCOMPLETE = 3   # Some but not all RAMMS input files exist
    FAILED = 4       # The job finished but did not produce full / correct output
    OVERRUN = 5      # Avalanche overran the boundary; auto-resubmit
    FINISHED = 6     # The avalanche (or chunk or combo) has finished, and it's successful
    MARKED_FINISHED = 7       # Chunk or combo has finished, and has been marked as such (shortcut)
    ARCHIVED = 8    # For combos: It's been fully archived to an arc directory

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
arguments               = /opt/runaval.py {inout_name}

initialdir              = {run_dir}
transfer_input_files    = {inout_name}.in.zip
transfer_output_files   = {inout_name}.out.zip
should_transfer_files   = YES
when_to_transfer_output = ON_EXIT
on_exit_hold            = False
on_exit_remove          = True

output                  = {inout_name}.job.out
error                   = {inout_name}.job.err
log                     = {inout_name}.job.log
request_cpus            = 1
request_memory          = 1000M
queue 1
"""

def submit_job(run_dir, job_name, inout_name):#, local=False):
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
    submit_txt = submit_tpl.format(job_name=job_name, inout_name=inout_name, run_dir=run_dir, DOCKER_TAG=DOCKER_TAG)

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


class JobInfo(typing.NamedTuple):
    combo: object
    chunkid: int
    id: int    # Avalanche ID

def get_mtime(fname):
    if os.path.exists(fname):
        return os.path.getmtime(fname)
    else:
        return -1

@functools.lru_cache()
def query_condor(expmod):
    # TODO: Make sure this distinguishes by experiment!!!

    # Query Condor
    schedd = htcondor.Schedd()   # get the Python representation of the scheduler
    #nfields = len(expmod.combo_keys) + 1
    jobRE_str = expmod.name + r'-([^-]*)' * (len(expmod.combo_keys) + 2 - 1)
    #jobRE_str = r'^{}_([0-9]+)$'.format(jb.ramms_name)
    jobRE = re.compile(jobRE_str)    # Compile to make sure the RE works
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
        parts= job_name.split('-')
        #expmod = parse.load_expmod(parts[0])
#        print('parts ', parts)
        combo = parse.new_combo(expmod, parts[1:-3])
        id = int(parts[-3])
        chunkid = int(parts[-1])

        job_info = JobInfo(combo, chunkid, id)

       
        if 'JobPartition' in ad:
            jp = ad['JobPartition']
            try:
                condor_statuses[job_info] = op_by_status[jp]
            except:
                pass
        else:
            # It's been submitted but not yet run
            condor_statuses[job_info] = JobStatus.INPROCESS

    return condor_statuses



# --------------------------------------------------------------------
def is_overrun(out_zip):
    """Determines whether a RAMMS result is overrun"""
    with zipfile.ZipFile(out_zip, 'r') as ozip:
        arcnames = [os.path.split(x)[1] for x in ozip.namelist()]
    return any(x.endswith('.out.overrun') for x in arcnames)

# --------------------------------------------------------------------

_subsceneRE = re.compile(r'x-(\d+-\d+)')
def add_id_status(akdf0):
    """Determines status of ALL Condor jobs for a RAMMS run.
    akdf0:
        Avalanche dataframe, resolved to the ID level with scenetype='x' and index='id'
        Must all have the same combo (scenedir)
    """

    # Make it idempotent
    if 'id_status' in akdf0.columns:
        return akdf0

    statuses = list()

    print('xxxxxxxxxxx ')
    print(akdf0)
    print(akdf0.columns)
    for exp,akdf1 in akdf0.groupby('exp'):
        expmod = parse.load_expmod(exp)

        # Pick up what info we can from HTCondor
        condor_statuses = query_condor(expmod)

        for combo,akdf2 in akdf1.groupby('combo'):
            xdir = expmod.combo_to_scenedir(combo, 'x')
            # Corresponding archive location
            arcdir = xdir.parents[0] / ('arc' + xdir.parts[-1][1:])

            for (chunkid,releasefile),akdf3 in akdf2.groupby(['chunkid', 'releasefile']):
                jb = file_info.parse_chunk_release_file(releasefile)

                for tup in akdf3.itertuples():
                    job_info = JobInfo(combo, tup.chunkid, tup.id)

                    #job_name = f'{jb.slope_name}_{jb.avalanche_name}_{id}'
                    inout = file_info.inout_name(jb, tup.chunkid, tup.id)
                    in_zip = jb.avalanche_dir / f'{inout}.in.zip'

                    # Mark as NOINPUT if the .in.zip file is not there.
                    if not os.path.exists(in_zip):
                        statuses.append((tup.combo, chunkid, tup.id, JobStatus.NOINPUT))
                        continue

                    # See if Condor knows is what's going on with the job
                    if job_info in condor_statuses:
                        statuses.append((tup.combo, chunkid, tup.id, condor_statuses[job_info]))
                        continue

                    # Not in Condor?  Either it hasn't launched, or it's finished / failed
                    # Let's look at the files on disk to decide.

                    in_zip_tm = get_mtime(in_zip)
                    out_zip = jb.avalanche_dir / f'{inout}.out.zip'
                    out_zip_tm = get_mtime(out_zip)

                    # If an archive NetCDF file exists, then this avalanche is FINISHED.
                    if arcdir is not None:
                        aval_nc = os.path.join(arcdir, f'aval-{id}.nc')
                        if os.path.exists(aval_nc):
                            aval_nc_tm = os.path.getmtime(aval_nc)
                            if (aval_nc_tm > out_zip_tm) and (out_zip_tm > in_zip_tm):
                                # .nc files only "count" if they are newer than raw files
                                # (or those raw files don't exist)
                                statuses.append((tup.combo, chunkid, tup.id, JobStatus.FINISHED))
                                continue

                    # Identify avalanches that have finished: .out.zip exists and has non-zero size
                    # (User can reset jobs by removing *.out.zip)
                    if os.path.exists(out_zip):

                        # Check for abandoned job
                        # TODO: Use is_file_good() instead!
                        statinfo = os.stat(out_zip)
                        if (statinfo.st_size==0):
                            # The HTCondor output file has been created, but
                            # no sign of the HTCondor job to write it at the
                            # end.  Sounds like things were killed, send
                            # status back to TODO.
                            statuses.append((tup.combo, chunkid, tup.id, JobStatus.TODO))
                            continue

                        # We tentatively think the job is finished.  But let's
                        # look inside the zip file to make sure the domain
                        # wasn't overrun.
                        statuses.append(
                            (combo, chunkid, tup.id,
                            JobStatus.OVERRUN if is_overrun(out_zip) else JobStatus.FINISHED) )
                        continue

                    # Default to TODO
                    statuses.append((tup.combo, chunkid, tup.id, JobStatus.TODO))


    df = pd.DataFrame(statuses, columns=('combo', 'chunkid', 'id', 'id_status'))

    # Keep only the avalanche from the most recent chunk
    # df = df.sort_values(['combo', 'id', 'chunkid'])    # Not needed
#    df.drop_duplicates(['combo', 'id'], keep='last', inplace=True)

    return akdf0.merge(df.reset_index(drop=True), how='left', left_on=['combo', 'chunkid', 'id'], right_on=['combo', 'chunkid', 'id'])
# --------------------------------------------------------
_include_statuses = {JobStatus.NOINPUT, JobStatus.INCOMPLETE, JobStatus.TODO, JobStatus.INPROCESS, JobStatus.OVERRUN, JobStatus.FAILED}
def print_job_statuses(akdf0):

    showall = (len(akdf0.index) <= 100)

    for (exp,combo),akdf1 in akdf0.reset_index(drop=True).groupby(['exp','combo']):
        scombo = '-'.join((str(x) for x in combo))
        print(f"=============== {exp}-{scombo}")

        for releasefile,akdf2 in akdf1.groupby('releasefile'):
            jb = file_info.parse_chunk_release_file(releasefile)
            print(f"----- {jb.avalanche_dir}")

            for jobstatus,akdf3 in akdf2.groupby('id_status'):
                if showall or (jobstatus in _include_statuses):
                    print('{}: {}'.format(repr(JobStatus(jobstatus)), sorted(akdf3.id.tolist())))




##    for (run_dir, job_status), group in df.groupby(['run_dir', 'job_status']):
#    for (jb_key, job_status), group in df.groupby(['jb_key', 'job_status']):
#        if job_status not in _include_statuses:
#            continue
#        jb = jb_key[-1]
#
#        print('=========== {} {}:'.format(job_status_labels[job_status], jb.avalanche_dir))
#        print(sorted(group.index.tolist()))
##        print(sorted(group['id'].tolist()))


# --------------------------------------------------------------------
def _submit_jobs(akdf):
    """Does an initial (or subsequent) submit of jobs for a set of
    release files.  Submits jobs that can be submitted, and that have
    not yet been.

    akdf:
        resolved to avalanche id
        Needs columns: releasefile, id

    Returns:
        df:
            Job statuses BEFORE submissions were made
    """

    for _,row in akdf.iterrows():
        jb = file_info.parse_chunk_release_file(row['releasefile'])

        # Eg: .../ak-ccsm-1981-1990-lapse-For-30/x-113-045/CHUNKS/c-L-00000/RESULTS/c-L-00000For_10m/30

        wcombo_name = jb.scene_dir.parts[-2]
        ij_name = jb.scene_dir.parts[-1][2:]
        id = row['id']
        job_name = f'{wcombo_name}-{ij_name}-{id}-{jb.pra_size}-{jb.chunkid:05}'
        inout = file_info.inout_name(jb, jb.chunkid, id)

        print('submit ', jb.avalanche_dir, job_name, inout)
        submit_job(jb.avalanche_dir, job_name, inout)

def submit_jobs(akdf):
    akdf = add_id_status(akdf)

    # Only submit jobs that are ready to go and not in process or completed or something.
    akdf = akdf[akdf.jobstatus == JobStatus.TODO]

    print('==================== Submitting:')
    print(akdf[['combo', 'chunkid', 'id']])
    _submit_jobs(akdf)

    return akdf
# ------------------------------------------------------------
