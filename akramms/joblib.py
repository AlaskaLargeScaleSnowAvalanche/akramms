import os,subprocess,functools,re,typing,zipfile,sys,contextlib,pathlib,glob,io,time
import htcondor2 as htcondor
import numpy as np
import pandas as pd
from uafgi.util import gdalutil
from akramms import config,file_info,parse,level,complete,resolve,archive,overrun,params,extent

# Categorize each job int one of four sets
#job_status_labels = ('noinput', 'incomplete', 'todo', 'inprocess', 'finished', 'overrun', 'failed')

JobStatus = file_info.JobStatus    # Alias

# =========================================================================================
# ===== RAMMS Stage 2: Manage avalanche jobs

# ---------------------------------------------------------------
#DOCKER_IMAGE = 'localhost:5000/ramms'
#DOCKER_IMAGE = 'git.akdggs.com/efischer/ramms:230210.2'

#docker_tag = config.docker_tag()

#requirements = opsys == 'WINDOWS'
#Requirements            = (Machine != "10.10.132.83")
#Requirements = (Name == "slot1@htcondor02.dnr.state.ak.us")
#Requirements = (Name != "slot1@khione.dnr.state.ak.us")
#Requirements            = (Machine != "10.10.132.212")

submit_tpl = \
"""universe                = docker
docker_image            = {docker_tag}
executable              = /usr/bin/python3
arguments               = /opt/runaval.py {inout_name}
initialdir              = {run_dir}
transfer_input_files    = {inout_name}.in.zip
transfer_output_files   = {inout_name}.out.zip
should_transfer_files   = YES
when_to_transfer_output = ON_EXIT
on_exit_hold            = False
on_exit_remove          = True
request_memory          = 3000M
output                  = {inout_name}.job.out
error                   = {inout_name}.job.err
log                     = {inout_name}.job.log
request_cpus            = 1
priority                = {condor_priority}
queue 1
"""
#Requirements            = (Machine == "khione.dnr.state.ak.us")
#request_memory          = 10000M
# Only a handful of jobs go over request_memory=1000M
# request_cpus --> --cpu-shares ==> nice



def submit_job(run_dir, job_name, inout_name, condor_priority=0):#, local=False):
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
#        cmd = ['docker', 'run', docker_tag, '/usr/bin/python', '/opt/runaval.py', job_name]
#        subprocess.run(cmd, cwd=run_dir, check=True)
#        return

    # Identify the RAMMS version (as of the last time it was built)
    version_txt = config.HARNESS / 'rammscore' / 'build' / 'version.txt'
    with open(version_txt) as fin:
        ramms_version = fin.read().strip()
    docker_tag = config.docker_tag(ramms_version)

    print('Submitting job: {}'.format(job_name))
    submit_txt = submit_tpl.format(job_name=job_name, inout_name=inout_name, run_dir=run_dir, docker_tag=docker_tag, condor_priority=condor_priority)

    # DEBUG
    with open('/home/efischer/tmp/avjob.txt', 'w') as out:
        out.write(submit_txt)

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
        combo = parse.new_combo(expmod, parts[1:-3])    # Take off idom,jdom,chunkid
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

# --------------------------------------------------------------
_subsceneRE = re.compile(r'x-(\d+-\d+)')
def add_id_status(akdf0, update=True, dry_run=False):
    """Determines status of ALL Condor jobs for a RAMMS run.
    akdf0:
        Avalanche dataframe, resolved to the ID level with scenetype='x' and index='id'
        Must all have the same combo (scenedir)
    """

    # Make it idempotent
    if 'id_status' in akdf0.columns:
        return akdf0

    statuses = list()

    for exp,akdf1 in akdf0.groupby('exp'):
        expmod = parse.load_expmod(exp)

        # Pick up what info we can from HTCondor
        condor_statuses = query_condor(expmod)

        for combo,akdf2 in akdf1.groupby('combo'):
            xdir = expmod.combo_to_scenedir(combo, 'x')
            scene_args = params.load(xdir)
            dem_tif = pathlib.Path(scene_args['dem_file'])
            dem_mask_tif = dem_tif.parents[0] / (dem_tif.parts[-1][:-4] + '_mask.tif')
            check_overruns = archive.OverrunChecker(dem_mask_tif)

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
                        xstat = \
                            (combo, chunkid, tup.id,
                            JobStatus.OVERRUN if check_overruns.is_overrun(in_zip, out_zip) else JobStatus.FINISHED)
