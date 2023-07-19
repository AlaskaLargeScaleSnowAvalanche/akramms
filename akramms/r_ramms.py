import os,subprocess,re,sys,itertools,gzip,collections,io,typing,codecs,copy
import multiprocessing
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

# 2023-04-24 Marc Christen said:
#   As you do not run Stage 2 in RAMMS, you do not use the variable
#   “NRCPUS” in the scenario-file. In the new version (link below) you
#   can now use this variable. NRCPUS = 8 means, that RAMMS will start
#   the first 8 exe-files to create the xy_coord-files in parallel, but
#   then RAMMS will wait for the 8-th exe-file to finish. Then RAMMS
#   will start the next 8 exe-files, and so on…..This will give a small
#   break, such that not 100 exe-files will execute in parallel. What do
#   you think? Could you please try this workaround for the moment? Of
#   course you could also increase NRCPUS, or decrease…..


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


# def rammsdir_rule(scene_dir, release_file, oramms_name=None, **scenario_kwargs):
# 
#     """Generates the scenario file, which becomes key to running RAMMS.
#     release:
#         Release file to process
#     oramms_name:
#         Output RAMMS directory to create
#     """
#     jb = rammsutil.parse_release_file(release_file)
#     if oramms_name is None:
#         oramms_name = jb
# 
#     scene_args = params.load(scene_dir)
#     resolution = scene_args['resolution']
#     name = scene_args['name']
#     scenario_txt = os.path.join(jb.ramms_dir, 'scenario.txt')
# 
#     links = dem_forest_links(scene_args, jb.ramms_dir, oramms_name.slope_name, forest=jb.forest)
# 
#     def action(tdir):
#         # Make symlinks for DEM file, etc.
#         for ifile,ofile in links:
#             setlink_or_copy(ifile, ofile)
# 
#         # Write scenario.txt
#         write_scenario_txt(jb, **scenario_kwargs)
# 
#     inputs = [d[0] for d in links]
#     linked_files = [d[1] for d in links]
#     outputs = [scenario_txt] + linked_files
#     return make.Rule(action, inputs, outputs)

def chunk_rule(scene_dir, ramms_names, **scenario_kwargs):
    """Generates the scenario file, which becomes key to running RAMMS.
    Also split into chunks.

    release:
        Release file to process
    oramms_name:
        Output RAMMS directory to create
    """

    scene_args = params.load(scene_dir)

    outputs = list()
    for jb,pra_size in ramms_names:
        outputs.append(rammsutil.chunks_csv(scene_args['scene_dir'], jb.ramms_name))


    def action(tdir):

        for jb,pra_size in ramms_names:

            # Read _rel and _dom shapefiles
            base = os.path.join(scene_args['scene_dir'], 'RELEASE', f'{jb.ramms_name}')
            rel_df = shputil.read_df(f'{base}_rel.shp', shape='pra').drop('fid', axis=1)

            dom_df = shputil.read_df(f'{base}_dom.shp', shape='dom').drop('fid', axis=1)

#            print('********* rel ')
#            print(rel_df[['area_m2','Mean_DEM','Mean_Slope','Id','VOL_30']])
#            print('********* dom ')
#            print(dom_df)
#            sys.exit(0)

            df = rel_df.merge(dom_df, on='Id')

            # Drop rows with missing domain
            df = df[df['dom'].notna()]

            ofnames = list()
            chunk_info = list()
            for segment,chunkix in enumerate(range(0,df.shape[0],config.max_ramms_pras)):
                # DEBUG
                if (config.max_chunks is not None) and (segment >= config.max_chunks):
                    break

                # Select out chunk
                dfc = df[chunkix:chunkix+config.max_ramms_pras]

                # Add the chunk number to the name
                jb1 = copy.copy(jb)
                jb1.set(segment=segment)

                # Make symlinks for DEM file, etc.
                for ifile,ofile in dem_forest_links(scene_args, jb1.ramms_dir, jb1.slope_name, forest=jb1.forest):
                    setlink_or_copy(ifile, ofile)



                # Write scenario.txt
                scenario_txt = os.path.join(jb1.ramms_dir, 'scenario.txt')
                write_scenario_txt(jb1, **scenario_kwargs)

                # Write the _rel.shp file
                ofname = os.path.join(jb1.ramms_dir, 'RELEASE', f'{jb1.ramms_name}_rel.shp')
                #print('xxxxx writing ', ofname)
                os.makedirs(os.path.dirname(ofname), exist_ok=True)
                #print('rel_def ', rel_df.columns)
                #print('dfc     ', dfc.columns)
                #rel_cols = list(rel_df.columns)
                #print('rel_cols ', rel_cols)
