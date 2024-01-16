import functools
import enum
import numpy as np
from uafgi.util import gdalutil, make
from osgeo import osr,gdal,gdal_array
from osgeo import gdalconst
from akramms import r_experiment

class Value(enum.IntEnum):
    MASK_OUT = 0      # Not part of the domain
    MARGIN = 1        # Avalanches can flow in here, but not start here
    MASK_IN = 2       # Avalanches can start here

def domain_mask(gridA, srcA, maxdist):

    """Uses GDAL's ComputeProximity() to assign a domain mask value to
    each gridcell, based on its distance from the edge of the domain
    (disregarding the natural rectangular edge).

    Assignment is one of Value:
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
    options = ['DISTUNITS=GEO', f'MAXDIST={maxdist}', f'NODATA={int(Value.MASK_IN)}']

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


    options.append(f'FIXED_BUF_VAL={int(Value.MARGIN)}')    # distance 0<=x<maxdist, label as MARGIN
    gdal.ComputeProximity(srcA_rb, proxA_rb, options, callback=gdal.TermProgress)

    return proxA

# NOTE: There is always 100% coverage from WRF

@functools.lru_cache()
def rule(exp_mod, idom, jdom):

    dem_tif = r_experiment.r_ifsar(exp_mod, idom, jdom).outputs[0]
    #domains_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains.shp')
    #domains_margin_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains_margin.shp')
    #inputs = [domains_shp, domains_margin_shp, dem_tif]
    inputs = [dem_tif]

    dem_mask_tif = dem_tif.parents[0] / (dem_tif.parts[-1][:-4] + '_mask.tif')
    outputs = [dem_mask_tif]

    def action(tdir):
        gridI, elevI, elevI_nd = gdalutil.read_raster(dem_tif)
        #ddf = shputil.read_df(domains_shp, read_shapes=True)
        #mdf = shputil.read_df(domains_margin_shp, read_shapes=True)

        mask_outI = (elevI == elevI_nd).astype(int)
        dmaskI = domain_mask(gridI, mask_outI, max(exp_mod.domain_margin))
        gdalutil.write_raster(dem_mask_tif, gridI, dmaskI, int(Value.MASK_OUT))

    return make.Rule(action, inputs, outputs)


#def main():
#    dem_tif = '/Users/eafischer2/tmp/maps/ak_dem_111_042.tif'
#    gridI, elevI, elevI_nd = gdalutil.read_raster(dem_tif)
#    mask_outI = (elevI == elevI_nd).astype(int)
#    proxI = compute_proximity(gridI, mask_outI, 8000.)
#    gdalutil.write_raster('x1.tif', gridI, proxI, int(Value.MASK_OUT))
#
#main()
    
