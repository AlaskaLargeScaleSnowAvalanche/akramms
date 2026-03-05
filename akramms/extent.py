import os,pathlib,subprocess,sys,typing,contextlib
import numpy as np
import pandas as pd
import pyproj
from osgeo import gdal,ogr,gdalconst
from uafgi.util import gdalutil,ogrutil,make
from uafgi.util import cfutil,ioutil,gisutil,rasterize
from akramms import experiment,archive,file_info,avalquery,downscale_snow
import akramms.parse
from akramms import resolve
import _mosaic
import geopandas
from akramms.plot import p_mosaic
import shapely.geometry.multipolygon

__all__ = ['write_gpkg']

# python -m cProfile -o prof -s cumtime `which akramms` mosaic juneau1-1981-1990.qy 


# ===================================================================
# ----------------------------------------------------------
def _mask_filter_full(nzmask_val, aval, tup_id):
        #nzmask_val[np.logical_and(np.logical_and(
        #    aval.max_height > 0,
        #    aval.max_vel > 0),
        #    aval.depo > 0)] = tup_id

        # Do not require depo>0 because there will be parts of extent
        # that are not also covered by extent_full.
        nzmask_val[np.logical_and(
            aval.max_height > 0,
            aval.max_vel > 0)] = tup_id

def _mask_filter_christen(nzmask_val, aval, tup_id):
        # On March 5, 2024 Marc Christen wrote:
        # > These outlines are defined as an envelope of grid cells
        # > of an avalanche, where
        # >   Flow-depth > 0.25m AND
        # >   velocity > 1m/s
        nzmask_val[np.logical_and(
            aval.max_height > 0.25, aval.max_vel > 1.0)] = tup_id


# TetraTech "severe": run this on the 30y
def _mask_filter_tetra30(nzmask_val, aval, tup_id, max_pressure=None): # 
    """SEVERE: Return period less than 30 years; AND/OR Impact
    pressure greater than or equal to 30 kPa"""
    nzmask_val[max_pressure > 30] = tup_id

# TetraTech "moderate" risk: run this on the 300y
def _mask_filter_tetra1(nzmask_val, aval, tup_id, max_pressure=None): # 
    """SEVERE: Return period less than 30 years; AND/OR Impact
    pressure greater than or equal to 30 kPa"""
    nzmask_val[max_pressure > 1] = tup_id

# ----------------------------------------------------------------------------
def extent_fname(expmod, combo, extent_type):
    arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')
    swcombo = arcdir.parts[-2]    # Eg: 'ak-ccsm-1981-2010-lapse-For-30'
    sijdom = arcdir.parts[-1][4:]    # Eg: 111-044
    expdir_ext = expmod.dir.parents[0] / 'ext'
    extent_dir = expdir_ext / swcombo / f'extent_{extent_type}'
    extent_gpkg = extent_dir / f'{swcombo}-{sijdom}-extent_{extent_type}.gpkg'
    return extent_gpkg


#extent_types = ('christen', 'full', 'tetra30', 'tetra1')
def polygonize_extent(combo, aval, tup_id,
    extent_layer, extent_Id, landcover, extent_type='christen', mask_kwargs={}):#full=False):
#    iA, jA, gridA_gt, crs_wkt, max_vel, max_height, depo,

    """Creates a polygon for the extent of an avalanche, and writes it
    into an open OGR datasource.
    NOTE: This will create multiple polygons in the face of discontinuous extents.

    aval: Result of read_nc()

    extent_layer: OUTPUT
        OGR layer to write into
    extent_Id: OUTPUT
        Reference to the OGR shapefile field called "Id", where
        Avalanche Id is to be stored.

    extent_type:
        'full': polygonize all non-zero gridcells (used for SpataLite index).
        'christen': polygonize using "user-level" definition of avalanche outline as per Marc Christen's definition
        'tetra30': Polygonize using Tetra Tech's 30-year criterion
        'tetra1': Polygonize using Tetra Tech's 300-year criterion

    Example creating extent inputs:
      extent_ds = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(extent_shp)
      extent_layer = extent_ds.CreateLayer(extent_shp, ogrutil.to_srs(gridM.wkt), geom_type=ogr.wkbMultiPolygon )
      # https://gis.stackexchange.com/questions/392515/create-a-shapefile-from-geometry-with-ogr
      extent_Id = extent_layer.CreateField(ogr.FieldDefn('Id', ogr.OFTInteger))

    """

    # Watch out for null polygons
    if len(aval.iiA) == 0:
        return None

