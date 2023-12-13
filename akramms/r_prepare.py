import subprocess,functools,pickle
import os,pathlib,shutil
import netCDF4
import numpy as np
from akramms import config,process_tree
from akramms.util import paramutil,harnutil,arcgisutil
from uafgi.util import make,gdalutil
from akramms import params

# TODO: Tar up
# tar cvfz scene3.tar.gz $(find scene3 -name '*' -and -type f | grep -v eCog)

__all__ = ('prepare_scene_rule', 'data_prep_PRA_rule', 'prepare_data')

# -----------------------------------------------------------------------
# ---------------------------------------------------------------------------
def prepare_scene_rule(xscene_dir, defaults=dict(), **kwargs):

    """Sets up a new scene by creating a directory with all
    parameters required for processing.
    Called from experiment/ak.py

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
        scene_dir = os.path.abspath(xscene_dir)
        os.makedirs(scene_dir, exist_ok=True)

        # Assemble the scene args, using default params if provided
        if isinstance(defaults, str):    # Lookup pre-loaded defaults
            xdefaults = params.DEFAULTS[defaults]
        else:
            xdefaults = defaults

        scene_args = {**xdefaults, **kwargs}
        scene_args = paramutil.validate_args(scene_args, params=params.ALL)

#        scene_args = paramutil.validate_args({**xdefaults, **kwargs}, params=params.ALL)

        # Get the scene name as the leaf of the scene_dir
        if 'name' not in scene_args:
            scene_args['name'] = os.path.split(scene_dir)[1]

        # Store the overall scene parameters
        paramutil.dump_nc(os.path.join(scene_dir, 'scene.nc'), scene_args, params=params.ALL)
        cmd = ['ncdump', os.path.join(scene_dir, 'scene.nc')]
        with open(os.path.join(scene_dir, 'scene.cdl'), 'w') as out:
            subprocess.run(cmd, stdout=out)

    inputs = [kwargs['dem_file'], kwargs['snow_file']]
    if 'forest_file' in kwargs:
        inputs.append(kwargs['forest_file'])
    outputs = [os.path.join(xscene_dir, 'scene.nc')]

    return make.Rule(action, inputs, outputs)

# ---------------------------------------------------------------------------
#@functools.lru_cache()
#def r_prepare_scene(scene_dir, defaults=dict(), **kwargs):
#    def action(tdir):
#        prepare_scene(scene_dir, defaults=defaults, **kwargs)
#    return make.Rule(action, [], [os.path.join(scene_dir, 'scene.nc')])

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

    return outputs

def prepare_data(scene_dir):
    """Called from prepare_scene.py; RUNS ON WINDOWS HOST WITH ArcGIS"""
    outputs = list()
    scene_args = params.load(scene_dir)

    # Delete all output files/folders
    # (otherwise ArcGIS complains)
    temporaries = [
        os.path.join(scene_dir, 'base_data'),
        os.path.join(scene_dir, 'temp_model_frequent'),
        os.path.join(scene_dir, 'temp_model_extreme'),
        os.path.join(scene_dir, 'in_mem'),
        os.path.join(scene_dir, 'mem'),
        os.path.join(scene_dir, 'eCog'),
    ]

    _outputs = _prepare_data_outputs(scene_dir, scene_args)
    for dir in (temporaries + _outputs):
        shutil.rmtree(dir, ignore_errors=True)

    # Assemble script args
    script_args = {'Workspace': str(scene_dir)}
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

    # Run the core script (we've already passed the rq barrier by now)
    data_prep_PRA_py = os.path.join(harnutil.HARNESS, 'akramms', 'sh', 'arcgis', 'data_prep_PRA.py')
    arcgisutil.run_script(data_prep_PRA_py, script_args, cwd=scene_dir, dry_run=False)


    # Declare our output files so they may be copied back to Linux
    harnutil.print_outputs(outputs)

# ---------------------------------------------------------------------------

def data_prep_PRA1_rule(scene_dir):
    """Runs the data_prep_PRA.py script on a scene
    TO RERUN:
        Delete arcgis_stage0.txt

    hostname:
        Remote host to run the command on
    HARNESS_REMOTE:
        Location of ~/git (parent of akramms/ repo)
    scene_dir:
        Scene dir on THIS host."""

    scene_args = params.load(scene_dir)

    # Assemble list of files to copy to remote Windows host
    inputs = [os.path.join(scene_dir, 'scene.nc')]

    # Input files: dem and forest
    for param in params.ALL.values():
        if (param.type == 'input_file') and (param.name in scene_args):
            inputs.append(scene_args[param.name])

    outputs = _prepare_data_outputs(scene_dir, scene_args) + [os.path.join(scene_dir, 'data_prep_PRA1.pik')]

    def action(tdir):
        from akramms.util import rqutil

        # Remote command to run
        scene_dir_rel = config.roots.relpath(scene_dir)
        cmd = ['sh', config.roots_w.syspath('{HARNESS}/akramms/sh/prepare_scene.sh', bash=True, as_str=True),
            scene_dir_rel]

        # Run it
#        harnutil.run_queued('arcgis',
#            harnutil.run_remote, inputs, cmd, tdir)
        with rqutil.blocking_lock('arcgis'):
            harnutil.run_remote(inputs, cmd, tdir)

#        # Make it clear / obvious we have finished
#        with open(os.path.join(scene_dir, 'data_prep_PRA1.pik'), 'w') as out:
#            out.write('Successfully finished running ArcGIS script data_prep_PRA.py')
        
    return make.Rule(action, inputs, outputs)
# -----------------------------------------------------------------------------
# ==============================================================================
# Part 2: Python and GDAL

def mask_and_copy(itif, mask_out, otif, type=None):
    if type is None:
        from osgeo import gdal
        type = gdal.GDT_Float64
    print(f'Masking and writing to: {otif}')
    ival = gdalutil.read_raster(itif)
    ival.data[mask_out] = ival.nodata
    gdalutil.write_raster(otif, *ival, type=type)
        
# -----------------------------------------------------------------------------
def _data_prep_PRA2(vv, Slope_lowerlimit, name_scenario):

    print("executing Scenario_" + name_scenario + "...")

    #-------------------------------------------------------------------------------
    tdir = os.path.join(vv.Workspace, f"temp_model_{name_scenario}")
    os.makedirs(tdir, exist_ok=True)
    def TDIR(leaf):
        return os.path.join(tdir, leaf)

    def ECOG(leaf):
        return os.path.join(vv.Workspace, 'eCog', leaf)
    #-------------------------------------------------------------------------------

    print("creating binary layers...")

    # create Slope binary 
    #     SlopeBinary = Con((arcpy.sa.Raster(Slope_tif) <
    #         float(Slope_lowerlimit)) | (arcpy.sa.Raster(Slope_tif) >
    #         float(Slope_upperlimit)), 0, 1)
    Slope_r = gdalutil.read_raster(vv.Slope_tif)
    Slope_in = np.logical_and(
        Slope_r.data >= Slope_lowerlimit,
        Slope_r.data <= vv.Slope_upperlimit)

    # create Curvature binary
    #     CurvBinary = Con((arcpy.sa.Raster(Curv_plan) <
    #         (-1*float(Curv_upperlimit))) |
    #         (arcpy.sa.Raster(Curv_plan) > float(Curv_upperlimit)), 0, 1)
    Curv_r = gdalutil.read_raster(vv.Curv_plan)
    Curv_in = np.logical_and(
        Curv_r.data >= -vv.Curv_upperlimit,
        Curv_r.data <=  vv.Curv_upperlimit)

    # create Ruggedness binary
    # RuggednessBinary = Con((Ruggedness > float(Rugged_upperlimit)), 0, 1)
    Ruggedness_r = gdalutil.read_raster(vv.Ruggedness_tif)
    Ruggedness_in = (Ruggedness_r.data <= vv.Rugged_upperlimit)

    # Combine all binaries
    print("combining binary layers...")
    SlopeCurvRuggedness_in = np.logical_and(np.logical_and(Slope_in, Curv_in), Ruggedness_in)
    #-------------------------------------------------------------------------------
    if vv.inForest is not None:

        # Forest may not be the same geometry / resolution as DEM
        # Forest is boolean dataset 1/0
        iForest_r = gdalutil.read_raster(vv.inForest)
        oForest_data = gdalutil.regrid(
            iForest_r.data, iForest_r.grid, iForest_r.nodata,
            Slope_r.grid, iForest_r.nodata)
        iForest_r = None    # Release memory
        Forest_in = (oForest_data != 0)
        oForest_data = None    # Release memory

        # https://stackoverflow.com/questions/10454316/how-to-project-and-resample-a-grid-to-match-another-grid-with-gdal-python
#        iForest_ds = gdal.Open(str(vv.inFOrest))
#        oForest_ds = gdalutil.clone_geometry('MEM', '', Slope_r.grad_info, 1, gdal.GDT_Byte)
#gdal.ReprojectImage(src, dst, src_proj, match_proj, gdalconst.GRA_Bilinear)


        # Boolean Overlay: Slope AND Curvature AND Ruggedness AND Forest
#        print('inForest ', vv.inForest)
#        Forest_r = gdalutil.read_raster(vv.inForest)
#        Forest_in = (Forest_r.data != 0)
        SlopeCurvRuggednessForest_in = np.logical_and(SlopeCurvRuggedness_in, Forest_in)

    #-------------------------------------------------------------------------------
    print("writing out PRA_raw...")

    # Boolean Overlay Raster to PRA_raw Raster

    # NoForest
    PRA_raw_NoForest = ECOG(f"{Name}__PRA_raw_{name_scenario}_NoForest.tif")
    val = np.zeros(SlopeCurvRuggedness_in.shape)#, dtype='i')
    val[SlopeCurvRuggedness_in] = 200
    val[mask_out] = DEM_r.nodata
    gdalutil.write_raster(PRA_raw_NoForest, DEM.grid, val, DEM.nodata)

    # Forest
    if inForest != "":
        PRA_raw_NoForest = ECOG(f"{Name}__PRA_raw_{name_scenario}_NoForest.tif")
        val = np.zeros(SlopeCurvRuggednessForest_in.shape)#, dtype='i')
        val[SlopeCurvRuggedness_in] = 200
        val[mask_out] = DEM_r.nodata
        gdalutil.write_raster(PRA_raw_NoForest, DEM.grid, val, DEM.nodata)


# -----------------------------------------------------------------
def _w2l(val):
    if val == '':
        return None

    val = config.roots_w.relpath(val)
    val = config.roots_l.syspath(val)
    return val

def _float(val):
    if val == '':
        return None
    return float(val)

# Keys from ArcGIS script that represent paths
_arcgis_vars = dict()
for vn in (
    'Workspace',
    'DEM', 'inPerimeter', 'Perimeter_Envelope_Buffer',
    'DEM_eCog', 'Slope_tif', 'Slope_eCog', 'Aspect_sectors_N0_eCog',
    'Aspect_sectors_Nmax_eCog', 'Curv_profile_eCog_temp',
    'Curv_profile_eCog', 'Curv_plan_eCog_temp', 'Curv_plan_eCog',
    'Hillshade_eCog', 'Curv_plan', 'Ruggedness_tif', 'inForest',
    ):
    _arcgis_vars[vn] = _w2l

for vn in (
    'Slope_lowerlimit_frequent', 'Slope_lowerlimit_extreme',
    'Slope_upperlimit', 'Curv_upperlimit', 'Rugged_upperlimit'):
    _arcgis_vars[vn] = _float


class LVars:
    ""

    "Convenient conversion from Windows to Linux paths"""

    def __init__(self, wvars):
        self.wvars = wvars
    def __getattr__(self, vname):
        val = self.wvars[vname]
        if vname in _arcgis_vars:
            return _arcgis_vars[vname](val)
        return val