#                print(rel_df[['fid', 'Id']])
                _dfx = dfc[list(rel_df.columns)]
                shputil.write_df(_dfx, 'pra', 'Polygon', ofname, wkt=scene_args['coordinate_system'])
            
                # Write the _dom.shp file 
                ofname = os.path.join(jb1.ramms_dir, 'DOMAIN', f'{jb1.ramms_name}_dom.shp')
                os.makedirs(os.path.dirname(ofname), exist_ok=True)
                shputil.write_df(dfc[list(dom_df)], 'dom', 'Polygon', ofname, wkt=scene_args['coordinate_system'])

                # Write the .relp and .domp files for each avalanche
                # (Secondary files, as written by Python)
                os.makedirs(jb1.avalanche_dir, exist_ok=True)
                for _,row in dfc.iterrows():
                    id = row['Id']
                    ofname = os.path.join(jb1.avalanche_dir, f'{jb1.ramms_name}_{id}.relp')
                    rammsutil.write_polygon(row['pra'], ofname)
                    ofname = os.path.join(jb1.avalanche_dir, f'{jb1.ramms_name}_{id}.domp')
                    rammsutil.write_polygon(row['dom'], ofname)

                # Store chunk info
                For = 'For' if jb1.forest else 'NoFor'
                chunk_info += [
                    (segment, id,
                    f'{jb1.scene_name}{jb1.segment:05d}{jb1.return_period}{jb1.pra_size}{For}_{jb1.resolution}m')
                    for id in dfc['Id']]
                #chunk_info.append(segment, list(dfc['Id']))
            
            # Write names of our PRA files into the _chunks.txt output file
            chunk_index_df = pd.DataFrame(chunk_info, columns=['segment', 'Id', 'chunk_name'])
#            with open(, 'w') as out:
            #chunk_index_df.to_csv(f'{base}_chunks.csv', index=False)
            ccsv = rammsutil.chunks_csv(scene_args['scene_dir'], jb.ramms_name)
            os.makedirs(os.path.dirname(ccsv), exist_ok=True)
            chunk_index_df.to_csv(ccsv)
    inputs = list()
    for jb,_ in ramms_names:
        # Get list of symlinks we WILL make, use that to determine input files
        links = dem_forest_links(scene_args, jb.ramms_dir, jb.slope_name, forest=jb.forest)
        inputs += [d[0] for d in links]

    return make.Rule(action, inputs, outputs)
# --------------------------------------------------------------------
def tiffmap(jb1):

    """Returns a mapping between a parsed RAMMS dir vs. "permanent"
    names for .tif files that can be reused for different chunks in
    RAMMS Stage 1.  After RAMMS stage 1, files will be copied from the
    chunk to their general location, as appropriate.

    jb1:
        Parsed release file name of one chunk
    Returns: [(fname_chunk, fname_general), ...]

    """

    # Parsed release file name of the dummy overall run used to create
    # reusable names for the TIF files.
    jb0 = jb1.copy(segment=None)
    scene_dir = os.path.dirname(jb1.ramms_harness)
    scene_args = params.load(scene_dir)

    results_dir1 = os.path.join(jb1.ramms_dir, 'RESULTS', jb1.rammsdir_name)

    map = [
#        # ./juneau10000030MFor_5m/DEM/juneau100000For_5m_dem.tif
#        (f'{jb1.ramms_dir}/DEM/{jb1.ramms_name}_dem.tif', scene_args['dem_file']),

#        # ./juneau10000030MFor_5m/FOREST/juneau100000For_5m_forest.tif
#        (f'{jb1.ramms_dir}/FOREST/{jb1.ramms_name}_forest.tif', scene_args['forest_file']),

        # -------------- Items for all sub-directories of the slope_dir
        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/slope.tif
        (f'{jb1.slope_dir}/slope.tif',
            f'SLOPE_TIF/{jb0.slope_name}/slope.tif'),
        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/curvidl.tif
        (f'{jb1.slope_dir}/curvidl.tif',
            f'SLOPE_TIF/{jb0.slope_name}/curvidl.tif'),

        # -------------- Items for each subdir
        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/juneau100000For_5m_M30_xi.tif
        (f'{jb1.slope_dir}/{jb1.slope_name}_{jb0.pra_size}{jb1.return_period}_xi.tif',
            f'SLOPE_TIF/{jb0.slope_name}/{jb0.slope_name}_{jb0.pra_size}{jb0.return_period}_xi.tif'),

        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/juneau100000For_5m_M30_mu.tif
        (f'{jb1.slope_dir}/{jb1.slope_name}_{jb0.pra_size}{jb1.return_period}_mu.tif',
            f'SLOPE_TIF/{jb0.slope_name}/{jb0.slope_name}_{jb0.pra_size}{jb0.return_period}_mu.tif'),

        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/logfiles/muxi_class.tif
    ]

    map = [
        (os.path.join(jb0.ramms_harness, x), os.path.join(scene_dir, y))
        for x,y in map]

    return map


