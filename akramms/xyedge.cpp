#include <Python.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>
//#include "structmember.h"    // Map C struct members to Python attributes

#include <cstdint>
#include <string>
#include <algorithm>    // std::max
#include <memory>

#include "nputil.hpp"

static char module_docstring[] = 
"Determine Avalanche gridcells that constitute overrun";

namespace akramms {

// Must match domain_mask.py
enum DomainMaskValue {
    MASK_OUT = 0,      // Not part of the domain
    MARGIN = 1,        // Avalanches can flow in here, but not start here
    MASK_IN = 2        // Avalanches can start here
};


/** Identifies the gridcells for a local avalanche run that:

  a) Have fewer than 4 neighbors (meaning, they are on the edge of the
     local avalanche domain).

       and

  b) In the wider tile domain for the scene, they do NOT border a
     masked-out gridcell (eg. Canada).

  This designates the set of cells that, if the avalanche ended in,
  then an overrun should be declared.
*/
void oedge(
    // Info on the gridcells within gridA represented by RAMMS
    int const ngridA,    // Number of gridcells for this avalanche
    int32_t *iAs,    // 
    int32_t *jAs,    // (0-based, this was determined from (x,y) values)

    // Info on subdomain tile the avalanche ran in
    int gridA_nx, int gridA_ny,

    // The domain mask
    char *domain_maskA,

    // OUTPUT: same dimension as iA/jA
    char *oedgeA)    // Is it an edge gridcell matching (a) and (b) criteria?
{


printf("AA1 %d\n", ngridA);
printf("%p %p %p %p\n", iAs, jAs, domain_maskA, oedgeA);

    // Determine limits of gridcells used so we can create a subgrid for them.
    int mini=0, minj=0;
    int maxi=std::numeric_limits<int>::max();
    int maxj=std::numeric_limits<int>::max();
    for (int k=0; k<ngridA; ++k) {
printf("ffff %d %d\n", iAs[k], jAs[k]);
        mini = std::min(mini, iAs[k]);
        maxi = std::max(maxi, iAs[k]);
        minj = std::min(minj, jAs[k]);
        maxj = std::max(maxj, jAs[k]);
    }

printf("AA2\n");

    // Creates subgrid S with just those limits (and one gridcell margin)
    int const i0 = mini - 1;
    int const i1 = maxi + 2;    // Range is [i0, i1)
    int const ni = i1-i0;
    int const j0 = minj - 1;
    int const j1 = maxj + 2;
    int const nj = j1-j0;

printf("AA3 %d %d %d %d %d %d\n", i0, i1, ni, j0, j1, nj);
    // Create 0/1 raster on subgrid indicating which gridcells are in the Avalanche domain.
    std::unique_ptr<char[]> xygrid(new char[nj*ni]);
printf("AA3.1\n");
    for (int k=0; k<nj*ni; ++k) xygrid[k] = 0;
printf("AA3.2\n");
    for (int k=0; k<ngridA; ++k) {
        int const jj = jAs[k] - j0;
        int const ii = iAs[k] - i0;
        int const ix = jj*ni + ii;
        if ((ix < 0) || (ix >= nj*ni))
            printf("ix out of bounds %d\n", ix);
        xygrid[ix] = 1;
    }

printf("AA4\n");
    // Compute the number of neighbors (0-4) of each gridcell in A
    std::unique_ptr<char[]> nneighbor(new char[nj*ni]);
    for (int k=0; k<nj*ni; ++k) nneighbor[k] = 0;
    for (int k=0; k<ngridA; ++k) {
        int const jj = jAs[k] - j0;
        int const ii = iAs[k] - i0;
        int const ix = jj*ni + ii;
        nneighbor[ix] = xygrid[ix-1] + xygrid[ix+1] + xygrid[ix-ni] + xygrid[ix+ni];
    }


printf("AA5\n");
    // Apply the condition to determine which gridcells are on a
    // domain edge that would be solved if we enlarge the domain.
//    int const gridA_nxy = gridA_nx * gridA_ny;
    for (int k=0; k<ngridA; ++k) {
        int const jj = jAs[k] - j0;
        int const ii = iAs[k] - i0;
        int const ix = jj*ni + ii;

        oedgeA[k] = 0;

        // It's an interior cell of the Avalanche sub-grid ==> NOT an oedge
        if (nneighbor[ix] == 4) continue;

        // Look at the domain mask
        int const dix = jAs[k]*gridA_nx + iAs[k];
        const int offset[] = {1, -1, gridA_nx, -gridA_nx};
        for (int kk=0; kk<4; ++kk) {
            int const dix1 = dix + offset[kk];
            // Check "neighbor" dix1 is on the grid
            if ((dix1 < 0) || (dix1 > gridA_nx * gridA_ny)) continue;

            // If any neighbor is masked out (Canada), this is NOT an oedge.
            // Because if Canada weren't there, the Avalanche domain could extend
            // further
            if (domain_maskA[dix1] == DomainMaskValue::MASK_OUT) goto continue_outer;
        }

        // This gridcell IS an oedge: meaning, if you touch this gridcell then you have
        // a genuine overrun.
        oedgeA[k] = 1;

    continue_outer: ;
    }

printf("AA6\n");

}

} // namespace
// =====================================================================
// Python Interface

