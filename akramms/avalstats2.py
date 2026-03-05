import os,copy,functools,itertools,subprocess,sys,itertools
import numpy as np
from osgeo import gdalconst
from uafgi.util import gisutil, gdalutil,ioutil,make
import akramms.parse
from akramms import avalquery,config

_last_idom_jdom = None
_last_ocean_mask = None

@functools.lru_cache()
def _section(expmod, combo, bar='-'):
    # Get name of section within publish eg: ak-ccsm-1981-2010-lapse-All-30
    lcombo = str(combo).split('-')
    section =  expmod.name + bar + bar.join(lcombo[:-2])
    return section

def _read_land_data(expmod, idom, jdom, imosaic_grid, tdir):
    """Read the ocean mask"""
    global _last_idom_jdom, _last_ocean_mask

    # Extract landcover for (idom,jdom) tile into temporary file
    ijpoly = expmod.gridD.poly(idom, jdom, margin=False)
    landcover_tif = tdir.filename(suffix='.tif')
    expmod.extract_landcover(ijpoly, landcover_tif)

    landcover30_grid, landcover30_data, landcover30_nd = gdalutil.read_raster(landcover_tif)    # landcover_grid includes margin

    # 11 = ocean, 0 = outside domain
    land30_mask = np.logical_and(landcover30_data != 11, landcover30_data != 0)
    land30_nd = 100    # Doesn't really matter, land30_data is either 0 or 1

    land30_data = np.zeros(landcover30_data.shape)
    land30_data[land30_mask] = 1

    # Regrid land mask to same grid as mosaic
    land_data = gdalutil.regrid(
        land30_data, landcover30_grid, land30_nd,
        imosaic_grid, land30_nd,
        resample_algo=gdalconst.GRA_Average)

    return land_data
# -------------------------------------------------------------------
def one_stats_outputs(expmod, combo, res, elev_label):
    section = _section(expmod, combo)

#    ivals = (fhc, ext)
    vnames = [f'fhc{elev_label}', f'extent{elev_label}', f'snow{elev_label}']

    stats_dir = expmod.root_dir / 'stats' / 'tiles' / f's{res}'
    outputs = [stats_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}-s{res}.tif' for vname in vnames]

    return outputs

def one_stats(expmod, combo, imosaic_grid, imosaic_nd, elev_label, elev_min, elev_max, fhc, ext, snow, res):
    """Computes stats for one combo / elevation class / resolution

    imosaic_grid, imosaic_nd:
        Input grid
    elev_min, elev_max: float
        Elevation class defined as elev_min <= x < elev_max
    fhc: (on imosaic_grid)
        Fraction of each gridcell in our elevation class

    It writes the stats out into a single-tile file with the same
    extent but different resolution from the input grid.
    """

    ofnames = one_stats_outputs(expmod, combo, res, elev_label)

#    if all(os.path.isfile(ofname) for ofname in ofnames):
#        return

    stats_dir = expmod.root_dir / 'stats' / 'tiles' / f's{res}'
    os.makedirs(stats_dir, exist_ok=True)

    # Output grid is same extent as input grid, but lower resolution
    stats_grid = expmod.gridD.sub(combo.idom, combo.jdom, res, res, margin=False)

    # -----------------------------------------------------

    # Regrid mosaic to the stats grid
    ext_sum = gdalutil.regrid(
        ext, imosaic_grid, imosaic_nd,
        stats_grid, imosaic_nd,
        resample_algo=gdalconst.GRA_Sum)
    snow_sum = gdalutil.regrid(
        snow, imosaic_grid, imosaic_nd,
        stats_grid, imosaic_nd,
        resample_algo=gdalconst.GRA_Sum)
    fhc_sum = gdalutil.regrid(
        fhc, imosaic_grid, imosaic_nd,
        stats_grid, imosaic_nd,
        resample_algo=gdalconst.GRA_Sum)
    fhc_mean = gdalutil.regrid(
        fhc, imosaic_grid, imosaic_nd,
        stats_grid, imosaic_nd,
        resample_algo=gdalconst.GRA_Average)


    print('EXT1 sum ', np.sum(np.logical_and(ext < 0, ext != imosaic_nd)))
    print('EXT2 sum ', np.sum(np.logical_and(ext_sum < 0, ext_sum != imosaic_nd)))


    ext_mean = ext_sum / fhc_sum
    ext_mean[ext_sum == imosaic_nd] = imosaic_nd
    ext_mean[fhc_sum == 0] = imosaic_nd
    ext_mean[fhc_sum == imosaic_nd] = imosaic_nd

    snow_mean = snow_sum / fhc_sum
    snow_mean[snow_sum == imosaic_nd] = imosaic_nd
    snow_mean[fhc_sum == 0] = imosaic_nd
    snow_mean[fhc_sum == imosaic_nd] = imosaic_nd


