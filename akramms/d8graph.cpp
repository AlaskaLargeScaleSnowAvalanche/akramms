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
#include <queue>
#include <iostream>
#include <iomanip>
#include <iterator>
#include <cmath>
#include <cwchar>
#include <ctime>

// https://stackoverflow.com/questions/77005/how-to-automatically-generate-a-stacktrace-when-my-program-crashes
#include <cstdio>
#include <execinfo.h>
#include <csignal>
#include <cstdlib>
//#include <cunistd>
#include <akramms/ulam.hpp>
#include <akramms/chull.hpp>
#include <akramms/mbr.hpp>

#include "nputil.hpp"

using namespace akramms;

// #define OPTIMIZE_D8        // Adds complication, only speeds things up a little bit.

static char module_docstring[] = 
"D8Graph 1.0.0 extension module computes graphs and flow paths in digital elevation models.";

typedef float dem_t;    // The Digital Elevation Model is single prceision
typedef int ix_t;
//typedef std::set<ix_t> neighbor_set;
typedef std::unordered_set<ix_t> neighbor_set;


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
#if 0    // unused
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
#endif
// ==================================================================================

// -------------------------------------------------------------------
// Create a quick lookup table for the first ring of the Ulam spiral (0 <= n <= 8)
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

// ----------------------------------------------------------
typedef std::vector<std::array<int,2>> dneigh_t;
const dneigh_t dneigh8 = {
    {-1,-1}, {-1,0}, {-1,1},
    {0, -1},         {0, 1},
    {1,-1},  {1,0},  {1,1}};

/** A graph with implicit 8-way neighbors based on DEM and used /
unused gridcells */
class DEMNeigh {
public:
    // Maintain a DEMNeigh (imported from Python), giving us our neighbors
    dem_t const * const dem;
    int const nj;
    int const ni;
    double const nodata;             // dem==nodata ==> unused gridcell
    dneigh_t const &dneigh;

//    std::vector<dem_t> spill;    // Temporary variable
//    std::vector<int> eqclass;

    inline int ji(int const j, int const i) const
        { return j*ni + i; }

