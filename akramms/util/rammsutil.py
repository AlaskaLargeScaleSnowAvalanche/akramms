import os,re,typing,functools
import numpy as np
import shapely

PRA_SIZES = {
    'T' : 'tiny',
    'S' : 'small',
    'M' : 'medium',
    'L' : 'large'}
# ---------------------------------------------------------------
def ramms_name(scene_name, forest, resolution, return_period, pra_size):
    For = 'For' if forest else 'NoFor'
    return f"{scene_name}{For}_{resolution}m_{return_period}{pra_size}"

class RammsRun(typing.NamedTuple):
    ramms_dir: str    # Directory just under RAMMS/
    scene_name: str
    forest: bool
    resolution: int
    return_period: int
    pra_size: str
    segment: int

    @property
    def scenario_name(self):    # Does NOT include segment number
        return '{}_{:03d}'.format(ramms_name(self.scene_name, self.forest, self.resolution, self.return_period, self.pra_size), self.segment)

    base = scenario_name

    @property
    def prefix(self):
        For = 'For' if self.forest else 'NoFor'
        return f'{self.scene_name}{For}'

    @property
    def suffix(self):
        return f'{self.resolution}m_{self.return_period}{self.pra_size}'

    @property
    def run_dir(self):
        """Directory RAMMS Core runs use for input and output"""
        For = 'For' if self.forest else 'NoFor'
        return os.path.join(self.ramms_dir, 'RESULTS',
            f'{self.scene_name}{For}_{self.resolution}m',
            f'{self.return_period}{self.pra_size}')

    def log_zip(self, id):
        return os.path.join(self.run_dir, '{}_{}.log.zip'.format(self.base, id))

    def arcname(self, id, ext):
        """Name of the logfile in the Zip archive
        extname:
            .log or .overrun
        """
        return '{}_{}{}'.format(self.base, id, ext)

# -------------------------------------------------------
release_fileRE = re.compile(r'^(.+)(NoFor|For)_(\d+)m_(\d+)(T|S|M|L)_(\d+)_(.*)\.(.*)')

@functools.lru_cache()
def parse_release_file(release_file):
    """Parses the full name of a release file into a RammsRun named tuple."""

    RELEASE_dir,leaf = os.path.split(release_file)
    ramms_dir = os.path.split(RELEASE_dir)[0]
    print('leaf ', leaf)
    match = release_fileRE.match(leaf)

    scene_name = match.group(1)
    For = match.group(2)
    forest = True if For == 'For' else False
    resolution = int(match.group(3))
    return_period = int(match.group(4))
    pra_size = match.group(5)
    segment = int(match.group(6))
    file_type = match.group(7)    # eg: _rel
    ext = match.group(8)          # eg: shp

    return RammsRun(
        ramms_dir,
        scene_name, forest, resolution, return_period, pra_size, segment)

# --------------------------------------------------------
def _ramms_to_release(ramms_dirs):
    """Given a bunch of RAMMS directories, returns the release files in them."""
    release_files = list()
    for ramms_dir in ramms_dirs:
        RELEASE_dir = os.path.join(ramms_dir, 'RELEASE')
        for file in os.listdir(RELEASE_dir):
            if file.endswith('_rel.shp'):
                release_files.append(os.path.join(RELEASE_dir, file))

    return release_files

def get_release_files(spec):
    """Given a directory above or below the RAMMS directory, finds a
    "ramms dir," which is one level below RAMMS/."""

    # *** The spec is a directory corresponding to a SINGLE shapefile
    # ** The spec is a SINGLE shapefile
    if spec.endswith('.shp'):
        return [spec]

    dir = os.path.abspath(spec)
    parts = dir.split(os.sep)

    # See if we're in, eg:
    #   RAMMS/juneau130yFor/RESULTS/juneau1_For/5m_30L$ 
    # Return just the shapefile
    if len(parts) >=3 and parts[-3] == 'RESULTS':
        parts2 = parts[:-3] + ['RELEASE', '{}_{}_rel.shp'.format(parts[-2], parts[-1])]
        return [os.sep.join(parts2)]


    # See if we're in a subdirectory
    for i in range(len(parts)):
        if parts[i] == 'RAMMS':
            # RAMMS/ is the last part of the path, we have multiple dirs.
            if len(parts) == i:
                ramms_dirs = [os.path.join(x) for x in os.listdir(dir)]
                return _ramms_to_release(ramms_dirs)
            else:
                # We have a path one lower than RAMMS, use it.
                return _ramms_to_release([os.sep.join(parts[:i+2])])

    raise ValueError('Could not interpret spec {} as one or more RAMMS dirs'.format(spec))
# ---------------------------------------------------------
def read_polygon(poly_file):
    """Reads a RAMMS polygon file (eg: .dom) into a Shapely Polygon."""
    with open(poly_file) as fin:
        line = next(fin).split(' ')
        # Get just the x,y coordinates, no count at beginning, no repeat at end
        coords = [float(x) for x in line[1:-2]]

    return shapely.geometry.Polygon(list(zip(coords[::2], coords[1::2])))

def write_polygon(p, poly_file):
    with open(poly_file, 'w') as out:
        coords = list(p.boundary.coords)
        out.write('{}'.format(len(coords)))
        for x,y in coords:
            out.write(f' {x} {y}')
        out.write('\n')
# --------------------------------------------------------
def edge_lengths(p):
    pts = np.array(p.boundary.coords)
    edges = np.diff(pts, axis=0)
    return np.linalg.norm(edges,axis=1)

def _scale_vec(vec,margin):
    """Adds a certain length to a vector.  Helper function."""
    veclen = np.linalg.norm(vec)
    if (veclen+margin) < 0:
        raise ValueError('Margin is larger than side')
    factor = margin / veclen
    return factor*vec

def add_margin(p,margin):
    """Adds a margin to a (rotated) rectangle, i.e. a domain rectangle.
    p: shapely.geometry.Polygon
        The rectangle
    margin:
        Absolute amount to add to length and width.
        If negative, subtract this amount; cannot subtract more than original length
    """
    pts = np.array(p.boundary.coords)
    edges = np.diff(pts, axis=0)
    margin2 = .5*margin
    pts[0,:] += (_scale_vec(edges[3,:],margin2) - _scale_vec(edges[0,:],margin2))
    pts[1,:] += (_scale_vec(edges[0,:],margin2) - _scale_vec(edges[1,:],margin2))
    pts[2,:] += (_scale_vec(edges[1,:],margin2) - _scale_vec(edges[2,:],margin2))
    pts[3,:] += (_scale_vec(edges[2,:],margin2) - _scale_vec(edges[3,:],margin2))

    p = shapely.geometry.Polygon(list(zip(pts[:-1,0], pts[:-1,1])))
    return p
# -----------------------------------------------------------
