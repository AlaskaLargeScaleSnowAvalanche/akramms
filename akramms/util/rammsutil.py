import os,re,typing,functools,copy,glob,io,struct
import numpy as np
import shapely
import pandas as pd
from uafgi.util import shputil
from akramms import config

PRA_SIZES = {
    'T' : 'tiny',
    'S' : 'small',
    'M' : 'medium',
    'L' : 'large'}
# ---------------------------------------------------------------
class RammsName:
    all_cols = ['ramms_harness', 'scene_name', 'segment', 'forest', 'resolution', 'return_period', 'pra_size', 'id']

    # Columns used to determine ORAMMS name
    required_cols = ['ramms_harness', 'scene_name', 'forest', 'resolution', 'return_period'] #, 'pra_size']
    optional_cols = ['segment', 'pra_size', 'id']

    def __init__(self, ramms_harness, scene_name, segment, forest, resolution, return_period, pra_size, id):
        """
        ramms_harness: REQUIRED
            Directory containing RAMMS directories
            Eg: ~/prj/juneau1/RAMMS
        scene_name: REQUIRED
            Overall name of scene in top-level project (eg: juneau1)
        segment: int OPTIONAL (None = not set)
            Segment numberwithin a run
        forest: bool REQUIRED
            Is this a forested or non-forested run?
        resolution: int REQUIRED
            Spatial resolution of the DEM used
        return_period: int OPTIONAL (None = not set)
            10y, 30y, 100y, 300y
        pra_size: str OPTIONAL
            Which segment of PRAs is being processed
            'T', 'S', 'M', 'L'
        id: int OPTIONAL (None = not set)
            ID number of a PRA
        """
        if return_period == -1:
            return_period = None
        self.args = dict(locals())    # Store original args to function
        self.__dict__.update(self.args)
        self.update()

    def update(self):
        """Update computed values"""
        self.scene_dir = os.path.dirname(self.ramms_harness)   # Top-level AKRAMMS directory
        self.For = 'For' if self.forest else 'NoFor'
        self.ssegment = '' if self.segment is None else '{:05d}'.format(self.segment)
        self.sid = '' if self.id is None else f'_{self.id}'
        spra_size = '' if self.pra_size is None else f'{self.pra_size}'
        suffix = '' if self.return_period is None else f'_{self.return_period}{spra_size}'
        self.reldom_name = f'{self.scene_name}{self.ssegment}{self.For}_{self.resolution}m{suffix}'
        self.ramms_name = self.reldom_name + str(self.sid)  #f'{self.scene_name}{self.ssegment}{self.For}_{self.resolution}m{suffix}{self.sid}'

        # Root of the RAMMS run (from RAMM's perspective)
        if self.return_period is not None:
            self.rammsdir_name = f'{self.scene_name}{self.ssegment}{self.return_period}{spra_size}{self.For}_{self.resolution}m'#{self.sid}' 
            self.ramms_dir = os.path.join(self.ramms_harness, self.rammsdir_name)

        # Place where slope files are placed.
        # (These are common for all return periods and T/S/M/L
        self.slope_name = f'{self.scene_name}{self.ssegment}{self.For}_{self.resolution}m'
        self.slope_dir = os.path.join(self.ramms_dir, 'RESULTS', self.slope_name)

        # Place where individual avalanche computations take place
        self.avalanche_dir = os.path.join(self.slope_dir, f'{self.return_period}{spra_size}')

        # ------------------ Name of individual avla
        # Base pathname for avalanche files; just append _{id}.{ext}
        self.avalanche_base = os.path.join(self.avalanche_dir, self.ramms_name)

    def set(self, **kwargs):
        """Change the value of one or more fields"""
        # Check we're not making any new fields
        assert all(key in self.__dict__ for key in kwargs)
        self.__dict__.update(kwargs)
        self.update()

    def copy(self, **kwargs):
        ret = copy.copy(self)
        ret.set(**kwargs)
        return ret

    # ---------- Per-avalanche naming...
    def avalanche_file(self, id, ext):
        """Name of an individual file read or written by RAMMS Core
        id: int
            ID of the avalanche
        ext: str
            Eg: '.av2', '.rel', etc.
        """
        return f'{self.avalanche_base}_{id}{ext}'


    def zip_file(self, id, ext='.in.zip'):
        return os.path.join(self.avalanche_dir, self.arcname(id, ext))

    def arcname(self, id, ext):
        """Name of the a file within the Zip archive of an avalanche

        """
        return f'{self.scene_name}{self.ssegment}{self.For}_{self.resolution}m_{self.return_period}{self.pra_size}_{id}{ext}'

    def key(self):
        """Standard sort order for RammsNames"""
        return (self.scene_name, self.forest, self.resolution, self.return_period, self.pra_size, self.segment, self.id, self)

    def format(self, format, scene_args=None):
        """Formats a general name, including parts from the RammsName
        and also the general scene."""

        if scene_args is None:
            dd = dict()
        else:
            dd = dict(scene_args)
        dd['For'] = 'For' if self.forest else 'NoFor'
        dd.update((col,getattr(self,col)) for col in RammsName.all_cols)

        return format.format(**dd)

