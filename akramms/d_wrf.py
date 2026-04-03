import datetime,os,sys,typing,pathlib
import numpy as np
import pandas as pd
import netCDF4
from uafgi.util import ncutil,cfutil,make
from akramms import config

# Datasets:
# era5: Downscaled ERA5 (past) from Chris Waigl
# fut: Downscaled future GCM predictions from Tricia Hutton

class DatasetInfo(typing.NamedTuple):
    root: pathlib.Path

# ------------------------------------------------------------
# Dataset: wrf_era5
fut_sres = {12: '12', 4: '4', 1.33: '1_33'}

_missing_dates = {
    (datetime.date(1991,8,19), 4, 'fut'),
    (datetime.date(2000,10,11), 4, 'fut'),
    (datetime.date(1989,11,11), 12, 'fut'),
}


def wrf_fname(date, res=4, dataset='era5'):
    """Produces filename from Chris Waigl input dataset"""

    # Use the previous day for a few missing spot dates
    if (date,res,dataset) in _missing_dates:
        date -= datetime.timedelta(days=1)

    if dataset == 'era5':
        if date is None:
            date = datetime.date(1940,3,12)    # Sample date
        return config.HARNESS / 'data' / 'waigl' / 'wrf_era5' / f'{res:02d}km' / f'{date.year:04d}' / f'era5_wrf_dscale_{res}km_{date:%Y-%m-%d}.nc'
    else:
        if date is None:
            date = datetime.date(1979,7,1)    # Sample date
        skm = fut_sres[res]
        return config.HARNESS / 'data' / 'hutton' / 'wrf_fut' / f'{skm}km' / f'{date.year:04d}' / f'wrf_dscale_{skm}km_{date:%Y-%m-%d}.nc'


def wrf_fname_agg3(olabel, res=4, dataset='era5'):
    olabel = str(olabel)    # year
    if dataset == 'era5':
        return config.HARNESS / 'outputs' / 'wrf_era5_agg3' / f'{res:02d}km' / f'acsnow_agg3_{res}km_{olabel}.nc'
    else:
        skm = fut_sres[res]
        return config.HARNESS / 'outputs' / 'wrf_fut_agg3' / f'{skm}km' / f'acsnow_agg3_{skm}km_{olabel}.nc'
# ------------------------------------------------------------







def single_acsnow_agg3(year_first, year_last, res=4, dataset='era5'):
    olabel = f'{year_first}_{year_last}'
    if dataset == 'era5':
        return config.HARNESS / 'outputs' / 'wrf_era5_agg3' / f'acsnow_agg3_{res}km_{olabel}.nc'
    else:
        skm = fut_sres[res]
        return config.HARNESS / 'outputs' / 'wrf_fut_agg3' / f'acsnow_agg3_{skm}km_{olabel}.nc'


def r_agg3_one(dt0, dt1, olabel, res=4, dataset='era5'):

    ofname = wrf_fname_agg3(olabel, res=res, dataset=dataset)

    def action_fn(tdir):
        """Create new timeseries of 3-day snowfall and write to a SINGLE output file"""
        print(f'======= agg3_one: {dt0}, {dt1}, {olabel}, {dataset}')

        now = datetime.datetime.now()
    #    dt0 = datetime.date(1979,7,1)
    ##    dt0 = datetime.date(1957,1,1)
    #    dt1 = datetime.date(2099,1,1)
        with netCDF4.Dataset(wrf_fname(None, res=res, dataset=dataset)) as nc:
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
                ifname = wrf_fname(dtt, res=res, dataset=dataset)
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
        print(f'Writing {ofname}')
        os.makedirs(ofname.parents[0], exist_ok=True)
        tmp_fname = str(ofname) + '.tmp'
        with netCDF4.Dataset(tmp_fname, 'w') as nc:
            schema.create(nc)
            nc.variables['acsnow'][:] = acsnow
            nc.variables['Time'][:] = Time
            nc.variables['XLONG'][:] = XLONG
            nc.variables['XLAT'][:] = XLAT
        os.rename(tmp_fname, ofname)

    return make.Rule(action_fn, [], [ofname])

def agg3(dt0, dt1, res=4, dataset='era5'):


    # Split up range into 1-year segments
    year = dt0.year
    dates = [dt0 + datetime.timedelta(days=x) for x in range((dt1-dt0).days)]
    dates = dates[0::3]    # Take every 3d element
    df = pd.DataFrame({'date': dates})
    df['year'] = df.date.apply(lambda date: date.year)
    bounds = [(year, df.date.iloc[0]) for year,df in df.groupby('year')] + [(None, dt1)]
    ranges = [(b0[0], b0[1], b1[1]) for b0,b1 in zip(bounds[:-1], bounds[1:])]

    makefile = make.Makefile()
    for res in (4,1.33):
        for year,dt0,dt1 in ranges:
            rule = r_agg3_one(dt0, dt1, str(year), res=res, dataset=dataset)
            makefile.add(rule)

    odir = config.HARNESS / 'outputs' / 'wrf_era5_agg3'
    makefile.generate(odir / 'agg3.mk', run=True, ncpu=20)
#    makefile.generate(odir / 'agg3.mk', run=True, ncpu=20)
    


def read_agg3(year0, year1, res=4, dataset='ear5'):
    fnames = [wrf_fname_agg3(year, dataset=dataset) for year in range(year0, year1)]

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

def write_single_agg3(year_first, year_last, res=4, dataset='era5'):
    # Read original (and transpose while reading)
    acsnow,times,fnames = read_agg3(year_first, year_last+1, res=res, dataset=dataset)

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
    ofname = single_acsnow_agg3(year_first, year_last, res=res, dataset=dataset)
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
