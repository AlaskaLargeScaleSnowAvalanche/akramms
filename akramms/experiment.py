# Fundamental stuff needed to run an experiment.

import math
import numpy as np
from osgo import ogr
from uafgi.util import make
from akramms import config
from akramms import d_ifar, d_usgs_landcover

class DomainGrid(gisutil.RasterInfo):    # (gridD)
    """Define a bunch of rectangles indexed by (idom, jdom).

    NOTE: This is a subclass of gisutil.RasterInfo.  Each "gridcell"
          in RasterInfo represents a domain in DomainGrid.
    """

    def __init__(self, wkt, index_region_shp, domain_size, domain_margin):

    """
        wkt:
            Projection to use.
        index_region_shp: shapefile name
            A simple polygon of the ENTIRE region that MIGHT be
            covered.  (i.e. all of Alaska).  This region is divided up
            into domain-size rectangles, which are given (idom,jdom)
            index numbers.  All portions of the experiment must happen
            INSIDE this region.
        domain_size: (x,y)
            Size of each domain
        domain_margin: (x,y)
            Amount of margin to add to each domain.
            (For avalanches that start near the edge and run out).

        """

        # Load the overall index region
        index_region = list(shputil.read(index_region_shp))[0]['_shape']
        index_box = index_region.envelope  # Smallest rectangle with sides oriented to axes

        # ----------------------------------------
        # Determine "domain geotransform" based on index_region
        domain_size = domain_size
        domain_margin = domain_margin
        xx,yy = index_region.exterior.coords.xy
        x0 = xx[0]
        x1 = xx[1]
        y0 = yy[0]
        y1 = yy[2]

        xsgn = np.sign(x1-x0)
        ysgn = np.sign(y1-y0)
        dx = xsgn * domain_size[0]
        dy = ysgn * domain_size[1]
        nx = math.ceil((x1-x0)/dx)
        ny = math.ceil((y1-y0)/dy)

        # Geotransform
        GT = np.array([x0, dx, 0, y0, 0, dy])
        super().__init__(wkt, nx, ny, GT)

        self.domain_margin = domain_margin

    def poly(self, ix, iy, margin=False):
        """Returns given rectangle by index.
        ix, iy:
            Coordinates of the domain within the overall region.
        margin:
            Should the margin be included in the box returned?
        Returns:
            A rectangular polygon, oriented in standard (counter clockwise) fashion.
        """

        GT = self.geotransform
        x0 = GT[0] + GT[1] * ix
        y0 = GT[3] + GT[5] * iy

        if margin:
            mx = self.xsgn * self.domain_margin[0]
            my = self.ysgn * self.domain_margin[1]
        else:
            mx = 0
            my = 0

        coords = [
            (x0-mx, y0-my),
            (x0+self.dx+mx, y0-my),
            (x0+self.dx+mx, y0+self.dy+my),
            (x0-mx, y0+self.dy+my),
            (x0-mx, y0-my)]
        return shapely.geometry.Polygon(coords)

