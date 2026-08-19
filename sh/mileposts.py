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

M_IN_MI = (5280*.3048)

def main():

    mpdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'Mileposts_AKDOT_-4629016772512910170.zip')
    mpdf["geometry"] = mpdf["geometry"].map(shapely.force_2d)
    rdf = geopandas.read_file(config.HARNESS / 'data/fischer' / 'Roads_AKDOT_6350608895875630378.zip')
    rdf["geometry"] = rdf["geometry"].map(shapely.force_2d)

#    print('All route names: ', set(rdf.Route_Name))
#    rdf = rdf[rdf.Route_Name == 'Seward Highway']


    nomps = list()
    route_names = list()
    segdfs = list()
    route_ids = list()
    ix=0
    for tup in rdf.itertuples(index=False):
        mpdf1 = mpdf[mpdf.Route_ID == tup.Route_ID]
        if len(mpdf1) == 0:
            nomps.append(True)
            continue
        nomps.append(False)
        route_names.append(tup.Route_Name)
        route_ids.append(tup.Route_ID)
        print(tup)

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

        segdf0 = geopandas.GeoDataFrame({'Route_ID': tup.Route_ID, 'Route_Name': tup.Route_Name, 'Route_Na_3': tup.Route_Na_3, 'mprange': mprange, 'roadseg': roadseg}, geometry=centroid, crs=rdf.crs)
        print(segdf0)
        segdfs.append(segdf0)

#        ix += 1
#        if ix > 5:
#            break
    print([type(x) for x in segdfs])
    segdf = pd.concat(segdfs, ignore_index=True)
    print(segdf)
    print(type(segdf))

#    nomps.extend([False] * (len(rdf) - len(nomps)))    # DEBUG
    nompdf = rdf.loc[nomps]
#    print('Route Names ', route_names)
#    nompdf = rdf[rdf.Route_Name.isin(set(route_names)) & ~rdf.Route_ID.isin(route_ids)]
    print('xxxxxxxxxx ', type(nompdf))
    xdf = segdf[['Route_ID', 'Route_Name', 'mprange', 'roadseg', 'geometry']]
    print(xdf)
    nompdf = nompdf.sjoin_nearest(xdf, distance_col='distance', exclusive=True)
#    nompdf = nompdf[['Route_ID_left', 'Route_ID_right', 'Route_Na_3', 'mprange', 'distance']].sort_values(by='distance')
#    pd.set_option('display.max_rows', None)
#    print(nompdf)
    nompdf.to_pickle('nompdf.pik')



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
