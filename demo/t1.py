from dggs import avalanche,arcgis
import os

# Set up a new workspace directory, and set ALL parameters for our computation
# (across ArcGIS, eCognition, RAMMS, etc)
name = 'xxx'
scene_dir = avalanche.prepare_scene(
    os.path.join('.', name), defaults='schweitz',
    name=name,
    dem='SampleProjects/PRA_ElizabethAK/DEM_5m_Evolenw_StMartin_buffer100m.tif',
    forest='SampleProjects/PRA_ElizabethAK/Wald_extreme_tot_final_10m.tif')

# Step 1: Run ArcGIS script to prepare files for eCognition
avalanche.prepare_data_rule(scene_dir)()
