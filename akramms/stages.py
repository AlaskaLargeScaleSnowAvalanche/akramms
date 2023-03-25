from uafgi.util import make,shputil
from akramms import config,params,process_tree
from akramms import r_prepare, r_ecog, r_pra_post, r_domain_builder, r_ramms
from akramms.util import paramutil,harnutil,rammsutil
import os,sys
import setuptools.sandbox


def add_stage0_rules(makefile, scene_dir):

    scene_args = params.load(scene_dir)

    # Run ArcGIS script to prepare files for eCognition
    prepare_outputs = makefile.add(r_prepare.rule(scene_dir)).outputs

    # Get neighbor1 graph for DEM routing network
    dem_file = scene_args['dem_file']
    dem_filled_file,sinks_file,neighbor1_file = makefile.add(r_domain_builder.neighbor1_rule(
        dem_file, scene_dir, fill_sinks=True)).outputs

    # Loop over combos
#    ramms_dirs_release_files = list()    # [(ramms_dir, [release_file, ...]), ...]
#    all_ramms_dirs = list()
    all_release_files = list()    # Release files we will run RAMMS on
    for return_period in scene_args['return_periods']:
        for forest in scene_args['forests']:

            # Run eCognition
            makefile.add(r_ecog.rule(scene_dir, prepare_outputs, return_period, forest))

            # Burn PRAs produced by eCognition into raster
            pra_file, pra_burn_file = process_tree.pra_files(scene_args, return_period, forest)
            makefile.add(
                r_domain_builder.burn_pra_rule(dem_file, pra_file, pra_burn_file))

            # Post-Process eCognition Output (the pra_file)
            # [f'{scene_name}{For}_{resolution}m_{return_period}{cat_letter}_rel.shp', ...]
            release_shplists = makefile.add(
                r_pra_post.rule(scene_dir, return_period, forest, require_all=False)).outputs

def read_shplists(scene_args):
    """Returns: release_files"""

    release_files = list()    # Release files we will run RAMMS on
    for return_period in scene_args['return_periods']:
        for forest in scene_args['forests']:
            for pra_size in rammsutil.PRA_SIZES.keys():    # T,S,M,L
                # DEBUG: Only do 'L' for now
                if pra_size not in config.allowed_pra_sizes:
                    continue

                # Figure out which release files we have for this (return_period, forest, pra_size)
                resolution = scene_args['resolution']
                scene_name = scene_args['name']

                jb = rammsutil.RammsName(
                    os.path.join(scene_dir, 'RAMMS'),
                    scene_args['name'], None, forest, resolution,
                    return_period, pra_size, None)

                release_shplist = os.path.join(scene_dir, 'RAMMS', f'{jb.ramms_name}_rel.shplist')

                with open(release_shplist, 'r') as fin:
                    release_files.extend(config.roots.syspath(x.strip()) for x in fin)
    return release_files

def add_stage1_rules(makefile, scene_dir):

    scene_args = params.load(scene_dir)

    dem_file = scene_args['dem_file']
    dem_root = os.path.split(dem_file)[1][:-4]
    dem_filled_file = os.path.join(scene_dir, f'{dem_root}_filled.tif')

    # Read release files from *_rel.shplist
    release_files = read_shplists(scene_args)

    # Domain finder for post-process output
    for release_file in release_files:
        jb = rammsutil.parse_release_file(release_file)

#        pra_burn_file = os.path.join(jb.ramms_dir, 'RELEASE', f'{jb.ramms_name}_burn.pik.gz')
#        makefile.add(
#            r_domain_builder.burn_pra_rule(dem_file, release_file, pra_burn_file))

        # Different directory for chull and domain
        chull_file = os.path.join(jb.ramms_dir, 'CHULL', '{}_chull.shp'.format(jb.ramms_name))
        domain_file = os.path.join(jb.ramms_dir, 'DOMAIN', '{}_dom.shp'.format(jb.ramms_name))
        makefile.add(r_domain_builder.domain_rule(
            dem_filled_file, release_file, pra_burn_file, chull_file, domain_file, min_alpha=18., margin=config.initial_margins[jb.pra_size]))


        # Now we have the input files for a RAMMS run:
        #    rammsdir_files, release_files, domain_files
        rammsdir_files = makefile.add(r_ramms.rammsdir_rule(
            scene_dir, release_file)).outputs

        # RAMMS Stage 1: IDL Prep
        ramms_files = shputil.expand_list([release_file, domain_file]) + rammsdir_files
        stage1_outputs = makefile.add(r_ramms.ramms_stage1_rule(
            release_file, ramms_files, dry_run=False, submit=False)).outputs

    return release_files



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
def run_stage0(scene_dir):
    makefile = make.Makefile()
    ramms_dirs_release_files = add_stage0_rules(makefile, scene_dir)

    makefile.generate(
        os.path.join(scene_dir, 'stage0_mk'),
        run=True, ncpu=1)
    return ramms_dirs_release_files
# =====================================================================
def run_stage1(scene_dir):
    makefile = make.Makefile()
    ramms_dirs_release_files = add_stage1_rules(makefile, scene_dir)

    # We do this to make sure the domain finder C++ code is compiled.
    setup_py = os.path.join(harnutil.HARNESS, 'akramms', 'setup.py')
    prefix = os.path.join(harnutil.HARNESS, 'akramms', 'inst')
    cmd = ['install', '--prefix', prefix]
    print('setup.py ', cmd)
    setuptools.sandbox.run_setup(setup_py, cmd)

    makefile.generate(
        os.path.join(scene_dir, 'stage1_mk'),
        run=True, ncpu=1)
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

    makefile.generate('juneau1_mk', run=True, ncpu=1)
    return stage3_outputs
