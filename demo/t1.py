from dggs import avalanche
import os

thisdir = os.path.split(os.path.abspath(__file__))[0]
akramms = os.path.split(thisdir)[0]

# Set up a new workspace directory, and set ALL parameters for our computation
# (across ArcGIS, eCognition, RAMMS, etc)
scene_dir = avalanche.prepare_scene(
    os.path.join(thisdir, 'scene1'), defaults='schweitz',
    dem=os.path.join(akramms, 'SampleProjects/PRA_ElizabethAK/DEM_5m_Evolenw_StMartin_buffer100m.tif'),
    forest=os.path.join(akramms, 'SampleProjects/PRA_ElizabethAK/Wald_extreme_tot_final_10m.tif'))

# Step 1: Run ArcGIS script to prepare files for eCognition
avalanche.prepare_data_rule(scene_dir)()
