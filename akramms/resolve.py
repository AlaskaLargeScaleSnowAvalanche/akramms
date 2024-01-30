import itertools,re,os,functools,glob,hashlib,pickle
import netCDF4
import pandas as pd
from uafgi.util import shputil
from akramms import level,parse,file_info

# Levels:
#   exp - combo - (pra_size) chunk - (pra_size) - aval

def initial(parseds):
    orows = list()
    for n,parsed in enumerate(parseds):
        orows.append({'sort_order': n, 'parsed': parsed})
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
    for tup in akdf.itertuples(index=False):
        parsed = tup.parsed

        if 'arcfile' in parsed:
            with netCDF4.Dataset(parsed['arcfile']) as nc:
                statusv = nc.variables['status']
                exp = statusv.getncattr('exp_mod')
        else:
            exp = parsed['exp']
        orows.append(itertools.chain(tup, [exp]))

#    return pd.DataFrame(orows, columns=tuple(
#        itertools.chain(type(tup)._fields, ['exp'])))
    return pd.DataFrame(orows, columns=list(akdf.columns) + ['exp'])


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


    for tup in akdf.itertuples(index=False):
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

    return pd.DataFrame(orows, columns=list(akdf.columns) + ['combo'])
#    return pd.DataFrame(orows, columns=tuple(
#        itertools.chain(type(tup)._fields, ['combo'])))

# ------------------------------------------------------------
#_chunk_subleafRE = re.compile(r'(\d\d\d\d\d)(\d+)([TSML])(For|NoFor)_(\d+)')
_chunkRE = re.compile(r'^c-([TSML])-(\d\d\d\d\d)$')
def resolve_chunk(akdf, scenetypes={'x'}, realized=True):
    """Resolves either to a CHUNK releasefile, or an ARCHIVE directory"""

    # Only does realized option
    assert realized

    # Make sure input is non-empty
#    assert len(akdf.index) > 0

    # Ensure this is idempotent
    if 'releasefile' in akdf:
        return akdf

    # -----------------------------
    orows = list()
    def process_releasedir(tup, chunkid, releasedir):

        # If the arc directory doesn't yet exist...
        if not os.path.exists(releasedir):
            return

#        print(f'process_releasedir({releasedir}')
        for name in os.listdir(releasedir):
            match = file_info.chunk_release_fileRE.match(name)
#            print('    match2 ', name, match)
            if match is not None:
                pra_size = match.group(1)
                orows.append(itertools.chain(tup, ['x', pra_size, chunkid, releasedir / name]))
    # -----------------------------

    # Base releasefile on **what we see on disk**

    # First find directories containing RELEASE files
    for tup in akdf.itertuples(index=False):
        parsed = tup.parsed

        if parsed['type'] == 'releasefile':
            # The releasefile is just given to us!
            orows.append(itertools.chain(tup,
                [parsed['scenetype'], parsed['pra_size'], int(parsed['chunkid']), parsed['releasefile']]))
        elif parsed['type'] == 'chunkdir':
            releasefile = level.chunkdir_to_releasefile(parsed['chunkdir'])
            orows.append(itertools.chain(tup,
                [parsed['scenetype'], parsed['pra_size'], int(parsed['chunkid']), releasefile]))
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

            if 'x' in scenetypes:
                scenedir = expmod.combo_to_scenedir(combo, scenetype='x')
                chunkdir = scenedir / 'CHUNKS'
                if os.path.isdir(chunkdir):
                    for name in sorted(os.listdir(chunkdir)):    # List chunsk in an x-dir
                        match = _chunkRE.match(name)
#                       print('    match = ', match)
                        if match is not None:
                            # We found a valid chunk dir!  Remember its associated RELEASE dir.
                            chunkid = int(match.group(2))
                            process_releasedir(tup, chunkid, scenedir / 'CHUNKS' / name / 'RELEASE')

        if 'arc' in scenetypes:
            scenedir = expmod.combo_to_scenedir(combo, scenetype='arc')

            # Put the arc_dir in place of the releasefile.
            if os.path.isdir(scenedir):
                orows.append(itertools.chain(tup, ['arc', None, None, scenedir]))

    df = pd.DataFrame(orows, columns=list(akdf.columns) + ['scenetype', 'pra_size', 'chunkid', 'releasefile'])
