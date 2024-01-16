import functools
import enum
import numpy as np
from uafgi.util import gdalutil
from osgeo import osr,gdal,gdal_array
from osgeo import gdalconst
from akramms import r_experiment



#def distance_from_coast(gridA, ocean_mask):
#
#    """For "land" gridcells, computes typical distance from "ocean"
#    gridcells.
#
#    ocean_mask:
#        True for "ocean" gridcells, False for "land"
#
#    """
#
#    ocean_mask1 = ocean_mask.reshape(-1)
#
#    # Get index and bounding box of each ocean gridcell
#    ocean_ix1 = np.where(ocean_mask1)[0]
#    ocean_ixs = np.where(ocean_mask)
#
#    centersy = gridA.centersy[ocean_ixs[0]]
#    lowy  = centersy - 0.5*gridA.dy
#    highy = centersy + 0.5*gridA.dy
#
#    centersx = gridA.centersx[ocean_ixs[1]]
#    lowx  = centersx - 0.5*gridA.dx
#    highx = centersx + 0.5*gridA.dx
#
#    # Make an rtree of it
#    print('Assembling the rtree...')
#    ocean_idx = rtree.index.Index()
#    for ix, lx,hx,ly,hy in zip(ocean_ix1, lowx, highx, lowy, highy):
#       ocean_idx.insert(ix, (ly,lx,hy,hx))
#    for ix,cx,cy in zip(ocean_ix1, centersx, centersy):
#        ocean_idx.insert(ix, (cy,cx,cy,cx))
#    print('Done!')
#
#    # Find index of nearest ocean gridcell(s) to all non-ocean gridcells
#    land_ixs = np.where(np.logical_not(ocean_mask1))[0]
#    jjs,iis = np.where(np.logical_not(ocean_mask))
#    xs,ys = gridA.to_xy(iis, jjs, center=True)
#
#    #hdy = 0.5*gridA.dy
#    #hdx = 0.5*gridA.dx
#    bounds = [0]
#    source_ixs = list()
#    source_xs = list()
#    source_ys = list()
#    nearest_ixs = list()
#    for ix,y,x in zip(land_ixs,ys,xs):
#         results = list(ocean_idx.nearest((y-hdy, x-hdx, y+hdy, x+hdx), num_results=1))
#        # Find 30 nearest ocean gridcells to the current gridcell
#        results = list(ocean_idx.nearest((y,x,y,x), num_results=30))
#        source_ixs += [ix]*len(results)
#        nearest_ixs += results
#        source_ys += [y]*len(results)
#        source_xs += [x]*len(results)
#        bounds.append(len(nearest_ixs))
#
#    # Convert 1D indices to x,y
#    nearest_js, nearest_is = np.divmod(nearest_ixs, gridA.nx)
#    nearest_xs, nearest_ys = gridA.to_xy(nearest_is, nearest_js, center=True)
#
#    # Put it all in a dataframe
#
#    dfdict = {'ix': source_ixs, 'landx': source_xs, 'landy': source_ys, 'oceanx': nearest_xs, 'oceany': nearest_ys}
#    for k,v in dfdict.items():
#        print(k, len(v))
#    df = pd.DataFrame(dfdict)
#
#    # Compute distance from land to ocean gridcell
#    x = (df.landx - df.oceanx)
#    x2 = x*x
#    y = (df.landy - df.oceany)
#    y2 = y*y
#    df['distance'] = (x2+y2).map(np.sqrt)
#
#    # Compute mean distance
#    df = df[['ix', 'distance']]
#    df = df.groupby('ix').mean().reset_index()
#
#    # Create distance raster
#    distanceA1 = np.zeros(gridA.nxy)
#    distanceA1[df.ix.to_numpy()] = df.distance.to_numpy()
#    distanceA = distanceA1.reshape((gridA.ny, gridA.nx))
#
#    # Save it to GeoTIFF
#    os.makedirs(os.path.split(ofname)[0], exist_ok=True)
#    gdalutil.write_raster(ofname, gridA, distanceA, 0, type=gdal.GDT_Float32)
#    # gdalutil.write_raster('hgt.tif', gridA, wrfdemA, wrfdemA_nodata, type=gdal.GDT_Float32)