#                        print('xstat ', xstat)
                        statuses.append(xstat)
                        continue

                    # Default to TODO
                    statuses.append((tup.combo, chunkid, tup.id, JobStatus.TODO))


    df = pd.DataFrame(statuses, columns=('combo', 'chunkid', 'id', 'id_status'))

    # Keep only the avalanche from the most recent chunk
    # df = df.sort_values(['combo', 'id', 'chunkid'])    # Not needed
#    df.drop_duplicates(['combo', 'id'], keep='last', inplace=True)

    akdf0 = akdf0.merge(df.reset_index(drop=True), how='left', left_on=['combo', 'chunkid', 'id'], right_on=['combo', 'chunkid', 'id'])

#    print('xxxxxxxxxxxxxxx 6570')
#    print(akdf0[akdf0.id==6570])
    
    if update:
        archive.archive_ids(akdf0, dry_run=dry_run)

    return akdf0
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

            for id_status,akdf3 in akdf2.groupby('id_status'):
                if showall or (id_status in _include_statuses):
                    print('{}: {}'.format(repr(JobStatus(id_status)), sorted(akdf3.id.tolist())))




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
def _submit_jobs(akdf, condor_priority=0):
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
        submit_job(jb.avalanche_dir, job_name, inout, condor_priority=condor_priority)

_totalsRE = re.compile(r'Total for query: (\d+) jobs; (\d+) completed, (\d+) removed, (\d+) idle')
def _condorq_njobs():
    cmd = ['condor_q',  '-totals']
    proc = subprocess.run(cmd, capture_output=True, text=True)
    for line in io.StringIO(proc.stdout):
        match = _totalsRE.match(line)
        if match is not None:
            return int(match.group(4))
    return None

def submit_jobs(akdf, **kwargs):
    akdf = add_id_status(akdf)

    # Only submit jobs that are ready to go and not in process or completed or something.
    akdf = akdf[akdf.id_status == JobStatus.TODO]

    # Slow down if too many jobs are in the condor queue
    while True:
        njobs = _condorq_njobs()
        if njobs < config.condor_maxjobs:
            break
        print(f"There are currently {njobs} jobs in the HTCondor queue.  I'm going to sleep until it dies down a bit.")
        time.sleep(120)    # Sleep for 2 minutes

    print('==================== Submitting:')
    print(akdf[['combo', 'chunkid', 'id']])
    _submit_jobs(akdf, **kwargs)

    return akdf
# ------------------------------------------------------------
def add_chunk_status(akdf, realized=True, update=True, ignore_statuses={}, dry_run=False):
    """Determins a status for each releasefile (chunk)

    akdf:
        Resolved to chunk
        Columns: chunkid, pra_size
    realized:
        if True:
            Check that all EXISTING avalanches are complete
            (i.e. there's an .out.zip for every .in.zip)
        if False:
            Check that ALL avalanches in the releasefile have been
            completed.
    """

    # Make it idempotent
    if 'chunk_status' in akdf.columns:
        return akdf

    if len(akdf) == 0:
        akdf['chunk_status'] = JobStatus.TODO
        return akdf

    dfs = list()
    for (exp,combo),akdf1 in akdf.reset_index(drop=True).groupby(['exp', 'combo']):
        expmod = parse.load_expmod(exp)
        xdir = expmod.combo_to_scenedir(combo, 'x')

        # Get releasefiles (chunks) that are not yet complete (as per cache)
        akdf1 = complete.add_chunk_complete_cached(akdf1, 2)    # chunk_complete_stage2_cached
        mask = akdf1['chunk_complete_stage2_cached']
        rf_complete_cached = akdf1[mask].copy()
        rf_complete_cached['chunk_status'] = JobStatus.MARKED_FINISHED
        dfs.append(rf_complete_cached)

        # Go on with releasefiles not marked as cached
        akdf1 = akdf1[~mask]

        # ------------------------------------------
        # Get jobstatus at id level
        # Pick up job statuses
        rfdf1 = resolve.resolve_chunk(akdf1, scenetypes={'x'})
        iddf1 = resolve.resolve_id(rfdf1, realized=realized)
        iddf1 = add_id_status(iddf1, update=update, dry_run=dry_run)

        # Aggregate id status back to releasefile level and add to akdf1
        chunk_status = \
            iddf1[['releasefile','id_status']].groupby('releasefile').agg(lambda x: agg_status(x,ignore_statuses)) \
            .rename(columns={'id_status': 'chunk_status'})
        akdf1 = rfdf1.merge(chunk_status, how='left', left_on='releasefile', right_index=True)

        # Mark chunks as finished if they have in fact finished
        mask = (akdf1.chunk_status == JobStatus.FINISHED)
        finished_df = akdf1[mask]
        if update:
            os.makedirs(xdir / 'ramms_stage2', exist_ok=True)
            for chunkname in finished_df.chunkname:
                fname = xdir / 'ramms_stage2' / f'{chunkname}.txt'
                with open(fname, 'w') as out:
                    out.write('RAMMS Stage 2 complete\n')
            finished_df['chunk_status'] = JobStatus.MARKED_FINISHED
        dfs.append(finished_df)

        # Append the rest of the chunk status rows as-is
        akdf1 = akdf1[~mask]
        dfs.append(akdf1)

    return pd.concat(dfs)

