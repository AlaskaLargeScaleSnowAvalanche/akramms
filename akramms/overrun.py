import os
import pandas as pd
from akramms import file_info,chunk,level
from akramms import r_ramms1
from uafgi.util import shapelyutil


"""Handle avalanches that overrun"""


def resubmit(akdf0, dry_run=False):
    """Creates new chunks for avalanches that have overrun.
    akdf:
        Resolved to id
        Eg: resolve.resolve_to(parseds, 'id', realized=True, stage='out')
    """
#    print('akdf0a ', akdf0.columns)
    akdf0['overrun'] = akdf0['avalfile'].map(joblib.is_overrun)
    akdf0 = akdf0.loc[ akdf0['overrun'] ]
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
        expmod = akramms.parse.load_expmod(exp)
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

            # TODO: Enlarge the  domains!!!

            akdf2 = akdf2.rename(columns={'id':'Id'})
            chunk.write_chunk(scene_args, jb, akdf2, {})

            # Run RAMMS Stage 1 (and auto-submit)
            chunk_dir = scene_args['scene_dir'] / 'CHUNKS' / jb.chunk_name
            assert not os.path.exists(chunk_dir)    # Sanity / Safety Check
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
