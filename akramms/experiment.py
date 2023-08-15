# Fundamental stuff needed to run an experiment.

import math


class DomainGrid(gisutil.RasterInfo):    # (gridD)
    def __init__(self, wkt, index_region_shp, domain_size, domain_margin):

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

def r_active_domains(exp_root, gridD, experiment_region_shp):
    """Writes a shapefile defining the domains for THIS experiment that will be used..."""

    # Load the experiment_region as a Shapely Multipolygon
    exp_name = os.path.split(exp_root)[1]
    domains_shp = os.path.join(exp_root, f'{exp_name}_domains.shp')
    domains_margin_shp = os.path.join(exp_root, f'{exp_name}_domains_margin.shp')
    def action(tdir):
        # Load the experiment region and convert to Shapely Polygon
        driver = ogr.GetDriverByName('ESRI Shapefile')
        src_ds = driver.Open(experiment_region_shp)
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
        os.makedirs(exp_root, exist_ok=True)
        shputil.write_df(df[['ix', 'iy', 'domain']], 'domain', 'MutliPolygon', somains_shp)
        shputil.write_df(df[['ix', 'iy', 'domain_margin']], 'domain_margin', 'MutliPolygon', somains_shp)
        
    return make.Rule([experiment_region_shp], [domains_shp, domains_margin_shp], action)

# -----------------------------------------------------------------------
@functools.lru_cache()
def r_ifsar(exp_mod, type, idom, jdom):
    """Select out a portion of the overall IFSAR dataset
    exp_dir:
        Top-level directory holding the Experment (assemblage of trials, defines idom,jdom meaning)
    exp_name:
        Short name for the experiment
    type:
        DTM / DSM / etc.
    idom, jdom:
        Index of the domain to select out.
    """

    ifsar_vrt = d_ifsar.r_vrt(type).outputs[0]
    ofname = os.path.join(exp_mod.dir, type, f'{exp_mod.name}_{type}_{idom}_{jdom}')

    def action(self, tdir):
        poly = exp_mod.domains.poly(combo.idom, combo.jdom, margin=True)
        return d_ifsar.extract(type, poly, ofname)
    return make.Rule([ifsar_vrt], [ofname], action)
# -----------------------------------------------------------------------
@functools.lru_cache()
def r_landcover(exp_mod, type, idom, jdom):
    """Select out a portion of the overall IFSAR dataset
    exp_dir:
        Top-level directory holding the Experment (assemblage of trials, defines idom,jdom meaning)
    exp_name:
        Short name for the experiment
    type:
        DTM / DSM / etc.
    idom, jdom:
        Index of the domain to select out.
    """

    ofname = os.path.join(exp_mod.dir, 'landcover', f'{exp_mod.name}_landcover_{idom}_{jdom}')

    def action(tdir):
        poly = exp_mod.domains.poly(combo.idom, combo.jdom, margin=True)
        return d_usgs_landcover.extract(type, poly, ofname)
    return make.Rule([d_usgs_landcover.landcover_img], [ofname], action)
        
# -----------------------------------------------------------------------
@functools.lru_cache()
def r_snow(exp_mod, snow_dataset, year0, year1, idom, jdom):

    dem_tif = r_ifsar(exp_mod, 'DTM', idom, jdom).outputs[0]
    ofname = os.path.join(exp_mod.dir, 'snow', f'{exp_mod.name}_'+snow_dataset+'_{idom}_{jdom}')

    def action(tdir):
        sx3_file = 








# (The "D" Grid)
def domain_grid(wkt, index_region_shp, domain_size, domain_margin):






class DomainGrid:
    def __init__(self, index_region_shp, domain_size, domain_margin):
        """
        experiment_root:
            Root directory for this experiment
        index_region_shp:
            Shapefile providing a rough polygon, which will be used to
            define the overall region in which ALL related experiments operate.
            Eg: Rough polygon around all of Alaska

        experiment_region_shp:
            More exact shapefile used to define domains for THIS experiment.
            Eg: exact polygon around land in Southeast Alaska
            (NOTE: If this is insize a .zip file, use:
                /vsizip/{avdomain_zip}/SE_AK_Domain_Land.shp)

        domain_size: (x, y) [m]
            Size of each domain within the experiment region
        domain_margin: (x, y) [m]
            Margin to add to each domain
        """

        # Load the overall index region
        self.index_region = list(shputil.read(index_region_shp))[0]['_shape']
        self.index_box = self.index_region.envelope  # Smallest rectangle with sides oriented to axes

        # ----------------------------------------
        # Determine "domain geotransform" based on index_region
        self.domain_size = domain_size
        self.domain_margin = domain_margin
        xx,yy = self.index_region.exterior.coords.xy
        self.x0 = xx[0]
        self.x1 = xx[1]
        self.y0 = yy[0]
        self.y1 = yy[2]

        self.xsgn = np.sign(self.x1-self.x0)
        self.ysgn = np.sign(self.y1-self.y0)
        self.dx = self.xsgn * self.domain_size[0]
        self.dy = self.ysgn * self.domain_size[1]
        self.nx = math.ceil((x1-x0)/self.dx)
        self.ny = math.ceil((y1-y0)/self.dy)

def r_




        # ----------------------------------------
        # Determine the experiment region (cached)
        fname = os.path.join(self.experiment_root, 'experiment_region.shp')
        if not os.path.exists(fname):
            os.makedirs(self.experiment_root, exist_ok=True)
            shutil.copy(experiment_region_shp, )

        # TODO: Write a YAML file with the __init__ parameter inputs



class DomainGrid:
    def __init__(self, root, wkt, index_region_shp, experiment_region_shp, domain_size, domain_margin):


    def domain(self, ix, iy, margin=False):
        """Identifies a domain polygon by index
        Returns: shapely.geometry.Polygon
            The domain with coordinates (ix,iy)
        """
        x0 = self.x0 + ix * self.dx
        y0 = self.y0 + iy * self.dy

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

    def experiment_region(self):
        """Returns: Shapely MultiPolygon
            Exact experiment domain shape"""


    def experiment_domains(self):
        """Returns dataframe with columns: (ix, iy, domain, domain_margin)
            Domains that overlap with the experiment region"""






    def domains(self):
        """
    # Load the overall Alaska shapefile
    print('Loading overall Alaska shapefile')
    all_alaska_zip = config.roots.syspath('{DATA}/fischer/AlaskaBounds.shp')
    all_alaska = list(shputil.read(all_alaska_zip))[0]['_shape']
    print(all_alaska)
    alaska_bounds = all_alaska.envelope    # Smallest rectangle with sides oriented to axes
    print(alaska_bounds)
    xx,yy = alaska_bounds.exterior.coords.xy
    #print(xx)
    #print(yy)
    x0 = xx[0]
    x1 = xx[1]
    y0 = yy[0]
    y1 = yy[2]


# ': gdal_translate -srcwin 60000 34000 500 500 ak_nlcd_2011_landcover_1_15_15.img ~/tmp/x.tif
