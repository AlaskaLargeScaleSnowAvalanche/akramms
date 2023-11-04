from uafgi.util import make,shputil
from akramms import config,params,process_tree,joblib
from akramms import r_prepare, r_ecog, r_pra_post, r_domain_builder, r_ramms
from akramms.util import paramutil,harnutil,rammsutil
import os,sys
import setuptools.sandbox
import pandas as pd

"""Rules for RAMMS Stage 1 (with auto submit to Stage 2)"""

__all__ = ('rule',)

# -------------------------------------------------------------
def tiffmap(jb1):

    """Returns a mapping between a parsed RAMMS dir vs. "permanent"
    names for .tif files that can be reused for different chunks in
    RAMMS Stage 1.  After RAMMS stage 1, files will be copied from the
    chunk to their general location, as appropriate.

    jb1:
        Parsed release file name of one chunk
    Returns: [(fname_chunk, fname_general), ...]

    """

    # Parsed release file name of the dummy overall run used to create
    # reusable names for the TIF files.
    jb0 = jb1.copy(segment=None)
    scene_dir = os.path.dirname(jb1.ramms_harness)
    scene_args = params.load(scene_dir)

    results_dir1 = os.path.join(jb1.ramms_dir, 'RESULTS', jb1.rammsdir_name)

    map = [
#        # ./juneau10000030MFor_5m/DEM/juneau100000For_5m_dem.tif
#        (f'{jb1.ramms_dir}/DEM/{jb1.ramms_name}_dem.tif', scene_args['dem_file']),

#        # ./juneau10000030MFor_5m/FOREST/juneau100000For_5m_forest.tif
#        (f'{jb1.ramms_dir}/FOREST/{jb1.ramms_name}_forest.tif', scene_args['forest_file']),

        # -------------- Items for all sub-directories of the slope_dir
        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/slope.tif
        (f'{jb1.slope_dir}/slope.tif',
            f'SLOPE_TIF/{jb0.slope_name}/slope.tif'),
        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/curvidl.tif
        (f'{jb1.slope_dir}/curvidl.tif',
            f'SLOPE_TIF/{jb0.slope_name}/curvidl.tif'),

        # -------------- Items for each subdir
        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/juneau100000For_5m_M30_xi.tif
        (f'{jb1.slope_dir}/{jb1.slope_name}_{jb0.pra_size}{jb1.return_period}_xi.tif',
            f'SLOPE_TIF/{jb0.slope_name}/{jb0.slope_name}_{jb0.pra_size}{jb0.return_period}_xi.tif'),

        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/juneau100000For_5m_M30_mu.tif
        (f'{jb1.slope_dir}/{jb1.slope_name}_{jb0.pra_size}{jb1.return_period}_mu.tif',
            f'SLOPE_TIF/{jb0.slope_name}/{jb0.slope_name}_{jb0.pra_size}{jb0.return_period}_mu.tif'),

        # ./juneau10000030MFor_5m/RESULTS/juneau100000For_5m/logfiles/muxi_class.tif
    ]

    map = [
        (os.path.join(jb0.ramms_harness, x), os.path.join(scene_dir, y))
        for x,y in map]

    return map

_izip_exts = ['.relp', '.domp', '.xyz', '.xy-coord', '.var', '.rel', '.dom']  # .dom MUST be last
def compress_avalanche_inputs(jb, gridI, ids):
    """Puts all avalanche inputs into a single Zip file."""
#    jb = rammsutil.parse_release_file(release_file)
    jb = jb.copy()
    gridI_pik = pickle.dumps(gridI)
    for id in ids:
        jb.set(id=id)
        base = os.path.join(jb.avalanche_dir, f'{jb.ramms_name}')
        zip_file = f'{base}.in.zip'

        files = [f'{base}{ext}' for ext in _izip_exts]
        arcnames = [f'{jb.ramms_name}{ext}' for ext in _izip_exts]
        arcnames[-1] = f'{jb.ramms_name}.v1.dom'    # First of many .dom files

        if (not os.path.exists(f'{base}.in.zip')) and \
            all(file_is_good(x) for x in files):

            print(f'Compressing {zip_file}')

            # Compress Avalanche intput files into a Zipfile
            with zipfile.ZipFile(
                zip_file, 'w', compression=zipfile.ZIP_DEFLATED) \
                as izip:

                # Write the grid info
                izip.writestr('grid.pik', gridI_pik)

                # Copy files
                for file,arcname in zip(files,arcnames):
                    izip.write(file, arcname=arcname)

                # Write the .av3 files based on the .av2 file
                arcname = f'{jb.ramms_name}.av3'
                av2_file = f'{base}.av2'
                files.append(av2_file)
                with open(av2_file, 'r') as fin:
                    av3_str = av2_to_av3(fin.read())
                izip.writestr(arcname, av3_str)

            # Remove old files
            for file in files:
                os.remove(file)

