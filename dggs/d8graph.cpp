#define PY_SSIZE_T_CLEAN
#include <Python.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>
//#include "structmember.h"    // Map C struct members to Python attributes
#include <numeric>    // iota
// https://docs.python.org/3.9/extending/newtypes_tutorial.html
#include <set>
#include <map>
#include <unordered_set>
#include <unordered_map>
#include <vector>
#include <array>
#include <iostream>
#include <iomanip>
#include <iterator>
#include <cmath>
#include <cwchar>

// https://stackoverflow.com/questions/77005/how-to-automatically-generate-a-stacktrace-when-my-program-crashes
#include <cstdio>
#include <execinfo.h>
#include <csignal>
#include <cstdlib>
//#include <cunistd>
#include <dggs/chull.hpp>
#include <dggs/mbr.hpp>


using namespace dggs;

// #define OPTIMIZE_D8        // Adds complication, only speeds things up a little bit.

static char module_docstring[] = 
"D8Graph 1.0.0 extension module computes graphs and flow paths in digital elevation models.";

typedef float dem_t;    // The Digital Elevation Model is single prceision
typedef int ix_t;


// ----------------------------------------------------------------------------------------
/** Simple allocation of 1D Numpy array
shape0:
    Length of array
typenum:
    Type to allocation, eg NPY_INT, NPY_DOUBLE
    https://numpy.org/devdocs/reference/c-api/dtype.html#c.NPY_TYPES
*/
PyArrayObject *np_new_1d(npy_intp shape0, int typenum)
{
    PyArray_Descr *tdescr = PyArray_DescrFromType(typenum);
    npy_intp dims[] = {shape0};
    npy_intp strides[] = {tdescr->elsize};
    return (PyArrayObject*) PyArray_NewFromDescr(&PyArray_Type, 
        tdescr, 1,    // rank 1
        dims, strides,
        NULL,        // Allocate new memory
        // PyArray_FLAGS(dem), ...
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);
}
// ----------------------------------------------------------------------------------------
static bool ff_check_input_int(PyArrayObject *dem, char const *name, int rank)
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
    if (PyArray_NDIM(dem) != rank) {
        snprintf(msg, 256, "Parameter %s must have rank %d", name, rank);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }
    return true;
}
static bool ff_check_input_double(PyArrayObject *dem, char const *name, int rank)
{
    char msg[256];

    // Check storage
    if (!PyArray_ISCARRAY_RO(dem)) {
        snprintf(msg, 256, "Parameter %s must be C-style, contiguous array.", name);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check type
    if (PyArray_DESCR(dem)->type_num != NPY_DOUBLE) {
        snprintf(msg, 256, "Parameter %s must have dtype double.", name);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check rank
    if (PyArray_NDIM(dem) != rank) {
        snprintf(msg, 256, "Parameter %s must have rank %d", name, rank);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }
    return true;
}
// ----------------------------------------------------------------------------------------
static bool ff_check_same_dimensions(std::vector<std::pair<PyArrayObject *, std::string>> const &arrays)
{
    char msg[256];

    for (size_t i=1; i<arrays.size(); ++i) {
        // Check same rank
        int const rank0 = PyArray_NDIM(arrays[i-1].first);
        int const rank1 = PyArray_NDIM(arrays[i].first);
        if (rank0 != rank1) {
            snprintf(msg, 256, "Array %s (rank %d) and %s (rank %d) must have matching rank.",
                arrays[i-1].second.c_str(), rank0,
                arrays[i].second.c_str(), rank1);
            PyErr_SetString(PyExc_TypeError, msg);
            return false;
        }

        // Check same dimensions
        for (int r=0; r<rank0; ++r) {
            int const dim0 = PyArray_DIM(arrays[i-1].first, r);
            int const dim1 = PyArray_DIM(arrays[i-1].first, r);
            if (dim0 != dim1) {
                snprintf(msg, 256, "Dimension %d of array %s (=%d) and %s (=%d) must match.", r,
                arrays[i-1].second.c_str(), dim0,
                arrays[i].second.c_str(), dim1);
            }
        }
    }
    return true;
}
// ==================================================================================
// Converting to/from the Ulam Spiral
// Clockwise spiral to match D8 ArcGIS
//https://pro.arcgis.com/en/pro-app/2.8/tool-reference/spatial-analyst/flow-direction.htm
inline std::array<ix_t,2> ulam_n_to_xy(ix_t n)
{
    // sqrt_n = np.sqrt(n)
    double const sqrt_n = sqrt((double)n);

    // m = int(np.floor(sqrt_n))
    ix_t const m = (ix_t)floor(sqrt_n);
    ix_t const m2 = (ix_t)(2*sqrt_n);
    // if int(np.floor(2*sqrt_n))%2 == 0:
    
    // if int(np.floor(2*sqrt_n))%2 == 0:
    ix_t k1x,k1y;
    if (m2%2 == 0) {
        k1x = n-m*(m+1);
        k1y = 0;
    } else {
        k1x = 0;
        k1y = n-m*(m+1);
    }

    // sgn = int(pow(-1,m))
    ix_t const sgn = (m%2 == 0 ? 1 : -1);
    // k2 = int(np.ceil(.5*m))
    ix_t const k2 = (ix_t)ceil(.5*m);

    ix_t const x = sgn * (k1x + k2);
    ix_t const y = sgn * (k1y - k2);
    return std::array{x,y};
}

inline ix_t ulam_xy_to_n(ix_t x, ix_t y)
{
    // sgn = -1 if x<y else 1
    ix_t const sgn = (x<y ? -1 : 1);

    // k = max(np.abs(x), np.abs(y))
    ix_t const k = std::max(std::abs(x), std::abs(y));

    // n = (4*k*k) + sgn * (2*k + x + y)
    ix_t const n = (4*k*k) + sgn * (2*k + x + y);

    return n;
}

// -------------------------------------------------------------------
class UlamLookup {
public:
    std::array<std::array<int,2>,9> to_delji;
    std::array<int,9> to_deln;

    UlamLookup()
    {
        for (int deln=0; deln<=8; ++deln) {
            std::array<ix_t,2> const delji(ulam_n_to_xy(deln));
            int const delj = delji[0];
            int const deli = delji[1];
            int const k = (delj+1)*3 + (deli+1);
            to_deln[k] = deln;
            to_delji[deln] = delji;
        }
    }
};

UlamLookup const ulookup;
// -------------------------------------------------------------------
void neighbor1_to_ulam(npy_int *neighbor1, int const nj, int const ni)
{
    // (j0,i0) is coordinate of 
    for (int j0=0; j0<nj; ++j0) {
    for (int i0=0; i0<ni; ++i0) {
        ix_t const ix0 = j0*ni + i0;
        int const ix1 = neighbor1[ix0];

        // Leave non-data gridcells untouched
        if (ix1 < 0) continue;

        // 2D coordinate of detination point
        int const j1 = ix1 / ni;
        int const i1 = ix1 % ni;    // Probably compiles down to divmod

        int const delj = j1-j0;
        int const deli = i1-i0;

        // Take care of the most common case
#if OPTIMIZE_D8
        if ((delj >= -1 && delj <= 1) && (deli >= -1 && deli <= 1)) {
            int const k = (delj+1)*3 + (deli+1);
            neighbor1[ix0] = ulookup.to_deln[k];
            continue;
        } else {
            // Convert (deli,delj) to ulam spiral coordinate
            int const deln = ulam_xy_to_n(j1-j0, i1-i0);    // Reverse coordinates to get clockwise spiral as in ArcGIS
            neighbor1[ix0] = deln;
        }
#else
        int const deln = ulam_xy_to_n(delj, deli);    // Reverse coordinates to get clockwise spiral as in ArcGIS
        neighbor1[ix0] = deln;
#endif

    }}

}


inline std::array<ix_t,2> ulam_n_to_xy2(ix_t const deln)
{
    if (deln >= 0 && deln <= 8) {
        return ulookup.to_delji[deln];
    } else {
        return ulam_n_to_xy(deln);
    }
}

void neighbor1_to_ix(npy_int *neighbor1, ix_t const nj, ix_t const ni)
{
    for (ix_t j0=0; j0<nj; ++j0) {
    for (ix_t i0=0; i0<ni; ++i0) {
        ix_t const ix0 = j0*ni + i0;
        ix_t const deln = neighbor1[ix0];

        // Leave non-data gridcells untouched
        if (deln < 0) continue;

        // The table lookup here doesn't save nearly as much time as
        // the table lookup the other direction.
#if OPTIMIZE_D8
        std::array<ix_t,2> const delji(ulam_n_to_xy2(deln));
#else
        std::array<ix_t,2> const delji(ulam_n_to_xy(deln));
#endif

        ix_t const i1 = i0 + delji[1];  // Reverse coordinates to get clockwise spiral as in ArcGIS
        ix_t const j1 = j0 + delji[0];
        ix_t const ix1 = j1*ni + i1;

        neighbor1[ix0] = ix1;
    }}
}

bool to_wstring(PyObject *py_str, std::wstring &out)
{
    Py_ssize_t size;
    wchar_t const *wdir = PyUnicode_AsWideCharString(py_str, &size);
    if (!wdir) return false;
    out = std::wstring(wdir, size);
    PyMem_Free((void *)wdir);
    return true;
}

static char const *d8graph_convert_neighbor1_docstring =
R"(Converts between absolute and relative indexing of the neighbor1
graph.

* Absolute indexing provides the 1D index of the next cell in the
  neighbor1 graph.  Cells are numbered from 0 to the number of cells
  in the neighbor1 array.

* Relative indexing uses a clockwise Ulam sprial relative to the
  source cell.  Numbering of the clockwise Ulam spiral matches the
  order of the ArcGIS D8 algorithm, but is generalized beyond direct
  neighbors.  Here are the first 24 elements of the clockwise Ulam
  spiral, centered on the "*" gridcell:

     20 21 22 23 24
     19  6  7  8  9
     18  5  *  1 10
     17  4  3  2 11
     16 15 14 13 12

Args:
    neighbor1: np.array(nj, ni, dtype=np.int32)
        The degree-1 graph, in either absolute or relative indexing.
    direction: 'absolute'|'relative'
        'absolute': Convert from relative to absolute indexing
        'relative': Convert from absolute to relative indexing
        In both cases, negative indices (unused=-2, sink=-1) are preserved.
.)";

static PyObject* d8graph_convert_neighbor1(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // Input arrays
    PyArrayObject *neighbor1;
    PyObject *py_dir;

    // Parse args and kwargs
    static char const *kwlist[] = {
        "neighbor1", "direction",         // *args,
               // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!U",
        (char **)kwlist,
        &PyArray_Type, &neighbor1,
        &py_dir
        )) return NULL;

    // ----------- Typecheck input arrays
    if (!ff_check_input_int(neighbor1, "neighbor1", 2)) return NULL;

    // Convert Python str to std::string, and dispatch on it
    std::wstring dir;
    if (!to_wstring(py_dir, dir)) return NULL;
    if (dir == L"absolute") {
        neighbor1_to_ix(
            (ix_t *)PyArray_GETPTR2(neighbor1,0,0),
            PyArray_DIM(neighbor1, 0), PyArray_DIM(neighbor1, 1));
        Py_INCREF(Py_None); return Py_None;
    } else if (dir == L"relative") {
        neighbor1_to_ulam(
            (ix_t *)PyArray_GETPTR2(neighbor1,0,0),
            PyArray_DIM(neighbor1, 0), PyArray_DIM(neighbor1, 1));
        Py_INCREF(Py_None); return Py_None;
    } else {
        PyErr_SetString(PyExc_TypeError, "Unrecognized value of dir, must be 'absolute' or 'relative'");
        return NULL;

    }
}


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

