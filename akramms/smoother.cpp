#include <Python.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>
//#include "structmember.h"    // Map C struct members to Python attributes

#include <string>
#include <vector>

//#include <akramms/smoother.hpp>
#include <akramms/ulam.hpp>
//#include <akramms/raster.hpp>

static char module_docstring[] = 
"3D Elevation-Aware Gaussian Smoother";

namespace akramms {


/** Computes 1D index offsets of cells within a certain radius of a
    central cell on a regular grid. */
std::vector<std::tuple<std::array<int,2>, double>> oval_offsets(
    double const dx, double const dy,
    //RasterInfo const &gridI,
    double const limit)        // How far in x/y space to go
{
    double const limit2 = limit*limit;
    // Determine how far out on the Ulam spiral we need to go for the
    // template for 3sigma
    int sigma_i = std::ceil(limit/dx);
    int sigma_j = std::ceil(limit/dy);
    int sigma_n = std::max({    // Maximum Ulam index of anything in 2sigma range
        ulam_xy_to_n(sigma_i,0),
        ulam_xy_to_n(-sigma_i,0),
        ulam_xy_to_n(0,sigma_j),
        ulam_xy_to_n(0,-sigma_j)});

    // Generate Gaussian template
    // Pre-compute x^2 + y^2; later add z^2 to compute distance betwen two gridcells in 3-space
    std::vector<std::tuple<std::array<int,2>, double>> offsets;
    for (int n=0; n<=sigma_n; ++n) {
        auto ij = ulam_n_to_xy(n);
        double const ii = ij[0];
        double const jj = ij[1];
        double const x = ii * dx;
        double const y = jj * dy;
        double xydist2 = x*x + y*y;

        // If it's within 2-sigma in the xy plan, it MIGHT also be within 2-sigma in 3-space
        if (xydist2 <= limit2) {
//            printf("off %d (%d, %d) -> %g\n", n, ij[0], ij[1], xydist2);
            offsets.push_back(std::make_tuple(ij, xydist2));
        }
    }

    return offsets;
}


void _smoother_smooth(
    int const nx, int const ny,
    double const dx, double const dy,
    // RasterInfo const &gridI,
    double const *elev,    // 1D array of elevations: elev[jj,ii]; nan for unused gridcells
    std::array<double,3> const &sigma,    // [x, y, z]
    double const *inI,        // Input value on I grid inI[jj, ii]
    // OUTPUT
    double *outI)            // Store output value on I grid HERE outI[jj,ii]
{
    // How far out in Gaussian to go out
    double const nsigma = 2.;    // 2 \sigma in standardized Gaussian
    double const nsigma_squared = nsigma*nsigma;

    // Index offsets to gridcells to consider
    auto offsets(oval_offsets(dx, dy, 2.*std::max(sigma[0], sigma[1])));

    // Loop through destination cells
    //double const area = dx * dy;

    double const by_sigma0 = 1. / sigma[0];
    double const by_sigma1 = 1. / sigma[1];
    double const by_sigma2 = 1. / sigma[2];

    for (int j1=0; j1<ny; ++j1)
    for (int i1=0; i1<nx; ++i1) {
        int const ix1 = j1 * nx + i1;    // ix1 = destination gridcell
        double const elev1 = elev[ix1];
        if (std::isnan(elev1)) continue;

        double sum = 0;
        double sum_weights = 0;
        for (auto &off : offsets) {
            int const deltai = std::get<0>(off)[0];
            int const deltaj = std::get<0>(off)[1];
            double const xydist2 = std::get<1>(off);

            // Find a valid point in the template
            int const i0 = i1 + deltai;
            if ((i0 < 0) || (i0 > nx)) continue;
            int const j0 = j1 + deltaj;
            if ((j0 < 0) || (j0 > ny)) continue;
            int const ix0 = j0 * nx + i0;
            double const elev0 = elev[ix0];
            if (std::isnan(elev0)) continue;


            // Compute a scaled distance metric, based on the radius
            // in each direction
            double const d0 = deltai * dx * by_sigma0;
            double const d1 = deltaj * dy * by_sigma1;
            double const d2 = (elev1 - elev0) * by_sigma2;
            double const norm_distance_squared = d0*d0 + d1*d1 + d2*d2;

            // Make sure we are within range of the scaled Gaussian
            if (norm_distance_squared > nsigma_squared) continue;

#if 0
            // Compute the Gaussian independently in each dimension
            // and multiply to gether.  (Gaussian with diagonal
            // covariance matrix) No need to normalize because we do
            // that empirically
            // https://cs229.stanford.edu/section/gaussians.pdf
#endif   

            // Add to accumulator
            double const weight = std::exp(-.5 * norm_distance_squared);    // Gaussian
//            printf("%d += %g * %d\n", ix1, weight, ix0-ix1);
            sum += inI[ix0] * weight;
            sum_weights += weight;
        }

        // Compute final weight for the smoothing matrix entry: (ix1, ix0)
        outI[ix1] = sum / sum_weights;
    }
}



} // namespace
// =====================================================================
// Python Interface