def striped_chunks(l, n):
    """Yield n number of striped chunks from l."""
    # https://stackoverflow.com/questions/24483182/python-split-list-into-n-chunks
    for i in range(0, n):
        yield l[i::n]
# -----------------------------------------------------------------
def rule(release_file, dem_file, inputs, dry_run=False, submit=False):
    """Runs Stage 1 of RAMMS for one chunk
    (IDL code prepares individual avalanche runs)

    dem_file:
        The name of ANY DEM file pertaining to this chunk.    
        It could be the copy (or symlink) of the DEM file inside the chunk dir.
        Alternately, it can just be the DEM file for the AKRAMMS scene overall.
    release_file:
        Name of a release file for the CHUNK you wish to run

    inputs:
        All input files for the RAMMS run (superset of release_files)
    """

    jb = rammsutil.parse_release_file(release_file)
    #logfile = os.path.join(jb.ramms_dir, 'RESULTS', 'lshm_rock.log')

    # Write extra output files to show we finished stage1 for a particular release file
#    done_output = os.path.join(jb.ramms_dir, 'RESULTS', f'{jb.ramms_name}_stage1.txt')
    done_output = os.path.join(jb.scene_dir, 'stage1', f'{jb.ramms_name}.txt')

    def action(tdir):
        # ---------------------------------------------------------
        # From former rammsdir rule

        # ---------------------------------------------------------

        # Copy files from previous RAMMS Stage 1, to speed things up
        tmap = tiffmap(jb)
        for fname0,fname1 in tmap:
            if (not os.path.exists(fname0)) and os.path.exists(fname1):
                dir0 = os.path.dirname(fname0)
                os.makedirs(dir0, exist_ok=True)
                shutil.copy(fname1, fname0)

        ramms_dir_rel = config.roots.relpath(jb.ramms_dir)
        cmd = ['sh', 
            config.roots_w.join('HARNESS', 'akramms', 'sh', 'run_ramms.sh', bash=True),
            '--ramms-version', config.ramms_version,
            config.roots_w.syspath(ramms_dir_rel, bash=True), '1']    # '1'=stage 1

        # RAMMS Stage 1 accepts inputs on stdin
        # rammsdist.run_on_windows_stage() calls read_inputs()
        dynamic_outputs = list()
        if config.queue_idl:
            dynamic_outputs = harnutil.run_remote_queued(inputs, cmd, tdir, write_inputs=True)
        else:
            dynamic_outputs = harnutil.run_remote(inputs, cmd, tdir, write_inputs=True)

        # Copy .tif files to be reused by later RAMMS Stage 1
        for fname0,fname1 in tmap:
            dir1 = os.path.dirname(fname1)
            os.makedirs(dir1, exist_ok=True)
            if not os.path.exists(fname1):
                shutil.copy(fname0, fname1)

            # Do NOT remove, we will need for Stage 2 (the .exe file).
            # os.remove(fname0)

        # Obtain raster grid and geotransform info
        gridI = gdalutil.read_grid(dem_file)

        # Compress Avalanche inputs, ready for Docker container
        df = shputil.read_df(release_file, read_shapes=False)
        all_ids = list(df['Id'])
        procs = list()
        for ids in striped_chunks(all_ids, config.ncpu_compress):
            proc = multiprocessing.Process(
                target=lambda: compress_avalanche_inputs(jb, gridI, ids))
            proc.start()
            procs.append(proc)
        for proc in procs:
            proc.join()

        # Check final outputs
        missing = list()
        jb1 = jb.copy()
        for id in all_ids:
            jb1.set(id=id)
            base = os.path.join(jb.avalanche_dir, f'{jb1.ramms_name}')
            in_zip = f'{base}.in.zip'
            if not os.path.exists(in_zip):
                missing.append(in_zip)
        if len(missing) > 0:
            for x in missing:
                print('Missing: ', x)
            raise ValueError('Missing avalanche input files')


        # Submit the individual avalanche runs immediately so we can
        # get going while preparing more RAMMS directories.
        if submit:
            joblib.submit_jobs([release_file])

        # Write output files
        os.makedirs(os.path.dirname(done_output), exist_ok=True)
        with open(done_output, 'w') as out:
            out.write('Finished RAMMS Stage 1\n')


        return dynamic_outputs

    return make.Rule(action, inputs, [done_output])


