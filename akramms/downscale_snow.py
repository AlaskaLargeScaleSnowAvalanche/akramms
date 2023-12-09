import subprocess
import os,pathlib,shutil,functools,sys
import netCDF4
import numpy as np
import pandas as pd
import rtree
from osgeo import gdalconst,gdal
from uafgi.util import wrfutil,gdalutil
from akramms import config,process_tree
from akramms.util import paramutil,harnutil,arcgisutil
from uafgi.util import make
from akramms import params

"""Rules to prepare the snow field for direct use in determining snow depth for PRAs."""

# --------------------------------------------------------------------------
@functools.lru_cache()
def r_distance_from_coast(wrf_geo_nc, ofname):
    """Computes the distance of every WRF gridcell from the coast
    wrf_geo_nc:
        The WRF geometry file.
    ofname:
        Output filename to produce
    """

    def action(tdir):
        # wrf-format files
        #sx3_dir = config.roots.syspath('{DATA}/lader/sx3')
        #wrf_geo_nc = os.path.join(sx3_dir, 'geo_southeast.nc')

        gridA = wrfutil.wrf_info(wrf_geo_nc)
        wrfdemA,wrfdemA_nodata = wrfutil.read_raw(wrf_geo_nc, 'HGT_M')    # North-up
        wrfdemA = wrfdemA[0,:,:]    # (y,x)

        # Turn ocean gridcells with little islands into pure ocean
        wrfdemA[np.abs(wrfdemA) < 10] = 0
        wrfdemA1 = wrfdemA.reshape(-1)


        # Get index and bounding box of each ocean gridcell
        ocean_ix1 = np.where(wrfdemA1 == 0)[0]
        ocean_ixs = np.where(wrfdemA == 0)

        centersy = gridA.centersy[ocean_ixs[0]]
        lowy  = centersy - 0.5*gridA.dy
        highy = centersy + 0.5*gridA.dy

        centersx = gridA.centersx[ocean_ixs[1]]
        lowx  = centersx - 0.5*gridA.dx
        highx = centersx + 0.5*gridA.dx

        # Make an rtree of it
        print('Assembling the rtree...')
        ocean_idx = rtree.index.Index()
#        for ix, lx,hx,ly,hy in zip(ocean_ix1, lowx, highx, lowy, highy):
#            ocean_idx.insert(ix, (ly,lx,hy,hx))
        for ix,cx,cy in zip(ocean_ix1, centersx, centersy):
            ocean_idx.insert(ix, (cy,cx,cy,cx))
        print('Done!')

        # Find index of nearest ocean gridcell(s) to all non-cean gridcells
        land_ixs = np.where(wrfdemA1 != 0)[0]
        jjs,iis = np.where(wrfdemA != 0)
        xs,ys = gridA.to_xy(iis, jjs, center=True)

        #hdy = 0.5*gridA.dy
        #hdx = 0.5*gridA.dx
        bounds = [0]
        source_ixs = list()
        source_xs = list()
        source_ys = list()
        nearest_ixs = list()
        for ix,y,x in zip(land_ixs,ys,xs):
#            results = list(ocean_idx.nearest((y-hdy, x-hdx, y+hdy, x+hdx), num_results=1))
            # Find 30 nearest ocean gridcells to the current gridcell
            results = list(ocean_idx.nearest((y,x,y,x), num_results=30))
            source_ixs += [ix]*len(results)
            nearest_ixs += results
            source_ys += [y]*len(results)
            source_xs += [x]*len(results)
            bounds.append(len(nearest_ixs))

        # Convert 1D indices to x,y
        nearest_js, nearest_is = np.divmod(nearest_ixs, gridA.nx)
        nearest_xs, nearest_ys = gridA.to_xy(nearest_is, nearest_js, center=True)

        # Put it all in a dataframe

        dfdict = {'ix': source_ixs, 'landx': source_xs, 'landy': source_ys, 'oceanx': nearest_xs, 'oceany': nearest_ys}
        for k,v in dfdict.items():
            print(k, len(v))
        df = pd.DataFrame(dfdict)

        # Compute distance from land to ocean gridcell
        x = (df.landx - df.oceanx)
        x2 = x*x
        y = (df.landy - df.oceany)
        y2 = y*y
        df['distance'] = (x2+y2).map(np.sqrt)

        # Compute mean distance
        df = df[['ix', 'distance']]
        df = df.groupby('ix').mean().reset_index()

        # Create distance raster
        distanceA1 = np.zeros(gridA.nxy)
        distanceA1[df.ix.to_numpy()] = df.distance.to_numpy()
        distanceA = distanceA1.reshape((gridA.ny, gridA.nx))

        # Save it to GeoTIFF
        os.makedirs(os.path.split(ofname)[0], exist_ok=True)
        gdalutil.write_raster(ofname, gridA, distanceA, 0, type=gdal.GDT_Float32)
        # gdalutil.write_raster('hgt.tif', gridA, wrfdemA, wrfdemA_nodata, type=gdal.GDT_Float32)
                
    return make.Rule(action, [wrf_geo_nc], [ofname])

