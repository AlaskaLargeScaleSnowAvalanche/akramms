from uafgi.util import shputil
import os,re

# ---------------------------------------------------------------
class ParsedJobBase(typing.NamedTuple):
    run_dir: str    # Full pathname, eg. .../juneau1_For/5m_30L  <ramms_dir>/RESULTS/<prefix>/<suffix>
    base: str
    prefix: str
    suffix: str

    def log_zip(self, id):
        return os.path.join(self.run_dir, '{}_{}.log.zip'.format(self.base, id))

    def arcname(self, id, ext):
        """Name of the logfile in the Zip archive
        extname:
            .log or .overrun
        """
        return '{}_{}{}'.format(self.base, id, ext)


# -------------------------------------------------------
_job_baseRE = re.compile(r'^(.+_.+)_(.+_.+)$')
@functools.lru_cache()
def parse_job_base(ramms_dir, job_base):
    """
    base:
        String of base of job names, with an avalanche ID.
        Eg: juneau1_For_5m_30L
    """
    print('job_base ',job_base)
    match = _job_baseRE.match(job_base)
    prefix = match.group(1)
    suffix = match.group(2)
    run_dir = os.path.join(ramms_dir, 'RESULTS', prefix, suffix)
    return ParsedJobBase(run_dir, job_base, prefix, suffix)

@functools.lru_cache()
def parse_release_file(release_file):
    """Parses the full name of a release file into a ParsedJobBase named tuple."""

    RELEASE_dir,shapefile = os.path.split(release_file)
    ramms_dir = os.path.split(RELEASE_dir)[0]
    base = shapefile[:-8]    # remove _rel.shp
    return parse_job_base(ramms_dir, base)

def get_job_ids(release_file):
    """Reads a release file, and returns a (sorted) list of PRA IDs in that file."""
    release_df = shputil.read_df(release_file, read_shapes=False)
    return sorted(list(release_df['Id']))
