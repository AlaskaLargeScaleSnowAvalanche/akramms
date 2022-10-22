import os,subprocess,re,sys,time
from dggs.avalanche import avalanche
from dggs.util import harnutil
from uafgi.util import make,ioutil
import itertools, functools

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
            kwargs['keep_data'] = '0'
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
def ramms_rule(hostname, ramms_dir, input_files, HARNESS_REMOTE, dry_run=False):

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

    return make.Rule(action,
        input_files,
        ['.xxx'])    # We don't really know the output files yet


# ----------------------------------------------------------
def kill_idl():
    cmd = ['taskkill.exe', '/F', '/IM', 'idlrt.exe']
    subprocess.run(cmd)
    cmd = ['taskkill.exe', '/F', '/IM', 'idl_opserver.exe']
    subprocess.run(cmd)


#_doneRE = re.compile(r"\s*Creating MUXI-Files...")    # Demo
_doneRE = re.compile(r"\s*Finsihed writing GEOTIFF files!")    # Prod
def run_on_windows(idlrt_exe, ramms_sav, ramms_dir):
    """Call this to run top-level RAMMS locally on Windows.
    idlrt_exe:
        Windows path to idlrt.exe IDL runtime
    ramms_sav:
        Windows path to lhsm RAMMS .sav file
    ramms_dir:
        RAMMS directory to run
    Returns:
        Nothing if OK.
        Raises Exception if it did not complete.
    """
    print(f'***** Running Top-Level RAMMS on {ramms_dir}')


    # Remove logfile (if it exists)
    logfile = os.path.join(ramms_dir, 'RESULTS', 'lshm_rock.log')
    try:
        os.remove(logfile)
    except FileNotFoundError:
        pass

    # Avoid extra IDL's lying around that would eat our license
    kill_idl()

    # Create batch file to run
    scenario_txt = os.path.join(ramms_dir, 'scenario.txt')
    batfile = os.path.join(ramms_dir, 'run_ramms.bat')
    with open(batfile, 'w') as out:
        out.write(f'"{idlrt_exe}" "{ramms_sav}" -args "{scenario_txt}"\n')

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
                print(line, end='')
                if _doneRE.match(line) is not None:
                    raise EOFError()   # Break out of double loop

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
