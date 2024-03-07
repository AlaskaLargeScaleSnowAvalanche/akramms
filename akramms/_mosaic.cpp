#include <Python.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>
//#include "structmember.h"    // Map C struct members to Python attributes

#include <cstdint>
#include <string>
#include <algorithm>    // std::max

#include "nputil.hpp"

static char module_docstring[] = 
"Core AKRAMMS Mosaic Code";

namespace akramms {

void mosaic_mosaic(
    // Info on the gridcells within gridA represented by RAMMS
    int const ngridA,    // Number of gridcells for this avalanche
    int32_t *i_diff,    // Diff-encoded (i,j) of those gridcells
    int32_t *j_diff,    // (0-based, this was determined from (x,y) values)

    // Info on subdomain tile the avalanche ran in
    double gridA_x0, double gridA_y0,    // gridA_gt[0], gridA_gt[3]

    // Data from the Avalanche .out file [ngridA]
    float *max_velA,
    float *max_heightA,
    float *depoA,

    // Constants
    double const rho,

    // Info on the overall mosaic grid
    int gridM_nx, double gridM_x0, double gridM_dx,
    int gridM_ny, double gridM_y0, double gridM_dy,

    // OUTPUT: mosaic variables [gridM_ny, gridM_nx]
    float *depositionM,
    float *max_heightM,
    float *max_velocityM,
    float *max_pressureM,
    int16_t *domain_countM,
    int16_t *avalanche_countM)
{
    int const deltai = std::lround(-(gridM_x0 - gridA_x0) / gridM_dx);
    int const deltaj = std::lround(-(gridM_y0 - gridA_y0) / gridM_dy);

    PySys_WriteStdout("(deltai, deltaj) = (%d, %d)\n", deltai, deltaj);
    PySys_WriteStdout("deltai: %f %f\n", -(gridM_x0 - gridA_x0), gridM_dx);

    int iA = 0;    // Current index in gridA
    int jA = 0;
    for (int kA=0; kA<ngridA; ++kA) {
        // Decode (i,j) indices from cumulative sum
        iA += i_diff[kA];
        jA += j_diff[kA];

        // Convert to (i,j) indices in gridM
        int const iM = iA + deltai;
        int const jM = jA + deltaj;

        // Skip gridcells outside the mosaic bounds
        if ((iM < 0) || (iM >= gridM_nx) || (jM < 0) || (jM >= gridM_ny)) continue;

        // Convert to 1-D index in gridM
        int const jiM = jM * gridM_nx + iM;

        // Update variables for all gridcells in the avalanche domain
        domain_countM[jiM] += 1;

        // Update variables for only used gridcells in avalanche domain
//        used = false;
//        if (max_velA[kA] > 0) {

        avalanche_countM[jiM] += 1;
        depositionM[jiM] = std::max(depositionM[jiM], depoA[kA]);
        max_heightM[jiM] = std::max(max_heightM[jiM], max_heightA[kA]);
        max_velocityM[jiM] = std::max(max_velocityM[jiM], max_velA[kA]);

        double const _max_vel = max_velA[kA];
        max_pressureM[jiM] = std::max(
            max_pressureM[jiM], (float)(rho * _max_vel * _max_vel));
    }
}



} // namespace
// =====================================================================
// Python Interface

using namespace akramms;

