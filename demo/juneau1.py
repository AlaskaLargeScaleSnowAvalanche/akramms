import dggs.data
from dggs import avalanche,pra_post
from dggs.util import paramutil,harnutil
import os

# Set up a new workspace directory, and set ALL parameters for our computation
# (across ArcGIS, eCognition, RAMMS, etc)
scene_dir = avalanche.prepare_scene(
    dggs.data.join('prj', 'juneau1'), defaults='alaska',
    dem=dggs.data.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'),
    forest=dggs.data.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_EvergreenForest_AKAlbers_EPSG_3338.tif'),
    snowdepth_geo=dggs.data.join('data', 'lader', 'sx3', 'geo_southeast.nc'),
    snowdepth_file=dggs.data.join('data', 'lader', 'sx3', 'gfdl_sx3_1986.nc'),
)

# Step 1: Run ArcGIS script to prepare files for eCognition
# avalanche.prepare_data_rule('davos', scene_dir, dggs.data.HARNESS_WINDOWS)()

# Step 2: Run eCognition
# Test out ALL the process trees
#for rp in [10,30,100,300]:
#    for forest in (True, False):
#        avalanche.run_ecog_rule(scene_dir, rp, forest)()

# Step 4: Post-processing of eCognition stuff, ready for RAMMS
pra_post.pra_post_rule(scene_dir, require_all=False)()
