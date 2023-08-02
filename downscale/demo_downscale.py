from uafgi.util import make,shputil
from akramms import config,params,process_tree
from akramms import r_prepare, r_ecog, r_pra_post, r_domain_builder, r_ramms, r_snow
from akramms.util import paramutil,harnutil,rammsutil
import os,sys
import setuptools.sandbox
import pandas as pd

def main():
    scene_dir = config.roots.syspath('{PRJ}/juneauA')
    scene_args = params.load(scene_dir)

    distance_from_coastA_tif = os.path.join(scene_dir, 'distance_from_coastA.tif')
    rule = r_snow.distance_from_coast_rule(
        scene_args['snowdepth_geo'], distance_from_coastA_tif)
    rule()

    rule = r_snow.lapse_sx3_rule(
        scene_dir, scene_args['snowdepth_file'], scene_args['snowdepth_geo'],
        distance_from_coastA_tif)
    rule()

main()

