import glob,sys,os
from akramms import parse

# Reset steps in the computation

# ========================================================================
# ----------------------------------------------------------------------
def _deletes_combo_arcgis(scenedir):
    return \
        _deletes_combo_ecog(scenedir) + \
        _deletes_combo_ramms1(scenedir) + \
        [scenedir / 'PRA_frequent',
        scenedir / 'PRA_extreme',
        scenedir / 'data_prep_PRA1.pik',
        scenedir / 'data_prep_PRA2.txt',
        scenedir / 'data_prep_PRA_args.pik']
# ----------------------------------------------------------------------
def _deletes_combo_ecog(scenedir):
    return \
        _deletes_combo_ramms1(scenedir) + \
        [scenedir / 'eCog']
# ----------------------------------------------------------------------
def _deletes_combo_pra(scenedir):

    """Forces rerun of pra_post but not eCognition.  Does NOT force
    rerun of RAMMS1 (for chunks that were previously successful)."""

    return [
        scenedir / 'RELEASE',
        scenedir / 'DOMAIN',
        scenedir / 'ramms_stage1.txt',
    ]
# ----------------------------------------------------------------------
def _deletes_combo_ramms1(scenedir):
    return [
        scenedir / 'ramms_stage1.txt',
        scenedir / 'ramms_stage1',
        scenedir / 'CHUNKS']
# ----------------------------------------------------------------------
def _deletes_chunk_chunk(chunkdir):

    """Removes the entire chunk.  After this, akramms will ignore the
    chunk until you regenerate it via `akramms reset combo pra`"""

    return [
        chunkdir
        scenedir / 'ramms_stage1.txt',    # We must re-run RAMMS Stage 1
    ]
# ----------------------------------------------------------------------
def _deletes_chunk_ramms1(chunkdir):
    """After reset, akramms run will re-run RAMMS Stage 1.
    Follow with `akramms reset chunk chunk` to fully reset the chunks

    akdf:
        Resolved to  chunk level
    """
    scenedir = chunkdir.parents[1]
    chunkname = chunkdir.parts[-1]
    return [
        chunkdir / 'RESULTS',
        scenedir / 'ramms_stage1.txt',
        scenedir / 'ramms_stage1' / f'{chunkname}.txt']

# ----------------------------------------------------------------------
def _deletes_chunk_ramms2(chunkdir):
    scenedir = chunkdir.parents[1]
    chunkname = chunkdir.parts[-1]

    return \
        list(glob.glob(chunkdir / 'RESULTS' / '*' / '*' / '*.out.zip')) + \
        [scenedir / 'ramms_stage2', f'{chunkname}.txt']
# ----------------------------------------------------------------------
def _deletes_combo_ramms2(scenedir):
    """RAMMS Stage 2 on a combo"""
    ret = list()

    # Delete *.out.zip for all chunks
    df = level.scenedir_to_chunknames(scenedir)    # pra_size, chunkid, name
    df = df.sort_values('name')
    for tup in df.itertuples(index=False):
        chunkdir = scene_dir / 'CHUNKS' / tup.name
        ret += _deletes_chunk_ramms2(chunkdir)

    return ret

# ----------------------------------------------------------------------
def _deletes_combo_archive(xdir):
    """Make akramms reconsider archiving parts of a combo"""
    xleaf = xdir.parts[-1]
    arcdir = xdir.parts[:-1] / 'arc' + xleaf[1:]
# ----------------------------------------------------------------------
# ========================================================================
# ----------------------------------------------------------------------
def rm_all(deletes):
    for f in deletes:
        if not os.path.exists(f):
#            print('# Path does not exist: {f}')
            pass
        elif os.path.isdir(f):
            print(f'rm -rf {f}')
        else:
            # Treat it like a file
            print(f'rm {f}')


# ----------------------------------------------------------------------
def reset(akdf0, level, step):
    """
    akdf0:
        Resolved to level
    level:
        Either 'combo' or 'chunk'
    step:
        Which step of the computation we are cleaning: arcgis, ecog, etc.
    """
    selfmod = sys.modules[__name__]
    deletes_fn = getattr(selfmod, f'_deletes_{level}_{step}')

    deletes = list()
    for exp,akdf1 in akdf0.reset_index(drop=True).groupby('exp'):
        expmod = parse.load_expmod(exp)

        # Figure out what to delete
        if level == 'chunk':
            for releasefile in akdf1.releasefile:
                chunkdir = releasefile.parents[1]
                deletes += deletes_fn(chunkdir)
        elif level == 'combo':
            for combo in akdf1.combo:
                scenedir = expmod.combo_to_scenedir(combo, 'x')
                deletes += deletes_fn(scenedir)
        else:
            raise ValueError(f'Illegal level {level}')

    # Delete it
    rm_all(deletes)
# -----------------------------------------------------------------------
