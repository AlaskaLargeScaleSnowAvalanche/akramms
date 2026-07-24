import os
from osgeo import gdal
import shapely.geometry
from uafgi.util import gdalutil


def read_subraster(gridD, raster_dir, name_pattern, extent, **kwargs):

    """
    extent: gisutil.Extent
        
    name_pattern: str
        Pattern for filenames found in raster_dir
        Must have {idom} and {jdom} as format fiels

    kwargs:
        For gdal.Warp

    Returns: grid_info, data, nodata_value
    """

    poly = shapely.geometry.box(*extent.xyxy)    # xyxy
    tiledf = gridD.intersecting_tiles(poly)

    # Files available in raster_dir
    all_names = set(os.listdir(raster_dir))

    # Set up in-memory vrt file (use GDAL's virtual filesystem)
    vrt_files = list()    # Names to include in the (in-memory)VRT file
    for tup in tiledf.itertuples():
        name = name_pattern.format(idom=tup.idom, jdom=tup.jdom)
        if name in all_names:
            vrt_files.append(str(raster_dir / name))

    print('VRT Files: ', raster_dir)
    for x in vrt_files:
        print('   ', x)

    raster_vrt = "/vsimem/raster.vrt"
    #options = gdal.BuildVRTOptions(resampleAlg="bilinear")
    vrt_ds = gdal.BuildVRT(raster_vrt, vrt_files)   #, options=options)

    # Warp into our extracted in-memory raster
    # srs = osr.SpatialReference(wkt=expmod.wkt)
    kwargs.update((
        ('dstSRS', vrt_ds.GetSpatialRef()), 
        ('outputBounds', extent.xyxy),
        ('format', 'VRT')))
    print('kwargs ', kwargs)
    mem_ds = gdal.Warp('', vrt_ds, **kwargs)
    return gdalutil.read_ds(mem_ds)