# -------------------------------------------------------
def master_ramms_names(scene_args, return_period, forest):
    """Generates list of RAMMS names of RELEASE files before they've been chopped up.
    Yields: jb (RammsName), pra_size
    """
    for pra_size in rammsutil.PRA_SIZES.keys():    # T,S,M,L
        if pra_size not in config.allowed_pra_sizes:
            continue
        jb = rammsutil.RammsName(
            os.path.join(scene_args['scene_dir'], 'CHUNKS'),
            scene_args['name'], None, forest, scene_args['resolution'],
            return_period, pra_size, None)
        yield jb, pra_size
# -------------------------------------------------------


release_fileRE = re.compile(r'^(.+)(\d\d\d\d\d)?(NoFor|For)_(\d+)m_(\d+)(T|S|M|L)_(.*)(\..*)')

@functools.lru_cache()
def parse_release_file(release_file):
    """Parses the full name of a release file into a RammsName.

    NOTE: This is only good for release files in CHUNK/ directories,
          not the original release files they were made from.
    """

    RELEASE_dir,leaf = os.path.split(release_file)
    ramms_dir = os.path.split(RELEASE_dir)[0]
    ramms_harness = os.path.abspath(os.path.split(ramms_dir)[0])
    match = release_fileRE.match(leaf)

    if match is None:
        raise ValueError('Cannot parse RELEASE file: {}'.format(release_file))

    scene_name = match.group(1)
    segment = None if match.group(2) is None else int(match.group(2))    # Works for CHUNKS/ or RELEASE/ release files.
    forest = True if match.group(3) == 'For' else False
    resolution = int(match.group(4))
    return_period = int(match.group(5))
    pra_size = match.group(6)
    file_type = match.group(7)    # eg: _rel
    ext = match.group(8)          # eg: shp

    return RammsName(ramms_harness, scene_name, segment, forest, resolution, return_period, pra_size, None)

# --------------------------------------------------------
def job_ids(release_file):
    """Reads a release file, and returns a (sorted) list of PRA IDs in that file."""
    release_df = shputil.read_df(release_file, read_shapes=False)
    return sorted(list(release_df['Id']))
# --------------------------------------------------------

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

def chunks_csv(scene_dir, ramms_name):
    """Returns name of the _chunks.csv control file for top-level (non-split) shapefiles."""
    #return os.path.join(scene_dir, 'RELEASE', f'{ramms_name}_chunks.csv')
    return os.path.join(scene_dir, 'stage0', f'{ramms_name}_chunks.csv')

#def release_csv(scene_dir, ramms_name):
#    """Returns name of the _release.csv for top-level (non-split) shapefiles."""
#    #return os.path.join(scene_dir, 'RELEASE', f'{ramms_name}_chunks.csv')
#    return os.path.join(scene_dir, 'stage0', f'{ramms_name}_release.csv')


