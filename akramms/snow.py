from uafgi.util import gdalutil,wrfutil
import pyproj

class WrfLookup:
    def __init__(self, scene_wkt, data_fname, vname, geo_fname, units=None):
        """
        units: str
            Units to convert to
        """

        # Determine WRF coordinates
        self.geo_info = wrfutil.wrf_info(geo_fname)
        print('geotransform = {}'.format(self.geo_info.geotransform))
        print('geoinv = {}'.format(self.geo_info.geoinv))
        print('extents = {}'.format(self.geo_info.extents))
        print('nx,ny = ({}, {})'.format(self.geo_info.nx, self.geo_info.ny))

        # Obtain transfomer from scene coordinates to WRF Snow File
        scene_crs = pyproj.CRS.from_string(scene_wkt)
        wrf_crs = pyproj.CRS.from_string(self.geo_info.wkt)
        # There will be "error" in this because the spheroids do not match.
        # WRF uses perfect sphere; whereas scene typically uses WGS84 or similar
        self.scene2wrf = pyproj.Transformer.from_crs(scene_crs, wrf_crs, always_xy=True)

        # Load the data file
        self.data = wrfutil.read(data_fname, units=units)

#        # Write a GeoTIFF file of our results
#        wrfutil.write_geotiff(self.geo_info, self.data, 'x.tif')

    def value_at_centroid(self, poly):
        centroid = poly.centroid    # In scene coordinates
        x_scene, y_scene = (centroid.x, centroid.y)
        x_wrf,y_wrf = self.scene2wrf.transform(x_scene, y_scene)    # --> WRF coordinates
        ir,jr = self.geo_info.to_ij(x_wrf, y_wrf)    # --> (j,i) index into data
        i = round(ir)
        j = round(jr)
        return self.data[j,i]

#    def to_ij(self, poly):
#        centroid = poly.centroid    # In scene coordinates
#        x_scene, y_scene = (centroid.x, centroid.y)
#        x_wrf,y_wrf = self.scene2wrf.transform(x_scene, y_scene)    # --> WRF coordinates
#        i,j = self.geo_info.to_ij(x_wrf, y_wrf)    # --> (j,i) index into data
#        return (round(i), round(j))

class RasterLookup:
    """Alternative to WrfLookup, pick out of a raster file on local grid"""
    def __init__(self, raster_file):
        print('RasterLookup reading ', raster_file)
        self.geo_info,self.value,self.value_nd = gdalutil.read_raster(raster_file)
        self.centroids = list()
    
    def value_at_centroid(self, poly):
        centroid = poly.centroid    # In scene coordinates
        x_scene, y_scene = (centroid.x, centroid.y)
        i,j = self.geo_info.to_ij(x_scene, y_scene)    # --> (j,i) index into data
#        print(f'value_at_centroid({j},{i}) = {self.value[j,i]}')
        self.centroids.append((j,i))
        return (j,i,self.value[j,i])
# ---------------------------------------------------------------------------------
