import gzip
import pickle
import numpy as np
import d8graph
from akramms import domain
from uafgi.util import shputil,shapelyutil,gdalutil
import sys
import os
import MinimumBoundingBox
import shapely

pras_file = '/Users/eafischer2/av/prj/juneau1/juneau1_For_5m_30L_rel.shp'
dem_file = '/Users/eafischer2/av/data/wolken/BaseData_AKAlbers/Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'
neighbors1_pik = 'neighbors1.pik.gz'


# =================== Read Data Files
if True:
    # Real Problem: read DEM
    grid_info,dem,dem_nodata = gdalutil.read_raster(dem_file)
    dem1d = dem.reshape(-1)

    print('nodata = ',dem_nodata)
    print('Total gridcells = ', dem.shape[0] * dem.shape[1])
    print('# nodata = ', np.sum(dem == dem_nodata))
    print('# zero = ', np.sum(dem == 0))

    dem[dem == 0] = dem_nodata    # Blank out zero-elevation squares (sea level)

    # Read (one) polygon
    pras_df = shputil.read_df(pras_file)


#print('============= DEM')
#print(dem)

# ================ Prepare the DEM graph
print('========== Preparing neighbors1')
if os.path.exists(neighbors1_pik):
    with gzip.open(neighbors1_pik, 'rb') as fin:
        dem = pickle.load(fin)    # Sinks are filled
        neighbors1 = pickle.load(fin)
else:
    neighbors1 = d8graph.neighbor_graph(dem, dem_nodata, 1)
    with gzip.open(neighbors1_pik, 'wb') as out:
        pickle.dump(dem, out)
        pickle.dump(neighbors1, out)



#print('============= DEM')
#print(dem)

#print('========== Neighbors1')
#print(neighbors1)


# ========== Loop through PRAs
for _,row in pras_df.iterrows():
    # -- Get PRA raster
    pra = row['shape']
    pra_ras = gdalutil.rasterize_polygons(shapelyutil.to_datasource(pra), grid_info)

    # -- Turn that into a bunch of start indices
    starts = np.where(pra_ras.reshape(-1))[0].astype('i')
    print('Seed Points: ', len(starts), starts)

    print('================ Filled Points')
    mbr = d8graph.find_domain(neighbors1, starts, grid_info.geotransform, margin=0)
    print('Domain is ', mbr)

    poly = shapely.geometry.Polygon(mbr)
    print('Area is ', poly.area)

#print('=============== Filled Raster')
#filled_ras = np.zeros(pra_ras.shape, dtype='i')
#filled_ras[jjarr,iiarr] = 1
#print(filled_ras)

