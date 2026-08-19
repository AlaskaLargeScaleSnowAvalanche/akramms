import statistics,math
from osgeo import ogr,gdal
import shapely
from akramms import config
import geopandas
import pandas as pd


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

def main():

    mpdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'Mileposts_AKDOT_-4629016772512910170.zip')
    mpdf["geometry"] = mpdf["geometry"].map(shapely.force_2d)
    rdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'Roads_AKDOT_6350608895875630378.zip')
    rdf["geometry"] = rdf["geometry"].map(shapely.force_2d)




    for Route_ID,rdf1 in rdf.groupby('Route_ID'):
        mpdf1 = mpdf[mpdf.Route_ID == Route_ID]
        if len(mpdf1) == 0:
            continue

        print('====================== Route_ID ', Route_ID)
        assert len(rdf1) == 1
        rec = rdf1.iloc[0]
#        print(rec)

        road = rec.geometry
#        print('================== Road')
#        print('road len ', road.length)
#        print(road)
#        print(list(road.coords))

        mileposts = list(mpdf1.geometry)
#        print('================== Mileposts')
#        print(list(mileposts))

#        print('mileposts ', mileposts)

        # 2. Project and sort milepost dists along the line
        # Include 0.0 (start of line) and road.length (end of line) as bounds
        mpdf1['dist'] = mpdf1.geometry.map(lambda mp: road.project(mp))
        mpdf1 = mpdf1.sort_values(by='dist')
#        print(mpdf1.dist)
        mpdf1['dist'] = mpdf1.dist.map(lambda x: x/(5280*.3048))
        mpdf1 = mpdf1[['Milepost_N', 'MPT', 'dist']]


        rows = list()
        mpt0 = [BEGIN] + list(mpdf1.MPT)
        mpt1 = list(mpdf1.MPT) + [rec.geometry.length / (5280*.3048)]
        milepost0 = [None] + list(mpdf1.Milepost_N)
        milepost1 = list(mpdf1.Milepost_N) + [None]
        roadseg = [shapely.ops.substring(rec.geometry, low, high) for low,high in zip(mpt0, mpt1)]
        p0 = [shapely.get_point(ls, 0) for ls in roadseg]
        p1 = [shapely.get_point(ls, -1) for ls in roadseg]



#        rdf2 = geopandas.GeoDataFrame({'Route_ID': Route_ID, 'Route_Name': rec.Route_Name, 'milepost0': milepost0, 'milepost1': milepost1, 'mpt0': mpt0, 'mpt1': mpt1, 'p0': p0, 'p1': p1}, geometry=roadseg, crs=rdf1.crs)

        rdf2 = geopandas.GeoDataFrame({'Route_ID': Route_ID, 'Route_Name': rec.Route_Name, 'Route_Na_3': rec.Route_Na_3, 'milepost0': milepost0, 'milepost1': milepost1, 'mpt0': mpt0, 'mpt1': mpt1}, geometry=roadseg, crs=rdf1.crs)
#        rdf2['Route_ID'] = Route_ID


        print(rdf2)
#        for mpt in zip(


#        print(mpdf1)

#        mpdf1['dist'] = [road.project(mp) for mp in mpdf1.geometry]
#        dists = sorted(list(set(dists))) # Remove duplicates and sort
#        print(dists)
#        print('road len ', road.length)

#        # 3. Create segments between each adjacent pair of dists
#        segments = []
#        for i in range(len(dists) - 1):
#            seg = shapely.ops.substring(road, dists[i], dists[i + 1])
#            if not seg.is_empty:
#                segments.append(seg)
#
               
#        return

def main2():
    print(config.HARNESS)

    mpdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'Mileposts_AKDOT_-4629016772512910170.zip')
    mpdf["geometry"] = mpdf["geometry"].map(shapely.force_2d)
#    print(mpdf)
#    print(mpdf.iloc[0])
#    print(mpdf.crs)


#    rdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'NTAD_North_American_Rail_Network_Lines_278491609840284355.zip')

    rdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'Roads_AKDOT_6350608895875630378.zip')
    rdf["geometry"] = rdf["geometry"].map(shapely.force_2d)

    print(rdf)
    print(rdf.iloc[0])
    print(rdf.crs)

    rdf['len'] = rdf.geometry.map(shapely.length)
    rdf = rdf[['Route_ID', 'Route_Name', 'Route_Na_2', 'Seg_Length', 'len', 'geometry']]
    conv = 5280*.3048    # Convert miles to meters
    print(conv*rdf.Seg_Length.min(), conv*rdf.Seg_Length.mean(), conv*rdf.Seg_Length.max())
    print(rdf.len.min(), rdf.len.mean(), rdf.len.max())



#    print(rdf[rdf.len > 100000])

    rdf = rdf[rdf.Route_Name == 'Seward Highway']

    rdf = rdf[['Route_ID', 'Route_Na_2', 'len']].sort_values(by=['len'])
    pd.set_option('display.max_columns', None)
    print(rdf)

    return







    mpdf = mpdf[mpdf.Route_ID.isin(rdf.Route_ID)]

    print(mpdf)

    minseg = 1e9
    maxseg = 0

    seglens = list()
    for tup in rdf.itertuples(index=False):
        for p0,p1 in iterate_ls(tup.geometry):
#        for xx in iterate_ls(tup.geometry):
#            print('xxxxxxxxxxx ', xx)
            seglens.append(math.dist(p0,p1))

    print(min(seglens), max(seglens), statistics.mean(seglens))



main()
