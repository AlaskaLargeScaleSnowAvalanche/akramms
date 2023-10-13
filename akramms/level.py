


# -----------------------------------------------------------
def theory_combos_in_set(exp_name, set_fn_name):
    """Lists theoretical combos in an experiment
    exp_name: str
        Name of the experiment (eg: ak)
    exp_fn:
        Function within the experiment Python module that details the combos
        Eg: juneau
    Yields:
        Fully specified combos (including idom / jdom)
    """

    exp_mod = parse.exp_mod(exp_name)
    set_fn = getattr(exp_mod, set_fn_name)
    yield from set_fn()
# -----------------------------------------------------------
def theory_wcombo_to_trial_dir(exp_name, wcombo):
    """
    Returns:
            Eg: /home/efischer/prj/ak/ak-ccsm-1981-1990-lapse-For-30
    """
    exp_mod = parse.exp_mod(exp_name)
    return exp_mod.combo_to_scene_dir(wcombo).parents[0]

def trial_dir_to_wcombo(trial_dir, exp_mod=None):
    trail_dir = pathlib.Path(trail_dir)

    # Get the rest of the combo
    sparts = trial_dir.parts[-1].split('-')[1:] + [None, None]

    # Get the exp_mod if needed
    if exp_mod is None:
        exp_mod = parse.exp_mod(scene_dir.parts[-3])

    return exp_mod, exp_mod.Combo(*sparts)

# -----------------------------------------------------------
def wcombo_to_combos(exp_name, wcombo, type='x'):
    """Resolves wildcard (idom,jdom) combos"""
    exp_mod = parse.exp_mod(exp_name)
    trial_dir = wcombo_to_trial_dir(exp_name, wcombo)
    sceneRE = re.compile('{'+type+r'}-(\d+)-(\d+)')
    for name in os.listdir(trial_dir):
        match = sceneRE.match(name)
        if match is None:
            continue
        idom = int(match.group(1))
        jdom = int(match.group(2))
        yield wcombo.replace(idom=idom, jdom=jdom)

# -----------------------------------------------------------
def exp_dir_to_wcombos(exp_mod):
    for name in os.listdir(exp_mod.dir):
        try:
            yield trial_dir_to_wcombo(exp_mod.dir / name)
        except:
            # Apparently this subdirectory is NOT a trial.
            pass
# -----------------------------------------------------------
def theory_combo_to_scene_dir(exp_name, combo, type='x'):
    """Returns the full pathname for a RAMMS scene, based on its experiment and combo.
    The combo must be fully specified!!!"""
    exp_mod = parse.exp_mod(exp_name)
    if type is None:
        types = ['x','arc']
    else:
        types = [type]

    for type in types:
        yield exp_mod.combo_to_scene_dir(combo, type=type)
# -------------------------------------------------------------
scene_dirRE = re.compile(r'(x|arc)-(\d+)-(\d+)$')
def theory_scene_dir_to_combo(scene_dir, exp_mod=None):
    """
    scene_dir:
        .../.../<exp_name>/<exp_name>-<combo-elements>/x|arc-<idom>-<jdom>
    """

    scene_dir = pathlib.Path(scene_dir)

    # Get idom, jdom
    match = scene_dirRE.match(scene_dir.parts[-1])
    idom = int(match.group(1))
    jdom = int(match.group(2))

    # Get the rest of the combo
    sparts = scene_dir.parts[-2].split('-')[1:] + [idom, jdom]

    # Get the exp_mod if needed
    if exp_mod is None:
        exp_mod = parse.exp_mod(scene_dir.parts[-3])

    return exp_mod, exp_mod.Combo(*sparts)

# -----------------------------------------------------------
def x_dir_to_chunk_dirs(scene_dir, chunk_stage=0):

    # Read list of chunks
    chunk_rfs = list()    # Names of release files for each CHUNK
    for name in os.listdir(scene_dir / 'stage0'):
        if not name.endswith('_chunks.csv'):
            continue
        df = pd.read_csv(stage0_dir / name)
        if config.max_chunks is not None:    # Testing
            df = df[df['segment'] < config.max_chunks]    # Cut down based on config

        for chunk_name in df['chunk_name'].unique():
            chunk_dir = scene_dir / f'CHUNKS{chunk_stage}' / chunk_name    # <scene>/CHUNKS/x-.....For_10m


def chunk_dir_to_release_file(chunk_dir):
    """Given a bunch of RAMMS directories, returns the release files in them."""
    RELEASE_dir = chunk_dir / 'RELEASE'
    release_files = list()
    for file in os.listdir(RELEASE_dir):
        if file.endswith('_rel.shp'):
            release_files.append(os.path.join(RELEASE_dir, file))

    # There should only be one release file per chunk!
    assert len(release_files) == 1
    return release_files[0]
# -----------------------------------------------------------
def arc_dir_to_release_files(arc_dir):
    RELEASE_dir = arc_dir / 'RELEASE'
    release_files = list()
    for file in os.listdir(RELEASE_dir):
        if file.endswith('_rel.shp'):
            release_files.append(os.path.join(RELEASE_dir, file))
    return release_files
# -----------------------------------------------------------
def release_file_to_df(release_file):
    """Reads a single _rel.shp and _dom.shp and merges them together.
    base: filename
        Everything but _rel.shp or _dom.shp
        Based on jb.ramms_name
    jb:
        Parsed Release file.
    Returns: df, rel_cols, dom_cols
        rel_cols, dom_cols: [str, ...]
            Names of columns
    """

    base = release_file[:-8]    # Strip off _rel.shp

    # Read _rel and _dom shapefiles
    rel_df = shputil.read_df(f'{base}_rel.shp', shape='pra').drop('fid', axis=1).set_index('Id')
    dom_df = shputil.read_df(f'{base}_dom.shp', shape='dom').drop('fid', axis=1).set_index('Id')
    df = rel_df.merge(dom_df[['dom']], left_index=True, right_index=True)

    # Drop rows with missing domain
    df = df[df['dom'].notna()]
    return df
# -----------------------------------------------------------