# --------------------------------------------------------------------------
## TODO: Make this NOT a rule.
def select_sx3_rule(scene_dir, sx3_file, geo_nc, smooth=False):
    """Regrids Lader's SX3 to the scene grid, and selects the nearest neighbor.
    sx3_file:
        Name of the input WRF NetCDF file to use.
        Eg: 555config.syspath('{DATA}/lader/sx3/cfsr_2010_sx3.nc')
                  cfsr: reanalysis
            ccsm, gfdl: climate models
    geo_nc:
        Name of the WRF geometry file that describes input.
        Eg: config.syspath('{DATA}/lader/sx3/geo_southeast.nc')
    """

    scene_args = params.load(scene_dir)
    scene_name = scene_args['name']

    inputs = [sx3_file]
    leaf = os.path.split(sx3_file)[1]
    base = os.path.splitext(leaf)[0]
    outputs = [os.path.join(scene_dir, f'{base}_{scene_name}_select.tif')]

    def action(tdir):
        # Read input from WRF
        gridA = wrfutil.wrf_info(geo_nc)
        sx3A,sx3A_nd = wrfutil.read_raw(sx3_file, 'sx3', fill_holes=True)    # NOTE: All gridcells are expected to have data
        if len(sx3A.shape) == 3:
            sx3A = sx3A[0,:]    # Get rid of Time dimension

        # Construct output grid (and also read the DEM, which might be useful elsewhere)
        gridI, elevI, elevI_nd = gdalutil.read_raster(scene_args['dem_file'])

        # Regrid sx3
        sx3I = gdalutil.regrid(
            sx3A, gridA, float(sx3A_nd),
            gridI, float(sx3A_nd),
            resample_algo=gdalconst.GRA_NearestNeighbour)

        # Write output
        gdalutil.write_raster(outputs[0], gridI, sx3I, sx3A_nd, type=gdal.GDT_Float32)
 
    return make.Rule(action, inputs, outputs)

# ---------------------------------------------------------------------
#def lapse_by_inland_rule(scene_dir, sx3_file, geo_nc):
def lapse_by_distance_from_coast(cdistA):
    """Computes a per-gridcell lapse rate based on distance from coast.
    See for how this curve was eyeballed: distance_lapse.py

    cdistA: array(nyA, nxA)
        Distance from coast (in lo-res grid)
    Returns: [mm /m]
        Lapse rate for sx3 variable
        (in mm snow per m of elevation)
    """
    lr0 = .0923    # Lapse rate [mm / m]
    lr1 = .0373
    dc0 = 90000.    # Distance from coast [m]
    dc1 = 240000.

    lapseA = np.zeros(cdistA.shape)

    # Lapse rate for cells <90km from coast
    lapseA[cdistA < dc0] = lr0

    # Lapse rate for cells between 90 and 240 km from coast
    slope = (lr1-lr0) / (dc1-dc0)
    mask_in = np.logical_and(cdistA >= dc0, cdistA < dc1)
    lapseA[mask_in] = lr0 + slope * (cdistA[mask_in] - dc0)

    # Lapse rate from cells >= 240km from coase
    mask_in = (cdistA >= dc1)
    lapseA[mask_in] = lr1

    return lapseA

#def lapse_sx3_rule(scene_dir, sx3_file, geo_nc, distance_from_coastA_tif):
#    """Regrids Lader's SX3 to the scene grid, and selects the nearest neighbor.
#    sx3_file: (A grid)
#        Name of the input WRF NetCDF file to use.
#        Eg: 555config.syspath('{DATA}/lader/sx3/cfsr_2010_sx3.nc')
#                  cfsr: reanalysis
#            ccsm, gfdl: climate models
#    geo_nc:
#        Name of the WRF geometry file that describes input.
#        Eg: config.syspath('{DATA}/lader/sx3/geo_southeast.nc')
#    distance_from_coastA_tif: (A grid)
#        File containing distance from gridcells
#    """
#
#    scene_args = params.load(scene_dir)
#    scene_name = scene_args['name']
#
#    inputs = [sx3_file, distance_from_coastA_tif]
#    leaf = os.path.split(sx3_file)[1]
#    base = os.path.splitext(leaf)[0]
#    outputs = [os.path.join(scene_dir, f'{base}_{scene_name}_lapse.tif')]
#
#    def action(tdir):


# -----------------------------------------------------------------
def downscale_sx3_with_lapse(sx3_file, geo_nc, distance_from_coastA_tif, dem_tif, ofname):
    """
    sx3_file: (gridA)
        The WRF output file containing sx3 snow variable
    geo_nc: (gridA)
        The WRF output file describing the CRS and geotransform
    distance_from_coastA_tif: (gridA)
        Previously computed distance-from-coast measure (see above)
    dem_tif: (gridI)
        The hi-res DEM for a particular RAMMS scene
    ofname:
        Name of the output file
    """
    # Read input from WRF
    gridA = wrfutil.wrf_info(geo_nc)
    sx3A,sx3A_nd = wrfutil.read_raw(sx3_file, 'sx3', fill_holes=True)    # NOTE: All gridcells are expected to have data
    if len(sx3A.shape) == 3:
        sx3A = sx3A[0,:]    # Get rid of Time dimension

    # Construct output grid (and also read the DEM, which might be useful elsewhere)
    gridI, elevI, elevI_nd = gdalutil.read_raster(dem_tif)
    print('elevI_nd = ', elevI_nd)

    # Regrid sx3
    sx3I_tif = os.path.join('sx3I.tif')
