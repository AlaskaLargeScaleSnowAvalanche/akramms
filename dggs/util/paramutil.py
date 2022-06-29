from dggs.util import harnutil
import collections
import pathlib
import textwrap
import os
import netCDF4
import numpy as np

class Type:
    def __init__(self, typ):
        self.typ = typ

    def validate(self, val):
        val = self.typ(val)
        assert isinstance(val, self.typ)
        return val

    def write_nc(self, nc, vname, val):
        ncv = nc.createVariable(vname, 'i', [])
        ncv.setncattr('value', val)
        return ncv

    def read_nc(self, ncv):
        return ncv.value

# Things one can use in a path; eg: '{ROOT}/...'
_path_vars = {
    'HARNESS': harnutil.HARNESS
}

class PathType(Type):
    def __init__(self):
        super().__init__(str)

    def validate(self, val):
#        return os.path.abspath(val.format(**_path_vars))
        ret = os.path.join('{HARNESS}', os.path.replath(os.path.abspath(val), HARNESS))
        if os.name == 'nt':
            ret = ret.replace(os.path.pathsep, '/')
        print('{} => {}'.format(val, ret))
        return ret

class InputFileType(Type):
    def __init__(self):
        super().__init__(str)

    def validate(self, val):
        val = os.path.abspath(val)
        if not os.path.exists(val):
            raise FileNotFoundError(val)

        ret = os.path.join('{HARNESS}', os.path.relpath(val, harnutil.HARNESS))
        if os.name == 'nt':
            ret = ret.replace(os.path.pathsep, '/')
        print('{} => {}'.format(val, ret))
        return ret

    def read_nc(self, ncv):
        return ncv.value.format(**_path_vars)

class ListType:
    def validate(self, val):
        assert isinstance(val, list)
        return val

    def write_nc(self, nc, vname, val):
        ncv = nc.createVariable(vname, 'i', [])
        ncv.setncattr('value', val)
        return ncv

    def read_nc(self, ncv):
        return list(ncv.value)

class ArrayType:
    def validate(self, val):
        assert isinstance(val, np.ndarray)
        return val

    def write_nc(self, nc, vname, val):
        dims = list()
        for ix,length in enumerate(val.shape):
            dims.append('{}_{}'.format(vname,ix))
            nc.createDimension(dims[-1], length)
        ncv = nc.createVariable(vname, val.dtype, dims)
        ncv[:] = val[:]
        return ncv

    def read_nc(self, ncv):
        return ncv[:]

class BoolType:
    def validate(self, val):
        assert isinstance(val, bool)
        return val

    def write_nc(self, nc, vname, val):
        ncv = nc.createVariable(vname, 'i', [])
        ncv.setncattr('value', 1 if val else 0)
        return ncv

    def read_nc(self, ncv):
        return (ncv.value != 0)


TYPES = {
    'str': Type(str),
    'int': Type(int),
    'float': Type(float),
    'bool': BoolType(),
    'path': PathType(),
    'input_file': InputFileType(),
    'list': ListType(),
    'array': ArrayType(),
}
    
# Describes a high-level parameter to something
Param = collections.namedtuple('Param', ('name', 'units', 'type', 'required', 'description'))

def parse(specs):
    PARAMS = dict()
    for x in specs:
        PARAMS[x[0]] = Param(x[0], x[1], x[2], x[3], textwrap.dedent(x[4]))
    return PARAMS


def dump_nc(ofname, args, params=None):
    """Writes a dict of arguments to a NetCDF file
    params:
        Dict of parameter descriptions (output of parse())"""
    with netCDF4.Dataset(ofname, 'w') as nc:
        for vname,val in args.items():
            #ncv = nc.createVariable(vname, 'i', [])
            param = params[vname]
            typ = TYPES[param.type]
            ncv = typ.write_nc(nc, vname, val)
            if param.units is not None:
                ncv.units = param.units
            ncv.type = param.type
            ncv.required = 1 if param.required else 0
            ncv.description = param.description

def load_nc(ifname):
    args = dict()
    with netCDF4.Dataset(ifname, 'r') as nc:
        nc.set_auto_mask(False)
        for vname,ncv in nc.variables.items():
            typ = TYPES[ncv.type]
            args[vname] = typ.read_nc(ncv)
    return args
# -------------------------------------------------------------
def validate_args(args, params=None):
    """Checks that arguments are of right type, exist if they should, no extra, etc."""

    ret = dict()
    remain_args = dict(args.items())
    for name,param in params.items():
        if name in remain_args:
            typ = TYPES[param.type]
            ret[name] = typ.validate(remain_args[name])
            del remain_args[name]
        elif param.required:
            raise ValueError('Missing REQUIRED argument: {}'.format(name))

    if len(remain_args) > 0:
        raise ValueError('Extra arguments: {}'.format(list(remain_args.keys())))
    return ret
