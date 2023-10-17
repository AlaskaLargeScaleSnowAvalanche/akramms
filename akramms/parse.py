import functools,re,os,itertools
import importlib


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
    print('xxxxxxx ', parts)

    exp = parts[0]
    ret = {'exp': exp}

    # Remove experiment name
    parts = parts[1:]


    if load:
        # If we have access to the experiment file, we can verify better

        expmod = None
        try:
            print('AA1')
            expmod = load_expmod(exp)
            print('AA2')
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
_expsetRE = re.compile(r'([^.]+)\.([^.]+)$')
def parse_expset(expset, load=True):
    """A run is a generator inside an experiment that yields a bunch of combos.
    expset: Eg:
        ak.juneau
    """
    match = _expsetRE.match(expset)
    if match is None:
        raise ValueError(f'Not an expset: {expset}')

    ret = {'exp': match.group(1), 'expset': match.group(2)}
    if load:
        try:
            ret['expmod'] = load_expmod(exp)
        except ModuleNotFoundError:
            pass    # Maybe the Python file for this experiment isn't available

        ret['expset_fn'] = getattr(ret['expmod'], ret['expset'])
    return ret


# =====================================================================
#Exp = collections.namedtuple('Exp', ('name',))
def parse_expdir(expdir, load=False):
    """
    expdir:
        Eg: .../ak
    """
    exp = parts[-1]
    ret = {'expdir': expdir, 'exp': exp}
    if load:
        try:
            ret['expmod'] = load_expmod(exp)
        except ModuleNotFoundError:
            pass    # Maybe the Python file for this experiment isn't available
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
# ----------------------------------------------------------------------
_scenedirRE = re.compile(r'(x|arc)-(\d+)-(\d+)$')
def parse_scenedir(scenedir):
    """
    scenedir: Eg:
        .../ak/ak-ccsm-1981-1990-lapse-For-30/x-113-045
        .../ak/ak-ccsm-1981-1990-lapse-For-30/arc-113-045
    """
    ret = parse_trialdir(scenedir.parents[0])
    ret['scenedir'] = scenedir

    # Get idom, jdom
    match = _scenedirRE.match(scenedir.parts[-1])
    if match is None:
        raise ValueError(f'Not a scenedir: {scenedir}')
    ret['scenetype'] = match.group(1)
    ret['ijdom'] = (int(match.group(2)), int(match.group(3)))

    return ret
# ----------------------------------------------------------------------
_chunk_subleafRE = re.compile(r'(\d+)([TSML])(For|NoFor)_(\d+)m')
#Chunk = collections.namedtuple('Chunk', ('ichunk', 'sizecat'))
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
    x_leaf = chunkdir.parents[1].parts[-1]    # Eg: x-113-045
    chunk_subleaf = chunk_leaf[len(x_leaf):]    # Eg: 0000230TFor_10m
    match = _chunk_subleafRE.match(chunk_subleaf)
    ret['ichunk'] = int(match.group(1))
    ret['sizecat'] = match.group(2)

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
_releasefileRE = re.compile(r'(.*)([TSML])([_-])rel.shp')
_releasefile_scenetypes = {'-': 'arc', '_': 'x'}
def parse_releasefile(releasefile):
    """releasefile: Eg:
        .../x-113-045/RELEASE/x-113-045For_10m_30L_rel.shp
        .../x-113-045/CHUNKS/x-113-0450001330MFor_10m/RELEASE/x-113-04500013For_10m_30M_rel.shp
        .../arc-113-045/RELEASE/ak-ccsm-1981-1990-lapse-For-30-113-045-S-rel.shp
    """

    match = _releasefileRE.match(releasefile.parts[-1])
    if match is None:
        raise ValueError(f'Not a releasefile: {releasefile}')

    ret = {'releasefile': releasefile}
    try:
        ret.update(parse_dir(releasefile.parents[1]))    # The directory above RELEASE
    except ValueError:
        pass    # Maybe this is a "naked" release file

    ret['sizecat'] = match.group(2)
    scenetype = _releasefile_scenetypes[match.group(3)]
    ret['scenetype'] = scenetype
    if scenetype == 'arc':
        parts = match.group(1).split('-')
        ret.update(parse_parts(parts, load=True))

    return parts
# ----------------------------------------------------------------------
def parse_file(file):
    return parse_releasefile(file)
# =============================================================
# ----------------------------------------------------------------------
def parse_args(args, load=True):
    """Parses anything on the command line"""

    rets = list()    # The things we parsed
    parts = list()    # Accumulate args

    # --------------------------------
    def flush_parts():    # Parses
        nonlocal rets, parts

        if len(parts) == 0:
            return

        if len(parts) == 1:
            # First try parsing as an expset
            try:
                rets.append(parse_expset(parts[0]), load=load)
            except ValueError:
                # I guess it's not an expset
                rets.append(parse_parts(parts, load=load))

        else:
            rets.append(parse_parts(parts, load=load))

    # --------------------------------
    for arg in args:
        if arg == ':':    # Separator
            flush_parts()
        elif os.path.isdir(arg):
            flush_parts()
            rets.append(parse_dir(arg))
        elif os.path.isfile(arg):
            flush_parts()
            rets.append(parse_file(arg))
        else:
            parts.append(arg)
    flush_parts()

    return rets
# -----------------------------------------------------------
def main():
    import sys
    rets = parse_args(sys.argv[1:], load=True)
    for ret in rets:
        print('-------------------------------')
        for k,v in ret.items():
            print(f'{k}: {v}')

main()

