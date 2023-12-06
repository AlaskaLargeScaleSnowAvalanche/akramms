import re,itertools,os,pathlib
from akramms import parse


# =====================================================================
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------





# =====================================================================
# -----------------------------------------------------------
def theory_expset_to_combos(exp_name, set_fn_name):
    """Lists theoretical combos in an experiment
    exp_name: str
        Name of the experiment (eg: ak)
    exp_fn:
        Function within the experiment Python module that details the combos
        Eg: juneau
    Yields:
        Fully specified combos (including idom / jdom)
    """

    exp_mod = parse.load_expmod(exp_name)
    set_fn = getattr(exp_mod, set_fn_name)
    yield from set_fn()
# -----------------------------------------------------------
def theory_wcombo_to_trialdir(exp_name, wcombo):
    """
    wcombo:
        Wildcard combo (i.e. might have null idom/jdom)
    Returns:
            Eg: /home/efischer/prj/ak/ak-ccsm-1981-1990-lapse-For-30
    """
    expmod = parse.load_expmod(exp_name)
    combo = expmod.Combo(*itertools.chain(wcombo, (0,0)))
    return expmod.combo_to_scenedir(combo).parents[0]


# -----------------------------------------------------------
def wcombo_to_combos(exp_name, wcombo, type='x'):
    """Resolves wildcard (idom,jdom) combos"""
    exp_mod = parse.load_expmod(exp_name)
    trialdir = wcombo_to_trialdir(exp_name, wcombo)
    sceneRE = re.compile('{'+type+r'}-(\d+)-(\d+)')
    for name in os.listdir(trialdir):
        match = sceneRE.match(name)
        if match is None:
            continue
        idom = int(match.group(1))
        jdom = int(match.group(2))
        yield wcombo.replace(idom=idom, jdom=jdom)

# -----------------------------------------------------------
def expdir_to_wcombos(exp_mod):
    for name in os.listdir(exp_mod.dir):
        try:
            yield trialdir_to_wcombo(exp_mod.dir / name)
        except:
            # Apparently this subdirectory is NOT a trial.
            pass
# -----------------------------------------------------------
def theory_combo_to_scenedir(exp_name, combo, scenetype='x'):
    """Returns the full pathname for an AKRAMMS scene, based on its experiment and combo.
    The combo must be fully specified!!!"""
    exp_mod = parse.load_expmod(exp_name)
    if scenetype is None:
        scenetypes = ['x','arc']
    else:
        scenetypes = [scenetype]

    for scenetype in scenetypes:
        yield exp_mod.combo_to_scenedir(combo, scenetype=scenetype)
# -------------------------------------------------------------
scenedirRE = re.compile(r'(x|arc)-(\d+)-(\d+)$')
def theory_scenedir_to_combo(scenedir, exp_mod=None):
    """
    scenedir:
        .../.../<exp_name>/<exp_name>-<combo-elements>/x|arc-<idom>-<jdom>
    """

    scenedir = pathlib.Path(scenedir)

    # Get idom, jdom
#    print('scenedir ', scenedir)
#    print('xxxxxxxxxxxxxxxxx ', scenedir.parts[-1])

    match = scenedirRE.match(scenedir.parts[-1])
    idom = int(match.group(2))
    jdom = int(match.group(3))

    # Get the rest of the combo
    sparts = scenedir.parts[-2].split('-')[1:] + [idom, jdom]

    # Get the exp_mod if needed
    if exp_mod is None:
        exp_mod = parse.load_expmod(scenedir.parts[-3])

    return exp_mod.Combo(*sparts)
# -----------------------------------------------------------
def commonprefix(ini_strlist):
    from itertools import takewhile
 
    ## Initialising string
    #ini_strlist = ['akshat', 'akash', 'akshay', 'akshita']
 
    # Finding common prefix using Naive Approach
    res = ''.join(c[0] for c in takewhile(lambda x:
            all(x[0] == y for y in x), zip(*ini_strlist)))
    return str(res)


def commonsuffix(strs):
    return commonprefix((x[::-1] for x in strs))[::-1]

