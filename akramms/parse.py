


# =====================================================================
@functools.lru_cache()
def load_expmod(exp_name):
    if isinstance(exp_name, module):
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
    exp = parts[0]
    ret = {'exp': exp}

    # Remove experiment name and process dots
    parts2 = list()
    for part in parts[1:]:
        if _all_dotsRE.match(part) is not None:    # '.' is a wildcard
            parts2 += [None] * len(part)
    parts = parts2


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
_expsetRE = re.compile(r'([^.]+)\.([^.]+)$')
def parse_expset(expset, load=True):
    """A run is a generator inside an experiment that yields a bunch of combos.
    expset: Eg:
        ak.juneau
    """
    match = experiment_specRE.match(spec)

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
_chunk_subleafRE = re.parse(r'(\d+)([TSML])(For|NoFor)_(\d+)m')
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
# ----------------------------------------------------------------------
