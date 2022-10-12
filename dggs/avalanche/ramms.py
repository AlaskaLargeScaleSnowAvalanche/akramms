import os,subprocess
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
    idlrt_exe=r'C:\Program Files\Harris/IDL88/bin/bin.x86_64/idlrt.exe',
#    ramms_lshm_sav=r'C:\Users\efischer\Downloads\RAMMS_LSHM_NEW2022\ramms_lshm.sav',
    ramms_lshm_sav=r'C:\opt\220922-RAMMS-x0928\ramms_lshm.sav',
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
        print(' '.join(cmd1))
        if not dry_run:
            proc1 = subprocess.Popen(cmd)
            cmd2 = ['ssh', hostname, 'tail', '-f', harnutil.remote_windows_name(log_file,  HARNESS_REMOTE, bash=True)]
            print(' '.join(cmd2))
            subprocess.run(cmd1, check=True)            

    return make.Rule(action,
        [run_ramms_sh] + input_files,
        [run_ramms_sh+'.xxx'])    # We don't really know the output files yet


