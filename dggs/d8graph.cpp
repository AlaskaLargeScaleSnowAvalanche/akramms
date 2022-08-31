#define PY_SSIZE_T_CLEAN
#include <Python.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>
//#include "structmember.h"    // Map C struct members to Python attributes
#include <numeric>    // iota
// https://docs.python.org/3.9/extending/newtypes_tutorial.html
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <array>
#include <iostream>
#include <iomanip>
#include <iterator>

// https://stackoverflow.com/questions/77005/how-to-automatically-generate-a-stacktrace-when-my-program-crashes
#include <cstdio>
#include <execinfo.h>
#include <csignal>
#include <cstdlib>
//#include <cunistd>

static char module_docstring[] = 
"D8Graph 1.0.0 extension module computes graphs and flow paths in digital elevation models.";


typedef int ix_t;

/** A memory-efficient version of map<KeyT,ValT> in two vectors. */
template<class KeyT, class ValT>
struct PackedMap {
    std::vector<KeyT> keys;    // TODO: Use Numpy array here, because this is used to/from Python
    std::vector<ValT> values;
};

/** A memory-efficient version of map<KeyT, vector<ValT>> in three vectors */
template<class KeyT, class ValT, class IndexT>
struct PackedMapVectors {
    std::vector<KeyT> keys;
    std::vector<IndexT> starts = {0};    // Index into values; keys.size+1
    std::vector<ValT> values;

};


// ==================================================================================
template<class IterT>
std::ostream& operator << (std::ostream& out, std::array<IterT,2> const &bounds)
{
    std::copy(bounds[0], bounds[1],
      std::ostream_iterator<typename std::iterator_traits<IterT>::value_type>(std::cout, " "));
    return out;
}

template<class IterT>
std::ostream& print_range(std::ostream& out, IterT const &begin, IterT const &end)
{
    std::copy(begin, end,
      std::ostream_iterator<typename std::iterator_traits<IterT>::value_type>(std::cout, " "));
    return out;
}


template<class TypeT>
std::ostream& print_raster(std::ostream& out, std::vector<TypeT> const &arr, int const nj, int const ni)
{
//    std::cout << std::setw(9);
    std::cout << std::showpos;
    for (int j=0; j<nj; ++j) {
//        for (int i=0; i<ni; ++i) {
            
        std::copy(arr.begin()+j*ni, arr.begin()+(j+1)*ni,
            std::ostream_iterator<TypeT>(std::cout, " "));
        std::cout << std::endl;
    }
    return out;
}

template<class TypeT>
std::ostream& print_raster(std::ostream& out, TypeT const *arr, int const nj, int const ni)
{
    for (int j=0; j<nj; ++j) {
        for (int i=0; i<ni; ++i) {
            std::cout << std::setw(6) << *(arr + j*ni + i);
        }
        std::cout << std::endl;
//        std::copy(arr+j*ni, arr+(j+1)*ni,
//            std::ostream_iterator<TypeT>(std::cout, " "));
//        std::cout << std::endl;
    }
    return out;
}

template<class TypeT>
std::array<TypeT, 2> sorted(TypeT a, TypeT b)
{
    if (a < b) return {a,b};
    return {b,a};
}

// ==================================================================================
class EQClasses {
    // Cell this has been merged into (if it's been merged)
    std::unordered_map<ix_t, ix_t> forwards;

    // EQClass with >1 element
    // Inner vector is SORTED
    std::unordered_map<ix_t, std::vector<ix_t>> eqclasses;

    // Stand-in for single-element eqclasses
    std::vector<ix_t> _single_ret{0};

public:

    EQClasses() {}    // Start off with everything in its own class

    void set_forwards(PackedMap<ix_t, ix_t> const &_forwards)
    {
        // Initialize forwards
        for (size_t k=0; k<_forwards.keys.size(); ++k) {
            forwards[_forwards.keys[k]] = _forwards.values[k];
        }
    }

