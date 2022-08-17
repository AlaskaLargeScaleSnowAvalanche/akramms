#define PY_SSIZE_T_CLEAN
// https://stackoverflow.com/questions/39760887/warning-message-when-including-numpy-arryobject-h
//#define NPY_NO_DEPRECATED_API 
#include <Python.h>                // Must be first
#include <numpy/arrayobject.h>
#include <cstdio>
#include <cmath>


static char module_docstring[] = "\
D8graph 1.1.0 module computes the Canada Fire Index on a gridded dataset.";

// For help with Python extension:
// https://stackoverflow.com/questions/56182259/how-does-one-acces-numpy-multidimensionnal-array-in-c-extensions
// https://www.oreilly.com/library/view/python-cookbook/0596001673/ch16s06.html
// https://docs.python.org/3/extending/newtypes_tutorial.html


// =====================================================================
static char *D8Graph_docstring = "D8Graph Class Docstring";

typedef struct {
    PyObject_HEAD
} D8GraphObject;

static PyTypeObject D8GraphType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "dggs.D8Graph",
    .tp_doc = PyDoc_STR(D8Graph_docstring),
    .tp_basicsize = sizeof(D8GraphObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_new = PyType_GenericNew,
};


// ===================================================================
// Python version of the D8Graph class
static char D8Graph_init_docstring[] = "\
D8Graph.__init__(self, dem):\n\
\n\
Positional Args:\n\
    dem: np.array(nj, ni)\n\
        The digital elevation model; also defines the domain.\n\
Keyword Args:\n\
    max_sink_size=10:\n\
        Don't merge sinks larger than this.\n\
";
static PyObject* D8Graph_init(PyObject *self, PyObject *args)
{
    // Input arrays
    PyArrayObject *dem;
    int max_sink_size = 10;

    // Parse args and kwargs
    static char *kwlist[] = {
        "dem",         // *args,
        "max_sink_size",    // **kwargs
        NULL};
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!|n",
        kwlist,
        &PyArray_Type, &dem,
        &max_sink_size
        )) return NULL;

    // -----------------------------------------
    // Typecheck
    // Check type
    if (PyArray_DESCR(dem)->type_num != NPY_DOUBLE) {
        PyErr_SetString(PyExc_TypeError, "Input dem must have type double");
        return NULL;
    }

    // Check rank
    if (PyArray_NDIM(dem) != 2) {
        PyErr_SetString(PyExc_TypeError, "Input dem must have rank 2");
        return false;
    }

    // -----------------------------------------
    // Collapse space dimensions

#if 0
// Probably not needed
    // Save original shape
    int ndim0 = PyArray_NDIM(dem);
    npy_intp const ntime = PyArray_DIM(dem, ndim0-1);
    npy_intp _dims0[ndim0];
    for (int j=0; j<ndim0; ++j) _dims0[j] = PyArray_DIM(dem,j);
    PyArray_Dims shape0 = {_dims0, ndim0};
