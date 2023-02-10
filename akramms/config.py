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
roots_w = default_roots('\\', r'C:\Users\efischer\av') # r'\\nona.dnr.state.ak.us\enggeo_projects\avalanche_sim\av'

# Differences from defaults
roots_l['PRJ'] = '/mnt/avalanche_sim/prj'
#roots_w['PRJ'] = r'\\nona.dnr.state.ak.us\enggeo_projects\avalanche_sim\prj'
roots_w['PRJ'] = r'M:\prj'

# Roots for the system we're running on
roots = roots_w if os.name=='nt' else roots_l

# Root directory of prj
#windows_host = 'davos'
ssh_w = ['sshpass',
    '-f', os.path.join(os.environ['HOME'], '.ssh', 'davos_password'),
    'ssh', 'davos']


# True if the Linux and Windows harnesses access the same location on a network drive.
shared_filesystem = True

debug = False

ramms_version = '230126'

# Maximum number of PRAs in a RAMMS run
max_ramms_pras = 100
#max_ramms_pras = 20

# ------------------------------
# DEBUG parameters
#allowed_pra_sizes = {'T', 'S', 'M', 'L'}
allowed_pra_sizes = {'L'}
#allowed_forests = {True}
#allowed_return_periods = {30}
