import subprocess
import os,pathlib,shutil
import netCDF4
import numpy as np
from dggs import paramutil,arcgis
from uafgi import make

# List of all parameters involved in an overall run.
PARAMS = paramutil.parse([
    ('name', None, 'str', False,
        """Root name of scene; to use for filenames, plotting, etc"""),
    ('dem', None, 'input_file', True,
        """Name of DEM file to use (GeoTIFF)"""),
    ('forest', None, 'input_file', False,
        """Name of forest cover file to use (GeoTIFF)"""),
    ('clip', None, 'input_file', False,
        """Clip domain to this region (Shapefile)"""),
    ('resample_cell_size', 'm', 'int', True,
        """Resample DEM and forest files to this resolution for computation"""),
    ('slope_lowerlimit_frequent', 'angular_degree', 'float', True,
        """Slope angle, frequent scenario"""),
    ('slope_lowerlimit_extreme', 'angular_degree', 'float', True,
        """Slope angle, extreme scenario"""),
    ('slope_upperlimit', 'angular_degree', 'float', True,
        """TODO"""),
    ('curve_upperlimit', 'rad 100-1 m-1', 'float', True,
        """TODO"""),
    ('rugged_neighborhood', None, 'int', True,
        """(pixels) TODO"""),
    ('rugged_upperlimit', '', 'float', True,
        """TODO"""),
    ('coordinate_system', None, 'str', True,
        """Coordinate system to use for intermediate and output files.
        Can be WKT string, EPS designator, etc.
        Eg: CH1903+_LV95 for Switzerland."""),
    ('return_periods', 'y', 'list', True,
        """List of return periods (years) to compute avalanche risk for"""),
    ('stats_kernel', None, 'array', True,
        """2D kernel used for statistics on DEM in ArcGIS data prep"""),
    ])


DEFAULTS = {
    'schweitz': dict(
    resample_cell_size=5,
    slope_lowerlimit_frequent=30,
    slope_lowerlimit_extreme=28,
    slope_upperlimit=55,
    curve_upperlimit=5.5,
    rugged_neighborhood=7,
    rugged_upperlimit=3.5,
    coordinate_system='CH1903+_LV95',
    return_periods=[10,30,100,300],
    stats_kernel=np.array([
        [0.625, 0.625, 0.625, 0.625, 0.625],
        [0.625, 1.5, 1.5, 1.5, 0.625],
        [0.625, 1.5, 3, 1.5, 0.625],
        [0.625, 1.5, 1.5, 1.5, 0.625],
        [0.625, 0.625, 0.625, 0.625, 0.625]])),

    'alaska': dict(
    resample_cell_size=5,
    slope_lowerlimit_frequent=30,
    slope_lowerlimit_extreme=28,
    slope_upperlimit=55,
    curve_upperlimit=5.5,
    rugged_neighborhood=7,
    rugged_upperlimit=3.5,
    coordinate_system='CH1903+_LV95',
    stats_kernel=np.array([
        [0.625, 0.625, 0.625, 0.625, 0.625],
        [0.625, 1.5, 1.5, 1.5, 0.625],
        [0.625, 1.5, 3, 1.5, 0.625],
        [0.625, 1.5, 1.5, 1.5, 0.625],
        [0.625, 0.625, 0.625, 0.625, 0.625]])),
}

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
        defaults = DEFAULTS[defaults]
    scene_args = paramutil.validate_args({**defaults, **kwargs}, params=PARAMS)

    # Get the scene name as the leaf of the scene_dir
    if 'name' not in scene_args:
        scene_args['name'] = os.path.split(scene_dir)[1]

    # Store the overall scene parameters
    paramutil.dump_nc(os.path.join(scene_dir, 'scene.nc'), scene_args, params=PARAMS)
    cmd = ['ncdump', os.path.join(scene_dir, 'scene.nc')]
    with open(os.path.join(scene_dir, 'scene.cdl'), 'w') as out:
        subprocess.run(cmd, stdout=out)

    return scene_dir

# ---------------------------------------------------------------------------
def load_scene_args(scene_dir):
    """Reads the scene """
    ret = paramutil.load_nc(os.path.join(scene_dir, 'scene.nc'))
    ret['scene_dir'] = scene_dir
    return ret


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

    scene_args = load_scene_args(scene_dir)

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
        script_args['outCoordSystem'] = arcgis.Lambda('arcpy', 'SpatialReference', scene_args['coordinate_system'])

        arcgis.run_script('data_prep_PRA.py', script_args, cwd=scene_dir, dry_run=False)

        # Clean up temporary files
        for dir in temporaries:
            shutil.rmtree(dir, ignore_errors=True)

        # Copy DEM to eCog folder
        ecog_dir = os.path.join(scene_dir, 'eCog')
        os.makedirs(ecog_dir, exist_ok=True)
        shutil.copy(scene_args['dem'], ecog_dir)

        # Write import...xml files 
        for freq in ('frequent', 'extreme'):
            with open(os.path.join(scene_args['scene_dir'], 'eCog', f'PRA_import_{freq}.xml'), 'w') as out:
                out.write(import_xml_str(scene_args, freq))

    return make.Rule(action, inputs, outputs)

