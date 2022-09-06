import gzip,pickle
import numpy as np
import shapely
import d8graph
from uafgi.util import shputil,shapelyutil,gdalutil,make

# --------------------------------------------------------------------
def neighbor1_rule(dem_file, fill_sinks=True):
    """Compute and store the neighbors graph."""

    neighbor1_file = '{}_neighbor1.pik.gz'.format(dem_file[:-4])

    def action(tdir):
        # Read the DEM
        grid_info, dem, nodata = gdalutil.read_raster(dem_file)

        # Print info on the DEM
        print('nodata = ',nodata)
        print('Total gridcells = ', dem.shape[0] * dem.shape[1])
        print('# nodata = ', np.sum(dem == nodata))
        print('# zero = ', np.sum(dem == 0))


        # Blank out zero-elevation squares because they are ocean (not land)
        dem[dem == 0] = nodata    # Blank out zero-elevation squares (sea level)

        # Compute the degree-1 neighbor graph on the DEM
        neighbor1 = d8graph.neighbor_graph(dem, nodata, int(fill_sinks))


        # For now, just store as Pickle.
        # TODO: Store as GeoTIFF
        with gzip.open(neighbor1_file, 'wb') as out:
            pickle.dump(grid_info, out)
            pickle.dump(nodata, out)
            pickle.dump(neighbor1, out)
            pickle.dump(dem, out)    # In case for later inspection

    return make.Rule(action, [dem_file], [neighbor1_file])

# --------------------------------------------------------------------
def domain_rule(neighbor1_file, pra_file, domain_file, margin=0):
    """Compute domains for each PRA.
    neighbor1_file: filename
        Result of neighbor1_rule
    pra_file: filename
        File of PRAs (result of pra_post_rule)
    domain_file: filename
        Output filename (shapefile of domains)
    margin:
        Margin to add around convex hull to minimum bounding rectangle."""

    def action(tdir):
        # Read the neighbor1 file
        with gzip.open(neighbor1_file, 'rb') as fin:
            grid_info = pickle.load(fin)
            nodata = pickle.load(fin)
            neighbor1 = pickle.load(fin)
            # dem = pickle.load(fin)    # Not needed

        # Read the PRAs
        pras_df = shputil.read_df(pra_file)
        if 'fid' in pras_df:
            pras_df = pras_df.rename(columns={'fid': 'Id'})  # RAMMS etc. want it named "Id"

        # Find domains based on the PRAs
        domains = list()
        for _,row in pras_df.iterrows():
            pra = row['shape']

            # Burn the PRA polygon into a raster
            pra_ds = shapelyutil.to_datasource(pra)
            pra_ras = gdalutil.rasterize_polygons(pra_ds, grid_info)
            pra_ds = None    # Free memory

            # Convert to a list of initial gridcell IDs
            pra_ras1d = pra_ras.reshape(-1)
            start_cells = np.where(pra_ras1d)[0].astype('i')

            # Find the domain based on the start cells
            domain = shapely.geometry.Polygon(
                d8graph.find_domain(neighbor1, start_cells, grid_info.geotransform, margin=margin))
            domains.append(domain)

        # All done... construct new dataframe
        domains_df = pras_df[['Id']]
        domains_df['shape'] = domains

        # Store it as a Shapefile
        shputil.write_df(domains_df, 'shape', 'Polygon', domain_file, wkt=grid_info.wkt)

    return make.Rule(action, [neighbor1_file, pra_file], [domain_file])
