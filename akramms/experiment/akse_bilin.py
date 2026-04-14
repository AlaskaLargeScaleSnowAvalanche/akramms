import os,collections,sys,itertools,pathlib
import numpy as np
import schema
from uafgi.util import schemautil,shputil,gisutil,ulam
from akramms import downscale_snow
from akramms import config, r_experiment
from akramms import r_prepare,r_domain_builder,file_info
from akramms import d_ifsar, d_usgs_landcover

# Top-level experimental design for Alaska

# Root directory of studies in this experiment
name = __name__.rsplit('.', 1)[-1]    # e_alaska
root_dir = config.roots['PRJ'] / name
root_xdir = config.roots_lx['PRJ'] / name
dir = root_dir / 'db'
publish_dir = root_dir / 'publish'

# Map coordinate system we use
epsg = 3338    # Same as WKT; see https://espg.io
wkt = 'PROJCS["NAD83 / Alaska Albers",GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Albers"],PARAMETER["standard_parallel_1",55],PARAMETER["standard_parallel_2",65],PARAMETER["latitude_of_origin",50],PARAMETER["central_meridian",-154],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["Meter",1]]'
resolution = 10    # 10m resolution for our DEM
pra_resolution = 10    # Use 5m DEM when computing PRAs
snow_density = 300    # [kg m-3], used for mosaic

#forest_landcover_types = [42,43]    # NCLD Land Cover Classifications *Evergreen* and *Mixed Deciduous*
forest_landcover_types = [42]    # NCLD Land Cover Classifications *Evergreen* only


# ----------------------------------------------
# Named regions we typically query: (x0, y0, x1, y1)
extents = {
    'southeast': [0,0,1,1],    # Dummy for now
}
# ----------------------------------------------
# Function extracts a DEM and writes it to a file
dem_img = d_ifsar.r_vrt('DTM').outputs[0]    # Master DEM image file
def extract_dem(poly, ofname, **kwargs):
    # Hard-code to resolution for akse
    return d_ifsar.extract('DTM', poly, ofname, resample_algo='bilinear', **kwargs)

landcover_img = d_usgs_landcover.landcover_img # Master landcover image file
extract_landcover = d_usgs_landcover.extract    # Function to extract from master landcover
# ----------------------------------------------

# Define the domains within all of Alaska, each with an (idom, jdom) coordinate.
# NOTE: Domain size and margin MUST be an even multiple of the
#       gridcell spacing of the DEM (10m) and Forest (30m) files.
domain_size = (30000., 30000.)   # 30km^2
domain_margin = (7980,7980)    # 7980m margin
gridD = gisutil.DomainGrid(
    wkt,
    config.roots.syspath('{DATA}/fischer/AlaskaBounds.shp'),
    domain_size, domain_margin)

# One of the "Juneau" domains has coordinates (ix,iy) = (113,26)

# /vzip/ is a GDAL thing for shapefiles contained in .zip

experiment_region_zip = config.roots.syspath('{DATA}/wolken/SE_AK_Domain_Land.zip')
experiment_region_shp = f'/vsizip/{experiment_region_zip}/SE_AK_Domain_Land.shp'

# Schema of top-level tuple describing a single trial.
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
    'forest': schemautil.EnumField(    # REQUIRED key for stdmosaic; see mosaic.py
        {'', 'For', 'NoFor'},    # Blank string in EnumField allows for wildcard forest in mosaic plotting
        "Use the forest file or not"),
    'return_period': schemautil.ParsedEnumField(
        int, repr,
        {10, 30, 100, 300},
        "Return period of avalanche hazard to consider."),
    'idom': schemautil.NullableInt(
        "x index of the Alaska sub-domain to run"),
    'jdom': schemautil.NullableInt(
        "y index of the Alaska sub-domain to run"),
})

