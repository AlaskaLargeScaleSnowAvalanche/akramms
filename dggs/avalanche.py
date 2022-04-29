import os,pathlib,shutil
import netCDF4
import numpy as np
from dggs import paramutil,arcgis
from uafgi import make

# List of all parameters involved in an overall run.
PARAMS = paramutil.parse([
    ('name', None, 'str', True,
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

def prepare_scene(scene_dir, defaults=dict(), **kwargs):
    """scene_dir,
        Top-level directory for all project files


    scene_args: dict
        All params needed for all aspects of the computation

        weighting_kernel: [[float, ...], ...]
            2D convolution kernel, reprented as a row major nested list of lists

        dem: 'xxx.tif'
            File for Digital Elevation Model (DEM)
        forest: 'xxx.tif'
            File for forest cover
        resample_cell-size: int
            Resolution to run at
            (dem and forest should be at least as fine as this)
        in_perimeter: file (OPTIONAL)
            
        ...
    """

    # Create the directory
    scene_dir = os.path.abspath(scene_dir)
    os.makedirs(scene_dir, exist_ok=True)

    # Assemble the scene args, using default params if provided
    if isinstance(defaults, str):    # Lookup pre-loaded defaults
        defaults = DEFAULTS[defaults]
    scene_args = paramutil.validate_args({**defaults, **kwargs}, params=PARAMS)

    # Store the overall scene parameters
    paramutil.dump_nc(os.path.join(scene_dir, 'scene.nc'), scene_args, params=PARAMS)

    return scene_dir

def load_scene_args(scene_dir):
    """Reads the scene """
    return paramutil.load_nc(os.path.join(scene_dir, 'scene.nc'))


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

    return make.Rule(action, inputs, outputs)
