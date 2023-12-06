import re,sys,os
import zipfile
#from akramms import rammsquery

"""Construct filter_in functions for Avalanche queries"""

this_module = sys.modules[__name__]

# ------------------------------------------------------
def all(id, row, sizecat, out_zip):
    return True


def none(id, row, sizecat, out_zip):
    return False
# ------------------------------------------------------
def resubmitted(id, row, sizecat, out_zip):
    """Finds avalanches that were resubmitted after an overrun."""

    if row['job_status'] != 0:
        print('fffff ', out_zip, row['job_status'])
    in_zip = out_zip[:-8] + '.in.zip'

    # We tentatively think the job is finished.  But let's
    # look inside the zip file to make sure the domain
    # wasn't overrun.
    with zipfile.ZipFile(in_zip, 'r') as ozip:
        arcnames = [os.path.split(x)[1] for x in ozip.namelist()]
    if any(x.endswith('.v2.dom') for x in arcnames):
        return True
    return False
# ------------------------------------------------------

