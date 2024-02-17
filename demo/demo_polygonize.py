import gdal,ogr,os
import pathlib

dir = pathlib.Path('/home/efischer/tmp')
raster_tif = dir / 'ak_DFC.tif'
out_shp = dir / 'ak_DFC.shp'

def main():
    # open raster file
    raster = gdal.Open(raster_tif)
    band = raster.GetRasterBand(1)

    #create new shp file
    shpDriver = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(out_shp):
        shpDriver.DeleteDataSource(out_shp)
    outDataSource = shpDriver.CreateDataSource(out_shp)
    outLayer = outDataSource.CreateLayer(out_shp, geom_type=ogr.wkbLineString )

    # polygonize
    gdal.Polygonize(band, None, outLayer, 1) 

main()
