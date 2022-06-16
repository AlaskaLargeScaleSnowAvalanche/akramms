from dggs.util import paramutil

# List of all parameters involved in an overall run.
# Param = collections.namedtuple('Param', ('name', 'units', 'type', 'required', 'description'))
ALL = paramutil.parse([
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

# Not included in main parameters because it doesn't affect the value
# of the computation.
SCENE_DIR = paramutil.Param('scene_dir', None, 'path', False,
    'Top-level directory of this scene / project')

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

def load(scene_dir):
    """Reads the scene """
    ret = paramutil.load_nc(os.path.join(scene_dir, 'scene.nc'))
    ret['scene_dir'] = scene_dir
    return ret
