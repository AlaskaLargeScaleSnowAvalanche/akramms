import gzip
import pickle
import numpy as np
import d8graph
from dggs.avalanche import domain
from uafgi.util import shputil,shapelyutil,gdalutil
import sys
import os
import MinimumBoundingBox
import shapely

pras_file = '/Users/eafischer2/av/prj/juneau1/juneau1_For_5m_30L_rel.shp'
dem_file = '/Users/eafischer2/av/data/wolken/BaseData_AKAlbers/Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'
neighbors1_pik = 'neighbors1.pik.gz'


def domain_rectangle(xx, yy):
    """Computes the domain rectangle enclosing a bunch of points.
    xx, yy: np.array
        Points to enclose (projected x/y space)
    margin:
        Margin around rectangle to enlarge
    """
    mp = shapely.geometry.MultiPoint(list(zip(xx,yy)))
    chull = mp.convex_hull
    chull_list = list(zip(*chull.exterior.coords.xy))
    mbb = MinimumBoundingBox.MinimumBoundingBox(chull_list[:-1])



if True:
    # Read DEM
    grid_info,dem,dem_nodata = gdalutil.read_raster(dem_file)
    dem1d = dem.reshape(-1)

    print('nodata = ',dem_nodata)
    print('Total gridcells = ', dem.shape[0] * dem.shape[1])
    print('# nodata = ', np.sum(dem == dem_nodata))
    print('# zero = ', np.sum(dem == 0))


#    ixs = (22270038,)
#    for ix in ixs:
#        print(f'dem[{ix}] = {dem1d[ix]}')
    

    dem[dem == 0] = dem_nodata    # Blank out zero-elevation squares (sea level)

    # Read (one) polygon
    pras_df = shputil.read_df(pras_file)
    row = pras_df.iloc[0]
    print(row)
    pra = row['shape']
    #print('*** ',pra)
    pra_ds = shapelyutil.to_datasource(pra)
    pra_ras = gdalutil.rasterize_polygons(pra_ds, grid_info)

else:
    grid_info,dem,dem_nodata = domain.dem_example()

    pra_ras = np.zeros((grid_info.ny,grid_info.nx), dtype='b')
    pra_ras[7,8] = 1
    pra_ras[6,8] = 1
    pra_ras[2,9] = 1




    pra_ras1d = pra_ras.reshape(-1)

print('============= DEM')
print(dem)

print('========== Running C++')
if os.path.exists(neighbors1_pik):
    with gzip.open(neighbors1_pik, 'rb') as fin:
        dem = pickle.load(fin)    # Sinks are filled
        neighbors1 = pickle.load(fin)
else:
    neighbors1 = d8graph.neighbor_graph(dem, dem_nodata, 1)
    with gzip.open(neighbors1_pik, 'wb') as out:
        pickle.dump(dem, out)
        pickle.dump(neighbors1, out)

print('============= DEM')
print(dem)

print('========== Neighbors1')
print(neighbors1)

print('========== Seed Raster')
# Start off with a rasterized polygon of the PRA
start_ixs = np.where(pra_ras.reshape(-1))[0].astype('i')
print(pra_ras)
print('Seed Points: ', len(start_ixs), start_ixs)

print('================ Filled Points')
mbr = d8graph.find_domain(neighbors1, start_ixs, grid_info.geotransform)
print('Domain is ', mbr)

poly = shapely.geometry.Polygon(mbr)
print('Area is ', poly.area)

#print('=============== Filled Raster')
#filled_ras = np.zeros(pra_ras.shape, dtype='i')
#filled_ras[jjarr,iiarr] = 1
#print(filled_ras)