@functools.lru_cache()
def r_active_domains(exp_mod):
    """Writes a shapefile defining the domains for THIS experiment that will be used...

    exp_mod:
        Root directory for the overall experiment (includes individual trials inside).
    gridD: DomainGrid
        The set of domains
    experiment_region_shp:
        A shapefile covering *just* the regions 
    Output:
        {exp_name}_domains.shp:
            The domains from griD that touch the experiment_region_shp
            Includes columns ix,iy giving indices of each domain.
        {exp_name}_domains_margin.shp:
            Same as {exp_name}_domains.shp, but includes margin.
            This is the domain that will be used for eCognition (and subsetted for RAMMS).
    """

    gridD = exp_mod.domains


    # Load the experiment_region as a Shapely Multipolygon
    domains_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains.shp')
    domains_margin_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains_margin.shp')
    def action(tdir):
        # Load the experiment region and convert to Shapely Polygon
        driver = ogr.GetDriverByName('ESRI Shapefile')
        src_ds = driver.Open(exp_mod.experiment_region_shp)
        src_lyr = src_ds.GetLayer()   # Put layer number or name in her
        while True:
            feature = src_lyr.GetNextFeature()
            if feature is None:    # There should be only ONE feature.
                break

            geom = feature.GetGeometryRef()
            polygons = list()
            npoly = geom.GetGeometryCount()
            for ix in range(npoly):
                ring = geom.GetGeometryRef(ix).GetGeometryRef(0)
                npoints = ring.GetPointCount()
                points = list()
                for p in range(0,npoints):
                    x,y,z = ring.GetPoint(p)
                    points.append(shapely.geometry.Point(x,y))
                polygons.append(shapely.geometry.Polygon(points))
            experiment_region shapely.geometry.MultiPolygon(polygons)

        rows = list()
        for iy in range(0, self.ny):
            for ix in range(0, self.nx):
                domain = self.domain(ix, iy)
                if domain.intersects(experiment_region):
                    domain_margin = self.domain(ix, iy, margin=True)
                    rows.append((ix,iy,domain,domain_margin)

        df = pd.DataFrame(rows, columns=('ix', 'iy', 'domain', 'domain_margin'))
        os.makedirs(exp_mod.dir, exist_ok=True)
        shputil.write_df(df[['ix', 'iy', 'domain']], 'domain', 'MutliPolygon', domains_shp)
        shputil.write_df(df[['ix', 'iy', 'domain_margin']], 'domain_margin', 'MutliPolygon', domains_margin_shp)
        
    return make.Rule([exp_mod.experiment_region_shp], [domains_shp, domains_margin_shp], action)

# -----------------------------------------------------------------------
@functools.lru_cache()
def r_ifsar(exp_mod, idom, jdom):
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

    type = 'DTM'
    ifsar_vrt = d_ifsar.r_vrt(type).outputs[0]
    ofname = os.path.join(exp_mod.dir, type, f'{exp_mod.name}_{type}_{idom:03d}_{jdom:03d}.tif')

    def action(self, tdir):
        poly = exp_mod.domains.poly(combo.idom, combo.jdom, margin=True)
        return d_ifsar.extract(type, poly, ofname)
    return make.Rule([ifsar_vrt], [ofname], action)
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
        poly = exp_mod.domains.poly(combo.idom, combo.jdom, margin=True)
        return d_usgs_landcover.extract(type, poly, ofname)
    return make.Rule([d_usgs_landcover.landcover_img], [ofname], action)
# -----------------------------------------------------------------------
@functools r_forest(exp_mod, idom, jdom):
    """Convert a landcover file to a forest file."""

    landcover_tif = r_landcover(exp_mod, idom, jdom).outputs[0]
    ofname = os.path.join(exp_mod.dir, 'forest', f'{exp_mod.name}_forest_{idom:03d}_{jdom:03d}.tif')
    def action(tdir):
        grid_info, landcover, landcover_nd = gdalutil.read_raster(landcover_tif)

        # Convert to forest
        forest = (landcover == 42)

        # Write it out!
        gdalutil.write_raster(ofname, grid_info, forest, 0, type=gdal.GDT_Byte)

    return make.Rule([landcover_tif], [ofname], action)

# -----------------------------------------------------------------------
@functools.lru_cache()
def r_dfcA(exp_mod, idom, jdom):
    """dfc = distance from coast
    It is computed from the IFSAR DTM file."""

    distance_from_coastA_tif = os.path.join(
        exp_mod.dir, 'DFC', f'{exp_mod.name}_DFC_{idom:03}_{jdom:03}.tif')
    geo_nc = config.join('DATA', 'lader', 'sx3', 'geo_southeast.nc')

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
    geo_nc = config.join('DATA', 'lader', 'sx3', 'geo_southeast.nc')
    if year1 is None or year1 == year0:
        sx3_file = config.join('DATA', 'lader', 'sx3', f'{snow_dataset}_sx3_{year0}.nc')
    else:
        sx3_file = config.join('DATA', 'outputs', 'sx3', f'{snow_dataset}_sx3_{year0}_{year1}.nc')

    domains_margin_shp = os.path.join(exp_mod.dir, f'{exp_mod.name}_domains_margin.shp')
    dem_tif = r_ifsar(exp_mod, 'DTM', idom, jdom).outputs[0]
    inputs = [domains_margin_shp, geo_nc, sx3_file]

    if downscale_algo == 'lapse':
        dfcA_tif = r_dfcA(exp_mod, idom, jdom).outputs[0]
        inputs.append(dfcA_tif)

    # Determine output filename
    ofname = os.path.join(exp_mod.dir, 'snow', f'{exp_mod.name}_{snow_dataset}_{downscale_algo}_{idom:03d}_{jdom:03d}')

    def action(tdir):
        if downscale_algo == 'lapse':
            downscale_snow.downscale_sx3_with_lapse(
                sx3_file, geo_nc,
                distance_from_coastA_tif, dem_tif,
                ofname)
        else:
            raise ValueError(f'Unsupported downscale_algo: {downscale_algo}')

    return make.Rule(inputs, [ofname], action)

# -----------------------------------------------------------------------


stage0_rules(rules, scene_dir):

    scene_args = params.load(scene_dir)

    # Create snow input file on the scene grid
    if scene_args['downscale'] == 'select':
        snow_input = rules.add(r_snow.select_sx3_rule(
            scene_dir, scene_args['snowdepth_file'], scene_args['snowdepth_geo'])).outputs[0]
    elif scene_args['downscale'] == 'lapse':
        distance_from_coastA_tif = os.path.join(scene_dir, 'distance_from_coastA.tif')
        rules.add(r_snow.distance_from_coast_rule(
            scene_args['snowdepth_geo'], distance_from_coastA_tif))

        snow_input = rules.add(r_snow.lapse_sx3_rule(
            scene_dir, scene_args['snowdepth_file'], scene_args['snowdepth_geo'],
            distance_from_coastA_tif)).outputs[0]

    else:
        raise ValueError("Illegel downscale algorithm: '{}'".format(scene_args['downscale']))

    # Run ArcGIS script to prepare files for eCognition
    prepare_outputs = rules.add(r_prepare.rule(scene_dir)).outputs

    # Get neighbor1 graph for DEM routing network
    dem_file = scene_args['dem_file']
    dem_filled_file,sinks_file,neighbor1_file = rules.add(r_domain_builder.neighbor1_rule(
        dem_file, scene_dir, fill_sinks=True)).outputs

    # Loop over combos
#    ramms_dirs_release_files = list()    # [(ramms_dir, [release_file, ...]), ...]
#    all_ramms_dirs = list()
    all_release_files = list()    # Release files we will run RAMMS on
    for return_period in scene_args['return_periods']:
        for forest in scene_args['forests']:

            # Run eCognition
            rules.add(r_ecog.rule(scene_dir, prepare_outputs, return_period, forest))

#            # Burn PRAs produced by eCognition into raster
#            pra_file, pra_burn_file = process_tree.pra_files(scene_args, return_period, forest)
#            rules.add(
#                r_domain_builder.burn_pra_rule(dem_file, pra_file, pra_burn_file))

            # Post-Process eCognition Output (the pra_file)
            # and also split into chunks.
            # [f'{scene_name}{For}_{resolution}m_{return_period}{cat_letter}_rel.shp', ...]
            pra_post_rule, ramms_names = r_pra_post.rule(
                scene_dir, dem_filled_file, return_period, forest, snow_input)
            release_shplists = rules.add(pra_post_rule).outputs

            rules.add(r_ramms.chunk_rule(scene_dir, ramms_names))
