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

// =========================================================================
// Python Interface Stuff

typedef struct {
    PyObject_HEAD
    std::unique_ptr<D8GraphObject> cobj;
} D8GraphObject;


static void
D8Graph_dealloc(D8GraphObject *self)
{
    self->cobj.reset();    // Delete allocated C++ object
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static int
D8Graph_init(D8GraphObject *self, PyObject *args, PyObject *kwds)
{




    static char *kwlist[] = {"first", "last", "number", NULL};
    PyObject *first = NULL, *last = NULL, *tmp;

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|OOi", kwlist,
                                     &first, &last,
                                     &self->number))
        return -1;

    if (first) {
        tmp = self->first;
        Py_INCREF(first);
        self->first = first;
        Py_XDECREF(tmp);
    }
    if (last) {
        tmp = self->last;
        Py_INCREF(last);
        self->last = last;
        Py_XDECREF(tmp);
    }
    return 0;



    // Properly construct the C++ object(s) in the D8GraphObject struct
    // (which was allocated by Python without proper construction)
    // Use placement new here...
    new(self->cobj) std::unique_ptr<D8GraphObject>(
        new D8GraphObject(...));


}

static PyMemberDef D8Graph_members[] = {
    {"first", T_OBJECT_EX, offsetof(D8GraphObject, first), 0,
     "first name"},
    {"last", T_OBJECT_EX, offsetof(D8GraphObject, last), 0,
     "last name"},
    {"number", T_INT, offsetof(D8GraphObject, number), 0,
     "d8graph number"},
    {NULL}  /* Sentinel */
};

static PyObject *
D8Graph_name(D8GraphObject *self, PyObject *Py_UNUSED(ignored))
{
    if (self->first == NULL) {
        PyErr_SetString(PyExc_AttributeError, "first");
        return NULL;
    }
    if (self->last == NULL) {
        PyErr_SetString(PyExc_AttributeError, "last");
        return NULL;
    }
    return PyUnicode_FromFormat("%S %S", self->first, self->last);
}

static PyMethodDef D8Graph_methods[] = {
    {"name", (PyCFunction) D8Graph_name, METH_NOARGS,
     "Return the name, combining the first and last name"
    },
    {NULL}  /* Sentinel */
};

static PyTypeObject D8GraphType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "dggs.d8graph.D8Graph",
    .tp_doc = PyDoc_STR("D8Graph objects"),
    .tp_basicsize = sizeof(D8GraphObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,    // BASETYPE=available for subclassing
    .tp_new = D8Graph_new,
    .tp_init = (initproc) D8Graph_init,
    .tp_dealloc = (destructor) D8Graph_dealloc,
    .tp_members = D8Graph_members,
    .tp_methods = D8Graph_methods,
};

static PyModuleDef d8graph_module = {
    PyModuleDef_HEAD_INIT,
    .m_name = "dggs.d8graph",
    .m_doc = "Example module that creates an extension type.",
    .m_size = -1,
};

PyMODINIT_FUNC
PyInit_d8graph(void)
{
    PyObject *m;
    if (PyType_Ready(&D8GraphType) < 0)
        return NULL;

    m = PyModule_Create(&d8graph_module);
    if (m == NULL)
        return NULL;

    Py_INCREF(&D8GraphType);
    if (PyModule_AddObject(m, "D8Graph", (PyObject *) &D8GraphType) < 0) {
        Py_DECREF(&D8GraphType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