#    print(f'polygonize_extent({tup_id})')

    # Create a sub-grid gridL around just the avalanche (fast polygonize)
    iL_min = np.min(aval.iiA) - 2
    iL_max = np.max(aval.iiA) + 3    # Max+1
    jL_min = np.min(aval.jjA) - 2
    jL_max = np.max(aval.jjA) + 3

    iL = aval.iiA - iL_min    # Vector operation
    jL = aval.jjA - jL_min
    gridL_gt = np.array(aval.gridA_gt, dtype='i8')
    gridL_gt[0] += gridL_gt[1] * iL_min
    gridL_gt[3] += gridL_gt[5] * jL_min
    gridL = gisutil.RasterInfo(
        aval.gridA_wkt, #nc.variables['grid_mapping'].crs_wkt,
        iL_max - iL_min,
        jL_max - jL_min,
        gridL_gt)

#    # Read avalanche output as values on list-of-gridcells
#    max_vel = nc.variables['max_vel'][:].astype('f4')
#    max_height = nc.variables['max_height'][:].astype('f4')
#    depo = nc.variables['depo'][:].astype('f4')

    nzmask_val = np.zeros(aval.max_vel.shape, dtype=np.int32)
    this_module = sys.modules[__name__]
    mask_filter_fn = getattr(this_module, f'_mask_filter_{extent_type}')
    mask_filter_fn(nzmask_val, aval, tup_id, **mask_kwargs)

    # ----------------
    # Now nzmask_val (on its limited grid) is tup_id where there is
    # avalanche, and 0 elsewhere.
#    print('Landcover shape ', landcover.shape)
#    print('nzmask shape ', nzmask_val.shape)
#    landcoverL = landcover[aval.iiA, aval.jjA]#iL_min:iL_max, jL_min:jL_max]
    landcoverL = landcover[aval.jjA, aval.iiA]#iL_min:iL_max, jL_min:jL_max]
#    print('landcover ', landcover.shape)
#    print('landcoverL ', landcoverL.shape, iL_min, iL_max, jL_min, jL_max)
#    print('nzmask_val ', nzmask_val.shape)
    nzmask_in = (nzmask_val != 0)
#    print(landcoverL[nzmask_in])
    extsizes = (
        np.sum(nzmask_in),
        np.sum(landcoverL[nzmask_in] == 41),
        np.sum(landcoverL[nzmask_in] == 42),
        np.sum(landcoverL[nzmask_in] == 43))
#    print('extsizes ', extsizes)
    # ----------------


    # Burn the gridcells that are part of our grid
    # (already pared down)
    nzmaskL = np.zeros((gridL.ny, gridL.nx), dtype=np.int32)
    nzmaskL[jL,iL] = nzmask_val    # This will get written into the attribute table

    nzmask_ds = gdalutil.raster_ds((gridL, nzmaskL, 0))
    nzmask_band = nzmask_ds.GetRasterBand(1)

    # Produces a separate polygon for each different (non-zero) value in nzmaskL
    # Since we've only set things to tup_id, we will only get Polygon(s) for that.
    # The pixel value is placed in the Id attribute
    # Polygonize docs: https://gdal.org/api/gdal_alg.html (search for GDALPolygonize)
    gdal.Polygonize(nzmask_band, nzmask_band,
        extent_layer, extent_Id)

    return extsizes

# ----------------------------------------------------------
def merge_multipolygons(df0, idcol):
    """Merges multiple polygons with the same Id into a single MultiPolygon"""
    rows = list()
    for id,df1 in df0.groupby(idcol):
        mpoly = shapely.geometry.multipolygon.MultiPolygon(list(df1.geometry))
        rows.append((id,mpoly))
    df = pd.DataFrame(rows, columns=('Id', 'geometry'))
    gdf = geopandas.GeoDataFrame(df, geometry='geometry')
    return gdf
# ----------------------------------------------------------

def extent_files(expmod, combo):
    """Extent files required for a given combo"""
    return [
        WriteGpkg(expmod, combo, extent_type, None).extent_gpkg \
        for extent_type in extent_types]

class WriteGpkg:
#    def __init__(self, expmod, combo, swcombo, sijdom, extent_dir, extent_type, tdir, overwrite=False, mask_kwargs={}):
    def __init__(self, expmod, combo, extent_type, landcover):
        """landcover:
            It is OK to set this to None, then set it by monkey
            patching later, before polygonize() is used.
        """

        self.expmod = expmod

        # Figure out where we will write extent files
        arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')
        swcombo = arcdir.parts[-2]    # Eg: 'ak-ccsm-1981-2010-lapse-For-30'
        sijdom = arcdir.parts[-1][4:]    # Eg: 111-044
        expdir_ext = expmod.dir.parents[0] / 'ext'
        self.extent_dir = expdir_ext / swcombo / f'extent_{extent_type}'


        self.extent_type = extent_type
        self.extent_gpkg = self.extent_dir / f'{swcombo}-{sijdom}-extent_{extent_type}.gpkg'
