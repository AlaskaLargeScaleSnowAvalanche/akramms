import re,sys
import zip

"""Construct filter_in functions for Avalanche queries"""

this_module = sys.modules[__name__]

# ------------------------------------------------------
def all(id, row, nc_fname):
    return True

def none(id, row, nc_fname):
    return False
# ------------------------------------------------------
#def overrun(val):
#    """Includes or excludes overruns."""
#    def _filter(id, id, out_zip):
#        in_zip = out_zip[:-8] + '.in.zip'
#
#        with netCDF4.Dataset(nc_fname) as nc:
#            overrun = (nc.variables['status'].overrun == 'True')
#        return overrun == val
#    return _filter
