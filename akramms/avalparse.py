# Fundamental stuff needed to run an experiment.

import re,os,collections,importlib
from akramms import config

"""Parse specifications from the user (on the command line) into a
list of either AvalTuple objects or names of archived avalanches."""


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
def parse_combo(exp_mod, scombo):
    """Parses strings into appropriate types and returns the Combo tuple."""
    svals = dict(zip(exp_mod.combo_schema.schema.keys(), scombo))
    vals = exp_mod.combo_schema.validate(svals)
    return exp_mod.Combo(**vals)

# -------------------------------------------------------
def parse_combo_dir(combo_dir, idom, jdom):

    # Obtain experiment name
    pieces = combo_dir.split('-')
    exp_mod = load(pieces[0])
    scombo = pieces[1:] + [idom, jdom]
    combo = parse_combo(exp_mod, scombo)

    return exp_mod, combo
# -------------------------------------------------------
def parse_scene_dir(scene_dir):
    """
    scene_dir:  x-000-000 or arc-000-000
    Returns: (type, idom, jdom)
    """

    match = scene_dirRE.match(scene_dir)
    if match is None:
        #raise ValueError(f'Directory {arg} must contain an original or archived RAMMS run!')
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))
# -------------------------------------------------------
# Modeled after ArcGIS Extent:
#    https://desktop.arcgis.com/en/arcmap/latest/tools/spatial-analyst-toolbox/extract-by-rectangle.htm
Extent = collections.namedtuple('Extent', ('x0','y0','x1','y1'))

def parse_id(exp_mod, sids):
    """Returns either a signal Avalanche ID, or a query Extent (region)"""

    # Try the wildcard
    if sids == '.':
        return None    # Wildcard on avalanche IDs

    # Try just a plain int
    try:
        return int(sids)
    except ValueError:
        pass

    # Try a named extent
    try:
        return Extent(*exp_mod.extents[sids])
    except KeyError:
        pass

    # Try parsing the extent (comma-separated)
    return Extent(*(float(x) for x in sids.split(',')))

# -------------------------------------------------------
all_dotsRE = re.compile(r'^([\.]+)$')
def replace_wildcards(pieces):
    ret = list()
    for piece in pieces:
        if all_dotsRE.match(piece) is not None:
            ret += [None]*len(piece)
        else:
            ret.append(piece)
    return ret
# -------------------------------------------------------
AvalTuple = collections.namedtuple('AvalTuple', ('exp_mod', 'combo', 'ids', 'extents'))


def parse_aval_specs(args):
    """
    1. Filename of existing arc-file: keep
    2. Filename of x-file: determine arc-dir, convert to arc-file
    3. experiment directory + combo: list all x- and arc-, then filter further
    Returns: [(exp_mod, combo, id, arc_fname), ...]
        (Some of these may be None)
    """

    aspecs = list()    # return val
    nc_fnames = list()    # return val
    cur_tuple = list()    # Current items for a combo

    state = 0    # 0=initial; 1=expectign combo items; 2=expecting id
    exp_mod = None    # Most recently parsed experiment
    scombo = list()
    ids = list()
    extents = list()
    def clear():
        state = 0
        exp_mod = None
        scombo = list()
        ids = list()

    for arg in args:
        if state == 3:
            try:
                id_or_extent = parse_id(exp_mod, arg)
                if isinstance(id_or_extent, Extent):
                    extents.append(id_or_extent)
                else:
                    ids.append()
                continue
            except:
                # It's not a parseable ID or extent, reinterpret arg in state 0
                aspecs.append( AvalTuple(exp_mod, combo, ids) )
                state = 0

        if state == 0:
            # Remove trailing slash
            if arg[-1] == os.sep:
                arg = arg[:-1]

            if os.path.isfile(arg):
                # Full pathname contains info on exp_mod, combo and id...

                # ----------- See if it's a .out.zip or a .nc file
                #scene_type, idom, jdom = parse_scene_dir(os.path.basename(arg))
                #if scene_type == 'x':

                leaf = os.path.basename(arg)
                if leaf.startswith('x-'):
                    pieces = arg.rsplit(os.sep, 8)
                    combo_dir = pieces[1]    # ak-ccsm-...
                    x_dir = pieces[2]
                    out_zip = pieces[-1]

                    scene_type,idom,jdom = parse_scene_dir(x_dir)
                    exp_mod,combo = parse_combo_dir(combo_dir, idom, jdom)

                    # Obtain ID from .out.zip
                    match = out_zipRE.match(out_zip)
                    id =int(match.group(2))

                    aspecs.append( AvalTuple(exp_mod, combo, id) )
                    clear()
                    continue

                if leaf.startswith('aval-'):
                    nc_fnames.append( os.path.abspath(arg) )
                    clear()
                    continue

                raise ValueError('Cannot parse information from file: {arg}')

            if os.path.isdir(arg) and (all_dotsRE.match(arg) is None):    # '.' is a wildcard

                # ------------ See if it's a scene_dir (x-... or arc-...)
                pieces = arg.rsplit(os.sep, 2)

                # Try as if if we have <combo-dir>/<scene-dir>
                xret = parse_scene_dir(pieces[2])
                if xret is not None:
                    scene_type, idom, jdom = xret
                    exp_mod,combo = parse_combo_dir(pieces[1], idom, jdom)
                    state = 3    # Looking for avalanche IDs
                    continue

                # That didn't work, so we just have <combo-dir>, which isn't a full combo yet
                pieces2 = replace_wildcards(pieces[2].split('-'))
                exp_mod = load(pieces2[0])
                scombo = pieces2[1:]
                state = 1    # Looking for more on scombo
                continue
            else:
                # Not a file or directory, just build up combo splitting on -
                pieces = arg.split('-')
                pieces = replace_wildcards(pieces)
                exp_mod = load(pieces[0])    # The first item better be the experiment
                scombo = pieces[1:]
                if len(scombo) == len(exp_mod.combo_schema.schema):
                    combo = parse_combo(exp_mod, scombo)
                    state = 3
                else:
                    state = 1    # not yet full scombo
                continue

        if state == 1:
            # Build up scombo piece by piece
            pieces = arg.split('-')
            pieces = replace_wildcards(pieces)
            if exp_mod is None:
                exp_mod = load(pieces[0])    # The first item better be the experiment
                scombo += pieces[1:]    # The rest, if any, go to the scombo
            else:
                scombo += pieces

            # See if we're ready to make a Combo
            if len(scombo) == len(exp_mod.combo_schema.schema):
                combo = parse_combo(exp_mod, scombo)
                state = 3
                continue    # Get more to consume

    # Finish up after we exit
    if state == 3:    # Looking for ID...
        # Emit any remaining ids (or floating point numbers) at end of parsing
        aspecs.append( AvalTuple(exp_mod, combo, ids) )
    elif state == 1:    # Looking for more of the combo...
        missing_len = len(exp_mod.combo_schema.schema) - len(scombo)
        if missing_len == 2:
            scombo += [None] * missing_len    # Wildcard for idom / jdom
        else:
            raise ValueError('Must specify full combo (except for idom / jdom)')

        combo = parse_combo(exp_mod, scombo)
        aspecs.append( AvalTuple(exp_mod, combo, [], extents) )

    return aspecs, nc_fnames

# -------------------------------------------------------
