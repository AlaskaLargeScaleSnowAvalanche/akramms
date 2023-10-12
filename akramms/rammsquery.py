import os
import pandas as pd
from akramms import rammsfilter
from akramms.util import exputil,rammsutil


# Queries avalanches in their RAMMS form, without archiving.

def query_aspecs(aspecs, filter_in_fn=rammsfilter.all):
    ret = list()
    for aspec in aspecs:
        # Info from all release files in the combo
        release_files, release_df = exputil.release_df(aspec.exp_mod, aspec.combo, type='x')

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
