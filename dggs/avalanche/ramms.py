import os
from dggs.avalanche import avalanche
from uafgi.util import make
import itertools

def ramms_dir(scene_dir, return_period, forest):
    scene_args = avalanche.params.load(scene_dir)
    name = scene_args['name']
    For = 'For' if forest else 'NoFor'
    ramms_name = f"{name}{return_period}y{For}"
    return os.path.join(scene_dir, 'RAMMS', ramms_name)

# --------------------------------------------------------------------
def rammsdir_rule_demfiles(scene_dir, return_period, forest):
    scene_args = avalanche.params.load(scene_dir)
    resolution = scene_args['resolution']
    name = scene_args['name']
    For = 'For' if forest else 'NoFor'

    idem_dir,idem_tif = os.path.split(scene_args['dem_file'])
    idem_stub = idem_tif[:-4]
    xramms_dir = ramms_dir(scene_dir, return_period, forest)
    return [
        (os.path.join(idem_dir, f'{idem_stub}.tif'), os.path.join(xramms_dir, 'DEM', f'{name}_{For}_{resolution}m_DEM.tif')),
        (os.path.join(idem_dir, f'{idem_stub}.tfw'), os.path.join(xramms_dir, 'DEM', f'{name}_{For}_{resolution}m_DEM.tfw')),
    ]

def rammsdir_rule(scene_dir, return_period, forest):
    dem_files = rammsdir_rule_demfiles(scene_dir, return_period, forest)

    def action(tdir):
        # Just make symlinks
        for ifile,ofile in dem_files:
            if not os.path.exists(ofile):
                odir = os.path.split(ofile)[0]
                os.makedirs(odir, exist_ok=True)
                os.symlink(ifile, ofile)

    return make.Rule(action, [d[0] for d in dem_files], [d[1] for d in dem_files])
# --------------------------------------------------------------------
def ramms_rule(scene_dir, dem_files, release_files, domain_files):

    def action(tdir):
        print('Running RAMMS ', dem_files[0])

    return make.Rule(action,
        list(itertools.chain(dem_files, release_files, domain_files)),
        [])    # We don't really know the output files yet

