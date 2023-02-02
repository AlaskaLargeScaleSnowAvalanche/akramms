import os,re,typing,functools

PRA_SIZE_NAMES = ('tiny', 'small', 'medium', 'large')
PRA_SIZES = ('T', 'S', 'M', 'L')
# ---------------------------------------------------------------
class RammsRun(typing.NamedTuple):
    ramms_dir: str    # Directory just under RAMMS/
    scene_name: str
    forest: bool
    resolution: int
    return_period: int
    pra_size: str

    @property
    def scenario_name(self):
        For = 'For' if self.forest else 'NoFor'
        return f"{self.scene_name}{For}_{self.resolution}m_{self.return_period}{self.pra_size}"

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
        return os.path.join(ramms_dir, 'RESULTS',
            f'{self.scene_name}{For}',
            f'{self.resolution}m_{self.return_period}{self.pra_size}')

    def log_zip(self, id):
        return os.path.join(self.run_dir, '{}_{}.log.zip'.format(self.base, id))

    def arcname(self, id, ext):
        """Name of the logfile in the Zip archive
        extname:
            .log or .overrun
        """
        return '{}_{}{}'.format(self.base, id, ext)

def ramms_name(*args, **kwargs):
    return RammsRun(None, *args, **kwargs).scenario_name

# -------------------------------------------------------
release_fileRE = re.compile(r'^(.+)(NoFor|For)_(\d+)m_(\d+)(T|S|M|L)_(.*)\.(.*)')

@functools.lru_cache()
def parse_release_file(release_file):
    """Parses the full name of a release file into a RammsRun named tuple."""

    RELEASE_dir,leaf = os.path.split(release_file)
    ramms_dir = os.path.split(RELEASE_dir)[0]
    match = release_fileRE.match(leaf)

    scene_name = match.group(1)
    For = match.group(2)
    forest = True if For == 'For' else False
    resolution = int(match.group(3))
    return_period = int(match.group(4))
    pra_size = match.group(5)
    file_type = match.group(6)    # eg: _rel
    ext = match.group(7)          # eg: shp

    return RammsRun(
        ramms_dir,
        scene_name, forest, resolution, return_period, pra_size)

