import os
import pandas as pd
from akramms import file_info,chunk,level,joblib,config
from akramms import r_ramms1,parse,params
from uafgi.util import shapelyutil


"""Handle avalanches that overrun"""


def resubmit(akdf0, check_running=True, update=True, dry_run=False):
    """Creates new chunks for avalanches that have overrun.
    akdf:
        Resolved to combo
        Eg: resolve.resolve_to(parseds, 'id', realized=True, stage='out')
    check_running:
        Check if any IDs are running (or should be running); and
        if so, aborts.
    """

    # ------------------ Work at the cdombo level
    # 1. Make sure combos aren't in-progres.
    akdf0 = joblib.add_combo_status(akdf0, realized=True, update=update)
    if check_running:
        running_df = akdf0[akdf0.combo_status <= joblib.JobStatus.INPROCESS]
        if len(running_df) > 0:
            print(running_df[['combo', 'combo_status']])
            raise ValueError('Some combos are still running')

    # 2 Dismiss combos that are already complete.
    mask = akdf0.combo_status >= joblib.JobStatus.FINISHED
    akdf0 = akdf0[~mask]



    akdf0 = joblib.add_id_status(akdf0)

    if check_running:
        akdf0['running'] = akdf0.id_status.isin({joblib.JobStatus.TODO, joblib.JobStatus.INPROCESS})



    akdf0 = akdf0[akdf0.id_status == joblib.JobStatus.OVERRUN]
    print('Resubmitting these avalanches...')
    joblib.print_status(akdf0, 'id')

#    print('akdf0a ', akdf0.columns)
#    akdf0['overrun'] = akdf0['avalfile'].map(joblib.is_overrun)
#    akdf0 = akdf0.loc[ akdf0['overrun'] ]
#    print('akdf0b ', akdf0.columns)
    if len(akdf0) == 0:
        print('Nothing to process')
        return

    # Add the release and domain shapefile info
    dfs = list()
    for releasefile,akdf1 in akdf0.groupby('releasefile'):
        jb = file_info.parse_chunk_release_file(releasefile)._replace(chunkid=-1)
        rdf = chunk.read_reldom(releasefile)
        akdf1 = akdf1.set_index('id').merge(rdf, how='left', left_index=True, right_index=True).reset_index()
        akdf1['chunkinfo'] = [jb]*len(akdf1)    # Everything is set correctly here except the new chunkid
        dfs.append(akdf1)
    akdf0 = pd.concat(dfs)

    # Enlarge the domain
    akdf0['dom'] = akdf0['dom'].map(lambda dom: shapelyutil.add_margin(dom, config.enlarge_increment))

    # Group into new chunks
    for (exp, combo),akdf1 in akdf0.groupby(['exp', 'combo']):
        expmod = parse.load_expmod(exp)
        scenedir = expmod.combo_to_scenedir(combo)
        max_chunkids = chunk.get_max_chunkids(scenedir)
        print('max_chunkids ', max_chunkids)

        scene_args = params.load(scenedir)

        for pra_size,akdf2 in akdf1.groupby('pra_size'):
            # Verify this is all within one chunk
            chunkinfos = akdf2['chunkinfo'].tolist()
#            print('chunkinfos ', chunkinfos)
            assert all((x == chunkinfos[0]) for x in chunkinfos[1:])

            chunkid = max_chunkids.get(pra_size,-1) + 1
            jb = chunkinfos[0]._replace(chunkid=chunkid)

#            print(akdf2.columns)
            print('------------- Writing chunk: ', pra_size)
            print(jb)
            print(akdf2.id.tolist())

            akdf2 = akdf2.rename(columns={'id':'Id'})
            chunk_dir = scene_args['scene_dir'] / 'CHUNKS' / jb.chunk_name
            if not not os.path.exists(chunk_dir):    # Sanity / Safety Check
                raise ValueError(f'Path should not exist but does: {chunk_dir}')
            chunk.write_chunk(scene_args, jb, akdf2, {})

            # Run RAMMS Stage 1 (and auto-submit)
            releasefile = chunk_dir / 'RELEASE' / f'{jb.slope_name}_{jb.avalanche_name}_rel.shp'
            rule = r_ramms1.rule(releasefile, scene_args['dem_file'], [releasefile], dry_run=dry_run, submit=True)
            rule()

            #parseds = [parse.parse_chunk_releasefile(release_file)]
            #akdf = resolve.resolve_to(parseds, 'id', stage='in', realized=True)
            #joblib.submit_jobs(akdf)




            # DEBUGGING: Just do one!
            break


def drop_duplicates(akdf):

    """Removes duplicate avalanches after resolving, keeping only the
    avalanche in the most recent chunk

    akdf:
        Resolved to id

    """
    # Keep only the avalanche from the most recent chunk
    # akdf = akdf.sort_values(['combo', 'id', 'chunkid'])    # Not needed
    akdf.drop_duplicates(['combo', 'id'], keep='last', inplace=True)
    return akdf
