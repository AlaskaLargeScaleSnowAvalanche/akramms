import os,copy,functools
import numpy as np
from osgeo import gdalconst
from uafgi.util import gisutil, gdalutil
import akramms.parse
from akramms import avalquery

_last_landcover_tif = None
_last_ocean_mask = None

@functools.lru_cache()
def _section(expmod, combo):
    # Get name of section within publish eg: ak-ccsm-1981-2010-lapse-All-30
    lcombo = str(combo).split('-')
    section =  expmod.name + '-' + '-'.join(lcombo[:-2])
    return section

def _read_ocean(expmod, combo, vname, imosaic_grid):
    """Read the ocean mask"""
    global _last_landcover_tif, _last_ocean_mask

    section = _section(expmod, combo)
    imosaic_tif = publish_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}.tif'

    # Handle memoize / LRU cache
    if landcover_tif == _last_landcover_tif:
        return _last_ocean_mask

    landcover30_grid, landcover30_data, landcover30_nd = gdalutil.read_raster(landcover_tif)    # landcover_grid includes margin

    ocean30_mask = (landcover30_data == 11)
    ocean30_nd = 100    # Doesn't really matter, ocean30_data is either 0 or 1

    ocean30_data = np.zeros(landcover30_data.shape, dtype=np.int8)
    ocean30_data[ocean30_mask] = 1

    # Regrid ocean mask to same grid as mosaic
    ocean_data = gdalutil.regrid(
        ocean30_data, landcover30_grid, ocean30_nd,
        imosaic_grid, ocean30_nd)
    ocean_mask = (ocean_data != 0)

    # Handle memoize
    _last_landcover_tif = landcover_tif
    _last_ocean_mask = ocean_mask
    return ocean_mask

# ------------------------------------------------------------------
# Read each different variable


def _read_land(combo):






def regrid_stdmosaic(expmod, combo, vname, res):

    section = _section(expmod, combo)

    publish_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_publish')
    stats_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + f'_stats_{res}')

#    imosaic_tif = publish_dir / vname / f'{expmod.name}_vname_{combo.idom:03d}_{combo.jdom:03d}.tif'
    omosaic_tif = stats_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}-stats{res}.tif'
#    omosaic_tif = stats_dir / section / vname / f'{expmod.name}_vname_{combo.idom:03d}_{combo.jdom:03d}_stats_{res}.tif'
    landcover_tif = expmod.dir / 'landcover' / f'{expmod.name}_landcover_{combo.idom:03d}_{combo.jdom:03d}.tif'

    # Read the variable
    imosaic_grid, imosaic_data, imosaic_nd = gdalutil.read_raster(imosaic_tif)
    imosaic_data = np.clip(imosaic_data, None, 1)
    imosaic_data = imosaic_data.astype('d')
    assert imosaic_nd == 0

    # Use the ocean mask to set nodata values
    ocean_mask = _read_ocean(landcover_tif, imosaic_grid)
    mosaic_nd = -1e10
    imosaic_data[ocean_mask] = imosaic_nd

    # Construct stats grid (at low resolution), used for averaging
    onx = int(round(imosaic_grid.nx * np.abs(imosaic_grid.dx) / res))
    ony = int(round(imosaic_grid.ny * np.abs(imosaic_grid.dy) / res))
    gt = copy.copy(imosaic_grid.geotransform)
    gt[1] = res * np.sign(imosaic_grid.geotransform[1])    # dx
    gt[5] = res * np.sign(imosaic_grid.geotransform[5])   # dy
    stats_grid = gisutil.RasterInfo(
        imosaic_grid.wkt, onx, ony,
        gt)

    # Regrid mosaic to the stats grid
    stats_data = gdalutil.regrid(
        imosaic_data, imosaic_grid, mosaic_nd,
        stats_grid, mosaic_nd,
        resample_algo=gdalconst.GRA_Average)

    print(f'Writing {omosaic_tif}')
    os.makedirs(omosaic_tif.parents[0], exist_ok=True)
    gdalutil.write_raster(
        omosaic_tif,
        stats_grid, stats_data, mosaic_nd)


def stats_combo(akdf0, res=1000):

    """

    akdf:
        Avalanches (in scenetype='arc') to mosiac
        Resolved to the combo level
        Must contain columns: releasefile (actually arcdir), avalfile, id

    res: [m]
        Gridcell size to average up to.
        Most be an even divisor of tile size.
    """

    print('=== BEGIN stats_combo()')
    print(akdf0)
    exp = akdf0.exp[0]
    expmod = akramms.parse.load_expmod(exp)

    for akdf1 in avalquery.consolidate_by_forest(expmod, akdf0):
        # Change For/NoFor to All
        combo = akdf1.combo[0]
#        exp = akdf1.exp[0]
        combo = combo._replace(forest='All')
        print('combo ', combo)

        res = 1000
        for vname in ('pra_count',):
            regrid_stdmosaic(expmod, combo, vname, res)