# --------------------------------------------------------------------
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
def file_is_good(fname):
    # Make sure file exists in non-zero length
    if not os.path.exists(fname):
        return False
    if os.path.getsize(fname) == 0:
        return False
    return True
    
_izip_exts = ['.relp', '.domp', '.xyz', '.xy-coord', '.var', '.rel', '.dom']  # .dom MUST be last
def compress_avalanche_inputs(jb, ids):
    """Puts all avalanche inputs into a single Zip file."""
#    jb = rammsutil.parse_release_file(release_file)
    jb = jb.copy()
    for id in ids:
        jb.set(id=id)
        base = os.path.join(jb.avalanche_dir, f'{jb.ramms_name}')
        zip_file = f'{base}.in.zip'

        files = [f'{base}{ext}' for ext in _izip_exts]
        arcnames = [f'{jb.ramms_name}{ext}' for ext in _izip_exts]
        arcnames[-1] = f'{jb.ramms_name}.v1.dom'    # First of many .dom files

        if (not os.path.exists(f'{base}.in.zip')) and \
            all(file_is_good(x) for x in files):

            print(f'Compressing {zip_file}')

            # Compress Avalanche intput files into a Zipfile
            with zipfile.ZipFile(
                zip_file, 'w', compression=zipfile.ZIP_DEFLATED) \
                as izip:

                for file,arcname in zip(files,arcnames):
                    izip.write(file, arcname=arcname)

                # Write the .av3 files based on the .av2 file
                arcname = f'{jb.ramms_name}.av3'
                av2_file = f'{base}.av2'
                files.append(av2_file)
                with open(av2_file, 'r') as fin:
                    av3_str = av2_to_av3(fin.read())
                izip.writestr(arcname, av3_str)

            # Remove old files
            for file in files:
                os.remove(file)

# --------------------------------------------------------------------

def striped_chunks(l, n):
    """Yield n number of striped chunks from l."""
    # https://stackoverflow.com/questions/24483182/python-split-list-into-n-chunks
    for i in range(0, n):
        yield l[i::n]

def ramms_stage1_rule(release_file, inputs, dry_run=False, submit=False):
    """Runs Stage 1 of RAMMS (IDL code prepares individual avalanche runs)

    inputs:
        All input files for the RAMMS run (superset of release_files)
    """

    jb = rammsutil.parse_release_file(release_file)
    #logfile = os.path.join(jb.ramms_dir, 'RESULTS', 'lshm_rock.log')

    # Write extra output files to show we finished stage1 for a particular release file
