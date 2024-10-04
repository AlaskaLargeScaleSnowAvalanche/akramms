import pathlib,os,glob
import geopandas
from akramms import archive,level


def arcdir_stats(arcdir):

    combo = level.theory_scenedir_to_combo(arcdir)
    pra_sizes = ('T', 'S') if combo.forest == 'For' else ('M', 'L')


    print(f'========= {arcdir}')

    reldf = archive.read_reldom(arcdir / 'RELEASE.zip', 'rel')
    print(f'The release file has {len(reldf)} PRAs, including size categories not run for this For / NoFor run')
    print('   ...ignoring PRAs of size categories not used in this combo...')
    reldf = reldf[reldf.pra_size.isin(pra_sizes)]   # Only use PRAs active for For vs. NoFor run
    n_rel = len(reldf)

    extdf = geopandas.read_file(arcdir / 'extent.gpkg')
    print(f'The extent file has {len(extdf)} polygons total, including more than one per avalanche')
    print('   ...consolidating polygons by Id...')
    n_ext = len(extdf.Id.unique())    # Multiple polygons per Id

    n_files = len(glob.glob(str(arcdir / 'aval-*-.nc')))

    print(f'After corrections this combo has {n_rel} PRAs, {n_ext} extent polygons and {n_files} Avalanche files')

def main():
    arcdir = pathlib.Path(os.environ['HOME']) / 'prj/ak/ak-ccsm-1981-2010-lapse-For-30/arc-119-053'
    dir_stats(arcdir, ['T','S'])

main()
