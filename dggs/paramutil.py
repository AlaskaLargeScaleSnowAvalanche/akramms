import collections
import pathlib
import textwrap
import os
import netCDF4

class Type:
    def __init__(self, parse_fn):
        self.parse = parse_fn
    def write_nc(self, nc, vname, val):
        ncv = nc.createVariable(vname, 'i', [])
        ncv.setncattr('value', val)
        return ncv
    def read_nc(self, ncv):
        return ncv.value

class ListType:
    def write_nc(self, nc, vname, val):
        ncv = nc.createVariable(vname, 'i', [])
        ncv.setncattr('value', val)
        return ncv

    def read_nc(self, ncv):
        return list(ncv.value)

class ArrayType:
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



TYPES = {
    'str': Type(str),
    'int': Type(int),
    'float': Type(float),
    'path': Type(pathlib.Path),
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