    void set_eqclasses(PackedMapVectors<ix_t, int, int> const &_eqclasses)
    {
        // Initialize eqclasses
        for (size_t k=0; k<_eqclasses.keys.size(); ++k) {
            size_t begin_ix = _eqclasses.starts[k];
            size_t end_ix = _eqclasses.starts[k+1];
            std::vector<int> eqc;
            for (size_t ix=begin_ix; ix<end_ix; ++ix)
                eqc.push_back(_eqclasses.values[ix]);
            eqclasses.insert(std::make_pair(_eqclasses.keys[k], std::move(eqc)));
        }
    }

    /** Initialized stored EQClasses from Python */
    EQClasses(
        PackedMap<ix_t, ix_t> const &_forwards,
        PackedMapVectors<ix_t, int, int> const &_eqclasses)
    {
        set_forwards(_forwards);
        set_eqclasses(_eqclasses);
    }


    /** Fetches the elements of the ith equivalence class */
    std::array<std::vector<ix_t>::iterator, 2> members(int eqi)
    {
        auto ii(eqclasses.find(eqi));
        if (ii != eqclasses.end()) {
            // This EQClass is stored explicitly, return it.
            return {ii->second.begin(), ii->second.end()};
        } else {
            // This EQClass is not explicitly represented, just equal to self
            _single_ret[0] = eqi;
            return {_single_ret.begin(), _single_ret.end()};
        }
    }

    /** Fetches the elements of the ith equivalence class */
    size_t size(int eqi)
    {
        auto ii(eqclasses.find(eqi));
        if (ii != eqclasses.end()) {
            // This EQClass is stored explicitly, return it.
            return ii->second.size();
        } else {
            // This EQClass is not explicitly represented, just equal to self
            return 1;
        }
    }




    /** SPECIAL CASE: Determines the lowest-number index in an eq class
    (Assumes members are always sorted)
    ix:
        An active eq class index (use parent() if needed).*/
    ix_t min_member(ix_t ix) const
    {
        auto ii(eqclasses.find(ix));
        if (ii != eqclasses.end()) {
            return ii->second[0];
        } else {
            return ix;
        }
    }

    /** Determines which eqclass the ith gridcell is a part of */
    ix_t parent(ix_t gci) const
    {
        auto ii(forwards.find(gci));
        if (ii != forwards.end()) return ii->second;
        return gci;
    }


    /** Merge eq class i into j
    i:
        Index of source equivalence class
    j:
        Index of destination equivalence class
    Returns:
        Sorted vector of members of newly merged j
    */
    std::vector<ix_t> &merge_eq(int j, int i)
    {
        // Access contents of the destination eq class,
        // converting to explicit form if needed.
        auto eqcj_it(eqclasses.find(j));
        if (eqcj_it == eqclasses.end()) {
            printf("Creating new eqclass for %d\n", j);
            eqcj_it = eqclasses.insert(eqcj_it, std::make_pair(j, std::vector<ix_t>{j}));
        }
        std::vector<ix_t> &eqcj(eqcj_it->second);
std::cout << "Dst EQClass " << j << ": "; print_range(std::cout, eqcj.begin(), eqcj.end()); std::cout << std::endl;

        // Access contents of the source eq class.  We don't know or
        // care whether it's in implicit or explicit form.
        auto eqci_bounds(members(i));

std::cout << "Src EQClass " << i << ": "; print_range(std::cout, eqci_bounds[0], eqci_bounds[1]); std::cout << std::endl;
        // Merge eq class i into eq class j
        std::vector<ix_t> eqcnew;
        std::set_union(
            eqcj.begin(), eqcj.end(), eqci_bounds[0], eqci_bounds[1],
            std::inserter(eqcnew, eqcnew.begin()));
        eqcj = std::move(eqcnew);

        // Delete eqclass i and forward to j
        eqclasses.erase(i);
        forwards[i] = j;

        // Return the new Equiv Class j
        return eqcj;
    }

};

