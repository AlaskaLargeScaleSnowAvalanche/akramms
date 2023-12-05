import os
import pandas as pd
from akramms import level,parse,resolve


def add_chunk_complete_cached(akdf0, ramms_stage):
    """Determines whether each chunk is finished with RAMMS stage 1
    (Generating avalanches to run)

    Looks for the file x-113-045/c-T-00002.txt

    akdf:
        Resolved to releasefile
        Columns: chunkid, pra_size
    ramms_stage:
        1 or 2
        Are we checking whether RAMMS Stage 1 or 2 has completed,
        according to cached values?
    """

    akdf0 = resolve.add_chunkname(akdf0)
    dfs = list()
    for (exp,combo),akdf1 in akdf0.groupby(['exp', 'combo']):
        expmod = parse.load_expmod(exp)
        xdir = expmod.combo_to_scenedir(combo, 'x')
        ramms_stage_dir = xdir / f'ramms_stage{ramms_stage}'

        akdf1[f'chunk_complete_stage{ramms_stage}_cached'] = akdf1.chunkname.map(
            lambda chunkname: os.path.isfile(ramms_stage_dir / f'{chunkname}.txt'))
        dfs.append(akdf1)

    return pd.concat(dfs)

# ------------------------------------------------------------
def add_combo_archived_cached(akdf0):
    """Determines whether each combo is complete (and has been fully archived)

    akdf0:
        Resolved to combo level."""

    dfs = list()
    for exp,akdf1 in akdf0.reset_index().groupby('exp'):
        expmod = parse.load_expmod(exp)

        def _is_archived(combo):
            arcdir = expmod.combo_to_scenedir(combo, 'arc')
            complete_txt = arcdir / 'archived.txt'
            return os.path.isfile(complete_txt)

        akdf1['combo_archived_cached'] = akdf1.combo.map(_is_archived)

        dfs.append(akdf1)

    return pd.concat(dfs)


# =================================================================
#def _is_aval_complete(out_zip):
#    """Determines whether an avalanche has been completed with
#    successful output (no overruns)"""
#    jb = 
#    return file_info.is_file_good(out_zip) and not joblib.is_overrun(out_zip)
#
#def add_id_complete_stage2(akdf0):
#    """Determines which avalanches are done running
#    Looks for .out.zip files
#    """
#
#    dfs = list()
#    for (releasefile, chunkid),akdf1 in akdf0.groupby(['releasefile', 'chunkid']):
#        jb = file_info.parse_chunk_release_file(releasefile)
#
#        def _is_complete(id):
#            inout = joblib.input_name(jb, chunkid, id)
#            out_zip = jb.avalanche_dir / f'{inout}.out.zip'
#            return os.path.is_file(out_zip)
#
#        akdf1['id_complete_stage2'] = akdf1.id.map(_is_complete)
#
#        dfs.append(akdf1)
#
#    return pd.concat(dfs)


#def add_chunk_status(akdf0, realized=True):
#    """Determines whether each chunk is finished with RAMMS stage 2
#    (ran all the avalanches)
#    ...and therefore ready to be archived
#
#    akdf:
#        Resolved to releasefile
#        Columns: chunkid, pra_size
#    realized:
#        if True:
#            Check that all EXISTING avalanches are complete
#            (i.e. there's an .out.zip for every .in.zip)
#        if False:
#            Check that ALL avalanches in the releasefile have been
#            completed.
#    """
#
##    for exp,akdf1 in akdf0.groupby('exp'):
#    orows = list()
#    for (exp,combo),akdf1 in akdf0.reset_index().groupby(['exp', 'combo']):
#
#        iddf1 = resolve_id(
#            resolve.resolve_chunk(akdf1, scenetypes={'x'}),
#            realized=False)
#        iddf1 = add_id_complete_stage2(iddf1)
#        complete = iddf1['id_complete_stage2'].all()
#        orows.append((exp, combo, complete]
#    df = pd.DataFrame(orows, columns=('exp', 'combo', 'chunk_complete_stage2'))
#
#    return akdf0.merge(df, on=['exp', 'combo'])
# ------------------------------------------------------------
def add_combo_complete_stage2(akdf0, realized=True):
    """Determines whether each chunk is finished with RAMMS stage 2
    (ran all the avalanches)
    ...and therefore ready to be archived

    akdf:
        Resolved to releasefile
        Columns: chunkid, pra_size
    realized:
        if True:
            Check that all EXISTING avalanches are complete
            (i.e. there's an .out.zip for every .in.zip)
        if False:
            Check that ALL avalanches in the releasefile have been
            completed.
    """

#    for exp,akdf1 in akdf0.groupby('exp'):
    orows = list()
    for (exp,combo),akdf1 in akdf0.reset_index().groupby(['exp', 'combo']):

        iddf1 = resolve_id(
            resolve.resolve_chunk(akdf1, scenetypes={'x'}),
            realized=False)
        iddf1 = add_id_complete_stage2(iddf1)
        complete = iddf1['id_complete_stage2'].all()
        orows.append((exp, combo, complete))
    df = pd.DataFrame(orows, columns=('exp', 'combo', 'combo_complete_stage2'))

    return akdf0.merge(df, on=['exp', 'combo'])
# ------------------------------------------------------------
# ------------------------------------------------------------


#QUESTIONS
#===============
#
#1. Do I need to create and submit any new chunks to RAMMS Stage 1 (per combo)?
#
#2. Is Stage 2 done running (for now) (per chunk)?
#  - Examine only chunks that are not yet complete stage 2 (cached)
#  - Use joblib.add_jobstatus()
#  - If any chunks are NOW determined to be complete, cache the result
#  ==> per combo: aggregate into chunks
#
#3. Are there any avalanches I need to archive to complete a specific mosaic query?
#
#
#4. Are there any complete chunks I need to archive?
#
#5. Are there any archived chunks I need to delete?
#
