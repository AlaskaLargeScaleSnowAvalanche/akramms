import setuptools.sandbox
import pathlib
import os
from uafgi.util import gdalutil, rasterize, shputil

#dir = pathlib.Path('/Users/eafischer2/tmp/maps')

dir = pathlib.Path('/mnt/avalanche_sim/prj/ak/dem')
neighbor1_file = dir / 'ak_dem_113_045_neighbor1.tif'
dem_filled_file = dir / 'ak_dem_113_045_filled.tif'

dir = pathlib.Path('/mnt/avalanche_sim/prj/ak/ak-ccsm-1981-1990-lapse-For-30/x-113-045/PRA_frequent')
pra_frequent_file = dir / 'PRA_30y_For.shp'

#HARNESS = '/Users/eafischer2/av'
HARNESS = '/home/efischer/av'

def main():


    # ------------
    # Make sure the domain finder C++ code is compiled. (needed for RAMMS Stage 1)
    setup_py = os.path.join(HARNESS, 'akramms', 'setup.py')
    prefix = os.path.join(HARNESS, 'akramms', 'inst')
    cmd = ['install', '--prefix', prefix]
    print('setup.py ', cmd)
    setuptools.sandbox.run_setup(setup_py, cmd)
    # ------------

    import d8graph

    # (grid_info includes the domain margin)
    grid_info, dem_filled, dem_nodata = gdalutil.read_raster(dem_filled_file)

    df = shputil.read_df(pra_frequent_file, shape='pra')
    df = df.rename(columns={'fid': 'Id'})    # RAMMS etc. want it named "Id"
    row = df[df.Id == 4857]
    print(row)
    print(type(row))

    # Get list of gridcells covered by the PRA polygon (the "PRA Burn")
    pra_burn = rasterize.rasterize_polygon_compressed(row['pra'], grid_info)

    print('pra_burn ', pra_burn)

    # Get the domain from the PRA burn
    args = ()
    #        margin = margins[row['pra_size']]
    margin = 1000.
    ret = d8graph.find_domain(
        dem_filled, dem_nodata, grid_info.geotransform, pra_burn,
        debug=1, margin=margin, **kwargs)

    print(ret)

main()
