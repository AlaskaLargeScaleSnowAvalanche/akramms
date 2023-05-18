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

def overlap_nearest_neighbors(gridI, mask_inI, gridA):

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
class coo_list(collections.namedtuple('coo_list', ('data', 'ii', 'jj'))):
    def coo_matrix(self, shape, transpose=False):
        if transpose:
            return scipy.sparse.coo_matrix((self.data, (self.jj, self.ii)), shape=(shape[1],shape[0]))
        else:
            return scipy.sparse.coo_matrix((self.data, (self.ii, self.jj)), shape=shape)

def extend_to_elev(GuA, elevG, hcdefs)
    """Builds an interpolation matrix between grid G and the elevation grid E.
    gridG:
        Could be the basic fine-scale grid (ice grid), or the exchange
        grid if exact polygon overlaps are being used.
    elevG: np.array(gridI.nxy)
        Hi-res elevations.  (NOt sure:::???/ Dense indexing, ALL gridcells should exist!)
    gridA:
        The coarse grid the elevation classes are based on
    hcdefs:
        Elevations at which we compute
    """
    # Consider using np.digitze here instead()???
    upper_ecG = np.searchsorted(hcdefs, elevG[GuA.ii])    # Upper elevation class for each gridcell GuA matrix
    lower_ecG = upper_ecG - 1

    intervalsG = hcdefs[upper_ecG] - hcdefs[lower_ecG] # Size EC interval each point is in
    lower_weightsG = (hcdefs[upper_ecG] - elevG) / intervalsG
    upper_weightsG = 1.0 - lower_weightsG

    # Index of each gridcell in E
    lower_eixG = GuA.jj * len(hcdefs) + lower_ecG
    lower_dataG = lower_weightsG * GuA.data

    upper_eixG = GuA.jj * len(hcdefs) + upper_ecG
    upper_dataG = upper_weightsG * GuA.data

    return coo_list(
        np.concatenate((lower_dataG, upper_dataG))
        np.concatenate((GuA.ii, GuA.ii))
        np.concatenate((lower_eixG, upper_eixG)))

# --------------------------------------------------------------------------
def diag(diagnoal):
    """A simple sparse diagonal matrix creator"""
    return scipy.sparse.diags([diagonal])

def scale_matrix(IuJ_list, transpose=False):
    """Returns:
    IuJ_list: coo_list
        Unscaled matrix, raw output of matrix generators
    IvJ: scipy.coo_matrix
        Scaled matrix, ready to use
    Returns:
        If transpose:
            IvJ
        Elase:
            JvI
    """
    # Or try this: https://stackoverflow.com/questions/52953231/numpy-aggregate-into-bins-then-calculate-sum
    IuJ = IuJ_list.coo_matrix(transpose=transpose)    # Or this might be JuI
    wIuJ = np.squeeze(np.asarray(IuJ.sum(axis=1)))
    return diag(wIuJ) * IuJ

# --------------------------------------------------------------------------


class MatrixSet:
    def __init__(self, gridI, mask_inI, elevI, gridA, hcdefs):
        self.gridI = gridI
        self.mask_inI = mask_inI
        self.elevI = elevI
        self.gridA = gridA
        self.hcdefs = hcdefs

    @cached_property
    def IuA_list(self):
        return overlap_nearest_neighbors(self.gridI, self.mask_inI, self.gridA)
    @cached_property
    def IuE_list(self):
        return extend_to_elev(self.IuA_list, self.elevI, self.hcdefs)

    @cached_property
    def IvA(self):
        return scale_matrix(self.IuA_list, tranpose=False)
    @cached_property
    def AvI(self):
        return scale_matrix(self.AuI_list, transpose=True)
    @cached_property
    def IvE(self):
        return scale_matrix(self.IuE_list, transpose=False)
    @cached_property
    def EvI(self):
        return scale_matrix(self.IuE_list, transpose=True)
    @cached_property
    def EvA(self):
        return self.EvI * self.IvA
    @cached_property
    def AvE(self):
        return AvI * IvE


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
