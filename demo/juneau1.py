from uafgi.util import make,shputil,ioutil
import dggs.data
from dggs.avalanche import avalanche, pra_post, domain_builder, ramms,akramms
from dggs.util import paramutil,harnutil
import os,sys
import setuptools.sandbox
from dggs import config



def main():

    scene_dir = config.roots.abspath('{PRJ}/juneau1')
    print(scene_dir)
    print(config.roots.relpath(scene_dir))
    return


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


    scene_args = avalanche.params.load(scene_dir)
    print(scene_args)

#    ramms_dirs_release_files = akramms.run_stage1(scene_dir)
#    outputs = akramms.run_stage1(scene_dir)
    print('xxx1 ', outputs)


##    release_files = akramms.run_stage1(scene_dir)
#
#    release_files = ramms.get_release_files(os.path.join(scene_dir, 'RAMMS/juneau130yFor/RESULTS/juneau1_For/5m_30L'))
#    print(release_files)
#
##    akramms.run_stage2(release_files)    # Enlarge domains, get it done
#
#    ramms_dir = os.path.join(scene_dir, 'RAMMS/juneau130yFor')#/RESULTS/juneau1_For/5m_30L')
##    ramms.run_ramms('davos', ramms_dir, 3, 3, dggs.data.HARNESS_WINDOWS)


#    with ioutil.TmpDir() as tdir:
#        ramms_dirs_release_files = akramms.add_stage1_rules(make.Makefile(), scene_dir)
#        for ramms_dir,release_files in ramms_dirs_release_files:
#            print('xxx ', ramms_dir, release_files)
##        ramms.stage3('davos', ramms_dir, dggs.data.HARNESS_WINDOWS, tdir)

main()