    /** Determines whether a gridcell is an edge cell, i.e. borders on
    an unused cell or grid edge.  This function is called a the
    beginning to build a lookup table, which is then modified as eq
    classes are merged. */
    bool is_edge(int j0, int i0) const
    {
        // Look at neighboring nodes in 2D space
        for (auto &dn : dneigh8) {
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
    DEMNeigh(dem_t *_dem, int _nj, int _ni, double _nodata, dneigh_t const &_dneigh)
        : dem(_dem), nj(_nj), ni(_ni), nodata(_nodata), dneigh(_dneigh)
//        spill(nj*ni), eqclass(nj*ni)
    {}

    size_t size() const { return nj*ni; }

};


/** Computes the "Spill" value as per

An effective depression filling algorithm for DEM-based 2-D surface flow modelling
D. Zhu1, Q. Ren2, Y. Xuan1, Y. Chen3, and I. D. Cluckie1
doi:10.5194/hess-17-495-2013

    For b ← [cells on data boundary or channel cells]
        Spill [b] ← Elevation [b]
        PQueue.push(b)
        Mark [b] = true
    End For

    While PQueue is not empty
        c ← PQueue.top()      # Cell with lowest spill elevation
        PQueue.pop(c)
        Mark [c] ← true
        For n ← [4 neighbors of c]
            If not Mark [n]
                Spill [n] ← Max(Elevation [n], Spill[c])
                PQueue.push(n)
            End If
        End For
    End While


spill: Output array
    Leveled values stored here


*/
static inline void compute_spill(DEMNeigh const &dem, std::vector<dem_t> &spill)
{
    PySys_WriteStdout("BEGIN compute_spill()\n");

    // True if this cell has been added to the priority queue.
    std::vector<bool> mark(dem.nj * dem.ni);    // Initialized to false

    // https://en.cppreference.com/w/cpp/container/priority_queue
    // Line 8 obtains the node with the least cost (the lowest spill
    // elevation) through the member function PQueue.Top()


    // Max priority queue by default stores tuples: (spill, j, i)
    // We will make it a min queue without any extra code by storing -spill
    std::priority_queue<std::tuple<double,int,int>> pqueue;    

    long nprocessed = 0;
    auto set_mark = [&mark, &nprocessed,&pqueue](int ji) {
        mark[ji] = true;
        ++nprocessed;
        if ((nprocessed % 100000) == 0) {
            PySys_WriteStdout("    nprocessed = %ld (q=%ld)\n", nprocessed, pqueue.size());
        }
    };

    // For b ← [cells on data boundary or channel cells]
    for (int bj=0; bj<dem.nj; ++bj) {
    for (int bi=0; bi<dem.ni; ++bi) {
        int const bji = dem.ji(bj, bi);
        if (dem.dem[bji] == dem.nodata) continue;

        if (dem.is_edge(bj, bi)) {
            int const bji = dem.ji(bj, bi);
            spill[bji] = dem.dem[bji];
            pqueue.push(std::tuple<double,int,int>{-spill[bji], bj, bi});
            set_mark(bji);
        }
    }}

    while (!pqueue.empty()) {
        std::tuple<double,int,int> const cq = pqueue.top();
            // double const cspill = -std::get<0>(cq);   // (not used)
            int const cj = std::get<1>(cq);
            int const ci = std::get<2>(cq);
        int const cji = dem.ji(cj, ci);
        pqueue.pop();

        // Look at neighboring nodes in 2D space (j1,i1)
        for (auto &dng : dem.dneigh) {
            int const j1 = cj + dng[0];
            int const i1 = ci + dng[1];
            if ((j1<0) || (j1>=dem.nj) || (i1<0) || (i1>dem.ni)) continue;
            int const ji1 = dem.ji(j1,i1);
            if (dem.dem[ji1] == dem.nodata) continue;

            if (!mark[ji1]) {
                spill[ji1] = std::max(dem.dem[ji1], spill[cji]);
                pqueue.push(std::tuple<double,int,int>{-spill[ji1], j1, i1});
                set_mark(ji1);
            }
        }

if (nprocessed > 20L) break;
    }
    PySys_WriteStdout("END compute_spill()\n");
}

// Find all cells with spill equal to cell (bj, bi)
static inline void equal_spill(
    DEMNeigh const &dem,
    std::vector<dem_t> const &spill,
    std::vector<bool> &mark,
    std::vector<int> &forward,
    std::vector<int> &neighbor_eqclass,
    // std::vector<int> &neighbor_within,
    npy_int *neighbor_within,
    int bj, int bi)
{

    std::vector<int> eqclass;    // ji 1D index of items in the eq class

    // We are looking for adjacent cells with this value of spill
    int const bji = dem.ji(bj, bi);
    dem_t spillval = spill[bji];

    // (1D) Index of lowest neighbor node
    int lowest_neighbor = -1;   // Will be set below.
    dem_t lowest_neighbor_spill = spillval;

    // Initialize our queue of cells we haven't yet looked at.
    std::queue<std::array<int,2>> todo;
    todo.push(std::array<int,2>{bj, bi});


    while (!todo.empty()) {
        std::array<int,2> const &cq(todo.front());
            int const cj = cq[0];
            int const ci = cq[1];
            int const cji = dem.ji(cj, ci);

        // Add it to our eq class and mark as seen
        eqclass.push_back(cji);
        mark[cji] = true;

        // Identify neighboring nodes to look at
        for (auto &dn : dem.dneigh) {
            int const j1 = cj + dn[0];
            int const i1 = ci + dn[1];
            if ((j1<0) || (j1>=dem.nj) || (i1<0) || (i1>dem.ni)) continue;
            int const ji1 = dem.ji(j1,i1);
            if (dem.dem[ji1] == dem.nodata) continue;
            if (mark[ji1]) continue;

            double const &neighbor_spill = spill[ji1];
            if (neighbor_spill == spillval) {
                // It's one of us: look at it later
                todo.push(std::array<int,2>{j1,i1});
            } else if (neighbor_spill < lowest_neighbor_spill) {
                // It's a real neighbor: determine if it's the LOWEST neighbor
                lowest_neighbor_spill = neighbor_spill;
                lowest_neighbor = ji1;
            }

        }
    }


    // forward:
    //    Points to the lowest gridcell in THIS eqclass
    //    We know we are the lowest if forward[ji]==ji
    //    If it's a non-consolidated eq class, then forward[ji]==-1
    // neighbor_eqclass:
    //    Only valid for the LOWEST gridcell in each eqclass
    //    Points tothe UNFORWARDED next-lowest neighbor.
    // neighbor_within:
    //    Valid for all but the LAST gridcell in each eqclass
    //    Points to the next neighbor in this class.
    //    neighbor2[LAST] = -2
    //    We know we are the LAST gridcell in an eqclass if neighbor2[ji] == -2
    //       In that case, our eqclass index is forward[ji]
    //       And (once all forwards have been set), we should set:
    //          neighbor1[ji] = forward[neighbor_eqclass[forward[ji]]]


    int const ji_eq = eqclass[0];    // Label of our equivalence class
    if (eqclass.size() == 1) {
        forward[ji_eq] = -1;
        neighbor_eqclass[ji_eq] = lowest_neighbor;
        neighbor_within[ji_eq] = -2;
    } else {
        // Use the computed equivalence class to set forward, neighbor_eqclass and neighbor_within
        std::sort(eqclass.begin(), eqclass.end());    // Sort by index

        // Set forward and neighbor_within
        int ji0 = ji_eq;
        neighbor_eqclass[ji0] = lowest_neighbor;
        forward[ji0] = ji_eq;
        for (size_t k=1; k<eqclass.size(); ++k) {
            int ji1 = eqclass[k];
            forward[ji1] = ji_eq;
            neighbor_within[ji0] = ji1;    // Setting neighbor_within for previous element
            ji0 = ji1;
        }
        neighbor_within[ji0] = -2;    // Last element in eqclass
    }

}


static inline void to_neighbor1(DEMNeigh const &dem, npy_int * const sinks, npy_int * const neighbor1)
{
    PySys_WriteStdout("BEGIN to_neighbor1()\n");

    int const nji = dem.nj * dem.ni;

    // Compute spill
    std::vector<dem_t> spill(nji, dem.nodata);
    compute_spill(dem, spill);

    // Initialize additional arrays
    std::vector<bool> mark(nji, false);    // Initialized to false
    std::vector<int> forward;    // Initialize to forward-to-self
        forward.reserve(nji);
        for (int ji=0; ji<nji; ++ji) forward[ji] = ji;
    std::vector<int> neighbor_eqclass(nji, -2);

    // neighbor_within can use same memory as neighbor1
    npy_int * const neighbor_within = neighbor1;
    for (int ji=0; ji<nji; ++ji) neighbor_within[ji] = -2;

    // Iterate through the gridcells collecting equivalence classes
    PySys_WriteStdout("BEGIN equal_spills\n");
    for (int bj=0; bj<dem.nj; ++bj) {
    for (int bi=0; bi<dem.ni; ++bi) {
        int const bji = dem.ji(bj, bi);
        if (dem.dem[bji] == dem.nodata) continue;
        if (mark[bji]) continue;    // Already saw it in another eq class

        equal_spill(dem, spill, mark, forward, neighbor_eqclass, neighbor_within, bj, bi);

    }}
    PySys_WriteStdout("END equal_spills\n");

    // Iterate through one last time and set the neighbor1 element
    // for the LAST of each eqclass
    PySys_WriteStdout("BEGIN neighbor1\n");
    for (int ji=0; ji<nji; ++ji) {
        if (neighbor1[ji] == -2) {
            int const fji = forward[ji];   // ==-1 if singleton
            if (fji == -1) {
                // It's a singleton
                sinks[ji] = -1;
                neighbor1[ji] = forward[neighbor_eqclass[ji]];
            } else {
                // Part of a larger eq class
                sinks[ji] = fji;
                neighbor1[ji] = forward[neighbor_eqclass[fji]];
            }
        }
    }
    PySys_WriteStdout("END neighbor1\n");
    PySys_WriteStdout("END to_neighbor1()\n");
}

// -------------------------------------------------------------
/** Does a breadth-first-search of the neighbor1 graph starting from
some gridcells.

start_begin, start_end:
    begin and end iterators for starting gridcell indices
*/
std::unordered_set<ix_t> avalanche_runout(
    double const *dem_filled,    // Our main source of information on neighbors
    double dem_nodata,
//    ix_t const *neighbor1,    // This optimization is not needed, runout is VERY fast anyway.
    int nj, int ni,     // Not needed, except for bounds checking on neighbor1 lookup
    double const *gt,    // Geotransform
    ix_t const *start_begin, ix_t const *start_end,
    double const min_alpha,
    double const max_runout)
{
    double const min_tan_alpha = tan((M_PI/180.)*min_alpha);

    // Get info on highest-elevation gridcell in the start set.
    // This will also be the most up-slope, and hence will have the highest
    // inclination (alpha angle) compared to downslope gridcells.
    // See: https://www.avalanche-center.org/Education/blog/?itemid=535
    ix_t ix_origin = *std::max_element(start_begin, start_end,
        [dem_filled](int const ix0, int const ix1) { return dem_filled[ix0] < dem_filled[ix1]; });
    double const z_origin = dem_filled[ix_origin];
    int const j_origin = ix_origin / ni;
    int const i_origin = ix_origin % ni;    // Probably compiles down to divmod
    double const x_origin = gt[0] + i_origin*gt[1] + j_origin*gt[2];
    double const y_origin = gt[3] + i_origin*gt[4] + j_origin*gt[5];


    // State of breadth-first-search
    std::unordered_set<ix_t> seen;

    // Current bunch of gridcells we're considering
    
    // -------------------------------------------------------
    auto _elev = [dem_filled,dem_nodata](ix_t ix) -> double
    {
        double ele1 = dem_filled[ix];
        if (ele1 == dem_nodata || ele1 < 0.0) ele1 = 0.0;
        return ele1;
    };
    auto add_neighbor =
        [&seen,gt,min_tan_alpha,max_runout,x_origin,y_origin,z_origin,ni,&_elev]
        (ix_t ix, std::vector<ix_t> &neighbors, bool check_min_alpha) -> void
    {
        // Don't add if we've already seen this neighbor
        if (seen.find(ix) != seen.end()) return;

        // Stop if we've hit the edge of the (valid) domain.
        // Clearly a useful avalanche simulation will not be possible.

        // Obtain geographic coordinates of this gridcell
        int const j = ix / ni;
        int const i = ix % ni;    // Probably compiles down to divmod
        double const x = gt[0] + i*gt[1] + j*gt[2];
        double const y = gt[3] + i*gt[4] + j*gt[5];
        double const delx = x - x_origin;
        double const dely = y - y_origin;
        double const delxy = sqrt(dely*dely + delx*delx);

        // See if we've gone too far.  Some small PRAs ("Tiny")
        // occur at relatively low elevation, and hence alpha will
        // never get down to 18 degrees.  This is especially a problem
        // for PRAs near the edge of the domain.
        if (delxy > max_runout) return;

        if (check_min_alpha) {
            // Compute slope of inclination from the top (tan(alpha))
            double const z = _elev(ix);
            double const delz = z_origin - z;
            double const tan_alpha = delz / delxy;
            // double const alpha = (180./M_PI) * abs(atan2(delz, delxy));

            // Quit if our azimuth (alpha) angle to the top of the
            // avalanche is too small.
    //        printf("tan_alpha %g %g\n", tan_alpha, min_tan_alpha);
            if (tan_alpha < min_tan_alpha) return;
        }

        // OK looks like a good neighbor!
        neighbors.push_back(ix);
        seen.insert(ix);
    };
    // ------------------------------------------------------

    for (std::vector<ix_t> cur(start_begin, start_end); cur.size()>0; ) {
        // Next bunch of gridcells we will be considering
        std::vector<ix_t> neighbors;   // can have duplicates

        // Determine neighbor values of each current node
        // Add to our vector of neighbors if we haven't seen it yet.
        // Also add to our seen set (most efficient this way)
        bool first = true;
        for (ix_t ji0 : cur) {
            if (false) {
            } else {
                // Get our list of neighbors directly from the filled DEM
                std::vector<ix_t> min_ix;
                // Iterate through neighbors of this gridcell
                int const j0 = ji0 / ni;
                int const i0 = ji0 % ni;    // Probably compiles down to divmod

                // Get list of minimum neighbors (that we haven't seen
                // before) based on the 2D DEM
                double min_ele = _elev(ji0);
                min_ix.clear();
                for (auto &dn : dneigh8) {
                    // Avoid outrunning our domain
                    int const j1 = j0 + dn[0];
                    int const i1 = i0 + dn[1];
                    if ((j1<0) || (j1>=nj) || (i1<0) || (i1>=ni)) continue;
                    ix_t const ji1 = j1*ni + i1;

                    // Stop if the runout is leaving our DEM.  There will be no
                    // way to get a realistic avalanche run from it.
                    if (dem_filled[ji1] == dem_nodata) return std::unordered_set<ix_t>();

                    // Unused cells look like elevation 0.0 to us now, same as ocean.
                    // Also, account for dem in case it's giving negative numbers for bathymetry
                    double const ele1 = _elev(ji1);

                    if (ele1 < min_ele) {
                        // Found a new minimum!
                        min_ix.clear();min_ix.push_back(ji1);
                    } else if (ele1 == min_ele) {
                        // Found another equal minimum neighbor
                        min_ix.push_back(ji1);
                    }
                }

                // Add our minimum neighbors to the list of neighbors for next step
                for (ix_t ix : min_ix) add_neighbor(ix, neighbors, !first);
                first = false;
            }
        }

        // cur becomes neighbors
        cur = std::move(neighbors);
    }

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

Also returns sinks: -1 for non-consolidated cells, otherwise ID of the eq class
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
    // auto const nj = PyArray_DIM(dem,0);
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
    PyArrayObject *sinks = (PyArrayObject*) PyArray_NewFromDescr(
        &PyArray_Type, 
        PyArray_DescrFromType(NPY_INT32),             // dtype='i'
        2,                                          // rank 2
        PyArray_DIMS(dem), strides,    // Same shape as DEM
        NULL,        // Allocate new memory
        // PyArray_FLAGS(dem), ...
        NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);

    // ========================================================
    // Do the computation

    PySys_WriteStdout("Filling sinks...\n");
    to_neighbor1(
        DEMNeigh(
            (dem_t *)PyArray_GETPTR2(dem,0,0), PyArray_DIM(dem,0), PyArray_DIM(dem,1), nodata,
            dneigh8),
        (npy_int *)PyArray_GETPTR2(sinks,0,0),
        (npy_int *)PyArray_GETPTR2(neighbor1,0,0));

    // ========================================================
    return Py_BuildValue("OO", (PyObject *)sinks, (PyObject *)neighbor1);
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
//static int ncall = 0;
//static bool trace = false;

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
    PyArrayObject *dem_filled;
    double dem_nodata = 0.0;
    // PyArrayObject *neighbor1;
    PyArrayObject *geotransform;
    PyArrayObject *start;
    double margin = 0;
    int debug = 0;    // bool
    double min_alpha = 18.;    // Minimum "alpha" angle at which avalanche expected to continue
    double max_runout = 10000.;    // Maximum distance avalanche can go [m]

//    printf("BEGIN d8graph_find_domain: %d\n", ncall);
//    trace = (ncall == 438);
//    ++ncall;

    // Parse args and kwargs
    static char const *kwlist[] = {
        "dem_filled", "dem_nodata", //"neighbor1",
        "geotransform", "start",         // *args,
        "margin", "debug", "min_alpha", "max_runout",        // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!dO!O!|didd",
        (char **)kwlist,
        &PyArray_Type, &dem_filled,
        &dem_nodata,
        //&PyArray_Type, &neighbor1,
        &PyArray_Type, &geotransform,
        &PyArray_Type, &start,
        &margin, &debug, &min_alpha, &max_runout
        )) return NULL;

    // ----------- Typecheck input arrays
//    if (!ff_check_input_int(neighbor1, "neighbor1", 2)) return NULL;
    if (!ff_check_input_double(dem_filled, "dem_filled", 2)) return NULL;
//    if (!ff_check_same_dimensions(
//        std::vector<std::pair<PyArrayObject *, std::string>>
//        {{neighbor1, "neighbor1"}, {dem_filled, "dem_filled"}})) return NULL;
    if (!ff_check_input_int(start, "start", 1)) return NULL;
    if (!ff_check_input_double(geotransform, "geotransform", 1)) return NULL;

    // int const nj = PyArray_DIM(dem_filled,0);
    int const ni = PyArray_DIM(dem_filled,1);

//if (trace) printf("BB1\n");
    // ============================ Run the Core Computation
    // Run the flood fill algorithm, result in a set of 1D indices
    std::unordered_set<ix_t> seen(
        avalanche_runout(
            (double *)PyArray_GETPTR2(dem_filled,0,0),
            dem_nodata,
//            (ix_t *)PyArray_GETPTR2(neighbor1,0,0),
            PyArray_DIM(dem_filled,0), PyArray_DIM(dem_filled,1),    // Not needed
            (double *)PyArray_GETPTR1(geotransform, 0),
            (ix_t *)PyArray_GETPTR1(start, 0),
            (ix_t *)PyArray_GETPTR1(start, PyArray_DIM(start,0)),
            min_alpha, max_runout));

//    PySys_WriteStdout("Flood Fill went from %ld -> %ld gridcells.\n", PyArray_DIM(start,0), seen.size());
    // No domain possible if we left the DEM domain in the runout.
    if (seen.size() == 0) { Py_INCREF(Py_None); return Py_None; }

//if (trace) printf("BB2\n");
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

//if (trace) printf("BB3 seen=%ld\n", seen.size());
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
    std::vector<std::array<int,2>> chull_ij(akramms::convex_hull(ij_points));
    // ij_points.clear();    // Free memory  (we need this below if degenerate)

//if (trace) printf("BB4\n");
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

//if (trace) printf("BB5 %ld\n", chull_xy.size());
    // Compute minimum bounding rectangle (MBR) on the convex hull
    PyObject *ret_mbr = nullptr;
    if (chull_xy.size() >= 3) {
        std::vector<std::array<double,2>> mbr(akramms::mbr_chull(chull_xy, margin));
        if (debug) ret_chull_xy = polygon_to_python(chull_xy);
        ret_mbr = polygon_to_python(mbr);
    } else {
        // Degenerate convex hull.  Make something non-degenerate.
        // It doesn't matte whether this is "correct" because the PRA is
        // quite small and the margin (1km) added to it will be MUCH larger.

        // Go back to one of our original seen points.
        // (We know there's at least one point, see code above if seen.size()==0)
        ix_t i = ij_points[0][0];
        ix_t j = ij_points[0][1];

        // Convert to x,y coordinates
        double const x = gt[0] + i*gt[1] + j*gt[2];
        double const y = gt[3] + i*gt[4] + j*gt[5];

        // Make a dummy but small "convex hull" around that one gridcell.
        double const dx = gt[1];
        double const dy = gt[5];
        std::vector<std::array<double,2>> chull_xy2 {
            std::array<double,2>{x-dx,y-dy},
            std::array<double,2>{x-dx,y+dy},
            std::array<double,2>{x+dx,y+dy},
            std::array<double,2>{x+dx,y-dy},
            std::array<double,2>{x-dx,y-dy}};
        if (debug) ret_chull_xy = polygon_to_python(chull_xy2);

        // Create the domain ("mbr" is a misnomer) by adding a margin
        std::vector<std::array<double,2>> mbr(akramms::mbr_chull(chull_xy2, margin));
        ret_mbr = polygon_to_python(mbr);
    }

//    printf("END d8graph_find_domain\n");

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

