from uafgi.util import make
import dggs.data
from dggs import avalanche
from dggs.util import paramutil,harnutil
import os

def add_akramms_rules(makefile, scene_dir):

    scene_args = avalanche.params.load(scene_dir)

    # Run ArcGIS script to prepare files for eCognition
    makefile.add(
        avalanche.prepare_data_rule('davos', scene_dir, dggs.data.HARNESS_WINDOWS))

    # Get neighbor1 graph for DEM routing network
    neighbor1_file = makefile.add(
        avalanche.neighbor1_rule(scene_args['dem_file'], fill_sinks=True)).outputs[0]

    # Loop over combos
    for return_period in scene_args['return_periods']:
        for forest in scene_args['forests']:

            # Run eCognition
            makefile.add(avalanche.run_ecog_rule(scene_dir, return_period, forest))

            # Post-Process eCognition Output
            # [f'{name}_{For}_{resolution}m_{return_period}{cat_letter}_rel.shp', ...]
            pra_files = makefile.add(
                avalanche.pra_post_rule(scene_dir, return_period, forest, require_all=False)).outputs

            # Domain finder for post-process output
            for pra_file in pra_files:
                domain_file = '{}_domains.shp'.format(pra_file[:-4])
                makefile.add(
                    avalanche.domain_rule(neighbor1_file, pra_file, domain_file))

def main():

    makefile = make.Makefile()

    # Set up a new workspace directory, and set ALL parameters for our computation
    # (across ArcGIS, eCognition, RAMMS, etc)
    scene_dir = avalanche.prepare_scene(
        dggs.data.join('prj', 'juneau1'), defaults='alaska',
        return_periods=[10,30,100,300],
        forests=[1,0],    # True,False],
        dem_file=dggs.data.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'),
        forest_file=dggs.data.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_EvergreenForest_AKAlbers_EPSG_3338.tif'),
        snowdepth_geo=dggs.data.join('data', 'lader', 'sx3', 'geo_southeast.nc'),
        snowdepth_file=dggs.data.join('data', 'lader', 'sx3', 'gfdl_sx3_1986.nc'))

    add_akramms_rules(makefile, scene_dir)
    makefile.generate('juneau1_mk')

main()
