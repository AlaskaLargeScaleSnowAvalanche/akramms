import datetime
from akramms import d_wrf

def wrf_fname_max3(olabel, res=4, dataset='era5'):
    olabel = str(olabel)    # year
    if dataset == 'era5':
        return config.HARNESS / 'outputs' / 'wrf_era5_max3' / f'{res:02d}km' / f'acsnow_max3_{res}km_{olabel}.nc'
    else:
        skm = fut_sres[res]
        return config.HARNESS / 'outputs' / 'wrf_fut_max3' / f'{skm}km' / f'acsnow_max3_{skm}km_{olabel}.nc'
# ----------------------------------------------------
# ----------------------------------------------------
def max_rolling_sum(arr, k):
    """
    Calculates the maximum of the rolling sum of an array 'arr' with window size 'k'.
    arr[time, :]
        Arry to sum over 0th dimension
    """

    result = 
    cur_window_sum = np.sum(arr[:k,:], keepdims=False)
# ----------------------------------------------------
def max_rolling_sum(dt0, dt1, k=72)
# ----------------------------------------------------
# ----------------------------------------------------
class DailyWrfData:
    def __init__(self, dt0, vname='acsnow', res=res, dataset=dataset):
        self.dt0 = dt0    # Origin date
        self.vname = vname
        self.res = res
        self.dataset = dataset
        self.cur_ix = -1

    def __getitem__(self, ix):
        if ix != self.cur_ix:
            dt = self.dt0 + datetime.timedelta(days=idt)
            ifname = wrf_fname(dtt, res=res, dataset=dataset)
            with netCDF4.Dataset(ifname) as nc:
                nc.set_always_mask(False)
                self.cur_data = nc.variables[self.vname][:]
            self.cur_ix = ix

        return self.cur_data

class HourlyWrfData:
    """Turns WRF data into a conceptual hourly array"""
    def __init__(self, dt0, **kwargs):
        self.daily = DailyWrfData(dt0, **kwargs)

    def __getitem__(self, ihr):
        idt,hour_in_day = divmod(ihr, 24)
        daily_data = self.daily[idt]
        hourly_data = daily_data[hour_in_day,:]
        return hourly_data
#        dt = self.dt0 + datetime.timedelta(days=idt)
        
# ----------------------------------------------------

# ----------------------------------------------------
sres = {
    12: '12',
    4: '4',
    1.33: '1_33',
}
def r_max3_range(dt0, dt1, olabel, vname='acsnow', res=4, dataset='era5'):
    """Computes the max 3-day snowfall within a date range (exclusive)"""

    ofname = config.HARNESS / 'outputs' / f'wrf_{dataset}_max3' / f'{res:02d}km' / f'max3_{vname}_{sres[res]}km_{dt0:%Y%m%d}_{dt1:%Y%m%d}.nc'

 #   ofname = wrf_fname_max3(olabel, res=res, dataset=dataset)

    def action_fn(tdir):
        """Create new timeseries of 3-day snowfall and write to a SINGLE output file"""
        print(f'======= agg3_one: {dt0}, {dt1}, {olabel}, {dataset}')

        now = datetime.datetime.now()
    #    dt0 = datetime.date(1979,7,1)
    ##    dt0 = datetime.date(1957,1,1)
    #    dt1 = datetime.date(2099,1,1)
        with netCDF4.Dataset(d_wrf.wrf_fname(None, res=res, dataset=dataset)) as nc:
            schema = ncutil.Schema(nc)
            XLONG = nc.variables['XLONG'][:]
            XLAT = nc.variables['XLAT'][:]

        # Modify the schema for what we will write out
        keeps = ('Time', 'XLONG', 'XLAT', vname)
        schema.keep_only_vars(*keeps)
    #    schema.vars = {key: schema.vars[key] for key in keeps}
#        ndays = (dt1 - dt0).days // 3
#        schema.dims['Time'] = ndays
#        Time = schema.vars['Time']
#        Time.attrs['units'] = f"days since {dt0:%Y-%m-%d} 00:00:00"

        schema.attrs['date'] = now.isoformat()
        schema.attrs['data'] = f"Three-day aggregation derived from: {schema.attrs['data']}"
        schema.attrs['contact'] = 'eafischer2@alaska.edu'
        acsnow = schema.vars[vname]
        acsnow.attrs['description'] = 'Accumulated Snow over 3 Days'
        del acsnow.dims['Time']

        # Allocate our variable
        sshape = list(schema.vars['acsnow'].dims)    # Dimension names
        shape = [schema.dims[x] for x in sshape]    # Dimension lengths
        print(f'Allocated acsnow[{shape}]')
    #    print('shape ', shape)
    #    print('ndays ', ndays)
        max_3day = np.zeros(shape)
        Time = np.zeros(shape[0])


        # Start the rolling sum over 72 hours
        dataset = HourlyWrfData(dt0, vname=vname, res=res, dataset=dataset)
        k = 72    # Size of window
        nix = 24 * (dt1 - dt0).days
        buf = list()
        cur_sum = np.zeros(shape)
        for ix in range(k):
            val = dataset[ix]
            buf.append(val)
            cur_sum += val
        cur_max = cur_sum.copy()

        for ix in range(k, nix):
            buf.append(dataset[ix])
            cur_sum -= buf[0]
            cur_sum += buf[-1]
            buf = buf[1:]
            cur_max = np.maximum(cur_max, cur_sum)

        # Write out to max3 file
        print(f'Writing {ofname}')
        os.makedirs(ofname.parents[0], exist_ok=True)
        tmp_fname = str(ofname) + '.tmp'
        with netCDF4.Dataset(tmp_fname, 'w') as nc:
            schema.create(nc)
            nc.variables[vname][:] = cur_max
            nc.variables['Time'][:] = Time
            nc.variables['XLONG'][:] = XLONG
            nc.variables['XLAT'][:] = XLAT
        os.rename(tmp_fname, ofname)

    return make.Rule(action_fn, [], [ofname])



# ----------------------------------------------------

def main():
    dt0 = datetime.date(1979,7,1)
#    dt0 = datetime.date(1957,1,1)
    dt1 = datetime.date(2100,7,1)
    d_wrf.agg3(dt0, dt1, dataset='fut')

main()

#d_wrf.write_single_agg3(1979, 1981, res=4, dataset='fut')
#d_wrf.write_single_agg3(1979, 2100, res=4, dataset='fut')
#d_wrf.write_single_agg3(1979, 2100, res=1.33, dataset='fut')

# ----------------------------------------------------

def mainx():
    dt0 = datetime.date(1940,1,1)
#    dt0 = datetime.date(1957,1,1)
    dt1 = datetime.date(2023,7,2)
    d_wrf.agg3(dt0, dt1, dataset='era5')


# This is step 2
#d_wrf.write_single_agg3(1940, 2023, dataset='era5')



#main()
