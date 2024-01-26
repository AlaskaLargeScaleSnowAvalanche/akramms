import os,subprocess,functools,re,typing,zipfile,sys,contextlib
import htcondor
import pandas as pd
from uafgi.util import gdalutil
from akramms import config,file_info,parse,level,complete,resolve,archive,overrun,params

# Categorize each job int one of four sets
#job_status_labels = ('noinput', 'incomplete', 'todo', 'inprocess', 'finished', 'overrun', 'failed')

JobStatus = file_info.JobStatus    # Alias

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

class OverrunChecker:

    def __init__(self, dem_mask_tif):
        self.gridI,self.dem_mask,_ = gdalutil.read_raster(dem_mask_tif)


    def is_overrun(self, in_zip, out_zip):
        """Determines whether a RAMMS result is overrun

        in_zip, out_zip:
            Already-open zip files
        """

        with contextlib.ExitStack() as stack:

            # Open .in.zip and .out.zip files if not already open
            if not isinstance(in_zip, zipfile.ZipFile):
                in_zip = zipfile.ZipFile(in_zip, 'r')
                stack.enter_context(in_zip)

            if not isinstance(out_zip, zipfile.ZipFile):
                out_zip = zipfile.ZipFile(out_zip, 'r')
                stack.enter_context(out_zip)


            # If RAMMS did not detect an overrun, we are fine.
            arcnames = [os.path.split(x)[1] for x in out_zip.namelist()]
            if not any(x.endswith('.out.overrun') for x in arcnames):
                return False

            # RAMMS thinks it overran.  Inspect the domain mask further to
            # determine whether it in fact overran.
            base = str(out_zip)[:-8]    # Remove .out.zip
            leaf = os.path.split(base)[1]

            # Identify oedge, the set of gridcells that, if the avalanche hits them,
            # constitute an overrun.
            with in_zip.open(arcname, 'r') as fin:
                ivec, jvec = parse_xy_coord(gridI, fin)
                oedge = xyedge.oedge(ivec, jvec, self.gridI.nx, self.gridI.ny, self.dem_mask)

            # See if we hit any of the oedge gridcells
            with out_zip.open(arcname, 'r') as fin:
                namevals = parse_out(fin)
                vals = {name:val for name,val,_ in namevals}

            return np.any(np.logical_and(oedge != 0, vals['max_height'] > 0))

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
                        with zipfile.ZipFile(f'{base}.in.zip', 'r') as izip:
                          with zipfile.ZipFile(f'{base}.out.zip', 'r') as ozip:
                            statuses.append(
                                (combo, chunkid, tup.id,
                                JobStatus.OVERRUN if check_overruns.is_overrun(inzip, ozip) else JobStatus.FINISHED) )
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
    akdf = akdf[akdf.id_status == JobStatus.TODO]

    print('==================== Submitting:')
    print(akdf[['combo', 'chunkid', 'id']])
    _submit_jobs(akdf)

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
        rf_complete_cached = akdf1[mask]
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


def add_combo_status(akdf0, realized=True, update=True, dry_run=False, ignore_statuses={}):
    """akdf:
        Resolved to combo level (theoretical, i.e. realized=False)
    """

    # Make it idempotent
    if 'combo_status' in akdf0.columns:
        return akdf0

    dfs = list()

    if len(akdf0) == 0:
        akdf0['combo_status'] = JobStatus.TODO
        return akdf0


    for exp,akdf1 in akdf0.reset_index(drop=True).groupby('exp'):
        expmod = parse.load_expmod(exp)

#        akdf1['combo_status'] = JobStatus.NOINPUT    # The Combo doesn't exist yet

        # Take care of combos we know are archived
        is_archived = akdf1.combo.apply(lambda combo: 
            os.path.isfile(expmod.combo_to_scenedir(combo, 'arc') / 'archived.txt') )
        df = akdf1[is_archived]
        df['combo_status'] = JobStatus.MARKED_FINISHED
        dfs.append(df)
        akdf1 = akdf1[~is_archived]

        # ------------------------------------------
        # Get jobstatus at id level
        rfdf1 = resolve.resolve_chunk(akdf1)
        iddf1 = resolve.resolve_id(rfdf1, realized=realized)
        iddf1 = add_id_status(iddf1, update=update, dry_run=dry_run)

        # Replace older avalanches runs with newer runs of the same ID
        # (which presumably have fixed overrun problems)
        iddf1 = overrun.drop_duplicates(iddf1)

        # Aggregate id status back to combo level and add to akdf1
        # (Now we know whether the combo has fully finished)
        combo_status = \
            iddf1[['combo','id_status']].groupby('combo').agg(lambda x: agg_status(x,ignore_statuses)) \
            .rename(columns={'id_status': 'combo_status'})
        akdf1 = akdf1.merge(combo_status, how='left', left_on='combo', right_index=True)
        akdf1['combo_status'] = akdf1.combo_status.fillna(JobStatus.NOINPUT).astype(int)

        # --------------------------------------------
        if update:
            # Mark combos that have fully finished
            mask = (akdf1.combo_status == JobStatus.FINISHED)
            for tup in akdf1[mask].itertuples(index=False):
                archive.finish_combo(expmod, tup.combo, dry_run=dry_run)

        dfs.append(akdf1)

        # ------------------------------------------
#        # Get jobstatus at releasefile level
#        rfdf1 = resolve.resolve_chunk(akdf1)
#        rfdf1 = add_chunk_status(rfdf1, realized=realized, update=update)
#
#        # Aggregate id status back to combo level and add to akdf1
#        combo_status = \
#            rfdf1[['combo','chunk_status']].groupby('combo').min() \
#            .rename(columns={'chunk_status': 'combo_status'})
#        akdf1 = akdf1.merge(combo_status, how='left', left_on='combo', right_index=True)
#        akdf1['combo_status'] = akdf1.combo_status.fillna(JobStatus.NOINPUT).astype(int)
#        # -------------------------------------------------
#
#        # Archive combos if they have in fact finished
#        if update:
#            mask = (akdf1.combo_status == JobStatus.FINISHED)
#            dfs.append(akdf1[~mask])
#
#            finished_combo_df = akdf1[mask]
#            archive.archive_combos(finished_combo_df, dry_run=dry_run)
#            finished_combo_df.combo_status = JobStatus.ARCHIVED
#            dfs.append(finished_combo_df)
#        else:
#            dfs.append(akdf1)

    return pd.concat(dfs)
# ------------------------------------------------------------
def add_status(akdf, level, realized=True, update=True, dry_run=False, ignore_statuses={}):
    if level == 'id':
        akdf = add_id_status(akdf, update=update, dry_run=dry_run)

    elif level == 'chunk':
        akdf = add_chunk_status(akdf, realized=realized, update=update, ignore_statuses=ignore_statuses, dry_run=dry_run)

    elif level == 'combo':
        akdf = add_combo_status(akdf, realized=realized, update=update, dry_run=dry_run, ignore_statuses=ignore_statuses)

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