#    done_output = os.path.join(jb.ramms_dir, 'RESULTS', f'{jb.ramms_name}_stage1.txt')
    done_output = os.path.join(jb.scene_dir, 'stage1', f'{jb.ramms_name}.txt')

    def action(tdir):
        # ---------------------------------------------------------
        # From former rammsdir rule

        # ---------------------------------------------------------

        # Copy files from previous RAMMS Stage 1, to speed things up
        tmap = tiffmap(jb)
        for fname0,fname1 in tmap:
            if (not os.path.exists(fname0)) and os.path.exists(fname1):
                dir0 = os.path.dirname(fname0)
                os.makedirs(dir0, exist_ok=True)
                shutil.copy(fname1, fname0)

        ramms_dir_rel = config.roots.relpath(jb.ramms_dir)
        cmd = ['sh', 
            config.roots_w.join('HARNESS', 'akramms', 'sh', 'run_ramms.sh', bash=True),
            '--ramms-version', config.ramms_version,
            config.roots_w.syspath(ramms_dir_rel, bash=True), '1']    # '1'=stage 1

        # RAMMS Stage 1 accepts inputs on stdin
        # rammsdist.run_on_windows_stage() calls read_inputs()
#        dynamic_outputs = list()
#        dynamic_outputs = harnutil.run_remote(inputs, cmd, tdir, write_inputs=True)
        dynamic_outputs = harnutil.run_remote_queued(inputs, cmd, tdir, write_inputs=True)

        # Write output files
        os.makedirs(os.path.dirname(done_output), exist_ok=True)
        with open(done_output, 'w') as out:
            out.write('Finished RAMMS Stage 1\n')

        # Copy .tif files to be reused by later RAMMS Stage 1
        for fname0,fname1 in tmap:
            dir1 = os.path.dirname(fname1)
            os.makedirs(dir1, exist_ok=True)
            if not os.path.exists(fname1):
                shutil.copy(fname0, fname1)

            # Do NOT remove, we will need for Stage 2 (the .exe file).
            # os.remove(fname0)

        # Compress Avalanche inputs, ready for Docker container
        df = shputil.read_df(release_file, read_shapes=False)
        all_ids = list(df['Id'])
        procs = list()
        for ids in striped_chunks(all_ids, config.ncpu_compress):
            proc = multiprocessing.Process(
                target=lambda: compress_avalanche_inputs(jb,ids))
            proc.start()
            procs.append(proc)
        for proc in procs:
            proc.join()

        # Check final outputs
        missing = list()
        jb1 = jb.copy()
        for id in all_ids:
            jb1.set(id=id)
            base = os.path.join(jb.avalanche_dir, f'{jb1.ramms_name}')
            in_zip = f'{base}.in.zip'
            if not os.path.exists(in_zip):
                missing.append(in_zip)
        if len(missing) > 0:
            for x in missing:
                print('Missing: ', x)
            raise ValueError('Missing avalanche input files')


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
#        job_suffixes = dict(analyze_rundir(jb.avalanche_dir, jb.ramms_name))

        # --------------------------------------------------

        # Consider each job in turn from our master list
        for id in ids:
            key = (jb.avalanche_dir, id)

            job_name = f'{jb.ramms_name}_{id}'

            # Mark as NOINPUT if the .in.zip file is not there.
            if not os.path.exists(os.path.join(jb.avalanche_dir, f'{job_name}.in.zip')):
                statuses.append((jb, id, JobStatus.NOINPUT))
                continue

            # See if Condor tells is what's going on with the job
            if job_name in condor_statuses:
                statuses.append((jb, id, condor_statuses[job_name]))
                continue

            # Not in Condor?  Either it hasn't launched, or it's finished / failed
            # Let's look at the files on disk to decide.

            # Identify avalanches that have finished: .out.zip exists and has non-zero size
            # (User can reset jobs by removing *.out.zip)
            out_zip = os.path.join(jb.avalanche_dir, f'{job_name}.out.zip')
            if os.path.exists(out_zip):

                # Check for abandoned job
                statinfo = os.stat(out_zip)
                if (statinfo.st_size==0):
                    # The HTCondor output file has been created, but
                    # no sign of the HTCondor job to write it at the
                    # end.  Sounds like things were killed, send
                    # status back to TODO.
                    statuses.append((jb, id, JobStatus.TODO))
                    continue

                # We tentatively think the job is finished.  But let's
                # look inside the zip file to make sure the domain
                # wasn't overrun.
                with zipfile.ZipFile(out_zip, 'r') as in_zip:
                    arcnames = [os.path.split(x)[1] for x in in_zip.namelist()]
                if any(x.endswith('.out.overrun') for x in arcnames):
                    statuses.append((jb, id, JobStatus.OVERRUN))
                else:
                    statuses.append((jb, id, JobStatus.FINISHED))
                continue

            # Default to TODO
            statuses.append((jb, id, JobStatus.TODO))

    statuses = [(jb.key(), jb, id, status) for jb,id,status in statuses]
