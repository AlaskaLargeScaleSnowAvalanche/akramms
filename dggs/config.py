import os
from uafgi.util import pathutil

# Default values of configuration parametesrs.  If these parameters
# are provided on the command line, they may be monkeypatched in here
# at runtime.

def default_roots(sep, harness):
    return pathutil.RootsDict(sep, (
        ('HARNESS', harness),
        ('DATA', sep.join((harness, 'data'))),
        ('PRJ', sep.join((harness, 'prj')))
    ))

roots_l = default_roots(os.sep, os.path.abspath(os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))))
roots_w = default_roots('\\', r'\\nona.dnr.state.ak.us\enggeo_projects\avalanche_sim\av')

# Roots for the system we're running on
roots = roots_w if os.name=='nt' else roots_l

# Root directory of prj
windows_host = 'davos'

# True if the Linux and Windows harnesses access the same location on a network drive.
shared_prj = True
