import functools,re,os,itertools,pathlib
import importlib
import netCDF4
from akramms import file_info

__all__ = ('parse_args', 'new_combo', 'new_combo_expand_forest')

# =====================================================================
_module_type = type(re)    # Any module will do here
@functools.lru_cache()
def load_expmod(exp_name):
    if isinstance(exp_name, _module_type):
        return exp_name

    try:
        exp_mod = importlib.import_module(exp_name)
    except ModuleNotFoundError:
        try:
            exp_mod = importlib.import_module('akramms.experiment.' + exp_name)
        except ModuleNotFoundError:
            raise ModuleNotFoundError(f'Cannot load module {exp_name} or akramms.experiment.{exp_name}') from None
    return exp_mod

_all_dotsRE = re.compile(r'^([\.]+)$')
def parse_parts(parts, load=False, assume_wcombo=False):
    """
    parts: Eg:
        ['ak', 'ccsm', '1981', '1990', 'lapse', 'For', '30', '.', '.']
        ['ak', 'ccsm', '1981', '1990', 'lapse', 'For', '30', '113', '045']
        ['ak', 'ccsm', '1981', '1990', 'lapse', 'For', '30']
    """

    # Process dashes
    parts = list(itertools.chain(*(part.split('-') for part in parts)))


    # Process dots
    parts2 = list()
    for part in parts:
        if _all_dotsRE.match(part) is not None:    # '.' is a wildcard
            parts2 += [None] * len(part)
        else:
            parts2.append(part)
    parts = parts2

    exp = parts[0]
    ret = {'type': 'parts', 'exp': exp}

    # Remove experiment name
    parts = parts[1:]


    if load:
        # If we have access to the experiment file, we can verify better

        expmod = None
        try:
            expmod = load_expmod(exp)
            ret['expmod'] = expmod

            if len(parts) == len(expmod.combo_keys) - 2:
                # This is a wcombo
                ret['wcombo'] = tuple(parts)
            elif len(parts) == len(expmod.combo_keys):
                # This is a full combo
                ret['wcombo'] = tuple(parts[:-2])
                ret['ijdom'] = tuple(parts[-2:])            

            return ret

        except ModuleNotFoundError:
            pass    # Maybe the Python file for this experiment isn't available

    # We were not able to load the experiment Python module.
    # Do our best without knowing how many combo keys there are.

    # We're told this is a wcombo
    if assume_wcombo:
        ret['wcombo'] = tuple(parts)
        return ret

    # We don't know if this is a wcombo or a combo, try to guess...
    sidom,sjdom = parts[-2:]
    if sidom is None and sjdom is None:
        # User provided placeholder wildcards, this is a wcombo
        ret['wcombo'] = tuple(parts[:-2])
    else:
        # Assume it's a full combo (if we can parse the idom/jdom)
        try:
            idom = int(sidom)
            jdom = int(sjdom)
            ret['wcombo'] = tuple(parts[:-2])
            ret['ijdom'] = (idom,jdom)
        except ValueError:
            # The last two don't look like integers, assume the full thing is a wcombo
            ret['wcombo'] = tuple(parts)

    return ret

# ----------------------------------------------------------------------
_expsetRE = re.compile(r'([^.]*[^-])\.([^-][^.]*)$')
def parse_expset(expset, load=True):
    """A run is a generator inside an experiment that yields a bunch of combos.
    expset: Eg:
        ak.juneau
    """
    match = _expsetRE.match(expset)
    if match is None:
        raise ValueError(f'Not an expset: {expset}')

    exp = match.group(1)
    expset = match.group(2)
    ret = {'type': 'expset', 'exp': exp, 'expset': expset}
    if load:
        ret['expmod'] = load_expmod(exp)
        ret['expset_fn'] = getattr(ret['expmod'], expset)
    return ret


