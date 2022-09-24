import scipy.spatial
from osgeo import gdal
from dggs.avalanche import params,process_tree
from uafgi.util import shputil,gdalutil,wrfutil,make
import os,sys
import subprocess
import json
import dggs.data
import pyproj
import netCDF4
import numpy as np
import gridfill


# From the gridfill docs...
#def gridfill.fill(grids, xdim, ydim, eps, relax=.6, itermax=100, initzonal=False,
#         cyclic=False, verbose=False):
#    """
#    Fill missing values in grids with values derived by solving
#    Poisson's equation using a relaxation scheme.
#    **Arguments:**
#    *grid*
#        A masked array with missing values to fill.
#    *xdim*, *ydim*
#        The numbers of the dimensions in *grid* that represent the
#        x-coordinate and y-coordinate respectively.
#    *eps*
#        Tolerance for determining the solution complete.
#    **Keyword arguments:**
#    *relax*
#        Relaxation constant. Usually 0.45 <= *relax* <= 0.6. Defaults to
#        0.6.
#    *itermax*
#        Maximum number of iterations of the relaxation scheme. Defaults
#        to 100 iterations.
#    *initzonal*
#        If *False* missing values will be initialized to zero, if *True*
#        missing values will be initialized to the zonal mean. Defaults
#        to *False*.
#    *cyclic*
#        Set to *False* if the x-coordinate of the grid is not cyclic,
#        set to *True* if it is cyclic. Defaults to *False*.
#    *verbose*
#        If *True* information about algorithm performance will be
#        printed to stdout, if *False* nothing is printed. Defaults to
#        *False*.
#    """

class WrfLookup:
    def __init__(self, scene_wkt, data_fname, vname, geo_fname):

        # Determine WRF coordinates
        self.geo_info = wrfutil.wrf_info(geo_fname)
        print('geotransform = {}'.format(self.geo_info.geotransform))
        print('geoinv = {}'.format(self.geo_info.geoinv))
        print('extents = {}'.format(self.geo_info.extents))
        print('nx,ny = ({}, {})'.format(self.geo_info.nx, self.geo_info.ny))

        # Obtain transfomer from scene coordinates to WRF Snow File
        scene_crs = pyproj.CRS.from_string(scene_wkt)
        wrf_crs = pyproj.CRS.from_string(self.geo_info.wkt)
        # There will be "error" in this because the spheroids do not match.
        # WRF uses perfect sphere; whereas scene typically uses WGS84 or similar
        self.scene2wrf = pyproj.Transformer.from_crs(scene_crs, wrf_crs, always_xy=True)

        # Load the data file
        with netCDF4.Dataset(data_fname) as nc:
            # Masked array
            masked_data = nc.variables[vname][:,:]    # sx3(j=south_north,i=west_east)
        self.data,converged = gridfill.fill(masked_data, 1, 0, .1)#, itermax=10000)

#        # Write a GeoTIFF file of our results
#        wrfutil.write_geotiff(self.geo_info, self.data, 'x.tif')

    def value_at_centroid(self, poly):
        centroid = poly.centroid    # In scene coordinates
        x_scene, y_scene = (centroid.x, centroid.y)
        x_wrf,y_wrf = self.scene2wrf.transform(x_scene, y_scene)    # --> WRF coordinates
        ir,jr = self.geo_info.to_ij(x_wrf, y_wrf)    # --> (j,i) index into data
        i = round(ir)
        j = round(jr)
        return self.data[j,i]

    def to_ij(self, poly):
        centroid = poly.centroid    # In scene coordinates
        x_scene, y_scene = (centroid.x, centroid.y)
        x_wrf,y_wrf = self.scene2wrf.transform(x_scene, y_scene)    # --> WRF coordinates
        i,j = self.geo_info.to_ij(x_wrf, y_wrf)    # --> (j,i) index into data
        return (round(i), round(j))

# ---------------------------------------------------------------------------------
_post_cat_bounds = (0.,5000.,25000.,60000.,1e10)    # Dummy value at end

def _pra_post_iter1():
    return iter(('tiny', 'small', 'medium', 'large'))



def release_rule(scene_dir, return_period, forest, ramms_dir, require_all=True):
    """
    scene_dir:
        Uses params: name ("site"), resample_cell_size ("res")

    return_period:
        Return period we are calculating for.
        Must be included in scene_args['return_periods']
    ramms_dir:
        Top-level directory for RAMMS run that's being created.
        Typically equal to:
           ramms.ramms_dir(scene_dir, scene_args['name'], return_period, forest)

    forest: bool  (formerly "Naming")
        Whether we are doing with / without forest
    sx3_file:
        Name of WRF file containing the sx3 snow depth variable
    geo_file:
        Name of WRF file containing eometry information for sx3_file
    """

    scene_args = params.load(scene_dir)

    # Main input and output files: THESE MUST BE FIRST
    inputs = list()
    outputs = list()
    resolution = scene_args['resolution']
    name = scene_args['name']
    For = 'For' if forest else 'NoFor'

    inputs.append(os.path.join(
        scene_dir,
        f'PRA_{process_tree.return_period_category(return_period)}',
        f'PRA_{return_period}y_{For}.shp'))

