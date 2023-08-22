import subprocess,functools
import os,pathlib,shutil
import netCDF4
import numpy as np
from akramms import config,process_tree
from akramms.util import paramutil,harnutil,arcgisutil
from uafgi.util import make
from akramms import params

# TODO: Tar up
# tar cvfz scene3.tar.gz $(find scene3 -name '*' -and -type f | grep -v eCog)



# -----------------------------------------------------------------------
# ---------------------------------------------------------------------------
def r_prepare_scene(scene_dir, defaults=dict(), **kwargs):

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

    def action(tdir):

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

    inputs = [kwargs['dem_file'], kwargs['snowdepth_file']]
    if 'forest_file' in kwargs:
        inputs.append(kwargs['forest_file'])
    outputs = [os.path.join(scene_dir, 'scene.nc')]

    return make.Rule(action, inputs, outputs)

# ---------------------------------------------------------------------------
@functools.lru_cache()
def r_prepare_scene(scene_dir, defaults=dict(), **kwargs):
    def action(tdir):
        prepare_scene(scene_dir, defaults=defaults, **kwargs)
    return make.Rule(action, [], [os.path.join(scene_dir, 'scene.nc')])

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
				<TagString>{froot}__PRA_raw_{freq}{_Forest}.tif</TagString>
			</ImageLayer>
		</SceneDefinition>
	</ImportDefinition>