#    df = pd.DataFrame(orows, columns=tuple(
#        itertools.chain(type(tup)._fields, ['scenetype', 'pra_size', 'chunkid', 'releasefile'])))
    #df['chunkinfo'] = df.map('releasefile', file_info.parse_chunk_release_file)
    return df

# ------------------------------------------------------------
_avalRE = re.compile(r'^aval-([TSML])-(\d+)-([^-]*).nc$')
#_out_zipRE = re.compile(r'(.*)_(\d+)\.out\.zip$')

@functools.lru_cache()
def _realized_ids(scenetype, releasefile, stage, include_overruns=False):
    """Find IDs that exist on disk.
    (Cached separate function)

    include_overruns:
        Only makes sense with scenetype='arc'
    stage: 'in' or 'out'
        Whether we are looking for .in.zip files or .out.zip
    Returns: {id: filename}
    """

    # include_overruns only makes sense for scenetype='arc'
    # To tell overruns with 'x', we have to look inside the files.
    if scenetype == 'x' and include_overruns:
        raise ValueError("include_overruns only makes sense for scenetype='arc'.  With scenetype='x', it is not possible to determine overruns from the filename.  To fix, set include_overruns=False")

#    print('realized_ids ', scenetype, stage, releasefile)

    stage_zipRE = re.compile(r'(.*)_(\d+)\.' + stage + r'\.zip$')

    avalfiles = list()

    # Find the IDs that exist on disk
    if scenetype == 'x':
#TODO: Apply proper comparisons to avoid race conditions
        resultsdir = releasefile.parents[1] / 'RESULTS'
        for out_zip in glob.iglob(str(resultsdir / '*' / '*' / f'*.{stage}.zip')):
            if not file_info.is_file_good(out_zip):
                continue
            match = stage_zipRE.match(os.path.split(out_zip)[1])
            id = int(match.group(2))
            # Do not provide info on whether the avalanche finished or overran
            avalfiles.append((id, out_zip, None))
    elif scenetype == 'arc':
        avaldir = releasefile
        for name in os.listdir(avaldir):
            match = _avalRE.match(name)
            if match is not None:
                # There could be >1 avalanche of the same name: overrun and (final) not overrun.
                overrun = (match.group(3) == 'overrun')    # Overrun info encoded in name
                id_status = file_info.JobStatus.OVERRUN if overrun else file_info.JobStatus.FINISHED
                avalfiles.append((int(match.group(2)), avaldir / name, id_status))
    else:
        assert False

    return avalfiles

def resolve_id(akdf, realized=True, stage='out', status_col=False):
    """
    stage:
        If realized, are we looking for avalanche IDs with .in.zip or .out.zip?
    status_col:
        Include status column? (overrun status)
    """


    # Ensure this is idempotent
    if 'id' in akdf:
        return akdf

    orows = list()

    akdf = akdf.reset_index(drop=True)
    for tup in akdf.itertuples(index=False):
#        print(tup)
        if tup.scenetype == 'arc':
            if not realized:
                raise ValueError('Must have realized=True when resolving IDs for archived scenes')
        else:
            if status_col:
                raise ValueError("Cannot provide status column for scene_type=='x'")

#        print('resolve_id tup ', realized, tup)
        parsed = tup.parsed

        # See if a single avalanche ID was already specified
        if parsed['type'] == 'arcfile':
            orows.append(itertools.chain(tup,
                [ parsed['id'], parsed['arcfile'], parsed['id_status'] ]))
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
            # Match releasefile against what's on disk
            avalfiles = _realized_ids(tup.scenetype, tup.releasefile, stage)