#    df = pd.DataFrame(statuses, columns=('jb_key', 'id', 'job_status'))
    df = pd.DataFrame(statuses, columns=('jb_key', 'jb', 'id', 'job_status'))
    df = df.sort_values(by=['jb_key', 'id'])
    #df = df[['run_dir', 'id', 'job_status']]
#    print(df)
    return df
# --------------------------------------------------------
_include_statuses = {JobStatus.NOINPUT, JobStatus.INCOMPLETE, JobStatus.TODO, JobStatus.INPROCESS, JobStatus.OVERRUN, JobStatus.FAILED}
def print_job_statuses(df):
#    for (run_dir, job_status), group in df.groupby(['run_dir', 'job_status']):
    for (jb_key, job_status), group in df.groupby(['jb_key', 'job_status']):
        if job_status not in _include_statuses:
            continue
        jb = jb_key[-1]

        print('=========== {} {}:'.format(job_status_labels[job_status], jb.avalanche_dir))
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
            run_dir = row['jb'].avalanche_dir
            parts = run_dir.split(os.sep)
            job_name = '{}_{}_{}'.format(parts[-2], parts[-1], row['id'])
            print('submit ', run_dir, job_name)
            submit_job(run_dir, job_name)

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
        shutil.copy2(
            dom_file,
            os.path.join(run_dir, f'{job_name}.v{max_version+1}.dom'))
        shutil.copy2(log_zip_file, log_zip_file + '.v{}'.format(max_version+1))
        rammsutil.write_polygon(dom1, dom_file)    # New timestamp


def enlarge_domains(release_files, ids=None):
    df = job_statuses(release_files)
    df = df[df.job_status == JobStatus.OVERRUN]
    for _,row in df.iterrows():
        jb = row.jb
        run_dir = jb.avalanche_dir
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


# Converts an extension on an arcname to extension on the zip filename
# (i.e.whether it is in _in.zip or _out.zip)
arcext2filext = {
    '.relp': '.in.zip',
    '.domp': '.in.zip',
    '.rel': '.in.zip',
    '.dom': '.in.zip',
    '.xyz': '.in.zip',
    '.xy-coord': '.in.zip',
    '.var': '.in.zip',
    '.av3': '.in.zip',
    '.out': '.out.zip',
    '.out.log': '.out.zip',
    '.out.overrun': '.out.zip',
}

# https://stackoverflow.com/questions/34447623/wrap-an-open-stream-with-io-textiowrapper
def cat(ramms_spec, ids=list(), ext='.out.log', out_bytes=sys.stdout.buffer):
    out_text = codecs.getwriter('utf-8')(out_bytes)
    for jb,id in ramms_iter(ramms_spec, ids=ids):
        try:
            zip_fname = jb.zip_file(id, arcext2filext[ext])
        except KeyError:
            zip_fname = jb.zip_file(id, '.in.zip')

        with zipfile.ZipFile(zip_fname, 'r') as izip:
            print('======== {}'.format(zip_fname), file=out_text)
            sys.stdout.flush()
            bytes = izip.read(jb.arcname(id, ext))
            out_bytes.write(bytes)

            #os.write(1, bytes)    # 1 = STDOUT
            #with os.fdopen(sys.stdout.fileno(), "wb", closefd=False) as stdout:
            #    stdout.write(bytes)
            #    stdout.flush()

def ls(ramms_spec, ids):
    """List the contenst of the .in.zip and .out.zip files for an id"""
    ret = list()
    for jb,id in ramms_iter(ramms_spec, ids=ids):
        zip_fnames = [jb.zip_file(id, ext) for ext in ('.in.zip', '.out.zip')]
        for zip_fname in zip_fnames:
            if not os.path.exists(zip_fname):
                continue
            with zipfile.ZipFile(zip_fname, 'r') as izip:
                infos = izip.infolist()
                ret += [(jb,id,info) for info in infos]

    return ret


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

