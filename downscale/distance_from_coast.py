import os
import numpy as np
import pandas as pd
from akramms import config,params
from uafgi.util import gdalutil,wrfutil
from osgeo import gdalconst
import rtree    # https://toblerity.org/rtree/class.html

def main():
    # wrf-format files
    sx3_dir = config.roots.syspath('{DATA}/lader/sx3')
    wrf_geo_nc = os.path.join(sx3_dir, 'geo_southeast.nc')

    gridA = wrfutil.wrf_info(wrf_geo_nc)
    wrfdemA,wrfdemA_nodata = wrfutil.read_raw(wrf_geo_nc, 'HGT_M')    # North-up
    wrfdemA = wrfdemA[0,:,:]    # (y,x)
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
    for ix, lx,hx,ly,hy in zip(ocean_ix1, lowx, highx, lowy, highy):
        ocean_idx.insert(ix, (ly,lx,hy,hx))
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
        results = list(ocean_idx.nearest((y-hdy, x-hdx, y+hdy, x+hdx), num_results=1))
        source_ixs += [ix]*len(results)
        nearest_ixs += results
        source_ys += [y]*len(results)
        source_xs += [x]*len(results)
        bounds.append(len(nearest_ixs))

    # Convert 1D indices to x,y
    nearest_js, nearest_is = np.divmod(nearest_ixs, gridA.nx)
    nearest_xs, nearest_ys = gridA.to_xy(nearest_is, nearest_js)

    # Put it all in a dataframe
    print('source_ixs ', source_ixs)

    dfdict = {'ix': source_ixs, 'x': source_xs, 'y': source_ys, 'oceanx': nearest_xs, 'oceany': nearest_ys}
    for k,v in dfdict.items():
        print(k, len(v))
    df = pd.DataFrame(dfdict)
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