# ------------------------------------------------------------
def agg_status(statuses, ignore_statuses={}):
    """Finds the minimu status in a Series, ignoring Statuses in ignores
    statuses: pd.Series
    ignores:
        Statuses to ignore
    """
    counts = statuses.value_counts().to_dict()    # {Status.xyz: <n>, ...}
    counts = {k:v for k,v in counts.items() if k not in ignore_statuses}

    ret = min(status for status in counts.keys())
    return ret

def is_combo_zero_size(expmod, combo, xdir):
    """Determines whether a combo has no avalanches in it."""

    shps = list()
    for pra_size in expmod.pra_sizes(combo):
        shps += glob.glob(str(xdir / 'RELEASE' / f'*{pra_size}_rel.shp'))

#    shps = glob.glob(str(xdir / 'RELEASE' / '*_rel.shp'))

    # If no shapefiles, then it's probbly not generated yet
    if len(shps) == 0:
        return False

    for shp in shps:
        if os.path.getsize(shp) > 0:
            return False
    # At least one shapefile and all zero length: it's a zero size combo!
    return True


def add_combo_quickstatus(expmod, akdf0, mtime=False):

    """Adds a quick per-combo status field based on just whether the
    combo has been marked finished.  Allows for easy exclusion of
    aready-finished combos in akramms run; and not-started combos when
    looking at status.

    akdf:
        Resolved to combo level (theoretical, i.e. realized=False)

    """

    # Make it idempotent
    if 'combo_quickstatus' in akdf0.columns:
        return akdf0

    dfs = list()
    if len(akdf0) == 0:
        akdf0['combo_quickstatus'] = JobStatus.UNKNOWN
        if mtime:
            akdf0['combo_quickstatus_mtime'] = -1
        return akdf0


    for exp,akdf1 in akdf0.reset_index(drop=True).groupby('exp'):
        expmod = parse.load_expmod(exp)

        combo_quickstatus = list()
        mtimes = list()
        for tup in akdf1.itertuples(index=False):
            arcdir = expmod.combo_to_scenedir(tup.combo, scenetype='arc')
#            print('quickstatus ', tup.combo, arcdir)
            if os.path.exists(arcdir / 'archived.txt'):
                if all(os.path.isfile(gpkg) for gpkg in extent.extent_files(expmod, tup.combo)):
#                if os.path.exists(arcdir / 'extent.gpkg') and os.path.exists(arcdir / 'extent_full.gpkg'):
                    status = JobStatus.EXTENT
                else:
                    status = JobStatus.MARKED_FINISHED
#                print(f'Quickstatus {arcdir}: {status}')
                mtimes.append(os.path.getmtime(arcdir / 'archived.txt'))
            else:
                xdir = expmod.combo_to_scenedir(tup.combo, scenetype='x')
                if not os.path.exists(xdir):
                    status = JobStatus.NOINPUT
                else:
                    if is_combo_zero_size(expmod, tup.combo, xdir):
                        status = JobStatus.FINISHED
                    else:
                        status = JobStatus.UNKNOWN
                if mtime:
                    mtimes.append(-1)
            combo_quickstatus.append(status)

        akdf1['combo_quickstatus'] = combo_quickstatus
        if mtime:
            akdf1['combo_quickstatus_mtime'] = mtimes

        dfs.append(akdf1)

    return pd.concat(dfs)


