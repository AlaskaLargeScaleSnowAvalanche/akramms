import os,copy,functools,itertools,subprocess
import numpy as np
from osgeo import gdalconst
from uafgi.util import gisutil, gdalutil,ioutil
import akramms.parse
from akramms import avalquery

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
# ------------------------------------------------------------------
# Read each different variable
def rbind(fn, *rargs):
    def _fn(*largs, **kwargs):
        return fn(*itertools.chain(largs, rargs), **kwargs)
    return _fn


def _read_snow(expmod, combo, tdir):
#    tile_grid = expmod.gridD.sub(combo.idom, combo.jdom, expmod.resolution, expmod.resolution, margin=True)

    snow_fname = expmod.dir / 'snow' / f'{expmod.name}_{combo.snow_dataset}_{combo.year0}_{combo.year1}_{combo.downscale_algo}_{combo.idom:03d}_{combo.jdom:03d}.tif'
    print('snow_fname ', snow_fname)
    return gdalutil.read_raster(snow_fname)


def _read_thresh(expmod, combo, tdir, vname):
    """Thresholds a "count" variable to 0 or 1"""

    section = _section(expmod, combo)
    imosaic_tif = expmod.root_dir / 'publish' / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}.tif'

    # Read the variable
    imosaic_grid, imosaic_data, imosaic_nd = gdalutil.read_raster(imosaic_tif)
    imosaic_data = np.clip(imosaic_data, None, 1)
    imosaic_data = imosaic_data.astype('d')
    assert imosaic_nd == 0

    # Use the ocean mask to set nodata values
    ocean_mask = (_read_land_data(expmod, combo.idom, combo.jdom, imosaic_grid, tdir) == 0)
    mosaic_nd = -1e10
    imosaic_data[ocean_mask] = imosaic_nd

    return imosaic_grid, imosaic_data, mosaic_nd

def _read_double(expmod, combo, tdir, vname):
    """No Thresholding, variable already double"""

    imosaic_tif =expmod.root_dir / 'publish' / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}.tif'

    # Read the variable
    imosaic_grid, imosaic_data, imosaic_nd = gdalutil.read_raster(imosaic_tif)
#    imosaic_data = np.clip(imosaic_data, None, 1)
    imosaic_data = imosaic_data.astype('d')
    assert imosaic_nd == 0

    # Use the ocean mask to set nodata values
    ocean_mask = (_read_ocean_data(expmod, combo.idom, combo.jdom, imosaic_grid, tdir) == 0)
    mosaic_nd = -1e10
    imosaic_data[ocean_mask] = imosaic_nd

    return imosaic_grid, imosaic_data, mosaic_nd

def _by_area(grid):
    return 1. / (grid.dx * grid.dy)

def _by_1(grid):
    return 1

stats_vars = {
##    'land': (_read_land, _by_1, '1'),
    'avy_extent': (rbind(_read_thresh, 'avalanche_count'), _by_1, '1'),
    'count': (rbind(_read_thresh, 'pra_centroid_count'), _by_area, 'km-2'),
    'release_extent': (rbind(_read_thresh, 'pra_count'), _by_1, '1'),
    'snow': (_read_snow, _by_1, '1'),
}


def regrid_stdmosaic(expmod, combo, vname, res):
    read_fn, scale_fn, sunits = stats_vars[vname]

    section = _section(expmod, combo)

    stats_dir = expmod.root_dir / 'stats' / 'tiles' / f's{res}'
#    stats_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + f'_stats') / f's{res}'

    omosaic_tif = stats_dir / section / vname / f'{section}-{combo.idom:03d}-{combo.jdom:03d}-F-{vname}-s{res}.tif'

    if os.path.isfile(omosaic_tif):
        return

    os.makedirs(stats_dir, exist_ok=True)
    try:
        with ioutil.TmpDir(stats_dir) as tdir:
            imosaic_grid, imosaic_data, imosaic_nd = read_fn(expmod, combo, tdir)
    except FileNotFoundError as e:
        print(f'No input file, skipping: {combo}: {read_fn}')
        print(e)
        return
#    except:
#        raise