#if 0
template<class TypeT>
std::array<TypeT, 2> sorted(TypeT a, TypeT b)
{
    if (a < b) return {a,b};
    return {b,a};
}
#endif

// ==================================================================================
PyObject *encode_sets(std::map<ix_t, std::set<ix_t>> const &eqclasses)
{
    // Determine size of arrays
    size_t nsets = eqclasses.size();
    size_t nelements = 0;
    for (auto &item : eqclasses) {
        nelements += item.second.size();
    }

    // Allocate arrays
    PyArrayObject *py_keys = np_new_1d((npy_intp)nsets, NPY_INT32);
    PyArrayObject *py_setbounds = np_new_1d((npy_intp)nsets+1, NPY_INT32);
    PyArrayObject *py_elements = np_new_1d((npy_intp)nelements, NPY_INT32);
    int *keys = (npy_int *)PyArray_GETPTR1(py_keys, 0);
    int *setbounds = (npy_int *)PyArray_GETPTR1(py_setbounds, 0);
    int *elements = (npy_int *)PyArray_GETPTR1(py_elements, 0);

    // Copy sets over into the arrays
    ix_t iset = 0;
    ix_t iele = 0;
    for (auto &item : eqclasses) {

        // Record length of this set
        auto &set(item.second);
        keys[iset] = item.first;
        setbounds[iset++] = iele;
        ++iset;

        // Record elements of this set
        for (ix_t ix : set) {    // This is in sorted order
            elements[iele++] = ix;
        }
    }
    setbounds[iset++] = iele;

    // Sanity check
    assert(iset == nsets+1);
    assert(iele == nelements);

    // Return as Python tuple
    return Py_BuildValue("OOO", py_keys, py_setbounds, py_elements);
}
// ------------------------------------------------------------
std::map<ix_t, std::set<ix_t>> decode_sets(PyObject *tup)
{
printf("BEGIN decode1\n");
    std::map<ix_t, std::set<ix_t>> ret;

    PyArrayObject *py_keys = (PyArrayObject *)PyTuple_GetItem(tup, 0);
    PyArrayObject *py_setbounds = (PyArrayObject *)PyTuple_GetItem(tup, 1);
    PyArrayObject *py_elements = (PyArrayObject *)PyTuple_GetItem(tup, 2);

    size_t nsets = PyArray_DIM(py_keys, 0);
    int *keys = (int *)PyArray_GETPTR1(py_keys, 0);
    int *setbounds = (int *)PyArray_GETPTR1(py_setbounds, 0);
    int *elements = (int *)PyArray_GETPTR1(py_elements, 0);

    // Iterate through each set and create the firstmap
    for (size_t i=0; i<nsets; ++i) {
        std::set<ix_t> set(&elements[setbounds[i]], &elements[setbounds[i+1]]);
        ret.insert(std::make_pair(keys[i], std::set(&elements[setbounds[i]], &elements[setbounds[i+1]])));
    }

printf("END decode1\n");
    return ret;
}
// ------------------------------------------------------------
/**
Returns:
    Map indicating the lowest-index gridcell of the EQ Class that each
    gridcell belongs to.  (Only for gridcells involved in an explicit
    EQ Class).
*/
std::unordered_map<ix_t, ix_t> decode_firstmap(PyObject *tup)
{
printf("BEGIN decode2\n");
    std::unordered_map<ix_t, ix_t> firstmap;

    PyArrayObject *py_keys = (PyArrayObject *)PyTuple_GetItem(tup, 0);
    PyArrayObject *py_setbounds = (PyArrayObject *)PyTuple_GetItem(tup, 1);
    PyArrayObject *py_elements = (PyArrayObject *)PyTuple_GetItem(tup, 2);

    size_t nsets = PyArray_DIM(py_setbounds, 0) - 1;
    int *setbounds = (int *)PyArray_GETPTR1(py_setbounds, 0);
    int *elements = (int *)PyArray_GETPTR1(py_elements, 0);

    // Iterate through each set and create the firstmap
    for (size_t i=0; i<nsets; ++i) {
//        if (i%100 == 0) printf("Working on %ld of %ld\n", i, nsets);
        int const j0 = elements[setbounds[i]];
        for (int j=setbounds[i]; j<setbounds[i+1]; ++j) {
            firstmap.insert(std::make_pair(elements[j], j0));
        }
    }

printf("END decode2\n");
    return firstmap;
}
// ------------------------------------------------------------
/** Determines which eqclass the ith gridcell is a part of */
ix_t _parent(std::unordered_map<ix_t, ix_t> const &forwards, ix_t gci)
{
    auto ii(forwards.find(gci));
    if (ii != forwards.end()) return ii->second;
    return gci;
}

