import os,subprocess,functools,re,typing,zipfile,enum,sys
import htcondor
import pandas as pd
from akramms import config,file_info,parse,level,complete,resolve

def add_chunk_status(akdf, realized=True, update=True):
    """Determins a status for each releasefile (chunk)

    akdf:
        Resolved to chunk
        Columns: chunkid, pra_size
    realized:
        if True:
            Check that all EXISTING avalanches are complete
            (i.e. there's an .out.zip for every .in.zip)
        if False:
            Check that ALL avalanches in the releasefile have been
            completed.
    """

    # Make it idempotent
    if 'chunk_status' in akdf.columns:
        return akdf

    if len(akdf) == 0:
        akdf['chunk_status'] = JobStatus.TODO
        return akdf

    dfs = list()
    for (exp,combo),akdf1 in akdf.reset_index(drop=True).groupby(['exp', 'combo']):
        expmod = parse.load_expmod(exp)
        xdir = expmod.combo_to_scenedir(combo, 'x')

        # Get releasefiles (chunks) that are not yet complete (as per cache)
        akdf1 = complete.add_chunk_complete_cached(akdf1, 2)    # chunk_complete_stage2_cached
        mask = akdf1['chunk_complete_stage2_cached']
        rf_complete_cached = akdf1[mask]
        rf_complete_cached['chunk_status'] = JobStatus.MARKED_FINISHED
        dfs.append(rf_complete_cached)

        # Go on with releasefiles not marked as cached
        akdf1 = akdf1[~mask]

        # ------------------------------------------
        # Get jobstatus at id level
        # Pick up job statuses
        rfdf1 = resolve.resolve_chunk(akdf1, scenetypes={'x'})
        iddf1 = resolve.resolve_id(rfdf1, realized=realized)
        iddf1 = add_id_status(iddf1)

        # Aggregate id status back to releasefile level and add to akdf1
        chunk_status = \
            iddf1[['releasefile','id_status']].groupby('releasefile').min() \
            .rename(columns={'id_status': 'chunk_status'})
        akdf1 = rfdf1.merge(chunk_status, how='left', left_on='releasefile', right_index=True)

        # Mark chunks as finished if they have in fact finished
        mask = (akdf1.chunk_status == JobStatus.FINISHED)
        finished_df = akdf1[mask]
        if update:
            os.makedirs(xdir / 'ramms_stage2', exist_ok=True)
            for chunkname in finished_df.chunkname:
                fname = xdir / 'ramms_stage2' / f'{chunkname}.txt'
                with open(fname, 'w') as out:
                    out.write('RAMMS Stage 2 complete\n')
            finished_df['chunk_status'] = JobStatus.MARKED_FINISHED
        dfs.append(finished_df)

        # Append the rest of the chunk status rows as-is
        akdf1 = akdf1[~mask]
        dfs.append(akdf1)

    return pd.concat(dfs)

# ------------------------------------------------------------
def add_combo_status(akdf0, realized=True, update=True):
    """akdf:
        Resolved to combo level (theoretical, i.e. realized=False)
    """
    print('zzzzzzzzzz1')
    # Make it idempotent
    if 'combo_status' in akdf0.columns:
        return akdf0
    print('zzzzzzzzzz2')

    dfs = list()

    if len(akdf0) == 0:
        akdf0['combo_status'] = JobStatus.TODO
        return akdf0

    print('zzzzzzzzzz3')

    for exp,akdf1 in akdf0.reset_index(drop=True).groupby('exp'):
        expmod = parse.load_expmod(exp)

#        akdf1['combo_status'] = JobStatus.NOINPUT    # The Combo doesn't exist yet

        # Take care of combos we know are archived
        is_archived = akdf1.combo.apply(lambda combo: 
            os.path.isfile(expmod.combo_to_scenedir(combo, 'arc') / 'archived.txt') )
        df = akdf1[is_archived]
        df['combo_status'] = JobStatus.MARKED_FINISHED
        dfs.append(df)
        akdf1 = akdf1[~is_archived]

        # ------------------------------------------
        # Get jobstatus at id level
        rfdf1 = resolve.resolve_chunk(akdf1)
        iddf1 = resolve.resolve_id(rfdf1, realized=realized)
        iddf1 = add_id_status(iddf1)

        # Replace older avalanches runs with newer runs of the same ID
        # (which presumably have fixed overrun problems)
        iddf1 = overrun.drop_duplciates(iddf1)

        df = iddf1[iddf1.id_status == joblib.JobStatus.OVERRUN]
        print('xxxxxxxxxxxyyyyyyyyyyyyyyyyy')
        print(df)


        # Aggregate id status back to combo level and add to akdf1
        combo_status = \
            iddf1[['combo','id_status']].groupby('combo').min() \
            .rename(columns={'id_status': 'combo_status'})
        akdf1 = akdf1.merge(combo_status, how='left', left_on='combo', right_index=True)
        akdf1['combo_status'] = akdf1.combo_status.fillna(JobStatus.NOINPUT).astype(int)