def scenedir_to_chunknames(scenedir):
    """Generator yields the chunks inside a scene
    Yields: (sizecat, chunkid, pathname)
    """

    scene_args = params.load(scenedir)
    chunknameRE = re.compile(r'([^_]+)([TSML])(For|NoFor)_(\d+m)'.format(scene_args['return_period']))

    # Partially parse the chunk directories.
    names = list()
    for name in os.listdir(scenedir / 'CHUNKS'):
        match = chunknameRE.match(name)
        if match is None:
            continue
        names.append((name, match.group(1), match.group(2)))    # Eg: (x-113-0450001430, S)

    if len(names) == 0:
        return

    # Discern where the base ends and the return period begins
    prefix = commonprefix(names)    # Eg: x-113-045000
    suffix = commonsuffix(names)    # Return period

    # Go through the names again
    lprefix = len(prefix)
    lsuffix = len(suffix)
    for name,subname,sizecat in names:
        chunkid = int(subname[lprefix:-lsuffix])
        rows.append((sizecat, chunkid, name))

    return pd.DataFrame(rows, columns=('sizecat', 'chunkid', 'name'))

# -----------------------------------------------------------
def trialdir_to_scenedirs(trialdir, scenetype='x'):
    """
    scenetype:
    Returns: [(scenedir, scenetype), ...]
        All the scenedirs found
    """
    rets = list()
    for name in os.listdir(trialdir):
        match = parse.scenedirRE.match(name)
        if (match is not None) and (match.group(1) == scenetype):
            ijdom = (int(match.group(2)), int(match.group(3)))
            rets.append( (ijdom, scenetype, os.path.join(trialdir, name)) )
    return rets

# -----------------------------------------------------------
def xdir_to_chunkdirs(scenedir, chunk_stage=0):

    # Read list of chunks
    chunk_rfs = list()    # Names of release files for each CHUNK
    for name in os.listdir(scenedir / 'stage0'):
        if not name.endswith('_chunks.csv'):
            continue
        df = pd.read_csv(stage0dir / name)
        if config.max_chunks is not None:    # Testing
            df = df[df['segment'] < config.max_chunks]    # Cut down based on config

        for chunk_name in df['chunk_name'].unique():
            chunkdir = scenedir / f'CHUNKS{chunk_stage}' / chunk_name    # <scene>/CHUNKS/x-.....For_10m


def chunkdir_to_releasefiles(chunkdir):
    """Given a single chunk directory, returns the (4) release files in it."""
    RELEASEdir = chunkdir / 'RELEASE'
    releasefiles = list()
    for file in os.listdir(RELEASEdir):
        if file.endswith('_rel.shp'):
            releasefiles.append(os.path.join(RELEASEdir, file))

    # There should only be one release file per chunk!
    assert len(releasefiles) == 1
    return releasefiles[0]

# -----------------------------------------------------------
def arcdir_to_releasefiles(arcdir):
    """Given an archive directory, returns the (4) release files in it."""
    RELEASEdir = arcdir / 'RELEASE'
    releasefiles = list()
    for file in os.listdir(RELEASEdir):
        if file.endswith('_rel.shp'):
            releasefiles.append(os.path.join(RELEASEdir, file))
    return releasefiles
# -----------------------------------------------------------
# ============================================================================
def _pr_parts_to_combos(pr, realized=True):
    if 'ijdom' in pr:    # Combo is fully specified
        return [expmod.Combo(*itertools.chain(pr['wcombo'], pr['ijdom']))]
    elif realized:    # Wildcard comb
        return list(wcombo_to_combos(pr['exp'], pr['wcombo'], type=None))
    else:
        raise NotYetImplementedError()
        

#def _pr_parts_to_releasefiles(pr):
#    expmod = pr['expmod']



#_to_releasefiles = {
#
#    'parts': _pr_parts_to_combos
#    'expset': 
#    'expdir': 
#    'trialdir': 
#    'scenedir': 
#    'releasefile': lambda pr: pr['releasefile'],
#}




#def to_releasefiles(pr):
#    """
#    pr:
#        Result of akramms.parse.parase_args()
#    """
#
#    # See if it was originally parsed as a releasefile
#    if pr['type'] == 'releasefile':
#        return [pr['releasefile']]


