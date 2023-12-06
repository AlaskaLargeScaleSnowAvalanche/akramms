import itertools,re,os,functools,glob
import netCDF4
import pandas as pd
from uafgi.util import shputil
from akramms import level,parse,file_info

# Levels:
#   exp - combo - (pra_size) releasefile - (pra_size) - aval

def initial(parseds):
    orows = list()
    for parsed in parseds:
        orows.append({'parsed': parsed})
    return pd.DataFrame(orows)


def resolve_exp(akdf):
    """
    parsed:
        Result of 
    """

    # Ensure this is idempotent
    if 'exp' in akdf:
        return akdf

    orows = list()
    for tup in akdf.itertuples():
        parsed = tup.parsed

        if 'arcfile' in parsed:
            with netCDF4.Dataset(parsed['arcfile']) as nc:
                statusv = nc.variables['status']
                exp = statusv.getncattr('exp_mod')
        else:
            exp = parsed['exp']
        orows.append(itertools.chain(tup, [exp]))

    return pd.DataFrame(orows, columns=tuple(
        itertools.chain(type(tup)._fields, ['exp'])))



def resolve_combo(akdf, realized=True, scenetypes={'x','arc'}):

    # Ensure this is idempotent
    if 'combo' in akdf:
        return akdf

    orows = list()

    # ----------------------------
    def process_trialdir(expmod, trialdir, wcombo):
        ijdoms = set()
        for scenetype in scenetypes:
            scenedirs = level.trialdir_to_scenedirs(trialdir, scenetype=scenetype)
            for ijdom,_,_ in scenedirs:
                ijdoms.add(ijdom)

        # Add rows to the dataframe now
        for ijdom in sorted(ijdoms):
            combo = parse.new_combo(expmod, (itertools.chain(wcombo, ijdom)))
            orows.append(itertools.chain(tup, [combo]))
    # ----------------------------


    for tup in akdf.itertuples():
        expmod = parse.load_expmod(tup.exp)
#        print('tup ', type(tup), tup)
        parsed = tup.parsed

        if parsed['type'] == 'arcfile':
            orows.append(itertools.chain(tup, [None]))
            continue

        if 'wcombo' in parsed:
            wcombo = parsed['wcombo']
            if 'ijdom' in parsed:
                combo = parse.new_combo(expmod, itertools.chain(wcombo, parsed['ijdom']))
                orows.append(itertools.chain(tup, [combo]))
            elif realized:
                # It's a wildcard combo, list the full combos there on disk
                trialdir = level.theory_wcombo_to_trialdir(tup.exp, wcombo)
                process_trialdir(expmod, trialdir, wcombo)

        elif 'expset_fn' in parsed:
            # User asked for a list of combos...
            for tcombo in parsed['expset_fn']():
                orows.append(itertools.chain(tup, [parse.new_combo(expmod, tcombo)]))

        elif realized:
            # No combo info given, our only clue is the experiment itself.
            # Let's list ALL the combos in this experiment

            #expmod = parse.load_expmod(tup.exp)
            if 'expdir' in parsed:
                expdir = parsed['expdir']
            else:
                expdir = expmod.dir
            nwcombo = len(expmod.combo_keys)-2
            xre = [parsed['exp']] + [r'([^-]*)'] * nwcombo
            sre = '-'.join(xre)
            trialRE = re.compile(sre)
            for name in os.listdir(expdir):
                match = trialRE.match(name)
                if match is not None:
                    wcombo = tuple(match.group(i) for i in range(1,nwcombo+1))
                    process_trialdir(expmod, expdir / name, wcombo)
        else:
            raise ValueError('Not able to determine combos for: {}'.format(tup))

    return pd.DataFrame(orows, columns=tuple(
        itertools.chain(type(tup)._fields, ['combo'])))

