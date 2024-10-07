import pathlib,os,glob
import geopandas
import shapely.geometry
import pandas as pd
from akramms import archive,level





# ----------------------------------------------------
def land_stats
# ----------------------------------------------------

def read_extent(fname):
    """Reads an extent file and post-processes into MultiPolygons"""
    extdf = geopandas.read_file(fname)

    ids = list()
    mpolys = list()
    for id,df1 in extdf.groupby('Id'):
        ids.append(id)
        polys = list(df1.geometry)
        mpolys.append(shapely.geometry.MultiPolygon(list(df1.geometry)))
    return geopandas.GeoDataFrame(ids, columns=('Id',), crs=extdf.crs, geometry=mpolys)


def read_full_extents(arcdir):

    """Union of thresholded and full extent is the ACTUAL full extent
    (due to bug in how they were originally computed.)"""

    ext_threshold_df = read_extent(arcdir / 'extent.gpkg')    # Thresholded
    ext_full_df = read_extent(arcdir / 'extent_full.gpkg')  # Full extent
    extdf = ext_full_df.merge(ext_threshold_df, on='Id', how='inner')

    unions = [shapely.unary_union(xy) for xy in zip(extdf.geometry_x, extdf.geometry_y)]

    ids = list(extdf.Id)
    extdf = geopandas.GeoDataFrame(ids, columns=('Id',), crs=ext_full_df.crs, geometry=unions)
    return extdf



def read_pras(arcdir):
    combo = level.theory_scenedir_to_combo(arcdir)
    pra_sizes = ('T', 'S') if combo.forest == 'For' else ('M', 'L')

    reldf = archive.read_reldom(arcdir / 'RELEASE.zip', 'rel')
    reldf = reldf[reldf.pra_size.isin(pra_sizes)]   # Only use PRAs active for For vs. NoFor run
    return reldf


def arcdir_stats(arcdir):

Divide by pra_size and 3km^2 sub-tiles:

pra_area
extent_area
extent_area_full
navalanche

land_area
forest_area



    combo = level.theory_scenedir_to_combo(arcdir)
    pra_sizes = ('T', 'S') if combo.forest == 'For' else ('M', 'L')

    print(f'========= {arcdir} (pra_sizes {pra_sizes})')

    extdf = read_full_extents(arcdir)
    print('xxxxxxxxxx ', len(extdf))

    return




















    reldf = archive.read_reldom(arcdir / 'RELEASE.zip', 'rel')
    reldf = reldf[reldf.pra_size.isin(pra_sizes)]   # Only use PRAs active for For vs. NoFor run
    n_rel = len(reldf)

    extdf = geopandas.read_file(arcdir / 'extent.gpkg')
    n_ext = len(extdf.Id.unique())    # Multiple polygons per Id

    efdf = geopandas.read_file(arcdir / 'extent_full.gpkg')
    n_ext = len(extdf.Id.unique())    # Multiple polygons per Id

    n_files = len(glob.glob(str(arcdir / 'aval-*-.nc')))

    print(f'After corrections this combo has {n_rel} PRAs, {n_ext} extent polygons and {n_files} Avalanche files')

def main():
    arcdir = pathlib.Path(os.environ['HOME']) / 'prj/ak/ak-ccsm-1981-2010-lapse-For-30/arc-119-053'
    arcdir_stats(arcdir)

main()
