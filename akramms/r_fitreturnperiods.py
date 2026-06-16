from uafgi.util import make
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
def gen_fits(ifname, ofname, include_year0, include_year1):
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
#        ofname = ifname.parents[0] / f'{ofstem}_{include_year0:04d}_{include_year1:04d}_fit.nc'
        tmp_fname = ofname.parents[0] / f'{ofname.parts[-1]}.tmp'
        os.makedirs(ofname.parents[0], exist_ok=True)
        with netCDF4.Dataset(tmp_fname, 'w') as nco:
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
#            if jj > 10:        # DEBUG
#                break

            iacsnow_j = iacsnow[jj,:,:]
            print(f'--- jj = {jj}')
            oacsnow += np.nan
            for ii in range(acsnow_shape[2]):
#                print(f'acsnow[{jj}, {ii}]')

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
#                            print('x')
                            pass


            with netCDF4.Dataset(tmp_fname, 'a') as nco:
                nco.variables['acsnow'][:,jj,:,:] = oacsnow[:,0,:,:]

    os.rename(tmp_fname, ofname)

    print(f'Done writing {ofname}')

# ----------------------------------------------------------------------
def r_fits(ifname, ofstem, year0, year1):
    ifname = pathlib.Path(ifname)
    ofname_fit = ifname.parents[0] / f'{ofstem}_{year0:04d}_{year1:04d}_fit.nc'

    def action(tdir):
        return gen_fits(ifname, ofname_fit, year0, year1)

    return make.Rule(action, [ifname], [ofname_fit])

# ----------------------------------------------------------------------

# Step 2
def gen_evt(ifname, geo_fname, ofname, return_periods):
    """Once the fits have been created, use them to produce a value
    for each return period"""

    landmask_in = read_landmask_in(geo_fname)

    rpinvs = [1. - (1./rp) for rp in return_periods]

#    name0 = _single_acsnow_agg3()
#    ifname = name0.parents[0] / f"{name0.stem}_fit.nc"
#    ofname = name0.parents[0] / f"{name0.stem}_evt.nc"

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

    tmp_fname = ofname.parents[0] / f'{ofname.parts[-1]}.tmp'
    with netCDF4.Dataset(tmp_fname, 'w') as nc:
        schema.create(nc)
        nc.variables['acsnow'][:] = oacsnow
        nc.variables['XLONG'][:] = XLONG
        nc.variables['XLAT'][:] = XLAT
        nc.variables['return_periods'][:] = return_periods

    os.rename(tmp_fname, ofname)

def r_evt(ifname_fit, geo_fname, return_periods):
    ifname_fit = pathlib.Path(ifname_fit)
    ofname_evt = ifname_fit.parents[0] / f'{ifname_fit.parts[-1][:-7]}_evt.nc'

    def action(tdir):
        gen_evt(ifname_fit, geo_fname, ofname_evt, return_periods)

    return make.Rule(action, [ifname_fit], [ofname_evt])
# --------------------------------------------------------------------
def read_landmask_in(geo_fname):
#    ifname = config.HARNESS / 'data' / 'waigl' / 'wrf_era5' / f'{RES:02d}km' / 'invar' / 'geo_em.d02.nc'
#    ifname = config.HARNESS / 'data' / 'hutton' / 'wrf_fut' / 'geo_em_files' / 'geo_em_4km.nc'
    with netCDF4.Dataset(geo_fname) as nc:
        landmask_v = nc.variables['LANDMASK']
        landmask = np.zeros(landmask_v.shape[1:], dtype='int8')
        landmask[:] = landmask_v[0,:,:]
    return landmask != 0

def to_geotiff(ifname_evt, geo_fname, return_periods, ofnames):
    landmask_out = np.logical_not(read_landmask_in(geo_fname))

#    geo_fname = config.HARNESS / 'data' / 'waigl' / 'wrf_era5' / '04km' / 'invar' / 'geo_em.d02.nc'
#    geo_fname = config.HARNESS / 'data' / 'hutton' / 'wrf_fut' / 'geo_em_files' / 'geo_em_4km.nc'
#    grid = wrfutil.wrf_info(geo_fname)

#    name0 = _single_acsnow_agg3()
#    ifname = name0.parents[0] / f"{name0.stem}_evt.nc"
    wrf_grid,acsnow,acsnow_nd = wrfutil.read(ifname_evt, 'acsnow', geo_fname)

    for rpix,(return_period,ofname) in enumerate(zip(return_periods, ofnames)):
        ofname = ifname_evt.parents[0] / f'{ifname_evt.parts[-1][:-7]}_{return_period:03d}.tif'

        acsnow_masked = np.ma.masked_array(acsnow[2,:,:,rpix], mask=landmask_out)
        acsnowx, converged = gridfill.fill(acsnow_masked, 1, 0, .1)
#        ofname = name0.parents[0] / f"{name0.stem}_{rp:03d}.tif"
        tmp_fname = ofname.parents[0] / f'{ofname.parts[-1]}.tmp'
        wrfutil.write_geotiff(wrf_grid, acsnowx, tmp_fname)
        os.rename(tmp_fname, ofname)

def r_geotiff(ifname_evt, geo_fname, return_periods):

    ofnames = [ifname_evt.parents[0] / f'{ifname_evt.parts[-1][:-7]}_{return_period:03d}.tif' for return_period in return_periods]

    def action(tdir):
        to_geotiff(ifname_evt, geo_fname, return_periods, ofnames)

    return make.Rule(action, [ifname_evt, geo_fname], ofnames)

# ----------------------------------------------------------------------


#gen_fits(pathlib.Path('/home/efischer/av/outputs/wrf_fut_agg3/acsnow_agg3_4km_1979_2100.nc'), 'xx', 1979,1980)
#gen_fits(pathlib.Path('/home/efischer/av/outputs/wrf_fut_agg3/acsnow_agg3_4km_1979_2100.nc'), 'xx', 1981,1982)