def copy_from_zip(zip_file, arcname, ofname):
    """Copies a single entry from a zipfile to a file.
    zip_file:
        The open ZilFile
    arcname:
        Archive name of the file to copy
    ofname:
        Name in filesystem to copy to.
    """
    bytes = zip_file.read(arcname)
    with open(ofname, 'wb') as out:
        out.write(bytes)

def copy_from_zip_to_gz(zip_file, arcname, ofname):
    """Copies a single entry from a zipfile to a file.
    zip_file:
        The open ZilFile
    arcname:
        Archive name of the file to copy
    ofname:
        Name in filesystem to copy to.
    """
    bytes = zip_file.read(arcname)
    with gzip.open(ofname, 'w') as out:
        out.write(bytes)

domRE = re.compile(r'(.*)\.v(\d+)\.dom')
def latest_dom_file(arcnames):
    """Digs through .in.zip to find the latest .vXXX.dom file"""
    max_itry = -1
    for arcname in arcnames:
        match = domRE.match(arcname)
        if match is not None:
            # It's a .dom.vXXX file.; identify the one with largest number
            itry = int(match.group(2))
            if itry > max_itry:
                dom_arcname = arcname
                max_itry = itry

    return dom_arcname

def copy_stage3_inputs(iavalanche_dir, aname, oavalanche_dir):
    """
    aname:
        Base name of avalanche, including the ID but no file extension.
    """

    all_exist = all(
        os.path.exists(os.path.join(oavalanche_dir, f'{aname}.rel'))
        for ext in ('.rel', '.dom', '.xy-coord.gz', '.out.gz'))
    if all_exist:
        return

    # Copy .rel and .dom from .in.zip
    with zipfile.ZipFile(os.path.join(iavalanche_dir, aname+'.in.zip')) as in_zip:
        for ext in ('.rel', '.xy-coord'):
            copy_from_zip(in_zip, f'{aname}{ext}', os.path.join(oavalanche_dir, f'{aname}{ext}'))

        # .dom requires a bit of digging...
        copy_from_zip(in_zip,
            latest_dom_file(in_zip.namelist()),
            os.path.join(oavalanche_dir, f'{aname}.dom'))


    # Copy .out.gz and .xy-coord.gz from .out.zip
    with zipfile.ZipFile(os.path.join(iavalanche_dir, aname+'.out.zip')) as out_zip:
        # .out.gz needs to be recompressed
        copy_from_zip_to_gz(
            out_zip, f'{aname}.out',
            os.path.join(oavalanche_dir, f'{aname}.out.gz'))



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


    # Find all available individual runs
    for ix,release_file in enumerate(release_files):
#        # DEBUG
#        if ix>1:
#            break

        jb = rammsutil.parse_release_file(release_file)
        ojb = oramms_name.copy(pra_size=jb.pra_size)
        ids = get_job_ids(release_file)


        # Decide on what the _rel.shp and _dom.shp files should be called
        orel_base = os.path.join(oramms_name.ramms_dir, 'RELEASE', ojb.reldom_name+'_rel')
        odom_base = os.path.join(oramms_name.ramms_dir, 'DOMAIN', ojb.reldom_name+'_dom')

        # Copy _rel.shp and _dom.shp files
        irel_base = os.path.join(jb.ramms_dir, 'RELEASE', jb.reldom_name+'_rel')
        idom_base = os.path.join(jb.ramms_dir, 'DOMAIN', jb.reldom_name+'_dom')

        # Merge shapefiles
        links = list()
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

        oslope_dir = oramms_name.slope_dir
        oavalanche_dir = os.path.join(oramms_name.slope_dir, f'{ojb.return_period}{ojb.pra_size}')

        ireleasefile_dir = os.path.split(release_file)[0]

        # Figure out which avalanches have been run
        required_exts = {'.in.zip', '.out.zip',}
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
        print('Assembling PRAs:')
        for id,exts in id_exts.items():
            print(f' {id}', end='')
            sys.stdout.flush()
            if len(exts) < len(required_exts):
                continue

            copy_stage3_inputs(
                jb.avalanche_dir, f'{jb.ramms_name}_{id}',
                oavalanche_dir)
        print()



