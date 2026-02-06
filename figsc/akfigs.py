import os,subprocess,pathlib
import cartopy
from osgeo import gdal
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
        cmd = ['magick', 'convert', self.tname, '-trim', self.ofname]
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


anchorage_cities = [
    # Lon, Lat, Name
    (-149.1599, 60.9543, 'Girdwood'),
    (-149.8977, 61.2176, 'Anchorage'),
    (-149.2305, 61.1934, 'Chugach State Park'),
#    (-149.6917, 61.2538, 'Fort Richardson AFB'),
    (-149.5680, 61.3293, 'Eagle River'),
    (-149.4819, 61.3889, 'Chugiak'),
    (-149.4411, 61.5809, 'Wasilla'),
    (-149.1146, 61.5994, 'Palmer'),
]

scalaska_cities = [
    # Lon, Lat, Name
    (-149.8977, 61.2176, 'Anchorage'),
    (-149.4411, 61.5809, 'Wasilla'),
#    (-150.0622, 61.7584, 'Willow'),
    (-145.751944, 60.543611, 'Cordova'),
    (-146.3499, 61.1309, 'Valdez'),
    (-144.4411, 61.5156, 'Chitina'),
#    (-142.9229, 61.4331, 'McCarthy'),    # out of bounds
#    (-145.5340, 62.1081, 'Glenallen'),    # out of bounds
    (-151.2418, 60.5577, 'Kenai'),
    (-151.5299, 59.6481, 'Homer'),
]

_cities_marker_kwargs = dict(marker='o', markersize=2, color='blue', alpha=0.5)
_cities_text_kwargs = dict(
            fontdict = {'size': 4, 'color': 'black'})

def plot_cities(ax, city_set, marker_kwargs=None, text_kwargs=None, only=None):
    cities = globals()[f'{city_set}_cities']
    # Plot Juneau and other cities
    # https://scitools.org.uk/cartopy/docs/latest/tutorials/understanding_transform.html
    for lon, lat, city_name in cities:
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
#sealaska_map_extent = ((320-180)*1000, 1670*1000, 300*1000, (1425+230)*1000)    # xmin, xmax, ymin, ymax; ymin in South
anchorage_map_extent = (210000-5000, 300000+5000, 1200000-5000, 1320000+5000)    # xmin, xmax, ymin, ymax; ymin in South

scalaska_map_extent = (-820*1000, 1900*1000, 0*1000, 2400*1000)


#(214750-15000, 300200+5000, 1199835-5000, 1320230+5000,)


#ccsm_dir = config.HARNESS / 'data' / 'lader' / 'sx3'#pathlib.Path(os.environ['HOME']) / 'av/data/lader/sx3'
#geo_nc = ccsm_dir / 'geo_southeast.nc'    # Describes grid
geo_nc = '/home/efischer/av/data/waigl/wrf_era5/04km/invar/geo_em.d02.nc'


def wrf_bbox_feature():
    # The overall bounding box (as a Shapely polygon)
    snow_grid = wrfutil.wrf_info(geo_nc)
    snow_crs = cartopyutil.crs(snow_grid.wkt)
    bbox = snow_grid.bounding_box()
    return cartopy.feature.ShapelyFeature(bbox, snow_crs)
    

def resample_lr(exp, tiles, tdir, vars=['dem', 'landcover'], xyres=60):
    """Read DM and Landcover rasters
    tiles: collection / iterator
        (idom, jdom) of tiles to include in ther aster
    """

    # Build a sinlge mosaic from the individual tiles
    tifss = [list() for vname in vars]
    for idom,jdom in sorted(tiles):
        for vname,tifs in zip(vars, tifss):
            if vname == 'snow':
#                root = f'{exp.name}_ccsm_past_sclapse_030'
                fname = exp.root_dir / 'publish' / f'{exp.name}-ccsm-past-sclapse-All-30' / 'snow' / f'{exp.name}-ccsm-past-sclapse-All-30-{idom:03d}-{jdom:03d}-F-snow.tif'
            else:
#                root = f'{vname}'
                root = f'{exp.name}_{vname}'
                fname = exp.dir / vname / f'{root}_{idom:03d}_{jdom:03d}.tif'
            print('vrt ', fname)
            tifs.append(fname)

    # Resample DEM to 100m resolution
    xyres = 60    # Resample to 100m

    tif_lrs = []
    for vname,tifs in zip(vars, tifss):
        fname_vrt = gisutil.build_vrt(tifs, tdir.location / f'{vname}.vrt')
        fname_lr = tdir.location / f'{vname}_lr.tif'

        ds = gdal.Warp(fname_lr, fname_vrt,
            xRes=xyres, yRes=xyres, resampleAlg='average')
        ds = None

        tif_lrs.append(fname_lr)


    return tif_lrs
