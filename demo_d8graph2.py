import numpy as np
import d8graph
from dggs.avalanche import domain
from uafgi.util import shputil,shapelyutil,gdalutil,make

pra_file = '/Users/eafischer2/av/prj/juneau1/juneau1_For_5m_30L_rel.shp'
dem_file = '/Users/eafischer2/av/data/wolken/BaseData_AKAlbers/Juneau_IFSAR_DTM_AKAlbers_EPSG_3338.tif'
neighbor1_file = 'neighbor1.pik'
domain_file = 'dom.shp'

# --------------------------------------------------------------------
def neighbor1_rule(dem_file, neighbor1_file, fill_sinks=True):
    """Compute and store the neighbors graph."""

    def action(tdir):
        grid_info, dem, nodata = gdalutil.read_raster(dem_file)
        neighbor1 = d8graph.neighbor_graph(dem, nodata, int(fill_sinks))

        # For now, just store as Pickle.
        # TODO: Store as GeoTIFF
        with gzip.open(neighbors1_pik, 'wb') as out:
            pickle.dump(grid_info)
            pickle.dump(nodata)
            pickle.dump(neighbor1, out)
            pickle.dump(dem, out)    # In case for later inspection

    return make.Rule(action, [dem_file], [neighbor1_file])

# --------------------------------------------------------------------
def domain_rule(neighbor1_file, pra_files, domain_files):
    """Compute domains for each PRA."""

    def action(tdir):
        # Read the neighbor1 file
        with gzip.open(neighbor1_pik, 'rb') as fin:
            grid_info = pickle.load(fin)
            nodata = pickle.load(fin)
            neighbor1 = pickle.load(fn)
            # dem = pickle.load(fn)    # Not needed

        for pra_file,domain_file in zip(pra_files, domain_files):
            # Read the PRAs
            pras_df = shputil.read_df(pras_file)
            if 'fid' in pras_df:
                pras_df = pras_df.rename(columns={'fid': 'Id'})  # RAMMS etc. want it named "Id"

            # Find domains based on the PRAs
            domains = list()
            for _,row in pras_df.iterrows():
                pra = row['shape']

                # Burn the PRA polygon into a raster
                pra_ds = shapelyutil.to_datasource(pra)
                pra_ras = gdalutil.rasterize_polygons(pra_ds, self.grid_info)
                pra_ds = None    # Free memory

                # Convert to a list of initial gridcell IDs
                pra_ras1d = pra_ras.reshape(-1)
                start_cells = np.where(pra_ras1d)[0].astype('i')

                # Find the domain based on the start cells
                domain = shapely.geometry.Polygon(
                    d8graph.find_domain(neighbor1, start_cells, grid_info.geotransform, margin=margin))
                domains.append(domain)

            # All done... construct new dataframe
            domains_df = pars_df[['Id']]
            domains_df['shape'] = domains

            # Store it as a Shapefile
            shputil.write_df(domains_df, 'shape', 'Polygon', domain_file, wkt=grid_info.wkt)

    return make.Rule(action, [neighbor1_file, pra_file], [domain_file])

def main():
    neighbor1_rule(dem_file, neighbor1_file)()
#    domain_rule(neighbor1_file, [pra_file], [domain_file])()

main()
