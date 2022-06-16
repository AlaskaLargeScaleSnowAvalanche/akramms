import subprocess
import os,pathlib,shutil
import netCDF4
import numpy as np
from dggs.util import paramutil,arcgisutil
from uafgi import make
from dggs.avalanche import process_tree,params




# -----------------------------------------------------------------------
# ---------------------------------------------------------------------------
def prepare_scene(scene_dir, defaults=dict(), **kwargs):

    """Sets up a new scene by creating a directory with all
    parameters required for processing.

    scene_dir:
        Top-level directory for all project files.
        The file `scene.nc` is created in this directory.
    defaults: dict or str
        dict:
            Default values for parameters, if they are not set in kwargs.
        str: 'schweitz' | 'alaska'
            Use pre-built set of defaults, appropriate for given project.
    kwargs:
        parameters to set for this scene.    
        See PARAMS variable above for a list and description.

    """

    # Create the directory
    scene_dir = os.path.abspath(scene_dir)
    os.makedirs(scene_dir, exist_ok=True)

    # Assemble the scene args, using default params if provided
    if isinstance(defaults, str):    # Lookup pre-loaded defaults
        defaults = params.DEFAULTS[defaults]
    scene_args = paramutil.validate_args({**defaults, **kwargs}, params=params.ALL)

    # Get the scene name as the leaf of the scene_dir
    if 'name' not in scene_args:
        scene_args['name'] = os.path.split(scene_dir)[1]

    # Store the overall scene parameters
    paramutil.dump_nc(os.path.join(scene_dir, 'scene.nc'), scene_args, params=params.ALL)
    cmd = ['ncdump', os.path.join(scene_dir, 'scene.nc')]
    with open(os.path.join(scene_dir, 'scene.cdl'), 'w') as out:
        subprocess.run(cmd, stdout=out)

    return scene_dir

# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
import_xml_tpl = """<?xml version="1.0" encoding="UTF-8"?>
<ImportDefinitions>
	<ImportDefinition name="PRA_import_{freq}" description="">
		<LcnsIds></LcnsIds>
		<SceneSearch folders-from-file-system="yes" bdi-driver="" scene-name="{scene_name}" map-name="">
			<TagString>{froot}_{layer}.tif</TagString>
			<SiteInfo x-coo="decimal" y-coo="decimal">
				<TagString></TagString>
			</SiteInfo>
		</SceneSearch>
		<SceneDefinition force-fitting="0" geo-coding="from-file" scene-extent="union" scene-unit="auto" pixel-size="auto">
			<ImageLayer channel="1" alias="Aspect_sectors_Nmax" driver="GDAL">
				<TagString>{froot}_Aspect_sectors_Nmax.tif</TagString>
			</ImageLayer>
			<ImageLayer channel="1" alias="Aspect_sectors_N0" driver="GDAL">
				<TagString>{froot}_Aspect_sectors_N0.tif</TagString>
			</ImageLayer>
			<ImageLayer channel="1" alias="Curv_plan" driver="GDAL">
				<TagString>{froot}_Curv_plan.tif</TagString>
			</ImageLayer>
			<ImageLayer channel="1" alias="Curv_profile" driver="GDAL">
				<TagString>{froot}_Curv_profile.tif</TagString>
			</ImageLayer>
			<ImageLayer channel="1" alias="DEM" driver="GDAL">
				<TagString>{froot}_DEM.tif</TagString>
			</ImageLayer>
			<ImageLayer channel="1" alias="Hillshade" driver="GDAL">
				<TagString>{froot}_Hillshade.tif</TagString>
			</ImageLayer>
			<ImageLayer channel="1" alias="Slope" driver="GDAL">
				<TagString>{froot}_Slope.tif</TagString>
			</ImageLayer>
			<ImageLayer channel="1" alias="PRA_raw" driver="GDAL">
				<TagString>{froot}__PRA_raw_{freq}_Forest.tif</TagString>
			</ImageLayer>
		</SceneDefinition>
	</ImportDefinition>
</ImportDefinitions>
"""
def import_xml_str(scene_args, freq):
    """Generates text for the ...import....xml file
    freq: 'frequent' | 'extreme'
    """

    args = {
        'froot': os.path.join(scene_args['scene_dir'], 'eCog', scene_args['name']),
        'scene_name': scene_args['name'],
        'freq': freq,
        'layer': '{layer}',    # Leave this for eCognition
    }
    return import_xml_tpl.format(**args)