# ------------------------------------------------------------
#_chunk_subleafRE = re.compile(r'(\d\d\d\d\d)(\d+)([TSML])(For|NoFor)_(\d+)')
_chunkRE = re.compile(r'c-([TSML])-(\d\d\d\d\d)')
def resolve_releasefile(akdf, scenetypes=['x'], realized=True):
    """These are CHUNK releasefiles."""

    # Only does realized option
    assert realized

    # Make sure input is non-empty
    assert len(akdf.index) > 0

    # Ensure this is idempotent
    if 'releasefile' in akdf:
        return akdf

    # -----------------------------
    orows = list()
    def process_releasedir(tup, scenetype, chunkid, releasedir):

        # If the arc directory doesn't yet exist...
        if not os.path.exists(releasedir):
            return

        print(f'process_releasedir({releasedir}')
        for name in os.listdir(releasedir):
            match = file_info.chunk_release_fileRE.match(name)
#            print('    match2 ', name, match)
            if match is not None:
                pra_size = match.group(2)
                orows.append(itertools.chain(tup, [scenetype, pra_size, chunkid, releasedir / name]))
    # -----------------------------

    # Base releasefile on **what we see on disk**
    for scenetype in scenetypes:
        # First find directories containing RELEASE files
        for tup in akdf.itertuples():
            parsed = tup.parsed

            if parsed['type'] == 'releasefile':
                # The releasefile is just given to us!
                orows.append(itertools.chain(tup,
                    [parsed['scenetype'], parsed['pra_size'], int(parsed['chunkid']), parsed['releasefile']]))
            elif parsed['type'] == 'arcfile':
                # arcfile does not have any chunkid, so set to -1
                orows.append(itertools.chain(tup,
                    ['arc', parsed['pra_size'], -1, None]))
            else:
                # We need to list releasefiles from a higher level
                expmod = parse.load_expmod(tup.exp)
                # combo = expmod.Combo(*tup.combo)
                combo = parse.new_combo(expmod, tup.combo)
                print('*********** Made combo ', combo)
                scenedir = expmod.combo_to_scenedir(combo, scenetype=scenetype)
                if scenetype == 'x':
                    chunkdir = scenedir / 'CHUNKS'
                    if os.path.isdir(chunkdir):
                        for name in sorted(os.listdir(chunkdir)):
                            match = _chunkRE.match(name)
#                           print('    match = ', match)
                            if match is not None:
                                # We found a valid chunk dir!  Remember its associated RELEASE dir.
                                chunkid = int(match.group(2))
                                process_releasedir(tup, 'x', chunkid, scenedir / 'CHUNKS' / name / 'RELEASE')
                elif scenetype == 'arc':
                    # Put the arc_dir in place of the releasefile.
                    if os.path.isdir(scenedir):
                        orows.append(itertools.chain(tup, [scenetype, None, None, scenedir]))

    df = pd.DataFrame(orows, columns=tuple(
        itertools.chain(type(tup)._fields, ['scenetype', 'pra_size', 'chunkid', 'releasefile'])))
    #df['chunkinfo'] = df.map('releasefile', file_info.parse_chunk_release_file)
    return df

# ------------------------------------------------------------
_avalRE = re.compile(r'^aval-([TSML])-(\d+)-([^-]*).nc$')
#_out_zipRE = re.compile(r'(.*)_(\d+)\.out\.zip$')

@functools.lru_cache()
def _realized_ids(scenetype, releasefile, stage, include_overruns=False):
    """Find IDs that exist on disk.
    (Cached separate function)

    Returns: {id: filename}
    """

    stage_zipRE = re.compile(r'(.*)_(\d+)\.' + stage + r'\.zip$')

    avalfiles = dict()

    # Find the IDs that exist on disk
    if scenetype == 'x':
#TODO: Apply proper comparisons to avoid race conditions
        resultsdir = releasefile.parents[1] / 'RESULTS'
#        print('resultsdir ', resultsdir)
        for out_zip in glob.iglob(str(resultsdir / '*' / '*' / f'*.{stage}.zip')):
            if not file_info.file_is_good(out_zip):
                continue
            match = stage_zipRE.match(os.path.split(out_zip)[1])
            id = int(match.group(2))
            avalfiles[id] = out_zip
    elif scenetype == 'arc':
        avaldir = releasefile
        avalfiles = dict()
        for name in os.listdir(avaldir):
            match = _avalRE.match(name)
            if match is not None:
                if (not include_overruns) and (match.group(3) == 'overrun'):
                    continue
                avalfiles[int(match.group(2))] = avaldir / name
    else:
        assert False

    return avalfiles

