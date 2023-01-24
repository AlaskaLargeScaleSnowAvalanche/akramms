from uafgi.util import make,shputil
import dggs.data
from dggs.avalanche import avalanche, pra_post, domain_builder, ramms,rammsutil
from dggs.util import paramutil,harnutil
import os,sys
import setuptools.sandbox

def add_stage1_rules(makefile, scene_dir, debug=False, windows_host='davos'):

    scene_args = avalanche.params.load(scene_dir)

    # Run ArcGIS script to prepare files for eCognition
    makefile.add(
        avalanche.prepare_data_rule(windows_host, scene_dir, dggs.data.HARNESS_WINDOWS))

    # Get neighbor1 graph for DEM routing network
    dem_file = scene_args['dem_file']
    dem_filled_file,sinks_file,neighbor1_file = makefile.add(domain_builder.neighbor1_rule(
        dem_file, scene_dir, fill_sinks=True)).outputs

    # Loop over combos
    ramms_dirs_release_files = list()    # [(ramms_dir, [release_file, ...]), ...]
    all_ramms_dirs = list()
    all_release_files = list()    # Release files we will run RAMMS on
    for return_period in scene_args['return_periods']:
        for forest in scene_args['forests']:

            # One RAMMS directory per loop iteration...
            scenario_name = rammsutil.scenario_name(
                scene_args['name'], return_period, forest)
            ramms_dir = rammsutil.ramms_dir(scene_dir, scenario_name)
            all_ramms_dirs.append(ramms_dir)

            # Run eCognition
            makefile.add(avalanche.run_ecog_rule(scene_dir, return_period, forest))

            # Post-Process eCognition Output
            # [f'{name}_{For}_{resolution}m_{return_period}{cat_letter}_rel.shp', ...]
            release_files = makefile.add(
                pra_post.release_rule(scene_dir, return_period, forest, ramms_dir, require_all=False)).outputs

            # TESTING: Do only L (and M)
            release_files = release_files[2:]    # DEBUG
            print('release_files ',release_files)
            ramms_dirs_release_files.append((ramms_dir, release_files))

            # Domain finder for post-process output
            domain_files = list()
            for release_file in release_files:
                jb = rammsutil.parse_release_file(release_file)

                pra_burn_file = '{}_burn.pik.gz'.format(release_file[:-4])    # Same dir, .pik.gz does not pollute directory of .shp
                makefile.add(
                    domain_builder.burn_pra_rule(dem_file, release_file, pra_burn_file))

                # Different directory for chull and domain
                pra_name = os.path.split(release_file)[1][:-8]
                chull_file = os.path.join(ramms_dir, 'CHULL', '{}_chull.shp'.format(pra_name))
                domain_file = os.path.join(ramms_dir, 'DOMAIN', '{}_dom.shp'.format(pra_name))
                makefile.add(domain_builder.domain_rule(
                    dem_filled_file, pra_burn_file, chull_file, domain_file, min_alpha=18., margin=1000.))
                domain_files.append(domain_file)

            # Now we have the input files for a RAMMS run:
            #    rammsdir_files, release_files, domain_files
            rammsdir_files = makefile.add(ramms.rammsdir_rule(
                ramms_dir, scenario_name, scene_dir, return_period, forest, dggs.data.HARNESS_WINDOWS,
                debug=debug)).outputs

            # RAMMS Stage 1: IDL Prep
            ramms_files = shputil.expand_list(release_files + domain_files) + rammsdir_files
            stage1_outputs = makefile.add(ramms.ramms_stage1_rule(
                windows_host, ramms_dir, release_files, ramms_files, dggs.data.HARNESS_WINDOWS, dry_run=False)).outputs


            all_release_files += release_files
            ramms_dirs_release_files.append((ramms_dir, release_files))
#            ramms_dirs_release_files.append((ramms_dir, release_files, stage1_outputs))


            break    # DEBUG

    return ramms_dirs_release_files
#    return all_ramms_dirs,all_release_files


def add_stage3_rules(makefile, ramms_dirs_release_files, debug=False, windows_host='davos'):
    """ramms_dirs_release_files:
        Output from add_stage1_rules()
    """

    stage3_outputs = list()
    for ramms_dir, release_files in ramms_dirs_release_files:
        out = makefile.add(ramms.ramms_stage3_rule(
            windows_host, ramms_dir, release_files,
            dggs.data.HARNESS_WINDOWS, dry_run=False)).outputs
        stage3_outputs.extend(out)

    return stage3_outputs
# -------------------------------------------------------------------
def run_stage1(scene_dir):
    makefile = make.Makefile()
    ramms_dirs_release_files = add_stage1_rules(makefile, scene_dir)

    # We do this to make sure the domain finder C++ code is compiled.
    setup_py = os.path.join(harnutil.HARNESS, 'akramms', 'setup.py')
    prefix = os.path.join(harnutil.HARNESS, 'akramms', 'inst')
    cmd = ['install', '--prefix', prefix]
    print('setup.py ', cmd)
    setuptools.sandbox.run_setup(setup_py, cmd)

    makefile.generate('juneau1_mk', run=True, ncpu=1)
    return ramms_dirs_release_files
# =====================================================================
def run_stage2(scene_dir):
    """Get the simulations run to completion"""
    dummy = make.Makefile()
    ramms_dirs_release_files = add_stage1_rules(dummy, scene_dir)
    release_files = list()
    for _,rfs in ramms_dirs_release_files:
        release_files.extend(rfs)



    pass
# =====================================================================
def run_stage3(scene_dir):
    dummy = make.Makefile()
    ramms_dirs_release_files = add_stage1_rules(dummy, scene_dir)

    makefile = make.Makefile()
    stage3_outputs = add_stage3_rules(makefile, ramms_dirs_release_files)

    # We do this to make sure the domain finder C++ code is compiled.
    setup_py = os.path.join(harnutil.HARNESS, 'akramms', 'setup.py')
    prefix = os.path.join(harnutil.HARNESS, 'akramms', 'inst')
    cmd = ['install', '--prefix', prefix]
    print('setup.py ', cmd)
    setuptools.sandbox.run_setup(setup_py, cmd)

    makefile.generate('juneau1_mk', run=True, ncpu=1)
    return stage3_outputs
