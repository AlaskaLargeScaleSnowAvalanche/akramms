import os
import numpy as np
from akramms import config,params
from uafgi.util import gdalutil,wrfutil
from osgeo import gdalconst


# Scene definition
scene_dir = config.roots.syspath('{PRJ}/juneau1')

# wrf-format files
sx3_dir = config.roots.syspath('{DATA}/lader/sx3')
wrf_geo_nc = os.path.join(sx3_dir, 'geo_southeast.nc')
wrf_sx3_nc = os.path.join(sx3_dir, 'ccsm_sx3_2010.nc')

def nearest_overlap(gridI, mask_inI, gridA):

    """Computes the overlap matrix IoA.  Assumes gridcells in I are
    really small (compared to A), and assigns each 100% to the nearest
    gridcell in A, even for gridcells in I on the border between two
    gridcells in A.  I may be incomplete, it is assumed A covers the
    entire domain of I.

    gridI, gridA:
        Grid definitions for I and A grid
    mask_inI: bool(ny,nx)
        True if gridell is included in the grid, False if not.
    Returns: IoA
    """
    # aidA = Indices of A gridcells, on the A grid
    aidA_1 = np.arange(gridA.nx * gridA.ny, dtype='i')    # "Data" to regrid contains unique ID of each gridcell.
    aidA = np.reshape(aidA_1, (gridA.ny, gridA.nx))

    # aidI = Indices of A gridcells, on the I grid
    aidI = gdalutil.regrid(
        aidA, gridA, -1,    # A has data everywhere
        gridI, -1,    # nodata value won't be used
        resample_algo=gdalconst.GRA_NearestNeighbour)
    #aidI[mask_inI] = -1    # Set a nodata value

    # iidI = Indices of I gridcells, on the I grid
    iidI_1 = np.arange(gridI.nx*gridI.ny, dtype='i')
    iidI = np.reshape(iidI_1, (gridI.ny, gridI.nx))

    # Overlap matrix depends on elements from (iidI, aidI), as long as it is not masked out
    mask_inI_1 = np.reshape(mask_inI, -1)
    iidI_masked_1 = np.reshape(iidI, -1)[mask_inI_1]
    aidI_masked_1 = np.reshape(aidI, -1)[mask_inI_1]
    areaI_1 = np.zeros(iidI_masked_1.shape) + (gridI.dx * gridI.dy)    # Area of gridcell

    return scipy.sparse.coo_matrix(
        (areaI_1, (iidI_masked_1, aidI_masked_1)),
        shape=(gridI.nxy, gridA.nxy))

# --------------------------------------------------------------------------
# --------------------------------------------------------------------------


def main():

    scene_args = params.load(scene_dir)

    # Read hi-res DEM
    print('Reading: ', scene_args['dem_file'])
    gridI, elevI, elevI_nodata = gdalutil.read_raster(scene_args['elev_file'])

    print('elevI.shape ', elevI.shape)    # It's stored (ny, nx)
    print('x y ', elevI_grid.nx, elevI_grid.ny)

    # Identify mask
    mask_outI = (elevI = elevI_nodata)

    # Obtain WRF grid
    gridA = wrfutil.wrf_info(wrf_geo_nc)

    # Compute overlap matrix

main()
