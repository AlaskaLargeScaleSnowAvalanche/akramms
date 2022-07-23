import scipy.spatial
from osgeo import gdal
from dggs.avalanche import params
from uafgi.util import shputil,gdalutil,wrfutil
import os,sys
import subprocess
import json
import dggs.data
import pyproj
import netCDF4
import numpy as np
import gridfill




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

        # Write a GeoTIFF file of our results
        wrfutil.write_geotiff(self.geo_info, self.data, 'x.tif')

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
def _pra_post_iter0(scene_args):
    for return_period in scene_args['return_periods']:
        for For in ('For', 'NoFor'):
            yield (return_period, For)

def _pra_post_iter1():
    return iter(('tiny', 'small', 'medium', 'large'))



def pra_post_rule(scene_dir, sx3_file, geo_file):
    """
    scene_dir:
        Uses params: name ("site"), resample_cell_size ("res")

    return_period:
        Return period we are calculating for.
        Must be included in scene_args['return_periods']
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
    for return_period,For in _post_cat_iter0(scene_args):
        inputs.append(os.path.join(
            scene_dir,
            f'PRA_{process_tree.return_period_category(rp)}',
            f'PRA_{return_period}y_{For}.shp'))

        for catname in _pra_post_iter1():
            cat_letter = catname[0].upper()
            outputs.append(os.path.join(scene_dir,
                f'{name}_{For}_{resolution}m_{return_period}{cat_letter}_rel.shp'))

    # Add one-off input files
    inputs += [os.path.join(scene_dir, 'scene.nc'), pra_input, sx3_file, geo_file]

    def action(tdir):

        # Create lookup for snow depth in WRF output file
        snow_lookup = WrfLookup(scene_args['coordinate_system'], sx3_file, 'sx3', geo_file)

        degree = np.pi / 180.
        name = scene_args['name']
        resolution = scene_args['resolution']

        # Use same loop as when constructing inputs / outputs
        inputsi = iter(inputs)
        outputsi = iter(outputs)
        for return_period,For in _post_cat_iter0(scene_args):
            input = next(inputsi)

            # Load the polygons
            df = shputil.read_df(pra_info, shape='pra').df
            df['sx3'] = df['pra'].map(snow_lookup.value_at_centroid)    # Raw snow depth

            # --- Elevation correction
            snowdepth_correction = (df['Mean_DEM'] - scene_args['reference_elevation']) *.01 * scene_args['gradient_snowdepth']
            sx3_corrected = (df['sx3'] + snowdepth_correction)
            # TODO: Why are we multiplying by cos(28) = .883?
            df['d0star'] = sx3_corrected * np.cos(28. * degree)

            # --- Slope angle correction (slopecorr)
            df['slopecorr'] =  0.291 / np.sin(df['Mean_slope']*degree) \
                             - 0.202 * np.cos(df['Mean_slope']*degree)

            # Wind load interpolation between 100 (0) and 200 (full wind load) elevation
            # Change max wind load dependent on scenario!!
            df['Wind'] = np.clip((df['Mean_DEM'] - 1000.) * .0001, 0., 0.1)

            # Calculate final d0 (d0_{return_period})
            d0_vname = f'd0_{return_period}'
            df[d0_vname] = ((df['d0star'] + df['Wind']) * df['slopecorr'])

            # Calculate volume (VOL_returnperiod)
            VOL_vname = f'VOL_{return_period}'
            # df[VOL_vname] = df['area_m2'] / np.cos(df['Mean_slope']*degree) * df[d0_vname]
            df[VOL_vname] = (df['area_m2'] * df[d0_vname]) / np.cos(df['Mean_slope']*degree)


            for catname in _pra_post_iter1():
                output = next(outputsi)

                for catname,low,high in zip(catnames, _post_cat_bounds[:-1], _post_cat_bounds[1:]):
                    df_cat = df[df['area_m2'].between(low, high, inclusive='both')]
                    cat_output = os.path.join(scene_dir, f'{name}_{For}_{resolution}m_{return_period}{cat_letter}_rel.shp')
#                    shputil.write_df(df_cat, cat_output)

                    print('------ writing ')
                    print(df.columns)
                    print([(c,c.dtype) for c in df.columns])
                
    return action

def main():
#    with netCDF4.Dataset('x.nc', 'a') as nc:
#        sx3 = nc.variables['sx3'][:]
#        for i in range(sx3.shape[0]):
#            sx3[i,:] = i
#        for j in range(sx3.shape[1]):
#            sx3[:,j] += j
#        nc.variables['sx3'][:] = sx3


    scene_dir = os.path.join(dggs.data.HARNESS, 'prj', 'juneau1')
    sx3_file = '/Users/eafischer2/av/data/lader/sx3/geo_southeast.nc'
    geo_file = '/Users/eafischer2/av/data/lader/sx3/gfdl_sx3_1986.nc'
    pra_post_rule(scene_dir, sx3_file, geo_file)(None)

main()



        # data_fname = os.path.join(dggs.data.HARNESS, 'data', 'lader', 'sx3', 'gfdl_sx3_1986.nc')
        # geo_fname = os.path.join(dggs.data.HARNESS, 'data', 'lader', 'sx3', 'geo_southeast.nc')