def write_to_zip(mzip, ifname, arcname):
    """The Windows fileshare we are using has poor consistency properties.
    Do some exponential backoff to wait until the file is written."""

    backoff = 1
    while True:
        try:
            mzip.write(ifname, arcname=arcname)
            return
        except FileNotFoundError as err:
            print('Retrying write to zip for ', ifname)
            if backoff >= 16:
                raise
            time.sleep(backoff)
            backoff *= 2


#_ramms3_exclude = {'forest.sav', 'lshm_rock.log'}

_ramms3RE = re.compile(r'(.*)(\.shx|\.shp|\.dbf|_maxPRESSURE\.tif|_maxHeight\.tif|_Xi\.tif|_ID\.tif|_COUNT\.tif)')

def run_ramms_stage3(oramms_name):

    oramms_dir = oramms_name.ramms_dir
    oramms_dir_rel = config.roots.relpath(oramms_dir)
    cmd = ['sh', 
        config.roots_w.join('HARNESS', 'akramms', 'sh', 'run_ramms.sh', bash=True),
        '--ramms-version', config.ramms_version,
        config.roots_w.syspath(oramms_dir_rel, bash=True), '3']    # '3'=stage 3

    with ioutil.TmpDir() as tdir:
        # Long timeout because mosaic can take a long time!!!
        dynamic_outputs = harnutil.run_remote_queued([], cmd, tdir, write_inputs=False, at_front=True, timeout=3*3600)

#    dynamic_outputs = ['/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/forest.sav', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L.dbf', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L.shp', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L.shx', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L_AblagerungStef.tif', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L_COUNT.tif', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L_ID.tif', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L_Xi.tif', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L_maxHeight.tif', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L_maxPRESSURE.tif', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/juneauAFor_5m/juneauAFor_5m_30L_maxVelocity.tif', '/mnt/avalanche_sim/prj/juneauA/ORAMMS/juneauA30LFor_5m/RESULTS/lshm_rock.log']

    # Copy output into final zip file
    # (for easy transport to visulatization computer)
    maps_dir = os.path.join(oramms_name.scene_dir, 'maps')
    os.makedirs(maps_dir, exist_ok=True)


    # Group output files into the Zip we will put them in
    groups = dict()
    for ifname_rel in dynamic_outputs:
        ifname = config.roots.syspath(ifname_rel)
        arcname = os.path.split(ifname)[1]
        match = _ramms3RE.match(arcname)
        if match is None:
            continue

        root = match.group(1)
        try:
            group = groups[root]
        except KeyError:
            group = list()
            groups[root] = group
        group.append((arcname, ifname))


    # Make the Zip files
    zip_outputs = list()
    for root,members0 in groups.items():

        # (Files are added in general creation order)

        # Copy in the main scene.cdl file
        members = [('scene.cdl', os.path.join(oramms_name.scene_dir, 'scene.cdl'))]

        # Identify files from the RELEASE dir to copy in
        release_dir = os.path.join(oramms_name.scene_dir, 'RELEASE')
        for name in sorted(os.listdir(release_dir)):
            if name.startswith(root):
                members.append((name, os.path.join(release_dir, name)))

        # Add in the original files
        members += members0

        # Create the zipfile
        zip_fname = os.path.join(maps_dir, f'{root}_maps.zip')
        with zipfile.ZipFile(zip_fname, 'w', compression=zipfile.ZIP_DEFLATED) as mzip:
            for arcname, ifname in members:
                write_to_zip(mzip, ifname, arcname)
        zip_outputs.append(zip_fname)

    # Delete ORAMMS directory
#    shutil.rmtree(oramms_dir, ignore_errors=True)

    # Convert zip outputs to relative filenames
    return [config.roots.relpath(x) for x in zip_outputs]



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
    ramms3_outputs = list()    # Outputs of raw RAMMS Stage 3
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
            ramms3_outputs.append(os.path.join(jb.ramms_dir, f'{jb.ramms_name}{ext}'))
            outputs.append(os.path.join(jb.scene_dir, 'AVMAPS', f'{jb.ramms_name}{ext}'))

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

