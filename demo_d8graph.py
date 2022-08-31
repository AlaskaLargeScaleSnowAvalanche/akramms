import d8graph
from dggs.avalanche import domain
from uafgi.util import shputil,shapelyutil,gdalutil

pras_file = '/Users/eafischer2/av/prj/juneau1/juneau1_For_5m_30L_rel.shp'
dem_file = '/Users/eafischer2/av/data/wolken/BaseData_AKAlbers/Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'

# Read DEM
#grid_info,dem,dem_nodata = gdalutil.read_raster(dem_file)
grid_info,dem,dem_nodata = domain.dem_example()


# Read (one) polygon
pras_df = shputil.read_df(pras_file)
row = pras_df.iloc[0]
print(row)
pra = row['shape']
#print('*** ',pra)
pra_ds = shapelyutil.to_datasource(pra)
pra_ras = gdalutil.rasterize_polygons(pra_ds, grid_info)



print(dem)

neighbors1 = d8graph.neighbor_graph(dem, dem_nodata, 2)
print(neighbors1)

