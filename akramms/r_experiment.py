# Fundamental stuff needed to run an experiment.

import functools
import math,os,subprocess
import numpy as np
from osgeo import ogr,gdal
import shapely
import pandas as pd
from uafgi.util import make,gisutil,shputil,gdalutil
from akramms import config
from akramms import downscale_snow
#from akramms import d_ifsar, d_usgs_landcover

 # -----------------------------------------------------
@functools.lru_cache()
def r_active_domains(exp_mod):
    """Writes a shapefile defining the domains for THIS experiment that will be used...

    exp_mod:
        Root directory for the overall experiment (includes individual trials inside).
    gridD: DomainGrid
        The set of domains
    experiment_region_shp:
        A shapefile covering *just* the region that needs to be covered
    Output:
        {exp_name}_domains.shp:
            The domains from griD that touch the experiment_region_shp
            Includes columns ix,iy giving indices of each domain.
        {exp_name}_domains.zip:
            Zipped shapefile
        {exp_name}_domains_margin.shp:
            Same as {exp_name}_domains.shp, but includes margin.
            This is the domain that will be used for eCognition (and subsetted for RAMMS).
        {exp_name}_domains_margin.zip:
            Zipped shapefile
    """

    gridD = exp_mod.gridD


    # Load the experiment_region as a Shapely Multipolygon
    domains_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains.shp')
    domains_margin_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains_margin.shp')

    domains_zip = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains.zip')
    domains_margin_zip = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains_margin.zip')

    def action(tdir):
        # Load the experiment region and convert to Shapely Polygon
        driver = ogr.GetDriverByName('ESRI Shapefile')
        print('Opening shapefile ', exp_mod.experiment_region_shp)
        src_ds = driver.Open(exp_mod.experiment_region_shp)
        src_lyr = src_ds.GetLayer()   # Put layer number or name in her
        while True:
            feature = src_lyr.GetNextFeature()
            if feature is None:    # There should be only ONE feature.
                break

            geom = feature.GetGeometryRef()
            polygons = list()
            npoly = geom.GetGeometryCount()
#            print('AA1 npoly = ', npoly)
            for ix in range(npoly):
                ring = geom.GetGeometryRef(ix).GetGeometryRef(0)
                npoints = ring.GetPointCount()
                points = list()
                for p in range(0,npoints):
                    x,y,z = ring.GetPoint(p)
                    points.append(shapely.geometry.Point(x,y))
                polygons.append(shapely.geometry.Polygon(points))

#                if len(polygons) > 1000:    # DEBUG
#                    break

            experiment_region = shapely.geometry.MultiPolygon(polygons)

#        for poly in polygons[:5]:
#            print('exp_region ', poly)

#        print('AA2 ', gridD.index_box.intersects(experiment_region))
#        print('AA3 ', experiment_region.intersects(gridD.index_box))

        rows = list()
        for iy in range(0, gridD.ny):
            print(f'Computing domains iy={iy}')
            for ix in range(0, gridD.nx):
                domain = gridD.poly(ix, iy)
#                print('domain ', domain)
                if domain.intersects(experiment_region):
                    domain_margin = gridD.poly(ix, iy, margin=True)
                    rows.append((ix,iy,domain,domain_margin))

        df = pd.DataFrame(rows, columns=('idom', 'jdom', 'domain', 'domain_margin'))
        df.idom = df.idom.astype('int32')
        df.jdom = df.jdom.astype('int32')
#        df = df.astype({'idom':'int', 'jdom':'int'})

        os.makedirs(exp_mod.dir, exist_ok=True)
        shputil.write_df(df[['idom', 'jdom', 'domain']], 'domain', 'MultiPolygon', domains_shp, wkt=exp_mod.wkt, zip_format=True)
        shputil.write_df(df[['idom', 'jdom', 'domain_margin']], 'domain_margin', 'MultiPolygon', domains_margin_shp, wkt=exp_mod.wkt, zip_format=True)

    return make.Rule(action, [exp_mod.experiment_region_zip],
        [domains_shp, domains_margin_shp, domains_zip, domains_margin_zip])

# -----------------------------------------------------------------------
@functools.lru_cache()
def r_ifsar(exp_mod, idom, jdom, sanity_check=True):
    """Select out a portion of the overall IFSAR digital terrain model dataset, for one domain.

    exp_mod:
        Python module defining the experiment (eg: akramms.e_alaska)
    type:
        DTM / DSM / etc.
        (Actually we just use the DTM)
    idom, jdom:
        Index of the domain to select out.
    Output:
        {type}/{exp_mod.name}_{type}_{idom:03d}_{jdom:03d}
    """

    #ifsar_vrt = d_ifsar.r_vrt(type).outputs[0]
    ofname = os.path.join(exp_mod.dir, 'dem', f'{exp_mod.name}_dem_{idom:03d}_{jdom:03d}.tif')

    def action(tdir):
        poly = exp_mod.gridD.poly(idom, jdom, margin=True)