class EQClasses {
    // Cell this has been merged into (if it's been merged)
    std::unordered_map<ix_t, ix_t> forwards;

public:
    // EQClass with >1 element
    // Inner vector is SORTED
    std::map<ix_t, std::set<ix_t>> eqclasses;

private:
    // Stand-in for single-element eqclasses
    std::set<ix_t> _single_ret{0};

public:

    EQClasses() {}    // Start off with everything in its own class

    /** Fetches the elements of the ith equivalence class */
    std::set<ix_t> &members(int eqi)
    {
        auto ii(eqclasses.find(eqi));
        if (ii != eqclasses.end()) {
            // This EQClass is stored explicitly, return it.
            return ii->second;
        } else {
            // This EQClass is not explicitly represented, just equal to self
            _single_ret.clear();
            _single_ret.insert(eqi);
            return _single_ret;
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
            return *(ii->second.begin());
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
    std::set<ix_t> &merge_eq(int j, int i)
    {
        // Access contents of the destination eq class,
        // converting to explicit form if needed.
        auto eqcj_it(eqclasses.find(j));
        if (eqcj_it == eqclasses.end()) {
//            PySys_WriteStdout("Creating new eqclass for %d\n", j);
            eqcj_it = eqclasses.insert(eqcj_it, std::make_pair(j, std::set<ix_t>{j}));
        }
        std::set<ix_t> &eqcj(eqcj_it->second);
//std::cout << "Dst EQClass " << j << ": "; print_range(std::cout, eqcj.begin(), eqcj.end()); std::cout << std::endl;

        // Access contents of the source eq class.  We don't know or
        // care whether it's in implicit or explicit form.
        auto &eqci(members(i));

//std::cout << "Src EQClass " << i << ": "; print_range(std::cout, eqci_bounds[0], eqci_bounds[1]); std::cout << std::endl;
        // Merge eq class i into eq class j
        for (ix_t ix : eqci) eqcj.insert(ix);

        // Delete eqclass i and forward to j
        eqclasses.erase(i);
        forwards[i] = j;

        // Return the new Equiv Class j
        return eqcj;
    }

    /** Re-key EQ Classes to the minimum element in each one. */
    void rekey()
    {
        std::map<ix_t, std::set<ix_t>> eqclasses1;
        for (auto eqii(eqclasses.begin()); eqii != eqclasses.end(); ++eqii) {
            ix_t key0 = eqii->first;
            ix_t key1 = *(eqii->second.begin());
            eqclasses1.insert(std::make_pair(key1, std::move(eqii->second)));
        }
        eqclasses = std::move(eqclasses1);
    }

};

// ----------------------------------------------------------
/** A graph with implicit 8-way neighbors based on DEM and used /
unused gridcells */
class D8Graph {
public:
    // Maintain nodes of our graph as equivalence classes
    EQClasses eqclasses;

private:
    // Maintain a DEM (imported from Python), giving us our neighbors
    dem_t *dem;
    int const nj;
    int const ni;
    double nodata;             // dem==nodata ==> unused gridcell
    // Tells whether an EQ class is on the edge of the grid or adjacent to an unused cell
    std::vector<bool> edge;

    // Explicit neighbors for merged EQ classes
    std::map<ix_t, std::set<ix_t>> neighborss;
    // Buffer used to return neighbors
    std::array<std::set<ix_t>, 2> _neighbors_rets;
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
    D8Graph(dem_t *_dem, int _nj, int _ni, double _nodata)
        : dem(_dem), nj(_nj), ni(_ni), nodata(_nodata)
    {
//PySys_WriteStdout("AA1 %f %f %f %f\n", dem[0], dem[1], dem[2], dem[3]);

        // Initialize edge indicator
        edge.reserve(nj*ni);
        for (int j=0; j<nj; ++j) {
        for (int i=0; i<ni; ++i) {
            bool const ie = is_edge(j,i);
            edge.push_back(ie);
//            PySys_WriteStdout("is_edge[%d, %d] = %d\n", j, i, (int)ie);
        }}

    }

    size_t size() { return nj*ni; }

private:
    /** Obtain list of neighbors based on raster. */
    std::set<ix_t> &d8_neighbors_list(int ji0, std::set<ix_t> &ngh)
    {
        ngh.clear();
        //ngh.reserve(8);

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
            if (dem[ji1] == 0.0) continue;    // Avoid the ocean

            // Follow forwrding for neighbors that have been merged
            // NOTE: This could result in non-unique neighbor lists being returned!
            ji1 = eqclasses.parent(ji1);

            // Add to our list of output
            ngh.insert(ji1);
        }

        return ngh;
    }

public:
    /**
    expl:
        If set, then convert to expl format if not already.
    */
    std::set<ix_t> &neighbors(int ji0, bool expl=false)
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
        reti = 1 - reti;    // swap dem_t buffer
        std::set<ix_t> &ngh(_neighbors_rets[reti]);

        // Obtain explicit list of neighbors
        d8_neighbors_list(ji0, ngh);

        // We're done if we don't need to store it for later use.
        if (!expl) return ngh;

        // We DO need to store the explicit representation.
        ii = neighborss.insert(std::make_pair(ji0, std::move(ngh))).first;
        return ii->second;
    }