# =====================================================================
#Exp = collections.namedtuple('Exp', ('name',))
def parse_expdir(expdir, load=False):
    """
    expdir:
        Eg: .../ak
    """
    exp = expdir.parts[-1]
    ret = {'expdir': expdir, 'exp': exp}
    if load:
        try:
            ret['expmod'] = load_expmod(exp)
        except ModuleNotFoundError:
            pass    # Maybe the Python file for this experiment isn't available
    ret['type'] = 'expdir'
    return ret
# ----------------------------------------------------------------------
#Trial = collections.namedtuple('Trial'
def parse_trialdir(trialdir):
    """
    trialdir:
        Eg: .../ak/ak-ccsm-1981-1990-lapse-For-30
    Returns:
        wcombo
    """

    # Get the rest of the combo
    parts = trialdir.parts[-1].split('-')
    if len(parts) == 1:
        raise ValueError(f'Not a trialdir: {trialdir}')
    ret = parse_parts(parts, load=False, assume_wcombo=True)
    ret['trialdir'] = trialdir
    ret['type'] = 'trialdir'
    return ret
# ----------------------------------------------------------------------
scenedirRE = re.compile(r'(x|arc)-(\d+)-(\d+)$')
def parse_scenedir(scenedir):
    """
    scenedir: Eg:
        .../ak/ak-ccsm-1981-1990-lapse-For-30/x-113-045
        .../ak/ak-ccsm-1981-1990-lapse-For-30/arc-113-045
    """
    ret = parse_trialdir(scenedir.parents[0])
    ret['scenedir'] = scenedir

    # Get idom, jdom
    match = scenedirRE.match(scenedir.parts[-1])
    if match is None:
        raise ValueError(f'Not a scenedir: {scenedir}')
    ret['scenetype'] = match.group(1)
    ret['ijdom'] = (int(match.group(2)), int(match.group(3)))

    ret['type'] = 'scenedir'
    return ret
# ----------------------------------------------------------------------
_chunk_leafRE = re.compile(r'^c-([TSML])-(\d+)$')
#Chunk = collections.namedtuple('Chunk', ('chunkid', 'pra_size'))
def parse_chunkdir(chunkdir):
    """
    chunkdir:
        Eg: .../ak/ak-ccsm-1981-1990-lapse-For-30/x-113-045/CHUNKS/x-113-0450000230TFor_10m
    """
    if chunkdir.parents[0].parts[-1] != 'CHUNKS':
        raise ValueError(f'Not a chunkdir: {chunkdir}')

    ret = parse_scenedir(chunkdir.parents[1])
    ret['chunkdir'] = chunkdir

    chunk_leaf = chunkdir.parts[-1]    # Eg: x-113-0450000230TFor_10m
    match = _chunk_leafRE.match(chunk_leaf)
    ret['pra_size'] = match.group(1)
    ret['chunkid'] = int(match.group(2))

    ret['type'] = 'chunkdir'
    return ret
# ----------------------------------------------------------------------
def parse_dir(dir):
    try:
        ret = parse_chunkdir(dir)
        ret['dirtype'] = 'chunk'
        return ret
    except ValueError:
        pass

    try:
        ret = parse_scenedir(dir)
        ret['dirtype'] = 'scene'
        return ret
    except ValueError:
        pass

    try:
        ret = parse_trialdir(dir)
        ret['dirtype'] = 'trial'
        return ret
    except ValueError:
        pass

    ret = parse_expdir(dir)
    ret['dirtype'] = 'exp'
    return ret
# =====================================================================

