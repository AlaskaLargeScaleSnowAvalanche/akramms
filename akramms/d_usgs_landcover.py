import os,subprocess
from akramms import config

# There needs to be a symlink to the ACTUAL location of the ifsar data
landcover_dir = config.roots.syspath('{DATA}/LandCover')
landcover_img = os.path.join(landcover_dir, 'ak_nlcd_2011_landcover_1_15_15.img')

# ------------------------------------------------------------------
def extract(poly, ofname):
    """
    poly:
        The rectangular domain to select.
    ofname:
        File to write.
    """
    xx,yy = poly.exterior.coords.xy
    x0 = xx[0]
    x1 = xx[2]
    y0 = yy[0]
    y1 = yy[2]

    cmd = ['gdal_translate']
    # https://gis.stackexchange.com/questions/1104/should-gdal-be-set-to-produce-geotiff-files-with-compression-which-algorithm-sh
    cmd += ['-co', 'COMPRESS=DEFLATE']
    cmd += ['-co', 'TFW=YES']   # https://gis.stackexchange.com/questions/271995/how-to-get-gdal-translate-to-create-world-file-for-geotiff
    cmd += ['-eco']    # Error when completely outside (SANITY CHECK)

    cmd.append('-projwin')
    cmd += [str(n) for n in (x0,y1,x1,y0)]
    cmd += [landcover_img, ofname]

    os.makedirs(os.path.split(ofname)[0], exist_ok=True)
    subprocess.run(cmd, check=True)

# ------------------------------------------------------------------

