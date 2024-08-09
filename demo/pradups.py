import zipfile,re,glob,pathlib,os,functools
import pandas as pd
import geopandas
import akramms.experiment.ak as expmod

dir0 = expmod.dir / 'ak-ccsm-1981-2010-lapse-For-30/arc-087-037'
dir1 = expmod.dir / 'ak-ccsm-1981-2010-lapse-For-30/arc-087-038'
arcRE = re.compile('arc-(\d+)-(\d+)')

def arc_to_ijdom(arc_dir_leaf):
    match = arcRE.match(arc_dir_leaf)
    idom = int(match.group(1))
    jdom = int(match.group(2))
    return idom,jdom

def read_release_zip(release_zip):
    """Reads the RELEASE.zip file into a dataframe"""

    idom,jdom = arc_to_ijdom(release_zip.parts[-2])

    dfs = list()
    with zipfile.ZipFile(release_zip, mode='r') as izip:
        infos = izip.infolist()
        for info in infos:
            if not info.filename.endswith('_rel.shp'):
                continue
            if info.file_size == 0:
                continue

            fname = f'/vsizip/{release_zip}/{info.filename}'
            print(f'Reading {fname}')
            df = geopandas.read_file(fname)
            df['idom'] = idom
            df['jdom'] = jdom
            dfs.append(df)

    df = pd.concat(dfs)
    print(df)
    print(df.columns)
    return df

def rewrite_release_gpkgs(expmod):

    """Reads all the RELEASE.zip files and copies them over to a
    single directory of release-<idom>-<jdom>.gpkg files."""

    work_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_work')
    release_dir = work_dir / 'release'
    for release_zip in sorted(glob.glob(str(expmod.dir / f'{expmod.name}-*' / 'arc-*' / 'RELEASE.zip'))):
        release_zip = pathlib.Path(release_zip)
        base = release_zip.parts[-3]    # Eg: ak/ak-ccsm-1981-2010-lapse-For-300
        idom,jdom = arc_to_ijdom(release_zip.parts[-2])
        # release_gpkg = release_dir / base / f'{base}-{idom:03d}-{jdom:03d}.gpkg'
        release_gpkg = release_dir / base / f'release-{idom:03d}-{jdom:03d}.gpkg'

        if not os.path.isfile(release_gpkg):
            print(release_zip)
            print(f'    ---> {release_gpkg}')
            os.makedirs(release_gpkg.parents[0], exist_ok=True)
            df = read_release_zip(release_zip)
            df.to_file(str(release_gpkg), driver='GPKG')


@functools.lru_cache(maxsize=30)
def read_release_gpkg(release_gpkg):
    """Caches reads of release files"""
    return geopandas.read_file(str(release_gpkg))

def find_dups(rel1_gpkg, rel2_gpkg):
    """Finds the PRAs that mostly overlap in two adjacent tiles.
    rel1_gpkg, rel2_gpkg:
        Names of djacent release-<idom>-<jdom>.gpkg files
    """

    # Follow this
    # https://gis.stackexchange.com/questions/418283/find-and-remove-overlapping-polygons-with-geopandas

    df1 = read_release_gpkg(rel1_gpkg)
    df2 = read_release_gpkg(rel2_gpkg)

    df2['savedindex']= df2.index #Save the index values as a new column

    inter = df1.sjoin(df2, how='inner')['savedindex'] #Find the polygons that intersect. Keep savedindex as a series

#    df_overlap = df2[~df2.savedindex.isin(intersecting)] #Filter away these, "savedindex is not in intersecting"
#    return df_overlap

    idup = 0
    dups = list()
    idups = list()
    for ix1,ix2 in inter.items():
        pra1 = df1.loc[ix1].geometry
        pra2 = df2.loc[ix2].geometry
        inter_area = pra1.intersection(pra2).area
        inter_pct1 = inter_area / pra1.area
        inter_pct2 = inter_area / pra2.area
        inter_pct = max(inter_pct1, inter_pct2)
#        inter_pct = 0.5 * (inter_pct1 + inter_pct2)
        print(ix1, ix2, inter_pct)
#        print('=====================================================')
#        print(df1.loc[ix1])
#        print('---------------------------------')
#        print(df2.loc[ix2])
        if inter_pct > .9:
            dups.append(df1.loc[ix1])
            idups.append(idup)
            dups.append(df2.loc[ix2])
            idups.append(idup)
            idup += 1
#            print(df1.loc[ix1])
#            print(df2.loc[ix2])
    df = pd.DataFrame(dups).reset_index().drop(['index', 'savedindex'], axis=1)
    return df

#    return intersecting

def main():
#    read_release_zip(dir0 / 'RELEASE.zip')
#    rewrite_release_gpkgs(expmod)

    work_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_work')
    release_dir = work_dir / 'release'
    section = 'ak-ccsm-2031-2060-lapse-For-30'
    rel1_gpkg = release_dir / section / 'release-113-045.gpkg'
    rel2_gpkg = release_dir / section / 'release-113-044.gpkg'

    inter = find_dups(rel1_gpkg, rel2_gpkg)
#    print(type(inter))
#    print(df_overlap)
#    print(df_overlap.columns)

main()