#            print('avalfiles ', avalfiles)

            if ids is None:    # Archive-type directory, no releasefile
                for x in avalfiles:    # (id, fname, id_status)
                    orows.append(itertools.chain(tup, x))
            else:
                #print('avalfiles ', tup.combo, len(avalfiles), len(ids))
                avalfile_set = {id: (fname, id_status) for id,fname,id_status in avalfiles}
                for id in ids:
                    try:
                        fname, id_status = avalfile_set[id]
                        orows.append(itertools.chain(tup, (id, fname, id_status)))
                    except KeyError:
                        # ID from releasefile was not realized, ignore it
                        pass
        else:
            # Just include the IDs, no avalfiles
            # User can fill in avalfile column later if desired.
            if ids is not None:
                for id in ids:
                    orows.append(itertools.chain(tup, (id, None, None)))


    df = pd.DataFrame(orows, columns=tuple(
        itertools.chain(akdf.columns, ['id', 'avalfile', 'id_status'])))
#        itertools.chain(type(tup)._fields, ['id', 'avalfile'])))

    if not status_col:
        df = df.drop('id_status', axis=1)
    return df

# ------------------------------------------------------------
def resolve_to(parseds, level, realized=True, scenetypes={'x'}, stage='out', status_col=False):
    """level: exp|combo|chunk|id
        Which level of detail to generate for this query.
        NOTE: level='id' is only used for QUERYING results, not for
              PRODUCING them.  When PRODUCING results, they are
              genderated one combo at a time, so things are resolved
              to level='combo' and then chunk.read_rel() or
              chunk.read_reldom() is used to load the releasefile.
    status_col:
        Include status column? (overrun status)
    """

    akdf = initial(parseds)
    akdf = resolve_exp(akdf)
    if level == 'exp':
        return akdf

    akdf = resolve_combo(akdf, realized=realized, scenetypes=scenetypes)
#    print('resolve_combo ', akdf)
    if level == 'combo':
        return akdf

    akdf = resolve_chunk(akdf, scenetypes=scenetypes)
#    print('resolve_chunk ', akdf)
    if level == 'chunk':
        return akdf

    akdf = resolve_id(akdf, realized=realized, stage=stage, status_col=status_col)
#    print('resolve_id ', akdf)
    if level == 'id':
        return akdf

    raise ValueError(f'Illegal level="{level}"')
# ------------------------------------------------------------
def add_chunkname(akdf1):
    akdf1['chunkname'] = akdf1.releasefile.map(lambda x: x.parents[1].parts[-1])
    return akdf1
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
        #akdf1['chunkname'] = akdf1.releasefile.map(lambda x: x.parents[1].parts[-1])
        akdf1 = akdf1.add_chunkname(akdf1)

        # Keep only the ID with the largest (newest) chunkname
        akdf1 = akdf1.sort_values(['id', 'chunkname'])
        akdf1.drop_duplicates(subset='id', keep='last', inplace=True)

        dfs.append(akdf1)

    return pd.concat(dfs)

# -------------------------------------------------------------

def _hashmod_combo(combo, nparts):
    hasher = hashlib.sha256()
    hasher.update(pickle.dumps(combo))
    dig = hasher.digest()
    val = int.from_bytes(dig, 'big')
    return val % nparts

# hash(combo) % nparts)

def filter_by_part_usinghash(akdf0, part, nparts):
    """Divide workload between multile running instances of akramms run.
    part:
        Which instance (start with 0)
    nparts:
        How many instances
    """

    # Filter by part
    assert (part >= -1) and (part < nparts)
    if part < 0:
        return akdf0

    hm = akdf0['combo'].map(lambda combo: _hashmod_combo(combo, nparts))
    akdf0 = akdf0[hm == part]

    return akdf0
# -------------------------------------------------------------
def part_range_section(nrows, part, nparts):
    k,m = divmod(nrows, nparts)
    return part*k+min(part, m),(part+1)*k+min(part+1, m)

def filter_by_part_section(akdf0, part, nparts):
    a,b = part_range(len(akdf0), part, nparts)
    return akdf0.iloc[a:b]
# -------------------------------------------------------------
# Let's stripe it!
def part_range(nrows, part, nparts):
    return list(range(part,nrows,nparts))

def filter_by_part(akdf0, part, nparts):
    rr = part_range(len(akdf0), part, nparts)
    return akdf0.iloc[rr]
