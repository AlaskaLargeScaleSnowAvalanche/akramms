import datetime,pickle,pandas,pathlib,re,os
import netCDF4
import pandas as pd
from uafgi.util import make
from akramms import d_wrf,config

idir = config.HARNESS / 'outputs' / 'wrf_fut_check'

yearRE = re.compile(r'check_([_0-9]+)km_(\d\d\d\d)\.nc')

def analyze(res):

    sres = d_wrf.fut_sres[res]
    idir_res = idir / f'{sres}km'

    dfs = list()
    for name in sorted(os.listdir(idir_res)):
        df = pd.read_pickle(idir_res / name)
        dfs.append(df)

    df = pd.concat(dfs)

    all_vars = set()
    for vars in df.variables:
        all_vars.update(vars)
    all_vars = sorted(all_vars)
#    print('all_vars ', all_vars)


    rows = list()
    in_all = set(df.iloc[0].variables)
    for tup in df.itertuples(index=False):
#        print(tup)
#    for vars in set(df.variables):
        vars = set(tup.variables)
        
        row = [tup.resolution, tup.date] + ['x' if v in vars else None for v in all_vars]
        rows.append(row)

    df = pd.DataFrame(rows, columns=['resolution', 'date'] + all_vars)
    df.to_csv(idir / f'check_{sres}km.csv')


    df = df[['resolution', 'date', 'acsnow']]
    df = df[df.acsnow.isna()]

    print(df)
    return



    print(df)
#        print(name)


def main():
#    analyze(4)
#    analyze(1.33)
    analyze(12)

