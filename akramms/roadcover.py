import os,pickle,gzip,shutil,zipfile,functools,subprocess
import numpy as np
import pandas as pd
import geopandas
import shapely
from uafgi.util import make,gdalutil,lineintegral,shapelyutil
from akramms import config
#from akramms.experiment import aksc5 as expmod

"""Analyze Extent IDs that overlap roads."""

mileposts_pik_gz = config.HARNESS / 'data/fischer' / 'mileposts2.pik.gz'
def load_road_segments():
    with gzip.open(mileposts_pik_gz, 'rb') as fin:
        roaddf = pickle.load(fin)
    roaddf['geometry'] = roaddf.geometry.force_2d()
    roaddf['seglen'] = roaddf.geometry.map(lambda x: x.length)
    roaddf = roaddf.reset_index().rename(columns={'index': 'Seg_ID'})
    return roaddf

def r_roadcover(expmod, acombo, combos):
    ifnames = [expmod.root_dir / 'ext' / f'{expmod.name}-{combo.base_str()}' / 'extent_christen' / f'{expmod.name}-{combo}-extent_christen.gpkg' for combo in combos]

    ofname = expmod.root_dir / 'roadcover' / f'{expmod.name}-{acombo.base_str()}-roadcover.gpkg'
#    mileposts_gpkg = config.HARNESS / 'data/fischer' / 'mileposts1.gpkg'


    def action(tdir):

        print(f'BEGIN r_roadcover with {len(combos)} combos')

        # Roads with Mileposts
#        roaddf = geopandas.read_file(mileposts_gpkg)
        roaddf = load_road_segments()


#        roaddf = roaddf[roaddf.Route_ID == '4441092X000']    # THane Road (Juneau)
        roaddf = roaddf[roaddf.Seg_ID==3627]    # THane Road (Juneau)   DEBUG

        idfs = list()
        for ix,(combo,ifname) in enumerate(zip(combos,ifnames)):
            # Open an extent
            print(f'{ix} of {len(ifnames)}: ', ifname.parts[-1])
            extdf = geopandas.read_file(ifname)
            extdf = extdf[['Id', 'rel_n', 'ext_n', 'geometry']]

            idf = geopandas.overlay(
                extdf[['Id', 'geometry']], roaddf, how='intersection', keep_geom_type=False)

            extdf = extdf.rename(columns={'geometry': 'extent'}).set_geometry('extent')
            idf = idf.merge(extdf, how='left', on='Id')
            idf = idf.drop(columns=['extent'])
            idf['affected_len'] = idf.geometry.map(lambda geom: geom.length)

            idf['exp'] = expmod.name
            for key in expmod.combo_keys:
                idf[key] = getattr(combo, key)

            if len(idf) > 0:
                idfs.append(idf)

        # Write output
        os.makedirs(ofname.parents[0], exist_ok=True)
        tmp_fname = f'{str(ofname)}.tmp'
        idf = pd.concat(idfs)
        idf['ijdoms'] = idf.ijdoms.map(repr)
        idf.to_file(tmp_fname, driver="GPKG")
#        with gzip.open(tmp_fname, 'wb') as out:
#            pickle.dump(pd.concat(idfs), out, protocol=pickle.HIGHEST_PROTOCOL)

        os.rename(tmp_fname, ofname)    # Atomic

    return make.Rule(action, ifnames + [mileposts_pik_gz], [ofname])
# -------------------------------------------------------------
#def r_combine(expmod, combos):
#    for combo in combos:
#        ileaf = f'{combo.base_str()}-roadcover.gpkg'
#        acombo = combo._replace(forest='All')
#
#
#
#    stems = [combo._replace(forest='All').base_str() for combo in combs]
#    ifnames = [expmod.root_dir / 'roadcover' / f'{stem}-roadcover.gpkg' for stem in stems]
#    ofname =     ifnames = [expmod.root_dir / 'roadcover' / f'{stem}-roadcover.gpkg' for stem in stems]
#
#
#
#
#    akdf = akdf.copy()
#    akdf['combo'] = akdf.combo.map(_repl
#
#    keys = [key for key in combo_keys if key not in {'forest', 'idom', 'jdom'}]
#    for key in expmod.combo_keys:
#        if key in {
#        akdf[key] = akdf.combo.map(lambda combo: getattr(combo, key))
#



# -------------------------------------------------------------
def _calc_integrations(df1):
    total_len = df1.len.sum()    # Divide by this when computing means...
    return pd.Series({
        'max_velocity': df1.max_velocity.max(),
        'interaction_length': total_len,
        'mean_deposition': (df1.len * df1.deposition).sum() / total_len,
        'max_deposition': df1.deposition.max(),
#        'naval': (df1.naval.min(), df1.naval.max()),
    })    

def _final_sum(df1):
#    print('dddddddddddf1 ')
#    print(df1)
    total_length = df1.interaction_length.sum()    # Divide by this when computing means...