class MaskType(enum.IntEnum):
    MASK_OUT = 0      # Not part of the domain
    MARGIN = 1        # Avalanches can flow in here, but not start here
    MASK_IN = 2       # Avalanches can start here

def domain_mask(gridA, srcA, maxdist):

    """Uses GDAL's ComputeProximity() to assign a domain mask value to
    each gridcell.
      MASK_OUT: Gridcell is not part of the domain, and we have no data for it.

      MARGIN: We have data for the gridcell, but it is too close to
             the edge of the domain to allow for avalanche iniitiation.

      MASK_INT: The main part of the domain, where PRAs may form.

    NOTE: Domains (tiles) typically have an 8km margin in the current
         experiment.  Gridcells in this "standard" margin are NOT set
         to MARGIN, only gridcells in "non-standard" margins, as
         happens near Canada.  r_pra_post must still check that PRAs
         don't happen too close to the overall edge.

    srcA:
        integer array in gridA.  (Use .astype(int) to convert from a bool array)
        !=0: target cells ("ocean")
        0: non-target cells ("land")

    maxdist:
        Gridcells this far or farther from target cells will be marked
        as MASK_IN

    """

    # Options for the ComputeProxmity() call
    # https://svn.osgeo.org/gdal/trunk/gdal/swig/python/scripts/gdal_proximity.py
    # https://gdal.org/api/gdal_alg.html#_CPPv420GDALComputeProximity15GDALRasterBandH15GDALRasterBandHPPc16GDALProgressFuncPv
    options = ['DISTUNITS=GEO', f'MAXDIST={maxdist}', f'NODATA={int(MaskType.MASK_IN)}']

    # Construct an in-memory dataset for the input grid info
    srcA_ds = gdal_array.OpenArray(srcA)    # returns None on error
    gdalutil.set_grid_info(srcA_ds, gridA)
    srcA_rb = srcA_ds.GetRasterBand(1)

    # Constrcut output dataset
#    proxA = np.zeros(srcA.shape, dtype='d')
    proxA = np.zeros(srcA.shape, dtype=np.byte)
    proxA_ds = gdal_array.OpenArray(proxA)
    proxA_rb = proxA_ds.GetRasterBand(1)
    proxA_rb.SetNoDataValue(maxdist)


    options.append(f'FIXED_BUF_VAL={int(MaskType.MARGIN)}')
    gdal.ComputeProximity(srcA_rb, proxA_rb, options, callback=gdal.TermProgress)

    return proxA




# TODO: Get forest at 10m resolution...
#


# TODO: Pull distance_from_coast() function from downscale_snow.  It
# must work on WRF, but also at small scale for edge

# NOTE: There is always 100% coverage from WRF

@functools.lru_cache()
def rule(exp_mod, idom, jdom):

    dem_tif = r_experiment.r_ifsar(exp_mod, idom, jdom).outputs[0]
    #domains_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains.shp')
    #domains_margin_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains_margin.shp')
    #inputs = [domains_shp, domains_margin_shp, dem_tif]
    inputs = [dem_tif]

    dem_mask_tif = dem_tif.with_suffix('_mask.tif')
    outputs = [dem_mask_tif]

    def action(tdir):
        gridI, elevI, elevI_nd = gdalutil.read_raster(dem_tif)
        #ddf = shputil.read_df(domains_shp, read_shapes=True)
        #mdf = shputil.read_df(domains_margin_shp, read_shapes=True)

        mask_outI = (elevI == elevI_nd).astype(int)
        dmaskI = domain_mask(gridI, mask_outI, max(exp_mod.domain_margin))
        gdalutil.write_raster(dem_mask_tif, gridI, dmaskI, int(MaskType.MASK_OUT))

    return action


def main():
    dem_tif = '/Users/eafischer2/tmp/maps/ak_dem_111_042.tif'
    gridI, elevI, elevI_nd = gdalutil.read_raster(dem_tif)
    mask_outI = (elevI == elevI_nd).astype(int)
    proxI = compute_proximity(gridI, mask_outI, 8000.)
    gdalutil.write_raster('x1.tif', gridI, proxI, int(MaskType.MASK_OUT))

main()
    
