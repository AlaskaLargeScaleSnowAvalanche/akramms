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

def rammsdir_rule(scene_dir, return_period, forest, HARNESS_REMOTE,
    debug=False, alt_lim_top=1500, alt_lim_low=1000, ncpu=8, ncpu_preprocess=4, cohesion=50):

    """Generates the scenario file, which becomes key to running RAMMS.
    HARNESS_REMOTE:
        Location of ~/git on remote Windows machine (parent of akramms/ repo)
    """

    scene_args = avalanche.params.load(scene_dir)
    resolution = scene_args['resolution']
    name = scene_args['name']
    For = 'For' if forest else 'NoFor'

    xscenario_name = scenario_name(scene_dir, return_period, forest)
    xramms_dir = ramms_dir(scene_dir, xscenario_name)
    scenario_file = os.path.join(xramms_dir, 'scenario.txt')
    run_ramms_sh = os.path.join(xramms_dir, 'run_ramms.sh')
    run_ramms_bat = os.path.join(xramms_dir, 'run_ramms.bat')


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

        # Create RAMMS run script
        args = [ramms_lshm_sav, '-args', harnutil.remote_windows_name(scenario_file, HARNESS_REMOTE)]

        cmd = [harnutil.bash_name(idlrt_exe)] + args
        with open(run_ramms_sh, 'w') as out:
            out.write("'{}'\n".format("' '".join(cmd)))

        cmd = [idlrt_exe] + args
        with open(run_ramms_bat, 'w') as out:
            out.write("'{}'\n".format("' '".join(cmd)))


    inputs = [d[0] for d in links]
    linked_files = [d[1] for d in links]
    outputs = [run_ramms_sh, run_ramms_bat, scenario_file] + linked_files
    print('rammsdir ',outputs)
    return make.Rule(action, inputs, outputs)
# --------------------------------------------------------------------

def ramms_rule(hostname, run_ramms_sh, input_files, HARNESS_REMOTE, dry_run=False):

    log_file = os.path.join(os.path.dirname(run_ramms_sh), 'RESULTS', 'lshm_rock.log')
    def action(tdir):
        print('Running RAMMS ', run_ramms_sh)

        # Create remote dir
        cmd = ['ssh', hostname, 'mkdir', '-p', harnutil.remote_windows_name(os.path.split(run_ramms_sh)[0], HARNESS_REMOTE, bash=True)]
        subprocess.run(cmd, check=True)

        # Sync RAMMS files to remote dir
        harnutil.rsync_files([run_ramms_sh] + input_files, hostname, HARNESS_REMOTE, tdir)

        # Run RAMMS
        cmd1 = ['ssh', hostname, 'sh', harnutil.remote_windows_name(run_ramms_sh, HARNESS_REMOTE, bash=True)]
        subprocess.run(cmd1, check=True)            


#        print(' '.join(cmd1))
#        if not dry_run:
#            proc1 = subprocess.Popen(cmd)
#            cmd2 = ['ssh', hostname, 'tail', '-f', harnutil.remote_windows_name(log_file,  HARNESS_REMOTE, bash=True)]
#            print(' '.join(cmd2))
#            subprocess.run(cmd1, check=True)            

    return make.Rule(action,
        [run_ramms_sh] + input_files,
        [run_ramms_sh+'.xxx'])    # We don't really know the output files yet


# ----------------------------------------------------------
#_doneRE = re.compile(r"\s*Creating MUXI-Files...")    # Demo
_doneRE = re.compile(r"\s*Finsihed writing GEOTIFF files!")    # Prod
def run(idlrt_exe, ramms_sav, ramms_dir):

    print(f'***** Running Top-Leve RAMMS on {ramms_dir}')
    logfile = os.path.join(ramms_dir, 'RESULTS', 'lshm_rock.log')
    print(f'logfile = {logfile}')

    # Remove logfile (if it exists)
    try:
        os.remove(logfile)
    except FileNotFoundError:
        pass

    # Avoid extra IDL's lying around that would eat our license
    cmd = ['taskkill.exe', '/F', '/IM', 'idlrt.exe']
    subprocess.run(cmd)

    # Start the main process running
    cmd1 = [idlrt_exe, ramms_sav, '-args',
        os.path.join(ramms_dir, 'scenario.txt')]
    print(' '.join("'{}'".format(x) for x in cmd1))

    proc1 = subprocess.Popen(cmd1)
#    print('started')
#    time.sleep(10)
#    print('Done sleeping ', proc1.returncode)
#    return

    try:
        xout = None
        fin = None
        xout = open('x.out', 'w')
        proc1 = subprocess.Popen(cmd1, stdout=xout, stderr=subprocess.STDOUT)

        timeout = 0.5
        state = 0
        while True:
#            # Addend to main process
#            try:
#                print('Communicate')
#                stdout, stderr = proc1.communicate(input, timeout=timeout)
#            except subprocess.TimeoutExpired:
#                pass

            time.sleep(0.5)

            # See if it exited unexpectedly
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
            # https://winaero.com/kill-process-windows-10/
            cmd = ['taskkill.exe', '/F', '/PID', str(proc1.pid)]
            print(' '.join("'{}'".format(x) for x in cmd))
            subprocess.run(cmd, check=False)

            # Just in case, wait for it to exit.
#            proc1.communicate()
            print('************ ALL DONE!!! ****************')

        if xout is not None:
            xout.close()



#  taskkill /f /im idlrt.exe
