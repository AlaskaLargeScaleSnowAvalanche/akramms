#include <icebin/smoother.hpp>
#include <akramms/ulam.hpp>

static char module_docstring[] = 
"3D Elevation-Aware Gaussian Smoother";

namespace icebin {


/** Computes 1D index offsets of cells within a certain radius of a
    central cell on a regular grid. */
std::vector<std::tuple<std::array<int,2>, double>> oval_offsets(
    RasterInfo const &gridI,
    double const limit)        // How far in x/y space to go
{
    double const limit2 = limit*limit;
    // Determine how far out on the Ulam spiral we need to go for the
    // template for 3sigma
    int sigma_i = int(std::ceil(limit/gridI.dx))
    int sigma_j = int(std::ceil(limit/gridI.dy))
    sigma_n = std::max({    // Maximum Ulam index of anything in 2sigma range
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
        double const x = ii * gridI.dx;
        double const y = jj * gridI.dy;
        double xydist2 = x*x + y*y;

        // If it's within 2-sigma in the xy plan, it MIGHT also be within 2-sigma in 3-space
        if (xydist2 <= limit2) {
            offsets.push_back(std::make_tuple(ij, xydist2));
        }
    }

    return offsets;
}


void _smoother_smooth(
    RasterInfo const &gridI,
    double const *elev_s,    // 1D array of elevations: elev_s[jj,ii]
    std::array<double,3> const &sigma,    // [x, y, z]
    double const *inI,        // Input value on I grid inI[jj, ii]
    // OUTPUT
    double *outI)            // Store output value on I grid HERE outI[jj,ii]
{
    // Index offsets to gridcells to consider
    auto offsets(oval_offsets(gridI, 2.*sigma));

    // Loop through destination cells
    double const area = gridI.dx * gridI.dy;

    for (int j1=0; j1<gridI.ny; ++j1)
    for (int i1=0; i1<gridI.nx; ++i1) {
        int const ix1 = j1 * gridI.nx + i1;    // ix1 = destination gridcell
        double const elev1 = elev_s[ix1];
        if (std::isnan(elev1)) continue;

        double sum = 0;
        int n = 0;
        for (auto &off : offsets_ix) {
            int const deltai = std::get<0>(off)[0];
            int const deltaj = std::get<0>(off)[1];
            double const xydist2 = std::get<1>(off);

            // Find a valid point in the template
            int const i0 = i1 + deltai;
            if ((i0 < 0) || (i0 > gridI.nx)) continue;
            int const j0 = j1 + deltaj;
            if ((j0 < 0) || (j0 > gridI.ny)) continue;
            ix0 = i0 * gridI.nx + j1;
            double const elev0 = elev_s[ix0];
            if (std::isnan(elev0)) continue;

            // Determine distance for Gaussian function
            // offsets_ij[0]*offsets_ij[0] + offsets_ij[1]*offsets_ij[1] + ...
            double const delta_elev = (elev1 - elev0);
            double const xyzdist2 = xydist2[ix0] + delta_elev * delta_elev;

            // Add to accumulator
            sum += inI[ix0] * std::exp(-.5 * xyzdist2);
            ++n;
        }

        // Compute final weight for the smoothing matrix entry: (ix1, ix0)
        outI[ix1] = sum / (double)n;
    }
}



} // namespace
// =====================================================================
// Python Interface

using namespace akramms;

// ----------------------------------------------------------------------------------------
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
// ---------------------------------------------------------
static char const *smoother_matrix_docstring =
R"SMoother Matrix Docstring
";
static PyObject *smoother_matrix(PyObject *module, PyObject *args, PyObject *kwargs)
{
    char msg[256];    // Error message

    int nx, ny;
    PyObject *_geotransform;    // Geotransform
    PyArrayObject *_elev;
    PyObject *_sigma;

    // Parse args and kwargs
    static char const *kwlist[] = {NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "iiOO!O|",
        (char **)kwlist,
        &PyArray_Type, &dem_filled,
        &dem_nodata,
        //&PyArray_Type, &neighbor1,
        &_geotransform,
        &PyArray_Type, &_elev,
        &_sigma
        )) return NULL;

    // -------------------------- Convert Args to C++
    // ----- geotransform
    std::array<double, 6> geotransform;
    if PySequence_Length(_geotransform) != 6 {
        PyErr_SetString(PyExc_TypeError, "geotransform must have length 6");
        return NULL;
    }
    for (int i=0; i<6; ++i) {
        PyObject *ele = PySequence_GetItem(_geotransform, i);
        geotransform[i] = PyFloat_AsDouble(ele);
        Py_DECREF(ele);
    }

    // ----- gridI
    RasterInfo const gridI("", nx, ny, geotransform);
    int nxy = gridI.nx * gridI.ny;

    // ----- elev
    double const *elev;

    // Check storage
    if (!PyArray_ISCARRAY_RO(_elev)) {
        snprintf(msg, 256, "Parameter elev must be C-style, contiguous array.");
        PyErr_SetString(PyExc_TypeError, msg);
        return NULL;
    }

    // Check type
    if (PyArray_DESCR(_elev)->type_num != NPY_DOUBLE) {
        snprintf(msg, 256, "Parameter elev must have dtype double.");
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check total number of elements (we will flatten to 1D in C++)
    if (PyArray_SIZE(_elev) != nxy) {
        snprintf(msg, 256, "Parameter elev must have %d elements.", nxy);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    double const * const elev((double *)PyArray_DATA(_elev));

    // ----- sigma
    std::array<double, 3> sigma;
    if PySequence_Length(_sigma) != 3 {
        PyErr_SetString(PyExc_TypeError, "sigma must have length 3");
        return NULL;
    }
    for (int i=0; i<6; ++i) {
        PyObject *ele = PySequence_GetItem(_sigma, i);
        sigma[i] = PyFloat_AsDouble(ele);
        Py_DECREF(ele);
    }

    // ------------------------------------------------------------------------
    // Run it
    std::vector<int> _js;
    std::vector<int> _is;
    std::vector<double> _vals;
    _smoother_matrix_RasterInfo(gridI, elev, sigma, _js, _is, _vals);

    // ------------------------------------------------------------------------
    // Convert results to Python
    PyArrayObject *is = np_new_1d((npy_intp)_is.size(), NPY_INT32);
    PyArrayObject *js = np_new_1d((npy_intp)_js.size(), NPY_INT32);
    PyArrayObject *vals = np_new_1d((npy_intp)_vals.size(), NPY_FLOAT);
    int *is0 = PyArray_DATA(is);
    int *js0 = PyArray_DATA(js);
    int *vals0 = PyArray_DATA(vals);
    for (size_t i=0; i<_vals.size(); ++i) {
        is0[i] = _is[i];
        js0[i] = _js[i];
        vals0[i] = _vals[i];
    }

    // return (vals, (is, js)) for scipy.sparse.coo_matrix()
    return PyTuple_Pack(2, vals0,
        PyTubple_Pack(2, is0, js0));

}

// ============================================================
// Random other Python C Extension Stuff
static PyMethodDef SmootherMethods[] = {
    {"matrix",
        (PyCFunction)smoother_matrix,
        METH_VARARGS | METH_KEYWORDS, smoother_matrix_docstring},

    // Sentinel
    {NULL, NULL, 0, NULL}
};


/* This initiates the module using the abo🙃ve definitions. */
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_smoother",    // Name of module
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

