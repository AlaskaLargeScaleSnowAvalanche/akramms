import statistics,math,pickle,gzip
from osgeo import ogr,gdal
import shapely
from akramms import config
import geopandas
import pandas as pd
from akramms.experiment import aksc5
from uafgi.util import shapelyutil

BEGIN = 0.0    # Begin sentinel marker 
END = 9999.0    # End sentinel marker for road




# =====================================================
# ------------------------------------------------------------------------------
def _iterate_Point(ls):
#    return
#    yield None
    yield from ()    # Yield nothing

def _iterate_LineString(ls):
    for p0,p1 in zip(ls.coords[:-1], ls.coords[1:]):
        yield p0,p1
#        yield p0[0], p0[1], p1[0], p1[1]
def _iterate_collection(ls):
    for part in ls.geoms:
        yield from iterate_ls(part)

_iterate_ls = {
    shapely.geometry.Point: _iterate_Point,
    shapely.geometry.LineString: _iterate_LineString,
    shapely.geometry.GeometryCollection: _iterate_collection,
    shapely.geometry.MultiLineString: _iterate_collection,
}


def iterate_ls(ls):
    """
    Iterates the line segments in a LineString or MultiLineString
    (This is a facade to iterate through either one)

    ls:
        LineString or MultiLineString
    yields:
        x0,y0,x1,y1: float
            Each line segment
    """
    try:
        xiter_fn = _iterate_ls[type(ls)]
    except KeyError:
        raise TypeError(f'I do not know how to iterate over {ls}')

    result = yield from xiter_fn(ls)
    return result

# =========================================================
#
# Roads
# =====
# Route_ID                                            1000000R001
# From_Date                                            2009-10-26
# To_Date                                              1899-12-30
# CDS_Num                                                  116803
# Route_Loca                                                  100
# Route_Numb                                                 0000
# Route_Type                                                    R
# Route_Qual                                                  001
# Edit_Comme                                                 None
# created_us                                            AKDOT_GIS
# created_da                                           2026-05-07
# last_edite                                            AKDOT_GIS
# last_edi_1                                           2026-05-07
# Route_Name                                     Sterling Highway
# Route_Na_1                                                 None
# GlobalID                   472c0ec5-d300-4a06-80ec-37cbb3f61369
# Route_Na_2                         Sterling SB Wye (Kenai Spur)
# Route_Na_3      Sterling SB Wye (Kenai Spur) (Sterling Highway)
# Seg_Length                                             0.055534
# Geometry_U                                          Not Started
# Geometry_1                                                 None
# geometry      LINESTRING (161155.84720000066 1170319.3071999...
# Name: 0, dtype: object
# 
# Mileposts
# =========
# Event_ID       {6787C2C0-377D-4B12-BB23-3468D5842657}
# Route_ID                                  1120000X000
# Field_Esta                                 1899-12-30
# From_Date                                  2016-05-27
# To_Date                                    1899-12-30
# MPT                                        103.669536
# Edit_Comme                                       None
# Side                                                R
# Frame_ID                                        20863
# Collection                                          4
# Collecti_1                                       2015
# Milepost_N                                      104.0
# LocError                                     NO ERROR
# Status                                              3
# GlobalID         1f01e416-c5b4-4ad2-bd0e-c1fa77b9e592
# created_us                                  AKDOT_GIS
# created_da                                 2024-09-06
# last_edite                                  AKDOT_GIS
# last_edi_1                                 2024-09-06
# Milepost_R        104,Denali Highway (Denali Highway)
# Route_Name            Denali Highway (Denali Highway)
# Route_Na_1                             Denali Highway
# geometry      POINT (297206.68099999987 1492396.7533)

M_IN_MI = (5280*.3048)

#class Route_ID(typing.NamedTuple):
#    Route_ID: str
#    maindf: geopandas.GeoDataFrame
##    offdf: geopandas.GeoDataFrame

