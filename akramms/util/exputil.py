# Fundamental stuff needed to run an experiment.

import re,os,collections,importlib
from akramms import config


out_zipRE = re.compile(r'[^_]+_[^_]+_(\d+[TSML])_(\d+)\.out\.zip$')
avalRE = re.compile(r'aval-([TSML])-(d+)\.nc')
scene_dirRE = re.compile(r'.*/(x|arc)-(\d+)-(\d+)$')
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
    svals = zip(exp_mod.combo_schema.keys(), scombo)
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

    match = scene_dirRE.match(arg)
    if match is None:
        #raise ValueError(f'Directory {arg} must contain an original or archived RAMMS run!')
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))
# -------------------------------------------------------
avaltuple = collections.namedtuple('AvalTuple', ('exp_mod', 'combo', 'id'))


def parse_avals(args):
    """
    1. Filename of existing arc-file: keep
    2. Filename of x-file: determine arc-dir, convert to arc-file
    3. experiment directory + combo: list all x- and arc-, then filter further
    Returns: [(exp_mod, combo, id, arc_fname), ...]
        (Some of these may be None)
    """

    rets = list()
    cur_tuple = list()    # Current items for a combo
    state = 0    # 0=initial; 1=expectign combo items; 2=expecting id
    exp_mod = None    # Most recently parsed experiment
    scombo = list()
    ids = list()

    def clear():
        exp_mod = None
        scombo = list()
        ids = list()
        state = 0

    for arg in args:
        if state == 3:
            # Accumulate avalanche IDs
            match = intRE.match(arg)
            if match is not None:
                ids.append(int(match.group(1)))
                continue

            # We are done accumulating Avalanche IDs...
            # Emit item from previous step
            rets.append( (AvalTuple(exp_mod, combo, ids), None) )
            clear()
            state = 0

        if state == 0:
            print('xxxxxxxxxx ', args)
            if os.path.isfile(arg):
                # Full pathname contains info on exp_mod, combo and id...

                # ----------- See if it's a .out.zip or a .nc file
                scene_type, idom, jdom = parse_scene_dir(os.path.basename(arg))
                if scene_type == 'x':
                    pieces = arg.rsplit(os.sep, 8)[1:2]
                    combo_dir = pieces[1]    # ak-ccsm-...
                    x_dir = pieces[2]
                    out_zip = pieces[-1]

                    exp_mod,combo = parse_combo_dir(combo_dir, idom, jdom)

                    # Obtain ID from .out.zip
                    match = out_zipRE.match(out_zip)
                    id =int(match.group(2))

                    rets.append( (AvalTuple(exp_mod, combo, [id]), None) )
                    clear()
                    continue

                if leaf.startswith('aval-'):
                    rets.append( (None, os.path.abspath(arg)) )
                    clear()
                    continue

                raise ValueError('Cannot parse information from file: {arg}')

            if os.path.isdir(arg):
                # ------------ See if it's a scene_dir (x-... or arc-...)
                pieces = arg.rsplit(os.sep, 2)
                combo_dir = pieces[1]
                scene_dir = pieces[2]
                xret = parse_scene_dir(scene_dir)
                if xret is not None:
                    # Parse as a scene_dir was successful
                    scene_type, idom, jdom = xret
                    exp_mod,combo = parse_combo_dir(combo_dir, idom, jdom)

                exp_mod,combo = parse_combo_dir(combo_dir, idom, jdom)
                state = 3    # Looking for avalanche ID...
                continue
            else:
                # Not a file or directory, just build up combo splitting on -
                pieces = arg.split('-')
                exp_mod = load(pieces[0])    # The first item better be the experiment
                scombo = pieces[1:]
                state = 1    # not yet full scombo
                continue

        if state == 1:
            # Build up scombo piece by piece
            pieces = arg.split('-')
            if exp_mod is None:
                exp_mod = load(pieces[0])    # The first item better be the experiment
                scombo += pieces[1:]    # The rest, if any, go to the scombo
            else:
                scombo = pieces

            # See if we're ready to make a Combo
            if len(scombo) == len(exp_mod.schema.schema):
                combo = parse_combo(exp_mod, scombo)
                state = 3
                continue    # Get more to consume

    return rets

# -------------------------------------------------------
def combo_to_scene_dir(exp_mod, combo, type='x'):
    """Returns the full pathname for a RAMMS scene, based on its experiment and combo"""
    return os.path.join(config.roots['PRJ'], exp_mod.name,
        exp_mod.combo_to_scene_subdir(combo, type=type))

def main():
    import sys
    for aval in parse_avals(sys.argv[1:]):
        print(aval)
main()
 