def resolve_id(akdf, realized=True, stage='out', include_overruns=False):
    """
    stage:
        If realized, are we looking for avalanche IDs with .in.zip or .out.zip?
    """

    # Ensure this is idempotent
    if 'id' in akdf:
        return akdf

    orows = list()

    for tup in akdf.itertuples():
        parsed = tup.parsed

        # See if a single avalanche ID was already specified
        if parsed['type'] == 'arcfile':
            orows.append(itertools.chain(tup,
                [ parsed['id'], parsed['arcfile'] ]))
            continue

        # Get list of IDs to include
        if 'ids' in parsed:
            # The user provided a list of IDs in the query
            ids = parsed['ids']
        else:
            # Read the releasefile
            if tup.scenetype == 'x':
                df = shputil.read_df(tup.releasefile, read_shapes=False)
                ids = df['Id'].tolist()
                #print(f'Reading releasefile {tup.releasefile}: {ids}')
            else:
                ids = None    # No releasefile for archive

        # Add those IDs
        if realized:
            # Match those IDs against what was requested in the releasefile
            avalfiles = _realized_ids(tup.scenetype, tup.releasefile, stage, include_overruns=include_overruns)

            if ids is None:    # Archive-type directory, no releasefile
                for id,fname in avalfiles.items():
                    orows.append(itertools.chain(tup, (id, fname)))
            else:
                #print('avalfiles ', tup.combo, len(avalfiles), len(ids))
                for id in ids:
                    try:
                        orows.append(itertools.chain(tup, (id, avalfiles[id])))
                    except KeyError:
                        # ID from releasefile was not realized, ignore it
                        pass
        else:
            # Just include the IDs, no avalfiles
            # User can fill in avalfile column later if desired.
            for id in ids:
                orows.append(itertools.chain(tup, (id, None)))


    return pd.DataFrame(orows, columns=tuple(
        itertools.chain(akdf.reset_index().columns, ['id', 'avalfile'])))
#        itertools.chain(type(tup)._fields, ['id', 'avalfile'])))

# ------------------------------------------------------------
def resolve_to(parseds, level, realized=True, scenetypes={'x'}, stage='out', include_overruns=False):
    """level: exp|combo|releasefile|id
        Which level of detail to generate for this query.
        NOTE: level='id' is only used for QUERYING results, not for
              PRODUCING them.  When PRODUCING results, they are
              genderated one combo at a time, so things are resolved
              to level='combo' and then chunk.read_rel() or
              chunk.read_reldom() is used to load the releasefile.
    include_overruns:
        List overrun avalanches?  (Only affects for 'arc' scenetype)
    """

    akdf = initial(parseds)
    akdf = resolve_exp(akdf)
    if level == 'exp':
        return akdf

    akdf = resolve_combo(akdf, realized=realized, scenetypes=scenetypes)
#    print('resolve_combo ', akdf)
    if level == 'combo':
        return akdf

    akdf = resolve_releasefile(akdf, scenetypes=scenetypes)
#    print('resolve_releasefile ', akdf)
    if level == 'releasefile':
        return akdf

    akdf = resolve_id(akdf, realized=realized, stage=stage, include_overruns=include_overruns)
#    print('resolve_id ', akdf)
    if level == 'id':
        return akdf

    raise ValueError(f'Illegal level="{level}"')
# ------------------------------------------------------------
def remove_duplicate_ids(akdf0):
    """Removes duplicate IDs (within the same combo).
    Chooses the ID from with the largest (most recent) CHUNK.
    akdf:
        Resolved to the ID level, no index set yet.
    """
    dfs = list()
    # IDs are only unique within each combo
    for combo,akdf1 in akdf0.groupby('combo'):

        # Obtain chunkname from releasefile
        akdf1['chunkname'] = akdf1.releasefile.map(lambda x: x.parents[1].parts[-1])

        # Keep only the ID with the largest (newest) chunkname
        akdf1 = akdf1.sort_values(['id', 'chunkname'])
        akdf1.drop_duplicates(subset='id', keep='last', inplace=True)

        dfs.append(akdf1)

    return pd.concat(dfs)

# -------------------------------------------------------------