#    # Construct stats grid (at low resolution), used for averaging
#    onx = int(round(imosaic_grid.nx * np.abs(imosaic_grid.dx) / res))
#    ony = int(round(imosaic_grid.ny * np.abs(imosaic_grid.dy) / res))
#    gt = copy.copy(imosaic_grid.geotransform)
#    gt[1] = res * np.sign(imosaic_grid.geotransform[1])    # dx
#    gt[5] = res * np.sign(imosaic_grid.geotransform[5])   # dy
#    stats_grid = gisutil.RasterInfo(
#        imosaic_grid.wkt, onx, ony,
#        gt)
    stats_grid = expmod.gridD.sub(combo.idom, combo.jdom, res, res, margin=False)


    # Regrid mosaic to the stats grid
    stats_data = gdalutil.regrid(
        imosaic_data, imosaic_grid, imosaic_nd,
        stats_grid, imosaic_nd,
        resample_algo=gdalconst.GRA_Average)

    stats_data *= scale_fn(stats_grid)


    print(f'Writing {omosaic_tif}')
    os.makedirs(omosaic_tif.parents[0], exist_ok=True)
    gdalutil.write_raster(
        omosaic_tif,
        stats_grid, stats_data, imosaic_nd)


def stats_combo(akdf0, ress=[1000]):

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

    for akdf1 in avalquery.consolidate_by_forest(expmod, akdf0):
        # Change For/NoFor to All
        combo = akdf1.combo.iloc[0]

#        exp = akdf1.exp[0]
        combo = combo._replace(forest='All')
        print('combo ', combo)

        for vname in stats_vars.keys():
            for res in ress:
                regrid_stdmosaic(expmod, combo, vname, res)

def stats_wcombo(akdf0, ress=[1000]):

    # Compute per-tile stats
    stats_combo(akdf0, ress=ress)
#    return    # DEBUG

    # Consolidate
    exp = akdf0.exp[0]
    expmod = akramms.parse.load_expmod(exp)

    # Separate list of combos into wcombo and tiles
    wcombos = set()
    for combo in akdf0.combo:
        combo = combo._replace(forest='All')
        wcombos.add(tuple(combo[:-2]))

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
                cmd = ['gdal_translate', ofname_vrt, ofname_tif]
                subprocess.run(cmd, check=True)
# --------------------------------------------------------------------------




def stats_landcover(expmod, ress):
    ifnamess = {res: list() for res in ress}
    for idom,jdom in expmod.all_domains():
#        print('idom jdom ', idom, jdom)

        for res in ress:
            # Get filename
            stats_dir = expmod.root_dir / 'stats' / 'tiles' / f's{res}' / 'land'
#            stats_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + f'_stats') / f's{res}' / 'land'
            os.makedirs(stats_dir, exist_ok=True)
            ofname = stats_dir / f'land-{idom:03d}-{jdom:03d}.tif'
#            print('land ', ofname)
            ifnamess[res].append(ofname)
            if os.path.isfile(ofname):
                continue

            # Get imosaic_grid
            ogrid = expmod.gridD.sub(idom, jdom, res, res, margin=False)#expmod.resolution, expmod.resolution)

            with ioutil.TmpDir(stats_dir) as tdir:
                land_data = _read_land_data(expmod, idom, jdom, ogrid, tdir)
            land_nd = -1e10

            # Write it out        
            gdalutil.write_raster(ofname, ogrid, land_data, land_nd)

    # Convert to single .tif
    tif_dir = expmod.dir.parents[0] / (expmod.dir.parts[-1] + f'_stats') / 'tif'
    for res,ifnames in ifnamess.items():
#        print('xxxx ', res, ifnames)
        ofname_vrt = tif_dir / f's{res}' / f'land-s{res}.vrt'
        ofname_tif = tif_dir / f's{res}' / f'land-s{res}.tif'
#        print('ofname_tif ', ofname_tif)
        gdalutil.build_vrt(ifnames, ofname_vrt)
        cmd = ['gdal_translate', ofname_vrt, ofname_tif]
        subprocess.run(cmd, check=True)