#        # ------------------------------------------
#        # Get jobstatus at id level
#        rfdf1 = resolve.resolve_chunk(akdf1)
#
#        # Separate into chunks we know are complete, vs chunks needing further investigation
#        rfdf1 = complete.add_chunk_complete_cached(rfdf1, 2)    # chunk_complete_stage2_cached
#        mask = rfdf1['chunk_complete_stage2_cached']
#        rfdf1_complete_cached = rfdf1[mask]
#        rfdf1 = rfdf1[~mask]
#
#        # For chunks not yet complete, get jobstatus at id level
#        iddf1 = resolve.resolve_id(rfdf1, realized=realized)
#        #rfdf1 = add_chunk_status(rfdf1, realized=realized, update=update)
#        iddf1 = add_id_status(iddf1)
#
#
#        # Aggregate id status back to  level and add to akdf1
#        combo_status = \
#            rfdf1[['combo','chunk_status']].groupby('combo').min() \
#            .rename(columns={'chunk_status': 'combo_status'})
#        akdf1 = akdf1.merge(combo_status, how='left', left_on='combo', right_index=True)
#        akdf1['combo_status'] = akdf1.combo_status.fillna(JobStatus.NOINPUT).astype(int)
#        # -------------------------------------------------
#
#
#        # Get jobstatus at chunk level
#        rfdf1 = resolve.resolve_chunk(akdf1)
#        rfdf1 = add_chunk_status(rfdf1, realized=realized, update=update)
#
#        # Aggregate id status back to combo level and add to akdf1
#        combo_status = \
#            rfdf1[['combo','chunk_status']].groupby('combo').min() \
#            .rename(columns={'chunk_status': 'combo_status'})
#        akdf1 = akdf1.merge(combo_status, how='left', left_on='combo', right_index=True)
#        akdf1['combo_status'] = akdf1.combo_status.fillna(JobStatus.NOINPUT).astype(int)
        # -------------------------------------------------

        # Archive combos if they have in fact finished
        if update:
            mask = (akdf1.combo_status == JobStatus.FINISHED)
            dfs.append(akdf1[~mask])

            finished_combo_df = akdf1[mask]
            archive.archive_combos(finished_combo_df)
            finished_combo_df.combo_status = JobStatus.ARCHIVED
            dfs.append(finished_combo_df)
        else:
            dfs.append(akdf1)

    return pd.concat(dfs)
# ------------------------------------------------------------
def add_status(akdf, level, realized=True, update=True):
    if level == 'id':
        akdf = add_id_status(akdf)

    elif level == 'chunk':
        akdf = add_chunk_status(akdf, realized=realized, update=update)

    elif level == 'combo':
        akdf = add_combo_status(akdf, realized=realized, update=update)

    return akdf

# ------------------------------------------------------------
_all_status = set(JobStatus._value2member_map_.values())
def print_status(akdf0, level, out=sys.stdout, statuses=_all_status):
    """
    level: 'id', 'chunk' or 'combo'
        Level of status we will print
    """

    if level == 'id':
        for releasefile,akdf1 in akdf0.groupby('releasefile'):
            print(f'-------------- {releasefile}', file=out)
            for id_status,akdf2 in akdf1.groupby('id_status'):
                if id_status not in statuses:
                    continue
                id_status = JobStatus._member_names_[id_status]
                ids = ', '.join(str(x) for x in akdf2.id.tolist())
                print(f'{id_status}: {ids}', file=out)
    elif level == 'releasefile' or level == 'chunk':
        for (exp,combo),akdf1 in akdf0.groupby(['exp', 'combo']):
            print(f'-------------- {exp} {combo}', file=out)
            for chunk_status,akdf2 in akdf1.groupby('chunk_status'):
                if chunk_status not in statuses:
                    continue

                chunk_status = JobStatus._member_names_[chunk_status]
                chunknames = ', '.join(akdf2.chunkname.tolist())
                print(f'{chunk_status}: {chunknames}', file=out)
    elif level == 'combo':
        for tup in akdf0.itertuples(index=False):
            if tup.combo_status not in statuses:
                continue
            scombo = '-'.join(str(x) for x in tup.combo)
            sstat = JobStatus._member_names_[tup.combo_status]
            print(f'{tup.exp}-{scombo}: {sstat}', file=out)



# ------------------------------------------------------------
