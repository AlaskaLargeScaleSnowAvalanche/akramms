import datetime,os
import numpy as np
import netCDF4
from akramms import d_wrf
from uafgi.util import cfutil,ncutil
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

    return_periods = (30, 300)
    ifname = d_wrf.single_acsnow_agg3(1940,2023)
    with netCDF4.Dataset(ifname) as nc:
        acsnow_nc = nc.variables['acsnow']
        shape = [len(return_periods)] + list(acsnow_nc.shape[:2])
        oacsnow = np.zeros(shape)

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
#        for ii in range(150,155):
#            for jj in range(280,285):
        for jj in range(shape[1]):
            for ii in range(shape[2]):
                print(f'acsnow[{jj}, {ii}]')

                # Non-blocked data
                data = acsnow_nc[jj,ii,:]

                # Block it one year at a time
                bdata = np.zeros(len(dfg))
                for blockix,(year,df) in enumerate(dfg):
                    ixs = df.ix
                    bdata[blockix] = np.max(data[ixs])
#                print('bdata ', bdata)


                # Fit to the GEV distribution
                params = genextreme.fit(bdata)

                for ix,rp in enumerate(return_periods):
                    oacsnow[ix,jj,ii] = genextreme.ppf(1.-(1./rp), *params)

        # Set up to write the output files
        schema = ncutil.Schema(nc)
        XLONG = nc.variables['XLONG'][:]
        XLAT = nc.variables['XLAT'][:]
        del schema.dims['Time']
        del schema.vars['Time']
        schema.dims['return_periods'] = len(return_periods)
        schema.vars['return_periods'] = ncutil.NSVar(int, ('return_periods',), {})

        acsnow_v = schema.vars['acsnow']
        acsnow_v.dims = ['return_periods'] + list(acsnow_v.dims[:2])

    # Write output files
    ofname = ifname.parents[0] / f"{ifname.stem}_evt.nc"
    for rp in return_periods:
#        stem = ifname.stem
#        print('stem ', type(stem), stem)

        os.makedirs(ofname.parents[0], exist_ok=True)
        with netCDF4.Dataset(ofname, 'w') as nc:
            schema.create(nc)
#            print('shape0 ', nc.variables['acsnow'].shape)
#            print('shape1 ', acsnow.shape)
            nc.variables['acsnow'][:] = oacsnow
            nc.variables['XLONG'][:] = XLONG
            nc.variables['XLAT'][:] = XLAT
            nc.variables['return_periods'][:] = return_periods


#subset_acsnow()
genx()
#main()