// ----------------------------------------------------------
/** A graph with implicit 8-way neighbors based on DEM and used /
unused gridcells */
class D8Graph {
    // Maintain nodes of our graph as equivalence classes
    EQClasses eqclasses;

    // Maintain a DEM (imported from Python), giving us our neighbors
    double *dem;
    int const nj;
    int const ni;
    double nodata;             // dem==nodata ==> unused gridcell
    // Tells whether an EQ class is on the edge of the grid or adjacent to an unused cell
    std::vector<bool> edge;

    // Explicit neighbors for merged EQ classes
    std::unordered_map<ix_t, std::vector<ix_t>> neighborss;
    // Buffer used to return neighbors
    std::array<std::vector<int>, 2> _neighbors_rets;
    int reti = 0;    // Double buffering
    // ---------------------------------------------------------

    // Increments to get to neighbors
    // These need to be in sorted order...
    static const std::vector<std::array<int,2>> dneigh;

    /** Determines whether a gridcell is an edge cell, i.e. borders on
    an unused cell or grid edge.  This function is called a the
    beginning to build a lookup table, which is then modified as eq
    classes are merged. */
    bool is_edge(int j0, int i0)
    {
        // Look at neighboring nodes in 2D space
        for (auto &dn : dneigh) {
            // It's an edge if at edge of domain
            int const j1 = j0 + dn[0];
            int const i1 = i0 + dn[1];
            if ((j1<0) || (j1>=nj) || (i1<0) || (i1>ni)) return true;

            // It's an edge if neighbor is unused
            int const ji1 = j1*ni + i1;
            if (dem[ji1] == nodata) return true;
        }
        return false;
    }

public:
    D8Graph(double *_dem, int _nj, int _ni, double _nodata)
        : dem(_dem), nj(_nj), ni(_ni), nodata(_nodata)
    {

        // Initialize edge indicator
        edge.reserve(nj*ni);
        for (int j=0; j<nj; ++j) {
        for (int i=0; i<ni; ++i) {
            bool const ie = is_edge(j,i);
            edge.push_back(ie);
//            printf("is_edge[%d, %d] = %d\n", j, i, (int)ie);
        }}

    }

    size_t size() { return nj*ni; }

private:
    /** Obtain list of neighbors based on raster. */
    std::vector<ix_t> &d8_neighbors_list(int ji0, std::vector<ix_t> &ngh)
    {
        ngh.clear();

        // Identify neighbors based on the 2D raster.
        int const j0 = ji0 / ni;
        int const i0 = ji0 % ni;    // Probably compiles down to divmod

        // Look at neighboring nodes in 2D space
        for (auto &dn : dneigh) {

            // Avoid outrunning our domain
            int const j1 = j0 + dn[0];
            int const i1 = i0 + dn[1];
            if ((j1<0) || (j1>=nj) || (i1<0) || (i1>=ni)) continue;

            // Avoid "neighbor" gridcells that are unused
            int ji1 = j1*ni + i1;
            if (dem[ji1] == nodata) continue;

            // Follow forwrding for neighbors that have been merged
            // NOTE: This could result in non-unique neighbor lists being returned!
            ji1 = eqclasses.parent(ji1);

            // Add to our list of output
            ngh.push_back(ji1);
        }

        // Uniq-ify and return
        std::sort(ngh.begin(), ngh.end());
        ngh.erase(std::unique(ngh.begin(), ngh.end()), ngh.end());

        return ngh;
    }

public:
    /**
    expl:
        If set, then convert to expl format if not already.
    */
    std::vector<ix_t> &neighbors(int ji0, bool expl=false)
    {
        // Are neighbors represented explicitly?
        // If so, just lookup and return that list.
        auto ii(neighborss.find(ji0));
        if (ii != neighborss.end()) {
            return ii->second;
        }

        // Neighbor is not represented explicitly.
        // Construct the neighbor list.

        // Prepare output buffer
        reti = 1 - reti;    // swap double buffer
        auto &ngh(_neighbors_rets[reti]);
        ngh.clear();
        ngh.reserve(8);

        // Obtain explicit list of neighbors
        d8_neighbors_list(ji0, ngh);

        // We're done if we don't need to store it for later use.
        if (!expl) return ngh;

        // We DO need to store the explicit representation.
        ii = neighborss.insert(std::make_pair(ji0, std::move(ngh))).first;
        return ii->second;
    }