using namespace akramms;

// -----------------------------------------------------------------
static char const *xyedge_oedge_docstring =
R"(Identifies the gridcells for a local avalanche run that:

  a) Have fewer than 4 neighbors (meaning, they are on the edge of the
     local avalanche domain).

       and

  b) In the wider tile domain for the scene, they do NOT border a
     masked-out gridcell (eg. Canada).

  This designates the set of cells that, if the avalanche ended in,
  then an overrun should be declared.)";
static PyObject *xyedge_oedge(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // Info on the gridcells within gridA represented by RAMMS
    //int ngridA;    // Number of gridcells for this avalanche
    PyArrayObject *iAs;    // Diff-encoded (i,j) of those gridcells
    PyArrayObject *jAs;    // (0-based, this was determined from (x,y) values)

    // Info on subdomain tile the avalanche ran in
    int gridA_nx, gridA_ny;


    // The domain mask
    PyArrayObject *domain_maskA;

    // OUTPUT: mosaic variables [gridM_ny, gridM_nx]
    // PyArrayObject *oedgeA;

    // Parse args and kwargs
    static char const *kwlist[] = {
        // *args
        "iAs", "jAs",
        "gridA_nx", "gridA_ny",
        "domain_maskA",
        // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!O!iiO!|",
        (char **)kwlist,

            &PyArray_Type, &iAs,
            &PyArray_Type, &jAs,

        &gridA_nx, &gridA_ny,

            &PyArray_Type, &domain_maskA
        )) return NULL;

    // -------------------------- Typecheck and Bounds Check
    int const ngridA = PyArray_SIZE(iAs);
    if (!check_array(iAs, "iAs", NPY_INT, "NPY_INT", ngridA)) return NULL;
    if (!check_array(jAs, "jAs", NPY_INT, "NPY_INT", ngridA)) return NULL;

    if (!check_array(domain_maskA, "domain_maskA", NPY_BYTE, "NPY_BYTE", gridA_nx*gridA_ny)) return NULL;

    PyArrayObject *oedgeA = np_new_1d((npy_intp)ngridA, NPY_BYTE);

    // ------------------------------------------------------------------------
    oedge(
        ngridA,
            (int32_t *)PyArray_DATA(iAs),
            (int32_t *)PyArray_DATA(jAs),
        gridA_nx, gridA_ny,
            (char *)PyArray_DATA(domain_maskA),
            (char *)PyArray_DATA(oedgeA));

    return (PyObject *)oedgeA;
}

// ============================================================
// Random other Python C Extension Stuff
static PyMethodDef _XyedgeMethods[] = {
    {"oedge",
        (PyCFunction)xyedge_oedge,
        METH_VARARGS | METH_KEYWORDS, xyedge_oedge_docstring},

    // Sentinel
    {NULL, NULL, 0, NULL}
};


/* This initiates the module using the above definitions. */
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "xyedge",    // Name of module
    module_docstring,    // Per-module docstring
    -1,  /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    _XyedgeMethods,    // Functions
    NULL,
    NULL,
    NULL,
    NULL
};

//extern "C" void handler(int sig) {
//  void *array[10];
//  size_t size;
//
//  // get void*'s for all entries on the stack
//  size = backtrace(array, 10);
//
//  // print out all the frames to stderr
//  PySys_WriteStderr("Error: signal %d:\n", sig);
//  backtrace_symbols_fd(array, size, STDERR_FILENO);
//  exit(1);
//}


PyMODINIT_FUNC PyInit_xyedge(void)
{
//    // TODO: Disable this in production so it doesn't interfere with
//    // Python interpreter in general.
//    signal(SIGSEGV, handler);   // install our handler

    import_array();    // Needed for Numpy

    return PyModule_Create(&moduledef);
}

