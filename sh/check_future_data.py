import datetime,pickle,pandas,pathlib,re,os
import netCDF4
import pandas as pd
from uafgi.util import make
from akramms import d_wrf,config

odir = config.HARNESS / 'outputs' / 'wrf_fut_check'

dayRE = re.compile(r'wrf_dscale_([_0-9]+)km_(\d\d\d\d)-(\d\d)-(\d\d)\.nc')

def r_check(res, year):
    import os

    sres = d_wrf.fut_sres[res]
    idir = config.HARNESS / 'data' / 'hutton' / 'wrf_fut' / f'{sres}km' / f'{year:04d}'
    ofname = odir / f'{sres}km' / f'check_{sres}km_{year:04d}.pik'
    otmp = odir / f'{sres}km' / f'check_{sres}km_{year:04d}.pik.tmp'

    def action(tdir):
        rows = list()
        print('listing ', idir)
        for name in sorted(os.listdir(idir)):
            match = dayRE.match(name)
            if match is None:
                continue
            ifname = idir / name

            date = datetime.date(int(match.group(2)), int(match.group(3)), int(match.group(4)))

            with netCDF4.Dataset(ifname) as nc:
                vars = list(nc.variables)
            row = (res, date, vars)
            print((row[0], row[1], len(row[2])))
            rows.append(row)

        df = pd.DataFrame(rows, columns=('resolution', 'date', 'variables'))
        print(df)
        os.makedirs(ofname.parents[0], exist_ok=True)
        df.to_pickle(otmp)
        os.rename(otmp, ofname)    # Atomic

    return make.Rule(action, [], [ofname])
            

def main():

    makefile = make.Makefile()
#    for res in (4,1.33,12):
    for res in (4,1.33,12):
        for year in range(1979,2101):
#        for year in range(1979,1990):
            rule = r_check(res, year)
            makefile.add(rule)

    makefile.generate(odir / 'check.mk', run=True, ncpu=20)


def xxx():

    dt0 = datetime.date(1979,7,1)
    dt1 = datetime.date(2099,1,1)



    rows = list()

    dataset = 'fut'
    for res in (1.33,4,12):
        dt = dt0
        while dt < dt1:

            ifname = d_wrf.wrf_fname(dt, res=res, dataset=dataset)
            print(ifname)

            with netCDF4.Dataset(ifname) as nc:
                print(list(nc.variables))

            rows.append((res, dt, list(nc.variables)))


#            break

            # loop around
            dt += datetime.timedelta(days=1)

    df = pd.DataFrame(rows, columns=('resolution', 'date', 'variables'))

    print(df)

    ofname = 'all_vars.pik'
    with open(ofname,'wb') as out:
        pickle.dump(df, out)