#        self.tdir = tdir    # This MUST be set manually before entering the context!  HACK!
        self.landcover = landcover
        self.complete = False

    def __enter__(self):
        os.makedirs(self.extent_dir, exist_ok=True)

        # ----------------- Write /vsizip/EXTENT.zip/extent.shp
        self.extent_shp = self.tdir.location / f'extent_{self.extent_type}.shp'

        # Open and write the extent file (Shapefile within a Zip archive)
        self.extent_ds = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(str(self.extent_shp))

        self.extent_layer = self.extent_ds.CreateLayer(str(self.extent_shp), ogrutil.to_srs(self.expmod.wkt),
                geom_type=ogr.wkbMultiPolygon)

        # https://gis.stackexchange.com/questions/392515/create-a-shapefile-from-geometry-with-ogr
        self.extent_Id = self.extent_layer.CreateField(ogr.FieldDefn('Id', ogr.OFTInteger))
        self.relrows = list()

        return self

    def __exit__(self, type, value, traceback):
        if not self.complete:
            return

        self.extent_Id = None
        self.extent_layer = None
        self.extent_ds = None    # Close the file
        #print('extent_shp ', str(self.extent_shp), os.path.isfile(self.extent_shp))
 
       # Convert to GeoPackage (indented to maintain open temp dir)
        extent_gpkg_tmp = self.extent_gpkg.parents[0] / (self.extent_gpkg.parts[-1][:-5] + '-tmp.gpkg')
        edf = geopandas.read_file(self.extent_shp)
        edf = merge_multipolygons(edf, 'Id')
        reldf = pd.DataFrame(self.relrows, columns=['Id', 'Mean_DEM', 'rel_n', 'rel_n41', 'rel_n42', 'rel_n43', 'ext_n', 'ext_n41', 'ext_n42', 'ext_n43'])
        edf = edf.merge(reldf, how='left', on='Id')
        edf.to_file(str(extent_gpkg_tmp), engine='fiona', crs=pyproj.CRS.from_user_input(self.expmod.wkt))


##        cmd = ['ogr2ogr', extent_gpkg_tmp, self.extent_shp]
#        cmd = ['ogr2ogr', '/home/efischer/tmp/xextent.gpkg', self.extent_shp]
#        subprocess.run(cmd, check=True)


        os.rename(extent_gpkg_tmp, self.extent_gpkg)

#        return self.extent_gpkg



    def polygonize(self, combo, aval, id, relsizes, mask_kwargs={}):
        extsizes = polygonize_extent(
            combo, aval, id, self.extent_layer, self.extent_Id, self.landcover,
            extent_type=self.extent_type, mask_kwargs=mask_kwargs)
        if extsizes is not None:
            self.relrows.append(list(relsizes) + list(extsizes))

# ----------------------------------------------------------------
extent_types = ('christen', 'full', 'tetra30', 'tetra1')

class combo_extent_action:

    def __init__(self, exp, row, rho=300):
        """
        rho: [kg m-2]
            Assumed snow density
        """
        self.exp = exp
        self.row = row
        self.rho = rho

        combo = row['combo']
        expmod = akramms.parse.load_expmod(exp)

#        extent_writers = {extent_type: WriteGpkg(expmod, combo, extent_type, None) for extent_type in extent_types}

#        self.outputs = [ew.extent_gpkg for ew in extent_writers.values()]
        self.outputs = extent_files(expmod, combo)


    def __call__(self, tdir):
        combo = self.row['combo']
        expmod = akramms.parse.load_expmod(self.exp)
        extent_writers = {extent_type: WriteGpkg(expmod, combo, extent_type, None) for extent_type in extent_types}
        extent_dir = extent_writers[extent_types[0]].extent_dir


        # Read the releasefile polygons so we can analyze land surface types
        # (reldf only needs to be set if there are avalanches in this combo)
        arcdir = expmod.combo_to_scenedir(combo, 'arc')
        RELEASE_zip = arcdir / 'RELEASE.zip'
        if os.path.isfile(RELEASE_zip):
            reldf = archive.read_reldom(RELEASE_zip, 'rel')
            reldfi = reldf.set_index('Id')

        # Make a dataframe from that one combo, then convert to IDs