def _get_release_files(spec):
    """Given a directory above or below the CHUNKS directory, finds a
    "ramms dir," which is one level below CHUNKS/."""

    # *** The spec is a directory corresponding to a SINGLE shapefile
    # ** The spec is a SINGLE shapefile
    if spec.endswith('.shp'):
        return [spec]

    # See if we're in the main Scene directory
    dir = os.path.abspath(spec)
    CHUNKS = os.path.join(dir, 'CHUNKS')
    if os.path.isdir(CHUNKS):
        release_files = []
        stage0_dir = os.path.join(dir, 'stage0')
        for leaf in os.listdir(stage0_dir):
            if not leaf.endswith('_chunks.csv'):
                continue
            df = pd.read_csv(os.path.join(stage0_dir, leaf))
            if config.max_chunks is not None:
                df = df[df['segment'] < config.max_chunks]    # Cut down based on config

            for chunk_name in df['chunk_name'].unique():
                chunk_dir = os.path.join(dir, 'CHUNKS', chunk_name)
                release_files += _get_release_files(chunk_dir)
        return release_files
            
    parts = dir.split(os.sep)

    # See if we're in, eg:
    #   RAMMS/juneau1017For_5m_30L/RESULTS/juneau1017For_5m/30L
    # Return just the shapefile
    if len(parts) >=3 and parts[-3] == 'RESULTS':
        parts2 = parts[:-3] + ['RELEASE', '{}_{}_rel.shp'.format(parts[-2], parts[-1])]
        return [os.sep.join(parts2)]


    # See if we're in a subdirectory
    for i in range(len(parts)):
        if parts[i] == 'CHUNKS':
            # CHUNKS/ is the last part of the path, we have multiple dirs.
            if i == len(parts)-1:
                ramms_dirs = [os.path.join(dir,x) for x in os.listdir(dir)]
                print('ramms_dirs ', ramms_dirs)
                return _ramms_to_release(ramms_dirs)
            else:
                # We have a path one lower than CHUNKS, use it.
                return _ramms_to_release([os.sep.join(parts[:i+2])])

    raise ValueError('Could not interpret spec {} as one or more RAMMS dirs'.format(spec))

def sort_release_files(ret):
    jbs = [(parse_release_file(release_file).key(), release_file) for release_file in ret]
    jbs.sort()
    release_files = [rf for _,rf in jbs]
    return release_files

def get_release_files(spec):
    # Expand wildcards
    specs = glob.glob(spec)
    if len(specs) == 0:
        return _get_release_files(spec)

    ret = list()
    for spec1 in specs:
        ret += _get_release_files(spec1)

    # Sort!
    return sort_release_files(ret)
# ---------------------------------------------------------
def read_polygon_from_zip(in_zip, poly_file):
    """Reads a RAMMS polygon file (eg: .dom) into a Shapely Polygon.
    in_zip:
        Open handle to {job_name}.in.zip
    poly_file:
        The arcname (archive name) of the file to read from the open zipfile"""
    with io.StringIO(in_zip.read(poly_file).decode('UTF-8')) as fin:
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

def write_polygon_to_zip(p, out_zip, arcname):
    """out_zip:
        Open zipfile
    """
    out = io.StringIO()

    coords = list(p.boundary.coords)
    out.write('{}'.format(len(coords)))
    for x,y in coords:
        out.write(f' {x} {y}')
    out.write('\n')

    # Write it to the ZipFile
    out_zip.writestr(arcname, out.getvalue())
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
def oramms_mapping(oramms_harness, release_files):

    """Collects tuple of source info from a RammsName.  In preparation
    for determing ORAMMS project names for Stage 3 assembly.

    Returns: {oramms_names: [release_file, ...], ...}
        Grouping of release files by output RAMMS name (tuple of args to RammsName())

    """

    # Assemble dataframe of original release files
    rows = list()
    for release_file in release_files:
        jb = parse_release_file(release_file)
        rows.append(jb.args)    # jb.args = dict of original arguments to RammsName constructor
    df = pd.DataFrame(rows)

    # Boil down input RAMMS Names into output...
    # Foreach optional col:
    #   If all rows have same value:
    #      leave at that value
    #   Else:
    #      set all rows to None

    for colname in RammsName.optional_cols:
        col = df[colname]
        val0 = col.iloc[0]
        if (not (col == val0).all()):
            df[colname] = None

    # Don't include segment in ORAMMS name in any case!
    df['segment'] = None

    # Determine output RAMMS name for each item
    oramms_names = dict()
    for ix,row in df.iterrows():
        oramms_name = tuple((oramms_harness, *(row[x] for x in RammsName.all_cols[1:])))
        if oramms_name not in oramms_names:
            oramms_names[oramms_name] = list()
        oramms_names[oramms_name].append(release_files[ix])

    return oramms_names

def groupby_oramms(release_files):
    """Groups a bunch of piecewise release files into output RAMMS
    runs.

    Yields: (oramms_name, [release_file, ...])
        oramms_name: RammsName:
            Name of an ORAMMS run to assemble and use.
        [release_file, ...]
            Constituent RAMMS runs to assemble into oramms_name
    """
    # Assume all in same harness
    jb = parse_release_file(release_files[0])
    oramms_harness = os.path.join(os.path.dirname(jb.ramms_harness), 'ORAMMS')

    for args,release_files in oramms_mapping(oramms_harness, release_files).items():
        ojb = RammsName(*args)
        yield ojb, release_files


# ------------------------------------------------
