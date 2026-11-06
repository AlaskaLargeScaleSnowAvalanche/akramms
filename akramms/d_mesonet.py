import subprocess,os,calendar
from uafgi.util import make
import numpy as np
import pandas as pd
from akramms import config

# https://mesonet.agron.iastate.edu/request/coop/fe.phtml?network=AKCLIMATE

#URL_TPL = 'https://mesonet.agron.iastate.edu/cgi-bin/request/coop.py?network={network}&stations=_ALL&year1={year1}&month1={month1}&day1={day1}&year2={year2}&month2={month2}&day2={day2}&vars%5B%5D=high&vars%5B%5D=highc&vars%5B%5D=low&vars%5B%5D=lowc&vars%5B%5D=temp_estimated&vars%5B%5D=precip&vars%5B%5D=precipmm&vars%5B%5D=precip_estimated&vars%5B%5D=snow&what=download&delim=comma&gis=yes&scenario_year=2025'

URL_TPL = 'https://mesonet.agron.iastate.edu/cgi-bin/request/coop.py?network={network}&stations=_ALL&year1={year}&month1={month}&day1=1&year2={year}&month2={month}&day2={nday}&vars%5B%5D=highc&vars%5B%5D=lowc&vars%5B%5D=temp_estimated&vars%5B%5D=precipmm&vars%5B%5D=precip_estimated&vars%5B%5D=snow&what=download&delim=comma&gis=yes&scenario_year=2025'

#  ----------------------------------------------
def get_month_fname(year, month, network='AKCLIMATE'):
    dir = config.HARNESS / f'data/fischer/{network}'
    ofname = dir / f'{network}_{year:04d}_{month:02d}.csv'
    return ofname


def r_download_month(year, month, network='AKCLIMATE'):
    ofname = get_month_fname(year, month, network=network)
    tmp_fname = str(ofname) + '.tmp'

    def action(tdir):
        os.makedirs(ofname.parents[0], exist_ok=True)

        _, nday = calendar.monthrange(year, month)

        # https://mesonet.agron.iastate.edu/request/coop/fe.phtml?network={network}
#        url = URL_TPL.format(year1=year, month1=month, day1=1, year2=year, month2=month, day2=ndays, network=network)
        url = URL_TPL.format(year=year, month=month, nday=nday, network=network)
        cmd = ['curl', url, '-o', str(tmp_fname)]
        print(' '.join(cmd))
        subprocess.run(cmd, check=True)
        os.rename(tmp_fname, ofname)

    return make.Rule(action, [], [ofname])

def get_month(year, month, network='AKCLIMATE'):
    ifname = get_month_fname(year, month, network=network)
    df = pd.read_csv(ifname, comment='#')

    df = df.replace('M', np.nan)
    try:
        df = df.apply(pd.to_numeric)
    except Exception:
        pass

    df['date'] = pd.to_datetime(df.day, format="%Y/%m/%d")
    df = df.drop(columns='day')

    return df

def get(first_year, last_year):
    dfs = list()
    for year in range(first_year, last_year+1):
        for month in range(1,13):
            print(f'Loading {year}_{month}')
            dfs.append(get_month(year, month))
    df = pd.concat(dfs)
    return df


