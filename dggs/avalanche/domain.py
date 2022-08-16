import collections,itertools,sys
from uafgi.util import gdalutil,shapelyutil,shputil,gisutil
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

class ECGNodeInfo(collections.namedtuple('ECGNode', ['ji', 'forward', 'edge', 'eqclass', 'neighbors'])):
    pass

class ECGraph:
    """Graph of Equivalence Classes.
    Graph has out-degree of 1."""
#    def __init__(self, forward, eqclass, neighbors, edge):
#        self.forward = forward
#        self.eqclass = eqclass
#        self.neighbors = neighbors
#        self.edge = edge

    def __init__(self, neighbors):
        """Begin by creating an equivalence class for every gridcell.

        neighbors: int[ji, 9]
            Index of neighbors of each gridcell
            neighbors[ji,0] < 0:
                gridcell ji doesn't exist
            neighbors[ji,k] < 0:
                gridcell ji doesn't have a kth neighbor
        """

        # Reshape neigbhors to 2D
        neighbors = neighbors.reshape((np.prod(neighbors.shape[:-1]), neighbors.shape[-1]))

        # Original number of nodes in graph
        self.nnode0 = neighbors.shape[0]

        unused = (neighbors[:,0] == -1)
        print('Found {} unused cells'.format(np.sum(unused)))

        # forwards[i] is the currently-valid equivalence class
        # that node i has been merged into.
        self.forward = np.arange(self.nnode0)
        self.forward[unused] = -1

        # eqclass[i] is the gridcells currently in equivalence class i
        # It is initialized to one gridcell per class
        self.eqclass = [None if unused[ji] else set((ji,)) for ji in range(self.nnode0)]

        # Neighbor nodes as sets
        # INVARIANT: This is disjoint from eqclass
        self.neighbors = [None if unused[ji] else
            set(x for x in neighbors[ji,1:] if x >= 0)
            for ji in range(self.nnode0)]

        # Determine whether it's an edge
        self.edge = (neighbors[:,-1] < 0)

    def __len__(self):
        return len(self.forward)

    def all_neighbors(self,i):
        """Returns neighbors of node i, including i itself, as a list."""
        return list(itertools.chain((i,), self.neighbors[i]))

    def info(self,i):
        """Useful for debuggin"""
        return ECGNodeInfo(i, self.forward[i], self.edge[i], self.eqclass[i], self.neighbors[i])

    def merge(self, i, j):
        """Merges eqclass i into j
        i:
            Index of source equivalence class
        j:
            Index of desitnation equivalence class.
        """
        # Update nodes in this equivalence class
        self.eqclass[j].update(self.eqclass[i])
        self.edge[j] = self.edge[j] or self.edge[i]

        # Merge neighbors
        # Maintain invariant, disjoint from eqclass
        self.neighbors[j].update(self.neighbors[i])
        self.neighbors[j].difference_update(self.eqclass[j])


        # Update forwards to j
        for k in self.eqclass[i]:
            self.forward[k] = j

        # Decommission i
        self.eqclass[i] = None
        self.neighbors[i] = None

def fill_sinks(ecg, dem, max_sink_size=10):
    """Merges equivalence classes with no outlets
    ecg:
        ECGraqph
    dem:
        Original digital elevation model
        (WILL BE MODIFIED)
    max_sink_size:
        Don't merge sinks larger than this.
    """
    dem = dem.reshape(-1)
    nnode = dem.shape[0]
    for ix in range(nnode):
        # Only look at primary node for each EQ class
        if ecg.forward[ix] != ix:
            continue

        # Progressively merge with neighbors
        while True:
            # Edge nodes don't get merged, the edge is "by definition" an outflow.
            if ecg.edge[ix]:
                break

            # Find lowest neighbor
            ngh = ecg.forward[list(ecg.neighbors[ix])]    # Could be dups
            min_ix = ngh[np.argmin(dem[ngh])]

            # This EQ class is not a sink because it has an outflow to a neighbor
            #print(ix, dem[ix], ngh, dem[ngh])
            if dem[ix] > dem[min_ix]:
                break

            # This EQ class IS a sink: merge with lowest neighbor
            print('Merging {} -> {}'.format(min_ix, ix))
            #print(dem[min_ix], ecg.info(min_ix))
            #print(dem[ix], ecg.info(ix))
            ecg.merge(min_ix, ix)   # Merge min_ix into ix
            # Set elevation for the EQ class accordingly
            dem[ix] = dem[min_ix]

            if len(ecg.eqclass[ix]) > max_sink_size:
                break

    # Look up all forwards (and remove neighbors pointing to now-defunct EC's)
    for ix in range(nnode):
        if ecg.neighbors[ix] is not None:
            ecg.neighbors[ix] = set(ecg.forward[list(ecg.neighbors[ix])])