# -------------------------------------------------------
#_releasefileRE = re.compile(r'(.*)([TSML])([_-])rel.shp')
#_releasefile_scenetypes = {'-': 'arc', '_': 'x'}
#def parse_releasefile(releasefile):
#    """Parses names of top-level (non-CHUNK) release files
#    TODO: The format here is wrong, MUST be fixed!
#
#    releasefile: Eg:
#        .../x-113-045/RELEASE/x-113-045For_10m_30L_rel.shp
#        .../x-113-045/CHUNKS/x-113-0450001330MFor_10m/RELEASE/x-113-04500013For_10m_30M_rel.shp
#        .../arc-113-045/RELEASE/ak-ccsm-1981-1990-lapse-For-30-113-045-S-rel.shp
#    """
#
#    raise ValueError("This needs to be fixed to parse CHUNK or non-CHUNK releasefiles.  See use of parsed['chunkid'] in resolve.py/resolve_chunk().  I don't think parsing by individual resleasefiles will be important going forward...")
#
#    match = _releasefileRE.match(releasefile.parts[-1])
#    if match is None:
#        raise ValueError(f'Not a releasefile: {releasefile}')
#
#    ret = {'releasefile': releasefile}
#    try:
#        ret.update(parse_dir(releasefile.parents[1]))    # The directory above RELEASE
#    except ValueError:
#        pass    # Maybe this is a "naked" release file
#    ret['type'] = 'releasefile'
#
#    ret['pra_size'] = match.group(2)
#    scenetype = _releasefile_scenetypes[match.group(3)]
#    ret['scenetype'] = scenetype
#    if scenetype == 'arc':
#        parts = match.group(1).split('-')
#        ret.update(parse_parts(parts, load=True))
#
#    return ret
# -------------------------------------------------------
# NOTE: HELPER FUNCTION.  See also file_info.parse_chunk_release_file
def _parse_chunk_releasefile(releasefile):
    """Parses names of CHUNK-level release files into a dict suitable for making dataframes.

    releasefile: Eg:
        ###.../x-113-045/RELEASE/x-113-045For_10m_30L_rel.shp
        .../x-113-045/CHUNKS/x-113-0450001330MFor_10m/RELEASE/x-113-04500013For_10m_30M_rel.shp
        ###.../arc-113-045/RELEASE/ak-ccsm-1981-1990-lapse-For-30-113-045-S-rel.shp
    """

    jb = file_info.parse_chunk_release_file(releasefile)
    if jb is None:
        raise ValueError(f'Not a releasefile: {releasefile}')

    wparts = releasefile.parts[-6].split('-')
    ijparts = releasefile.parts[-5].split('-')


    ret = {
        'exp': wparts[0],
        'wcombo': tuple(wparts[1:]),
        'ijdom': tuple(ijparts[1:]),
        'type': 'releasefile',
        'releasefile': releasefile,
        'scenetype': 'x',
        'scenedir': jb.scene_dir,
        'chunkid': jb.chunkid,
        'pra_size': jb.pra_size
    }
    return ret

# ----------------------------------------------------------------------
# TODO: Read all info from INSIDE the arcfile, allowing it to be named anything.  We can tell it's an arcfile because it ends in .nc
#_avalRE = re.compile(r'aval-([TSML])-(\d+)')
_avalRE = re.compile(r'^aval-([TSML])-(\d+)-([^-]*).nc$')
def parse_arcfile(arcfile):
    match = _avalRE.match(arcfile.parts[-1])
    if match is None:
        raise ValueError(f'Not an archived avalanche file: {arcfile}')

    pra_size = match.group(1)
    overrun = (match.group(3) == 'overrun')    # Overrun info encoded in name

    with netCDF4.Dataset(arcfile) as nc:
        statusv = nc.variables['status']
        # TODO: Change to exp in the NetCDF file
        exp = statusv.getncattr('exp_mod')

    ret = {
        'exp': exp, 'type': 'arcfile', 'pra_size': pra_size,
        'arcfile': arcfile, 'id': int(match.group(2)),
        'id_status': (file_info.JobStatus.OVERRUN if overrun else file_info.JobStatus.FINISHED) }
    return ret
# ----------------------------------------------------------------------
def parse_file(file):

    """Can specify release files or individual avalanche files (in
    archive form)
    """

    try:
        return _parse_chunk_releasefile(file)
    except ValueError as e:
        pass
    return parse_arcfile(file)