#        return d_ifsar.extract(type, poly, ofname, resolution=resolution, sanity_check=True)
        return exp_mod.extract_dem(poly, ofname, sanity_check=True)
    return make.Rule(action, [exp_mod.dem_img], [ofname])
# -----------------------------------------------------------------------
@functools.lru_cache()
def r_landcover(exp_mod, idom, jdom):
    """Select out a portion of the overall USGS landcover map.
    exp_mod:
        Python module defining the experiment (eg: akramms.e_alaska)
    idom, jdom:
        Index of the domain to select out.
    Output: {exp_mod.name}_landcover_{idom:03d}_{jdom:03d}.tif
        Landcover selected for the given region.
    """

    ofname = os.path.join(exp_mod.dir, 'landcover', f'{exp_mod.name}_landcover_{idom:03d}_{jdom:03d}.tif')

    def action(tdir):
        poly = exp_mod.gridD.poly(idom, jdom, margin=True)
#        return d_usgs_landcover.extract(poly, ofname)
        return exp_mod.extract_landcover(poly, ofname)
    return make.Rule(action, [exp_mod.landcover_img], [ofname])
# -----------------------------------------------------------------------
@functools.lru_cache()
def r_forest(exp_mod, idom, jdom):
    """Convert a landcover file to a forest file."""

    landcover_tif = r_landcover(exp_mod, idom, jdom).outputs[0]
    ofname = os.path.join(exp_mod.dir, 'forest', f'{exp_mod.name}_forest_{idom:03d}_{jdom:03d}.tif')
    def action(tdir):
        grid_info, landcover, landcover_nd = gdalutil.read_raster(landcover_tif)

        # Convert to forest
        forest = (landcover == 42)

        # Write it out!
        os.makedirs(os.path.split(ofname)[0], exist_ok=True)
        gdalutil.write_raster(ofname, grid_info, forest, 255, type=gdal.GDT_Byte)

        # Add statistics in a .tif.aux.xml file
        # (Needed by the ArcGIS prep script)
        # https://gis.stackexchange.com/questions/208996/how-to-create-raster-statistics-with-gdal-externally
        cmd = ['gdalinfo', '-stats', '-hist', ofname]
        subprocess.run(cmd, check=True)


    return make.Rule(action, [landcover_tif], [ofname])

# -----------------------------------------------------------------------
@functools.lru_cache()
def r_dfcA(exp_mod):
    """dfc = distance from coast
    It is computed from the IFSAR DTM file."""

    distance_from_coastA_tif = os.path.join(
        exp_mod.dir, f'{exp_mod.name}_DFC.tif')
    geo_nc = config.roots.join('DATA', 'lader', 'sx3', 'geo_southeast.nc')

    return downscale_snow.r_distance_from_coast(geo_nc, distance_from_coastA_tif)
# -----------------------------------------------------------------------
@functools.lru_cache()
def r_snow(exp_mod, snow_dataset, downscale_algo, year0, year1, idom, jdom):
    """Downscales snow from WRF.
    rules: {Rule, ...}
        Add sub-rules here!
    snow_dataset:
        Which kind of model / reanlysis run to use.
        Eg: 'cfsr'
    downscale_algo: {select, lapse}
        Algorithm to use in downscaling WRF snow.
    exp_mod:
        Python module defining the experiment (eg: akramms.e_alaska)
    Output: {exp_mod.name}_{snow_dataset}_{idom}_{jdom}
        Snow downscaled and selected for a given region (with margins)
    """

    # Determine input filenames
    geo_nc = config.roots.join('DATA', 'lader', 'sx3', 'geo_southeast.nc')
    if year1 is None or year1 == year0:
        sx3_file = config.roots.join('DATA', 'lader', 'sx3', f'{snow_dataset}_sx3_{year0}.nc')
    else:
        sx3_file = config.roots.join('DATA', 'outputs', 'sx3', f'{snow_dataset}_sx3_{year0}_{year1}.nc')

    domains_margin_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains_margin.shp')
    dem_tif = r_ifsar(exp_mod, idom, jdom).outputs[0]
    inputs = [dem_tif, domains_margin_shp, geo_nc, sx3_file]

    if downscale_algo == 'lapse':
        dfcA_tif = r_dfcA(exp_mod).outputs[0]
        inputs.append(dfcA_tif)

    # Determine output filename
    ofname = os.path.join(exp_mod.dir, 'snow',
        f'{exp_mod.name}_{snow_dataset}_{year0}_{year1}_{downscale_algo}_{idom:03d}_{jdom:03d}.tif')

    def action(tdir):
        if downscale_algo == 'lapse':
            downscale_snow.downscale_sx3_with_lapse(
                sx3_file, geo_nc,
                dfcA_tif, dem_tif,
                ofname)
        else:
            raise ValueError(f'Unsupported downscale_algo: {downscale_algo}')

    return make.Rule(action, inputs, [ofname])

# -----------------------------------------------------------------------

