import numpy as np
from uafgi.util import gdalutil
from osgeo import gdal,ogr
import os
import pathlib

#dir = pathlib.Path('/home/efischer/tmp')
dir = pathlib.Path('/Users/eafischer2/tmp/maps')
raster_tif = dir / 'ak_DFC.tif'
out_shp = dir / 'ak_DFC.shp'

def main0():
    # open raster file
    print(raster_tif)
    raster = gdal.Open(str(raster_tif))
    band = raster.GetRasterBand(1)

    #create new shp file
    shpDriver = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(out_shp):
        os.remove(out_shp)
#        shpDriver.DeleteDataSource(out_shp)
    outDataSource = shpDriver.CreateDataSource(str(out_shp))
    outLayer = outDataSource.CreateLayer(str(out_shp), geom_type=ogr.wkbLineString )

    # polygonize
    gdal.Polygonize(band, None, outLayer, -1)



def main():

    # Read raster, make mask, and  create in-memory dataset
    raster = gdalutil.read_raster(raster_tif)
    mask = (raster.data != raster.nodata).astype(np.int8)
    raster_ds = gdalutil.raster_ds((raster.grid, mask, 3))


    band = raster_ds.GetRasterBand(1)

    #create new shp file
    shpDriver = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(out_shp):
        os.remove(out_shp)
#        shpDriver.DeleteDataSource(out_shp)
    outDataSource = shpDriver.CreateDataSource(str(out_shp))

    raster_srs = ogr.osr.SpatialReference()
    raster_srs.ImportFromWkt(raster.grid.wkt)

    outLayer = outDataSource.CreateLayer(str(out_shp), raster_srs, geom_type=ogr.wkbMultiPolygon )

    # polygonize; outLayer can have other stuff in it already.
    gdal.Polygonize(band, band, outLayer, -1)


main()