#    ovals = (fhc_mean, ext_mean)
    ovals = (fhc_sum, ext_mean, snow_mean)
    for ofname,oval in zip(ofnames, ovals):
        os.makedirs(ofname.parents[0], exist_ok=True)
        print('Writing ', ofname)
        gdalutil.write_raster(
            ofname,
            stats_grid, oval, imosaic_nd)



# ----------------------------------------------------------------------
elev_ranges = [('040', -100,40), ('160', 40,160), ('8000', 160,8000), ('full', -100,9000)]

def r_stats_one_combo(makefile, expmod, combo, tdir, ress=[100,1000,10000]):
    """Reads the (multiple) variables for a single combo"""


    section = _section(expmod, combo)

#    vname = 'avalanche_count'
    imosaic_tif = expmod.root_dir / 'publish' / section / 'avalanche_count' / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-avalanche_count.tif'
    isnow_tif = expmod.root_dir / 'publish' / section / 'snow' / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-snow.tif'
    

    outputss = [one_stats_outputs(expmod, combo, res, elev_label) for res,(elev_label,_,elev_max) in itertools.product(ress,elev_ranges)]
    outputs = [item for sublist in outputss for item in sublist]
#    for x in outputs:
#        print(x)
#    sys.exit(0)
    inputs = [imosaic_tif]

    if not os.path.isfile(imosaic_tif):
        print('xyz ', imosaic_tif)
#        sys.exit(0)
        return None

    def action(tdir):

        # ------- Read Data
        # Read avalanche extent info
    #    if not os.path.isfile(imosaic_tif):
    #        return False    # Avoid degenerate tile
        imosaic_grid, extent_data, imosaic_nd = gdalutil.read_raster(imosaic_tif)
        extent_data = np.clip(extent_data, None, 1)
        extent_data = extent_data.astype('d')
        assert imosaic_nd == 0
        imosaic_nd = -1e10    # For the future

        # Read the snow
        snow_grid, snow_data, snow_nd = gdalutil.read_raster(isnow_tif)
        snow_data[snow_data == snow_nd] = imosaic_nd    # Change to new Nodata value

    #    # Read the Land / Ocean Mask
    #    land_mask_in = (_read_land_data(expmod, combo.idom, combo.jdom, imosaic_grid, tdir) == 0)

        # Read the DEM
        ijpoly = expmod.gridD.poly(combo.idom, combo.jdom, margin=False)
        dem_tif = tdir.filename(suffix='.tif')
        expmod.extract_dem(ijpoly, dem_tif)
        dem5_grid, dem5_data, dem5_nd = gdalutil.read_raster(dem_tif)

        # Regrid DEM to same grid as mosaic
        dem_data = gdalutil.regrid(
            dem5_data, dem5_grid, dem5_nd,
            imosaic_grid, dem5_nd,
            resample_algo=gdalconst.GRA_Average)


        # ------------- Process into multiple variables
        ret = dict()
        for elev_label,elev_min,elev_max in elev_ranges:
            mask_ocean_out = (dem_data <= 0)
            mask_fhc_out = np.logical_or(dem_data < elev_min, dem_data >= elev_max)


    #        mask_in = np.logical_and(dem_data > 0, np.logical_and(
    #        mask_out = np.logical_not(mask_in)

            # Compute extent of avalanche
            #vname = 'ext{elev_max:03d}'
            elev_ext = extent_data.copy()    # Extent in an elevation class
