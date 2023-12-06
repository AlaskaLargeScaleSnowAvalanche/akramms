# Fundamental stuff needed to run an experiment.

import functools
import re,os,collections,importlib
from uafgi.util import shputil
from akramms import config


out_zipRE = re.compile(r'[^_]+_[^_]+_(\d+[TSML])_(\d+)\.out\.zip$')
avalRE = re.compile(r'aval-([TSML])-(d+)\.nc')
scene_dirRE = re.compile(r'(x|arc)-(\d+)-(\d+)$')
intRE = re.compile(r'\s*(\d+)\s*')
# -----------------------------------------------------
def load(ename):
    """Loads the module of an experiment based on its name."""

    try:
        exp_mod = importlib.import_module(ename)
    except ModuleNotFoundError:
        try:
            exp_mod = importlib.import_module('akramms.experiment.' + ename)
        except ModuleNotFoundError:
            raise ModuleNotFoundError(f'Cannot load module {ename} or akramms.experiment.{ename}')# from None
    return exp_mod

# -------------------------------------------------------

# -------------------------------------------------------
def combo_to_scene_dir(exp_mod, combo, type='x'):
    """Returns the full pathname for a RAMMS scene, based on its experiment and combo"""
    return os.path.join(config.roots['PRJ'], exp_mod.name,
        exp_mod.combo_to_scene_subdir(combo, type=type))
# -------------------------------------------------------
@functools.lru_cache()
def _release_df(scene_dir):
    # Look in RELEASE-dir shapefiles to determine theoretical set Avalanche IDs
    # (By looking here, we avoid picking up random junk)
    for leaf in os.listdir(os.path.join(scene_dir, 'RELEASE')):
        match = _relRE.match(leaf)
        if match is not None:
            fname = os.path.join(scene_dir, 'RELEASE', leaf)
            df = shputil.read_df(
                fname, read_shapes=False)
            df = df.set_index('Id')
            return fname,df    # There will be only one

    return None

_relRE = re.compile(r'^(.*)_rel\.shp$')
def release_df(exp_mod, combo, type=None):
    """Read the RELEASE files to determine which avalanche IDs are
    involved in a combo.

    type:  'x' or 'arc'.
           None means read release files from either one, don't care.
    Returns:
        Datframe from the RELEASE file.
        Index is Id
    """

    # Determine whether we look at original, archived or both
    if type is None:
        types = ['x','arc']
    else:
        types = [type]

    for type in types:
        scene_dir = combo_to_scene_dir(exp_mod, combo, type=type)
        ret = _release_df(scene_dir)
        if ret is not None:
            return ret

    raise ValueError(f'No RELEASE file found for combo: {combo}')
# ----------------------------------------------------------
