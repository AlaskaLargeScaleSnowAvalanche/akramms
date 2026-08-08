import gzip,pickle
import geopandas
import shapely
from uafgi.util import lineintegral




def main():
    import akramms.experiment.aksc5 as expmod
    from uafgi.util import gdalutil

#    rdf = geopandas.read_file(expmod.root_dir / 'roadcover' / f'{expmod.name}_roadcover.gpkg')
#    print(rdf)

    combo = expmod.Combo('ccsm', 'past', 'sclapse', 'NoFor', 30, 91, 41)

    ifname = f'/home/efischer/prj/aksc5/roadcover/aksc5-ccsm-past-sclapse-NoFor-30/{expmod.name}-{repr(combo)}-roadcover.pik.gz'

    with gzip.open(ifname) as fin:
        rdf = pickle.load(fin)
    rdf = rdf.sort_values('Id')
    print(rdf[['Id', 'Route_ID']])
    print(rdf.iloc[0])
    return


    # Clip to within the margin
    bbox = val_grid.bounding_box()
    rdf['geometry'] = [shapely.intersection(ls, bbox) for ls in rdf.geometry]


    rows = list()
    for Route_ID, xdf in rdf.groupby('Route_ID'):
        ls = shapely.unary_union(xdf.geometry)
        Avalanche_Ids = tuple(xdf.Id)    # AKRAMMS avlanache IDs for this combo
        rows.append((Route_ID, ls))



    print(sum(x.length for x in rdf.geometry))
    ls = shapely.unary_union(rdf.geometry)
    print(ls.length)
#    print(rdf)
#    return


#    for tup in rdf.itertuples(index=False):
#        print(tup)
#        print(tup.geometry)
#        print(combo.idom,combo.jdom)
    if True:
#        lss = [shapely.unary_union(rdf.geometry)]
        lss = list(rdf.geometry)
        lss = [shapely.force_2d(ls) for ls in lss]

        val_tif = expmod.root_dir / 'publish.v6/aksc5-ccsm-past-sclapse-All-300/max_pressure' / f'aksc5-ccsm-past-sclapse-All-300-{combo.idom:03d}-{combo.jdom:03d}-F-max_pressure.tif'
        val_grid, val_data, val_nd = gdalutil.read_raster(val_tif)
        dfs = integrate_linestrings(lss, val_grid, val_data)
        print('=========== len = ', dfs.vallen[0])
#        print(tup)


#        break

    return

    # WLOG, x(t) and y(t) must be increasing functions
#    x0,y0 = 5.1,11
#    x1,y1 = 8.1,14
    x0,y0 = 1.1,1
    x1,y1 = 4.1,4

    df = pixel_crossings(x0,y0,x1,y1)
    print(df)




main()
