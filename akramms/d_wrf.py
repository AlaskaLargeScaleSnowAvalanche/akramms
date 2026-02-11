import datetime,os,sys
import numpy as np
import pandas as pd
import netCDF4
from uafgi.util import ncutil,cfutil
from akramms import config

def era5_wrf_dscale(date, res=4):
    """Produces filename from Chris Waigl input dataset"""
    if date is None:
        date = datetime.date(1940,3,12)    # Sample date
    return config.HARNESS / 'data' / 'waigl' / 'wrf_era5' / f'{res:02d}km' / f'{date.year:04d}' / f'era5_wrf_dscale_{res}km_{date:%Y-%m-%d}.nc'

def era5_wrf_dscale_agg3(olabel, res=4):
    olabel = str(olabel)    # year
    return config.HARNESS / 'outputs' / 'wrf_era5_agg3' / f'{res:02d}km' / f'acsnow_agg3_{res}km_{olabel}.nc'

def single_acsnow_agg3(year_first, year_last, res=4):
    olabel = f'{year_first}_{year_last}'
    return config.HARNESS / 'outputs' / 'wrf_era5_agg3' / f'acsnow_agg3_{res}km_{olabel}.nc'


def agg3_one(dt0, dt1, olabel, res=4):
    """Create new timeseries of 3-day snowfall and write to a SINGLE output file"""
    print(f'======= agg3_one: {dt0}, {dt1}, {olabel}')

    now = datetime.datetime.now()
    with netCDF4.Dataset(era5_wrf_dscale(None, res=res)) as nc:
        schema = ncutil.Schema(nc)
        XLONG = nc.variables['XLONG'][:]
        XLAT = nc.variables['XLAT'][:]

    # Modify the schema for what we will write out
    keeps = ('Time', 'XLONG', 'XLAT', 'acsnow')
    schema.keep_only_vars(*keeps)
#    schema.vars = {key: schema.vars[key] for key in keeps}
    ndays = (dt1 - dt0).days // 3
    schema.dims['Time'] = ndays
    Time = schema.vars['Time']
    Time.attrs['units'] = f"days since {dt0:%Y-%m-%d} 00:00:00"

    schema.attrs['date'] = now.isoformat()
    schema.attrs['data'] = f"Three-day aggregation derived from: {schema.attrs['data']}"
    schema.attrs['contact'] = 'eafischer2@alaska.edu'
    acsnow = schema.vars['acsnow']
    acsnow.attrs['description'] = 'Accumulated Snow over 3 Days'


    # Allocate our variable
    sshape = list(schema.vars['acsnow'].dims)    # Dimension names
    shape = [schema.dims[x] for x in sshape]    # Dimension lengths
    print(f'Allocated acsnow[{shape}]')
#    print('shape ', shape)
#    print('ndays ', ndays)
    acsnow = np.zeros(shape)
    Time = np.zeros(shape[0])

    # Aggregate three days
    for ix in range((dt1-dt0).days // 3):
        # Start of 3-day range to aggregate.  This will be the label we use...
        dtt0 = dt0 + datetime.timedelta(days=ix*3)
        Time[ix] = ix*3

        for daydelta1 in range(0,3):
            dtt = dtt0 + datetime.timedelta(days=daydelta1)
            ifname = era5_wrf_dscale(dtt, res=res)
            if not os.path.exists(ifname):
                raise ValueError(f'Path not exists: {ifname}')
#                acsnow[ix,:] = np.nan    # Blank out 3-day agg this belongs to
            else:
                print(f'Reading {ix} <- {ifname}')
                sys.stdout.flush()
                with netCDF4.Dataset(ifname) as nc:
                    nc.set_always_mask(False)
                    acsnow[ix,:] += np.sum(nc.variables['acsnow'][:],0)

    # Write out to agg3 file
    ofname = era5_wrf_dscale_agg3(olabel, res=res)
    print(f'Writing {ofname}')
    os.makedirs(ofname.parents[0], exist_ok=True)
    with netCDF4.Dataset(ofname, 'w') as nc:
        schema.create(nc)
        nc.variables['acsnow'][:] = acsnow
        nc.variables['Time'][:] = Time
        nc.variables['XLONG'][:] = XLONG
        nc.variables['XLAT'][:] = XLAT

def agg3(dt0, dt1, res=4):

    # Split up range into 1-year segments
    year = dt0.year
    dates = [dt0 + datetime.timedelta(days=x) for x in range((dt1-dt0).days)]
    dates = dates[0::3]    # Take every 3d element
    df = pd.DataFrame({'date': dates})
    df['year'] = df.date.apply(lambda date: date.year)
    bounds = [(year, df.date.iloc[0]) for year,df in df.groupby('year')] + [(None, dt1)]
    ranges = [(b0[0], b0[1], b1[1]) for b0,b1 in zip(bounds[:-1], bounds[1:])]

    for year,dt0,dt1 in ranges:
        agg3_one(dt0, dt1, str(year))


def read_agg3(year0, year1, res=4):
    fnames = [era5_wrf_dscale_agg3(year) for year in range(year0, year1)]

    # Figure out dimensions
    ntime = 0
    for fname in fnames:
        with netCDF4.Dataset(fname) as nc:
            ntime += len(nc.dimensions['Time'])
            shape = nc.variables['acsnow'].shape

    # Allocate overall array
    times = list()
    acsnow = np.zeros((shape[1], shape[2], ntime))

    # Read into the array
    ix = 0
    for fname in fnames:
        print(f'Reading {fname}')
        with netCDF4.Dataset(fname) as nc:
            nc.set_auto_mask(False)
            n = len(nc.dimensions['Time'])
            times += list(cfutil.read_time(nc, 'Time'))
            acs = nc.variables['acsnow'][:]
            acsnow[:,:,ix:ix+n] = np.transpose(acs, (1,2,0))
            ix += n
    return acsnow,times,fnames

def write_single_agg3(year_first, year_last, res=4):
    # Read original (and transpose while reading)
    acsnow,times,fnames = read_agg3(year_first, year_last+1, res=res)

    # Get the schema
    with netCDF4.Dataset(fnames[0]) as nc:
        schema = ncutil.Schema(nc)
        XLONG = nc.variables['XLONG'][:]
        XLAT = nc.variables['XLAT'][:]

    now = datetime.datetime.now()

    # Modify the schema for what we will write out
    schema.dims['Time'] = len(times)

    schema.attrs['date'] = now.isoformat()
    schema.attrs['data'] = f"Three-day aggregation derived from: {schema.attrs['data']}"
    schema.attrs['contact'] = 'eafischer2@alaska.edu'
    schema.vars['acsnow'].attrs['description'] = 'Accumulated Snow over 3 Days'

    # Tranpose dims on acsnow
    ddims = schema.vars['acsnow'].dims
    schema.vars['acsnow'].dims = (ddims[1], ddims[2], ddims[0])

    # Write out to agg3 file
    ofname = single_acsnow_agg3(year_first, year_last, res=res)
    print(f'Writing {ofname}')
    os.makedirs(ofname.parents[0], exist_ok=True)
    with netCDF4.Dataset(ofname, 'w') as nc:
        schema.create(nc)
        print('shape0 ', nc.variables['acsnow'].shape)
        print('shape1 ', acsnow.shape)
        nc.variables['acsnow'][:] = acsnow
        nc.variables['Time'][:] = np.array([(t - times[0]).days for t in times])
        nc.variables['XLONG'][:] = XLONG
        nc.variables['XLAT'][:] = XLAT