# ---------------------------------------------------------------------------
def prepare_data_rule(scene_dir):
    """Runs the data_prep_PRA.py script on a scene"""

    scene_args = params.load(scene_dir)

    inputs = [scene_dir]
    outputs = [
        os.path.join(scene_dir, 'eCog'),
        os.path.join(scene_dir, 'stats_kernel.txt'),
        os.path.join(scene_dir, '{}_DataPrep_InputParameters.csv'.format(scene_args['name']))]

    def action(tdir):

        temporaries = [
            os.path.join(scene_dir, 'base_data'),
            os.path.join(scene_dir, 'temp_model_frequent'),
            os.path.join(scene_dir, 'temp_model_extreme')]

        # Delete all output files/folders
        # (otherwise ArcGIS complains)
        for dir in (temporaries + outputs):
            shutil.rmtree(dir, ignore_errors=True)

        # Assemble script args
        script_args = {'Workspace': scene_dir}
        for script_arg, scene_arg in [
            ('inDEM', 'dem'),
            ('resampCellSize', 'resample_cell_size'),
            ('Slope_lowerlimit_frequent', 'slope_lowerlimit_frequent'),
            ('Slope_lowerlimit_extreme', 'slope_lowerlimit_extreme'),
            ('Slope_upperlimit', 'slope_upperlimit'),
            ('Curv_upperlimit', 'curve_upperlimit'),
            ('Rugged_neighborhood', 'rugged_neighborhood'),
            ('Rugged_upperlimit', 'rugged_upperlimit')]:
            script_args[script_arg] = str(scene_args[scene_arg])

        # Optional arguments...
        for script_arg, scene_arg in [
            ('inForest', 'forest'),
            ('inPerimeter', 'clip')]:
            if scene_arg in scene_args:
                script_args[script_arg] = str(scene_args[scene_arg])

        # Generate the weighting kernel file
        kernel_txt = os.path.join(scene_dir, 'stats_kernel.txt')
        script_args['Weightingkernel'] = kernel_txt
        kernel = scene_args['stats_kernel']
        with open(kernel_txt, 'w') as out:
            out.write('{} {}\n'.format(*kernel.shape))
            for irow in range(kernel.shape[0]):
                out.write(' '.join(str(x) for x in kernel[irow,:]))
                out.write('\n')

        # Obtain ArcGIS SpatialReference object (script needs as a script variable)
        script_args['outCoordSystem'] = arcgisutil.Lambda('arcpy', 'SpatialReference', scene_args['coordinate_system'])

#        arcgisutil.run_script('data_prep_PRA.py', script_args, cwd=scene_dir, dry_run=False)

        # Clean up temporary files from ArcGIS step
        for dir in temporaries:
            shutil.rmtree(dir, ignore_errors=True)

        # Copy DEM to eCog folder
        ecog_dir = os.path.join(scene_dir, 'eCog')
        os.makedirs(ecog_dir, exist_ok=True)
        shutil.copy(scene_args['dem'], os.path.join(ecog_dir, '{}_DEM.tif'.format(scene_args['name'])))

        # Write import...xml files 
        for freq in ('frequent', 'extreme'):
            with open(os.path.join(ecog_dir, f'PRA_import_{freq}.xml'), 'w') as out:
                out.write(import_xml_str(scene_args, freq))

        # Add process trees to the eCog/ workspace
        ptdir = os.path.join(ecog_dir, 'process_trees')
        os.makedirs(ptdir, exist_ok=True)
        for leaf in process_tree.list_all():
            tpl = process_tree.load_tpl(leaf)
            with open(os.path.join(ecog_dir, 'process_trees', leaf), 'w') as out:
                args = {'scene_dir': scene_dir}
                out.write(tpl.format(**args))

        # Generate the required process trees
        for return_period in scene_args['return_periods']:

            # They are sorted into two categories: _frequent and _extreme
            return_period_category = 'frequent' if return_period < 100 else 'extreme'
            odir = os.path.join(scene_dir, f'PRA_{return_period_category}')
            os.makedirs(odir, exist_ok=True)

            for forest in (False, True):
                sforest = 'For' if forest else 'NoFor'
                with open(os.path.join(odir, f'GHK_{return_period:d}y_{sforest}.dcp')) as out:
                    out.write(process_tree.get(scene_dir, return_period, forest))

    return make.Rule(action, inputs, outputs)