#    ramms_dir = ramms.ramms_dir(scene_dir, scene_args['name'], return_period, forest)
    for catname in _pra_post_iter1():
        cat_letter = catname[0].upper()
        outputs.append(os.path.join(ramms_dir, 'RELEASE',
            f'{name}_{For}_{resolution}m_{return_period}{cat_letter}_rel.shp'))

    # Add one-off input files
#    inputs += [os.path.join(scene_dir, 'scene.nc'), scene_args['snowdepth_file'], scene_args['snowdepth_geo']]
    inputs += [scene_args['snowdepth_file'], scene_args['snowdepth_geo']]

    def action(tdir):

        # Create lookup for snow depth in WRF output file
        snow_lookup = WrfLookup(scene_args['coordinate_system'], scene_args['snowdepth_file'], 'sx3', scene_args['snowdepth_geo'])
        snow_info = snow_lookup.geo_info

        degree = np.pi / 180.
        name = scene_args['name']
        resolution = scene_args['resolution']

        # Load the polygons
        print('======== Reading {}'.format(inputs[0]))
        df = shputil.read_df(inputs[0], shape='pra')
        df = df.rename(columns={'fid': 'Id'})    # RAMMS etc. want it named "Id"
        df['sx3'] = df['pra'].map(snow_lookup.value_at_centroid)    # Raw snow depth

        # --- Elevation correction Reduces amount of snow with
        # steepness.  All traditional.  We measure 3-day snow depth
        # increase in flat field at a station.  But PRAs are very
        # different.  So they're putting it from flat to 28 degrees.
        # Then they add the lapse rate.  Then they do a second slope
        # angle correction for steeper terrain.  In the end, add
        # windblown snow parameter.  This is how every PRA gets its
        # own d0 dependent on slope angle and elevation.

        # GW: In SE Alaska, steep terrain can hold several meters of
        # snow in something almost 70 degrees from time to time.

        snowdepth_correction = (df['Mean_DEM'] - scene_args['reference_elevation']) *.01 * scene_args['gradient_snowdepth']
        sx3_corrected = (df['sx3'] + snowdepth_correction)
        # TODO: Why are we multiplying by cos(28) = .883?

        # Very old rule developed 30-40 years ago: the steeper the
        # slope, the less snow that can accumulate.  Very
        # traditional from SLF.  DO NOT use for Alaska.

        # (BUT... the steeper a release point is, the less snow it
        # has, MIGHT be useful for Alaska.  TODO: Discuss with
        # Gabe).  If snow is very moist...???
        if False:
            df['d0star'] = sx3_corrected * np.cos(28. * degree)
        else:
            df['d0star'] = sx3_corrected

        # --- Slope angle correction (slopecorr)
        # TODO: Discuss with Gabe.  Do we want to apply slope angle correction?
        # If yes, we can make it much simpler than what we have here.
        df['slopecorr'] =  0.291 / np.sin(df['Mean_Slope']*degree) \
                         - 0.202 * np.cos(df['Mean_Slope']*degree)

        # Wind load interpolation between 100 (0) and 200 (full wind load) elevation
        # Change max wind load dependent on scenario!!
        # TODO: Discuss with Gabe, how we do the wind load.
        df['Wind'] = np.clip((df['Mean_DEM'] - 1000.) * .0001, 0., 0.1)

        # Calculate final d0 (d0_{return_period})
        d0_vname = f'd0_{return_period}'
        df[d0_vname] = ((df['d0star'] + df['Wind']) * df['slopecorr'])

        # Calculate volume (VOL_returnperiod)
        VOL_vname = f'VOL_{return_period}'
        # df[VOL_vname] = df['area_m2'] / np.cos(df['Mean_Slope']*degree) * df[d0_vname]
        df[VOL_vname] = (df['area_m2'] * df[d0_vname]) / np.cos(df['Mean_Slope']*degree)

        # Create directories needed for output files
        dirs = set(os.path.split(x)[0] for x in outputs)
        for dir in dirs:
            print(f'Creating directory: {dir}')
            os.makedirs(dir, exist_ok=True)

        # Split into segments and save
        outputsi = iter(outputs)
        for catname,low,high in zip(_pra_post_iter1(), _post_cat_bounds[:-1], _post_cat_bounds[1:]):
            print('Category: {}, [{}, {})'.format(catname, low, high))
            output = next(outputsi)

            df_cat = df[df['area_m2'].between(low, high, inclusive='both')]  # SHOULD be inclusive='left'

            shputil.write_df(df_cat, 'pra', 'Polygon', output, wkt=scene_args['coordinate_system'])
                
    return make.Rule(action, inputs, outputs)