# ---------------------------------------------------------------------        
def prepare_data2(scene_dir):
    """Called from prepare_scene.py; RUNS LOCALLY ON LINUX"""

    scene_args = params.load(scene_dir)

    # Retrieve filenames used in data_prep_PRA.py ArcGIS script
    with open(os.path.join(scene_dir, 'data_prep_PRA1.pik'), 'rb') as fin:
        vv = LVars(pickle.load(fin))
    Workspace = vv.Workspace

    # -------------------------------------------------------------
    def MEM(leaf):
        # Formerly: return f"memory/{leaf}"
        return os.path.join(Workspace, 'mem', f'{leaf}.tif')
    # -------------------------------------------------------------

    # Clip eCog files to the same extent as the DEM or perimeter polygon

    print("clipping eCog files to the same extent")

    # Make a mask based on DEM extent
    DEM_r = gdalutil.read_raster(vv.DEM)
    mask_out = (DEM_r.data == DEM_r.nodata)

    # Mask out areas beyond the perimeter
    if vv.inPerimeter is not None:
        # Mask based on the perimeter polygon
        ds = ogr.GetDriverByName('ESRI Shapefile').Open(vv.Perimeter_Envelope_Buffer)
        try:
            # This will be 1 inside perimeter polygon, 0 outside
            in_perimeter = rasterize.rasterize_polygons(ds, DEM_r.grid)
        finally:
            ds = None

        # Mask out anything additional outside the perimeter.
        mask_out[np.logical_not(in_perimeter)] = True

    # Apply mask to files
    mask_and_copy(vv.DEM, mask_out, vv.DEM_eCog)
    mask_and_copy(vv.Slope_tif, mask_out, vv.Slope_eCog)
    print('AA ', MEM("Aspect_sectors_N0_eCog"))
    print('BB ', vv.Aspect_sectors_N0_eCog)
    mask_and_copy(MEM("Aspect_sectors_N0_eCog"), mask_out, vv.Aspect_sectors_N0_eCog)
    mask_and_copy(MEM("Aspect_sectors_Nmax_eCog"), mask_out, vv.Aspect_sectors_Nmax_eCog)
    mask_and_copy(vv.Curv_profile_eCog_temp, mask_out, vv.Curv_profile_eCog)
    mask_and_copy(vv.Curv_plan_eCog_temp, mask_out, vv.Curv_plan_eCog)
    mask_and_copy(MEM("Hillshade_eCog"), mask_out, vv.Hillshade_eCog)

    if vv.Slope_lowerlimit_frequent is not None:
        _data_prep_PRA2(vv, vv.Slope_lowerlimit_frequent, "frequent")

    if vv.Slope_lowerlimit_extreme is not None:
        _data_prep_PRA2(vv, vv.Slope_lowerlimit_extreme, "extreme")


# ----------------------------------------------------------------------------
def data_prep_PRA2_rule(scene_dir, inputs):
    """
    inputs:
        Outputs from data_prep_PRA1_rule
    outputs:
    """
    outputs = [os.path.join(scene_dir, 'data_prep_PRA2.txt')]

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

    def action(tdir):

        prepare_data2(scene_dir)

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


        # Copy DEM to eCog folder
        ecog_dir = os.path.join(scene_dir, 'eCog')
        os.makedirs(ecog_dir, exist_ok=True)
        dem_tif = os.path.join(ecog_dir, '{}_DEM.tif'.format(scene_args['name']))
        outputs.append(dem_tif)
        shutil.copy(scene_args['dem_file'], os.path.join(ecog_dir, '{}_DEM.tif'.format(scene_args['name'])))
#        # Clean up temporary files from ArcGIS step
#        for dir in temporaries:
#            shutil.rmtree(dir, ignore_errors=True)


        # Make it clear / obvious we have finished
        with open(os.path.join(scene_dir, 'data_prep_PRA2.txt'), 'w') as out:
            out.write('Successfully finished running ArcGIS script data_prep_PRA.py')

    return make.Rule(action, inputs, outputs)
# -----------------------------------------------------------------------------
