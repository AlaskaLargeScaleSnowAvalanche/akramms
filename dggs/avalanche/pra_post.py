import scipy.spatial
from osgeo import gdal
from dggs.avalanche import params
from uafgi.util import shputil,gdalutil,wrfutil
import os,sys
import subprocess
import json
import dggs.data
import pyproj
import netCDF4
import numpy as np
import gridfill




#def gridfill.fill(grids, xdim, ydim, eps, relax=.6, itermax=100, initzonal=False,
#         cyclic=False, verbose=False):
#    """
#    Fill missing values in grids with values derived by solving
#    Poisson's equation using a relaxation scheme.
#    **Arguments:**
#    *grid*
#        A masked array with missing values to fill.
#    *xdim*, *ydim*
#        The numbers of the dimensions in *grid* that represent the
#        x-coordinate and y-coordinate respectively.
#    *eps*
#        Tolerance for determining the solution complete.
#    **Keyword arguments:**
#    *relax*
#        Relaxation constant. Usually 0.45 <= *relax* <= 0.6. Defaults to
#        0.6.
#    *itermax*
#        Maximum number of iterations of the relaxation scheme. Defaults
#        to 100 iterations.
#    *initzonal*
#        If *False* missing values will be initialized to zero, if *True*
#        missing values will be initialized to the zonal mean. Defaults
#        to *False*.
#    *cyclic*
#        Set to *False* if the x-coordinate of the grid is not cyclic,
#        set to *True* if it is cyclic. Defaults to *False*.
#    *verbose*
#        If *True* information about algorithm performance will be
#        printed to stdout, if *False* nothing is printed. Defaults to
#        *False*.
#    """

class WrfLookup:
    def __init__(self, scene_wkt, data_fname, vname, geo_fname):

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
        with netCDF4.Dataset(data_fname) as nc:
            # Masked array
            masked_data = nc.variables[vname][:,:]    # sx3(j=south_north,i=west_east)
        #print('filled ',masked_data.mask[0,0], masked_data.data[0,0])
        #import copy
        #data2 = copy.copy(masked_data.data)
        #data2[data2<0] = 0.
        #print('sum is ',np.sum(data2))
        self.data,converged = gridfill.fill(masked_data, 1, 0, .001, itermax=10000)
        #print('filled ',self.data[0,0])
        #print('converged ',converged)

        #print(type(self.data), self.data.shape)
        #print(np.sum(self.data))
        #print(type(self.data), self.data[0,0])
        #print(np.sum(self.data < 0))

        # Write a GeoTIFF file of our results
        if False:
            (rows, cols) = self.data.shape
            gdalDriver = gdal.GetDriverByName('GTiff')
            outRaster = gdalDriver.Create('x.tif', cols, rows, 1, gdal.GDT_Float32,
              ['COMPRESS=DEFLATE'])
            try:
                outRaster.SetGeoTransform(self.geo_info.geotransform)
                outRaster.SetProjection(self.geo_info.wkt)
                outBand = outRaster.GetRasterBand(1)
                outBand.SetNoDataValue(np.nan)
                outBand.WriteArray(self.data)
            finally:
                outRaster = None


    def centroid_value(self, poly):
        centroid = poly.centroid    # In scene coordinates
        x_scene, y_scene = (centroid.x, centroid.y)
        x_wrf,y_wrf = self.scene2wrf.transform(x_scene, y_scene)    # --> WRF coordinates
        ir,jr = self.geo_info.to_ij(x_wrf, y_wrf)    # --> (j,i) index into data
        i = round(ir)
        j = round(jr)
#        print(f'({x_scene}, {y_scene}) -> ({x_wrf}, {y_wrf}) -> ({i}, {j})')
#        x2,y2 = self.geo_info.to_xy(i,j)
#        print(f'   -> ({x2},{y2})')
        return self.data[j,i]

    def to_ij(self, poly):
        centroid = poly.centroid    # In scene coordinates
        x_scene, y_scene = (centroid.x, centroid.y)
        x_wrf,y_wrf = self.scene2wrf.transform(x_scene, y_scene)    # --> WRF coordinates
        i,j = self.geo_info.to_ij(x_wrf, y_wrf)    # --> (j,i) index into data
        return (round(i), round(j))

def pra_post(scene_dir):
    scene_args = params.load(scene_dir)

    # Create lookup for snow depth in WRF output file
    scene_wkt = scene_args['coordinate_system']
    data_fname = os.path.join(dggs.data.HARNESS, 'data', 'lader', 'sx3', 'gfdl_sx3_1986.nc')
    vname = 'sx3'
    geo_fname = os.path.join(dggs.data.HARNESS, 'data', 'lader', 'sx3', 'geo_southeast.nc')

    print(geo_fname)
    print(data_fname)
    snow_lookup = WrfLookup(scene_wkt, data_fname, vname, geo_fname)


    # Load the polygons
    ifname = os.path.join(scene_dir, 'PRA_frequent', 'PRA_30y_For.shp')
    df = shputil.read_df(ifname, shape='pra').df
    df['area2'] = df['pra'].map(lambda pra: pra.area)
    df['loc'] = df['pra'].map(lambda pra: (round(pra.centroid.x), round(pra.centroid.y)))
    df['sx3'] = df['pra'].map(snow_lookup.centroid_value)
    df['ij'] = df['pra'].map(snow_lookup.to_ij)

    dfx = df[['fid','area_m2','area2','loc', 'ij', 'sx3']] 
#    print(dfx[dfx.sx3 < 0])
    print(dfx)
#    print(dfx.iloc[0])


def main():
#    with netCDF4.Dataset('x.nc', 'a') as nc:
#        sx3 = nc.variables['sx3'][:]
#        for i in range(sx3.shape[0]):
#            sx3[i,:] = i
#        for j in range(sx3.shape[1]):
#            sx3[:,j] += j
#        nc.variables['sx3'][:] = sx3


    scene_dir = os.path.join(dggs.data.HARNESS, 'prj', 'juneau1')
    pra_post(scene_dir)

main()
