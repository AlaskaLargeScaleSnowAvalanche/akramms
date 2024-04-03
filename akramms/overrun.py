import os,time,datetime
import pandas as pd
from akramms import file_info,chunk,level,joblib,config
from akramms import r_ramms1,parse,params,resolve
from uafgi.util import shapelyutil


"""Handle avalanches that overrun"""


def rerun_ramms_stage1(akdf0, dry_run=False):
    """Re-runs RAMMS Stage 1 on "NOINPUT" chunks.
    akdf0:
        Resolved to combo
    dem_file:
        scene_args['dem_file']
    """
    cdf0 = resolve.resolve_chunk(akdf0)
    print('xxxxxxxxx ', cdf0.columns)
    cdf0 = cdf0[cdf0.chunk_status == file_info.JobStatus.NOINPUT]

    for (exp, releasefile, combo),cdf1 in cdf0.groupby(['exp', 'releasefile', 'chunk']):
        expmod = parse.load_expmod(exp)
        jb = file_info.parse_chunk_release_file(releasefile)
        scene_args = params.load(expmod.combo_to_scenedir(combo))

        # Run RAMMS Stage 1 (and auto-submit)
        # releasefile = chunk_dir / 'RELEASE' / f'{jb.slope_name}_{jb.avalanche_name}_rel.shp'

        rule = r_ramms1.releasefile_rule(releasefile, dem_file, [releasefile], dry_run=dry_run, submit=True, at_front=True, condor_priority=1)
        if dry_run:
            print(f'Except for --dry-run, I would be running RAMMS on the releasefile {releasefile}')
        else:
            rule()


def resubmit(akdf0, check_running=True, ignore_statuses={}, update=True, dry_run=False, block=True):
    """Creates new chunks for avalanches that have overrun.
    akdf:
        Resolved to combo
        Eg: resolve.resolve_to(parseds, 'id', realized=True, stage='out')
    check_running:
        Check if any IDs are running (or should be running); and
        if so, aborts.
    block:
        If True, poll and wait for chunks to finish running before making decisions.
    Returns: akdf
        Dataframe of resubmitted avalanches
    """

    # ------------------ Work at the combo level

    # Poll until RAMMS Stage 2 is done running for these combos
    while True:
        akdf0 = joblib.add_combo_status(akdf0, realized=False, update=update, dry_run=dry_run, ignore_statuses=ignore_statuses)

        if block:
            mask = (akdf0.combo_status == joblib.JobStatus.INPROCESS)
            inprocess = akdf0[mask]
            if len(inprocess) == 0:
                # Nothing is running or about to run, we can continue synchronously
                break
            else:
                # Not everything is done running, sleep for a while and try again
                print('The following combos are still computing:')
                print(inprocess[['combo', 'combo_status']])
                now = datetime.datetime.now()
                wake_time = now + datetime.timedelta(seconds=config.poll_period)
                print(f'Current time is {now}')
                print(f'Sleeping until {wake_time}')
                time.sleep(config.poll_period)
        else:
            # We're not doing synchronous.
            # Resubmit whatever we can, knowing it might not be complete
            break


    # Re-run RAMMS for combos in the NOINPUT state
    mask = (akdf0.combo_status == joblib.JobStatus.NOINPUT)
    rerun_ramms_stage1(akdf0[mask], dry_run=dry_run)
    akdf0 = akdf0[~mask]
    return    # DEBUG


    # Only look at combos in the OVERRUN state, ignore all others
    mask = (akdf0.combo_status == joblib.JobStatus.OVERRUN)
    ignores = akdf0[~mask][['combo', 'combo_status']]
    if len(ignores) > 0:
        print('Not resubmitting combos because of status:')
        for tup in ignores.itertuples():
            scombo = '-'.join(str(x) for x in tup.combo)
            sstatus = joblib.JobStatus._member_names_[tup.combo_status]
            print(f'    {scombo} : {sstatus}')
    akdf0 = akdf0[mask]

    if len(akdf0) == 0:
        print('No combos eligible to resubmit')
        return

    # ----------------- Move to id level
    akdf0 = resolve.resolve_chunk(akdf0, scenetypes={'x'}, realized=True)
    akdf0 = resolve.resolve_id(akdf0, realized=True)
    akdf0 = drop_duplicates(akdf0)    # Account for past successful overrun resubmissions
    akdf0 = joblib.add_id_status(akdf0)
    akdf0 = akdf0[akdf0.id_status == joblib.JobStatus.OVERRUN]

    if len(akdf0) == 0:
        print('No IDs need to be resubmitted')
        return akdf0

    print('Resubmitting these avalanches...')
    joblib.print_status(akdf0, 'id')
    print('------------------------------------------------------')

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
            if dry_run:
                print(f'Except for --dry-run, I would be writing chunk to directory {chunk_dir}')
            else:
                chunk.write_chunk(scene_args, jb, akdf2, {})
                with open(chunk_dir / 'overrun.txt', 'w') as out:
                    out.write('This chunk resubmits avalanches that overran in a previous chunk')

            # Run RAMMS Stage 1 (and auto-submit)
            releasefile = chunk_dir / 'RELEASE' / f'{jb.slope_name}_{jb.avalanche_name}_rel.shp'
            rule = r_ramms1.releasefile_rule(releasefile, scene_args['dem_file'], [releasefile], dry_run=dry_run, submit=True, at_front=True, condor_priority=1)
            if dry_run:
                print(f'Except for --dry-run, I would be running RAMMS on the releasefile {releasefile}')
            else:
                rule()


def drop_duplicates(akdf):

    """Removes duplicate avalanches after resolving, keeping only the
    avalanche in the most recent chunk

    akdf:
        Resolved to id

    """
    # Keep only the avalanche from the most recent chunk
    akdf = akdf.sort_values(['combo', 'id', 'chunkid'])    # Not needed
    akdf.drop_duplicates(['combo', 'id'], keep='last', inplace=True)
    return akdf
