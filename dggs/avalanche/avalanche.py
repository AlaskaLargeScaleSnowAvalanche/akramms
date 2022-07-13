import subprocess
import os,pathlib,shutil
import netCDF4
import numpy as np
from dggs.util import paramutil,harnutil,arcgisutil
from uafgi.util import make
from dggs.avalanche import process_tree,params

# TODO: Tar up
# tar cvfz scene3.tar.gz $(find scene3 -name '*' -and -type f | grep -v eCog)



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
#        'froot': os.path.join(scene_args['scene_dir'], 'eCog', scene_args['name']),
        'froot': '/mnt/eCog/{}'.format(scene_args['name']),    # Runs on mounted drive inside Docker container
        'scene_name': scene_args['name'],
        'freq': freq,
        'layer': '{layer}',    # Leave this for eCognition
    }
    return import_xml_tpl.format(**args)
# ---------------------------------------------------------------------------
def _prepare_data_outputs(scene_dir, scene_args):
    outputs = [
        os.path.join(scene_dir, 'eCog'),
        os.path.join(scene_dir, 'stats_kernel.txt'),
        os.path.join(scene_dir, '{}_DataPrep_InputParameters.csv'.format(scene_args['name']))]
    return outputs

def prepare_data(scene_dir):
    """Called from prepare_scene.py; RUNS ON WINDOWS HOST WITH ArcGIS"""

    scene_args = params.load(scene_dir)

    temporaries = [
        os.path.join(scene_dir, 'base_data'),
        os.path.join(scene_dir, 'temp_model_frequent'),
        os.path.join(scene_dir, 'temp_model_extreme')]

    # Delete all output files/folders
    # (otherwise ArcGIS complains)
    outputs = _prepare_data_outputs(scene_dir, scene_args)
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

    # Generate the coordinate_system file in ESRI .prj format
    crs_prj = os.path.join(scene_dir, 'crs.prj')
    with open(crs_prj, 'w') as out:
        out.write(scene_args['coordinate_system_prj'])

    # Obtain ArcGIS SpatialReference object (script needs as a script variable)
#    script_args['outCoordSystem'] = arcgisutil.Lambda('arcpy', 'SpatialReference', scene_args['coordinate_system'])
    print('crs_prj = ',crs_prj)
    script_args['outCoordSystem'] = arcgisutil.Lambda('arcpy', 'SpatialReference', crs_prj)
    data_prep_PRA_py = os.path.join(harnutil.HARNESS, 'akramms', 'sh', 'arcgis', 'data_prep_PRA.py')
    arcgisutil.run_script(data_prep_PRA_py, script_args, cwd=scene_dir, dry_run=False)

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
            with open(ofname, 'w') as out:
                # scene_dir=/mnt because this runs in a docker container
                out.write(process_tree.get('/mnt', return_period, forest))
#                out.write(process_tree.get(scene_dir, return_period, forest))

# ---------------------------------------------------------------------------

def prepare_data_rule(hostname, scene_dir, HARNESS_REMOTE):
    """Runs the data_prep_PRA.py script on a scene
    hostname:
        Remote host to run the command on
    HARNESS_REMOTE:
        Location of ~/git (parent of akramms/ repo)
    scene_dir:
        Scene dir on THIS host."""

    scene_args = params.load(scene_dir)

    inputs = [os.path.join(scene_dir, 'scene.nc')]
    outputs = _prepare_data_outputs(scene_dir, scene_args)

    def action(tdir):
        remote_scene_dir = harnutil.remote_name(scene_dir, HARNESS_REMOTE, bash=True)
        remote_scene_host_dir = '{}:{}'.format(hostname, remote_scene_dir)

        # Copy scene.nc to remote host
        cmd = ['ssh', hostname, 'mkdir', '-p', remote_scene_dir]
        print(cmd)
        subprocess.run(cmd, check=True)

        cmd = ['rsync', os.path.join(scene_dir, 'scene.nc'), remote_scene_host_dir+'/']
        print(cmd)
        subprocess.run(cmd, check=True)

        # Copy input files: dem and forest
        for param in params.ALL.values():
            if param.type != 'input_file':
                continue
            if param.name not in scene_args:
                continue

            cmd = ['ssh', hostname, 'mkdir', '-p',
                harnutil.bash_name(harnutil.remote_name(os.path.split(scene_args[param.name])[0], HARNESS_REMOTE))]
            print(cmd)
            subprocess.run(cmd, check=True)

            cmd = ['rsync', scene_args[param.name],
                '{}:{}'.format(hostname, harnutil.remote_name(scene_args[param.name], HARNESS_REMOTE, bash=True))]
            print(cmd)
            subprocess.run(cmd, check=True)

        # Run script on remote host
        cmd = ['ssh', hostname, 'python', harnutil.bash_name(f'{HARNESS_REMOTE}\\akramms\\sh\\prepare_scene.py'), remote_scene_dir]
        print(cmd)
        subprocess.run(cmd, check=True)

        # TODO: Copy outputs back to local host
        cmd = ['rsync', '-avz', remote_scene_host_dir+'/', scene_dir]
        print(cmd)
        subprocess.run(cmd, check=True)


    return make.Rule(action, inputs, outputs)