def compute_mileposts():

    mpdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'Mileposts_AKDOT_-4629016772512910170.zip')
    mpdf["geometry"] = mpdf["geometry"].map(shapely.force_2d)
    rdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'Roads_AKDOT_6350608895875630378.zip')
    rdf["geometry"] = rdf["geometry"].map(shapely.force_2d)

#    print('All route names: ', set(rdf.Route_Name))
#    rdf = rdf[rdf.Route_Name == 'Seward Highway']

#    rdf = rdf.head(100)    # DEBUG


    # Segment "main" highways, i.e. those with mileposts
    maindfs = list()
    ix=0
    for tup in rdf.itertuples(index=False):
        mpdf1 = mpdf[mpdf.Route_ID == tup.Route_ID]
        if len(mpdf1) == 0:
            continue

        print(f'======== {tup.Route_Name} - {tup.Route_ID}')
        road = tup.geometry

        # 2. Project and sort milepost dists along the line
        # Include 0.0 (start of line) and road.length (end of line) as bounds
        mpdf1 = mpdf1[['Milepost_N', 'MPT']].sort_values(by='MPT')



        mpt0 = [BEGIN] + list(mpdf1.MPT)
        mpt1 = list(mpdf1.MPT) + [tup.geometry.length / M_IN_MI]
        
        milepost0 = [None] + list(mpdf1.Milepost_N)
        milepost1 = list(mpdf1.Milepost_N) + [None]
        mprange = list(zip(milepost0, milepost1))
        roadseg = [shapely.ops.substring(tup.geometry, low * M_IN_MI, high * M_IN_MI) for low,high in zip(mpt0, mpt1)]
        centroid = [shapely.centroid(x) for x in roadseg]
        p0 = [shapely.get_point(ls, 0) for ls in roadseg]
        p1 = [shapely.get_point(ls, -1) for ls in roadseg]

        segdf0 = geopandas.GeoDataFrame({'Route_Name': tup.Route_Name, 'Route_ID': tup.Route_ID, 'Route_Na_3': tup.Route_Na_3, 'mprange': mprange, 'roadseg': roadseg}, geometry=centroid, crs=rdf.crs)

        maindfs.append(segdf0)
    maindf = pd.concat(maindfs)


    # Match off-route segments for Route_IDs not yet processed
    rdf = rdf[~rdf.Route_ID.isin(maindf.Route_ID)]
    offdfs = list()
    for Route_Name,maindf1 in maindf.groupby('Route_Name'):
        print(f'======== {Route_Name}')
        offdf = rdf[rdf.Route_Name == Route_Name]
        offdf = offdf.sjoin_nearest(maindf1, distance_col='distance', exclusive=True)
        offdfs.append(offdf)
    offdf = pd.concat(offdfs)

    # Leftover roads
    leftoverdf = rdf[~rdf.Route_ID.isin(offdf.Route_ID_left)]

    ofname = config.HARNESS / 'data/fischer' / 'mileposts.pik'
    with open(ofname, 'wb') as out:
        pickle.dump({'maindf': maindf, 'offdf': offdf, 'leftoverdf': leftoverdf}, out)

def  assemble_mileposts():
    ifname = config.HARNESS / 'data/fischer' / 'mileposts.pik'
    with open(ifname, 'rb') as fin:
        dd = pickle.load(fin)

    dfs = list()

    # Main highways with mileposts
    df0 = df = dd['maindf']
    is_highway = df0.Route_Name.str.contains('Highway')
#    print(df.columns)
    mprange = df.mprange
    df = df[['Route_ID', 'Route_Na_3', 'roadseg', 'Route_Name']]
    df = df.rename(columns={'Route_Na_3': 'Route_Name', 'roadseg': 'geometry', 'Route_Name': 'Main_Route_Name'})
    df['mp0'] = mprange.map(lambda x: x[0])
    df['mp1'] = mprange.map(lambda x: x[1])
