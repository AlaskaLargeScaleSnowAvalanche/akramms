import os,collections,sys
import numpy as np
import schema
from uafgi.util import schemautil,shputil,gisutil
from akramms import config, experiment, stages
from akramms import r_prepare,r_domain_builder
from akramms import d_ifsar, d_usgs_landcover

# Top-level experimental design for Alaska

# Root directory of studies in this experiment
name = __name__.rsplit('.', 1)[-1]    # e_alaska
dir = os.path.join(config.roots['PRJ'], name)

# Map coordinate system we use
wkt = 'PROJCS["NAD83 / Alaska Albers",GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Albers"],PARAMETER["standard_parallel_1",55],PARAMETER["standard_parallel_2",65],PARAMETER["latitude_of_origin",50],PARAMETER["central_meridian",-154],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["Meter",1]]'
resolution = 10    # 10m resolution for our DEM
snow_density = 300    # [kg m-3], used for mosaic

# ----------------------------------------------
# Function extracts a DEM and writes it to a file
dem_img = d_ifsar.r_vrt('DTM').outputs[0]    # Master DEM image file
def extract_dem(poly, ofname, **kwargs):
    return d_ifsar.extract('DTM', poly, ofname, resolution=resolution, **kwargs)

landcover_img = d_usgs_landcover.landcover_img # Master landcover image file
extract_landcover = d_usgs_landcover.extract    # Function to extract from master landcover
# ----------------------------------------------

# Define the domains within all of Alaska, each with an (idom, jdom) coordinate.
domain_size = (30000., 30000.)   # 30km^2
domain_margin = (8000,8000)    # 8km margin
gridD = gisutil.DomainGrid(
    wkt,
    config.roots.syspath('{DATA}/fischer/AlaskaBounds.shp'),
    domain_size, domain_margin)

# One of the "Juneau" domains has coordinates (ix,iy) = (113,26)

# /vzip/ is a GDAL thing for shapefiles contained in .zip

experiment_region_zip = config.roots.syspath('{DATA}/wolken/SE_AK_Domain_Land.zip')
experiment_region_shp = f'/vsizip/{experiment_region_zip}/SE_AK_Domain_Land.shp'

# Scehma of top-level tuple describing a single trial.
combo_schema = schema.Schema({
    'snow_dataset': schemautil.EnumField(
        {'ccsm', 'cfsr', 'gfdl'},
        "Available WRF Dataset to use in obtaining snow data"),
    'year0': schemautil.Int(
        "First year of snow dataset to accumulate over"),
    'year1': schemautil.Int(
        "Last year of snow dataset to accumulate over"),
    'downscale_algo': schemautil.EnumField(
        {'select', 'lapse'},
        "Algorithm to use downscaling snow from WRF to RAMMS grid"),
    'forest': schemautil.EnumField(
        {'For', 'NoFor'},
        "Use the forest file or not"),
    'return_period': schemautil.ParsedEnumField(
        int, repr,
        {10, 30, 100, 300},
        "Return period of avalanche hazard to consider."),
    'idom': schemautil.Int(
        "x index of the Alaska sub-domain to run"),
    'jdom': schemautil.Int(
        "y index of the Alaska sub-domain to run"),
})

combo_keys = list(combo_schema.schema.keys())
Combo = collections.namedtuple('Combo', combo_keys)

# -------------------------------------------------------------
def combo_to_scene_subdir(combo, type='x'):
    trial_name = f'{name}-{combo.snow_dataset}-{combo.year0}-{combo.year1}-{combo.downscale_algo}-{combo.forest}-{combo.return_period}'
    scene_name = f'{type}-{combo.idom:03d}-{combo.jdom:03d}'    # Underscores would confuse things

    return os.path.join(trial_name, scene_name)

# -------------------------------------------------------------
def add_dem(makefile, idom, jdom, sanity_check=True):
    exp_mod = sys.modules[__name__]    # This module
    return makefile.add(r_experiment.r_ifsar(exp_mod, idom, jdom, sanity_check=sanity_check)).outputs[0]

def add_combo(makefile, combo):
    """Adds rules needed to set up (and also run) a trial. (step1)"""

    exp_mod = sys.modules[__name__]    # This module

    # Set of domains that cover our experiment region
    # (This file is the same for ALL trials)
