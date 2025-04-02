import datetime,os
import numpy as np
import netCDF4
#from akramms import d_wrf
from scipy.stats import genextreme
import seaborn
import matplotlib.pyplot as plt
import pickle

#jj,ii = 152,282
ii,jj = 152,282

def main():

    fnames = [d_wrf.era5_wrf_dscale_agg3(year) for year in range(1940,1957)]

    # Figure out dimensions
    ntime = 0
    for fname in fnames:
        with netCDF4.Dataset(fname) as nc:
            ntime += len(nc.dimensions['Time'])
            shape = nc.variables['acsnow'].shape

    # Allocate overall array
    Time = list()
    acsnow = np.zeros((ntime, shape[1], shape[2]))


    # Read into the array
    ix = 0
    for fname in fnames:
        print(f'Reading {fname}')
        with netCDF4.Dataset(fname) as nc:
            nc.set_auto_mask(False)
            n = len(nc.dimensions['Time'])
            acs = nc.variables['acsnow'][:]
            print('val ', acs[:,jj,ii])
            acsnow[ix:ix+n,:] = acs[:]
            ix += n

    with open('acsnow.pik', 'wb') as out:
        pickle.dump(acsnow, out)

def xyz():

#    jj = acsnow.shape[1] // 2
#    ii = acsnow.shape[2] // 2
    data = acsnow[:,jj,ii]
    print(list(data))
    fit = genextreme.fit(data)
    print(fit)

def subset_acsnow():
    with open('acsnow.pik', 'rb') as fin:
        acsnow = pickle.load(fin)

    acsub = acsnow[:, 270:290, 140:160]
    with open('acsub.pik', 'wb') as out:
        pickle.dump(acsub, out)

def genx():
    with open('acsub.pik', 'rb') as fin:
        acsub = pickle.load(fin)

    acsub = acsub[:,-3:,-3:]

    os.makedirs('plots', exist_ok=True)
    os.makedirs('rps', exist_ok=True)
    for jj in range(acsub.shape[1]):
        for ii in range(acsub.shape[2]):
#    for jj in (0,):
#        for ii in (2,):
            data = acsub[:,jj,ii]

            if True:    # Histograms
                for mx in (2,):
                    datax = data[data >= mx]
                    ax = seaborn.histplot(datax, stat='density')
                    ax.set_yscale('log')
                    ax.set_ylim((1e-4,0.5))
                    fname = f'plots/plot_{jj:02d}_{ii:02d}.png'
                    print('--------------- ', fname)
                    print(datax)

            for mx in (2,):
                datax = data[data >= mx]
                params = genextreme.fit(datax)
                print(f'{jj}, {ii}: c, loc, scale = {params}')
                xx = np.linspace(1,30,200)
                yy = genextreme.pdf(xx, *params)
                plt.plot(xx,yy)


            plt.savefig(fname)
            plt.clf()

            # Plot return period max. numbers
            rp_3days = np.linspace(1,300*365./3.,50)
            rp_years = rp_3days * 3. / 365.
            ppf = np.array([
                genextreme.ppf(1-(1/rp), *params)
                for rp in rp_3days])
            plt.plot(rp_years, ppf)
            plt.savefig(f'rps/rp_{jj:02d}_{ii:02d}.png')


def geny():
#    data = np.random.normal(loc=5.0, scale=1.0, size=1000000)

    for block_size in (100,1000,10000):
        # Split into blocks (years)
        num_blocks = np.floor(len(data) / block_size)
        blocks = np.split(data, num_blocks)
        block_maxima = np.max(blocks, axis=1)

#        print('block_maxima size ', block_maxima)
        params = genextreme.fit(block_maxima)
        print(f'c, loc, scale = {params}')

#        return_periods = np.linspace(1,300,50)
        rp_3days = np.linspace(1,300*365./3.,50)
        rp_years = rp_3days * 3 / 365.
        ppf = np.array([
            genextreme.ppf(1-(1/return_period), *params)
            for return_period in rp_3days])

#        print(ppf)
        plt.plot(rp_years, ppf)

#    ax = seaborn.histplot(block_maxima)
    plt.show()

#    print(data)
#    fit = genextreme.fit(data)
#   print(fit)
#    print(np.random.normal.fit(data))

    fit = genextreme.fit(data)
    print(fit)
    print(np.random.normal.fit(data))

#subset_acsnow()
genx()
#main()
