import os,subprocess,re,sys,itertools,collections,shutil,zipfile
from dggs.util import harnutil

RAMMS_220922 = ('220922', 'RAMMS_LSHM_NEW2022.zip')
_base_upgrade_for_version = {
    '220922' : (RAMMS_220922, None),
    '220928' : (RAMMS_220922, '220928'),
    '221101' : (RAMMS_220922, '221101'),
}
def install_ramms_on_windows(version)
    """Installs RAMMS into the appropriate distro file inside the harness."""

    # Figure out where raw distro files are for our version.
    base_args, upgrade_leaf = _base_upgrade_for_version(version)

    # Create destination directory
    ramms_dir = os.path.join(harnutil.HARNESS, 'opt', 'RAMMS', version)
    shutil.rmtree(ramms_dir, ignore_errors=True)
    os.makedirs(ramms_dir, exist_ok=True)

    # Unpack the Zipfile
    base_zip = os.path.join(harnutil.HARNESS, *base_args)
    with zipfile.ZipFile(base_zip, 'r') as zipf:
        names = zipf.namelist()

    print(names)
    



def install_ramms_rule(hostname, version, HARNESS_REMOTE):
    """
    Installs a version of RAMMS onto the remote machine."""




def configure_ramms_distro(ramms_distro):
    """Make sure the RAMMS distribution has been fiddled properly"""

    bin = os.path.join(ramms_distro, 'bin')
    with ioutil.pushd(bin):
        if not os.path.exists('ramms_aval_LHM_orig.exe'):
            # Need to move
            print('Moving to ramms_aval_LHM_orig.exe')
            os.rename('ramms_aval_LHM.exe', 'ramms_aval_LHM_orig.exe')

        if not os.path.exists('ramms_aval_LHM.exe'):
            # Need to build
            src = os.path.join(harnutil.HARNESS, 'akramms', 'ramms_aval_LHM_stub.cpp')
            cmd = ['g++', src, '-o', 'ramms_aval_LHM.exe']
            print(' '.join(cmd))
            subprocess.run(cmd, check=True)
