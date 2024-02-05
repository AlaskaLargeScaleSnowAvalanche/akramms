import pathlib,os
import setuptools.sandbox
from akramms.util import harnutil

# ------------
if True:
    # Make sure the domain finder C++ code is compiled. (needed for RAMMS Stage 1)
    setup_py = os.path.join(harnutil.HARNESS, 'akramms', 'setup.py')
    prefix = os.path.join(harnutil.HARNESS, 'akramms', 'inst')
    cmd = ['install', '--prefix', prefix]
    print('setup.py ', cmd)
    setuptools.sandbox.run_setup(setup_py, cmd)
# ------------

from akramms import r_domain_builder


HOME = pathlib.Path(os.environ['HOME'])
dem_file = HOME / 'prj' / 'ak' / 'dem' / 'ak_dem_109_042.tif'
odir = HOME / 'tmp'

def main():


    rule = r_domain_builder.neighbor1_rule(dem_file, odir)
    rule()

main()
