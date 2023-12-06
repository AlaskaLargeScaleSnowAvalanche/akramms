import functools,re,os,subprocess
from akramms import config
from uafgi.util import make,gdalutil

# There needs to be a symlink to the ACTUAL location of the ifsar data
ifsar_root = config.roots.syspath('{DATA}/ifsar')

# The top-level virtual raster file we select out of
@functools.lru_cache()
def ifsar_vrt(type):
    return config.roots.syspath('{DATA}/fischer/ifsar_'+type+'.vrt')

# ---------------------------------------------------------
_cellRE = re.compile(r'((Cell_)|(CELL_))(\d+)')
def list_tiles(type):
    """
    Lists all the available IFSAR tiles in the raw data
    """
    tiles = list()

    # Determine the Cell_ or CELL_ directories
    for name in os.listdir(IFSAR_ROOT):
        match = _cellRE.match(name)
        if match is None:
            continue
        cell = int(match.group(4))

        # List the tiles with each Cell_* directory
        nameRE = re.compile(r'{}.*\.tif$'.format(type))
        for root, dirs, names in os.walk(os.path.join(IFSAR_ROOT, name)):
            for name in names:
                match = nameRE.match(name)
                if match is None:
                    continue
                tiles.append((cell, os.path.join(root, name)))

    # Sort it all
    tiles.sort()
    return tiles

@functools.lru_cache()
def r_vrt(type):
    """Assemble the IFSAR data into a GDAL Virtual Raster"""
    ofname = ifsar_vrt(type)

    def action(self, tdir):
        tiles = list_tiles(type)
        data_root = config.roots['DATA']
        tile_relnames = [os.path.relpath(fname, data_root) for _,fname in tiles]
        print(f'Building {ofname} with {len(tile_relnames)} tiles')
        cmd = ['gdalbuildvrt']


        # Tiles use the same projection, but named differently
        # Error received: expected NAD83 / Alaska Albers, got NAD_1983_CORS96_Alaska_Albers
        # Eg: ifsar/CELL_391/N5430W13200P/DTM_N5430W13200P.tif
        cmd.append('-allow_projection_difference')

        cmd.append(ofname)
        cmd += tile_relnames
        subprocess.run(cmd, cwd=data_root, check=True)

    return make.Rule(action, [], [ofname])
# ------------------------------------------------------------------
def extract(type, poly, ofname, resolution=None, sanity_check=True):
    """
    poly:
        A rectangle
    ofname:
        Output raster filename
    """
    xx,yy = poly.exterior.coords.xy

    x0,x1,y0,y1 = gdalutil.positive_rectangle(xx[0], xx[2], yy[0], yy[2])

    cmd = ['gdal_translate']
    # https://gis.stackexchange.com/questions/1104/should-gdal-be-set-to-produce-geotiff-files-with-compression-which-algorithm-sh
    cmd += ['-co', 'COMPRESS=DEFLATE']
    cmd += ['-co', 'TFW=YES']   # https://gis.stackexchange.com/questions/271995/how-to-get-gdal-translate-to-create-world-file-for-geotiff
#    if sanity_check:
#        cmd += ['-eco']    # Error when completely outside (SANITY CHECK)
    if resolution is not None:
        cmd += ['-tr', str(resolution), str(resolution)]

    cmd.append('-projwin')
    # -projwin <ulx> <uly> <lrx> <lry>
    # Therefore, y1<y0 in typical projection, where y increases as you go northward.
    cmd += [str(n) for n in (x0,y1,x1,y0)]

    # This needs to be in i/j not x/y
    # cmd.append('-srcwin')
    # cmd += [str(n) for n in (min(x0,x1), min(y0,y1), abs(x1-x0), abs(y1-y0))]

#    cmd += [str(n) for n in (min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))]
#    cmd += ['-projwin', str(x0), str(y1), str(x1), str(y0), ifsar_vrt, ofname]    # North-up
    cmd += [r_vrt(type).outputs[0], ofname]

    os.makedirs(os.path.split(ofname)[0], exist_ok=True)
    subprocess.run(cmd, check=True)

# ------------------------------------------------------------------