def _finished_status(expmod, combo):
    arcdir = expmod.combo_to_scenedir(combo, 'arc')
    if not os.path.isfile(arcdir / 'archived.txt'):
        return JobStatus.UNKNOWN
    if not (os.path.isfile(arcdir / 'extent.gpkg') and os.path.isfile(arcdir / 'extent_full.gpkg')):
        return JobStatus.MARKED_FINISHED
    return JobStatus.EXTENT

@functools.lru_cache()
def _ignore_ids(expmod):
    rows = [(row[0], row[1], True) for row in expmod.ignore_ids()]
    return pd.DataFrame(rows, columns=['combo', 'id', 'ignore'])

#def _noid_status(row):
#    """Determines status for a combo with no avalanches in it."""
#    xdir = expmod.combo_to_scenedir(row['combo'], scenetype='x')
#    glob.glob(xdir / 

def add_combo_status(expmod, akdf0, realized=True, update=True, dry_run=False, delete_xdir=True, ignore_statuses={}):
    """akdf:
        Resolved to combo level (theoretical, i.e. realized=False)
    update:
        Archive xdir if possible?
    delete_xdir:
        Delete xdir after archiving?
    """


    # Make it idempotent
    if 'combo_status' in akdf0.columns:
        return akdf0

    dfs = list()

    if len(akdf0) == 0:
        akdf0['combo_status'] = JobStatus.TODO
        return akdf0

    # Cull combos that have finished or not yet started
    akdf0 = add_combo_quickstatus(expmod, akdf0)#, mtime=mtime)

    # Write extent.gpkg (Actually this does NOT write extents, it just moves it to MARKED_FINISHED
    if update:
#        mask = (akdf0.combo_quickstatus.isin([JobStatus.MARKED_FINISHED, JobStatus.FINISHED]))
        mask = (akdf0.combo_quickstatus.isin([JobStatus.FINISHED]))
        for exp,akdf1 in akdf0[mask].reset_index(drop=True).groupby('exp'):
            expmod = parse.load_expmod(exp)
            for tup in akdf1.itertuples(index=False):
                print('Finishing combo (c): {}'.format(tup.combo))
                archive.finish_combo(expmod, tup.combo, dry_run=dry_run, delete_xdir=delete_xdir)

    # -----
    mask = (~akdf0.combo_quickstatus.isin([JobStatus.MARKED_FINISHED, JobStatus.FINISHED, JobStatus.EXTENT]))

    renames = {'combo_quickstatus':'combo_status'}
    dfs.append(akdf0[~mask].rename(columns=renames))
    akdf0 = akdf0[mask].drop('combo_quickstatus', axis=1)

    # Go to more work to determine the status of the rest of them.
    for exp,akdf1 in akdf0.reset_index(drop=True).groupby('exp'):
        expmod = parse.load_expmod(exp)

        # Take care of combos we know are archived
        finished_status = akdf1.combo.apply(lambda combo: _finished_status(expmod, combo))
        is_archived = (finished_status != JobStatus.UNKNOWN)
        df = akdf1[is_archived]
        if len(df) > 0:
            df['combo_status'] = finished_status
            if update:
                # Do extent.gpkg on files that only have archived.txt
                for tup in df[df.combo_status == JobStatus.MARKED_FINISHED].itertuples(index=False):

                    print('Finishing combo (b): {}'.format(tup.combo))
                    archive.finish_combo(expmod, tup.combo, dry_run=dry_run)

            dfs.append(df)
            akdf1 = akdf1[~is_archived]

        # ------------------------------------------
        # Get jobstatus at id level
        rfdf1 = resolve.resolve_chunk(akdf1)
        iddf1 = resolve.resolve_id(rfdf1, realized=realized)
        iddf1 = add_id_status(iddf1, update=update, dry_run=dry_run)

        # Remove jobs we wish to ignore
        iddf1 = iddf1.merge(_ignore_ids(expmod), how='left', on=['combo', 'id'])
        iddf1['ignore'] = iddf1.ignore.fillna(False).astype(bool)

        iddf1 = iddf1[~iddf1.ignore]

        # Replace older avalanches runs with newer runs of the same ID
        # (which presumably have fixed overrun problems)
        iddf1 = overrun.drop_duplicates(iddf1)
