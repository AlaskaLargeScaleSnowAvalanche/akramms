# Stuff related to using ArcGIS
import os,sys,pickle
import subprocess
import importlib

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
SCRIPT_DIR = os.path.abspath(os.path.join(os.path.abspath(__file__), '..', '..', 'sh', 'arcgis'))

# ------------------------------------------------------------------

class Lambda:
    def __init__(self, module_name, fn_name, *args, **kwargs):
        self.module_name = module_name
        self.fn_name = fn_name
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        mod = importlib.import_module(self.module_name)
        return getattr(mod, self.fn_name)(*self.args, **self.kwargs)

# ---------------------------------------------------
def get_script_vars(namespace, script_vars):
    """Determines the script variables for an ArcGIS script
    script_vars: [(vname, get_param, ...]
        namespace: dict
            Place to store variables returned.
            Typically scripts will use globals()
        vname: Name of variable
        get_param:
            Name of arcpy function used to obtain parameter if running within GUI
            Eg: 'GetParameterAsText'
    """
    ret = dict()
    if len(sys.argv) > 1:
        # ------- We are called from external Python.
        # The (one) command line arg indicates a 

        # Read script variables as Pickle from file specified on command line
        args_pik = sys.argv[1]
        with open(args_pik, 'rb') as fin:
            args = pickle.load(fin)

        # Run any lambdas in the args
        args0 = args
        args = dict()
        for name,val in args0.items():
#            print(type(val), Lambda, val)
            if isinstance(val, Lambda):
                args[name] = val()
            else:
                args[name] = val

        # Copy script variables out of args and into  globals
        _globals = globals()
        for vname,_ in script_vars:
            if vname in args:
                ret[vname] = args[vname]
                del args[vname]
            else:
                # Missing args get coded as empty string for ArcGIS scripts
                ret[vname] = ''

        # Check for extra script vars
        if len(args) > 0:
            raise TypeError("{} got unexpected Pickled arguments: {}".format(
                __file__, list(args.keys())))

    else:
        import arcpy    # Only from ArcGIS Python

        # We are calling from ArcGIS GUI
        for ix,(vname,get_param) in enumerate(script_vars):
            ret[vname] = getattr(arcpy, get_param)(ix)

    # Display script variables
    for vname,val in ret.items():
        namespace[vname] = val
        print("{} = {}".format(vname,val))
    print('-----------------------------------')
    sys.stdout.flush()

# ------------------------------------------------------    
def run_script(script_file, args, cwd=None, dry_run=False):
    """Runs and ArcGIS Python script
    script_file: xxx.py
        Name of script to run.
        Either full pathname, or name in the akramms/sh folder.
    args: dict
        Arguments to pass to the script
    cwd: str
        Directory to run in
    dry_run: bool
        If True, don't ACTUALLY run the script"""

    # Determine actual script file
    if not os.path.exists(script_file):
        file2 = os.path.join(SCRIPT_DIR, script_file)
        if os.path.exists(file2):
            script_file = file2
        else:
            raise ValueError('Cannot locate ArcGIS script: {}'.format(script_file))

#    # Convert all args to string
#    args = {k:str(v) for k,v in args.items()}

    # Write args to Pickle file in the output directory
    args_pik = os.path.join(cwd,
        os.path.splitext(os.path.split(script_file)[1])[0] + '_args.pik')
    with open(args_pik, 'wb') as out:
        pickle.dump(args, out)

    # Run the script using ArcGIS Conda environment
    cmd = [PYTHON_EXE, script_file, args_pik]
    kwargs = {}
    if cwd is not None:
        kwargs['cwd'] = cwd
    env = dict(os.environ.items())
    del env['PYTHONPATH']    # Avoid polluting ArcGIS Python
    print('cwd: {}'.format(cwd))
    print('cmd: {}'.format(' '.join(x for x in cmd)))
    if not dry_run:
        print('============== BEGIN {}'.format(script_file))
        sys.stdout.flush()
        subprocess.run(cmd, check=True, env=env, **kwargs)
        sys.stdout.flush()
        print('============== END {}'.format(script_file))
