import typing,re,os

# ---------------------------------------------------------------------
def is_file_good(fname):
    # Make sure file exists in non-zero length
    if not os.path.exists(fname):
        return False
    if os.path.getsize(fname) == 0:
        return False
    return True
    
# --------------------------------------------------------------------
class ComboInfo(typing.NamedTuple):
    """Key input files needed for a combo"""
    scene_dir: object
    dem_file: object
    landcover_file: object
    forest_file: object
    snow_file: object

# ---------------------------------------------------------------------
class ChunkInfo(typing.NamedTuple):
    """Describe<s one chunk."""

    # Eg: /home/efischer/prj/ak/bak/ak-ccsm-1981-1990-lapse-For-30/x-113-045/CHUNKS/x-113-0450000030SFor_10m
    #dir: pathutil.Path

    scene_dir: str
    scene_name: str        # Eg: x-113-045
    chunkid: int                # Eg: 17
    For: str            # For / NoFor
    resolution: int    # 10
    return_period: int
    pra_size: str    # TSML

    @property
    def chunk_name(self):
        """{scene_dir}/CHUNKS/{chunk_name}"""
        return f'c-{self.pra_size}-{self.chunkid:05}'

    @property
    def chunk_dir(self):
        return self.scene_dir / 'CHUNKS' / self.chunk_name

    @property
    def slope_name(self):
        """{scene_dir}/CHUNKS/{chunk_name}/RESULTS/{slope_name}/{return_period}{pra_size}"""
        return f'{self.chunk_name}{self.For}_{self.resolution}m'    # Used for DEM / Forest files

    @property
    def slope_dir(self):
        return self.chunk_dir / 'RESULTS' / self.slope_name

    @property
    def avalanche_name(self):
        return f'{self.return_period}{self.pra_size}'

    @property
    def avalanche_dir(self):
        return self.slope_dir / self.avalanche_name

def inout_name(jb, chunkid, id):
    """Helper function used in a few places"""
    return f'c-{jb.pra_size}-{chunkid:05d}{jb.For}_{jb.resolution}m_{jb.return_period}{jb.pra_size}_{id}'

def chunk_info(scene_args, pra_size, chunkid):
    return ChunkInfo(
        scene_args['scene_dir'],
        scene_args['name'], chunkid,
        'For' if scene_args.forests[0] else 'NoFor',
        scene_args['resolution'],
        scene_arsgs['return_periods'][0],
        pra_size)

# ---------------------------------------------------------------------
chunk_release_fileRE = re.compile(r'c-([TSML])-(\d\d\d\d\d)(For|NoFor)_(\d+)m_(\d+)([TSML])_rel.shp')
def parse_chunk_release_file(release_file):
    leaf = release_file.parts[-1]
    match = chunk_release_fileRE.match(leaf)

    if match is None:
        return None

    scene_dir = release_file.parents[3]
#    scene_args = params.load(scene_dir)
    return ChunkInfo(
        scene_dir,
        scene_dir.parts[-1], #scene_name
        int(match.group(2)),    # chunkid
        match.group(3),        # For
        int(match.group(4)),    # resolution
        int(match.group(5)),    # return_period
        match.group(1))        # pra_size
