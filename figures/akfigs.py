import os,subprocess,pathlib
import cartopy
from akramms import config
from uafgi.util import wrfutil,cartopyutil,gisutil
from akramms import config

PALETTES = config.HARNESS / 'akramms' / 'palettes'
OSM_DIR = config.HARNESS / 'data' / 'openstreetmap'

class TrimmedPng:
    def __init__(self, ofname):
        self.ofname = ofname
        baseleaf,ext = os.path.splitext(ofname.parts[-1])
        self.tname = ofname.parents[0] / f'{baseleaf}_tmp.{ext}'
    def __enter__(self):
        return self.tname

    def __exit__(self ,type, value, traceback):
        cmd = ['convert', self.tname, '-trim', self.ofname]
        subprocess.run(cmd, check=True)
        os.remove(self.tname)

class TrimmedPdf:
    def __init__(self, ofname):
        ofname = pathlib.Path(ofname)
        self.ofname = ofname
        baseleaf,ext = os.path.splitext(ofname.parts[-1])
        self.tname = ofname.parents[0] / f'{baseleaf}_tmp.{ext}'
    def __enter__(self):
        return self.tname

    def __exit__(self ,type, value, traceback):
        cmd = ['pdfcrop', self.tname, self.ofname]
        subprocess.run(cmd, check=True)
        os.remove(self.tname)


SECities = [
    # Lon, Lat, Name
    (-134.4201, 58.3005, 'Juneau'),
    (-135.4473, 59.2351, 'Haines'),
    (-135.3346, 57.0532, 'Sitka'),
    (-131.6461, 55.3422, 'Ketchikan'),
    (-145.751944, 60.543611, 'Cordova'),
    (-146.3499, 61.1309, 'Valdez'),
    (-139.7268, 59.5453, 'Yakutat'),

]

_cities_marker_kwargs = dict(marker='o', markersize=2, color='blue', alpha=0.5)
_cities_text_kwargs = dict(
            fontdict = {'size': 4, 'color': 'black'})

def plot_cities(ax, marker_kwargs=None, text_kwargs=None, only=None):
    # Plot Juneau and other cities
    # https://scitools.org.uk/cartopy/docs/latest/tutorials/understanding_transform.html
    for lon, lat, city_name in SECities:
        if (only is None) or (city_name in only):
    #        lon,lat = (-134.4201, 58.3005)
            ax.plot(lon, lat, transform=cartopy.crs.PlateCarree(), **(marker_kwargs if marker_kwargs is not None else _cities_marker_kwargs))
            # https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.text.html
            ax.text(lon, lat, f'  {city_name}', transform=cartopy.crs.PlateCarree(), **(text_kwargs if text_kwargs is not None else _cities_text_kwargs))

def map_crs():
    # HACK: Increase the bounds that this projection is allowed to display
    crs = cartopy.crs.epsg(3338)    # Alaska Albers
    bb = crs.bounds
#    crs.bounds = (bb[0], bb[1]+100*1000, bb[2]-100*1000, bb[3])
    crs.bounds = (bb[0], bb[1]+300*1000, -1000, bb[3])
    print('bounds ', crs.bounds)
    return crs

allalaska_map_extent = (-820*1000, 1900*1000, 0*1000, 2400*1000)
sealaska_map_extent = ((320-180)*1000, 1670*1000, 300*1000, (1425+230)*1000)    # xmin, xmax, ymin, ymax; ymin in South

ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'#pathlib.Path(os.environ['HOME']) / 'av/data/lader/sx3'
geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid


def wrf_bbox_feature():
    # The overall bounding box (as a Shapely polygon)
    snow_grid = wrfutil.wrf_info(geo_nc)
    snow_crs = cartopyutil.crs(snow_grid.wkt)
    bbox = snow_grid.bounding_box()
    return cartopy.feature.ShapelyFeature(bbox, snow_crs)
    
