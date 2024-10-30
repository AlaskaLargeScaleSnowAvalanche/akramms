import os,copy,functools,itertools
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

def _read_ocean(expmod, idom, jdom, imosaic_grid):
    """Read the ocean mask"""
    global _last_landcover_tif, _last_ocean_mask

    landcover_tif = expmod.dir / 'landcover' / f'{expmod.name}_landcover_{idom:03d}_{jdom:03d}.tif'

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
def rbind(fn, *rargs):
    def _fn(*largs, **kwargs):
        return fn(*itertools.chain(largs, rargs), **kwargs)
    return _fn


def _read_land(expmod, combo):
    """Variable = 1 for land gridcells, 0 for ocean"""

    # Get imosaic_grid
    section = _section(expmod, combo)
    vname = 'avalanche_count'    # Any name works
    publish_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_publish')
    imosaic_tif = publish_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}.tif'
    imosaic_grid = gdalutil.read_grid(imosaic_tif)

    ocean_mask = _read_ocean(expmod, combo.idom, combo.jdom, imosaic_grid)
    return imosaic_grid, np.logical_not(ocean_mask).astype('d'), -1e10

def _read_thresh(expmod, combo, vname):
    """Thresholds a "count" variable to 0 or 1"""

    section = _section(expmod, combo)
    publish_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_publish')
    imosaic_tif = publish_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}.tif'

    # Read the variable
    imosaic_grid, imosaic_data, imosaic_nd = gdalutil.read_raster(imosaic_tif)
    imosaic_data = np.clip(imosaic_data, None, 1)
    imosaic_data = imosaic_data.astype('d')
    assert imosaic_nd == 0

    # Use the ocean mask to set nodata values
    ocean_mask = _read_ocean(expmod, combo.idom, combo.jdom, imosaic_grid)
    mosaic_nd = -1e10
    imosaic_data[ocean_mask] = imosaic_nd

    return imosaic_grid, imosaic_data, mosaic_nd

def _read_double(expmod, combo, vname):
    """No Thresholding, variable already double"""

    publish_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_publish')
    imosaic_tif = publish_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}.tif'

    # Read the variable
    imosaic_grid, imosaic_data, imosaic_nd = gdalutil.read_raster(imosaic_tif)
#    imosaic_data = np.clip(imosaic_data, None, 1)
    imosaic_data = imosaic_data.astype('d')
    assert imosaic_nd == 0

    # Use the ocean mask to set nodata values
    ocean_mask = _read_ocean(expmod, combo.idom, combo.jdom, imosaic_grid)
    mosaic_nd = -1e10
    imosaic_data[ocean_mask] = imosaic_nd

    return imosaic_grid, imosaic_data, mosaic_nd

def _by_area(grid):
    return 1. / (grid.dx * grid.dy)

def _by_1(grid):
    return 1

stats_vars = {
    'land': (_read_land, _by_area, '1'),
    'avy_extent': (rbind(_read_thresh, 'avalanche_count'), _by_1, '1'),
    'count': (rbind(_read_thresh, 'pra_centroid_count'), _by_area, 'km-2'),
    'release_extent': (rbind(_read_thresh, 'pra_count'), _by_area, '1'),
}


def regrid_stdmosaic(expmod, combo, vname, res):
    read_fn, scale_fn, sunits = stats_vars[vname]

    section = _section(expmod, combo)

    stats_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + f'_stats') / f'{res}'

    omosaic_tif = stats_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}-stats{res}.tif'

    if os.path.isfile(omosaic_tif):
        return

    imosaic_grid, imosaic_data, imosaic_nd = read_fn(expmod, combo)

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
        imosaic_data, imosaic_grid, imosaic_nd,
        stats_grid, imosaic_nd,
        resample_algo=gdalconst.GRA_Average)

    print(f'Writing {omosaic_tif}')
    os.makedirs(omosaic_tif.parents[0], exist_ok=True)
    gdalutil.write_raster(
        omosaic_tif,
        stats_grid, stats_data, imosaic_nd)


def stats_combo(akdf0, ress=[1000]):

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

        for vname in stats_vars.keys():
            for res in ress:
                regrid_stdmosaic(expmod, combo, vname, res)