# =============================================================
# ----------------------------------------------------------------------
_exclude_dirs = {'.', '..'}
def parse_args(args, load=True):
    """Parses anything on the command line.  Top-level function"""

    rets = list()    # The things we parsed
    parts = list()    # Accumulate args
    ids = list()

    # --------------------------------
    def flush_parts():    # Parses
        nonlocal rets, parts, ids

        # ----------- Handle main portion (before the single colon)
        if len(parts) == 1:
            try:
                # First try parsing as an expset
                rets.append(parse_expset(parts[0], load=load))
            except ValueError:
                # I guess it's not an expset
                rets.append(parse_parts(parts, load=load))

        elif len(parts) > 1:
            rets.append(parse_parts(parts, load=load))

        parts = list()

        # ----------- Handle IDs
        if len(ids) > 0:
            rets.append(ids)
        ids = list()

    # --------------------------------
    state = 'p'
    for arg in args:
        if arg == '::':    # Separate one parse-thing from the next
            flush_parts()
        else:
            if state == 'p':    # Parsing parts
                if arg == ':':    # Separate parts from avalanche IDs
                    state = 'i'
                    ids.clear()
                elif (os.sep in arg) and os.path.isdir(arg) and (arg != '.') and (arg != '..'):  # If it's '.', it might be an actual directory
                    flush_parts()
                    rets.append(parse_dir(pathlib.Path(arg).resolve()))
                elif os.path.isfile(arg):
                    flush_parts()
                    rets.append(parse_file(pathlib.Path(arg).resolve()))
                else:
                    parts.append(arg)
            elif state == 'i':
                ids.append(int(arg))
                print('Added to ids ', ids)
            else:
                assert False    # Illegal state
#    print('vv1 done loop')
    flush_parts()

    # Now  combine IDs into previous item
    last_dict = None
    rets2 = list()
    for ret in rets:
        if isinstance(ret, dict):    # Query
            last_dict = ret
            rets2.append(ret)
        else:    # Additional IDs
            if 'ids' in last_dict:
                last_dict['ids'] += ret
            else:
                last_dict['ids'] = ret
    return rets2
# -----------------------------------------------------------
def new_combo(expmod, scombo):
    """Given individual parts of Combo as strings, creates a fully
    typed Combo object."""
    dcombo = {key:val for key,val in zip(expmod.combo_keys, scombo)}
    return expmod.Combo(**expmod.combo_schema.validate(dcombo))
# -----------------------------------------------------------
def new_combos_expand_forest(expmod, scombo):
    """Similar to new_combo(), but returns multiple combos, expanding with forest=None as a wildcard.
    Returns: [Combo, ...]
    """

    dcombo = {key:val for key,val in zip(expmod.combo_keys, scombo)}
    if dcombo.get('forest', '') is None:
        combos = list()
        for forest in ('For', 'NoFor'):
            dcombo['forest'] = forest
            combos.append(expmod.Combo(**expmod.combo_schema.validate(dcombo)))
        return combos
    else:
        # No wildcard
        return [expmod.Combo(**expmod.combo_schema.validate(dcombo))]

# -----------------------------------------------------------
#def main():
#    import sys
#    rets = parse_args(sys.argv[1:], load=True)
#    for ret in rets:
#        print('-------------------------------')
#        for k,v in ret.items():
#            print(f'{k}: {v}')
#
#main()
# ==============================================================

_extent_strings = {'tile', 'aval'}
def parse_extent(expmod, sextent):
    """
    sextent:
        Extent designator from command line
    Returns:
        (x0,y0,x1,y1)
            or
        'tile': Use the extent of an (idom,jdom) subdomain tile
            or
        'dynamic': Use extent determined by the avalanches
    """

    # See if it's a special string
    if sextent is None:
        return 'aval'

    if sextent in _extent_strings:
        return sextent

    # See if it's a named extent
    try:
        return expmod.extents[sextent]
    except KeyError:
        pass

    # Try to parse a numeric extent (x0,y0,x1,y1)
    parts = [x.strip() for x in sextent.split(',')]
    if parts != 4:
        raise ValueError(f"Numeric extent requires four values x0,y0,x1,y1: {sextent}")
    return tuple(float(x) for x in parts)

# ------------------------------------------------------------------