    /** Merge neighbor lists in prep for an eqclass merger of j <- i */
    std::set<ix_t> &merge_neighbor_lists(ix_t j, ix_t i, bool debug=false)
    {
        // Original neighbor lists
        std::set<ix_t> &nghj(neighbors(j, true));
        std::set<ix_t> &nghi(neighbors(i));

if (debug) PySys_WriteStdout("********* Merging %d (%f) <- %d (%f)\n", j, dem[j], i, dem[i]);
#if 0
PySys_WriteStdout(" pre neighbors[%d]: ", j); for (auto ii(nghj.begin()); ii != nghj.end(); ++ii) PySys_WriteStdout(" %d", *ii); PySys_WriteStdout("\n");
PySys_WriteStdout(" pre neighbors[%d]: ", i); for (auto ii(nghi.begin()); ii != nghi.end(); ++ii) PySys_WriteStdout(" %d", *ii); PySys_WriteStdout("\n");
#endif

        // ------------------- Merge the lists
        for (ix_t ix : nghi) nghj.insert(ix);

#if 0
PySys_WriteStdout("joined neighbors %d: ", j); for (auto ii(ngh_joined.begin()); ii != ngh_joined.end(); ++ii) PySys_WriteStdout(" %d", *ii); PySys_WriteStdout("\n");
#endif

        // --------------- Filter out i and j
        nghj.erase(i);
        nghj.erase(j);

        // Delete neighbors list for i
        neighborss.erase(i);

        // ============== Replace i->j in neighbor lists of neighbors
        for (ix_t k : nghj) {
            std::set<ix_t> &nghk(neighbors(k, true));
            auto findi(nghk.find(i));
            if (findi != nghk.end()) {
                nghk.erase(i);
                nghk.insert(j);
            }
        }

#if 0
auto &xnghj(neighbors(j));
PySys_WriteStdout(" post neighbors[%d]: ", j); for (auto ii(xnghj.begin()); ii != xnghj.end(); ++ii) PySys_WriteStdout(" %d", *ii); PySys_WriteStdout("\n");
#endif

        return nghj;
    }




