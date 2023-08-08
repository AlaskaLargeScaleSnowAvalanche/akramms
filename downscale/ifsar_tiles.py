import os,re,subprocess
from akramms import config
from uafgi.util import pathutil


IFSAR_ROOT = config.roots.syspath('{DATA}/ifsar')
ifsar_roots = pathutil.RootsDict(os.path.sep,
    [('IFSAR', IFSAR_ROOT)] )

# ---------------------------------------------------------
def _list_tiles0(dir, type, tiles):
    """
    Lists all the tiles of a particular type within a directory (recursively)
    type: str
        'DTM', 'DSM', etc.
    tiles: list (OUTPUT)
        Add the tiles found here
    """

    nameRE = re.compile(r'{}.*\.tif'.format(type))

    for root, dirs, names in os.walk(dir):
        for name in names:
            match = nameRE.match(name)
            if match is None:
                continue
            tiles.append(os.path.join(root, name))

_cellRE = re.compile(r'((Cell_)|(CELL_))(\d+)')
def list_tiles(type):
    """
    Lists all the available IFSAR tiles
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

def build_vrt(type):
    tiles = list_tiles(type)
    data_root = config.roots['DATA']
    tile_relnames = [os.path.relpath(fname, data_root) for _,fname in tiles]
    ofname = config.roots.syspath('{DATA}/fischer/ifsar_'+type+'.vrt')
    print(f'Building {ofname} with {len(tile_relnames)} tiles')
    cmd = ['gdalbuildvrt']


    # Tiles use the same projection, but named differently
    # Error received: expected NAD83 / Alaska Albers, got NAD_1983_CORS96_Alaska_Albers
    # Eg: ifsar/CELL_391/N5430W13200P/DTM_N5430W13200P.tif
    cmd.append('-allow_projection_difference')

    cmd.append(ofname)
    cmd += tile_relnames
    subprocess.run(cmd, cwd=data_root, check=True)


def main():
#    tiles = list_tiles('DTM')
#    for tile in tiles:
#        print(tile)
##    print(tiles)
    build_vrt('DTM')

main()