// -----------------------------------------------------------------
static char const *_mosaic_mosaic_docstring =
R"(_Mosaic Function Docstring
)";
static PyObject *_mosaic_mosaic(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // Info on the gridcells within gridA represented by RAMMS
    //int ngridA;    // Number of gridcells for this avalanche
    PyArrayObject *i_diff;    // Diff-encoded (i,j) of those gridcells
    PyArrayObject *j_diff;    // (0-based, this was determined from (x,y) values)

    // Info on subdomain tile the avalanche ran in
    double gridA_x0; double gridA_y0;    // gridA_gt[0], gridA_gt[3]

    // Data from the Avalanche .out file [ngridA]
    PyArrayObject *max_velA;
    PyArrayObject *max_heightA;
    PyArrayObject *depoA;

    // Constants
    double rho;

    // Info on the overall mosaic grid
    int gridM_nx; double gridM_x0; double gridM_dx;
    int gridM_ny; double gridM_y0; double gridM_dy;

    // OUTPUT: mosaic variables [gridM_ny, gridM_nx]
    PyArrayObject *depositionM;
    PyArrayObject *max_heightM;
    PyArrayObject *max_velocityM;
    PyArrayObject *max_pressureM;
    PyArrayObject *domain_countM;
    PyArrayObject *avalanche_countM;

    // Parse args and kwargs
    static char const *kwlist[] = {
        // *args
        /*"ngridA",*/ "i_diff", "j_diff",
        "gridA_x0", "gridA_y0",
        "max_velA", "max_heightA", "depoA",
        "rho",
        "gridM_nx", "gridM_x0", "gridM_dx",
        "gridM_ny", "gridM_y0", "gridM_dy",
        "depositionM", "max_heightM", "max_velocityM", "max_pressureM", "domain_countM", "avalanche_countM",
        // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!O!ddO!O!O!diddiddO!O!O!O!O!O!|",
        (char **)kwlist,

        //&ngridA,
            &PyArray_Type, &i_diff,
            &PyArray_Type, &j_diff,

        &gridA_x0, &gridA_y0,

            &PyArray_Type, &max_velA,
            &PyArray_Type, &max_heightA,
            &PyArray_Type, &depoA,

        &rho,

        &gridM_nx, &gridM_x0, &gridM_dx,
        &gridM_ny, &gridM_y0, &gridM_dy,

            &PyArray_Type, &depositionM,
            &PyArray_Type, &max_heightM,
            &PyArray_Type, &max_velocityM,
            &PyArray_Type, &max_pressureM,
            &PyArray_Type, &domain_countM,
            &PyArray_Type, &avalanche_countM
        )) return NULL;

    // -------------------------- Typecheck and Bounds Check
    int const ngridA = PyArray_SIZE(i_diff);
    if (!check_array(i_diff, "i_diff", NPY_INT, "NPY_INT", ngridA)) return NULL;
    if (!check_array(j_diff, "j_diff", NPY_INT, "NPY_INT", ngridA)) return NULL;

    if (!check_array(max_velA, "max_velA", NPY_FLOAT, "NPY_FLOAT", ngridA)) return NULL;
    if (!check_array(max_heightA, "max_heightA", NPY_FLOAT, "NPY_FLOAT", ngridA)) return NULL;
    if (!check_array(depoA, "depoA", NPY_FLOAT, "NPY_FLOAT", ngridA)) return NULL;

    int const nxyM = gridM_nx * gridM_ny;
    if (!check_array(depositionM, "depositionM", NPY_FLOAT, "NPY_FLOAT", nxyM)) return NULL;
    if (!check_array(max_heightM, "max_heightM", NPY_FLOAT, "NPY_FLOAT", nxyM)) return NULL;
    if (!check_array(max_velocityM, "max_velocityM", NPY_FLOAT, "NPY_FLOAT", nxyM)) return NULL;
    if (!check_array(max_pressureM, "max_pressureM", NPY_FLOAT, "NPY_FLOAT", nxyM)) return NULL;
    if (!check_array(domain_countM, "domain_countM", NPY_INT16, "NPY_INT16", nxyM)) return NULL;
    if (!check_array(avalanche_countM, "avalanche_countM", NPY_INT16, "NPY_INT16", nxyM)) return NULL;

    // ------------------------------------------------------------------------
    mosaic_mosaic(
        ngridA,
            (int32_t *)PyArray_DATA(i_diff),
            (int32_t *)PyArray_DATA(j_diff),
        gridA_x0, gridA_y0,
            (float *)PyArray_DATA(max_velA),
            (float *)PyArray_DATA(max_heightA),
            (float *)PyArray_DATA(depoA),
        rho,
        gridM_nx, gridM_x0, gridM_dx,
        gridM_ny, gridM_y0, gridM_dy,
            (float *)PyArray_DATA(depositionM),
            (float *)PyArray_DATA(max_heightM),
            (float *)PyArray_DATA(max_velocityM),
            (float *)PyArray_DATA(max_pressureM),
            (int16_t *)PyArray_DATA(domain_countM),
            (int16_t *)PyArray_DATA(avalanche_countM));

    Py_RETURN_NONE;
}

// ============================================================
// Random other Python C Extension Stuff
static PyMethodDef _MosaicMethods[] = {
    {"mosaic",
        (PyCFunction)_mosaic_mosaic,
        METH_VARARGS | METH_KEYWORDS, _mosaic_mosaic_docstring},

    // Sentinel
    {NULL, NULL, 0, NULL}
};


/* This initiates the module using the above definitions. */
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "_mosaic",    // Name of module
    module_docstring,    // Per-module docstring
    -1,  /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
    _MosaicMethods,    // Functions
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


PyMODINIT_FUNC PyInit__mosaic(void)
{
//    // TODO: Disable this in production so it doesn't interfere with
//    // Python interpreter in general.
//    signal(SIGSEGV, handler);   // install our handler

    import_array();    // Needed for Numpy

    return PyModule_Create(&moduledef);
}

