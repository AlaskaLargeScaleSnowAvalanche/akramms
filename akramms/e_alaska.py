import os,collections
import schema
from uafgi.util import schemautil,shputil
from akramms import config, experiment

# Top-level experimental design for Alaska

# Root directory of studies in this experiment
name = 'ak'
dir = os.path.join(config.roots['PRJ'], name)

# Map coordinate system we use
wkt = 'PROJCS["NAD83 / Alaska Albers",GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Albers"],PARAMETER["standard_parallel_1",55],PARAMETER["standard_parallel_2",65],PARAMETER["latitude_of_origin",50],PARAMETER["central_meridian",-154],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["Meter",1]]',

# Define the domains within all of Alaska, each with an (idom, jdom) coordinate.
domain_size = (30000., 30000.)   # 25km^2
domain_margin = (8000,8000)    # 8km margin
domains = experiment.DomainGrid(
    wkt,
    config.roots.syspath('{DATA}/fischer/AlaskaBounds.shp'),
    
    domain_size, domain_margin)

# /vzip/ is a GDAL thing for shapefiles contained in .zip
experiment_region_shp = '/vzip/' + config.roots.syspath('{DATA}/wolken/SE_AK_Domain_Land.zip') + '/SE_AK_Domain_Land.shp',

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
def add_combo(makefile, combo):
    """Adds rules needed to set up (and also run) a trial."""

    exp_mod = sys.modules[__name__]    # This module

    # Set of domains that cover our experiment region
    # (This file is the same for ALL trials)
#    makefile.add(experiment.r_active_domains(exp_mod))

    # DTM and Forest (landcover==42)
    dem_tif = makefile.add(experiment.r_ifsar(exp_mod, combo.idom, combo.jdom))
    if combo.forest == 'For':
        landcover_tif = makefile.add(experiment.r_landcover(
            exp_mod, combo.idom, combo.jdom))
        forest_tif = makefile.add(experiment.r_forest(
            exp_mod, combo.idom, combo.jdom))

    # Snow downscaling
    if combo.downscale_algo == 'lapse':
        makefile.add(experiment.r_dfcA(exp_mod, idom, jdom))
    sx3I_tif = makefile.add(experiment.r_snow(
        exp_mod, combo.snow_dataset, combo.downscale_algo,
        combo.year0, combo.year1, combo.idom, combo.jdom)).outputs[0]

    # Convert Combo to a scene_dir / scen_args
    scene_name = f'{name}-{combo.idom:03d}-{combo.jdom:03d}'    # Underscores would confuse things
    scene_dir = os.path.join(exp_mod.dir, scene_name)
    kwargs = dict(
        return_periods=[combo.return_period],
        forests=[1 if combo.forest=='For' else 0],
        dem_file=dem_tif,
        snowdepth_file=sx3I_tif)
    if combo.forest:
        kwargs['forest_file'] = forest_tif
    makefile.add(r_prepare.r_prepare_scene(
        scene_dir, defaults='alaska', **kwargs))


    # TODO: call stages.add_stage0_rules() and stages.add_stage1_rules()
    # Those will need to be changed, due to changes in kwargs for r_prepare_scene().


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

