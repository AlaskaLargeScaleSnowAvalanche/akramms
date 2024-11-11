# Fundamental stuff needed to run an experiment.

import functools,glob
import re,os,collections,importlib
import pandas as pd
from uafgi.util import shputil
from akramms import config
from akramms.util import rammsutil


out_zipRE = re.compile(r'[^_]+_[^_]+_(\d+[TSML])_(\d+)\.out\.zip$')
avalRE = re.compile(r'aval-([TSML])-(d+)\.nc')
scene_dirRE = re.compile(r'(x|arc)-(\d+)-(\d+)$')
intRE = re.compile(r'\s*(\d+)\s*')
# -----------------------------------------------------
# -------------------------------------------------------
def combo_to_scene_dirs(exp_mod, combo, type='x'):
    """Returns the full pathname for a RAMMS scene, based on its experiment and combo"""
    if type is None:
        types = ['x','arc']
    else:
        types = [type]

    for type in types:
        yield exp_mod.combo_to_scene_dir(combo, type=type)
# -------------------------------------------------------
_relRE = re.compile(r'^(.*)_rel\.shp$')
def _release_files(scene_dir):
    for leaf in os.listdir(os.path.join(scene_dir, 'RELEASE')):
        match = _relRE.match(leaf)
        if match is not None:
            fname = os.path.join(scene_dir, 'RELEASE', leaf)
            yield fname

def release_files(exp_mod, combo, type=None):
    """Lists release files by combo."""
    scene_dir = exp_mod.combo_to_scene_dir(combo, type='x')
    for x in _release_files(scene_dir):
        yield x
# ----------------------------------------------------------
@functools.lru_cache()
def _release_df(scene_dir):
    """Returns:
        release_fname, df
    """
    # Look in RELEASE-dir shapefiles to determine theoretical set Avalanche IDs
    # (By looking here, we avoid picking up random junk)
    rfs = list()
    dfs = list()
    for fname in _release_files(scene_dir):
        #jb = rammsutil.parse_release_file(fname)
        df = shputil.read_df_noshapes(fname, read_shapes=False)
        if not ('pra_size' in df):
            pra_size = fname[-9]    # Ends in X_rel.shp
            df['pra_size'] = pra_size
        dfs.append(df)
        rfs.append(fname)

    if len(dfs) > 0:
        return rfs, pd.concat(dfs).set_index('Id')
    else:
        return None
# ----------------------------------------------------------------
def release_df(exp_mod, combo, type=None):
    """Read the CHUNKS/RELEASE files to determine which avalanche IDs are
    involved in a combo.

    type:  'x' or 'arc'.
           None means read release files from either one, don't care.
    Returns: release_files, release_df
        release_files: [fname, ...]
            List of release files
        release_df: df
            Concatenated Dataframe of all release files
    """

    # Determine whether we look at original, archived or both
    for scene_dir in combo_to_scene_dirs(exp_mod, combo, type=type):
        ret = _release_df(scene_dir)
        if ret is not None:
            return ret

    raise ValueError(f'No RELEASE file found for combo: {combo}')
# ----------------------------------------------------------
out_zipRE = re.compile(r'[^_]+_[^_]+_\d+([TSML])_(\d+)\.out\.zip$')
def out_zips(exp_mod, combo):
    """
    Returns: [(out_zip_filename, sizecat), ...]
    """

    x_dir = exp_mod.combo_to_scene_dir(combo, type='x')
    out_zips = dict()    
    for out_zip in glob.iglob(os.path.join(x_dir, 'CHUNKS', '*', '*', '*', '*', '*.out.zip')):
        match = out_zipRE.match(os.path.basename(out_zip))
        sizecat = match.group(1)
        id = int(match.group(2))
        out_zips[id] = (out_zip, sizecat)    # full-pathname, sizecat
    return out_zips

avalRE = re.compile(r'aval-([TSML])-(\d+)\.nc')
def archive_ncs(exp_mod, combo):
    arc_dir = exp_mod.combo_to_scene_dir(combo, type='arc')
    ncs = dict()
    if os.path.isdir(arc_dir):
        for name in os.listdir(arc_dir):
            match = avalRE.match(name)
            if match is not None:
                ncs[int(match.group(2))] = (name, match.group(1))    # leaf-name, sizecat
# ---------------------------------------------------------------
sfilterRE = re.compile(r'^\s*([^()\s]+)(\(([^)]*)\))?\s*$')
def parse_filter(sfilter, default_module):
    match = sfilterRE.match(sfilter)
    sfn = match.group(1)
    sargs = match.group(3)    # Excludes parentheses

    # Get the filter function
    parts = sfn.rsplit('.',1)
    if len(parts) == 1:
        # No module included; use avalfilter
        #mod = this_module
        mod = importlib.import_module(default_module)
        filter_fn = getattr(mod, sfn)
    else:
        # A module was included; use it
        mod = importlib.import_module('.'.join(parts[:-1]))
        filter_fn = getattr(mod, parts[-1])

    # See if arguments were provided.
    if sargs is None:
        # No parentheses or arguments provided: the provided filter_fn
        # is the final filter_in_fn to be used by archive.fetch().
        return filter_fn
    else:
        # Arguments were provided: Run the provided filter_fn to
        # generate the final filter.
        args = eval(f'[{sargs}]')
        return filter_fn(*args)
