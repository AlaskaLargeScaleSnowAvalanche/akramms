import datetime
import numpy as np
import netCDF4
#from akramms import d_wrf
from scipy.stats import genextreme
import seaborn
import matplotlib.pyplot as plt

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

    jj,ii = 152,282

    # Read into the array
    ix = 0
    for fname in fnames:
        print(f'Reading {fname}')
        with netCDF4.Dataset(fname) as nc:
            n = len(nc.dimensions['Time'])
            acs = nc.variables['acsnow'][:]
            print('val ', acs[:,jj,ii])
            acsnow[ix:ix+n,:] = acs[:]
            ix += n

#    jj = acsnow.shape[1] // 2
#    ii = acsnow.shape[2] // 2
    data = acsnow[:,jj,ii]
    print(list(data))
    fit = genextreme.fit(data)
    print(fit)

def genx():
    data = np.random.normal(loc=5.0, scale=1.0, size=1000000)

    for block_size in (100,1000,10000):
        # Split into blocks (years)
        num_blocks = np.floor(len(data) / block_size)
        blocks = np.split(data, num_blocks)
        block_maxima = np.max(blocks, axis=1)

#        print('block_maxima size ', block_maxima)
        params = genextreme.fit(block_maxima)
        print(f'c, loc, scale = {params}')

        return_periods = np.linspace(1,300,50)
        ppf = np.array([
            genextreme.ppf(1-(1/return_period), *params)
            for return_period in return_periods])

#        print(ppf)
        plt.plot(return_periods, ppf)

#    ax = seaborn.histplot(block_maxima)
    plt.show()

#    print(data)
#    fit = genextreme.fit(data)
#   print(fit)
#    print(np.random.normal.fit(data))

genx()
#main()
