import dggs.data
from dggs import avalanche
from dggs.util import paramutil,harnutil
import os

# Set up a new workspace directory, and set ALL parameters for our computation
# (across ArcGIS, eCognition, RAMMS, etc)
scene_dir = avalanche.prepare_scene(
    dggs.data.join('prj', 'juneau1'), defaults='alaska',
    dem=dggs.data.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'),
    forest=dggs.data.join('data', 'wolken', 'BaseData_AKAlbers', 'Juneau_EvergreenForest_AKAlbers_EPSG_3338.tif'))

# Step 1: Run ArcGIS script to prepare files for eCognition
#avalanche.prepare_data_rule('davos', scene_dir, dggs.data.HARNESS_WINDOWS)()

# Step 2: Run eCognition
# Test out ALL the process trees
#for rp in [10,30,100,300]:
#    for forest in (True, False):
#        avalanche.run_ecog_rule(scene_dir, rp, forest)()

rp = 30
forest = True
avalanche.run_ecog_rule(scene_dir, rp, forest)()


#avalanche.run_ecog_rule(scene_dir, 30, True)()
#avalanche.run_ecog_rule(scene_dir, 100, True)()