#        akdf1 = akdf0.iloc[[irow]]    # Returns a dataframe of just one row
        akdf1 = pd.DataFrame([self.row])
        akdf1 = resolve.resolve_chunk(akdf1, scenetypes={'arc'})
        akdf1 = resolve.resolve_id(akdf1, realized=True)


        # ----------------------------------------
        # Read the land surface file for this tile
        dem_fname = expmod.root_dir / 'db' / 'dem' / f'{expmod.name}_dem_{combo.idom:03d}_{combo.jdom:03d}.tif'
        grid_info = gdalutil.read_grid(dem_fname)

        landcover_fname = expmod.root_dir / 'db' / 'landcover' / f'{expmod.name}_landcover_{combo.idom:03d}_{combo.jdom:03d}.tif'
        landcover30_grid,landcover30,landcover30_nd = gdalutil.read_raster(landcover_fname)

        # Regrid land mask to same grid as mosaic
        print('landcover30_nd ', landcover30_nd)
        landcover = gdalutil.regrid(
            landcover30, landcover30_grid, landcover30_nd,
            grid_info, landcover30_nd,
            resample_algo=gdalconst.GRA_Average)


        landcover_1d = landcover.reshape(-1)
        for ew in extent_writers.values():
            ew.landcover = landcover
        # ----------------------------------------


        # Iterate through avalanches and polygonize each one
        print(f'Writing extents for {combo} ({len(akdf1)} avalanches): {extent_dir}')
        with contextlib.ExitStack() as stack:
            tdir = stack.enter_context(ioutil.TmpDir(extent_dir))
            for extent_writer in extent_writers.values():
                extent_writer.tdir = tdir    # Hack
                stack.enter_context(extent_writer)

            count = 0
            for tup in akdf1.itertuples(index=False):    # Iterate through each avalanche (tup.avalfile)
                count += 1
                if count%100 == 0:
                    print('.', end='')
                    sys.stdout.flush()
#                    break    # DEBUG

#                if tup.id != 9288:
#                    continue        # DEBUG
#                print('FOUND 9288!!!!')

                if not os.path.isfile(tup.avalfile):
                    print(f'Missing avalanche file: {tup.avalfile}')
                    continue
                if os.path.getsize(tup.avalfile) == 0:    # Avoid dummy placeholder avalanches
                    continue
                aval = archive.read_nc(tup.avalfile)

                # Process the PRA
                relrow = reldfi.loc[tup.id]
                pra_burn = rasterize.rasterize_polygon_compressed(relrow['geometry'], grid_info)
                lc1 = landcover_1d[pra_burn]

                relsizes = (tup.id, relrow['Mean_DEM'], len(lc1), np.sum(lc1==41), np.sum(lc1==42), np.sum(lc1==43))
                extent_writers['christen'].polygonize(combo, aval, tup.id, relsizes)
                extent_writers['full'].polygonize(combo, aval, tup.id, relsizes)
                max_pressure = self.rho * aval.max_vel * aval.max_vel
                extent_writers['tetra30'].polygonize(combo, aval, tup.id, relsizes,
                    mask_kwargs=dict(max_pressure=max_pressure))
                extent_writers['tetra1'].polygonize(combo, aval, tup.id, relsizes,
                    mask_kwargs=dict(max_pressure=max_pressure))
            print()
            for ew in extent_writers.values():
                ew.complete = True

def r_combo_extent( exp, row):
    action_fn = combo_extent_action(exp, row)
    rule = make.Rule(action_fn, [], action_fn.outputs)

def read_annotated_extent(expmod, combo, extent_type):

    """Reads an extent GPKG file, annotates it with info from the
    RELEASE.zip file."""

    # One polygon per ID
    arcdir = expmod.combo_to_scenedir(combo, 'arc')
    reldf = archive.read_reldom(arcdir / 'RELEASE.zip', 'rel', read_shapes=False)

    # Multiple polygons per ID
    extent_gpkg = extent_fname(expmod, combo, 'christen')
    if not os.path.isfile(extent_gpkg):
        raise FileNotFoundError(extent_gpkg)    # Raise a recognizable exception
    extdf = geopandas.read_file(str(extent_gpkg), engine='fiona')

    # Merge the two.  The merging retains the sames tructure as extdf
    # because reldf has ONLY ONE polygon per ID.
    _extdf = geopandas.GeoDataFrame(extdf.drop('Mean_DEM', axis=1))
    _reldf = reldf.drop('geometry',axis=1)
    return _extdf.merge(_reldf, on='Id')
