import os
from dggs.avalanche import avalanche
from dggs.util import harnutil
from uafgi.util import make
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
    debug=False, alt_lim_top=1500, alt_lim_low=1000, ncpu=2, cohesion=50):
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
            if not os.path.exists(ofile):
                odir = os.path.split(ofile)[0]
                os.makedirs(odir, exist_ok=True)
                os.symlink(ifile, ofile)

        # Create the scenario file
        kwargs = dict()
        kwargs['scenario_name'] = xscenario_name
        kwargs['remote_ramms_dir'] = harnutil.remote_windows_name(xramms_dir, HARNESS_REMOTE)
        kwargs['ncpu'] = str(ncpu)
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
    return make.Rule(action, inputs, outputs)
# --------------------------------------------------------------------

#def ramms_rule(scene_dir, scenario_file, HARNESS_REMOTE):
#
#    def action(tdir):
#        print('Running RAMMS ', linked_files[0])
#
#    return make.Rule(action,
#        list(itertools.chain(linked_files, input_files)),
#        [])    # We don't really know the output files yet
#
#
