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


#    for id in range(4800,4900):
    for id in [4857]:

    #    row = df[df.Id == 4857].squeeze()    # The problem PRA
#        row = df[df.Id == 4856].squeeze()
        row = df[df.Id == id].squeeze()

        print(row)
        print(type(row))

        # Get list of gridcells covered by the PRA polygon (the "PRA Burn")
        pra_burn = rasterize.rasterize_polygon_compressed(row['pra'], grid_info)

        print('pra_burn ', pra_burn)

        # Get the domain from the PRA burn
        args = ()
        #        margin = margins[row['pra_size']]
        margin = 1000.
        kwargs = {}
    #    Optional kwargs
    #        Forwarded to d8graph.find_domain()
    #        debug: int
    #            Set to 1 to put d8graph CPP code in debug mode
    #        min_alpha: (default 18.0 degrees)
    #            Minimum "alpha" angle at which avalanche expected to continue
    #        max_runout: (default 10000.)
    #            Maximum distance avalanche can go [m]


        ret = d8graph.find_domain(
            dem_filled, dem_nodata, grid_info.geotransform, pra_burn,
            debug=1, margin=margin, **kwargs)

        seen_list,chull_list,domain_list = ret
        print(ret)

        # Determine if this is clockwise or CCW
        # https://stackoverflow.com/questions/1165647/how-to-determine-if-a-list-of-polygon-points-are-in-clockwise-order
        sum = 0
        for edge in zip(domain_list[:-1], domain_list[1:]):
            sum += (edge[1][0] - edge[0][0]) * (edge[1][1] + edge[1][0])
        print(f'{id}: CW/CCW sum = {sum}')

main()
