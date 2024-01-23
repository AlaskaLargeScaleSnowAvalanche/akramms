#pragma once

//namespace akramms {

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
// ----------------------------------------------------------------------------------------

static bool check_array(PyArrayObject *_arr, std::string const &name, int type_num, std::string const &stype_num, int const nxy)
{
    char msg[256];    // Error message

    // Check storage
    if (!PyArray_ISCARRAY_RO(_arr)) {
        snprintf(msg, 256, "Parameter %s must be C-style, contiguous array.", name.c_str());
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check type
    if (PyArray_DESCR(_arr)->type_num != type_num) {    // Eg: NPY_DOUBLE
        snprintf(msg, 256, "Parameter %s must have dtype %s.", name.c_str(), stype_num.c_str());
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    // Check total number of elements (we will flatten to 1D in C++)
    if ((nxy >= 0) && (PyArray_SIZE(_arr) != nxy)) {
        snprintf(msg, 256, "Parameter %s must have %d elements.", name.c_str(), nxy);
        PyErr_SetString(PyExc_TypeError, msg);
        return false;
    }

    return true;

}
// ---------------------------------------------------------

//}    // namespace

