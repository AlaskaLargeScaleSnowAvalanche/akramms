import datetime,os
import numpy as np
import netCDF4
from akramms import d_wrf
from uafgi.util import cfutil
from scipy.stats import genextreme
import seaborn
import matplotlib.pyplot as plt
import pickle
import pandas as pd

#jj,ii = 152,282
#ii,jj = 152,282


def genx():
    os.makedirs('plots/hist', exist_ok=True)
    os.makedirs('plots/rp', exist_ok=True)

    with netCDF4.Dataset(d_wrf.single_acsnow_agg3(1940,2023)) as nc:
        acsnow_nc = nc.variables['acsnow']

        # Develop yearly bins for times
        times = cfutil.read_time(nc, 'Time')
        times = [datetime.date(dt.year, dt.month, dt.day) for dt in times]
        year0 = times[0].year - 1
        yearn = times[-1].year + 1

        bounds = np.array([datetime.date(year,7,1) for year in range(year0,yearn+1)])
        dt0 = bounds[0]
        ibounds = [(dt-dt0).days for dt in bounds]
        itimes = [(dt-dt0).days for dt in times]
        bins = np.digitize(itimes, ibounds)    # Integer says which bin it is in
        bin_dt0 = [bounds[bin-1] for bin in bins]
        bin_dt1 = [bounds[bin] for bin in bins]

        # Divide time into years
        df = pd.DataFrame({'time': times, 'bin': bins})
        df['ix'] = df.index
        df['year'] = df.time.map(lambda dt: dt.year)
        df['bin_dt0'] = bin_dt0
        dfg = list(df.groupby('bin_dt0'))


#        for ii in range(152,153):
#            for jj in range(282,283):
        for ii in range(150,155):
            for jj in range(280,285):

                # Non-blocked data
                data = acsnow_nc[jj,ii,:]

                # Block it one year at a time
                bdata = np.zeros(len(dfg))
                for blockix,(year,df) in enumerate(dfg):
                    ixs = df.ix
                    bdata[blockix] = np.max(data[ixs])
                print('bdata ', bdata)
                data = bdata

                if True:    # Histograms
                    for mx in (2,):
                        datax = data#[data >= mx]
                        ax = seaborn.histplot(datax, stat='density')
#                        ax.set_yscale('log')
#                        ax.set_ylim((1e-4,0.5))
                        fname = f'plots/hist/hist_{jj:03d}_{ii:03d}.png'
                        print('--------------- ', fname)
                        print(datax)

                if True:    # Fit
                    for mx in (2,):
                        datax = data#[data >= mx]
                        params = genextreme.fit(datax)
                        print(f'{jj}, {ii}: c, loc, scale = {params}')
                        xx = np.linspace(1,np.max(datax),100)
                        yy = genextreme.pdf(xx, *params)
                        plt.plot(xx,yy)


                plt.savefig(fname)
                plt.clf()

                if True:
                    # Plot return period max. numbers
#                    rp_3days = np.linspace(1,300*365./3.,50)
#                    rp_years = rp_3days * 3. / 365.
                    rp_years = np.linspace(1,300,50)
                    ppf = np.array([
                        genextreme.ppf(1-(1/rp), *params)
                        for rp in rp_years])
                    plt.plot(rp_years, ppf)
                    plt.savefig(f'plots/rp/rp_{jj:03d}_{ii:03d}.png')
                plt.clf()



#subset_acsnow()
genx()
#main()
