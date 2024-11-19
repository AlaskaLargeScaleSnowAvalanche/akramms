import subprocess
import os,pathlib,shutil
import netCDF4
import numpy as np
from akramms import config
from akramms.util import paramutil,rqutil,harnutil,arcgisutil
from uafgi.util import make
from akramms import process_tree,params

__all__ = ('rule',)

# ---------------------------------------------------------------------------
def _subprocess_run(msg, *args, **kwargs):
    print(msg)
    subprocess.run(*args, **kwargs)


_dia_cmd_engine_usage = """
Usage: 
- analyze image file:  
    DIACmdEngine image=path1 [image=pathN..] [thematic=pathN] ruleset=path [options]
- analyze image imported using connector:   
    DIACmdEngine image-dir=path import-connector=name [import-connector-file=path] [image=extra_image_pathN] [thematic=extra_thematic_pathN] ruleset=path [options]
- analyze existing project (.dpr):  
    DIACmdEngine dpr=path1 ruleset=path [options]
- analyze image imported using scene file list (multiple scenes within single run):   
    DIACmdEngine image-dir=path scene-xml=path ruleset=path [options]
- resave ruleset to force usage of latest algorithm versions:   
    DIACmdEngine --update-ruleset input_ruleset_path output_ruleset_path

- where:
    image=path                 - path to raster or point cloud data file (.tif, .asc, ...). 
    thematic=path              - path to thematic data file (.shp, gdb, ...). 
    ruleset=path               - path to rule set file (.dcp). 
    import-dir=path            - root directory for image/thematic data files. 
    import-connector=name      - name of the predefined import connector or custom import connector (.xml). 
    import-connector-file=path - path to .xml file containing customized import connector. 
    dpr=path                   - path to .dpr file to be used as analysis input. 


- options:
    param:nameN=valueN     - parameter to the rule set, where nameN is name of scene variable and 
                         valueN is the value of the scene variable. There can be arbitrary amount of params.
    array-param:nameN=value1,value2,..,valueN - array parameter to the rule set, where nameN is name of rule set array and 
                         valueN is the comma-separated value list, for example: array-param:myArray=0,90,180,270. There can be arbitrary amount of array-params.
    --map path1=path2        - local drive - network path mapping
    --output-dir=path      - output diretory for export files
    --license-token=json   - additional license information in json format
    --save-dpr[-min][=path/to/project.dpr] - save project file (without rule set if '--save-dpr-min') 
                         If explicit path to .dpr specified, 
                         it will be used instead default path ({:Workspc.OutputRoot}\dpr\{:Project.Name}.v{:Project.Ver}.dpr) 
    --log-file=path        - log file path (if not specified, default log file is written based on path in eCognition.cfg)
    --pause                - pause application after done
"""

def rule(scene_dir, scene_args, inputs, return_period, For):
    """inputs:
        Outputs of r_prepare.rule()
    """

#    scene_args = params.load(scene_dir)
#    inputs = _prepare_data_outputs(scene_dir, scene_args)

    # Systematically generate list of output files
    rp = return_period
    rpcat = process_tree.return_period_category(rp)
    _For = '_'+For
#    _For = '_For' if forest else '_NoFor'
    outputs = list()
    for ext in ('.dbf', '.prj', '.shp', '.shx'):
        outputs.append(os.path.join(scene_dir, f'PRA_{rpcat}', f'PRA_{rp}y{ext}'))

#    for rp in process_tree.return_periods:    # [10,30,100,300]
#        rpcat = process_tree.return_period_category[rp]
#        for _For in ('_For', '_NoFor'):
#            for ext in ('.dbf', '.prj', '.shp', '.shx'):
#                outputs.append(os.path.join(scene_dir, f'PRA_{rpcat}', f'PRA_{rp}y{_For}{ext}'))

    def action(tdir):
        import os
        import pyproj

        # Base Docker command
        cmd = ['docker', 'run', '--rm', '--network', 'host']

        # Tell eCognition to make more output.
        cmd += ['-e', 'ECOG_CONFIG_logging=trace level=Detailed']

        # eCognition licensing
        cmd += ['-e', 'LM_LICENSE_FILE=27000@10.10.129.211']

        # Mount paths inside eCognition container
        cmd += ['-v', f'{scene_dir}:/mnt']

        # Write files to that mount with the currect user and group ID
        # https://stackoverflow.com/questions/20894086/in-docker-writing-file-to-mounted-file-system-as-non-root
        # NOTE: To affect umask, the Docker container will have to be adjusted.
        # https://widerin.net/blog/change-umask-in-docker-containers/
        cmd += ['-u', '{}:{}'.format(os.getuid(), os.getgid())]


        # Docker container and command to run
        cmd += ['ecognition/linux_cle:10.2.0', './DIACmdEngine']

        # Arguments to DIACmdEnginer (see _dia_cmd_engine_usage above)
        # ----------

        # Import Connect to images in <scene_dir>/eCog
        cmd += ['image-dir=/mnt/eCog', f'import-connector=PRA_import_{rpcat}', f'import-connector-file=/mnt/eCog/PRA_import_{rpcat}.xml']

        # Add the appropriate ruleset
        cmd += [f'ruleset=/mnt/eCog/GHK_{return_period:d}y.dcp']

        # Place for output
        # eCognition writes out files with problems in the projection.
        # In a later rule we will copy them out of the eCog/ directory and
        # fix that.  The polygon files are small...
        odir = os.path.join(scene_dir, f'PRA_{rpcat}')
        os.makedirs(odir, exist_ok=True)
        cmd += [f'--output-dir=/mnt/PRA_{rpcat}']

        # See if there's anything to see in a log file
        # unfortunately not much.
        cmd += [f'--log-file=/mnt/eCog/GHK_{return_period:d}y.log']

        # Run eCognition (in Docker container)!
        print(' '.join(cmd))
        msg = f'---------- Running eCog for {scene_dir}'

        # NOTE: If this fails, check that the TIF files has correct
        # data types, they cannot all be Float64.
        harnutil.run_queued('ecognition',
            _subprocess_run, msg, cmd, check=True)
#        with rqutil.blocking_lock('ecognition'):
#            subprocess.run(cmd, check=True)

        # ---------------------------------------
        # eCognition writes out shapefiles with wrong projection.  Fix that
        # by overwriting with the right projection

        # Read correct projection and convert to WKT format (if it is not already)
        wkt = pyproj.CRS(scene_args['coordinate_system']).to_wkt()

        # Replace original projection from eCognition with that WKT string
        prjs = [out for out in outputs if out.endswith('.prj')]
        for prj in prjs:
            os.rename(prj, f'{prj}.orig')
            with open(prj, 'w') as out:
                out.write(wkt)

    return make.Rule(action, inputs, outputs)