</ImportDefinitions>
"""
def import_xml_str(scene_args, freq, forest):
    """Generates text for the ...import....xml file
    freq: 'frequent' | 'extreme'
    """

    args = {
#        'froot': os.path.join(scene_args['scene_dir'], 'eCog', scene_args['name']),
        'froot': '/mnt/eCog/{}'.format(scene_args['name']),    # Runs on mounted drive inside Docker container
        'scene_name': scene_args['name'],
        'freq': freq,
        '_Forest' : '_Forest' if forest else '_NoForest',
        'layer': '{layer}',    # Leave this for eCognition
    }
    return import_xml_tpl.format(**args)
# ---------------------------------------------------------------------------
def _prepare_data_outputs(scene_dir, scene_args):


    # Basic stuff
    outputs = [
        os.path.join(scene_dir, 'stats_kernel.txt'),
        os.path.join(scene_dir, '{}_DataPrep_InputParameters.csv'.format(scene_args['name'])),
    ]

    # xml import files
    for freq in ('frequent', 'extreme'):
        for forest in ((True,False) if scene_args['forest_file'] else (False,)):
            _Forest = '_Forest' if forest else '_NoForest'
            import_xml = os.path.join(scene_dir, 'eCog', f'PRA_import_{freq}{_Forest}.xml')
            outputs.append(import_xml)

    # GHK Files
    for return_period in scene_args['return_periods']:
        for forest in (False, True):
            _For = '_For' if forest else '_NoFor'
            ofname = os.path.join(scene_dir, 'eCog',
                f'GHK_{return_period:d}y{_For}.dcp')
            outputs.append(ofname)


    return outputs

def prepare_data(scene_dir):
    """Called from prepare_scene.py; RUNS ON WINDOWS HOST WITH ArcGIS"""
    outputs = list()
    scene_args = params.load(scene_dir)

    temporaries = [
        os.path.join(scene_dir, 'base_data'),
        os.path.join(scene_dir, 'temp_model_frequent'),
        os.path.join(scene_dir, 'temp_model_extreme')]

    # Delete all output files/folders
    # (otherwise ArcGIS complains)
    _outputs = _prepare_data_outputs(scene_dir, scene_args)
    for dir in (temporaries + _outputs):
        shutil.rmtree(dir, ignore_errors=True)

    # Assemble script args
    script_args = {'Workspace': scene_dir}
    for script_arg, scene_arg in [
        ('inDEM', 'dem_file'),
        ('resampCellSize', 'resolution'),
        ('Slope_lowerlimit_frequent', 'slope_lowerlimit_frequent'),
        ('Slope_lowerlimit_extreme', 'slope_lowerlimit_extreme'),
        ('Slope_upperlimit', 'slope_upperlimit'),
        ('Curv_upperlimit', 'curve_upperlimit'),
        ('Rugged_neighborhood', 'rugged_neighborhood'),
        ('Rugged_upperlimit', 'rugged_upperlimit')]:
        script_args[script_arg] = str(scene_args[scene_arg])

    # Optional arguments...
    for script_arg, scene_arg in [
        ('inForest', 'forest_file'),
        ('inPerimeter', 'clip_file')]:
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
    if '[' in scene_args['coordinate_system']:    # It's a PRJ string
        # Generate the coordinate_system file in ESRI .prj format
        crs_prj = os.path.join(scene_dir, 'crs.prj')
        with open(crs_prj, 'w') as out:
            out.write(scene_args['coordinate_system'])
        print('crs_prj = ',crs_prj)

        script_args['outCoordSystem'] = arcgisutil.Lambda('arcpy', 'SpatialReference', crs_prj)
    else:
        # It's an ESRI code
        script_args['outCoordSystem'] = arcgisutil.Lambda('arcpy', 'SpatialReference', scene_args['coordinate_system'])

    # Run the core script
    data_prep_PRA_py = os.path.join(harnutil.HARNESS, 'akramms', 'sh', 'arcgis', 'data_prep_PRA.py')
    arcgisutil.run_script(data_prep_PRA_py, script_args, cwd=scene_dir, dry_run=False)

    # Clean up temporary files from ArcGIS step
    for dir in temporaries:
        shutil.rmtree(dir, ignore_errors=True)

    # Copy DEM to eCog folder
    ecog_dir = os.path.join(scene_dir, 'eCog')
    os.makedirs(ecog_dir, exist_ok=True)
    dem_tif = os.path.join(ecog_dir, '{}_DEM.tif'.format(scene_args['name']))
    outputs.append(dem_tif)
    shutil.copy(scene_args['dem_file'], os.path.join(ecog_dir, '{}_DEM.tif'.format(scene_args['name'])))

    # Write import...xml files 
    for freq in ('frequent', 'extreme'):
        for forest in ((True,False) if scene_args['forest_file'] else (False,)):
            _Forest = '_Forest' if forest else '_NoForest'
            import_xml = os.path.join(ecog_dir, f'PRA_import_{freq}{_Forest}.xml')
            outputs.append(import_xml)
            with open(import_xml, 'w') as out:
                out.write(import_xml_str(scene_args, freq, forest))

    # Generate the required process trees
    for return_period in scene_args['return_periods']:

        # They are sorted into two categories: _frequent and _extreme
        return_period_category = 'frequent' if return_period < 100 else 'extreme'
        odir = os.path.join(scene_dir, f'PRA_{return_period_category}')
        os.makedirs(odir, exist_ok=True)

        for forest in (False, True):
            _For = '_For' if forest else '_NoFor'
            ofname = os.path.join(scene_dir, 'eCog',
                f'GHK_{return_period:d}y{_For}.dcp')
            outputs.append(ofname)
            with open(ofname, 'w') as out:
                # scene_dir=/mnt because this runs in a docker container
                out.write(process_tree.get(scene_args, '/mnt', return_period, forest))
#                out.write(process_tree.get(scene_dir, return_period, forest))

    # Declare our output files so they may be copied back to Linux
    harnutil.print_outputs(outputs)

# ---------------------------------------------------------------------------

def rule(scene_dir):
    """Runs the data_prep_PRA.py script on a scene
    hostname:
        Remote host to run the command on
    HARNESS_REMOTE:
        Location of ~/git (parent of akramms/ repo)
    scene_dir:
        Scene dir on THIS host."""

    scene_args = params.load(scene_dir)

    # inputs = [os.path.join(scene_dir, 'scene.nc')]
    inputs = []
    outputs = _prepare_data_outputs(scene_dir, scene_args)

    def action(tdir):
        scene_dir_rel = config.roots.relpath(scene_dir)

        # Assemble list of files to copy to remote Windows host
        inputs = [os.path.join(scene_dir, 'scene.nc')]

        # Input files: dem and forest
        for param in params.ALL.values():
            if param.type != 'input_file':
                continue
            if param.name not in scene_args:
                continue

            inputs.append(scene_args[param.name])

        # Transfer over input files
        cmd = ['sh', config.roots_w.syspath('{HARNESS}/akramms/sh/prepare_scene.sh', bash=True),
            config.roots_w.syspath(scene_dir_rel, bash=True)]
        harnutil.run_remote(inputs, cmd, tdir)

    return make.Rule(action, inputs, outputs)
