#define PY_SSIZE_T_CLEAN
#include <Python.h>
//#include "structmember.h"    // Map C struct members to Python attributes
#include <numeric>    // iota
// https://docs.python.org/3.9/extending/newtypes_tutorial.html

typedef int ix_t;

class D8Node {
public:
    std::unorderd_set<ix_t> eqclass;    // All gridcells at same elevation as this one (including self)
    std::unordered_set<ix_t> neighbors;    // Neighbors of this cell (disjoint from eqclass).  Does NOT include self!

    // Initializes a node to a single gridcell
    D8Node(i, std::vector<int> const &_neighbors)
        : eq_class{i}, neighbors(_neighbors.begin(), _neighbors.end())
    {}
};

class D8Graph {
public:
    //PyArrayObject *dem;        // double[nj,ni]
    double *dem;      // double[nji=nj*ni]
    int nj, ni;
    double nodata;             // dem==nodata ==> unused gridcell
    std::vector<ix_t> forwards;    // Cell this has been merged into
    std::vector<bool> edge;

    // ------- For EQ classes that are combined gridcells
    std::unordered_map<ix_t,D8Node> nodes;

    // Buffer used to return neighbors
    std::vector<int> _neighbors;

    // Increments to get to neighbors
    static const std::vector<std::array<int,2>> dneigh {
        {-1,-1}, {-1,0}, {-1,1},
        {0, -1},       , {0, 1},
        {1,-1},  {1,0},  {1,1}};

private:
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
            if (dem[ji1] == nodata) continue;
    }

public:
    D8Graph(double *_dem, int _nj, int _ni, double _nodata)
        : dem(_dem), nj(_nj), ni(_ni), nodata(_nodata)
    {
        // Initialize forward[i] == i
        const int nji = nj*ni;
        forwards.reserve(nji);
        for (int ji=0; ji<nji; ++ji) forwards.push_back(ji);

        // Initialize edge indicator
        edge.reserve(nji);
        for (int j=0; i<nj; ++j) {
        for (int i=0; i<ni; ++i) {
            edge.push_back(is_edge(j,i));
        }}

        // Reserve output vector for sharing neighbors
        _neighbors.reserve(32);
    }

    auto size() { return forwards.size(); }

    std::vector<int> const &neighbors(int ji0)
    {
        // Follow forwards
        ji0 = forwards[ji];

        // Is this EQ class a result of a merger?
        _neighbors.clear();
        auto ii(nodes.find(ji0));
        if (ii == nodes.end()) {
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
                ji1 = forwards[ji1];

                // Add to our list of output
                _neighbors.push_back(ji1);
            }
        } else {
            // -------------------------------------------
            // This node has been merged, its neighbors are stored explicitly
            auto &node(ii->second);
            for (auto ngh : ii->second) _neighbors.push_back(ngh);
        }
        return _neighbors;
    }

    /** Converts node i to an equivalence class, if it is not already. */
    D8Node &to_node(int i)
    {
        // Return it if it's already there
        auto ii(nodes.find(i));
        if (ii == nodes.end()) {
            // Insert a blank node
            ii = nodes.insert(ii, D8Node(i, neighbors(i)));

        }
        return ii->second;
    }

    /** Merge eq class i into j
    i:
        Index of source equivalence class
    j:
        Index of destination equivalence class
    */
    D8Node &merge(int j, int i)
    {
        // The destination will HAVE to be in node form
        auto &nodej(to_node(j))

        // For now, convert the source to node form (if not already),
        // and then delete it.
        // TODO: If this is too slow, implement the merge directly from original form.
        auto &nodei(to_node(i));

        // Merge the two nodes
        forwards[i] = j;
        nodej.eqclass.insert(nodei.eqclass.begin(), nodei.eqclass.end());
        nodej.neighbors.insert(nodei.neighbors.begin(), nodei.neighbors.end());

        // Maintain invariant: eqclass and neighbors are disjoint!
        for (auto jj=nodej.neighbors.begin(); jj != nodej.neighbors.end(); ) {
            // https://stackoverflow.com/questions/2874441/deleting-elements-from-stdset-while-iterating
            if (nodej.eqclass.find(*jj) != nodej.eqclass.end()) {
                nodej.neighbors.erase(jj++);    // post-increment to avoid invalidating iterator
            } else {
                ++jj;
            }
        }

        // Maintain edge designation
        edge[j] |= edge[i];

        // Return reference to destination node
        return nodej;
    }

    /**
    max_sink_size:
        Don't merge sinks larger than this.
    */
    void fill_sinks(size_t max_sink_size)
    {

        for (int ix=0; ix<(int)size(); ++ix) {
            // Only look at primary node for each EQ class
            if (forwards[ix] != ix) continue;

            // Progressively merge with neighbors
            for (;;) {

                // Edge nodes don't get merged, the unused gridcell
                // nextdoor is by definition a place we can flow to from this
                // gridcell.
                if (edge[ix]) break;

                // Find index of the neighbor with the lowest elevation in the dem
                auto &ngh(neighbors(ix));
                ix_t min_ix = *std::min_element(ngh.begin(), ngh.end(),
                    [](int const ix0, int const ix1) { return dem[ix0] < dem[ix1] });

                // This Equiv class is not a sink because it has an outflow to a neighbor
                if (dem[ix] > dem[min_ix]) break;

                // This EQ class IS a sink: merge with lowest neighbor
                printf("Merging %d -> %d\n", min_ix, ix);
                auto &node_ix(merge(ix, min_ix));    // Merge min_ix into ix

                // Set elevation for the EQ class accordingly
                dem[ix] = dem[min_ix];

                // Stop if we've gotten too large
                if (node_ix.eqclass.size() > max_sink_size) break;
            }
        }

        // Look up all forwards (and remove neighbors pointing to now-defunct EC's)
        for (auto ii(nodes.begin()); ii != nodes.end(); ++ii) {
            auto &node(ii->second);
            for (auto jj(node.neighbors.begin()); jj < node.neighbors.end(); ++jj) {
                *jj = forwards[*jj];
            }
        }
    }

    /** Returns: vector<int>
        ret[i] =
            If gridcell i is unused: -1
            If gridcell i has been merged into equiv class j != i: -1
            else:
                 Index of lowest neighbor of eq class i
                 (including i as a neighbor)
    */
    std::vector<int> to_single_neighbors()
    {
    }

};

// =========================================================================
static void
D8Graph_dealloc(D8GraphObject *self)
{
    Py_XDECREF(self->first);
    Py_XDECREF(self->last);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static PyObject *
D8Graph_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    D8GraphObject *self;
    self = (D8GraphObject *) type->tp_alloc(type, 0);
    new(self) D8GraphObject();    // Placement new

    if (self != NULL) {
        self->first = PyUnicode_FromString("");
        if (self->first == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->last = PyUnicode_FromString("");
        if (self->last == NULL) {
            Py_DECREF(self);
            return NULL;
        }
        self->number = 0;
    }
    return (PyObject *) self;
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