    /** Merge neighbor lists in prep for an eqclass merger of j <- i */
    std::vector<ix_t> &merge_neighbor_lists(ix_t j, ix_t i)
    {
        // Original neighbor lists
        std::vector<ix_t> &nghj(neighbors(j, true));
        std::vector<ix_t> &nghi(neighbors(i));

printf("********* Merging %d -> %d\n", i, j);
{
printf(" pre neighbors[%d]: ", j); for (auto ii(nghj.begin()); ii != nghj.end(); ++ii) printf(" %d", *ii); printf("\n");
printf(" pre neighbors[%d]: ", i); for (auto ii(nghi.begin()); ii != nghi.end(); ++ii) printf(" %d", *ii); printf("\n");
}

        // ------------------- Merge the lists
        std::vector<ix_t> ngh_joined;
        std::set_union(nghj.begin(), nghj.end(), nghi.begin(), nghi.end(),
            std::inserter(ngh_joined, ngh_joined.begin()));

printf("joined neighbors %d: ", j); for (auto ii(ngh_joined.begin()); ii != ngh_joined.end(); ++ii) printf(" %d", *ii); printf("\n");

        // --------------- Filter out i and j
        std::vector<ix_t> ngh_filtered;
        for (auto ii(ngh_joined.begin()); ii != ngh_joined.end(); ++ii) {
            if ((*ii != i) && (*ii != j)) ngh_filtered.push_back(*ii);
        }

        // Store back merged / filtered list
        nghj = std::move(ngh_filtered);

        // Delete neighbors list for i
        neighborss.erase(i);

        // ============== Replace i->j in neighbor lists of neighbors
        for (ix_t k : nghj) {
            std::vector<ix_t> &nghk(neighbors(k, true));
            for (auto kk(nghk.begin()); kk != nghk.end(); ++kk) {
                if (*kk == i) *kk = j;
            }

            // Uniquify
            std::sort(nghk.begin(), nghk.end());
            nghk.erase(std::unique(nghk.begin(), nghk.end()), nghk.end());
        }

{
auto &xnghj(neighbors(j));
printf(" post neighbors[%d]: ", j); for (auto ii(xnghj.begin()); ii != xnghj.end(); ++ii) printf(" %d", *ii); printf("\n");
}

        return nghj;
    }




    /** Returns merged {eqclass vector, neighbor vector} */
    std::array<std::vector<ix_t> *, 2> const merge(int j, int i)
    {
        // ----------- Merge neighbor lists
        std::vector<ix_t> &nghj(merge_neighbor_lists(j, i));

        // ----------- Maintain edge designation
        edge[j] = edge[j] || edge[i];


        // ----------- Merge underlying EQClasses
        std::vector<ix_t> &eqclassj(eqclasses.merge_eq(j,i));
        return {&eqclassj, &nghj};
    }


