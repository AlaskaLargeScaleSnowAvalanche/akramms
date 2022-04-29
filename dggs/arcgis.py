# Stuff related to using ArcGIS
import os,sys,json
import subprocess

# ------------------------------------------------------------------
# Paths to the ArcGIS installation.
# In general, ArcGIS Python scripts will be run using subprocess, thereby
# providing independence between ArcGIS Python and the rest of the codebase.

# Root of ArcGIS installation; will normally be the same.
ROOT = os.environ.get('ARCGIS_ROOT', r'C:\Program Files\ArcGIS')

# Root of ArcGIS Conda Environment
CONDA_ENV = os.path.join(ROOT, 'Pro', 'bin', 'Python', 'envs', 'arcgispro-py3')

# Raw Python executable; should "just work" without any fiddling because
# DLLs are in the same directory
PYTHON_EXE = os.path.join(CONDA_ENV, 'python.exe')

# Windows batch script used in place of `python.exe`.  This scripts
# loads the appropriate Conda environment before running Python.
# This is the "official" sanctioned way to run.
PROPY_BAT = os.path.join(ROOT, 'Pro', 'bin', 'Python', 'Scripts', 'propy.bat')

# Where ArcGIS scripts are stored in the akramms code tree
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.abspath(__file__), '..', '..'))

# ------------------------------------------------------------------


# ---------------------------------------------------
def get_script_vars(script_vars, set_globals=True):
    """Determines the script variables for an ArcGIS script
    script_vars: [(vname, get_param, ...]
        vname: Name of variable
        get_param:
            Name of arcpy function used to obtain parameter if running within GUI
            Eg: 'GetParameterAsText'
    """
    ret = dict()
    if len(sys.argv) > 1:
        # ------- We are called from external Python.
        # The (one) command line arg indicates a 

        # Read script variables as JSON from file specified on command line
        args_json = sys.argv[1]
        with open(args_json, 'r') as fin:
            args = json.load(fin)

        # Copy script variables out of args and into 
        _globals = globals()
        for vname,_ in SCRIPT_VARS:
            ret[vname] = args[vname]
            del args[vname]

        # Check for extra script vars
        if len(args) > 0:
            raise TypeError("{} got unexpected JSON arguments: {}".format(
                __file__, list(args.keys())))

    else:
        import arcpy    # Only from ArcGIS Python

        # We are calling from ArcGIS GUI
        for ix,(vname,get_param) in enumerate(script_vars):
            ret[vname] = getattr(arcpy, get_param)(ix)


    if set_globals:
        _globals = globals()
        for vname,val in ret.items():
            _globals[vname] = val

    print(ret)
    return ret
# ------------------------------------------------------    
def run_script(script_file, args, cwd=None):
    """Runs and ArcGIS Python script
    script_file: xxx.py
        Name of script to run.
        Either full pathname, or name in the akramms/sh folder.
    args: dict
        Arguments to pass to the script
    cwd: str
        Directory to run in"""

    # Determine actual script file
    if not os.path.exists(script_file):
        file2 = os.path.join(SCRIPT_DIR, script_file)
        if os.path.exists(file2):
            script_file = file2
        else:
            raise ValueError('Cannot locate ArcGIS script: {}'.format(script_file))

    # Convert all args to string
    args = {k:str(v) for k,v in args.items()}

    # Write args to JSON file in the output directory
    args_json = os.path.splitext(script_file)[0] + '_args.json'
    with open(args_json, 'w') as out:
        json.dump(args, out)

    # Run the script using ArcGIS Conda environment
    cmd = [PYTHON_EXE, script_file, args_json]
    kwargs = {}
    if cwd is not None:
        kwargs['cwd'] = cwd
    env = dict(os.environ.items())
    del env['PYTHONPATH']    # Avoid polluting ArcGIS Python
    subprocess.run(cmd, check=True, env=env, **kwargs)
