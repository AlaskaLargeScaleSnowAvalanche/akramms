import os
import pandas as pd
from akramms import level,parse


def add_combo_archived(akdf0):
    """Determines whether each combo is complete (and has been fully archived)

    akdf0:
        Resolved to combo level."""

    dfs = list()
    for exp,akdf1 in akdf0.reset_index().groupby('exp'):
        expmod = parse.load_expmod(exp)

        completes = list()
        for tup in akdf1.reset_index().itertuples():
            arcdir = expmod.comb_to_scenedir(combo, 'arc')

            complete_txt = arcdir / 'complete.txt'
            completes.append(os.path.isfile(complete_txt))

        akdf1['combo_complete'] = completes
        dfs.append(akdf1)

    return pd.concat(dfs)


# ------------------------------------------------------------

def add_chunk_complete_stage1(akdf0):
    """Determines whether each chunk is finished with RAMMS stage 1
    (Generating avalanches to run)

    Looks for the file x-113-045/c-T-00002.txt

    akdf:
        Resolved to releasefile
        Columns: chunkid, pra_size
    """

    akdf0 = akdf0.add_chunkname(akdf1)
    dfs = list()
    for (exp,combo),akdf1 in akdf0.groupby(['exp', 'combo']):
        expmod = parse.load_expmod(exp)
        xdir = expmod.comb_to_scenedir(combo, 'x')

        def _is_complete(chunkname):
            complete_txt = xdir / 'ramms_stage1' / f'{chunkname}.txt'
            return os.path.isfile(complete_txt)

        akdf1['chunk_complete_stage1'] = akdf1.chunkname.map(_is_chunk_complete_stage1)
        dfs.append(akdf1)

    return pd.concat(dfs)

# ------------------------------------------------------------
def _is_aval_complete(out_zip):
    """Determines whether an avalanche has been completed with
    successful output (no overruns)"""
    jb = 
    return file_info.is_file_good(out_zip) and not joblib.is_overrun(out_zip)

def add_id_complete_stage2(akdf0):
    """Determines which avalanches are done running
    Looks for .out.zip files
    """

    dfs = list()
    for (releasefile, chunkid),akdf1 in akdf0.groupby(['releasefile', 'chunkid']):
        jb = file_info.parse_chunk_release_file(releasefile)

        def _is_complete(id):
            inout = joblib.input_name(jb, chunkid, id)
            out_zip = jb.avalanche_dir / f'{inout}.out.zip'
            return os.path.is_file(out_zip)

        akdf1['id_complete_stage2'] = akdf1.id.map(_is_complete)

        dfs.append(akdf1)

    return pd.concat(dfs)
# ------------------------------------------------------------
def add_combo_complete_stage2(akdf0):
    """Determines whether each chunk is finished with RAMMS stage 2
    (ran all the avalanches)
    ...and therefore ready to be archived

    akdf:
        Resolved to releasefile
        Columns: chunkid, pra_size
    """

#    for exp,akdf1 in akdf0.groupby('exp'):
    orows = list()
    for (exp,combo),akdf1 in akdf0.reset_index().groupby(['exp', 'combo']):

        iddf1 = resolve_id(
            resolve.resolve_releasefile(akdf1, scenetypes={'x'}),
            realized=False)
        iddf1 = add_id_complete_stage2(iddf1)
        complete = iddf1['id_complete_stage2'].all()
        orows.append((exp, combo, complete]
    df = pd.DataFrame(orows, columns=('exp', 'combo', 'combo_complete_stage2'))

    return akdf0.merge(df, on=['exp', 'combo'])
# ------------------------------------------------------------
def add_combo_complete(akdf0):
    """Determines whether all avalanches in an x-dir combo have been
    completed (and therefore it is ready to be archived).  Should ONLY
    be run on combos that have not already been confirmed archived."""
