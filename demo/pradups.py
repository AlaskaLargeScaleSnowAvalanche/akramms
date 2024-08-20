import zipfile,re,glob,pathlib,os,functools,subprocess
import shapely.validation
import pandas as pd
import geopandas
import akramms.experiment.ak as expmod

dir0 = expmod.dir / 'ak-ccsm-1981-2010-lapse-For-30/arc-087-037'
dir1 = expmod.dir / 'ak-ccsm-1981-2010-lapse-For-30/arc-087-038'
arcRE = re.compile('arc-(\d+)-(\d+)')
releaseRE = re.compile('release-(\d+)-(\d+).gpkg')

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
    df = geopandas.read_file(str(release_gpkg))
    df['savedindex'] = df.index
    return df

def find_neighbor_dups(rel1_gpkg, rel2_gpkg):
    """Finds the PRAs that mostly overlap in two adjacent tiles.
    rel1_gpkg, rel2_gpkg:
        Names of djacent release-<idom>-<jdom>.gpkg files
    """

    # Follow this
    # https://gis.stackexchange.com/questions/418283/find-and-remove-overlapping-polygons-with-geopandas

    df1 = read_release_gpkg(rel1_gpkg)
    df2 = read_release_gpkg(rel2_gpkg)

    if len(df1) == 0 or len(df2) == 0:
        return None

#    df2['savedindex']= df2.index #Save the index values as a new column

    sj = df1.sjoin(df2, how='inner')
    if len(sj) == 0:
        return None

#    print('sjjjjjjjjjjjjjjjjjjjj ', sj.columns)
    inter = sj['savedindex_right'] #Find the polygons that intersect. Keep savedindex as a series

#    df_overlap = df2[~df2.savedindex.isin(intersecting)] #Filter away these, "savedindex is not in intersecting"
#    return df_overlap

    idup = 0
    dups = list()
    idups = list()
    for ix1,ix2 in inter.items():

        # make_valid() is used here to ensure the intersection() method works
        pra1 = shapely.validation.make_valid(df1.loc[ix1].geometry)
        pra2 = shapely.validation.make_valid(df2.loc[ix2].geometry)

        inter_geom = pra1.intersection(pra2)

        inter_area = inter_geom.area
        inter_pct1 = inter_area / pra1.area
        inter_pct2 = inter_area / pra2.area
        inter_pct = max(inter_pct1, inter_pct2)
        if inter_pct > .9:
            dups.append(df1.loc[ix1])
            idups.append(idup)
            dups.append(df2.loc[ix2])
            idups.append(idup)
            idup += 1
    if len(dups) == 0:
        return None

    df = geopandas.GeoDataFrame(dups).reset_index()
    delcols = [column for column in df.columns if column.startswith('savedindex')]
    df = df.drop(['index'] + delcols, axis=1)
    return df

def find_all_dups(release_dir):
    """
    release_dir:
        Directory containing release-<idom>-<jdom>.gpkg files
        for a single section.
    """
    work_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_work')

    # Identify available tiles
    files = dict()
    for name in sorted(os.listdir(release_dir)):
        match = releaseRE.match(name)
        if match is None:
            continue
        idom = int(match.group(1))
        jdom = int(match.group(2))

        files[(idom,jdom)] = release_dir / name

    # Identify pairs
    complete = set()    # Completed pairs
    for ijdom0,release_gpkg0 in files.items():
        ofname = work_dir / 'dups' / f'dups-{ijdom0[0]:03d}-{ijdom0[1]:03d}.gpkg'
        if os.path.isfile(ofname):
            continue

        print(f'============ {ofname}')
        dfs = list()
        for delta_ijdom in ((-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)):
            ijdom1 = (ijdom0[0] + delta_ijdom[0], ijdom0[1] + delta_ijdom[1])

            # Make sure this pair exists (ijdom0 might be at an edge
            # with reduced neighbors)
            if ijdom1 not in files:
                continue

            ijdom_pair = (ijdom0, ijdom1) if ijdom0 < ijdom1 else (ijdom1, ijdom0)

            # Only do each pair once
            if ijdom_pair in complete:
                continue

            df = find_neighbor_dups(release_gpkg0, files[ijdom1])
            if df is not None:
                print(f'---------- {ijdom0} {ijdom1}: {len(df)}')
                dfs.append(df)
            complete.add((ijdom0, ijdom1))

        if len(dfs) > 0:
            df = pd.concat(dfs)
            os.makedirs(ofname.parents[0], exist_ok=True)
            df.to_file(str(ofname), driver='GPKG')
        else:
            with open(ofname, 'wb') as out:
                pass

    
def merge_all_dups1(dups_dir):
    ofname = dups_dir.parents[0] / 'dups.gpkg'
    cmd = ['ogrmerge.py', '-f', 'GPKG', '-o', ofname]
    for name in sorted(os.listdir(dups_dir)):
        ifname = dups_dir / name
        if os.path.getsize(ifname) > 0:
            cmd.append(str(ifname))

    print(cmd)
    subprocess.run(cmd, check=True)

def merge_all_dups(dups_dir):
    ofname = dups_dir.parents[0] / 'dups.gpkg'
    dfs = list()
    for name in sorted(os.listdir(dups_dir)):
        ifname = dups_dir / name
        if os.path.getsize(ifname) > 0:
            print(f'...{name}')
            dfs.append(geopandas.read_file(str(ifname)))

    df = pd.concat(dfs)
    df.to_file(str(ofname), driver='GPKG')




def main():
#    read_release_zip(dir0 / 'RELEASE.zip')
#    rewrite_release_gpkgs(expmod)

    work_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_work')
    release_root = work_dir / 'release'
    section = 'ak-ccsm-2031-2060-lapse-For-30'
    rel1_gpkg = release_root / section / 'release-113-045.gpkg'
    rel2_gpkg = release_root / section / 'release-113-044.gpkg'

#    inter = find_neighbor_dups(rel1_gpkg, rel2_gpkg)
#    find_all_dups(release_root / section)

    merge_all_dups(work_dir / 'dups')
main()


