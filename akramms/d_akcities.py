from osgeo import ogr, osr
import pyproj
from akramms import config

cities = [
    # Lon, Lat, Name

    # Southeast Alaska
    (-134.4201, 58.3005, 'Juneau'),
    (-135.4473, 59.2351, 'Haines'),
    (-135.3346, 57.0532, 'Sitka'),
    (-131.6461, 55.3422, 'Ketchikan'),
    (-145.751944, 60.543611, 'Cordova'),
    (-146.3499, 61.1309, 'Valdez'),
    (-139.7268, 59.5453, 'Yakutat'),

    # South Central Alaska
    (-145.7297, 61.1286, 'Thompson Pass'),
    (-149.8997, 61.2176, 'Anchorage'),
    (-148.6858, 60.7746, 'Whittier'),
    (-149.1146, 61.5994, 'Palmer'),
    (-149.4421, 60.1048, 'Seward'),
    (-149.4411, 61.5809, 'Wasilla'),

    # Interior
    (-147.7200, 64.8401, 'Fairbanks'),
    (-145.5380, 68.1271, 'Arctic Village'),

]


def write_cities(cities, ofname):

    # Define the spatial reference system (e.g., WGS 84)
    #isrs = osr.SpatialReference()
    #isrs.ImportFromEPSG(4326)  # EPSG code for WGS 84
    osrs = osr.SpatialReference()
    osrs.ImportFromEPSG(3338)    # Alaska Albers

    icrs = pyproj.CRS(4326)
    ocrs = pyproj.CRS(3338)
    transformer = pyproj.Transformer.from_crs(icrs, ocrs, always_xy=True)

    # Create a new shapefile
    driver = ogr.GetDriverByName("GeoJSON")

#    ofname = "akcities.geojson"
    print('Removing and writing ', ofname)
    try:
        os.remove(ofname)
    except Exception:
        pass
    data_source = driver.CreateDataSource(ofname)

    # Create a new layer in the shapefile
    layer = data_source.CreateLayer("points", osrs, ogr.wkbPoint)

    # Define fields (attributes) for the layer (optional)
    field_name = ogr.FieldDefn("Name", ogr.OFTString)
    layer.CreateField(field_name)
#    field_id = ogr.FieldDefn("ID", ogr.OFTInteger)
#    layer.CreateField(field_id)

#    for id,(lon,lat,name) in enumerate(cities):
    for lon,lat,name in cities:
        # Convert to output srs
        x,y = transformer.transform(lon,lat)

        # Create a new point geometry
        point = ogr.Geometry(ogr.wkbPoint)
        point.AddPoint(x, y)

        # Create a new feature
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(point)

        # Set attribute values
        feature.SetField("Name", name)
#        feature.SetField("ID", id)

        # Add the feature to the layer
        layer.CreateFeature(feature)

        # Destroy the feature to free resources
        feature = None

    # Save and close the data source
    data_source = None


write_cities(cities, 'akcities.geojson')
