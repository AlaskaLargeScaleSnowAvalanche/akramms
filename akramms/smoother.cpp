#include <icebin/smoother.hpp>

static char module_docstring[] = 
"3D Elevation-Aware Gaussian Smoother";

namespace icebin {

Smoother::~Smoother() {}

// ---------------------------------------------------------
Smoother::Smoother(std::vector<Smoother::Tuple> &&_tuples,
    std::array<double,3> const &_sigma) :
    nsigma(2.),
    nsigma_squared(nsigma*nsigma),
    sigma(_sigma),
    tuples(std::move(_tuples))
{
    // Create an RTree and insert our tuples into it
    for (auto t(tuples.begin()); t != tuples.end(); ++t) {
        rtree.Insert(&t->centroid[0], &t->centroid[0], &*t);
    }
}
// -----------------------------------------------------------
/** Inner loop for Smoother::matrix() */
bool Smoother::matrix_callback(Smoother::Tuple const *t)
{
    // t0 = point from outer loop
    // t = point from innter loop

    // Compute a scaled distance metric, based on the radius in each direction
    double norm_distance_squared = 0;
    for (int i=0; i<3; ++i) {
        double const d = (t->centroid[i] - t0->centroid[i]) / sigma[i];
        norm_distance_squared += d*d;
    }

    if (norm_distance_squared < nsigma_squared) {
        double const gaussian_ij = std::exp(-.5 * norm_distance_squared);
        double w = gaussian_ij * t->area;
        M_raw.push_back(std::make_pair(t->iX_d, w));
        denom_sum += w;
    }
    return true;
}

void Smoother::matrix(std::vector<int> &js, std::vector<int> &is, std::vector<double> &vals)
{
    using namespace std::placeholders;  // for _1, _2, _3...

    RTree::Callback callback(std::bind(&Smoother::matrix_callback, this, _1));
    for (auto _t0(tuples.begin()); _t0 != tuples.end(); ++_t0) {
        t0 = &*_t0;
        M_raw.clear();
        denom_sum = 0;

        // Pair t0 with nearby points
        std::array<double,3> min, max;
        for (int i=0; i<3; ++i) {
            min[i] = t0->centroid[i] - nsigma*sigma[i];
            max[i] = t0->centroid[i] + nsigma*sigma[i];
        }
        rtree.Search(min, max, callback);

        // Add to the final matrix
        double factor = 1. / denom_sum;
        for (auto ii=M_raw.begin(); ii != M_raw.end(); ++ii) {
            iis.push_back(t0->iX_d);
            jjs.push_back(ii->first);
            vals.push_back(factor * ii->second);
            // ret.add({t0->iX_d, ii->first}, factor * ii->second);
        }
    }
}
// -----------------------------------------------------------
void _smoother_matrix_RasterInfo(
    RasterInfo const &gridI,
    double const *elev_s,    // 1D array of elevations: elev_s[jj,ii]
    std::array<double,3> const &sigma,
    // OUTPUT
    std::vector<int> &js,
    std::vector<int> &is,
    std::vector<double> &vals)
{
    std::vector<Smoother::Tuple> tuples;
    double const area = gridI.dx * gridI.dy;

    for (int jj=0; jj<gridI.ny; ++jj)
    for (int ii=0; ii<gridI.nx; ++ii) {
        int iX_s = jj * gridI.nx + ii;

        // Ignore masked-out gridcells (in case dimX (dimI) includes all ice gridcells)
        double const elev(elev_s(iX_s));
        if (std::isnan(elev)) continue;

        //auto iX_d(dimX.to_dense(iX_s));

        tuples.push_back(Smoother::Tuple(iX_s, gridI.to_xy(ii, jj), elev, area));
    }
    Smoother smoother(std::move(tuples), sigma);
    smoother.matrix(js, is, vals);
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

