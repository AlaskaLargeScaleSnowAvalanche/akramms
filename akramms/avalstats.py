def regrid_stdmosaic(expmod, combo, vname, res):
    publish_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_publish')
    stats_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + '_stats_{res}')

    imosaic_tif = publish_dir / vname / f'{expmod.name}_vname_{combo.idom:03d}_{combo.jdom:03d}.tif'
    omosaic_tif = stats_dir / vname / f'{expmod.name}_vname_{combo.idom:03d}_{combo.jdom:03d}_stats_{res}.tif'
    forest_tif = expmod.dir / 'forest' / f'{expmod.name}_forest_{combo.idom:03d}_{combo.jdom:03d}.tif'



    # Read the variable
    imosaic_grid, imosiac_data, imosaic_nd = gdalutil.read_raster(imosaic_tif)
    assert imosaic_nd == 0


    # Read the ocean mask
    landcover30_grid, landcover30_data, landcover30_nd = gdalutil.read_raster(landcover_tif)    # landcover_grid includes margin
    ocean30_mask = [landcover30_data == 11]    # 11 = "Open Water"
    ocean30_data = np.zeros(ocean30_mask.shape, dtype='d')
    ocen30_data[ocean30_mask] = 1

    # Regrid ocean mask to same grid as mosaic
    ocean_mask = gdalutil.regrid(
        ocean30_data, ocean30_grid, ocean30_nd,
        imosaic_grid, ocean30_nd)

    # Use the ocean mask to set nodata values
    mosaic_nd = -10e10
    imosaic_data[ocean_mask] = imosaic_nd

    # Construct stats grid (at low resolution), used for averaging
    onx = int(round(imosaic_grid.nx * imosiac_grid.resx / res))
    ony = int(round(imosaic_grid.ny * imosiac_grid.resy / res))
    stats_grid = gisutil.RasterInfo(
        imosaic_grid.wkt, onx, ony,
        imosaic_grid.geotransform)

    # Regrid mosiac to the stats grid
    stats_data = gdalutil.regrid(
        imosaic, imosaic_grid, mosaic_nd,
        stats_grid, mosaic_nd,
        resample_algo=gdalconst.GRA_Average)


    gdalutil.write_raster(
        omosaic_tif,
        stats_grid, stats_data, stats_nd)