#    print('ddddddddddddddddddddd ', (df1.interaction_length * df1.mean_deposition).sum() / total_length, total_length, list(df1.interaction_length))

    return pd.Series({
        'max_velocity': df1.max_velocity.max(),
        'interaction_length': total_length,
        'mean_deposition': (df1.interaction_length * df1.mean_deposition).sum() / total_length,
        'max_deposition': df1.max_deposition.max(),
        'naval': df1.iloc[0].naval,
        'geometry': df1.iloc[0].geometry,
#        'idom': df1.iloc[0].idom,
#        'jdom': df1.iloc[0].jdom,

    })    

def _remove_points(ls0):
    if not isinstance(ls0, shapely.geometry.GeometryCollection):
        return ls0
    mls = [ls1 for ls1 in ls0.geoms if not isinstance(ls1, shapely.geometry.Point)]
    return shapely.geometry.MultiLineString(mls)


def _raster_fname(expmod, acomboij, vname):
    val_tif = expmod.root_dir / 'publish' / f'{expmod.name}-{acomboij.base_str()}' / vname / f'{expmod.name}-{repr(acomboij)}-F-{vname}.tif'
    return val_tif


def r_integrate(expmod, acombo, ifname):

    """Computes all required line integrals and line integral-like
    functions between roads and rasters, for road segments that cross
    avalanche extents.

    expmod, combo:
        The combo to compute this for.
    """

#    ifname = expmod.root_dir / f'roadcover/{expmod.name}-{combo.base_str()}-roadcover.pik.gz'
#    ofname_base = expmod.root_dir / f'roadcover/{expmod.name}-{combo.base_str()}/{expmod.name}-{repr(combo)}-roadstats'
#    ofname = str(ofname_base) + '.shp.zip'

    ifname = expmod.root_dir / f'roadcover/{expmod.name}-{acombo.base_str()}-roadcover.gpkg'

    ofname = expmod.root_dir / 'roadcover' / f'{expmod.name}-{acombo.base_str()}-roadstats.gpkg'



    # Variables to read
    vnames = ['max_velocity', 'deposition']


    def action(tdir):

        # Read road segments that intersect with one or more avalanches
#        with gzip.open(ifname) as fin:
#           rdf = pickle.load(fin)
        rdf0 = geopandas.read_file(ifname)
        rdf0['ijdoms'] = rdf0.ijdoms.map(eval)
        rdf0['geometry'] = [shapely.force_2d(ls) for ls in rdf0.geometry]

        print('=============== geo1')
        print(rdf0.geometry)

#        # Get the grid for this tile
#        row = rdf0.iloc[0]
#        combo0 = expmod.combo(**{key: row[key] for key in expmod.combo_keys})
#        grid, _, _ = gdalutil.read_raster(val_tifs[0], False)
#
#        # Clip to within the margin
#        bbox = grid.bounding_box()
#        print('bbox ', bbox)
#        rdf0['geometry'] = [shapely.intersection(ls, bbox) for ls in rdf0.geometry]
#        print('geo2 ', rdf0.geometry)

        # -------------------------------------------------
        # Group linestrings together by Seg_ID
        # (Because one road segment can intersect multiple avalanche extents)
        rows = list()
        for Seg_ID, xdf in rdf0.groupby('Seg_ID'):
            # Join all avalanches on this segment into one (Multi?)LineString
            ls = shapely.union_all(xdf.geometry, grid_size=.000000001)
            ls = shapely.ops.linemerge(ls)


#            ls = shapely.unary_union(xdf.geometry)

            # ijdoms depends on Seg_ID, they will all be the same, choose the first
            ijdoms = xdf.iloc[0].ijdoms

            rows.append((Seg_ID, ijdoms, len(xdf), ls))
        rdf = geopandas.GeoDataFrame(rows, columns=('Seg_ID', 'ijdoms', 'naval', 'geometry'), geometry='geometry', crs=expmod.wkt)

        # Make a single ijdom per column
        rdf = rdf.explode('ijdoms', ignore_index=True).rename(columns={'ijdoms':'ijdom'})

#        df = rdf.groupby(['Seg_ID', 'ijdom']).size().reset_index()
#        print(df.groupby('Seg_ID').size().sort_values())
#        return
#        rdf = rdf[rdf.Seg_ID == 27849]    # DEBUG
#        rdf = rdf[rdf.Seg_ID == 17823]    # DEBUG
#        rdf = rdf[rdf.Route_ID == '4441092X000']    # THane Road (Juneau)
#        print(rdf)
#        return

        # ------------------------------------------------
        # Process by tile
        statsdfs = list()
#        print(rdf.iloc[0])
        for (idom, jdom), xdf in rdf.groupby('ijdom'):