#    makefile.add(r_experiment.r_active_domains(exp_mod))

    # DTM and Forest (landcover==42)
    dem_tif = add_dem(makefile, combo.idom, combo.jdom)  #makefile.add(r_experiment.r_ifsar(exp_mod, combo.idom, combo.jdom, resolution=resolution)).outputs[0]
    dem_filled_file,sinks_file,neighbor1_file = makefile.add(r_domain_builder.neighbor1_rule(
        dem_tif, os.path.split(dem_tif)[0], fill_sinks=True)).outputs

    # Forest File
    if combo.forest == 'For':
        landcover_tif = makefile.add(r_experiment.r_landcover(
            exp_mod, combo.idom, combo.jdom)).outputs[0]
        forest_tif = makefile.add(r_experiment.r_forest(
            exp_mod, combo.idom, combo.jdom)).outputs[0]

    # Snow downscaling
    if combo.downscale_algo == 'lapse':
        makefile.add(r_experiment.r_dfcA(exp_mod))
    sx3I_tif = makefile.add(r_experiment.r_snow(
        exp_mod, combo.snow_dataset, combo.downscale_algo,
        combo.year0, combo.year1, combo.idom, combo.jdom)).outputs[0]

    # Convert Combo to a scene_dir / scen_args
    scene_dir = os.path.join(exp_mod.dir, combo_to_scene_subdir(combo))

    # Determine which parts of the domain are interior (vs margin)
    # Coordinates are in (i,j) space relative to full-margin domain's origin
    domain_margin = gridD.poly(combo.idom, combo.jdom, margin=True)
    domain = gridD.poly(combo.idom, combo.jdom, margin=False)

    kwargs = dict(
        resolution=resolution,
        # Bounds of interior, in the (i,j) space of the full-with-margin domain
        # https://stackoverflow.com/questions/20474549/extract-points-coordinates-from-a-polygon-in-shapely
        domain = list(np.asarray(domain.exterior.coords).reshape(-1)),
        domain_margin = list(np.asarray(domain_margin.exterior.coords).reshape(-1)),

        return_periods=(combo.return_period,),
        forests=((1 if combo.forest=='For' else 0),),
        dem_file=dem_tif,
        snow_file=sx3I_tif)
    if combo.forest:
        kwargs['forest_file'] = forest_tif

    # Print out what we've got!
    print('------ Rules to Prepare Scene:')
    print(f'   scene_dir: {scene_dir}')
    for k,v in kwargs.items():
        print(f'   {k}: {v}')
    rule = r_prepare.r_prepare_scene(
        scene_dir, defaults='alaska', **kwargs)
    makefile.add(rule)

#    stages.add_stage0_rules(makefile, scene_dir)
def add_experiment(makefile, combos):
#    add_dem(makefile, 0, 0, sanity_check=False)    # Get the origin scene
#    add_dem(makefile, 1, 0, sanity_check=False)    # Get the origin scene
#    add_dem(makefile, 55, 0, sanity_check=False)    # Get the origin scene
#    add_dem(makefile, 113, 0, sanity_check=False)    # Get the origin scene
    for combo in combos:
        print(f'----- Adding Combo: {combo}')
        add_combo(makefile, combo)


# -------------------------------------------------------------
# Different subsets of combos to try when running the experiment
def full():
    """Yields the combos for the FULL experiment.
    REQUIRES: domains.shp and domains_margin.shp
    """

    domains_margin_shp = os.path.join(dir, 'domains_margin.shp')
    domains_df = shputil.read_df(domains_margin_shp).setindex(['ix', 'iy'])
    domains_ij = [(row.i,row.j) for row in domains_df.iterrows()]

    # Generate set of trials
    snow = 'ccsm'
    downscale_algo = 'lapse'
    for year0,year1 in [(1981, 1990),]:
        for forest in ('For', 'NoFor'):
            for return_period in [10,30,100,300]:
                for idom,jdom in domains_ij:
                    yield Combo(snow, year0, year1, downscale_algo, forest, return_period, idom, jdom)

# -----------------------------------------------------------------
def juneau():
    # Just one combo for now
    yield Combo('ccsm', 1981, 1990, 'lapse', 'For', 30, 113, 45)    # A Juneau-close box
#    yield Combo('ccsm', 1981, 1990, 'lapse', 'For', 30, 113, 44)    # North of Juneau
