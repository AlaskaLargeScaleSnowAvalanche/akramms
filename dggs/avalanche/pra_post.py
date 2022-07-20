import scipy.spatial
from osgeo import gdal
from dggs.avalanche import params
from uafgi.util import shputil,gdalutil
import os
import subprocess
import json
import dggs.data
import pyproj
import netCDF4
import numpy as np

#def gdal_info(fname):
#    ds = gdal.Open(fname)
#    band = ds.GetRasterBand(1)
#    l = band.GetMinimum()
#    r = band.GetMaximum()
#print(gdal.Info(ds))
#print(l)
#print(r)

#GDALInfo = collections.namedtuple('GDALInfo', ('zo))
#    1

class WRFTransformer:
    def __init__(self, geo_fname, scene_wkt):
        with netCDF4.Dataset(geo_fname) as nc:
            # lon/lat of center of each gridcell
            lon_m = nc.variables['XLONG_M'][0,:,:]
            lat_m = nc.variables['XLAT_M'][0,:,:]

        # NOTE: WRF NetCDF file is in north-down format; i.e. the most
        #       northernly points are at the END of the Y axis.  This
        #       is the opposite of typical GeoTIFF, and we would
        #       expect dy to be positive.

        self.nii = lon_m.shape[0]
        self.njj = lon_m.shape[1]

        print('llllon\n', lon_m[0:2,0:2])
        print('llllat\n', lat_m[0:2,0:2])

        print('llllon\n', lon_m[-2:,-2:])
        print('llllat\n', lat_m[-2:,-2:])


#        lon_m = lon_m[0:2,0:2]
#        lat_m = lat_m[0:2,0:2]

        # Get gridcell centers in scene's CRS
        lonlat_crs = pyproj.CRS.from_string(dggs.data.grs1980_wkt)
        # https://fabienmaussion.info/2018/01/06/wrf-projection/
        # TODO: This CAN all come out of the WRF geo file.
        # MAP_PROJ=1  ==> LCC
        wrf_crs = pyproj.CRS.from_string('+proj=lcc +lat_1=58 +lat_2=58 +lat_0=58 +lon_0=-138.5 +x_0=0 +y_0=0 +a=6370000 +b=6370000 +units=m +no_defs')
        scene_crs = pyproj.CRS.from_string(scene_wkt)

        # https://spatialreference.org/ref/sr-org/epsg3857/proj4/
        # We are LIKE EPSG 3857; except WRF uses radius of 6370000m
        #    EPSG 3857: https://spatialreference.org/ref/sr-org/epsg3857/proj4/
        #    WRF Radius: https://github.com/Unidata/thredds/issues/753
        ll0_crs = pyproj.CRS.from_string('+proj=merc +lon_0=0 +k=1 +x_0=0 +y_0=0 +a=6370000 +b=6370000 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs ')
        ll02wrf = pyproj.Transformer.from_crs(lonlat_crs, wrf_crs, always_xy=True)

        # There will be "error" in this because the spheroids do not match.
        # WRF uses perfect sphere; whereas scene typically uses WGS84 or similar
        self.scene2wrf = pyproj.Transformer.from_crs(scene_crs, wrf_crs, always_xy=True)

        xx_m_wrf, yy_m_wrf = ll02wrf.transform(lon_m,lat_m)

        # Set up the geotransform for the WRF raster
        # See: https://gdal.org/tutorials/geotransforms_tut.html
        # Grid is indexed [j,i]
        dx = np.mean(xx_m_wrf[:,1:] - xx_m_wrf[:,0:-1])
        dy = np.mean(yy_m_wrf[1:,:] - yy_m_wrf[0:-1,:])