    /**
    max_sink_size:
        Don't merge sinks larger than this.
    */
    void fill_sinks(size_t max_sink_size)
    {

        for (int ix=0; ix<(int)size(); ++ix) {
            // Only look at primary node for each EQ class
            if (eqclasses.parent(ix) != ix) continue;

            // Progressively merge with neighbors
            for (;;) {

                // Edge nodes don't get merged, the unused gridcell
                // nextdoor is by definition a place we can flow to from this
                // gridcell.
                if (edge[ix]) break;

                // Find index of the neighbor with the lowest elevation in the dem
                // (that is small enough to merge)
                ix_t min_ix = -1;
                double min_elev = 1.e20;
                auto &ngh(neighbors(ix));
                for (auto kk(ngh.begin()); ; ++kk) {
                    if (kk == ngh.end()) break;
                    if (eqclasses.size(ix) + eqclasses.size(*kk) > max_sink_size) continue;
                    if (dem[*kk] < min_elev) {
                        min_ix = *kk;
                        min_elev = dem[min_ix];
                    }
                }
                if (min_ix == -1) break;    // No merge candidates with small number of cells

                //ix_t const min_ix = *std::min_element(ngh.begin(), ngh.end(),
                //    [this](int const ix0, int const ix1) { return dem[ix0] < dem[ix1]; });

                // This Equiv class is not a sink because it has an outflow to a neighbor
                if (dem[ix] > dem[min_ix]) break;

                // This EQ class IS a sink: merge with lowest neighbor
                std::array<ix_t, 2> sorted_ix(sorted(ix, min_ix));

                // Merge min_ix into ix, return neighbors of merged ix
//                std::array<std::vector<ix_t> *, 2> const merged(merge(sorted_ix[0], sorted_ix[1]));    // Merge into lower index always
                std::array<std::vector<ix_t> *, 2> const merged(merge(ix, min_ix));    // Merge into lower-elevation     index always
                auto &merged_eqclass(*merged[0]);    // Unpack results
                //auto &merged_neighbors(*merged[1]);

                // Set elevation for the EQ class accordingly
                dem[ix] = dem[min_ix];

                // Stop if we've gotten too large
                if (merged_eqclass.size() > max_sink_size) break;
            }
        }

#if 0
        // Look up all forwards on explicit eq classes
        // (and remove neighbors pointing to now-defunct EC's)
        for (auto ii(neighborss.begin()); ii != neighborss.end(); ++ii) {
            std::vector<ix_t> &neighbors(ii->second);
            for (auto jj(neighbors.begin()); jj < neighbors.end(); ++jj) {
                *jj = eqclasses.parent(*jj);
            }
            std::sort(neighbors.begin(), neighbors.end());
            neighbors.erase(std::unique(neighbors.begin(), neighbors.end()), neighbors.end());
        }
#endif


// ---------------------- Debugging
{
std::vector<ix_t> keys;
for (auto kv: neighborss) keys.push_back(kv.first);
std::sort(keys.begin(), keys.end());

for (auto key : keys) {
    std::vector<ix_t> &neighbors(neighborss[key]);
    printf("Neighbors of %d: ", key);
    print_range(std::cout, neighbors.begin(), neighbors.end());
    printf("\n");
}

printf("Filled DEM:\n"); print_raster(std::cout, dem, nj, ni);
}
// ----------------------

    }


    /** Construct the degree-1 neighbor relationship.  Represented as
    a 1D array by gridcell.  Gridcells in each EQ class are arranged
    in a linear fashion, so all of them are traversed in any graph
    search.
    neighbors1:  [nj*ni]
        Base of 1D array of gridcell neighbors.
        (Potentially this is a Numpy array.)
    */
    void to_neighbors1(npy_int *neighbors1)
    {
printf("CC1 %ld %ld\n", size(), sizeof(npy_int));
        // Initialize all to -1
        for (ix_t ix_i=0; ix_i<(ix_t)size(); ++ix_i) {
            neighbors1[ix_i] = -2;
        }

        // ix_i is the index of the "current" eq class
        for (ix_t ix_i=0; ix_i<(ix_t)size(); ++ix_i) {
            // Only consider lead gridcells of equivalence classes
            if ((dem[ix_i] != nodata) && (eqclasses.parent(ix_i) == ix_i)) {

                // ix_j is index of lowest neighboring eq class
                auto &ngh(neighbors(ix_i));

                ix_t ix_j = *std::min_element(ngh.begin(), ngh.end(),
                    [this](int const ix0, int const ix1) { return dem[ix0] < dem[ix1]; });

#if 0           // NOT POSSIBLE: Because neihbors and eq class are disjoint!!!!
                // If the lowest neighboring eq class is ourself, then
                // we are a sink.  Record no outbound neighbor.
                if (ix_i == ix_j) {
                    neighbors1[ix_i] = -1;
                    continue;
                }
#else
                // If the lowest neighboring eq class is higher than us, then we are a sink.
                // Record no outbound neighbor.  AVOID CYCLES IN THE GRAPH!
                if (dem[ix_j] > dem[ix_i]) {
                    neighbors1[ix_i] = -1;
                    continue;
                }
#endif

                // Now create graph link: ix_i -> ix_j
                // if ix_i is a compound eq class, link from the LARGEST gridcell in it
                // if ix_j is a compound eq class, link to the SMALLEST gridcell in it
                auto members_bounds(eqclasses.members(ix_i));
                ix_t max_member_i = *(members_bounds[1]-1);   // Largest in i
                ix_t min_member_j = eqclasses.min_member(ix_j);         // Smallest in j
                neighbors1[max_member_i] = min_member_j;

                // Create links *within* eq class i, from the min to
                // the max gridcell.  Any flow into eq class i will
                // enter at the min gridcell, then traverse all
                // portions of the eq class.
                for (auto ii(members_bounds[0]+1); ii<members_bounds[1]; ++ii) {
                    neighbors1[*(ii-1)] = *ii;
                }
                
            }
        }
printf("CC3\n");

    }
};