def set_lowest_neighbor(ecg, dem):
    """Starting with a graph of ALL neighbors, removes those that are
    not the steepest."""

    dem = dem.reshape(-1)
    for ix in range(len(ecg)):
        if ecg.neighbors[ix] is not None:
            ngh = list(ecg.neighbors[ix])
            elev = dem[ngh]
            min = np.min(elev)
            #min_ix = ngh[np.argmin(dem[ngh])]
            ecg.neighbors[ix] = set(itertools.compress(ngh, elev == min))
        
# Remove extra neighbors...

def fill_region(ecg, cells0):
    """Finds the set of nodes reachable from cells0.
    ecg:
        The graph, with nodes ALREADY consolidated.
    cells0:
        Gridcells in the UNCONSOLIDATED graph to start with.
        (Any collection type OK)
    """

    # Get set of starting nodes in consolidated graph
    seen = set(ecg.forward[list(cells0)])

    # Fill until we reach a sink
    while True:
        nghs = [ecg.neighbors[ix] for ix in seen]
        print('seen: ', sorted(list(seen)))
        #print('nghhs ',list(zip(seen,nghs)))
        #print('******* ',ecg.info(45))
        neighbors = set().union(*nghs)
        new_neighbors = neighbors.difference(seen)
        #print(neighbors)
        #print(new_neighbors)
        if len(new_neighbors) == 0:
            break
        seen.update(new_neighbors)

    # Convert from EQ classes back to node indices
    print('seen: {}'.format(sorted(list(seen))))
    cells1 = np.array(sorted(list(set().union(*[ecg.eqclass[ix] for ix in seen]))))
    return cells1


# --------------------------------------------------------------
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
    dem[4:6,4:6] = 6.

    grid_info = gisutil.RasterInfo('', ni, nj, [0.0, 2.0, 0.0, 0.0, 0.0, 2.0])

    return dem,-5,grid_info

def main():

    # Compute filled-out set of points
    #importlib.reload(domain)
    dem,nodata0,grid_info=domain.dem_example()
    nj,ni = dem.shape

    neighbors = domain.neighbor_array(dem,nodata0)
    ecg = domain.ECGraph(neighbors)
    domain.fill_sinks(ecg, dem)
    domain.set_lowest_neighbor(ecg,dem)
    cells0 = {78,68,29}
    cells1 = domain.fill_region(ecg, cells0)

    ivals = np.tile(np.arange(0,ni),(nj,1)).reshape(-1)
    jvals = np.tile(np.arange(0,nj).reshape(-1,1), (1,ni)).reshape(-1)
    ii = ivals[cells1]
    jj = jvals[cells1]

    xx,yy = grid_info.to_xy(ii,jj)
    print(yy)
    print(xx)



    import MinimumBoundingBox
    mp = shapely.geometry.MultiPoint(list(zip(xx,yy)))
    chull = mp.convex_hull
    chull_list = list(zip(*chull.exterior.coords.xy))
    mbb = MinimumBoundingBox.MinimumBoundingBox(chull_list[:-1])

    margin = 2
    center = np.array(list(mbb.rectangle_center))
    j0 = np.array(list(mbb.unit_vector))
    jj0 = j0 * (margin + .5*mbb.length_parallel)
    j1 = np.array([j0[1],-j0[0]])
    jj1 = j1 * (margin + .5*mbb.length_orthogonal)
    mbb_points = [center+jj0+jj1, center+jj0-jj1,  center-jj0+jj1, center-jj0-jj1]
    mbb_rectangle = shapely.geometry.MultiPoint(list(mbb_points)).convex_hull

    #mbb_rectangle=shapely.geometry.MultiPoint(list(mbb.corner_points)).convex_hull
    mbb



    # mbb_rectangle is our domain!!!
    plt.plot(*mbb_rectangle.exterior.xy)
    plt.plot(*chull.exterior.xy)
    plt.plot(xx,yy,marker='.', linewidth=0)
    mbb_points = list(np.array(xy) for xy in zip(*mbb_rectangle.exterior.xy))
    print(mbb_points)



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
