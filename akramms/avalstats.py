import os,copy
import numpy as np
from osgeo import gdalconst
from uafgi.util import gisutil, gdalutil


def regrid_stdmosaic(expmod, combo, vname, res):

    # Get name of section within publish eg: ak-ccsm-1981-2010-lapse-All-30
    lcombo = str(combo).split('-')
    section =  expmod.name + '-' + '-'.join(lcombo[:-2])
    




    publish_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_publish')
    stats_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + f'_stats_{res}')

#    imosaic_tif = publish_dir / vname / f'{expmod.name}_vname_{combo.idom:03d}_{combo.jdom:03d}.tif'
    imosaic_tif = publish_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}.tif'
    omosaic_tif = stats_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}-stats{res}.tif'
#    omosaic_tif = stats_dir / section / vname / f'{expmod.name}_vname_{combo.idom:03d}_{combo.jdom:03d}_stats_{res}.tif'
    landcover_tif = expmod.dir / 'landcover' / f'{expmod.name}_landcover_{combo.idom:03d}_{combo.jdom:03d}.tif'

    # Read the variable
    imosaic_grid, imosaic_data, imosaic_nd = gdalutil.read_raster(imosaic_tif)
#    imosaic_data = np.maximum(imosaic_data, 1)
    imosaic_data = np.clip(imosaic_data, None, 1)
    imosaic_data = imosaic_data.astype('d')
    assert imosaic_nd == 0

    # Read the ocean mask
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

    # Use the ocean mask to set nodata values
    mosaic_nd = -1e10
    imosaic_data[ocean_mask] = imosaic_nd

    # Construct stats grid (at low resolution), used for averaging
    onx = int(round(imosaic_grid.nx * np.abs(imosaic_grid.dx) / res))
    ony = int(round(imosaic_grid.ny * np.abs(imosaic_grid.dy) / res))
    gt = copy.copy(imosaic_grid.geotransform)
    gt[1] = res * np.sign(imosaic_grid.geotransform[1])    # dx
    gt[5] = res * np.sign(imosaic_grid.geotransform[5])   # dy
    print('onx ony ', onx, ony)
    stats_grid = gisutil.RasterInfo(
        imosaic_grid.wkt, onx, ony,
        gt)
    print('stats_grid res ', stats_grid.dx, stats_grid.dy)


    print('imosaic_grid ', imosaic_grid)
    print('stats_grid ', stats_grid)

    # Regrid mosaic to the stats grid
    stats_data = gdalutil.regrid(
        imosaic_data, imosaic_grid, mosaic_nd,
#        imosaic_grid, mosaic_nd,
        stats_grid, mosaic_nd,
        resample_algo=gdalconst.GRA_Average)
    print('stats_data dtype ', stats_data.dtype)
    print(stats_data)

    os.makedirs(omosaic_tif.parents[0], exist_ok=True)
    gdalutil.write_raster(
        omosaic_tif,
#        imosaic_grid, imosaic_data, mosaic_nd)
        stats_grid, stats_data, mosaic_nd)