#            print('===================================== AA1 ', idom, jdom, len(xdf))
#            print(xdf)

            # Load rasters to integrate over


            # Find line segment crossings, raster coordinates and lengths
            ifname1 = _raster_fname(expmod, acombo._replace(idom=idom, jdom=jdom), vnames[0])
            grid, _, _ = gdalutil.read_raster(ifname1, data=False)
            ijdf = lineintegral.linestrings_crossings(xdf.set_index('Seg_ID').geometry, grid, index_col_name='Seg_ID')

            if len(ijdf) > 0:
                # =============== Compute functions on rasters
                cols = dict()

                # Load rasters to integrate over
                for vname in vnames:
                    rfname = _raster_fname(expmod, acombo._replace(idom=idom, jdom=jdom), vname)
                    print('Integrating over ', rfname)
                    grid, val_data, val_nd = gdalutil.read_raster(rfname)
                    ijdf[vname] = val_data[ijdf.i, ijdf.j]

                # Do the integration
# #               print(ijdf)
# #               print(ijdf.columns)
                statsdf = ijdf.groupby('Seg_ID').apply(_calc_integrations) # Newer Pythons, include_groups=False)
#                print('===================== ijdf')
#                print(ijdf)
#                print(ijdf.index)
##                print('===================== statsdf')
##                print(statsdf)
##                print(statsdf.index)
##                print('===================== xdf')
##                print(xdf)
##                print(xdf.index)
###                print(xdf.loc['Seg_ID', statsdf.iloc[0].Seg_ID])

                statsdf = statsdf.merge(xdf, on=['Seg_ID'])
                statsdf = geopandas.GeoDataFrame(statsdf, crs=expmod.wkt)
                statsdf['idom'] = idom
                statsdf['jdom'] = jdom

                # Remove GeometryCollection by removing points
                statsdf.geometry = statsdf.geometry.map(_remove_points)

                statsdfs.append(statsdf)

#                print('===================== statsdf1')
                # naval here is the number of avalanches interacted
                # with for the entire Seg_ID, not just for this
                # (idom,jdom)

#                print(statsdf)
#                print(statsdf.index)
#                print(statsdf.iloc[0])
##                return

        statsdf = pd.concat(statsdfs)

        statsdf = statsdf[(statsdf.max_velocity != 0) | (statsdf.max_deposition != 0)]

        print('=================== Final1 statsdf')
        print(statsdf)

        # Merge tiles, and re-join with original road segment database
        statsdf = statsdf.groupby('Seg_ID').apply(_final_sum)
        mpdf = load_road_segments()
        statsdf = statsdf.merge(mpdf[['Seg_ID', 'Route_ID', 'Route_Name', 'Main_Route_Name', 'mp0', 'mp1', 'type', 'seglen']], on='Seg_ID', how='left')

#        print(mpdf.iloc[0])
#        return

        print('=================== Final2 statsdf')
        print(statsdf)
        print(statsdf.iloc[0])



#            else:
#                statsdf = geopandas.GeoDataFrame([], columns=('Seg_ID', 'max_velocity', 'length', 'mean_deposition', 'max_deposition', 'geometry'))
#
#
#
#        else:
#            statsdf = geopandas.GeoDataFrame([], columns=('Seg_ID', 'max_velocity', 'length', 'mean_deposition', 'max_deposition', 'geometry'))

        print('Writing ', ofname)
        statsdf.set_crs(epsg=3338)
        statsdf.to_file(str(ofname), driver='GPKG', crs='EPSG:3338', engine='fiona')


        cmd = ['ogr2ogr', '-f', 'CSV', ofname.with_suffix('.csv'), ofname]
        subprocess.run(cmd, check=True)
#ogr2ogr -f "CSV" aksc5-ccsm-past-sclapse-All-30-roadstats.csv aksc5-ccsm-past-sclapse-All-30-roadstats.gpkg 


#        # Write shapefile to a directory
#        tdir = ofname_base.with_suffix('.tmp')
#        shutil.rmtree(tdir, ignore_errors=True)
#        os.makedirs(tdir, exist_ok=True)
#        statsdf.to_file(str(tdir / (ofname_base.parts[-1] + '.shp')))#, driver="ESRI Shapefile")
#
#        # Zip it up
#        tmp_zip = ofname_base.with_suffix('.zip.tmp')
#        with zipfile.ZipFile(tmp_zip, 'w', zipfile.ZIP_DEFLATED) as ozip:
#            for name in os.listdir(tdir):
#                ozip.write(tdir / name, name)
#
#        os.rename(tmp_zip, ofname)    # Atomic
#
#        # Clean up
#        shutil.rmtree(tdir, ignore_errors=True)
#        try:
#            os.remove(tmp_zip)
#        except FileNotFoundError:
#            pass
##        tmp_zip.unlink(missing_ok=True)

    return make.Rule(action, [ifname], [ofname, ofname.with_suffix('.csv')])
