import scipy.spatial
from osgeo import gdal
from akramms import params,process_tree
from akramms.util import rammsutil
from uafgi.util import shputil,gdalutil,wrfutil,make,cfutil,ioutil
import os,sys
import subprocess
import json
from akramms import config
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
    def __init__(self, scene_wkt, data_fname, vname, geo_fname, units=None):
        """
        units: str
            Units to convert to
        """

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
            ncv = nc.variables[vname]
            orig_units = ncv.units
            masked_data = ncv[:,:]    # sx3(j=south_north,i=west_east)
        data_rawunits, converged = gridfill.fill(masked_data, 1, 0, .1)#, itermax=10000)
        self.data = cfutil.convert(data_rawunits, orig_units, units)

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
# {'T': (low, high), 'S': (low, high), ...}
post_cat_bounds = \
    dict((pra_size, (_post_cat_bounds[ix], _post_cat_bounds[ix+1])) for ix,pra_size in enumerate(rammsutil.PRA_SIZES.keys()))


def rule(scene_dir, return_period, forest, require_all=True):
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
    resolution = scene_args['resolution']
    scene_name = scene_args['name']
    For = 'For' if forest else 'NoFor'

    # eCognition filename conventions
    pra_file,_ = process_tree.pra_files(scene_args, return_period, forest)
    inputs.append(pra_file)    # This rule does NOT use the burn files for domains...

    # Full pathnames of release files generated from this (scene_name, return_period, forest) combo
    outputs = list()
    ramms_names = list()
    for pra_size in rammsutil.PRA_SIZES.keys():    # T,S,M,L
        # DEBUG: Only do 'L' for now
        if pra_size not in config.allowed_pra_sizes:
            continue
        jb = rammsutil.RammsName(os.path.join(scene_dir, 'RAMMS'), scene_name, None, forest, resolution, return_period, pra_size, None)
        ramms_names.append((jb,pra_size))
        # This filename does NOT have any segment numbers.
        outputs.append(os.path.join(scene_dir, 'RAMMS', f'{jb.ramms_name}_rel.shplist'))

    # Add one-off input files
    inputs += [scene_args['snowdepth_file'], scene_args['snowdepth_geo']]

    def action(tdir):

        # Create lookup for snow depth in WRF output file
        snow_lookup = WrfLookup(
            scene_args['coordinate_system'], scene_args['snowdepth_file'],
            'sx3', scene_args['snowdepth_geo'], units='m')
        snow_info = snow_lookup.geo_info

        degree = np.pi / 180.
        name = scene_args['name']
        resolution = scene_args['resolution']

        # Load the polygons
        print('======== Reading {}'.format(inputs[0]))
        df = shputil.read_df(inputs[0], shape='pra')
        df = df.rename(columns={'fid': 'Id'})    # RAMMS etc. want it named "Id"
        sx3_mm_swe = df['pra'].map(snow_lookup.value_at_centroid)    # Raw snow amount [kg m-2]
        by_SNOW_DENSITY = 1. / 200.    # [m^3 kg-1]   (Wolken; based on data we have on field work in these areas).
        # Typical values: 1m
        df['sx3'] = sx3_mm_swe * by_SNOW_DENSITY    # Depth of SNOW [m]


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
# gradient_snowdepth needs to be based on precip. lapse rates around Juneau; Gabe will get back on that.
# Yves: reference_elevation should be elveation value from Rick's raster.
# If PRA is above DEM gridcell then must inflate reanalysis snow volume.  If PRA is below DEM, then defalte it.
        # def['Mean_DEM'] is mean elevation of the PRA

        gradient_snowdepth_si_units = .01 * scene_args['gradient_snowdepth'] # gradient_snowdepth parameter is in m/100m, translate to unitless

        snowdepth_correction = \
            (df['Mean_DEM'] - scene_args['reference_elevation']) \
            * gradient_snowdepth_si_units
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
        mean_slope_rad = df['Mean_Slope'] * degree
        df['slopecorr'] =  0.291 / \
            (np.sin(mean_slope_rad) - 0.202 * np.cos(mean_slope_rad))

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

        # Split into segments and save
        ioutil.mkdirs_for_files(outputs)
        for ((jb,pra_size),output) in zip(ramms_names,outputs):
            low,high = post_cat_bounds[pra_size]

            print(f'Category: {pra_size}, [{low}, {high})')
            df_cat = df[df['area_m2'].between(low, high, inclusive='both')]  # SHOULD be inclusive='left'


            # Split df for this category (size) PRAs into bite-size chunks
            df_chunks = [df_cat[i:i+config.max_ramms_pras] for i in range(0,df_cat.shape[0],config.max_ramms_pras)]
            ofnames = list()
            for segment,dfc in enumerate(df_chunks):
                jb.set(segment=segment)
                ofname = os.path.join(jb.ramms_dir, 'RELEASE', f'{jb.ramms_name}_rel.shp')
                ofnames.append(ofname)
                os.makedirs(os.path.split(ofname)[0], exist_ok=True)
                shputil.write_df(dfc, 'pra', 'Polygon', ofname, wkt=scene_args['coordinate_system'])

            # Write names of our PRA files into the final output file.
            with open(output, 'w') as out:
                for ofname in ofnames:
                    out.write('{}\n'.format(config.roots.relpath(ofname)))

                
    return make.Rule(action, inputs, outputs)