#    df.loc[~is_highway, 'mp0'] = None
#    df.loc[~is_highway, 'mp1'] = None
    df.loc[is_highway, 'type'] = 'highway'    # Highway with mileposts
    df.loc[~is_highway, 'type'] = 'regional'    # Highway with mileposts
    df = geopandas.GeoDataFrame(df, geometry=df.geometry, crs=dd['leftoverdf'].crs)
    print(type(df))
    print(df.columns)
    dfs.append(df)


    # Access roads related to main highways
    df = dd['offdf']
    df0 = df
#    print(df.columns)
    df = df[['Route_ID_left', 'Route_Na_3_left', 'Route_Name_right', 'geometry']]
    df = df.rename(columns={
        'Route_ID_left': 'Route_ID',
        'Route_Na_3_left': 'Route_Name',
        'Route_Name_right': 'Main_Route_Name'})
    is_highway = df.Main_Route_Name.str.contains('Highway')
    df['mp0'] = df0.mprange.map(lambda x: x[0])
    df['mp1'] = df0.mprange.map(lambda x: x[1])
    df['type'] = 'access'    # Access roads / ramps / etc associated with main highways
    df.loc[~is_highway, 'type'] = 'local'
    df.loc[~is_highway, 'mp0'] = None
    df.loc[~is_highway, 'mp1'] = None

    print(type(df))
    print(df.columns)
    print('xxxxxxxxx ', df.geometry.name)
    dfs.append(df)

    # Stuff without mile markers
    df = dd['leftoverdf']
    df = df[['Route_ID', 'Route_Na_3', 'geometry']]
    df = df.rename(columns={
        'Route_Na_3': 'Route_Name'})
    df['Main_Route_Name'] = None
    df['mp0'] = None
    df['mp1'] = None
    df['type'] = 'secondary'
    print(type(df))
    print(df.columns)
    dfs.append(df)

    mpdf = pd.concat(dfs)
    mpdf.set_crs(epsg=3338)
    print(mpdf.columns)
    print(mpdf)


    # Identify ijdom gridcell intersections
    lsdf = lineintegral.linestrings_crossings(roaddf.geometry, expmod.gridD)

    ofname = config.HARNESS / 'data/fischer' / 'mileposts1.gpkg'
    mpdf.to_file(ofname, driver="GPKG")

# -----------------------------------------------------------
def all_coords(geom):
    """Recursively extract all coordinate tuples from any Shapely geometry."""
    
    if geom.is_empty:
        return []
        
    # Handle geometry collections and multi-geometries
    if geom.geom_type.startswith('Multi') or geom.geom_type == 'GeometryCollection':
        coords = []
        for part in geom.geoms:
            coords.extend(all_coords(part))
        return coords
            
    # Handle LineString, LinearRing, and Point
    elif hasattr(geom, 'coords'):
        return geom.coords
        
    return coords


def add_ijdoms():
    import akramms.experiment.aksc5 as expmod    # Any experiment will do

    ifname = config.HARNESS / 'data/fischer' / 'mileposts1.gpkg'
    roaddf = geopandas.read_file(ifname)

    geoinv_affine = shapelyutil.to_affine(expmod.gridD.geoinv)
    ijdomss = list()
    for ix,tup in enumerate(roaddf.itertuples(index=False)):
        if ix % 100 == 0:
            print(f'ijdoms {ix} of {len(roaddf)}')
        points = shapely.geometry.MultiPoint(all_coords(tup.geometry))
        ijpoints = shapely.affinity.affine_transform(points, geoinv_affine)
        ijdoms = sorted(set((int(ij.x), int(ij.y)) for ij in ijpoints.geoms))
        ijdomss.append(ijdoms)
    roaddf['ijdoms'] = ijdomss
    print(roaddf)

    ofname = config.HARNESS / 'data/fischer' / 'mileposts2.pik.gz'
    with gzip.open(ofname, 'wb') as out:
        pickle.dump(roaddf, out)


add_ijdoms()

