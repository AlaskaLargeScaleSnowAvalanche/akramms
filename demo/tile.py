import os
import geopandas
from akramms import avalquery
from akramms.experiment import ak

#avalquery.tile_rtree(ak)


from uafgi.util import ogrutil

def main():

    expmod = ak
    query_box = expmod.gridD.sub(94,38,10,10, margin=False).bounding_box(type='shapely')


    rt = avalquery.tile_rtree(ak)
    subrows = rt.intersection(query_box)
    print(subrows)
    return



    domains_margin_shp = os.path.join(expmod.dir, f'{expmod.name}_domains_margin.shp')
    sf = ogrutil.read_df(domains_margin_shp)




    print('Area of query_box ', query_box.GetArea())
    return


    domains_margin_shp = os.path.join(expmod.dir, f'{expmod.name}_domains_margin.shp')
#    domains_df = shputil.read_df(domains_margin_shp)

    domains_margin_sf = ogrutil.read_df(domains_margin_shp)

    x = expmod.gridD.sub(94,35,10,10).bounding_box(type='ogr')
    print(x)
    print(domains_margin_sf.df['shape'][0])


#    print(df)



def main2():
    x0=0
    x1=2
    y0=0
    y1=2



def main3():

    # https://mapscaping.com/reading-and-writing-geopackage-in-python/
    ifname = '/Users/eafischer2/tmp/maps/x.gpkg'
    df = geopandas.read_file(ifname)
    print(df)


#from shapely.geometry import box
#
#bbox = box(minx, miny, maxx, maxy)  # Replace with desired bounding box coordinates
#filtered_data = data[data.geometry.intersects(bbox)]

main3()