using namespace akramms;

// -----------------------------------------------------------------
#if 0
/** Simple allocation of 1D Numpy array
shape0:
    Length of array
typenum:
    Type to allocation, eg NPY_INT, NPY_DOUBLE
    https://numpy.org/devdocs/reference/c-api/dtype.html#c.NPY_TYPES
*/
static PyArrayObject *np_new_1d(npy_intp shape0, int typenum)
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
#endif
// ---------------------------------------------------------
static bool check_array(PyArrayObject *_arr, std::string const &name, int const nxy)
{
    char msg[256];    // Error message

    // Check storage
    if (!PyArray_ISCARRAY_RO(_arr)) {
        snprintf(msg, 256, "Parameter %s must be C-style, contiguous array.", name.c_str());
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check type
    if (PyArray_DESCR(_arr)->type_num != NPY_DOUBLE) {
        snprintf(msg, 256, "Parameter %s must have dtype double.", name.c_str());
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check total number of elements (we will flatten to 1D in C++)
    if (PyArray_SIZE(_arr) != nxy) {
        snprintf(msg, 256, "Parameter %s must have %d elements.", name.c_str(), nxy);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    return true;

}
// ---------------------------------------------------------
bool check_sequence(PyObject *_seq, std::string const &name, int len)
{
    char msg[256];    // Error message
    if (PySequence_Length(_seq) != len) {
        snprintf(msg, 256, "%s must have length %d", name.c_str(), len);
        PyErr_SetString(PyExc_TypeError, msg);

        return false;
    }
    return true;
}


template<int len>
std::array<double, len> fixed_sequence(PyObject *_seq)
{
    std::array<double, len> arr;
    for (int i=0; i<len; ++i) {
        PyObject *ele = PySequence_GetItem(_seq, i);
        arr[i] = PyFloat_AsDouble(ele);
        Py_DECREF(ele);
    }
    return arr;
}
// ---------------------------------------------------------
static char const *smoother_smooth_docstring =
R"(SMoother Function Docstring
)";
static PyObject *smoother_smooth(PyObject *module, PyObject *args, PyObject *kwargs)
{
    int nx, ny;
    double dx, dy;
    //PyObject *_geotransform;    // Geotransform
    PyArrayObject *_elev;
    PyObject *_sigma;
    PyArrayObject *_inI;

    // Parse args and kwargs
    static char const *kwlist[] = {
        // *args
        "nx", "ny", "dx", "dy", "elev", "sigma", "inI",
        // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "iiddO!OO!|",
        (char **)kwlist,
        &nx, &ny,
        &dx, &dy,
        // &_geotransform,
        &PyArray_Type, &_elev,
        &_sigma,
        &PyArray_Type, &_inI
        )) return NULL;

    // -------------------------- Convert Args to C++
    // ----- geotransform
    //if (!check_sequence(_geotransform, "geotransform", 6)) return NULL;
    //std::array<double,6> const geotransform(fixed_sequence<6>(_geotransform));

    // ----- gridI
    //RasterInfo const gridI("", nx, ny, geotransform);
    int const nxy = nx * ny;

    // ----- elev
    if (!check_array(_elev, "elev", nxy)) return NULL;
    double const * const elev((double *)PyArray_DATA(_elev));

    // ----- sigma
    if (!check_sequence(_sigma, "sigma", 3)) return NULL;
    std::array<double,3> const sigma(fixed_sequence<3>(_sigma));

    // ----- inI
    if (!check_array(_inI, "inI", nxy)) return NULL;
    double const * const inI((double *)PyArray_DATA(_inI));

    // ------------------------------------------------------------------------
    // Run it
    PyArrayObject *_outI = (PyArrayObject *)PyArray_NewLikeArray(_inI, NPY_KEEPORDER, NULL, 0);
    double * const outI((double *)PyArray_DATA(_outI));
    _smoother_smooth(nx, ny, dx, dy, elev, sigma, inI, outI);

    // ------------------------------------------------------------------------
    // Return created array
    return (PyObject *)_outI;
}

// ============================================================
// Random other Python C Extension Stuff
static PyMethodDef SmootherMethods[] = {
    {"smooth",
        (PyCFunction)smoother_smooth,
        METH_VARARGS | METH_KEYWORDS, smoother_smooth_docstring},

    // Sentinel
    {NULL, NULL, 0, NULL}
};


/* This initiates the module using the above definitions. */
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "smoother",    // Name of module
    module_docstring,    // Per-module docstring
    -1,  /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    SmootherMethods,    // Functions
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


PyMODINIT_FUNC PyInit_smoother(void)
{
//    // TODO: Disable this in production so it doesn't interfere with
//    // Python interpreter in general.
//    signal(SIGSEGV, handler);   // install our handler

    import_array();    // Needed for Numpy

    return PyModule_Create(&moduledef);
}

