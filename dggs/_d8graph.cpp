#define PY_SSIZE_T_CLEAN
#include <Python.h>
//#include "structmember.h"    // Map C struct members to Python attributes
#include <numeric>    // iota
// https://docs.python.org/3.9/extending/newtypes_tutorial.html

typedef int ix_t;

/** A memory-efficient version of map<KeyT,ValT> in two vectors. */
template<class KeyT, class ValT>
struct PackedMap {
    std::vector<KeyT> keys;    // TODO: Use Numpy array here, because this is used to/from Python
    std::vector<ValT> values;
};

/** A memory-efficient version of map<KeyT, vector<ValT>> in three vectors */
template<class KeyT, class ValT, IndexT>
struct PackedMapVectors {
    std::vector<KeyT> keys;
    std::vector<IndexT> starts {0};    // Index into values; keys.size+1
    std::vector<ValT> values;

};

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
            forwards[_forwards.keys[k]] = _values[k];
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
    std::array<std::vector<ix_t>::iterator, 2> members(int eqi) const
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
        if (ii != forwards.end()) return *ii;
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
    std::vector<ix_t> &merge(int j, int i)
    {
        // Access contents of the destination eq class,
        // converting to explicit form if needed.
        auto eqcj_it(eqclasses.find(j));
        if (eqcj_it == eqclasses.end()) {
            eqcj_it = eqclasses.insert(eqcj_it, std::vector<ix_t>{i});
        }
        std::vector<ix_t> &eqcj(eqcj_it->second);

        // Access contents of the source eq class.  We don't know or
        // care whether it's in implicit or explicit form.
        auto eqci_bounds(members(i));

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
    std::vector<int> _neighbors_ret;
    // ---------------------------------------------------------

    // Increments to get to neighbors
    // These need to be in sorted order...
    static const std::vector<std::array<int,2>> dneigh {
        {-1,-1}, {-1,0}, {-1,1},
        {0, -1},       , {0, 1},
        {1,-1},  {1,0},  {1,1}};

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
        edge.reserve(nji);
        for (int j=0; i<nj; ++j) {
        for (int i=0; i<ni; ++i) {
            edge.push_back(is_edge(j,i));
        }}

        // Reserve output vector for sharing neighbors
        _neighbors_ret.reserve(32);
    }

    size_t size() { return nj*ni; }

    std::array<std::vector<ix_t>::iterator, 2> const &neighbors(int ji0)
    {
        // Follow forwards
        ji0 = eqclasses.parent(ji0);

        // Is this EQ class a result of a merger?
        _neighbors_ret.clear();
        auto ii(neighborss.find(ji0));
        if (ii != neighborss.end())
            // -------------------------------------------
            // This node has been merged, its neighbors are stored explicitly
            std::vector<ix_t> &neighs(ii->second);
            return {neighs.begin(), neigs.end()}
        }

        // -------------------------------------------
        // This node has not been merged; identify its neighbors
        // based on the 2D raster
        int const j0 = ji0 / ni;
        int const i0 = ji0 % ni;    // Probably compiles down to divmod

        // Look at neighboring nodes in 2D space
        for (auto &dn : dneigh) {

            // Avoid outrunning our domain
            int const j1 = j0 + dn[0];
            int const i1 = i0 + dn[1];
            if ((j1<0) || (j1>=nj) || (i1<0) || (i1>ni)) contine;

            // Avoid "neighbor" gridcells that are unused
            int const ji1 = j1*ni + i1;
            if (dem[ji1] == nodata) continue;

            // Follow forwrding for neighbors that have been merged
            ji1 = eqclasses.parent[ji1];

            // Add to our list of output
            _neighbors_ret.push_back(ji1);
            return {_neighbors_ret.begin(), _neighbors_ret.end()};
        }
    }

    /** Returns merged {eqclass vector, neighbor vector} */
    std::array<std::vector<ix_t>*, 2> &merge(int j, int i)
    {
        // -------- Merge equivalence classes
        auto &eqclassj(eqclasses.merge(j,i));

        // -------- Merge neighbors
        // Access contents of the destination neighbors,
        // converting to explicit form if needed.
        auto nghj_it(neighborss.find(j));
        if (nghj_it == neighborss.end()) {
            // Initialize with explicit list of neighbors
            auto neighs_bounds(neighbors(i));
            nghj_it = neighborss.insert(
                nghj_it,
                std::vector<ix_t>(neighs_bounds[0], neighs_bounds[1]));
        }
        std::vector<ix_t> &nghj(nghj_it->second);

        // Access contents of the source eq class.  We don't know or
        // care whether it's in implicit or explicit form.
        auto nghi_bounds(members(i));

        // Copy neighbors of i into neighbors of j
        std::vector<ix_t> nghnew;
        std::set_union(
            nghj.begin(), nghj.end(), nghi_bounds[0], nghi_bounds[1],
            std::inserter(nghnew, nghnew.begin()));
        //std::sort(nghnew.begin(), nghnew.end());    // not needed

        // ------ Maintain invariant: eqclass and neighbors are disjoint!
        auto eqc_bounds(eqclasses.members(j));
        std::vector<ix_t> nghnew2;
        std::set_difference(
            nghnew.begin(), nghnew.end(),    // Copy these
            eqc_bounds[0], eqc_bounds[1],    // As long as they are not in here
            std::insert(nghnew2, nghnew2.begin()));
        nghj = std::move(nghnew2);


        // ----------- Maintain edge designation
        edge[j] |= edge[i];

        return {&eqclassj, nghj};
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
                auto ngh_bounds(neighbors(ix));
                ix_t min_ix = *std::min_element(ngh_bounds[0], ngh_bounds[1],
                    [](int const ix0, int const ix1) { return dem[ix0] < dem[ix1] });

                // This Equiv class is not a sink because it has an outflow to a neighbor
                if (dem[ix] > dem[min_ix]) break;

                // This EQ class IS a sink: merge with lowest neighbor
                printf("Merging %d -> %d\n", min_ix, ix);
                // Merge min_ix into ix, return neighbors of merged ix
                auto &merged(merge(ix, min_ix));
                auto &merged_eqclass(*merged[0]);    // Unpack results
                //auto &merged_neighbors(*merged[1]);

                // Set elevation for the EQ class accordingly
                dem[ix] = dem[min_ix];

                // Stop if we've gotten too large
                if (merged_eqclass.size() > max_sink_size) break;
            }
        }

        // Look up all forwards on explicit eq classes
        // (and remove neighbors pointing to now-defunct EC's)
        for (auto ii(neighborss.begin()); ii != neighborss.end(); ++ii) {
            std::vector<ix_t> &neighbors(ii->second);
            for (auto jj(neighbors.begin()); jj < neighbors.end(); ++jj) {
                *jj = eqclasses.parent(*jj);
            }
        }
    }


    /** Construct the degree-1 neighbor relationship.  Represented as
    a 1D array by gridcell.  Gridcells in each EQ class are arranged
    in a linear fashion, so all of them are traversed in any graph
    search.
    neighbors1:  [nj*ni]
        Base of 1D array of gridcell neighbors.
        (Potentially this is a Numpy array.)
    */
    void to_neighbors1(double *neighbors1)
    {
        // Initialize all to -1
        for (ix_t ix_i=0; ix_i<(ix_t)size(); ++ix_i)
            neighbors1[ix_i] = -1;

        // ix_i is the index of the "current" eq class
        for (ix_t ix_i=0; ix_i<(ix_t)size(); ++ix_i) {
            // Only consider lead gridcells of equivalence classes
            if ((dem[ix_i] != nodata) && (parent(ix_i) == ix_i)) {

                // ix_j is index of lowest neighboring eq class
                auto ngh_bounds(neighbors(ix_i));
                ix_t ix_j = *std::min_element(ngh_bounds[0], ngh_bounds[1],
                    [](int const ix0, int const ix1) { return dem[ix0] < dem[ix1] });

                // If the lowest neighboring eq class is ourself, then
                // we are a sink.  Record no outbound neighbor.
                if (ix_i == ix_j) {
                    neighbors1[ix_i] = -1;
                    continue;
                }


                // Now create graph link: ix_i -> ix_j
                // if ix_i is a compound eq class, link from the LARGEST gridcell in it
                // if ix_j is a compound eq class, link to the SMALLEST gridcell in it
                auto members_i_bounds(members(ix_i));
                ix_t max_member_i = *(members_bounds[1]-1);   // Largest in i
                ix_t min_member_j = min_member(ix_j);         // Smallest in j
                neighbors1[max_member_i] = min_member_j;

                // Create links *within* eq class i, from the min to
                // the max gridcell.  Any flow into eq class i will
                // enter at the min gridcell, then traverse all
                // portions of the eq class.
                for (auto ii(members_bounds[0])+1; ii<members_bounds[1]; ++ii)
                    neighbors1[*(ii-1)] = *ii;
                
            }
        }
        return neighbors1;

    }
};

