from uafgi.util import make,shputil,ioutil
from akramms import config,params
from akramms import r_prepare,stages
from akramms.util import paramutil,harnutil
import os,sys
from akramms import config

def main():

    scene_dir = config.roots.join('prj', 'juneau1_1981_1990')

    # Set up a new workspace directory, and set ALL parameters for our computation
    # (across ArcGIS, eCognition, RAMMS, etc)
    scene_dir = r_prepare.prepare_scene(
        config.roots.join('prj', 'juneau1'), defaults='alaska',
#        return_periods=[10,30,100,300],
#        forests=[1,0],    # True,False],
        return_periods=[30],
        forests=[1],
        dem_file=config.roots.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'),
        forest_file=config.roots.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_EvergreenForest_AKAlbers_EPSG_3338.tif'),
        snowdepth_geo=config.roots.join('data', 'lader', 'sx3', 'geo_southeast.nc'),
        snowdepth_file=config.roots.join('data', 'outputs', 'sx3', 'ccsm_sx3_1981_1990.nc'))


    scene_args = params.load(scene_dir)
    print(scene_args)

    stages.run_stage0(scene_dir)
    stages.run_stage1(scene_dir)

main()