#            print('AA1 ', len(elev_ext), elev_ext.shape)
#            print('AA2 ', len(mask_ocean_out), mask_ocean_out.shape)
            elev_ext[mask_ocean_out] = imosaic_nd
            elev_ext[mask_fhc_out] = 0

            # Compute snowfall
            elev_snow = snow_data.copy()
            elev_snow[mask_ocean_out] = imosaic_nd
            elev_snow[mask_fhc_out] = 0

            # Compute land cover fraction at this elevation class
            fhc = np.ones(elev_ext.shape)
            fhc[mask_fhc_out] = 0        # These two lines MUST be in this order.
            fhc[mask_ocean_out] = imosaic_nd
    #        fhc = mask_in.astype('d')


            for res in ress:
                one_stats(expmod, combo, imosaic_grid, imosaic_nd, elev_label, elev_min, elev_max, fhc, elev_ext, elev_snow, res)


    #        ret.append(((elev_min, elev_max), (fhc, elev_ext)))
    #    return imosaic_grid,ret,imosaic_nd

    makefile.add(make.Rule(action, inputs, outputs))
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
def stats_by_combos(akdf0, ress=[100,1000,10000]):

    """

    akdf:
        Avalanches (in scenetype='arc') to mosiac
        Resolved to the combo level
        Must contain columns: releasefile (actually arcdir), avalfile, id

    res: [m]
        Gridcell size to average up to.
        Most be an even divisor of tile size.
    """

    print('=== BEGIN stats_combo()')
    print(akdf0)
    exp = akdf0.exp[0]
    expmod = akramms.parse.load_expmod(exp)

    makefile = make.Makefile()
    xdir = expmod.root_dir / 'stats'
    with ioutil.TmpDir(xdir) as tdir:
        for akdf1 in avalquery.consolidate_by_forest(expmod, akdf0):
            # Change For/NoFor to All
            combo = akdf1.combo.iloc[0]

    #        exp = akdf1.exp[0]
            combo = combo._replace(forest='All')

            os.makedirs(xdir, exist_ok=True)
            rule = r_stats_one_combo(makefile, expmod, combo, tdir, ress=ress)
            makefile.add(rule)
#            print('avalstast2 rule ', rule)

        makefile.generate(expmod.root_dir / '_make', run=True, ncpu=config.stats_ncpu)


def combine_tiles(akdf0, ress=[1000]):
    """Combines tiles from stats_by_combo"""

    # Compute per-tile stats
#    stats_combo(akdf0, ress=ress)

    # Consolidate
    exp = akdf0.exp[0]
    expmod = akramms.parse.load_expmod(exp)

    # Separate list of combos into wcombo and tiles
    wcombos = set()
    for combo in akdf0.combo:
        combo = combo._replace(forest='All')
        wcombos.add(tuple(combo[:-2]))



    stats_varss = [[f'fhc{elev_label}', f'extent{elev_label}', f'snow{elev_label}'] for elev_label,elev_min,elev_max in elev_ranges]
    stats_vars = [item for sublist in stats_varss for item in sublist]

    for res in ress:

        istats_dir = expmod.root_dir / 'stats' / 'tiles' / f's{res}'
        ostats_dir = expmod.root_dir / 'stats' / 'tif' / f's{res}'
#        istats_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + f'_stats') / f's{res}'
#        ostats_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + f'_stats') / 'tif' / f's{res}'
        os.makedirs(ostats_dir, exist_ok=True)
        for wcombo in wcombos:
            combo = expmod.Combo(*(list(wcombo) + [0,0]))
            section = _section(expmod, combo)    # Eg: ak-ccsm-1981-2010-lapse-All-30

            for vname in stats_vars:
                idir = istats_dir / section / vname
                inames = [name for name in os.listdir(idir) if name.endswith('.tif')]
                ifnames = [idir / name for name in inames]

                ofname_vrt = ostats_dir / f'{section}-{vname}-s{res}.vrt'
                ofname_tif = ostats_dir / f'{section}-{vname}-s{res}.tif'

                gdalutil.build_vrt(ifnames, ofname_vrt)
                cmd = ['gdal_translate', '-co', 'COMPRESS=DEFLATE', ofname_vrt, ofname_tif]
                subprocess.run(cmd, check=True)

def diff_stats(expmod, res):
    """Finds the difference climate change will make in the stats"""

    stats_dir = expmod.root_dir / 'stats' / 'tif' / f's{res}'
    for vname in ('extent040', 'extent160', 'extent8000'):
        ifname_hist = f'{expmod.name}-ccsm-1981-2010-lapse-All-30-{vname}-s{res}.tif'
        ifname_fut = f'{expmod.name}-ccsm-2031-2060-lapse-All-30-{vname}-s{res}.tif'
        
            

