from uafgi.util import gdalutil,shapelyutil,shputil
import numpy as np


# Original axis=2 index into neighbor array
# (before neighbors are sorted)
NW,NN,NE = (1,2,3)
WW,CC,EE = (4,0,5)
SW,SS,SE = (6,7,8)

def neighbor_array(raster, nodata):
    """Create an graph of nodes with adjoining nodes.
    The graph is represented as a 3D array of integers.

    raster: np.array(nj,ni); nj=# rows
        A raster
    nodata: scalar
        Value of cells in raster with missing data
    Returns: nparray((nj, ni, 9), dtype='i')
        1-D index of each of the 8 neighbors of each cell.
        
        neighbor[j,i,0] = index of cell (j,i)
            --> or -1 if no data in (j,i)
        neighbor[j,i,n] = nth neighbor of cell (j,i)
            --> or -1 if cell (j,i) has fewer than n neighbors
            Neighbors are reverse sorted by their 1D index

        By definition, cells with neighbor[j,i,0] == -1 have zero
        neighbors; and thus, neighbor[j,i,1:] == -1 as well.
    """

    # Create 3D output array
    nj,ni = raster.shape
    neighbors = np.zeros((nj, ni, 9), dtype='i')

    # Create 2-D array giving 1-D index of each cell
    # ixvals = array([
    #   [ 0,  1,  2,  3,  4,  5,  6,  7,  8,  9],
    #   [10, 11, 12, 13, 14, 15, 16, 17, 18, 19],
    #   [20, 21, 22, 23, 24, 25, 26, 27, 28, 29],
    #   [30, 31, 32, 33, 34, 35, 36, 37, 38, 39]])
    ivals = np.tile(np.arange(0,ni),(nj,1))
    jvals = np.tile(np.arange(0,nj).reshape(-1,1), (1,ni))
    neighbors[:,:,CC] = jvals * ni + ivals

    # Any cells with missing values, turn their 1-D index to -1 This
    # will result in a -1 as the appropriate index for neighbors with
    # missing values.
    ixvals = neighbors[:,:,CC]   # live slice
    ras_nodata = (raster == nodata)
    ixvals[ras_nodata] = -1

    # Compute neighbors NN and SS by shifting up/down
    izeros=np.zeros((1,ni), dtype='int64')-1
    neighbors[:,:,NN] = np.concatenate((izeros, ixvals[:-1,:]))
    neighbors[:,:,SS] = np.concatenate((ixvals[1:,:], izeros))

    # Compute neighbors WW and EE by shifting left/right
    jzeros=np.zeros((nj,1), dtype='int64')-1
    neighbors[:,:,WW] = np.concatenate((jzeros, ixvals[:,:-1]), axis=1)
    neighbors[:,:,EE] = np.concatenate((ixvals[:,1:], jzeros), axis=1)

    # Compute neighbors NW and SW by shifting WW up/down
    neighbors[:,:,NW] = np.concatenate((izeros, neighbors[:-1,:,WW]))
    neighbors[:,:,SW] = np.concatenate((neighbors[1:,:,WW], izeros))

    # Compute neighbors NE and SE by shifting EE up/down
    neighbors[:,:,NE] = np.concatenate((izeros, neighbors[:-1,:,EE]))
    neighbors[:,:,SE] = np.concatenate((neighbors[1:,:,EE], izeros))

    # Remove neighbors of non-existant cells
    neighbors[ras_nodata,:] = -1

    # Sort so neighbors[j,i,:] yields:
    #     [index, neighbor1, neighbor2, .., -1, -1,]
    ixvals = neighbors[:,:,0:1]
    sorted_neighbors = -np.sort(-neighbors[:,:,1:],axis=2)
    neighbors = np.concatenate((ixvals, sorted_neighbors), axis=2)

    return neighbors.astype('i')

def dem_example():
    # Small example
    nj=9
    ni=10
    ivals = np.tile(np.arange(0,ni),(nj,1))
    jvals = np.tile(np.arange(0,nj).reshape(-1,1), (1,ni))

    # Make a ramp from SE to NW, with a notch down the middle
    ramp = ivals + jvals
    notch = np.maximum(np.flipud(jvals) + ivals, jvals + np.fliplr(ivals))

    dem = ramp + notch*.4

    # Make an ocean in the corner
    dem[0:4,0] = -5
    dem[0:2,1] = -5
    dem[0:1,2] = -5

    # Make an internally drained basin
    # (to be corrected for later)
    # dem[4:6,4:6] = 6.

    return dem,-5

def main():

    dem,nodata = dem_example()
    ngh = neighbor_array()


# =====================================================



def find_domain(pra, dem_file):
    """
    grid_info: gisutil.RasterInfo
        see gdalutil.file_info()
    pra: Shapely Polygon
        Potential Release Area
    dem: np.array
        The Digital Elevation Model
        Should have same dimensions as grid_info
    """

    # ---- Do this just once
    # Read the raster file
    grid_info,dem,dem_nodata = gdalutil.read_raster(dem_file)
    dem[dem==dem_nodata] = 0

    print(grid_info)
    print(dem)
    print(dem.dtype)

#    dem[np.abs(dem) > 1e10] = 0
    print(dem)
    print(np.sum(dem==0))
    print(np.sum(dem))
    print(dem.shape, np.min(dem), np.max(dem), np.mean(dem))

    # ------ Do this many times
    # Convert the (single) Shapely polygon to an OGR datasource
    pra_ds = shapelyutil.to_datasource(pra)

    # Burn everything in the OGR datasource into a raster
    # Returned as numpy array
    pra_ras = gdalutil.rasterize_polygons(pra_ds, grid_info)

    print(np.sum(pra_ras))



pras_file = '/Users/eafischer2/av/prj/juneau1/juneau1_For_5m_30L_rel.shp'
dem_file = '/Users/eafischer2/av/data/wolken/BaseData_AKAlbers/Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'

def main0():
    pras_df = shputil.read_df(pras_file)
    row = pras_df.iloc[0]
    print(row)
    print(row.shape)


    find_domain(row.shape, dem_file)


#main()
