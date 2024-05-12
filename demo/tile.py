import os
import geopandas
from akramms import avalquery
from akramms.experiment import ak

#avalquery.tile_rtree(ak)


from uafgi.util import ogrutil

def main():
    combo = ak.Combo('ccsm', 1981, 2010, 'lapse', 'For', 30, -1, -1)
    expmod = ak

    query_box = expmod.gridD.sub(110,42,10,10, margin=False).bounding_box(type='shapely')

    rt = avalquery.tile_rtree(ak)
    qdf = rt.intersection(query_box)

    missing_tiles = list()
    for tup in qdf.itertuples(index=False):
        # Replace (idom,jdom) on the combo
        lqcombo = list(combo)[:-2] + [tup.idom, tup.jdom]
        qcombo = expmod.Combo(*lqcombo)
        arcdir = expmod.combo_to_scenedir(qcombo, scenetype='arc')
        extent_full = arcdir / 'extent_full.gpkg'

        if not os.path.isfile(extent_full):
            missing_tiles.append(extent_full)
        else:

            df = geopandas.read_file(str(extent_full))
            dfi = df[df.geometry.intersects(query_box)]
            print(f'{qcombo}: {len(dfi)} of {len(df)} --- {dfi.columns}')

    print('-------- missing')
    for missing_tile in missing_tiles:
        print(missing_tile)

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
#    ifname = '/Users/eafischer2/tmp/maps/x.gpkg'
    ifname = '/home/efischer/prj/ak/ak-ccsm-1981-2010-lapse-For-30/arc-097-035/extent_full.gpkg'
    df = geopandas.read_file(ifname)
    print(df)



#from shapely.geometry import box
#
#bbox = box(minx, miny, maxx, maxy)  # Replace with desired bounding box coordinates
#filtered_data = data[data.geometry.intersects(bbox)]

main()