    /** Returns merged {eqclass vector, neighbor vector} */
    std::array<std::set<ix_t> *, 2> const merge(int j, int i, bool debug=false)
    {
        // ----------- Merge neighbor lists
        std::set<ix_t> &nghj(merge_neighbor_lists(j, i, debug));

        // ----------- Maintain edge designation
        edge[j] = edge[j] || edge[i];


        // ----------- Merge underlying EQClasses
        std::set<ix_t> &eqclassj(eqclasses.merge_eq(j,i));
        return {&eqclassj, &nghj};
    }


    /**
    max_sink_size: (DEPRECATED; IGNORED)
        Don't merge sinks larger than this.
    */
    void fill_sinks(size_t max_sink_size)
    {

        int merge_count = 0;
        for (int ix=0; ix<(int)size(); ++ix) {
            // Only look at primary node for each EQ class
            if (eqclasses.parent(ix) != ix) continue;

            // Progressively merge with neighbors
            for (;;) {

#if 1
                // Edge nodes don't get merged, the unused gridcell
                // nextdoor is by definition a place we can flow to from this
                // gridcell.
                if (edge[ix]) break;
#endif

                // Find index of the neighbor with the lowest elevation in the dem
                // (that is small enough to merge)
                ix_t min_ix = -1;
                dem_t min_elev = 1.e20;
                auto &ngh(neighbors(ix));
                for (auto kk(ngh.begin()); ; ++kk) {
                    if (kk == ngh.end()) break;
#if 0     // max_sink_size is too buggy
                    if (eqclasses.size(ix) + eqclasses.size(*kk) > max_sink_size) continue;
#endif
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

                // Set elevation for the EQ class to the (higher) elevation of the neighbor
                // (Elevation of other gridcells in the EQ class will be adjusted later)
                dem[ix] = dem[min_ix];

                // Merge min_ix into ix, return neighbors of merged ix
//if (ix == 18729844 || min_ix == 18729844) printf("TRACE Merge %d <- %d\n", ix, min_ix);
                merge(ix, min_ix, merge_count % 10000 == 0);    // Merge into lower-elevation     index always
                ++merge_count;

#if 0     // max_sink_size is too buggy
                // Stop if we've gotten too large
                if (merged_eqclass.size() > max_sink_size) break;
#endif

            }
        }

        // Set DEM level for all cells in each eqclass
        for (auto eqii(eqclasses.eqclasses.begin()); eqii != eqclasses.eqclasses.end(); ++eqii) {
            dem_t const elev = dem[eqii->first];
            std::set<ix_t> &members(eqii->second);
            for (auto ix2 : members) dem[ix2] = elev;
        }
    }


    /** Construct the degree-1 neighbor relationship.  Represented as
    a 1D array by gridcell.  Gridcells in each EQ class are arranged
    in a linear fashion, so all of them are traversed in any graph
    search.
    neighbor1:  [nj*ni]
        Base of 1D array of gridcell neighbors.
        (Potentially this is a Numpy array.)
    */
    void to_neighbor1(npy_int *neighbor1) const
    {
        // Initialize all to -2
        for (ix_t ix_i=0; ix_i<(ix_t)size(); ++ix_i) {
            neighbor1[ix_i] = -2;
        }

        // ix_i is the index of the "current" eq class
        for (ix_t ix_i=0; ix_i<(ix_t)size(); ++ix_i) {
            // Skip cells that aren't part of the grid
            if (dem[ix_i] == nodata) continue;

            // Only consider each equivalence class once (when we are
            // looking at its lead gridcell, which is not necessarily
            // the largest or smallest)
            if (eqclasses.parent(ix_i) != ix_i) continue;

            // Consider how we will link FROM ix_i, TO something else
            // if ix_i is a compound eq class, link from the HIGHEST INDEX gridcell in it
            auto &members_i(eqclasses.members(ix_i));
            ix_t max_member_i = *members_i.rbegin();   // Highest index in EQ Class ix_i

            // Set ix_j to index of lowest neighboring eq class
            auto &ngh(neighbors(ix_i));
            ix_t ix_j = *std::min_element(ngh.begin(), ngh.end(),
                [this](int const ix0, int const ix1) { return dem[ix0] < dem[ix1]; });

            // Link to the next-lowest neighbor
            if (dem[ix_j] < dem[ix_i]) {
                // The lowest neighbor ix_j is LOWER than ix_i (typical case).
                // Create graph link: ix_i -> ix_j
                // if ix_j is a compound eq class, link to the LOWEST INDEX gridcell in it
                ix_t min_member_j = eqclasses.min_member(ix_j);         // Smallest in j
                neighbor1[max_member_i] = min_member_j;
//if (members_i.find(18729844) != members_i.end()) printf("Found target 18729844 in %d, linking to %d\n", ix_i, ix_j);
            } else {
                // The lowest neighboring EQ class is no lower than us.
                // So we are a sink.
                // Record no outbound neighbor.  AVOID CYCLES IN THE GRAPH!
                neighbor1[max_member_i] = -1;
//if (members_i.find(18729844) != members_i.end()) printf("Found target 18729844 in %d, linking to %d\n", ix_i, -1);
            }

            // --------------------------------------------------
            // Create links *within* eq class ix_i, from the lowest
            // index to the highest index gridcell.  Any flow into eq
            // class ix_i will enter at the lowest index gridcell,
            // then traverse all portions of the eq class before
            // exiting from the highest index.
            auto ii0(members_i.begin());

            auto ii1(ii0);   ++ii1;
            while (ii1 != members_i.end()) {
                neighbor1[*ii0] = *ii1;
                ii0 = ii1;
                ++ii1;
            }
        }
    }

    std::map<ix_t, std::set<ix_t>> ocean_neighborss() const
    {
        std::map<ix_t, std::set<ix_t>> ocean_neighborss;
        for (auto eqii(eqclasses.eqclasses.begin()); eqii != eqclasses.eqclasses.end(); ++eqii) {
            std::set<ix_t> ocean_neighbors;    // Will be ocean neighbors of this EQ Class
            std::set<ix_t> const &members(eqii->second);    // Members of this EQ Class

            for (ix_t ji0 : members) {
                // Identify neighbors based on the 2D raster.
                int const j0 = ji0 / ni;
                int const i0 = ji0 % ni;    // Probably compiles down to divmod

                // Look at neighboring nodes in 2D space
                for (auto &dn : dneigh) {
                    // Avoid outrunning our domain
                    int const j1 = j0 + dn[0];
                    int const i1 = i0 + dn[1];
                    if ((j1<0) || (j1>=nj) || (i1<0) || (i1>=ni)) continue;

                    // Keep only neighbor gridcells that are unused or ocean
                    int ji1 = j1*ni + i1;
                    if ((dem[ji1] === nodata) || (dem[ji1] == 0.0)) {
                        ocean_neighbors.insert(ji1);
                    }
                }
            }
//            if (ocean_neighbors.size() > 0)
                ocean_neighborss.insert(std::make_pair(eqii->first, std::move(ocean_neighbors)));
        }
        return ocean_neighborss;
    }
};



const std::vector<std::array<int,2>> D8Graph::dneigh = {
    {-1,-1}, {-1,0}, {-1,1},
    {0, -1},         {0, 1},
    {1,-1},  {1,0},  {1,1}};

// ====================================================================

// ------------------------------------------------------------


/** Does a depth-first-search of the neighbor1 graph starting from
some gridcells.

start_begin, start_end:
    begin and end iterators for starting gridcell indices
*/
std::unordered_set<ix_t> find_domain(
    std::unordered_map<ix_t, ix_t> const &firstmap,    // Lowest-index cell in each eq class
    ix_t const *neighbor1,
    std::map<ix_t, std::set<ix_t>> const &ocean_neighborss,
    double const *dem_filled,
    int const nj, int const ni,
    double const *gt,    // Geotransform
    ix_t const *start_begin, ix_t const *start_end,
    double const min_alpha)
{
    // Adds a gridcell to the list of cells we need to start from.
    // If the cell is part of an EQ class, adds the entire class.
    // EQ Classes are identified by the LOWEST-VALUE index in them.
    std::vector<ix_t> starts;
    std::unordered_set<ix_t> eqclasses_seen;    // Which eqclasses we've seen
    std::set<ix_t> ocean_starts;

    // --------------------------------------------------------------
    auto add_eqclass_to_starts =
        [neighbor1,dem_filled,&starts,&eqclasses_seen]
        (ix_t first_ix) -> void
    {
        // Make sure we haven't already added this EQ Class
        auto ii(eqclasses_seen.find(first_ix));
        if (ii != eqclasses_seen.end()) return;
        eqclasses_seen.insert(first_ix);

//printf("add_eqclass:"); for (ix_t ix=first_ix; ix>=0; ix = neighbor1[ix]) printf(" (%d %f)", ix); printf("\n");

        // Add gridcells in the class to starts
        int count = 0;
        for (ix_t ix=first_ix; ;) {
//if (ix >= 0) printf("add_eqclass: %d %f\n", ix, dem_filled[ix]);
            starts.push_back(ix);  ++count;
            ix_t const next_ix = neighbor1[ix];
            if (next_ix < 0) break;
            if (dem_filled[next_ix] != dem_filled[ix]) break;
            ix = next_ix;
        }
//printf("Added %d cells when adding EQClass to starts\n", count);

    };
    // --------------------------------------------------------------

    // Initialize our starting set (PRA), while expanding EQ classes that
    // might be within it.
    for (auto ixp=start_begin; ixp != start_end; ++ixp) {
        ix_t const ix = *ixp;

        auto ii(firstmap.find(ix));
        if (ii != firstmap.end()) {
            add_eqclass_to_starts(ii->second);
        } else {
            starts.push_back(ix);
        }
        
    }


    // Get info on highest-elevation gridcell in the start set.
    // This will also be the most up-slope, and hence will have the highest
    // inclination (alpha angle) compared to downslope gridcells.
    // See: https://www.avalanche-center.org/Education/blog/?itemid=535
    ix_t ix_highest = *std::max_element(starts.begin(), starts.end(),
        [dem_filled](int const ix0, int const ix1) { return dem_filled[ix0] < dem_filled[ix1]; });
    double const dem_highest = dem_filled[ix_highest];
    int const j_highest = ix_highest / ni;
    int const i_highest = ix_highest % ni;    // Probably compiles down to divmod
    double const x_highest = gt[0] + i_highest*gt[1] + j_highest*gt[2];
    double const y_highest = gt[3] + i_highest*gt[4] + j_highest*gt[5];

    // Depth First Search
    std::unordered_set<ix_t> seen;
    while (starts.size() > 0) {
        ix_t ix = starts.back(); starts.pop_back();
        for (;;) {
            // Stop if already visited
            {auto ii(seen.find(ix));
            if (ii != seen.end()) break;}

            // -------------------------------------
            // Stop if alpha is low enough to suggest
            // the runout would have stopped by this point (18 degrees
            // should be OK).  In that case, we should never have been
            // looking at this gridcell to begin with (it might be WAY
            // out of bounds).  So don't even add to the seen set.

            // Obtain geographic coordinates of this gridcell
            int const j = ix / ni;
            int const i = ix % ni;    // Probably compiles down to divmod
            double const x = gt[0] + i*gt[1] + j*gt[2];
            double const y = gt[3] + i*gt[4] + j*gt[5];

            // Compute angle of inclination from the top (alpha)
            double const delx = x - x_highest;
            double const dely = y - y_highest;
            double const delxy = sqrt(dely*dely + delx*delx);
            double const delz = dem_filled[ix] - dem_highest;
            double const alpha = (180./M_PI) * abs(atan2(delz, delxy));

            if (alpha < min_alpha) break;

            // ----------------------------------------------------
            // This gridcell is within alpha range, so add it to the
            // seen set.
            seen.insert(ix);

            // -------------------------------------------------------
            // Add any ocean neighbors
            auto ocnii(ocean_neighborss.find(ix)) {
            }

            // --------------------------------------------------------
            ix_t const next_ix = neighbor1[ix];
            // Quit this runout if it's finished itself.
            if (next_ix < 0) break;

            // Determine if next step is in an EQ class
            // If so, add the entire EQ class to starts, and quit this start.
            {auto ii(firstmap.find(next_ix));
            if (ii != firstmap.end()) {
                add_eqclass_to_starts(ii->second);
                break;
            }}

            // Determine if this gridcell borders any ocean gridcells

            // Add ocean neighbors to ocean_starts
            auto ocnii(ocean_neighborss.find(first_ix));
            if (ocnii != ocean_neighborss.end()) {
                // This is an EQ Class with many potential ocean neighbors
                auto &ocean_neighbors(ocnii->second);
                ocean_starts.insert(ocean_neighbors.begin(), ocean_neighbors.end());
            } else {
                // Identify ocean neighbors based on the 2D raster.
                int const ji0 = first_ix;
                int const j0 = ji0 / ni;
                int const i0 = ji0 % ni;    // Probably compiles down to divmod

                // Look at neighboring nodes in 2D space
                for (auto &dn : dneigh) {
                    // Avoid outrunning our domain
                    int const j1 = j0 + dn[0];
                    int const i1 = i0 + dn[1];
                    if ((j1<0) || (j1>=nj) || (i1<0) || (i1>=ni)) continue;

                    // Keep only neighbor gridcells that are unused or ocean
                    int ji1 = j1*ni + i1;
                    if ((dem[ji1] === nodata) || (dem[ji1] == 0.0)) {
                        ocean_starts.insert(ji1);
                    }
                }
              }        

            // --------------------------------------------------------
            // Next gridcell is just a regular cell.  Advance and continue.
            ix = next_ix;
        }
    }

    // We're done searching all LAND-based gridcells.  Now look out in
    // the ocean, based on ocean_starts.

    return seen;
}



// =========================================================================
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

dem: np.array(nj, ni, dtype=np.single)  INOUT
    The input digital elevation model
    Elevations get changed here if fill-sinks is turned on (max_sink_size > 0)
nodata: double
    dem takes this value for unused cells (eg ocean)
max_sink_size: int DEFAULT 0
    Maximum number of cells to join together in equivalence classes
    (Currently deprecated: 0=don't fill sinks, >0=do fill sinks)

Returns: neighbor1=np.array(nj, ni, dtype=np.int32)
    Representation of the degree-1 graph
    neighbor1[j,i] = 1D index of the downstream node.
       ...or -1 if cell (j,i) is unused, or there is no downstream node.
)XXX";
static PyObject* d8graph_neighbor_graph(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // Input arrays
    PyArrayObject *dem;
    double nodata;
    int max_sink_size = 0;

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
    if (PyArray_DESCR(dem)->type_num != NPY_FLOAT) {
        PyErr_SetString(PyExc_TypeError, "Input dem must have type float (single precision)");
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
    PyArrayObject *neighbor1 = (PyArrayObject*) PyArray_NewFromDescr(
        &PyArray_Type, 
        PyArray_DescrFromType(NPY_INT32),             // dtype='i'
        2,                                          // rank 2
        PyArray_DIMS(dem), strides,    // Same shape as DEM
        NULL,        // Allocate new memory
        // PyArray_FLAGS(dem), ...
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);

    // ========================================================
    // Do the computation

    D8Graph d8g((dem_t *)PyArray_GETPTR2(dem,0,0), PyArray_DIM(dem,0), PyArray_DIM(dem,1), nodata);

    PySys_WriteStdout("Filling sinks...\n");
    if (max_sink_size > 0) d8g.fill_sinks(max_sink_size);

    PySys_WriteStdout("Converting to neighbor1 format\n");

    PySys_WriteStdout("neighbor1 dims: %ld %ld\n", PyArray_DIM(neighbor1,0), PyArray_DIM(neighbor1,1));

    // Convert graph to degree-1, with neighbors running through each EQ Class
    d8g.to_neighbor1((npy_int *)PyArray_GETPTR2(neighbor1,0,0));

    // Now that we have neighbor1, we can re-do the keying on our
    // EQClasses.  NOTE: This will break links in d8g that use the old
    // keying; but we don't need d8g anymore.
    d8g.eqclasses.rekey();

    // Encode the EQClasses as two Numpy arrays
    PyObject *eqclasses = encode_sets(d8g.eqclasses.eqclasses);

    // Encode ocean neighbors of each EQClass as two Numpy arrays
    PyObject *ocean_neighborss = encode_sets(d8g.ocean_neighborss());
    // ========================================================
    return Py_BuildValue("OOO", eqclasses, (PyObject *)neighbor1, ocean_neighborss);
}
// ----------------------------------------------------------------------------------------
static PyObject *polygon_to_python(std::vector<std::array<double,2>> const &mbr)
{
    PyObject *mbr_list = PyList_New(mbr.size());
    if (!mbr_list) return Py_BuildValue("");    // return None

    for (size_t i=0; i<mbr.size(); ++i) {
        auto const &xy = mbr[i];
        PyObject *tup = Py_BuildValue("dd", xy[0], xy[1]);
        if (!tup) return NULL;
        PyList_SetItem(mbr_list, i, tup);
    }
    return mbr_list;
}
// ----------------------------------------------------------------------------------------
static char const *d8graph_find_domain_docstring =
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

static PyObject* d8graph_find_domain(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // ======================== Parse Python Input
    // Input arrays
    PyObject *eqclasses_py;
    PyArrayObject *neighbor1;
    PyArrayObject *ocean_neighbors_py;
    PyArrayObject *dem_filled;
    PyArrayObject *geotransform;
    PyArrayObject *start;
    double margin = 0;
    int debug = 0;    // bool
    double min_alpha = 18.;    // Minimum "alpha" angle at which avalanche expected to continue

    // Parse args and kwargs
    static char const *kwlist[] = {
        "eqclasses", "neighbor1", "ocean_neighbors", "dem_filled", "geotransform", "start",         // *args,
        "margin", "debug", "min_alpha",        // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "OO!O!O!O!|did",
        (char **)kwlist,
        &eqclasses_py,    // (keys, setbounds, elements)
        &PyArray_Type, &neighbor1,
        &ocean_neighbors_py,    // (keys, setbounds, elements)
        &PyArray_Type, &dem_filled,
        &PyArray_Type, &geotransform,
        &PyArray_Type, &start,
        &margin, &debug, &min_alpha
        )) return NULL;

    // ----------- Typecheck input arrays
    if (!ff_check_input_int(neighbor1, "neighbor1", 2)) return NULL;
    if (!ff_check_input_double(dem_filled, "dem_filled", 2)) return NULL;
    if (!ff_check_same_dimensions(
        std::vector<std::pair<PyArrayObject *, std::string>>
        {{neighbor1, "neighbor1"}, {dem_filled, "dem_filled"}})) return NULL;
    if (!ff_check_input_int(start, "start", 1)) return NULL;
    if (!ff_check_input_double(geotransform, "geotransform", 1)) return NULL;

    // int const nj = PyArray_DIM(neighbor1,0);
    int const ni = PyArray_DIM(neighbor1,1);


    std::unordered_map<ix_t, std::set<ix_t>> ocean_neighbors(decode_sets(ocean_neighbors_py));
    std::unordered_map<ix_t, ix_t> firstmap(decode_firstmap(eqclasses_py));

    // ============================ Run the Core Computation
    // Run the flood fill algorithm, result in a set of 1D indices
    std::unordered_set<ix_t> seen(
        find_domain(
            firstmap,
            (ix_t *)PyArray_GETPTR2(neighbor1,0,0),
            ocean_neighbors,
            (double *)PyArray_GETPTR2(dem_filled,0,0),
            PyArray_DIM(neighbor1,0), PyArray_DIM(neighbor1,1),    // Not needed
            (double *)PyArray_GETPTR1(geotransform, 0),
            (ix_t *)PyArray_GETPTR1(start, 0),
            (ix_t *)PyArray_GETPTR1(start, PyArray_DIM(start,0)),
            min_alpha));

    PySys_WriteStdout("Flood Fill went from %ld -> %ld gridcells.\n", PyArray_DIM(start,0), seen.size());

    // ================ Return raw results of the flood fill
    PyArrayObject *ret_seen = nullptr;
    if (debug) {
        // Sort result
        std::vector<ix_t> seen_vec(seen.begin(), seen.end());
        std::sort(seen_vec.begin(), seen_vec.end());

        // ============================= Construct Python Output
        ret_seen = np_new_1d((npy_intp)seen.size(), NPY_INT32);

        // Copy to ret_seen
        for (size_t k=0; k<seen_vec.size(); ++k) {
            *(npy_int *)PyArray_GETPTR1(ret_seen, k) = seen_vec[k];
        }
        // ========================================================
    }

    // Compute Convex Hull
    // Compute convex hull in integer coordinate space
    // (because we can, and we avoid computational geometry
    // problems that stem from floating point)
    std::vector<std::array<int,2>> ij_points;
    ij_points.reserve(seen.size());
    for (auto ii(seen.begin()); ii != seen.end(); ++ii) {

        // Convert 1D index to 2D index
        ix_t const ji = *ii;
        ix_t const j = ji / ni;
        ix_t const i = ji % ni;    // Probably compiles down to divmod

        // Add it in (notice we are standardizing on i-j coordinate order here on out)
        ij_points.push_back(std::array{i,j});
    }
    std::vector<std::array<int,2>> chull_ij(dggs::convex_hull(ij_points));
    ij_points.clear();    // Free memory

    // Convert convex hull to geographic coordinates by applying the geotransform
    // https://gdal.org/tutorials/geotransforms_tut.html
    std::vector<std::array<double,2>> chull_xy;
    chull_xy.reserve(chull_ij.size());
    double const *gt = (double *)PyArray_GETPTR1(geotransform, 0);
    for (auto &ij : chull_ij) {
        ix_t const i = ij[0];
        ix_t const j = ij[1];
        double const x = gt[0] + i*gt[1] + j*gt[2];
        double const y = gt[3] + i*gt[4] + j*gt[5];
        chull_xy.push_back(std::array{x,y});
    }

    PyObject *ret_chull_xy = nullptr;
    if (debug) ret_chull_xy = polygon_to_python(chull_xy);

    // Compute minimum bounding rectangle (MBR) on the convex hull
    PyObject *ret_mbr = nullptr;
    if (chull_xy.size() >= 3) {
        std::vector<std::array<double,2>> mbr(dggs::mbr_chull(chull_xy, margin));
        ret_mbr = polygon_to_python(mbr);
    } else {
        ret_mbr = PyList_New(0);
    }

    if (debug) {
        return PyTuple_Pack(3, ret_seen, ret_chull_xy, ret_mbr);
    } else {
        return ret_mbr;
    }
}

// ============================================================
// Random other Python C Extension Stuff
static PyMethodDef D8GraphMethods[] = {
    {"neighbor_graph",
        (PyCFunction)d8graph_neighbor_graph,
        METH_VARARGS | METH_KEYWORDS, d8graph_neighbor_graph_docstring},

    {"find_domain",
        (PyCFunction)d8graph_find_domain,
        METH_VARARGS | METH_KEYWORDS, d8graph_find_domain_docstring},

    {"convert_neighbor1",
        (PyCFunction)d8graph_convert_neighbor1,
        METH_VARARGS | METH_KEYWORDS, d8graph_convert_neighbor1_docstring},

    // Sentinel
    {NULL, NULL, 0, NULL}
};


/* This initiates the module using the above definitions. */
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "d8graph",    // Name of module
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
  PySys_WriteStderr("Error: signal %d:\n", sig);
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

