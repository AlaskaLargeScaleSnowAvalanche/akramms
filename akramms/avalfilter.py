import re,sys
import netCDF4

"""Construct filter_in functions for Avalanche queries"""

this_module = sys.modules[__name__]

# ------------------------------------------------------
def all(id, row, nc_fname):
    return True

def none(id, row, nc_fname):
    return False
# ------------------------------------------------------
def overrun(val):
    """Includes or excludes overruns."""
    def _filter(id, row, nc_fname):
        with netCDF4.Dataset(nc_fname) as nc:
            overrun = (nc.variables['status'].overrun == 'True')
        return overrun == val
    return _filter
# ------------------------------------------------------