# ---------------------------------------------------------------------------
_dia_cmd_engine_usage = """
Usage: 
- analyze image file:  
    DIACmdEngine image=path1 [image=pathN..] [thematic=pathN] ruleset=path [options]
- analyze image imported using connector:   
    DIACmdEngine image-dir=path import-connector=name [import-connector-file=path] [image=extra_image_pathN] [thematic=extra_thematic_pathN] ruleset=path [options]
- analyze existing project (.dpr):  
    DIACmdEngine dpr=path1 ruleset=path [options]
- analyze image imported using scene file list (multiple scenes within single run):   
    DIACmdEngine image-dir=path scene-xml=path ruleset=path [options]
- resave ruleset to force usage of latest algorithm versions:   
    DIACmdEngine --update-ruleset input_ruleset_path output_ruleset_path

- where:
    image=path                 - path to raster or point cloud data file (.tif, .asc, ...). 
    thematic=path              - path to thematic data file (.shp, gdb, ...). 
    ruleset=path               - path to rule set file (.dcp). 
    import-dir=path            - root directory for image/thematic data files. 
    import-connector=name      - name of the predefined import connector or custom import connector (.xml). 
    import-connector-file=path - path to .xml file containing customized import connector. 
    dpr=path                   - path to .dpr file to be used as analysis input. 


- options:
    param:nameN=valueN     - parameter to the rule set, where nameN is name of scene variable and 
                         valueN is the value of the scene variable. There can be arbitrary amount of params.
    array-param:nameN=value1,value2,..,valueN - array parameter to the rule set, where nameN is name of rule set array and 
                         valueN is the comma-separated value list, for example: array-param:myArray=0,90,180,270. There can be arbitrary amount of array-params.
    --map path1=path2        - local drive - network path mapping
    --output-dir=path      - output diretory for export files
    --license-token=json   - additional license information in json format
    --save-dpr[-min][=path/to/project.dpr] - save project file (without rule set if '--save-dpr-min') 
                         If explicit path to .dpr specified, 
                         it will be used instead default path ({:Workspc.OutputRoot}\dpr\{:Project.Name}.v{:Project.Ver}.dpr) 
    --log-file=path        - log file path (if not specified, default log file is written based on path in eCognition.cfg)
    --pause                - pause application after done
"""

def run_ecog_rule(scene_dir, return_period, forest):

    scene_args = params.load(scene_dir)
    inputs = _prepare_data_outputs(scene_dir, scene_args)

    # Systematically generate list of output files
    rp = return_period
    rpcat = process_tree.return_period_category(rp)
    _For = '_For' if forest else '_NoFor'
    outputs = list()
    for ext in ('.dbf', '.prj', '.shp', '.shx'):
        outputs.append(os.path.join(scene_dir, f'PRA_{rpcat}', f'PRA_{rp}y{_For}{ext}'))

#    for rp in process_tree.return_periods:    # [10,30,100,300]
#        rpcat = process_tree.return_period_category[rp]
#        for _For in ('_For', '_NoFor'):
#            for ext in ('.dbf', '.prj', '.shp', '.shx'):
#                outputs.append(os.path.join(scene_dir, f'PRA_{rpcat}', f'PRA_{rp}y{_For}{ext}'))

    def action(tdir):
        # Base Docke rcommand
        cmd = ['docker', 'run', '--rm', '--network', 'host']

        # eCognition licensing
        cmd += ['-e', 'LM_LICENSE_FILE=27000@10.10.129.211']

        # Mount paths inside eCognition container
        cmd += ['-v', f'{scene_dir}:/mnt']

        # Docker container and command to run
        cmd += ['ecognition/linux_cle:10.2.0', './DIACmdEngine']

        # Arguments to DIACmdEnginer (see _dia_cmd_engine_usage above)
        # ----------

        # Import Connect to images in <scene_dir>/eCog
        cmd += ['image-dir=/mnt/eCog', f'import-connector=PRA_import_{rpcat}', f'import-connector-file=/mnt/eCog/PRA_import_{rpcat}.xml']

        # Add the appropriate ruleset
        cmd += [f'ruleset=/mnt/eCog/GHK_{return_period:d}y{_For}.dcp']

        # Place for output
        odir = os.path.join(scene_dir, f'PRA_{rpcat}')
        os.makedirs(odir, exist_ok=True)
        cmd += [f'--output-dir=/mnt/PRA_{rpcat}']

        # See if there's anything to see in a log file
        # unfortunately not much.
        cmd += [f'--log-file=/mnt/eCog/GHK_{return_period:d}y{_For}.log']

        print(' '.join(cmd))
        subprocess.run(cmd, check=True)

    return make.Rule(action, inputs, outputs)
