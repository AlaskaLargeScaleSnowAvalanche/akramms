import os,subprocess
from akramms import config
from uafgi.util import gdalutil

# There needs to be a symlink to the ACTUAL location of the ifsar data
landcover_dir = config.roots.syspath('{DATA}/LandCover')
#landcover_img = os.path.join(landcover_dir, 'OlderVersions', 'ak_nlcd_2011_landcover_1_15_15.img')
landcover_img = os.path.join(landcover_dir, 'NLCD_2016_Land_Cover_AK_20200724', 'NLCD_2016_Land_Cover_AK_20200724.img')


# ------------------------------------------------------------------
def extract(poly, ofname):
    """
    poly:
        The rectangular domain to select.
    ofname:
        File to write.
    """
    xx,yy = poly.exterior.coords.xy

    # -projwin <ulx> <uly> <lrx> <lry>
    # Therefore, y1<y0 in typical projection, where y increases as you go northward.
    x0,x1,y0,y1 = gdalutil.positive_rectangle(xx[0], xx[2], yy[0], yy[2])

    cmd = ['gdal_translate']
    # https://gis.stackexchange.com/questions/1104/should-gdal-be-set-to-produce-geotiff-files-with-compression-which-algorithm-sh
    cmd += ['-co', 'COMPRESS=DEFLATE']
    cmd += ['-co', 'TFW=YES']   # https://gis.stackexchange.com/questions/271995/how-to-get-gdal-translate-to-create-world-file-for-geotiff
    cmd += ['-eco']    # Error when completely outside (SANITY CHECK)

    cmd.append('-projwin')
    cmd += [str(n) for n in (x0,y1,x1,y0)]
    cmd += [landcover_img, ofname]

    print('cmd ', cmd)


    os.makedirs(os.path.split(ofname)[0], exist_ok=True)
    subprocess.run(cmd, check=True)

# ------------------------------------------------------------------


# https://gis.stackexchange.com/questions/349818/resample-raster-from-one-resolution-to-another-with-gdal-python-api
