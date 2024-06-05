import os,configparser,functools,sys,pathlib
from uafgi.util import pathutil,ioutil


def _harness_dir():
    path = os.path.abspath(__file__)
    for i in range(3):
        path = os.path.split(path)[0]
    return pathlib.Path(path)
HARNESS = _harness_dir()

# Default values of configuration parametesrs.  If these parameters
# are provided on the command line, they may be monkeypatched in here
# at runtime.

def default_roots(PureSysPath, harness):
    harness = PureSysPath(harness)
    return pathutil.RootsDict(PureSysPath, (
        ('HARNESS', harness),
        ('DATA', harness / 'data'),
        ('PRJ', harness / 'prj'),
    ))

roots_l = default_roots(
    pathlib.PurePosixPath,
    os.path.abspath(os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))))
roots_w = default_roots(pathlib.PureWindowsPath, r'C:\Users\efischer\av') # r'\\nona.dnr.state.ak.us\enggeo_projects\avalanche_sim\av'

# Differences from defaults
#roots_l['PRJ'] = '/mnt/avalanche_sim/prj'
#roots_w['PRJ'] = r'\\nona.dnr.state.ak.us\enggeo_projects\avalanche_sim\prj'
roots_l['PRJ'] = (pathlib.Path(os.environ['HOME']) / 'prj').resolve()
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

# Submit Avalanche simulations to Stage 2 immediately upon completion of Stage 1?
auto_submit = True
#auto_submit = False

#ramms_version = '230126'
#ramms_version = '230210'
#ramms_version = '230321'
#ramms_version = '230401'
#ramms_version = '230423'
#ramms_version = '240111'
#ramms_version = '240515'
#docker_container_version = f'${ramms_version}.0'

# Maximum number of PRAs in a RAMMS run
max_ramms_pras = 100
#max_ramms_pras = 20
#max_ramms_pras = 500

enlarge_increment = 5000.    # Enlarge domains by 5km each time.

#setup_ncpu = 8
setup_ncpu = 1   # 1 is the only value that works here
#ramms_ncpu = 6    # Native RAMMS Stage 2 (and also Stage 1 xy-coords)
ramms_ncpu = 5    # Native RAMMS Stage 2 (and also Stage 1 xy-coords)    # Avoid memory overrun
#ramms_ncpu_preprocess = 8    # This matters for RAMMS Stage 1 (and maybe Stage 3)
ramms_ncpu_preprocess = 1    # 1 is fastest, due to IDL's overhead in parallelizing and the small granularity of RAMMS Stage 1
ncpu_compress = 6    # Number of CPUs to use when compressing stuff after RAMMS Stage 1
ncpu_archive = 6
poll_period = 60*5    # Seconds between polling attempts

# Should we use the Redis Queue for running remote IDL commands?
queue = {'arcgis': True, 'ecognition': True, 'idl': True}
#queue = {'arcgis': False, 'ecognition': True, 'idl': True}

# ------------------------------
# DEBUG parameters
#allowed_pra_sizes = ['L']
allowed_pra_sizes = ['L', 'M', 'S', 'T']
#allowed_pra_sizes = {'M', 'S'}
#allowed_forests = {True}
#allowed_return_periods = {30}

# Maximum number of chunks in one set
#max_chunks = 2
max_chunks = None

# Amount of margin to provide avalanche for first run
initial_margins = {
    'T' : 1000.,
    'S' : 1000.,
    'M' : 1000.,
    'L' : 1000.
}

#ramms_distro_dir = roots.join('data', 'christen', 'RAMMS', ramms_version)

# Host we use for Docker registry
docker_host = 'git.akdggs.com'
builds_ini = os.path.join(HARNESS, 'akramms', 'docker', 'builds.ini')

# Determine the Docker image to use to run RAMMS
@functools.lru_cache()
def docker_tag(ramms_version):
    ini = configparser.ConfigParser()
    ini.read(builds_ini)
    section = ini['builds']
    build = int(section[ramms_version])

    vers = f'{ramms_version}.{build}'
    return f'{docker_host}/efischer/ramms:{vers}'


# ------------------------------------------------------------
class update_docker_build:

    def __init__(self, ramms_version):
        self.ini = configparser.ConfigParser()
        self.ramms_version = ramms_version

    def __enter__(self):
        self.ini.read(builds_ini)

        # Determine build count for this version
        section = self.ini['builds']
        try:
            self.build_count = int(section[self.ramms_version])
        except KeyError:
            self.build_count = 0
        self.build_count += 1
        return self.build_count


    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        # Only update if body completed successfully
        section = self.ini['builds']
        section[self.ramms_version] = str(self.build_count)
        with ioutil.WriteIfDifferent(builds_ini) as owid:
            with open(owid.tmpfile, 'w') as out:
                self.ini.write(out)