#        dx = xx_m_wrf[0,1] - xx_m_wrf[0,0]
#        dy = yy_m_wrf[1,0] - yy_m_wrf[0,0]
        print('dx dy', dx,dy)

        gt_wrf = [
            np.mean(xx_m_wrf[:,0]) - .5*dx,    # edge of x-coord of origin (most westerly pixel)
            dx,                       # W-E pixel width
            0,                        # Row rotation
            np.mean(yy_m_wrf[0,:]) + .5*dy,    # edge of y-coord of origin (most southerly pixel in this case)
            0,                        # Column rotation

            dy]                       # N-S pixel resolution (negative val for north-up images)
        # Account for low precision of original XLONG_M and XLAT_M variables
        self.gt_wrf = [float(round(x)) for x in gt_wrf]
        self.gti_wrf = gdalutil.invert_geotransform(gt_wrf)    # Inverse transform

        print('gt_wrf = ',gt_wrf)

    def to_ji(self, xx_scene, yy_scene):
        """points: [(x,y), ...]
        """

        xx_wrf,yy_wrf = self.scene2wrf.transform(xx_scene, yy_scene)

        # Apply the inverse geotransform
        GT = self.gti_wrf
        ir = GT[0] + xx_wrf*GT[1] + yy_wrf*GT[2]
        jr = GT[3] + xx_wrf*GT[4] + yy_wrf*GT[5]

        print('jr, ir = ', jr, ir)
        return np.round(ir), np.round(jr)

#        ii = round(xx_wrf / self.gt_wrf[1])
#        jj = round(yy_wrf / self.gt_wrf[5])


#        distances,indices = self.tree_wrf.query(points)
#        ii = np.mod(indices, self.nii)
#        jj = indices / self.nii

        return jj,ii    # Return in order ready to index WRF array

def pra_post(scene_dir):
    scene_args = params.load(scene_dir)

    # TODO: Put this in
    wrf_geo = os.path.join(dggs.data.HARNESS, 'data', 'lader', 'sx3', 'geo_southeast.nc')
    wrf_trans = WRFTransformer(wrf_geo, scene_args['coordinate_system'])

#    print(wrf_trans.to_ji(170663, 1334998))
    print(wrf_trans.to_ji(400971, 361673))    # Lower left
    print(wrf_trans.to_ji(1412333,1629588))    # Upper right
    return

#    ij = wrf_trans.to_ji([(1113095,1104476), (1112986,1104563)])
#    print(ij)

#    return

#    # Load a snow file (Alaska style)
#    # https://automating-gis-processes.github.io/2016/Lesson7-read-raster.html
#    snowf = os.path.join(dggs.data.HARNESS, 'data', 'lader', 'sx3', 'gfdl_1986_sx3.tif')
#    info = gdalutil.file_info(snowf)
#    print('geotransform ', info.geotransform)
#    print(info.to_xy(0,0))
#    print(info.to_xy(0,1))
#    print(info.to_xy(0,2))
#    try:
#        gd = gdal.Open(snowf)
#        band = gd.GetRasterBand(1)
#        snowdepths = gd.ReadAsArray()
#    finally:
#        gd = None

    # Load the polygons
    ifname = os.path.join(scene_dir, 'PRA_frequent', 'PRA_30y_For.shp')
    df = shputil.read_df(ifname, shape='pra').df
    df['area2'] = df['pra'].map(lambda pra: pra.area)
    loc = df['pra'].map(lambda pra: pra.centroid)
    df['loc'] = loc
    print(df['loc'])
#    df['locx'] = loc.map(lambda pt: pt.x)
#    df['locy'] = loc.map(lambda pt: pt.y)

#    print(df[['fid','area_m2','area2','loc']])
    wkt = scene_args['coordinate_system']

    # Look up (i,j) in raster of each polygon
    def _snow_depth(poly):
        centroid = poly.centroid
        ii,jj = info.to_ji(centroid.x, centroid.y)
#        print('ij ',centroid.x,centroid.y,ii,jj)
#        snowdepth = snowdepths[ii,jj]
#        return snowdepth
        return (ii,jj)
    df = df.iloc[[0,1]]
    df['ij'] = df['pra'].map(_snow_depth)
#    df['snowdepth'] = df['pra'].map(_snow_depth)
    print(df[['fid','area_m2','area2','loc', 'ij']])

    for _,row in df.iterrows():
        print('ij->loc ',row['ij'], info.to_xy(*row['ij']))



def main():
    scene_dir = os.path.join(dggs.data.HARNESS, 'prj', 'juneau1')
    pra_post(scene_dir)

main()