#endif

    // Reshape to rank 1
    npy_intp nji = PyArray_DIM(dem,0) * PyArray_DIM(dem,1);
    PyArray_Dims shape1 = {nji};
    PyArrayObject *dem1d = (PyArrayObject *)PyArray_Newshape(dem, &shape1, NPY_CORDER);
    if (!dem1d) return NULL;


    // Reference Counting
    // https://stackoverflow.com/questions/4657764/py-incref-decref-when





    printf("D8Graph.__init__ called\n");
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject* D8Graph_doSomething(PyObject *self, PyObject *args)
{
    printf("D8Graph.doSomething called\n");
    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef D8GraphMethods[] =
{
    {"__init__", D8Graph_init, METH_VARARGS, "doc string"},
    {"doSomething", D8Graph_doSomething, METH_VARARGS, "doc string"},
    {0, 0},
};


// ===================================================================
// The Python-callable method

static char d8graph_d8graph_docstring[] = ""

static PyObject* d8graph_d8graph(PyObject *module, PyObject *args, PyObject *kwargs)
{
    // Input arrays
    PyArrayObject *tin;  // Temperature [C]
    PyArrayObject *hin;  // Relative Humidity [%, 0-100]
    PyArrayObject *win;  // Wind speed [km/h]
    PyArrayObject *rin;  // 24-hour integrated rain [mm]
    PyArrayObject *imonth = NULL;    // Month of each point in time
    int debug = 0;          // Optional kwarg, are we debugging?
    double ffmc00 = 85.5;    // Initial fine fuel moisture code (FMC)
    double dmc00 = 6.0;      // Initial duff moister code (DMC)
    double dc00 = 15.0;      // Initial drought code (DC)
    PyArrayObject *mask_out = NULL;
    double fill_value = -1.e10;    // Value for masked-out gridcells

    // List must include ALL arg names, including positional args
    static char *kwlist[] = {
        "tin", "hin", "win", "rin",    // *args
        "imonth", "ffmc0", "dmc0", "dc0", "debug",         // **kwargs
        "mask_out", "fill_value",
        NULL};
    // -------------------------------------------------------------------------    
    /* Parse the Python arguments into Numpy arrays */
    // p = "predicate" for bool: https://stackoverflow.com/questions/9316179/what-is-the-correct-way-to-pass-a-boolean-to-a-python-c-extension
    if(!PyArg_ParseTupleAndKeywords(args, kwargs, "O!O!O!O!|O!dddpO!d",
        kwlist,
        &PyArray_Type, &tin,    // tin(yx,t)
        &PyArray_Type, &hin,    // hin(yx,t)
        &PyArray_Type, &win,    // win(yx,t)
        &PyArray_Type, &rin,    // rin(yx,t)
//        &PyArray_Type, &imonth,    // imonth(t)
        &PyArray_Type, &imonth, &ffmc00, &dmc00, &dc00, &debug,
        &PyArray_Type, &mask_out, &fill_value
        )) return NULL;

    // Construct standard 183-day imonth array if none given.
    bool imonth_alloc = false;
    if (imonth == NULL) {
        static npy_intp imonth_dims[] = {183};
        static npy_intp imonth_strides[] = {sizeof(int)};
        static int imonth_data[] = {
            4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,      // April
            5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,5,    // May
            6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,6,      // June
            7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,    // July
            8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,8,    // August
            9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9};     // September
        imonth = (PyArrayObject*) PyArray_NewFromDescr(&PyArray_Type, 
            PyArray_DescrFromType(NPY_INT), 1, imonth_dims, imonth_strides, imonth_data,
            NPY_ARRAY_C_CONTIGUOUS | NPY_ARRAY_ALIGNED, NULL);
        imonth_alloc = true;
    }




    const char *input_names[] = {"tin", "hin", "win", "rin"};
    PyArrayObject *inputs0[] = {tin, hin, win, rin};
    const int ninputs = 4;
    char msg[256];

    if (debug) {
        fprintf(stderr, "module = ");
        PyObject_Print(module, stderr, 0);
        fprintf(stderr, "\nargs = ");
        PyObject_Print(args, stderr, 0);
        fprintf(stderr, "\nkwargs = ");
        PyObject_Print(kwargs, stderr, 0);
        fprintf(stderr, "\n");
    }

    // -----------------------------------------
    // Make sure main arrays all have same rank and dimensions
    for (int i=0; i<ninputs; ++i) {
        if (!check_rank_dims(input_names[0], inputs0[0], input_names[i], inputs0[i]))
            return NULL;
    }

    // -----------------------------------------
    // Collapse space dimensions

    // Save original shape
    int ndim0 = PyArray_NDIM(tin);
    npy_intp const ntime = PyArray_DIM(tin, ndim0-1);
    npy_intp _dims0[ndim0];
    for (int j=0; j<ndim0; ++j) _dims0[j] = PyArray_DIM(tin,j);
    PyArray_Dims shape0 = {_dims0, ndim0};

    // Reshape to rank 2
    npy_intp nxy = 1;
    {
        for (int j=0; j<ndim0-1; ++j) nxy *= PyArray_DIM(inputs0[0],j);
        npy_intp _dims1[] = {nxy, ntime};
        PyArray_Dims shape1 = {_dims1, 2};
        PyArray_Dims shape1b = {_dims1, 1};

        // This will copy arrays if not already in C order.
        // That would be a good thing, since it would make time the lowest-stride dimension.
        tin = (PyArrayObject *)PyArray_Newshape(tin, &shape1, NPY_CORDER);
        if (!tin) return NULL;
        hin = (PyArrayObject *)PyArray_Newshape(hin, &shape1, NPY_CORDER);
        if (!hin) return NULL;
        win = (PyArrayObject *)PyArray_Newshape(win, &shape1, NPY_CORDER);
        if (!win) return NULL;
        rin = (PyArrayObject *)PyArray_Newshape(rin, &shape1, NPY_CORDER);
        if (!rin) return NULL;

        if (mask_out != NULL) {
            mask_out = (PyArrayObject *)PyArray_Newshape(mask_out, &shape1b, NPY_CORDER);
            if (!mask_out) return NULL;
        }
    }

    // -------------------------------------------------
    // imonth: Check type, rank and size
    // Type
    if (PyArray_DESCR(imonth)->type_num != NPY_INT) {
        PyErr_SetString(PyExc_TypeError, "Parameter imonth must have type int");
        return NULL;
    }

    // Rank
    if (PyArray_NDIM(imonth) != 1) {
        PyErr_SetString(PyExc_TypeError,
            "Parameter imonth must have rank 1");
        return NULL;
    }

    // Dimensions
    if ((int)PyArray_DIM(imonth, 0) != (int)ntime) {
        sprintf(msg, "Parameter imonth must have length %d equal to the time dimension of other variables; but has length %d instead.", (int)ntime, (int)PyArray_DIM(imonth,0));
        PyErr_SetString(PyExc_TypeError, msg);
        return NULL;
    }

    if (mask_out != NULL) {
        if (PyArray_DESCR(mask_out)->type_num != NPY_BOOL) {
            PyErr_SetString(PyExc_TypeError, "Parameter mask_out must have type bool");
            return NULL;
        }
        if (PyArray_NDIM(mask_out) != 1) {
            PyErr_SetString(PyExc_TypeError,
                "Parameter mask_out must have just spatial dimension(s), no time");
            return NULL;
        }
        if (PyArray_DIM(mask_out,0) != nxy) {
            sprintf(msg, "Parameter mask_out must have total size %d equal to other variables; but it has %d instead.", (int)nxy, (int)PyArray_DIM(mask_out,0));
        }
    }


    // -------------------------------------------------------------------------    

    // Output arrays (1 spatial dimension)
    PyArrayObject *ffmcout = (PyArrayObject *)PyArray_NewLikeArray(tin, NPY_ANYORDER, NULL, 0);
    PyArrayObject *isiout = (PyArrayObject *) PyArray_NewLikeArray(tin, NPY_ANYORDER, NULL, 0);
    PyArrayObject *fwiout = (PyArrayObject *)PyArray_NewLikeArray(tin, NPY_ANYORDER, NULL, 0);
    PyArrayObject *dmcout = (PyArrayObject *)PyArray_NewLikeArray(tin, NPY_ANYORDER, NULL, 0);
    PyArrayObject *buiout = (PyArrayObject *)PyArray_NewLikeArray(tin, NPY_ANYORDER, NULL, 0);
    PyArrayObject *dcout = (PyArrayObject *)PyArray_NewLikeArray(tin, NPY_ANYORDER, NULL, 0);


    // Loop through space; typically a 2D grid.  But could be (for
    // example) a small set of discrete regions for which we have
    // appropriate input data.
    for (int ii=0; ii<nxy; ++ii) {

        // enter in the inital values here
        // 3 fuel moisture codes, initialize
        double ffmc0 = ffmc00;
        double dmc0 = dmc00;
        double dc0 = dc00;


        // Loop through time.  Assumed to be solar noon on each of
        // April 1 -- September 30.  But it could be any set of
        // timepoints.
        for (int ti=0; ti<ntime; ++ti) {

            // Obtain values at this point in (space,time).
            const double t = *((double *)PyArray_GETPTR2(tin,ii,ti));
            const double h = *((double *)PyArray_GETPTR2(hin,ii,ti));
            const double w = *((double *)PyArray_GETPTR2(win,ii,ti));
            const double r = *((double *)PyArray_GETPTR2(rin,ii,ti));
            const int im =  *((int *)PyArray_GETPTR1(imonth,ti));
            // If no mask_out, compute for all pixels
            const char msk_out = (mask_out == NULL ? 0 :
                *((char *)PyArray_GETPTR1(mask_out,ii)));

            // Run the core computation on a single gridpoint.
            double bui, ffm, isi, fwi, dsr, dmc, dc;   // Output vars
            if (msk_out) {
                bui = fill_value;
                ffm = fill_value;
                isi = fill_value;
                fwi = fill_value;
                dmc = fill_value;
                dc = fill_value;
            } else {
                // Keep humidity in range [0,100]
            	double _h = (h>100. ? 100. : h);
            	_h = (_h < 0. ? 0. : _h);
                d8graph(
                    t, _h, w, r, im,
                    ffmc0, dmc0, dc0,    // Running values from one day to the next
                    &bui, &ffm, &isi, &fwi, &dsr, &dmc, &dc);
            }

            // housekeeping items
            // set todays values to the yesterdays values before going on
            ffmc0 = ffm;
            dmc0 = dmc;
            dc0 = dc;

            // Store results back in Arrays
            *((double *)PyArray_GETPTR2(buiout,ii,ti)) = bui;
            *((double *)PyArray_GETPTR2(ffmcout,ii,ti)) = ffm;
            *((double *)PyArray_GETPTR2(isiout,ii,ti)) = isi;
            *((double *)PyArray_GETPTR2(fwiout,ii,ti)) = fwi;
            *((double *)PyArray_GETPTR2(dmcout,ii,ti)) = dmc;
            *((double *)PyArray_GETPTR2(dcout,ii,ti)) = dc;
            
        }
    }

    // ---------------------------------------------------------
    // Free input arrays we allocated (the version w/ 1 spatial dimension)
    Py_DECREF(tin);
    Py_DECREF(hin);
    Py_DECREF(win);
    Py_DECREF(rin);
    if (imonth_alloc) Py_DECREF(imonth);

    // ---------------------------------------------------------
    // Reshape to original rank; and free the 1-spatial-dim version
    PyArrayObject *_ffmcout = (PyArrayObject *)PyArray_Newshape(ffmcout, &shape0, NPY_ANYORDER);
    if (!ffmcout) return NULL;
    Py_DECREF(ffmcout);
    PyArrayObject *_isiout = (PyArrayObject *)PyArray_Newshape(isiout, &shape0, NPY_ANYORDER);
    if (!isiout) return NULL;
    Py_DECREF(isiout);
    PyArrayObject *_fwiout = (PyArrayObject *)PyArray_Newshape(fwiout, &shape0, NPY_ANYORDER);
    if (!fwiout) return NULL;
    Py_DECREF(fwiout);
    PyArrayObject *_dmcout = (PyArrayObject *)PyArray_Newshape(dmcout, &shape0, NPY_ANYORDER);
    if (!dmcout) return NULL;
    Py_DECREF(dmcout);
    PyArrayObject *_buiout = (PyArrayObject *)PyArray_Newshape(buiout, &shape0, NPY_ANYORDER);
    if (!buiout) return NULL;
    Py_DECREF(buiout);
    PyArrayObject *_dcout = (PyArrayObject *)PyArray_Newshape(dcout, &shape0, NPY_ANYORDER);
    if (!dcout) return NULL;
    Py_DECREF(dcout);

    // Return a tuple of the output arrays we created.
    // https://stackoverflow.com/questions/3498210/returning-a-tuple-of-multipe-objects-in-python-c-api
    PyObject *ret = PyTuple_Pack(6, _buiout,_ffmcout,_isiout,_fwiout,_dmcout,_dcout);
    return ret;
}
// ============================================================



// ============================================================
// Random other Python C Extension Stuff
static PyMethodDef D8graphMethods[] = {
    {"d8graph",
        (PyCFunction)d8graph_d8graph,
        METH_VARARGS | METH_KEYWORDS, d8graph_d8graph_docstring},

    {"solar_noon",
        (PyCFunction)d8graph_solar_noon,
        METH_VARARGS | METH_KEYWORDS, d8graph_solar_noon_docstring},

    // Sentinel
    {NULL, NULL, 0, NULL}
};

/* This initiates the module using the above definitions. */
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    .m_name = "dggs.d8graph",    // Name of module
    .m_doc = "dggs.d8graph C Extnesion Module",    // Per-module docstring
    .m_size = -1,  /* size of per-interpreter state of the module,
                 or -1 if the module keeps state in global variables. */
};

PyMODINIT_FUNC PyInit_d8graph(void)
{
    import_array();    // Needed for Numpy

    return PyModule_Create(&moduledef);
}