#    if os.path.exists(sx3I_tif):
#        _,sx3I,_ = gdalutil.read_raster(sx3I_tif)
#    else:
    if True:
        print('Computing sx3I...')

        # Regrid WRF snow field sx3 to the local grid by resampling
        sx3I = gdalutil.regrid(
            sx3A, gridA, float(sx3A_nd),
            gridI, float(sx3A_nd),
            resample_algo=gdalconst.GRA_NearestNeighbour)

        # Smooth it!
        sigma = (.5*gridA.dy, .5*gridA.dx)
#        kernel = gaussian(sigma, (gridA.dy, gridA.dx))
#        sx3I = scipy.signal.fftconvolve(sx3I, kernel mode='same')    # Assumes no missing values
        sx3I = scipy.ndimage.gaussian_filter(sx3I, sigma)

        if True:
            gdalutil.write_raster(
                sx3I_tif,
                gridI, sx3I, sx3A_nd, type=gdal.GDT_Float32)


    sys.exit(0)

    # --------------------------------------------------------
    # Read input from distance file
    gridA0, distanceA, distanceA_nd = gdalutil.read_raster(distance_from_coastA_tif)

    # Compute lapse rate based on distance from coast

#    lapseAI_tif = os.path.join(scene_dir, 'lapseAI.tif')
#    if os.path.exists(lapseAI_tif):
#        _,lapseAI,_ = gdalutil.read_raster(lapseAI_tif)
#    else:
    if True:
        print('Computing lapseA...')
        lapseA = lapse_by_distance_from_coast(distanceA)
#        gdalutil.write_raster(
#            os.path.join(scene_dir, 'lapseA.tif'),
#            gridA, lapseA, -1.e30, type=gdal.GDT_Float32)

        print('Computing lapseAI...')
        lapseAI = gdalutil.regrid(
            lapseA, gridA, float(-1.e30),
            gridI, float(-1.e30),
            resample_algo=gdalconst.GRA_NearestNeighbour)
#        gdalutil.write_raster(
#            lapseAI_tif,
#            gridI, lapseAI, -1.e30, type=gdal.GDT_Float32)

    # Determine "average over A grid" elevation of each gridcell in I
#    elevAI_tif = os.path.join(scene_dir, 'elevAI.tif')
#    if os.path.exists(elevAI_tif):
#        _,elevAI,_ = gdalutil.read_raster(elevAI_tif)
#    else:
    if True:
        print('Computing elevA...')
        elevA = gdalutil.regrid(
            elevI, gridI, float(elevI_nd),
            gridA, float(elevI_nd),
            resample_algo=gdalconst.GRA_Average)
        print('Computing elevAI...')
        elevAI = gdalutil.regrid(
            elevA, gridA, float(elevI_nd),
            gridI, float(elevI_nd),
            resample_algo=gdalconst.GRA_NearestNeighbour)

#        gdalutil.write_raster(elevAI_tif, gridI, elevAI, elevI_nd, type=gdal.GDT_Float32)

    # Determine elevation difference used to downscale
#    elevdiffI_tif = os.path.join(scene_dir, 'elevdiffI.tif')
#    if os.path.exists(elevdiffI_tif):
#        _,elevdiffI,_ = gdalutil.read_raster(elevdiffI_tif)
#    else:
    if True:
        # TODO: Mysterious corners of elevAI that should be filled actually have NOVAL.
        # Maybe something funny happening for GRA_Average on small numbers of points?
        mask_out = np.logical_or(elevI == elevI_nd, elevAI == elevI_nd)
        elevdiffI = elevI - elevAI
        elevdiffI[mask_out] = 0
#        gdalutil.write_raster(elevdiffI_tif, gridI, elevdiffI, elevI_nd, type=gdal.GDT_Float32)

    # Adjust sx3I base on lapse rate
    sx3I += lapseAI * elevdiffI
    sx3I[sx3I < 0] = 0

    # --------------------------------------------------------
    # Write output
    print(f'Writing output: {ofname}')
    os.makedirs(os.path.split(ofname)[0], exist_ok=True)
    gdalutil.write_raster(ofname, gridI, sx3I, sx3A_nd, type=gdal.GDT_Float32)


#rule = select_sx3_rule(
#    '/home/efischer/prj/juneau1',
#    '/home/efischer/av/data/outputs/sx3/ccsm_sx3_1981_2010.nc',
#    '/home/efischer/av/data/lader/sx3/geo_southeast.nc')
#rule.action(None)