const std::vector<std::array<int,2>> D8Graph::dneigh = {
    {-1,-1}, {-1,0}, {-1,1},
    {0, -1},         {0, 1},
    {1,-1},  {1,0},  {1,1}};

// ====================================================================

/** Does a breadth-first-search of the neighbors1 graph starting from
some gridcells.

start_begin, start_end:
    begin and end iterators for starting gridcell indices
*/
std::unordered_set<ix_t> flood_fill(
    ix_t const *neighbors1,
    // int nj, int ni,     // Not needed, except for bounds checking on neighbors1 lookup
    ix_t const *start_begin, ix_t const *start_end)
{
    // State of breadth-first-search
    std::unordered_set<ix_t> seen;
    std::vector<ix_t> cur(start_begin, start_end);
    std::vector<ix_t> neighbors;   // can have duplicates
    for (;;) {
        // Determine neighbor values of each current node
        // Add to our vector of neighbors if we haven't seen it yet.
        // Also add to our seen set (most efficient this way)
        for (ix_t ix : cur) {
            ix_t ngh = neighbors1[ix];
            if (ngh < 0) continue;    // No neighbor for this node

            auto ii(seen.find(ngh));
            if (ii == seen.end()) {
                neighbors.push_back(ngh);
                seen.insert(ngh);
            }
        }

        // Exit condition: no more neighbors!
        if (neighbors.size() == 0) break;

        // neighbors becomes cur
        // O(1) time see: https://www.geeksforgeeks.org/difference-between-stdswap-and-stdvectorswap/
        std::swap(cur, neighbors);
        neighbors.clear();
    }

    return seen;
}



// =========================================================================
// Functions in the Python interface

static char const *d8graph_neighbor_graph_docstring = 
R"XXX(Produces the single-neighbor graph from a DEM; a degree-1 graph
providing the D8 routing from each gridcell to the next; with the
following caveats:

  1. Interior sinks are filled by combining cells into *equivalence classes*.

  2. The graph routes into the lowest numbered cell in each
     equivalence class, and out the highest number, while going
     through all intervening members.  This ensures that flow entering
     the equivalence class will reach all members.  (Corner case: this
     will not necessarily be true if the flow begans in the middle of
     an equivalence class).

  3. The out-degree of the graph can be at most 1.  If two neighboring
     cells are equally low, then one is chosen.

  4. 

dem: np.array(nj, ni, dtype='d')
    The input digital elevation model
nodata: float
    dem takes this value for unused cells (eg ocean)
max_sink_size: int
    Maximum number of cells to join together in equivalence classes