#        print('add_combo_status() rows')
#        xdf = iddf1[['combo', 'pra_size', 'chunkid', 'id', 'id_status']]
#        print('All rows ID')
#        print(xdf)
#        print('combo_status ID NOINPUT rows')
#        print(xdf[xdf.id_status == JobStatus.NOINPUT])

        # Aggregate id status back to combo level and add to akdf1
        # (Now we know whether the combo has fully finished)
        combo_status = \
            iddf1[['combo','id_status']].groupby('combo').agg(lambda x: agg_status(x,ignore_statuses)) \
            .rename(columns={'id_status': 'combo_status'})
        akdf1 = akdf1.merge(combo_status, how='left', left_on='combo', right_index=True)
#        print('combo_status ', akdf1[['combo', 'combo_status']])

        akdf1['combo_status'] = akdf1.combo_status.fillna(JobStatus.NOINPUT).astype(int)

#        # 
#        for i,row in akdf1.iterrows():
#            if np.isnan(row['combo_status']):
#
#                # No avalanches available for this combo.  That is OK
#                # if the combo had no avalanches to begin wtih.
#                print(row)
#
#            print(i,row['combo_status'])


        # --------------------------------------------
        if update:
            # Copy shapefiles
            for tup in akdf1.itertuples(index=False):
                archive.copy_shapefiles(expmod, tup.combo, dry_run=dry_run)

            # Mark combos that have fully finished
            mask = (
                (akdf1.combo_status == JobStatus.FINISHED) |
                (akdf1.combo_status == JobStatus.MARKED_FINISHED))
            for tup in akdf1[mask].itertuples(index=False):
                print('Finishing combo (a): {}'.format(tup.combo))
                archive.finish_combo(expmod, tup.combo, dry_run=dry_run)

        dfs.append(akdf1)

    return pd.concat(dfs).sort_values('combo_order')
# ------------------------------------------------------------
def add_status(expmod, akdf, level, realized=True, update=True, dry_run=False, ignore_statuses={}):
    if level == 'id':
        akdf = add_id_status(akdf, update=update, dry_run=dry_run)

    elif level == 'chunk':
        akdf = add_chunk_status(akdf, realized=realized, update=update, ignore_statuses=ignore_statuses, dry_run=dry_run)

    elif level == 'combo':
        akdf = add_combo_status(expmod, akdf, realized=realized, update=update, dry_run=dry_run, ignore_statuses=ignore_statuses)

    return akdf

# ------------------------------------------------------------
_all_status = set(JobStatus._value2member_map_.values())
def print_status(akdf0, level, out=sys.stdout, statuses=_all_status):
    """
    level: 'id', 'chunk' or 'combo'
        Level of status we will print
    """

    if level == 'id':
        for releasefile,akdf1 in akdf0.groupby('releasefile'):
            print(f'-------------- {releasefile}', file=out)
            for id_status,akdf2 in akdf1.groupby('id_status'):
                if id_status not in statuses:
                    continue
                id_status = JobStatus._member_names_[id_status]
                ids = ', '.join(str(x) for x in akdf2.id.tolist())
                print(f'{id_status}: {ids}', file=out)
    elif level == 'releasefile' or level == 'chunk':
        for (exp,combo),akdf1 in akdf0.groupby(['exp', 'combo']):
            print(f'-------------- {exp} {combo}', file=out)
            for chunk_status,akdf2 in akdf1.groupby('chunk_status'):
                if chunk_status not in statuses:
                    continue

                chunk_status = JobStatus._member_names_[chunk_status]
                chunknames = ', '.join(akdf2.chunkname.tolist())
                print(f'{chunk_status}: {chunknames}', file=out)
    elif level == 'combo':
        for tup in akdf0.itertuples(index=False):
            if tup.combo_status not in statuses:
                continue
            scombo = '-'.join(str(x) for x in tup.combo)
            sstat = JobStatus._member_names_[tup.combo_status]
            print(f'{tup.exp}-{scombo}: {sstat}', file=out)



# ------------------------------------------------------------
