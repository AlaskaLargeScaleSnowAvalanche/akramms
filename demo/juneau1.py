from uafgi.util import make
import dggs.data
from dggs.avalanche import avalanche, pra_post, domain_builder, ramms
from dggs.util import paramutil,harnutil
import os
import setuptools.sandbox

def add_akramms_rules(makefile, scene_dir, debug=False):

    scene_args = avalanche.params.load(scene_dir)

    # Run ArcGIS script to prepare files for eCognition
    makefile.add(
        avalanche.prepare_data_rule('davos', scene_dir, dggs.data.HARNESS_WINDOWS))

    # Get neighbor1 graph for DEM routing network
    dem_file = scene_args['dem_file']
    dem_filled_file,sinks_file,neighbor1_file = makefile.add(domain_builder.neighbor1_rule(
        dem_file, scene_dir, fill_sinks=True)).outputs

    # Loop over combos
    for return_period in scene_args['return_periods']:
        for forest in scene_args['forests']:

            # One RAMMS directory per loop iteration...
            ramms_dir = ramms.ramms_dir(scene_dir, return_period, forest)

            # Run eCognition
            makefile.add(avalanche.run_ecog_rule(scene_dir, return_period, forest))

            # Post-Process eCognition Output
            # [f'{name}_{For}_{resolution}m_{return_period}{cat_letter}_rel.shp', ...]
            release_files = makefile.add(
                pra_post.release_rule(scene_dir, return_period, forest, ramms_dir, require_all=False)).outputs

            # Domain finder for post-process output
            domain_files = list()
            for pra_file in release_files:
#            for pra_file in release_files[3:]:    # TESTING: Do only L (large)
                pra_burn_file = '{}_burn.pik.gz'.format(pra_file[:-4])    # Same dir, .pik.gz does not pollute directory of .shp
                makefile.add(
                    domain_builder.burn_pra_rule(dem_file, pra_file, pra_burn_file))

                # Different directory for chull and domain
                pra_name = os.path.split(pra_file)[1][:-4]
                chull_file = os.path.join(ramms_dir, 'CHULL', '{}_chull.shp'.format(pra_name))
                domain_file = os.path.join(ramms_dir, 'DOMAIN', '{}_dom.shp'.format(pra_name))
                makefile.add(domain_builder.domain_rule(
                    dem_filled_file, pra_burn_file, chull_file, domain_file, min_alpha=18., margin=1000.))
                domain_files.append(domain_file)

            # Now we have the input files for a RAMMS run:
            #    rammsdir_files, release_files, domain_files
            rammsdir_files = makefile.add(ramms.rammsdir_rule(
                scene_dir, return_period, forest, dggs.data.HARNESS_WINDOWS,
                debug=debug)).outputs[0]
            scenario_file = rammsdir_files[0]
            linked_files = rammsdir_files[1:]


def main():

    makefile = make.Makefile()

    # Set up a new workspace directory, and set ALL parameters for our computation
    # (across ArcGIS, eCognition, RAMMS, etc)
    scene_dir = avalanche.prepare_scene(
        dggs.data.join('prj', 'juneau1'), defaults='alaska',
#        return_periods=[10,30,100,300],
#        forests=[1,0],    # True,False],
        return_periods=[30],
        forests=[1],
        dem_file=dggs.data.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'),
        forest_file=dggs.data.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_EvergreenForest_AKAlbers_EPSG_3338.tif'),
        snowdepth_geo=dggs.data.join('data', 'lader', 'sx3', 'geo_southeast.nc'),
        snowdepth_file=dggs.data.join('data', 'lader', 'sx3', 'gfdl_sx3_1986.nc'))

    add_akramms_rules(makefile, scene_dir)

    setup_py = os.path.join(harnutil.HARNESS, 'akramms', 'setup.py')
    prefix = os.path.join(harnutil.HARNESS, 'akramms', 'inst')
    cmd = ['install', '--prefix', prefix]
    print('setup.py ', cmd)
    setuptools.sandbox.run_setup(setup_py, cmd)

    makefile.generate('juneau1_mk')#, run=True)

main()