Returns: neighbors1=np.array(nj, ni, dtype=np.int32)
    Representation of the degree-1 graph
    neighbors1[j,i] = 1D index of the downstream node.
       ...or -1 if cell (j,i) is unused, or there is no downstream node.
)XXX";
static PyObject* d8graph_neighbor_graph(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // Input arrays
    PyArrayObject *dem;
    double nodata;
    int max_sink_size = 10;

    // Parse args and kwargs
    static char const *kwlist[] = {
        "dem", "nodata",         // *args,
        "max_sink_size",    // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!d|i",
        (char **)kwlist,
        &PyArray_Type, &dem, &nodata,
        &max_sink_size
        )) return NULL;

    // -----------------------------------------
    // Typecheck
    // Check storage
    if (!PyArray_ISCARRAY_RO(dem)) {
        PyErr_SetString(PyExc_TypeError, "Input dem must be C-style, contiguous array.");
        return NULL;
    }

    // Check type
    if (PyArray_DESCR(dem)->type_num != NPY_DOUBLE) {
        PyErr_SetString(PyExc_TypeError, "Input dem must have type double");
        return NULL;
    }

    // Check rank
    if (PyArray_NDIM(dem) != 2) {
        PyErr_SetString(PyExc_TypeError, "Input dem must have rank 2");
        return NULL;
    }

    // -----------------------------------------
    // Create output array (uninitialized)
    auto const ni = PyArray_DIM(dem,1);
    npy_intp const strides[] = {(npy_intp)(sizeof(int) * ni), (npy_intp)sizeof(int)};
    PyArrayObject *neighbors1 = (PyArrayObject*) PyArray_NewFromDescr(
        &PyArray_Type, 
        PyArray_DescrFromType(NPY_INT32),             // dtype='i'
        2,                                          // rank 2
        PyArray_DIMS(dem), strides,    // Same shape as DEM
        NULL,        // Allocate new memory
        // PyArray_FLAGS(dem), ...
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);

    // ========================================================
    // Do the computation

    D8Graph d8g((double *)PyArray_GETPTR2(dem,0,0), PyArray_DIM(dem,0), PyArray_DIM(dem,1), nodata);

    printf("Filling sinks...\n");
    d8g.fill_sinks(max_sink_size);

    printf("Converting to neighbors1 format\n");

    printf("neighbors1 dims: %ld %ld\n", PyArray_DIM(neighbors1,0), PyArray_DIM(neighbors1,1));
    d8g.to_neighbors1((npy_int *)PyArray_GETPTR2(neighbors1,0,0));

