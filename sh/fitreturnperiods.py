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

#jj,ii = 152,282
#ii,jj = 152,282

return_periods = (10,30,100,300)

def _lieblein(data):
    params = skextremes.models.engineering.Lieblein(data)
    return (params.c, params.loc, params.scale)

def _classic_GEV(data):
    params = skextremes.models.classic.GEV(data)
    return (params.c, params.loc, params.scale)


def gen_fits():

    fit_fns = (genextreme.fit, _lieblein, _classic_GEV)
    fit_names = ('sp', 'en', 'cl')    # SciPy, Engineering, Classical

    return_periods = (30, 300)
    ifname = d_wrf.single_acsnow_agg3(1940,2023)

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
        ofname = ifname.parents[0] / f"{ifname.stem}_fit.nc"
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
        dfg = list(df.groupby('bin_dt0'))

        # Fill in the output file
        oacsnow = np.zeros((3, 1, acsnow_shape[2], acsnow_shape[3]))
        for jj in range(acsnow_shape[1]):
        
#        for jj in (139,):
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

def read_landmask_in():
    res = 4
    ifname = config.HARNESS / 'data' / 'waigl' / 'wrf_era5' / f'{res:02d}km' / 'invar' / 'geo_em.d02.nc'
    with netCDF4.Dataset(ifname) as nc:
        landmask_v = nc.variables['LANDMASK']
        landmask = np.zeros(landmask_v.shape[1:], dtype='int8')
        landmask[:] = landmask_v[0,:,:]
    return landmask != 0

def gen_evt():
    """Once the fits have been created, use them to produce a value
    for each return period"""

    landmask_in = read_landmask_in()

    rpinvs = [1. - (1./rp) for rp in return_periods]

    name0 = d_wrf.single_acsnow_agg3(1940,2023)
    ifname = name0.parents[0] / f"{name0.stem}_fit.nc"
    ofname = name0.parents[0] / f"{name0.stem}_evt.nc"

    with netCDF4.Dataset(ifname) as nc:
        schema = ncutil.Schema(nc)
        XLONG = nc.variables['XLONG'][:]
        XLAT = nc.variables['XLAT'][:]
        paramss = nc.variables['acsnow'][:,:,:,:]

    nfit = paramss.shape[0]
    nj = paramss.shape[1]
    ni = paramss.shape[2]

    oacsnow = np.zeros((nfit,nj,ni, len(return_periods)))
    for jj in range(nj):
        print(f'jj = {jj}')
        for ii in range(ni):
            for ifit in range(nfit):
                params = paramss[ifit, jj,ii,:]
                if landmask_in[jj,ii]:
                    oacsnow[ifit,jj,ii,:] = [genextreme.ppf(rpinv, *params) for rpinv in rpinvs]

    for vname in ('param',):
        del schema.dims[vname]
        del schema.vars[vname]
    schema.dims['return_periods'] = len(return_periods)
    schema.vars['return_periods'] = ncutil.NSVar(int, ('return_periods',), {})
    acsnow_v = schema.vars['acsnow']
    acsnow_v.dims = ['fit', acsnow_v.dims[1], acsnow_v.dims[2], 'return_periods']

    with netCDF4.Dataset(ofname, 'w') as nc:
        schema.create(nc)
        nc.variables['acsnow'][:] = oacsnow
        nc.variables['XLONG'][:] = XLONG
        nc.variables['XLAT'][:] = XLAT
        nc.variables['return_periods'][:] = return_periods



