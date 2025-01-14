import os,pathlib,subprocess,sys,typing,contextlib
import numpy as np
import pandas as pd
import zipfile,netCDF4
from osgeo import gdal,ogr
from uafgi.util import gdalutil,ogrutil
from uafgi.util import cfutil,ioutil,gisutil,rasterize
from akramms import experiment,archive,file_info,avalquery,downscale_snow
import akramms.parse
from akramms import resolve
import _mosaic
import geopandas
from akramms.plot import p_mosaic

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
#extent_types = ('christen', 'full', 'tetra30', 'tetra1')
def polygonize_extent(combo, aval, tup_id,
    extent_layer, extent_Id, extent_type='christen', mask_kwargs={}):#full=False):
#    iA, jA, gridA_gt, crs_wkt, max_vel, max_height, depo,

    """Creates a polygon for the extent of an avalanche, and writes it
    into an open OGR datasource.

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

#    print(f'polygonize_extent({tup_id})')

    # Create a sub-grid gridL around just the avalanche (fast polygonize)
    iL_min = np.min(aval.iiA) - 2
    iL_max = np.max(aval.iiA) + 3
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


# ----------------------------------------------------------


class WriteGpkg:
#    def __init__(self, expmod, combo, swcombo, sijdom, extent_dir, extent_type, tdir, overwrite=False, mask_kwargs={}):
    def __init__(self, expmod, combo, extent_type):
        self.expmod = expmod

        # Figure out where we will write extent files
        arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')
        swcombo = arcdir.parts[-2]    # Eg: 'ak-ccsm-1981-2010-lapse-For-30'
        sijdom = arcdir.parts[-1][4:]    # Eg: 111-044
        expdir_ext = expmod.dir.parents[0] / 'ext'
        self.extent_dir = expdir_ext / swcombo / 'extent'


        self.extent_type = extent_type
        self.extent_gpkg = self.extent_dir / f'{swcombo}-{sijdom}-extent_{extent_type}.gpkg'

#        self.tdir = tdir    # This MUST be set manually before entering the context!  HACK!

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


        return self

    def __exit__(self, type, value, traceback):
        self.extent_Id = None
        self.extent_layer = None
        self.extent_ds = None    # Close the file
        #print('extent_shp ', str(self.extent_shp), os.path.isfile(self.extent_shp))
 
       # Convert to GeoPackage (indented to maintain open temp dir)
        extent_gpkg_tmp = self.extent_gpkg.parents[0] / (self.extent_gpkg.parts[-1][:-5] + '-tmp.gpkg')
        cmd = ['ogr2ogr', extent_gpkg_tmp, self.extent_shp]
        subprocess.run(cmd, check=True)
        os.rename(extent_gpkg_tmp, self.extent_gpkg)

#        return self.extent_gpkg



    def polygonize(self, combo, aval, id, mask_kwargs={}):
        polygonize_extent(combo, aval, id, self.extent_layer, self.extent_Id, extent_type=self.extent_type, mask_kwargs=mask_kwargs)




extent_types = ('christen', 'full', 'tetra30', 'tetra1')
def write_combos_extents(expmod, akdf0, overwrite=False, rho=300):
    """Write the extent files for a number of combos.
    akdf:
        Resolved to combo level (in arc dir)
    """
    
    # Iterate through one combo at a time
    for irow in range(len(akdf0)):

        row = akdf0.iloc[irow]    # Returns a Series
        combo = row['combo']
        extent_writers = {extent_type: WriteGpkg(expmod, combo, extent_type) for extent_type in extent_types}
        extent_dir = extent_writers['full'].extent_dir    # All extent_dirs are the same
        os.makedirs(extent_dir, exist_ok=True)

        # Don't need to re-do extents if ALL output files are there
        if (not overwrite) and all((os.path.isfile(extent_writer.extent_gpkg) for extent_writer in extent_writers.values())):
            continue

        # Make a dataframe from that one combo, then convert to IDs
        akdf1 = akdf0.iloc[[irow]]    # Returns a dataframe of just one row
        akdf1 = resolve.resolve_chunk(akdf1, scenetypes={'arc'})
        akdf1 = resolve.resolve_id(akdf1, realized=True)

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

                if not os.path.isfile(tup.avalfile):
                    print(f'Missing avalanche file: {tup.avalfile}')
                    continue
                aval = archive.read_nc(tup.avalfile)

                extent_writers['christen'].polygonize(combo, aval, tup.id)
                extent_writers['full'].polygonize(combo, aval, tup.id)
                max_pressure = rho * aval.max_vel * aval.max_vel
                extent_writers['tetra30'].polygonize(combo, aval, tup.id,
                    mask_kwargs=dict(max_pressure=max_pressure))
                extent_writers['tetra1'].polygonize(combo, aval, tup.id,
                    mask_kwargs=dict(max_pressure=max_pressure))
            print()





#
#
#
#def write_gpkg(expmod, combo, extent_type, overwrite=False, mask_kwargs={}):
#
#    arcdir = expmod.combo_to_scenedir(combo, scenetype='arc')
#    swcombo = arcdir.parts[-2]    # Eg: 'ak-ccsm-1981-2010-lapse-For-30'
#    sijdom = arcdir.parts[-1][4:]    # Eg: 111-044
#    expdir_ext = expmod.dir.parents[0] / 'ext'
#
#    odir = expdir_ext / swcombo / 'extent'
#    extent_gpkg = odir / f'{swcombo}-{sijdom}-extent_{extent_type}.gpkg'
#
#    if (not overwrite) and os.path.isfile(extent_gpkg):
#        return extent_gpkg
#
#    os.makedirs(odir, exist_ok=True)
#
#    with ioutil.TmpDir(odir) as tdir:
#
#            for tup in akdf.sort_values('id').itertuples(index=False):
#                if n%100 == 0:
#                    print('.', end='')
#                    sys.stdout.flush()
#                if not os.path.isfile(tup.avalfile):
#                    raise ValueError(f'Missing avalanche file: {tup.avalfile}')
#
#                aval = archive.read_nc(tup.avalfile)
#
#                polygonize_extent(combo, aval, tup.id, extent_layer, extent_Id, extent_type=extent_type, mask_kwargs=mask_kwargs)
#                n += 1
#            print('Done!')
#        finally:
#            extent_ds = None
#
#
#        # Convert to GeoPackage (indented to maintain open temp dir)
#        extent_gpkg_tmp = extent_gpkg.parents[0] / (extent_gpkg.parts[-1][:-5] + '-tmp.gpkg')
#        cmd = ['ogr2ogr', extent_gpkg_tmp, extent_shp]
#        subprocess.run(cmd, check=True)
#        os.rename(extent_gpkg_tmp, extent_gpkg)
#
#        return extent_gpkg
#
#
#
