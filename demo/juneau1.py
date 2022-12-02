from uafgi.util import make,shputil
import dggs.data
from dggs.avalanche import avalanche, pra_post, domain_builder, ramms,akramms
from dggs.util import paramutil,harnutil
import os,sys
import setuptools.sandbox




def main():


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

    release_files = akramms.run_stage1(scene_dir)

#    akramms_stage2(release_files)    # Enlarge domains, get it done

main()