def gen_30_300():
    """Find 30y and 300y max 3-day snowfall for all gridcells"""

    os.makedirs('plots/hist', exist_ok=True)
    os.makedirs('plots/rp', exist_ok=True)

    fit_fns = (genextreme.fit, _lieblein, _classic_GEV)
    fit_names = ('sp', 'en', 'cl')    # SciPy, Engineering, Classical

    return_periods = (30, 300)
    ifname = d_wrf.single_acsnow_agg3(1940,2023)
    with netCDF4.Dataset(ifname) as nc:
        acsnow_nc = nc.variables['acsnow']
        shape = [len(return_periods)] + list(acsnow_nc.shape[:2])

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


        # Set up to write the output files
        schema = ncutil.Schema(nc)
        XLONG = nc.variables['XLONG'][:]
        XLAT = nc.variables['XLAT'][:]
        del schema.dims['Time']
        del schema.vars['Time']
        schema.dims['return_periods'] = len(return_periods)
        schema.vars['return_periods'] = ncutil.NSVar(int, ('return_periods',), {})

        schema.vars['acsnow'].dims = ['return_periods'] + list(acsnow_v.dims[:2])

        # Fill in the output files
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
                for (fit_fn, fit_name) in zip(fit_fns, fit_names):
                    #params = genextreme.fit(bdata)    # c, loc, scale
                    params = fit_fn(bdata)    # c, loc, scale

                    for ix,rp in enumerate(return_periods):
                        oacsnow = oacsnows[fit_name]
                        oacsnow[ix,jj,ii] = genextreme.ppf(1.-(1./rp), *params)


    # Write output files
    ofname = ifname.parents[0] / f"{ifname.stem}_evt.nc"
    for rp in return_periods:

        os.makedirs(ofname.parents[0], exist_ok=True)
        with netCDF4.Dataset(ofname, 'w') as nc:
            schema.create(nc)
            nc.variables['acsnow'][:] = oacsnow
            nc.variables['XLONG'][:] = XLONG
            nc.variables['XLAT'][:] = XLAT
            nc.variables['return_periods'][:] = return_periods
# ===========================================================================
class FitRec(typing.NamedTuple):
    bdata: np.ndarray
    oacsnow: list
    params: list

class EVTFit:
    def __init__(self, ifname, return_periods):
        self.ifname = ifname
        self.return_periods = return_periods

    def __enter__(self):
        self.nc = netCDF4.Dataset(self.ifname)
        self.acsnow_nc = self.nc.variables['acsnow']
        self.shape = [len(self.return_periods)] + list(self.acsnow_nc.shape[:2])

        # Develop yearly bins for times
        times = cfutil.read_time(self.nc, 'Time')
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

        self.dfg = list(df.groupby('bin_dt0'))

        return self

    def __exit__(self, typ, value, traceback):
        self.nc.__exit__(typ, value, traceback)


    def fit(self, jj,ii):

        # Non-blocked data
        data = self.acsnow_nc[jj,ii,:]

        # Block it one year at a time
        bdata = np.zeros(len(self.dfg))
        for blockix,(year,df) in enumerate(self.dfg):
            ixs = df.ix
            bdata[blockix] = np.max(data[ixs])
        print(bdata)

        # Fit to the GEV distribution
        params = genextreme.fit(bdata)

        # https://scikit-extremes.readthedocs.io/en/latest/User%20guide.html
        params2 = skextremes.models.engineering.Lieblein(bdata)
        params3 = skextremes.models.classic.GEV(bdata, fit_method='mle', ci=0.05, ci_method='delta')


        print(f'xx: {params}')
        print(f'en: {params2.c}, {params2.loc}, {params2.scale}')
        print(f'cl: {params3.c}, {params3.loc}, {params3.scale}')

        params2 = (params2.c, params2.loc, params2.scale)
        params3 = (params3.c, params3.loc, params3.scale)

        oacsnow = [genextreme.ppf(1.-(1./rp), *params3) for rp in self.return_periods]
#        for ix,rp in enumerate(return_periods):
#            oacsnow[ix,jj,ii] = genextreme.ppf(1.-(1./rp), *params)
        return FitRec(bdata, oacsnow, params3)
# ----------------------------------------------------------
def plot_fit(data, params):
    ax = seaborn.histplot(data, stat='density')

    params = genextreme.fit(data)
    xx = np.linspace(1,np.max(data),100)
    yy = genextreme.pdf(xx, *params)
    plt.plot(xx,yy)