# SQL types for the files in the combo
combo_sql_types = {
    'snow_dataset': 'varchar(10)',
    'year0': 'int4',
    'year1': 'int4',
    'downscale_algo': 'varchar(10)',
    'forest': 'varchar(5)',
    'return_period': 'int4',
    'idom': 'int4',
    'jdom': 'int4',
}


combo_keys = list(combo_schema.schema.keys())
_Combo = collections.namedtuple('Combo', combo_keys)
class Combo(_Combo):
    def base_str(self):
        return f'{self.snow_dataset}-{self.year0:04d}-{self.year1:04d}-{self.downscale_algo}-{self.forest}-{self.return_period}'
    def __repr__(self):
        return f'{self.base_str()}-{self.idom:03d}-{self.jdom:03d}'

def snowfile(snow_dataset, year0, year1, downscale_algo, idom, jdom):
    """Creates the name of a snow file.
    idom,jdom:
        may be '*' to allow for wildcards and globbing."""

    sidom = idom if isinstance(idom,str) else f'{idom:03d}'
    sjdom = jdom if isinstance(jdom,str) else f'{jdom:03d}'
    ofname = os.path.join(dir, 'snow',
        f'{name}_{snow_dataset}_{year0}_{year1}_{downscale_algo}_{sidom}_{sjdom}.tif')
    return pathlib.Path(ofname)


def combo_to_snowfile_args(combo):
    return (
        combo.snow_dataset,
        combo.year0, combo.year1, combo.downscale_algo,
        combo.idom, combo.jdom)

# -------------------------------------------------------------
_root_dir = {
    'x': (root_xdir, 'x'),
    'arc': (root_dir, 'arc'),
    'xs': (root_dir, 'x')}

def combo_to_scenedir(combo, scenetype='x'):
    root_dir, stype = _root_dir[scenetype]

    trial_name = f'{name}-{combo.snow_dataset}-{combo.year0}-{combo.year1}-{combo.downscale_algo}-{combo.forest}-{combo.return_period}'
    scene_name = f'{stype}-{combo.idom:03d}-{combo.jdom:03d}'    # Underscores would confuse things

    ret = root_dir / 'db' / trial_name / scene_name
#    print(f'combo_to_scene_dir({scenetype}) = {ret}')
    return ret

def combo_to_snowfile_args(combo):
    return (dir, name,
        combo.snow_dataset,
        combo.year0, combo.year1, combo.downscale_algo,
        combo.idom, combo.jdom)

_pra_sizes = {'NoFor': ['L','M'], 'For': ['S','T']}
def pra_sizes(combo):
    """Determimes the PRA sizes we will compute in this experiment, for a given Combo."""
    return _pra_sizes[combo.forest]

# Avalanches that just wouldn't compute; so we ignore them when looking at job status
def ignore_ids():
    return [
        ( Combo('ccsm', 1981, 2010, 'lapse', 'NoFor', 300, 123, 50), 203 ),
    ]


# -------------------------------------------------------------
def add_dem(makefile, idom, jdom, sanity_check=True, folder='dem', resolution=resolution):
    exp_mod = sys.modules[__name__]    # This module
    return makefile.add(r_experiment.r_ifsar(exp_mod, idom, jdom, sanity_check=sanity_check, folder=folder, resolution=resolution)).outputs[0]

def add_combo(makefile, combo):
    """Adds rules needed to set up (and also run) a trial. (step1)"""

    exp_mod = sys.modules[__name__]    # This module

    # Set of domains that cover our experiment region
    # (This file is the same for ALL trials)
# This is done in `akramms step1` so no need to do it here again.
#    makefile.add(r_experiment.r_active_domains(exp_mod))

    # DTM and Forest (landcover==42)
#    pra_dem_tif = add_dem(makefile, combo.idom, combo.jdom, folder='pra_dem', resolution=pra_resolution)
    dem_tif = add_dem(makefile, combo.idom, combo.jdom, resolution=resolution)  #makefile.add(r_experiment.r_ifsar(exp_mod, combo.idom, combo.jdom, resolution=resolution)).outputs[0]
    pra_dem_tif = dem_tif
    assert pra_resolution == resolution    # This must be true for our shortcut here to work

