import functools
import os
import numpy as np
import pathlib
from akramms.util import paramutil


# List of all parameters involved in an overall run.
# Param = collections.namedtuple('Param', ('name', 'units', 'type', 'required', 'description'))
ALL = paramutil.parse([
    # Basic parameters of the scene
    ('name', None, 'str', False,
        """Root name of scene; to use for filenames, plotting, etc"""),
#    ('basename', None, 'str', False,
#        """part of name shared with other similar scenes."""),
    ('dem_file', None, 'input_file', True,
        """Name of DEM file to use (GeoTIFF)"""),
    ('forest_file', None, 'input_file', False,
        """Name of forest cover file to use (GeoTIFF)"""),
    ('snow_file', None, 'input_file', True,
        """Downscaled snow field on the local grid."""),
    ('clip_file', None, 'input_file', False,
        """Clip domain to this region (Shapefile)"""),
#    ('interior_bounds', None, 'list', True,
#        """i/j coordinates denoting the interior of the region (vs margin): (i0, i1, j0, j1)"""),

    ('domain', None, 'list', False,
        """[x0,y0, x1,y1, ...] Coordinates of the domain, without margin"""),
    ('domain_margin', None, 'list', False,
        """[x0,y0, x1,y1, ...] Coordinates of the domain, with margin"""),




    # Parameters for preprocessing and eCognition
    ('resolution', 'm', 'int', True,
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
    ('forests', '', 'list', True,
        """List of boolean forest params to compute (out of [1,0])"""),
    ('min_pra_elevation', 'm', 'float', True,
        """Minimum elevation of potential release areas (PRAs) to export from eCognition."""),
    ('stats_kernel', None, 'array', True,
        """2D kernel used for statistics on DEM in ArcGIS data prep"""),

    ])

## Not included in main parameters because it doesn't affect the value
## of the computation.
#SCENE_DIR = paramutil.Param('scene_dir', None, 'path', False,
#    'Top-level directory of this scene / project')

DEFAULTS = {
    'schweitz': dict(
    resolution=5,
    slope_lowerlimit_frequent=30,
    slope_lowerlimit_extreme=28,
    slope_upperlimit=55,
    curve_upperlimit=5.5,
    rugged_neighborhood=7,
    rugged_upperlimit=3.5,
    coordinate_system='CH1903+_LV95',
    return_periods=[10,30,100,300],
    forests=[1,0],
    min_pra_elevation=600.,
    stats_kernel=np.array([
        [0.625, 0.625, 0.625, 0.625, 0.625],
        [0.625, 1.5, 1.5, 1.5, 0.625],
        [0.625, 1.5, 3, 1.5, 0.625],
        [0.625, 1.5, 1.5, 1.5, 0.625],
        [0.625, 0.625, 0.625, 0.625, 0.625]]),
    ),

    'alaska': dict(
    resolution=5,
    slope_lowerlimit_frequent=30,
    slope_lowerlimit_extreme=28,
    slope_upperlimit=55,
    curve_upperlimit=5.5,
    rugged_neighborhood=7,
    rugged_upperlimit=3.5,

    # https://gis.stackexchange.com/questions/18651/do-arcgis-spatialreference-object-factory-codes-correspond-with-epsg-numbers
    # If an Esri well-known ID is below 32767, it corresponds to the
    # EPSG ID. WKIDs that are 32767 or above are Esri-defined. Either
    # the object isn't in the EPSG Geodetic Parameter Dataset yet, or
    # it probably won't be added. If an object is later added to the
    # EPSG Dataset, Esri will update the WKID to match the EPSG one,
    # but the previous value will still work.

    # EPSG 26908
    # coordinate_system='PROJCS["NAD_1983_UTM_Zone_8N",GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",-135],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["Meter",1]]',
    # EPSG 3338
    coordinate_system='PROJCS["NAD83 / Alaska Albers",GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",SPHEROID["GRS_1980",6378137,298.257222101]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Albers"],PARAMETER["standard_parallel_1",55],PARAMETER["standard_parallel_2",65],PARAMETER["latitude_of_origin",50],PARAMETER["central_meridian",-154],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["Meter",1]]',
    return_periods=[10,30,100,300],
    forests=[1,0],
    min_pra_elevation=0.,        # Or maybe 150m (as per Gabe) 2022-07-19: Yves, I think we imposed a lower limit of 150 m to remove unrealistic PRA mapping in warm/wet maritime areas.
    stats_kernel=np.array([
        [0.625, 0.625, 0.625, 0.625, 0.625],
        [0.625, 1.5, 1.5, 1.5, 0.625],
        [0.625, 1.5, 3, 1.5, 0.625],
        [0.625, 1.5, 1.5, 1.5, 0.625],
        [0.625, 0.625, 0.625, 0.625, 0.625]]),

)}

@functools.lru_cache()
def load(scene_dir):
    """Reads the scene """
    ret = paramutil.load_nc(os.path.join(scene_dir, 'scene.nc'))
    ret['scene_dir'] = pathlib.Path(scene_dir)
    return ret
