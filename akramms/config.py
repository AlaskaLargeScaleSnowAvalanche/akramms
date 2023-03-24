import os,configparser,functools
from uafgi.util import pathutil,ioutil


def _harness_dir():
    path = os.path.abspath(__file__)
    for i in range(3):
        path = os.path.split(path)[0]
    return path
HARNESS = _harness_dir()

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

#ramms_version = '230126'
#ramms_version = '230210'
ramms_version = '230321'
#docker_container_version = f'${ramms_version}.0'

# Maximum number of PRAs in a RAMMS run
max_ramms_pras = 100
#max_ramms_pras = 20

# ------------------------------
# DEBUG parameters
#allowed_pra_sizes = {'T', 'S', 'M', 'L'}
#allowed_pra_sizes = {'L', 'M'}
allowed_pra_sizes = {'L'}
#allowed_forests = {True}
#allowed_return_periods = {30}

# Amount of margin to provide avalanche for first run
initial_margins = {
    'T' : 1000.,
    'S' : 1000.,
    'M' : 1000.,
    'L' : 1000.
}

ramms_distro_dir = os.path.join(HARNESS, 'data', 'christen', 'RAMMS', ramms_version)

# Host we use for Docker registry
docker_host = 'git.akdggs.com'
builds_ini = os.path.join(HARNESS, 'akramms', 'docker', 'builds.ini')

# Determine the Docker image to use to run RAMMS
@functools.lru_cache()
def docker_tag():
    ini = configparser.ConfigParser()
    ini.read(builds_ini)
    section = self.ini['builds']
    build = int(section[ramms_version])

    vers = f'{ramms_version}.{build}'
    return f'{docker_host}/efischer/ramms:{vers}'


# ------------------------------------------------------------
class update_docker_build:

    def __init__(self):
        self.ini = configparser.ConfigParser()

    def __enter__(self):
        self.ini.read(builds_ini)

        # Determine build count for this version
        section = self.ini['builds']
        try:
            self.build_count = int(section[ramms_version])
        except KeyError:
            self.build_count = 0
        self.build_count += 1
        return self.build_count


    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        # Only update if body completed successfully
        section = self.ini['builds']
        section[ramms_version] = str(self.build_count)
        with ioutil.WriteIfDifferent(builds_ini) as owid:
            with open(owid.tmpfile, 'w') as out:
                self.ini.write(out)