#    dem_filled_file,sinks_file,neighbor1_file = makefile.add(r_domain_builder.neighbor1_rule(
#        dem_tif, os.path.split(dem_tif)[0], fill_sinks=True)).outputs

    # Forest File
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
    scene_dir = os.path.join(exp_mod.dir, combo_to_scenedir(combo))

    # Determine which parts of the domain are interior (vs margin)
    # Coordinates are in (i,j) space relative to full-margin domain's origin
    domain_margin = gridD.poly(combo.idom, combo.jdom, margin=True)
    domain = gridD.poly(combo.idom, combo.jdom, margin=False)

    kwargs = dict(
        resolution=resolution,
        pra_resolution=pra_resolution,
        # Bounds of interior, in the (i,j) space of the full-with-margin domain
        # https://stackoverflow.com/questions/20474549/extract-points-coordinates-from-a-polygon-in-shapely
        domain = list(np.asarray(domain.exterior.coords).reshape(-1)),
        domain_margin = list(np.asarray(domain_margin.exterior.coords).reshape(-1)),

        return_periods=(combo.return_period,),
        forests=((1 if combo.forest=='For' else 0),),
        pra_dem_file=pra_dem_tif,
        dem_file=dem_tif,
        snow_file=sx3I_tif)
    kwargs['forest_file'] = forest_tif

    # Print out what we've got!
    print('------ Rules to Prepare Scene:')
    print(f'   scene_dir: {scene_dir}')
    for k,v in kwargs.items():
        print(f'   {k}: {v}')
    rule,scene_args = r_prepare.prepare_scene_rule(
        scene_dir, defaults='alaska', **kwargs)
    makefile.add(rule)
    print('   --- prepare inputs')
    for inp in rule.inputs:
        print(f'   {inp}')
    print('   --- prepare outputs')
    for out in rule.outputs:
        print(f'   {out}')

    # Return files produced by this experiment
    return file_info.ComboInfo(scene_dir, dem_tif, landcover_tif, forest_tif, sx3I_tif), scene_args

##    stages.add_stage0_rules(makefile, scene_dir)
#def add_experiment(makefile, combos):
##    add_dem(makefile, 0, 0, sanity_check=False)    # Get the origin scene
##    add_dem(makefile, 1, 0, sanity_check=False)    # Get the origin scene
##    add_dem(makefile, 55, 0, sanity_check=False)    # Get the origin scene
##    add_dem(makefile, 113, 0, sanity_check=False)    # Get the origin scene
#    for combo in combos:
#        print(f'----- Adding Combo: {combo}')
#        add_combo(makefile, combo)


def mosaic_filter(df):
    """Filters low-elevation avalanches based on advanced criteria.
    df:
        Result of extent.read_annotated_extent()
    Returs: df_include, df_exclude
        Splits df into avalanches to include, and avalanches to exclude.
    """
    # Separate
#    df = df[df['Mean_DEM'] < 300]
    keep = np.logical_or(
        df['Mean_DEM'] >= 300,
        np.logical_and(
            (((df.rel_n41 + df.rel_n43) / df.rel_n) < 0.3),
            (((df.ext_n42 + df.ext_n43) / df.ext_n) < 0.3)))
    df_include = df[keep]
    df_exclude = df[~keep]

    return df_include, df_exclude
# -------------------------------------------------------------
# Degenerate tiles we do NOT want to run (blacklist)
exclude_tiles = {
    (112,51),
    (123, 56),
    (102,44),
    (96,43),
    (90,45),
    # These tiles processed OK but had no avalanches
    (88,42), (92,43), }

