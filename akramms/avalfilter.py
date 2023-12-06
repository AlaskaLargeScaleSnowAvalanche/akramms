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
sfilterRE = re.compile(r'^\s*([^()\s]+)(\(([^)]*)\))?\s*$')
def parse(sfilter):
    match = sfilterRE.match(sfilter)
    sfn = match.group(1)
    sargs = match.group(3)    # Excludes parentheses

    # Get the filter function
    parts = sfn.rsplit('.',1)
    if len(parts) == 1:
        # No module included; use avalfilter
        mod = this_module
        filter_fn = getattr(mod, sfn)
    else:
        # A module was included; use it
        mod = importlib.import_module('.'.join(parts[:-1]))
        filter_fn = getattr(mod, parts[-1])

    # See if arguments were provided.
    if sargs is None:
        # No parentheses or arguments provided: the provided filter_fn
        # is the final filter_in_fn to be used by archive.fetch().
        return filter_fn
    else:
        # Arguments were provided: Run the provided filter_fn to
        # generate the final filter.
        args = eval(f'[{sargs}]')
        return filter_fn(*args)