def plot_rp(params):
    # Plot return period max. numbers
    rp_years = np.linspace(1,300,50)
    ppf = np.array([
        genextreme.ppf(1-(1/rp), *params)
        for rp in rp_years])
    plt.plot(rp_years, ppf)

# -----------------------------------------------------------------


def eval_large():
    np.set_printoptions(threshold=np.inf) 

    ifname = pathlib.Path(os.environ['HOME']) / 'av/outputs/wrf_era5_agg3/acsnow_agg3_4km_1940_2023_evt.nc.v1'
    with netCDF4.Dataset(ifname) as nc:
        acsnow_evt = nc.variables['acsnow'][:,:,:]

#    ii,jj = 162,151
#    jj,ii = 139,366
    jj,ii = 139,344
    print(f'acsnow_evt[{jj}, {ii}] = {acsnow_evt[:,jj,ii]}')


    ifname = d_wrf.single_acsnow_agg3(1940,2023)
    with EVTFit(ifname, (30,300)) as evt_fit:
        fit = evt_fit.fit(jj,ii)
        print(fit)

    plot_fit(fit.bdata, fit.params)
    plt.savefig('hist.png')
    plt.clf()
    plot_rp(fit.params)
    plt.savefig('rp.png')
    plt.clf()

        

def to_geotiff():
    landmask_out = np.logical_not(read_landmask_in())

    geo_fname = config.HARNESS / 'data' / 'waigl' / 'wrf_era5' / '04km' / 'invar' / 'geo_em.d02.nc'
#    grid = wrfutil.wrf_info(geo_fname)

    name0 = d_wrf.single_acsnow_agg3(1940,2023)
    ifname = name0.parents[0] / f"{name0.stem}_evt.nc"
    wrf_grid,acsnow,acsnow_nd = wrfutil.read(ifname, 'acsnow', geo_fname)


    with netCDF4.Dataset(ifname) as nc:
        # acsnow(fit, south_north, west_east, return_periods)
#        acsnow = nc.variables['acsnow'][:]
        xlong = nc.variables['XLONG'][:]
        xlat = nc.variables['XLAT'][:]

    xx = wrf_grid.centersx
    yy = wrf_grid.centersy

    xy_x,xy_y = np.meshgrid(xx, yy)

#    wrf_crs = cartopyutil.crs(wrf_grid.wkt)
#    wrf_crs = pyproj.crs.CRS(wrf_grid.wkt)
    proj = pyproj.Proj(wrf_grid.wkt)
#    proj = pyproj.Proj('proj=stere lat_0=90 lat_ts=63.99999237060547 lon_0=-152 x_0=0 y_0=0 R=6370000 nadgrids=@null units=m no_defs')
    print('proj = ', proj)
    print('shapes ', xx.shape, yy.shape)
    xy_long, xy_lat = proj.transform(xy_x, xy_y, direction=pyproj.enums.TransformDirection.INVERSE)

    wrf_x,wrf_y = proj.transform(xlong, xlat)
    print('--------- LON errors')
    print(xlong[0,:3] - xy_long[0,:3])
    print(xlat[0,:3] - xy_lat[0,:3])
    print('--------- X errros')
    print(wrf_x[0,:3] - xy_x[0,:3])
    print(wrf_y[:3,17] - xy_y[:3,17])


    max_err_lon = np.max(np.abs(xlong - xy_long))
    max_err_lat = np.max(np.abs(xlat - xy_lat))
    print('mmmmmmmmmmmmax ', max_err_lon, max_err_lat)



    for rpix,rp in enumerate(return_periods):
        acsnow_masked = np.ma.masked_array(acsnow[2,:,:,rpix], mask=landmask_out)
        acsnowx, converged = gridfill.fill(acsnow_masked, 1, 0, .1)
        ofname = name0.parents[0] / f"{name0.stem}_{rp:03d}.tif"
        wrfutil.write_geotiff(wrf_grid, acsnowx, ofname)

#    res=4
#    print(grid)


#examine()


#eval_large()
#gen_fits()
#gen_evt()

to_geotiff()


