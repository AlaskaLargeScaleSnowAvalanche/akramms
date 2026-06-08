import datetime,os,pathlib,typing,pyproj
import numpy as np
import netCDF4
from akramms import d_wrf
from uafgi.util import cfutil,ncutil,wrfutil
from scipy.stats import genextreme
import seaborn
import matplotlib.pyplot as plt
import pickle
import pandas as pd
import skextremes
from akramms import config
import gridfill

"""Stuff to go from 3-day collated WRF output to snow fields for RAMMS."""



def _lieblein(data):
    params = skextremes.models.engineering.Lieblein(data)
    return (params.c, params.loc, params.scale)

def _classic_GEV(data):
    params = skextremes.models.classic.GEV(data)
    return (params.c, params.loc, params.scale)

# Step 1
def gen_fits(ifname, include_year0, include_year1):
    """
    ifname:
        Eg: acsnow_agg3_4km_1979_2100.nc

    year0:
        First year to include in fits
    year1:
        Last year (+0) to include in fits
    """

    fit_fns = (genextreme.fit, _lieblein, _classic_GEV)
    fit_names = ('sp', 'en', 'cl')    # SciPy, Engineering, Classical

    with netCDF4.Dataset(ifname) as nc:
        iacsnow = nc.variables['acsnow']

        # Set up to write the output files
        schema = ncutil.Schema(nc)
        XLONG = nc.variables['XLONG'][:]
        XLAT = nc.variables['XLAT'][:]
        del schema.dims['Time']
        del schema.vars['Time']
#        schema.dims['return_periods'] = len(return_periods)
#        schema.vars['return_periods'] = ncutil.NSVar(int, ('return_periods',), {})

        schema.dims['fit'] = 3    # scipy, engineering, classic
        schema.vars['fit'] = ncutil.NSVar(str, ('fit',), {})

        schema.dims['param'] = 3    # c, loc, scale
        schema.vars['param'] = ncutil.NSVar(str, ('param',), {})

        acsnow_v = schema.vars['acsnow']
        acsnow_v.dims = ['fit'] + list(acsnow_v.dims[:2]) + ['param']
    
        # Write output files
#        ofname = ifname.parents[0] / f"{ifname.stem}_fit.nc"
        os.makedirs(ofname.parents[0], exist_ok=True)
        with netCDF4.Dataset(ofname, 'w') as nco:
            schema.create(nco)
            acsnow_shape = nco.variables['acsnow'].shape
#            nco.variables['acsnow'][:] = oacsnow
            nco.variables['XLONG'][:] = XLONG
            nco.variables['XLAT'][:] = XLAT
#            nco.variables['return_periods'][:] = return_periods
            nco.variables['fit'][:] = np.array(['scipy', 'engineering', 'classic'])
            nco.variables['param'][:] = np.array(['c', 'loc', 'scale'])

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
        df['bin_year'] = df['bin_dt0'].map(lambda dt: dt.year)

        # Trim by year range
        df = df[(df.bin_year >= include_year0) & (df.bin_year <= include_year1)]
        dfg = list(df.groupby('bin_dt0'))

        # Fill in the output file
        oacsnow = np.zeros((3, 1, acsnow_shape[2], acsnow_shape[3]))
        for jj in range(acsnow_shape[1]):
            iacsnow_j = iacsnow[jj,:,:]
            print(f'--- jj = {jj}')
            oacsnow += np.nan
            for ii in range(acsnow_shape[2]):
                print(f'acsnow[{jj}, {ii}]')

                # Non-blocked data
                data = iacsnow_j[ii,:]

                # Block it one year at a time
                bdata = np.zeros(len(dfg))
                for blockix,(year,df) in enumerate(dfg):
                    ixs = df.ix
                    bdata[blockix] = np.max(data[ixs])
#                print('bdata ', bdata)


                if np.all(bdata == 0):
                    # Lakes and ocean get no snowfall
                    oacsnow[:,0,ii,:] = 0
                else:
                    # Fit to the GEV distribution
                    for ix,fit_fn in enumerate((genextreme.fit, _lieblein, _classic_GEV)):
                        try:
                            oacsnow[ix,0,ii,:] = fit_fn(bdata)
                        except Exception:
                            print('x')
                            pass


            with netCDF4.Dataset(ofname, 'a') as nco:
                nco.variables['acsnow'][:,jj,:,:] = oacsnow[:,0,:,:]

    print(f'Done writing {ofname}')


def r_fits(ifname, date0, date1):
    pass


gen_fits(pathlib.Path('/home/efischer/av/outputs/wrf_fut_agg3/acsnow_agg3_4km_1979_2100.nc'), 1979,2008)