def all_domains():
    domains_margin_shp = os.path.join(dir, f'{name}_domains_margin.shp')
    domains_df = shputil.read_df_noshapes(domains_margin_shp)
    domains_df = domains_df.set_index(['idom', 'jdom'])
    domains_ij = domains_df.index.tolist()
    domains_ij = [ij for ij in domains_ij if ij not in exclude_tiles]
#    domains_ij = [(row.idom, row.jdom) for row in domains_df.itertuples(index=False)]
    return domains_ij


def spiral_domains(x0, y0):
    """Use Ulam Spiral out from a central domain tile"""

#    yield (110,43)
#    return


    dij = set(all_domains())

    # High prioirty domains
    # (Code usese x/y and i/j interchangibly here)
    high_priority = [
        (110, 42), (109,42),    # Haines and West: Avalanche of 2024-2-2

        (91,42), (91,41), (91, 40),  # Cordova
        (90, 42), (90, 41), (90,40),
        (89, 39),        # Valdez
#        (90, 40), (91, 40),     # Cordova
#        (90, 41), (91, 41), 
#        (90, 42), (91, 42), 
    ]
    for xy in high_priority:
        if xy in dij:
            yield xy
            dij.remove(xy)

    for n in itertools.count(start=0, step=1):
        dxy = ulam.n_to_xy(n)
        xy = (x0 + dxy[0], y0 + dxy[1])
        if xy in dij:
            yield xy
            dij.remove(xy)
            if len(dij) == 0:
                return

# Different subsets of combos to try when running the experiment
def full():
    """Yields the combos for the FULL experiment.
    REQUIRES: domains.shp and domains_margin.shp
    """



    # Generate set of trials
    snow = 'ccsm'
    downscale_algo = 'lapse'
    for idom,jdom in spiral_domains(113, 45):    # Spiral around Juneau
        for year0,year1 in [(1981, 2010),(2031,2060)]:        # 30-year climatologies
#            for return_period in [10,30,100,300]:
            for return_period in [30,300]:
                for forest in ('NoFor','For'):
                    yield Combo(snow, year0, year1, downscale_algo, forest, return_period, idom, jdom)

def urban():
    for year0,year1 in [(1981,2010), (2031,2060)]:
        for return_period in [30,300]:
            for idom,jdom in [        (90, 41), (91, 41), (90, 42), (91, 42),    # Cordova
                (89, 39),        # Valdez
                (110, 42), (109,42),    # Haines and West: Avalanche of 2024-2-2
                (113, 45)]:    # Juneau
                for forest in ('NoFor','For'):
                    yield Combo('ccsm', year0, year1, 'lapse', forest, return_period, idom, jdom)
# -----------------------------------------------------------------
def juneau():
    for year0,year1 in [(1981,2010)]:
        for return_period in [30,300]:
            for idom,jdom in [(113,45), (113,44)]:
                for forest in ('NoFor','For'):
                    yield Combo('ccsm', year0, year1, 'lapse', forest, return_period, idom, jdom)





#    for year0,year1 in [(1981,1990), (2051,2060)]:
#    for year0,year1 in [(2051,2060)]:

#        # Just one combo for now
#        yield Combo('ccsm', year0, year1, 'lapse', 'For', 30, 113, 45)    # A Juneau-close box
#        yield Combo('ccsm', year0, year1, 'lapse', 'For', 30, 113, 44)    # North of Juneau
#        yield Combo('ccsm', year0, year1, 'lapse', 'For', 30, 111, 42)    # Tile borders with Canada

def simple():
    yield Combo('ccsm', 1981, 1990, 'lapse', 'For', 30, 113, 45)    # A Juneau-close box

def elizabeth():
    yield Combo('ccsm', 1981, 1990, 'lapse', 'For', 30, 113, 47)    # A Juneau-close box

def edge():
    # A single edge cell
    for return_period in [30,300]:
        for forest in ('NoFor','For'):
            yield Combo('ccsm', 1981, 2010, 'lapse', forest, return_period, 111, 42)   # Tile borders  Canada
