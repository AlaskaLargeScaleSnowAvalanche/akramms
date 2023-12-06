import os
import pandas as pd
from akramms.util import exputil,rammsutil
from akramms import r_ramms

# Queries avalanches in their RAMMS form, without archiving.

def query_aspecs(aspecs, filter_in_fn=lambda *args: True):
    ret = list()
    for aspec in aspecs:
        # Info from all release files in the combo
#        release_files, release_df = exputil.release_df(aspec.exp_mod, aspec.combo, type='x')

        for scene_dir in exputil.combo_to_scene_dirs(aspec.exp_mod, aspec.combo, type=type):
            release_files = rammsutil._get_release_files(scene_dir)    # Read CHUNKS/ release files
            job_statuses = r_ramms.job_statuses(release_files)
            release_df = release_df.merge(job_statuses, left_index=True, right_index=True)    # col: job_status

            #print('release_df ', release_df)

            out_zips = exputil.out_zips(aspec.exp_mod, aspec.combo)

            for id,row in release_df.iterrows():
                # Only pay attention to avalanches that have already run
                if id not in out_zips:
                    continue

                # Apply user filter
                out_zip,sizecat = out_zips[id]
                if filter_in_fn(id, row, sizecat, out_zip):
                    ret.append((id,release_file,sizecat,out_zip))

    df = pd.DataFrame(ret, columns=['id', 'release_file', 'sizecat', 'out_zip']).set_index('id')
    df = release_df.merge(df, left_index=True, right_index=True)

    return df
