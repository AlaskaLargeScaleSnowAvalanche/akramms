import os
import numpy as np
import pandas as pd
from akramms import config,params
from uafgi.util import gdalutil,wrfutil
from osgeo import gdalconst,gdal
import rtree    # https://toblerity.org/rtree/class.html

def main():
    # wrf-format files
    sx3_dir = config.roots.syspath('{DATA}/lader/sx3')
    wrf_geo_nc = os.path.join(sx3_dir, 'geo_southeast.nc')

    gridA = wrfutil.wrf_info(wrf_geo_nc)
    wrfdemA,wrfdemA_nodata = wrfutil.read_raw(wrf_geo_nc, 'HGT_M')    # North-up
    wrfdemA = wrfdemA[0,:,:]    # (y,x)

    # Turn ocean gridcells with little islands into pure ocean
    wrfdemA[np.abs(wrfdemA) < 10] = 0
    wrfdemA1 = wrfdemA.reshape(-1)


    # Get index and bounding box of each ocean gridcell
    ocean_ix1 = np.where(wrfdemA1 == 0)[0]
    ocean_ixs = np.where(wrfdemA == 0)

    centersy = gridA.centersy[ocean_ixs[0]]
    lowy  = centersy - 0.5*gridA.dy
    highy = centersy + 0.5*gridA.dy

    centersx = gridA.centersx[ocean_ixs[1]]
    lowx  = centersx - 0.5*gridA.dx
    highx = centersx + 0.5*gridA.dx

    # Make an rtree of it
    print('Assembling the rtree...')
    ocean_idx = rtree.index.Index()
#    for ix, lx,hx,ly,hy in zip(ocean_ix1, lowx, highx, lowy, highy):
#        ocean_idx.insert(ix, (ly,lx,hy,hx))
    for ix,cx,cy in zip(ocean_ix1, centersx, centersy):
        ocean_idx.insert(ix, (cy,cx,cy,cx))
    print('Done!')

    # Find index of nearest ocean gridcell(s) to all non-cean gridcells
    land_ixs = np.where(wrfdemA1 != 0)[0]
    jjs,iis = np.where(wrfdemA != 0)
    xs,ys = gridA.to_xy(iis, jjs)

    hdy = 0.5*gridA.dy
    hdx = 0.5*gridA.dx
    bounds = [0]
    source_ixs = list()
    source_xs = list()
    source_ys = list()
    nearest_ixs = list()
    for ix,y,x in zip(land_ixs,ys,xs):
#        results = list(ocean_idx.nearest((y-hdy, x-hdx, y+hdy, x+hdx), num_results=1))
        results = list(ocean_idx.nearest((y,x,y,x), num_results=30))
        source_ixs += [ix]*len(results)
        nearest_ixs += results
        source_ys += [y]*len(results)
        source_xs += [x]*len(results)
        bounds.append(len(nearest_ixs))

    # Convert 1D indices to x,y
    nearest_js, nearest_is = np.divmod(nearest_ixs, gridA.nx)
    nearest_xs, nearest_ys = gridA.to_xy(nearest_is, nearest_js)

    # Put it all in a dataframe

    dfdict = {'ix': source_ixs, 'landx': source_xs, 'landy': source_ys, 'oceanx': nearest_xs, 'oceany': nearest_ys}
    for k,v in dfdict.items():
        print(k, len(v))
    df = pd.DataFrame(dfdict)

    # Compute distance from land to ocean gridcell
    x = (df.landx - df.oceanx)
    x2 = x*x
    y = (df.landy - df.oceany)
    y2 = y*y
    df['distance'] = (x2+y2).map(np.sqrt)

    # Compute mean distance
    df = df[['ix', 'distance']]
    df = df.groupby('ix').mean().reset_index()

    # Create distance raster
    distanceA1 = np.zeros(gridA.nxy)
    distanceA1[df.ix.to_numpy()] = df.distance.to_numpy()
    distanceA = distanceA1.reshape((gridA.ny, gridA.nx))

    # Save it to GeoTIFF
    gdalutil.write_raster('distance.tif', gridA, distanceA, 0, type=gdal.GDT_Float32)
    gdalutil.write_raster('hgt.tif', gridA, wrfdemA, wrfdemA_nodata, type=gdal.GDT_Float32)

    print(df)


    return


    print(wrfdemA.shape)
    print(wrfdemA_nodata)
    print(wrfdemA1[0])
    print(np.sum(wrfdemA, axis=0))
    print(np.sum(wrfdemA, axis=1))
    print(zeros_ix)
    print(wrfdemA1.shape)
        
main()