/** Does a breadth-first-search of the neighbor1 graph starting from
some gridcells.

start_begin, start_end:
    begin and end iterators for starting gridcell indices
*/
std::unordered_set<ix_t> flood_fill(
    ix_t const *neighbor1,
    // int nj, int ni,     // Not needed, except for bounds checking on neighbor1 lookup
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
            ix_t ngh = neighbor1[ix];
            if (ngh < 0) continue;    // No neighbor for this node

            auto ii(seen.find(ngh));
            if (ii == seen.end()) {
                neighbors.push_back(ngh);
                seen.insert(ngh):
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
R"Produces the single-neighbor graph from a DEM; a degree-1 graph
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

Returns: neighbor1=np.array(nj, ni, dtype=np.int32)
    Representation of the degree-1 graph
    neighbor1[j,i] = 1D index of the downstream node.
       ...or -1 if cell (j,i) is unused, or there is no downstream node.
";
static PyObject* d8graph_neighbor_graph(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // Input arrays
    PyArrayObject *dem;
    double nodata;
    int max_sink_size = 10;

    // Parse args and kwargs
    static char *kwlist[] = {
        "dem", "nodata",         // *args,
        "max_sink_size",    // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!d|i",
        kwlist,
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
    PyArrayObject *neighbor1 = (PyArrayObject *)PyArray_NewLikeArray(
        dem, NPY_ANYORDER, NULL, 0);

    PyArrayObject *neighbor1 = (PyArrayObject*) PyArray_NewFromDescr(
        &PyArray_Type, 
        PyArray_DescrFromType(NPY_INT),             // dtype='i'
        2,                                          // rank 2
        PyArray_DIMS(dem), PyArray_STRIDES(dem),    // Same shape as DEM
        NULL,        // Allocate new memory
        // PyArray_FLAGS(dem), ...
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);

    // ========================================================
    // Do the computation

    D8Graph d8g((double *)PyArray_GETPTR2(dem,0,0), PyArray_DIM(dem,0), PyArray_DIM(dem,1), nodata);

    printf("Filling sinks...\n");
    d8g.fill_sinks(max_sink_size);

    printf("Converting to neighbors1 format\n");
    d8g.to_neighbors1(PyArray_GETPTR(neighbors1,0,0));

    // ========================================================
    return neighbor1;
}
// ----------------------------------------------------------------------------------------
static bool ff_check_input(PyArrayObject *arr, char const *name)
{
    char msg[256];

    // Check storage
    if (!PyArray_ISCARRAY_RO(dem)) {
        snprintf(msg, 256, "Parameter %s must be C-style, contiguous array.", name);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check type
    if (PyArray_DESCR(dem)->type_num != NPY_INT) {
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

neighbor1: np.array(nj, ni, dtype=np.int32)
    Representation of the degree-1 graph
    neighbor1[j,i] = 1D index of the downstream node.
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
    PyArrayObject *neighbor1;
    PyArrayObject *start;

    // Parse args and kwargs
    static char *kwlist[] = {
        "neighbor1", "start",         // *args,
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!O!",
        kwlist,
        &PyArray_Type, &neighbor1,
        &PyArray_Type, &start,
        &max_sink_size
        )) return NULL;

    // ----------- Typecheck input arrays
    if (!ff_check_input(neighbor1, "neighbor1") return NULL;
    if (!ff_check_input(start, "start") return NULL;

    // ============================ Run the Core Computation
    // Run the flood fill algorithm, result in a set of 1D indices
    std::unordered_set<ix_t> seen(
        flood_fill(
            (ix_t *)PyArray_GETPTR2(neighbor1,0,0),
            // PyArray_DIM(neighbor1,0), PyArray_DIM(neighbor1,1),    // Not needed
            (ix_t *)PyArray_GETPTR1(start, 0),
            (ix_t *)PyArray_GETPTR1(start, PyArray_DIM(start,0))));

    // ============================= Construct Python Output
    // Allocate output arrays
    static npy_intp out_dims[] = {seen.size()};
    static npy_intp out_strides[] = {sizeof(int)};

    // Allocate jj and ii output arrays
    std::array<PyArrayObject *, 2> jjii;
    for (int k=0; k<2; ++k) {
        jjii[k] = (PyArrayObject*) PyArray_NewFromDescr(&PyArray_Type, 
            PyArray_DescrFromType(NPY_INT),             // dtype='i'
            1,                                          // rank 1
            out_dims, out_strides,
            NULL,        // Allocate new memory
            // PyArray_FLAGS(dem), ...
            NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);
    }


    // Convert the set of 1D indices to (j,i) index pairs
    // int const nj = PyArray_DIM(neighbor1,0);
    int const ni = PyArray_DIM(neighbor1,1);

    for (ix_t ix : seen) {
        int const j = ix / ni;
        int const i = ix % ni;    // Probably compiles down to divmod

        jjii[0].push_back(j);
        jjii[1].push_back(i);
    }


    // Return a tuple of the output arrays we created.
    // https://stackoverflow.com/questions/3498210/returning-a-tuple-of-multipe-objects-in-python-c-api
    PyObject *ret = PyTuple_Pack(2, jj, ii);
    return ret;

}

// ============================================================
// Random other Python C Extension Stuff
static PyMethodDef D8graphMethods[] = {
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
    "dggs._d8graph",    // Name of module
    module_docstring,    // Per-module docstring
    -1,  /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    D8GraphMethods,    // Functions
    NULL,
    NULL,
    NULL,
    NULL
};

extern "C"
PyMODINIT_FUNC PyInit_d8graph(void)
{
    import_array();    // Needed for Numpy

    return PyModule_Create(&moduledef);
}