printf("DD1\n");
    // ========================================================
    return (PyObject *)neighbors1;
}
// ----------------------------------------------------------------------------------------
static bool ff_check_input(PyArrayObject *dem, char const *name)
{
    char msg[256];

    // Check storage
    if (!PyArray_ISCARRAY_RO(dem)) {
        snprintf(msg, 256, "Parameter %s must be C-style, contiguous array.", name);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check type
    if (PyArray_DESCR(dem)->type_num != NPY_INT32) {
        snprintf(msg, 256, "Parameter %s must have dtype int.", name);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check rank
    if (PyArray_NDIM(dem) != 1) {
        snprintf(msg, 256, "Parameter %s must have rank 1", name);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }
    return true;
}
// ----------------------------------------------------------------------------------------
static char const *d8graph_flood_fill_docstring =
R"(Given indices of starting nodes, "rolls a marble downhill."  Returns
j (N-S) and i (E-W) gridcell coordinates of all nodes touched.

neighbors1: np.array(nj, ni, dtype=np.int32)
    Representation of the degree-1 graph
    neighbors1[j,i] = 1D index of the downstream node.
       ...or -1 if cell (j,i) is unused, or there is no downstream node.

start: np.array(m, dtype='i')
    1D index of starting gridcells (eg burned from a PRA polygon)
    (for m starting nodes)

Returns: (jj, ii)
    jj: np.array(n, dtype='i')
        2D N-S index of nodes reached
    ii: np.array(n, dtype='i')
        2D E-W index of nodes reached
)";

static PyObject* d8graph_flood_fill(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // ======================== Parse Python Input
    // Input arrays
    PyArrayObject *neighbors1;
    PyArrayObject *start;
    int max_sink_size;

    // Parse args and kwargs
    static char const *kwlist[] = {
        "neighbors1", "start",         // *args,
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!O!",
        (char **)kwlist,
        &PyArray_Type, &neighbors1,
        &PyArray_Type, &start,
        &max_sink_size
        )) return NULL;

    // ----------- Typecheck input arrays
    if (!ff_check_input(neighbors1, "neighbors1")) return NULL;
    if (!ff_check_input(start, "start")) return NULL;

    // ============================ Run the Core Computation
    // Run the flood fill algorithm, result in a set of 1D indices
    std::unordered_set<ix_t> seen(
        flood_fill(
            (ix_t *)PyArray_GETPTR2(neighbors1,0,0),
            // PyArray_DIM(neighbors1,0), PyArray_DIM(neighbors1,1),    // Not needed
            (ix_t *)PyArray_GETPTR1(start, 0),
            (ix_t *)PyArray_GETPTR1(start, PyArray_DIM(start,0))));

    // ============================= Construct Python Output
    // Allocate output arrays
    npy_intp out_dims[] = {(npy_intp) seen.size()};
    npy_intp out_strides[] = {(npy_intp) sizeof(int)};

    // Allocate jj and ii output arrays
    std::array<PyArrayObject *, 2> jjii;
    for (int k=0; k<2; ++k) {
        jjii[k] = (PyArrayObject*) PyArray_NewFromDescr(&PyArray_Type, 
            PyArray_DescrFromType(NPY_INT32),             // dtype='i'
            1,                                          // rank 1
            out_dims, out_strides,
            NULL,        // Allocate new memory
            // PyArray_FLAGS(dem), ...
            NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);
    }


    // Convert the set of 1D indices to (j,i) index pairs
    // int const nj = PyArray_DIM(neighbors1,0);
    int const ni = PyArray_DIM(neighbors1,1);

    for (ix_t ix : seen) {
        int const j = ix / ni;
        int const i = ix % ni;    // Probably compiles down to divmod

        *(npy_int *)PyArray_GETPTR1(jjii[0], ix) = j;
        *(npy_int *)PyArray_GETPTR1(jjii[1], ix) = i;
    }


    // Return a tuple of the output arrays we created.
    // https://stackoverflow.com/questions/3498210/returning-a-tuple-of-multipe-objects-in-python-c-api
    PyObject *ret = PyTuple_Pack(2, jjii[0], jjii[1]);
    return ret;

}

// ============================================================
// Random other Python C Extension Stuff
static PyMethodDef D8GraphMethods[] = {
    {"neighbor_graph",
        (PyCFunction)d8graph_neighbor_graph,
        METH_VARARGS | METH_KEYWORDS, d8graph_neighbor_graph_docstring},

    {"flood_fill",
        (PyCFunction)d8graph_flood_fill,
        METH_VARARGS | METH_KEYWORDS, d8graph_flood_fill_docstring},

    // Sentinel
    {NULL, NULL, 0, NULL}
};


/* This initiates the module using the above definitions. */
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "dggs.d8graph",    // Name of module
    module_docstring,    // Per-module docstring
    -1,  /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    D8GraphMethods,    // Functions
    NULL,
    NULL,
    NULL,
    NULL
};

extern "C" void handler(int sig) {
  void *array[10];
  size_t size;

  // get void*'s for all entries on the stack
  size = backtrace(array, 10);

  // print out all the frames to stderr
  fprintf(stderr, "Error: signal %d:\n", sig);
  backtrace_symbols_fd(array, size, STDERR_FILENO);
  exit(1);
}


PyMODINIT_FUNC PyInit_d8graph(void)
{
    // TODO: Disable this in production so it doesn't interfere with
    // Python interpreter in general.
    signal(SIGSEGV, handler);   // install our handler

    import_array();    // Needed for Numpy

    return PyModule_Create(&moduledef);
}

