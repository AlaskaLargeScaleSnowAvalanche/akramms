from osgeo import gdal
import gzip,pickle,os
import numpy as np
import shapely
import d8graph
import sys
from uafgi.util import shputil,shapelyutil,gdalutil,make,gisutil,rasterize

# --------------------------------------------------------------------
def read_neighbor1(neighbor1_file):
    """Read the neighbor1 file, converting from on-disk relative
    indexing to in-memory absolute indexing."""
    grid_info, neighbor1, nodata = gdalutil.read_raster(neighbor1_file)
    d8graph.convert_neighbor1(neighbor1, 'absolute')
    return grid_info, neighbor1, nodata

def write_neighbor1(neighbor1_file, grid_info, neighbor1, nodata_value):
    """Write the neighbor1 file, temporarily converting to relative indexing."""
    d8graph.convert_neighbor1(neighbor1, 'relative')
    gdalutil.write_raster(
        neighbor1_file, grid_info, neighbor1, nodata_value,
        driver='GTiff', type=gdal.GDT_Int32)
    d8graph.convert_neighbor1(neighbor1, 'absolute')
# --------------------------------------------------------------------
def neighbor1_rule(dem_file, odir, fill_sinks=True):
    """Compute and store the neighbors graph."""

    dem_root = os.path.split(dem_file)[1][:-4]
    dem_filled_file = os.path.join(odir, f'{dem_root}_filled.tif')
    sinks_file = os.path.join(odir, f'{dem_root}_sinks.tif')
    neighbor1_file = os.path.join(odir, f'{dem_root}_neighbor1.tif')

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
        # (This also fills sinks in dem)
        sinks, neighbor1 = d8graph.neighbor_graph(dem, nodata, int(fill_sinks))
        dem_filled = dem    # dem has now been filled in, change name appropriately

        # Write sinks and neighbor1 so we can forget about them
        gdalutil.write_raster(sinks_file, grid_info, sinks, -1)
        sinks = None
        write_neighbor1(neighbor1_file, grid_info, neighbor1, None)
        neighbor1 = None

        # -----------------------------------------------------------
        # dem has now been filled in.  Re-read the original DEM to mask-in ocean areas.
        _, dem, _ = gdalutil.read_raster(dem_file)
        dem_filled[dem==0.0] = 0.0
        gdalutil.write_raster(dem_filled_file, grid_info, dem, nodata, type=gdal.GDT_Float64)

    return make.Rule(action, [dem_file], [dem_filled_file, sinks_file, neighbor1_file])
# --------------------------------------------------------------------
def burn_pra_rule(dem_file, pra_file, pra_burn_file):#, ix0, ix1):
    """Reads a PRA _rel.shp file into a dataframe; adds a column for
    the gridcell indices of the burned polygon; and writes out to a
    Pickle.gz file.

    neighbor1_file: filename
        Result of neighbor1_rule.  (Used ONLY for the grid_info at the beginning of this file)
    pra_file: filename
        File of PRAs (result of pra_post_rule)

    """

    def action(tdir):
        debug = False   # Check domain-limited burn against full burn

        # Read the grid_info from the DEM
        grid_info = gdalutil.grid_info(dem_file)

        # Read the PRAs from the shapefile
        pras_df = shputil.read_df(pra_file)
#        pras_df = pras_df.head(10)    # DEBUG

        # Burn the PRAs into rasters; and extract lists of start_cells
        pra_burns = list()
        npra = len(pras_df)
        for ipra,(_,row) in enumerate(pras_df.iterrows()):
            pra = row['shape']

            # ---------------------------------------------------
            # Burn on entire raster ("Slow Burn")
            if debug:
                pra_ds = shapelyutil.to_datasource(pra)
                pra0_ras = rasterize.rasterize_polygons(pra_ds, grid_info)
                pra_ds = None    # Free memory

                # Convert to a list of initial gridcell IDs
                jarr0, iarr0 = np.where(pra0_ras)
                jarr0 = jarr0.astype('i')
                iarr0 = iarr0.astype('i')

                pra0_ras1d = pra0_ras.reshape(-1)
                pra0_burn_a = np.where(pra0_ras1d)[0].astype('i')
                pra0_burn_b = jarr0 * grid_info.nx + iarr0
                assert np.all(pra0_burn_a == pra0_burn_b)  # Get our indexing correct

            # ------------ Work in a smaller coord system ("Fast Burn")
            # Get oriented minimum bounding rectangle (MBR)
            xx,yy = pra.exterior.coords.xy
            minx = np.min(xx)
            maxx = np.max(xx)
            miny = np.min(yy)
            maxy = np.max(yy)

            # Extent of the polygon in pixels
            margin = 2
            mini,minj = grid_info.to_ij(minx,miny)
            maxi,maxj = grid_info.to_ij(maxx,maxy)
            origin_i = mini-margin if grid_info.dx > 0 else maxi-margin
            origin_j = minj-margin if grid_info.dy > 0 else maxj-margin
            origin_x,origin_y = grid_info.to_xy(origin_i, origin_j)

            #if debug:
            #    print('pra ', pra)
            #    print('origin_xy ', origin_x, origin_y)

            # Size to make new grid: put 2-pixel margen on all sides
            nx1 = abs(maxi-mini) + margin*2
            ny1 = abs(maxj-minj) + margin*2

            # Define new grid_info for smaller coord system
            gt1 = np.array(grid_info.geotransform)
            gt1[0] = origin_x
            gt1[3] = origin_y
            #print('gt-diff x: ', gt1[0] - grid_info.geotransform[0])
            #print('gt-diff y: ', gt1[3] - grid_info.geotransform[3])
            grid_info1 = gisutil.RasterInfo(
                grid_info.wkt, nx1, ny1, gt1)

            # ---------- Now working in sub-coord system (grid_info1 / pra1)
            # Burn the PRA polygon into a raster
            # pra1_ras is np.array(nj, ni)
            pra1_ds = shapelyutil.to_datasource(pra)
            pra1_ras = rasterize.rasterize_polygons(pra1_ds, grid_info1)
            pra1_ds = None    # Free memory

            #print('pra1_ras\n', pra1_ras)
            #print('yyyy ', grid_info.nx, grid_info.ny)
            #print('burn-size: {} vs {}'.format(np.sum(pra1_ras), np.sum(pra0_ras)))
            if debug:
                assert np.sum(pra1_ras) == np.sum(pra0_ras)

            # Get x and y coordinates of burnt pixels (two numpy arrays of indices)
            jarr1, iarr1 = np.where(pra1_ras)
            jarr1 = jarr1.astype('i')
            iarr1 = iarr1.astype('i')

            #if debug:
                #print('iarr0 ', iarr0)
                #print('iarr1 ', iarr1 + origin_i)
                #print('jarr0 ', jarr0)
                #print('jarr1 ', jarr1 + origin_j)


            pra1_burn = (jarr1+origin_j) * grid_info.nx + (iarr1 + origin_i)
            if debug:
                print('pra0_burn_a ', pra0_burn_a)
                print('pra1_burn ', pra1_burn)
                assert np.all(pra0_burn_a == pra1_burn)

            print('PRA {} of {} burned with {} cells'.format(ipra, npra, len(pra1_burn)))
            sys.stdout.flush()
            pra_burns.append(pra1_burn)

        # Add to the dataframe and save
#        pras_df['pra_burn'] = pra_burns
        print('Writing PRAs to file: {}'.format(pra_burn_file))
        with gzip.open(pra_burn_file, 'wb') as out:
            pickle.dump(grid_info, out)
            pickle.dump(pra_burns, out)
#            pickle.dump(pras_df, out)

    return make.Rule(action, [dem_file, pra_file], [pra_burn_file])

# --------------------------------------------------------------------
def domain_rule(dem_filled_file, release_file, chull_file, domain_file, min_alpha=18., max_runout=10000., margin=0.):
    """Compute domains for each PRA.
    neighbor1_file: filename
        Result of neighbor1_rule
    dem_filled_file: filename
        DEM that with sinks filled (while computing neighbor1)
    pra_file: filename
        File of PRAs (result of pra_post_rule)
    chull_file: filename
        Output filename for convex hulls
    domain_file: filename
        Output filename (shapefile of domains)
    margin:
        Margin to add around convex hull to minimum bounding rectangle."""

    outputs = [domain_file, chull_file]

    def action(tdir):
        # Read dem_filled and neighbor1
        grid_info, dem_filled, dem_nodata = gdalutil.read_raster(dem_filled_file)
#        grid_info, neighbor1, _ = read_neighbor1(neighbor1_file)
#        print('Sample dem_filled[18729844] = {}'.format(dem_filled.reshape(-1)[18729844]))

        # Read the PRAs
        pras_df = shputil.read_df(release_file)
#        with gzip.open(pra_burn_file, 'rb') as fin:
#            _ = pickle.load(fin)    # grid_info
#            pra_burns = pickle.load(fin)
##            pras_df = pickle.load(fin)

        # Find domains based on the PRAs
        chulls = list()
        domains = list()
        for n,(_,row) in enumerate(pras_df.iterrows()):
            id = row['Id']
            if n%1000 == 0:
                print(f'Found {n} domains.')


#            pra_burn = pra_burns[id]    # Look up pra_burn in auxilliary list (or maybe dict)

            # Get list of gridcells covered by the PRA polygon (the "PRA Burn")
            pra_burn = rasterize.rasterize_polygon_compressed(row['shape'], grid_info)

            # Get the domain from the PRA burn
            args = (dem_filled, dem_nodata, grid_info.geotransform, pra_burn)
            ret = d8graph.find_domain(*args, margin=margin, debug=1, min_alpha=min_alpha, max_runout=max_runout)
            if ret is not None:
                seen,chull_list,domain_list = ret
                chulls.append(shapely.geometry.Polygon(chull_list))
                domains.append(shapely.geometry.Polygon(domain_list))
            else:
                # Not able to make a domain
                chulls.append(shapely.geometry.Polygon([]))
                domains.append(shapely.geometry.Polygon([]))

        # Create directories needed for output files
        dirs = set(os.path.split(x)[0] for x in outputs)
        for dir in dirs:
            print(f'Creating directory: {dir}')
            os.makedirs(dir, exist_ok=True)

        # Store chulls as a Shapefile
        chulls_df = pras_df[['Id']]
        chulls_df['shape'] = chulls
        shputil.write_df(chulls_df, 'shape', 'Polygon', chull_file, wkt=grid_info.wkt)

        # Store domains as a Shapefile
        domains_df = pras_df[['Id']]
        domains_df['shape'] = domains
        shputil.write_df(domains_df, 'shape', 'Polygon', domain_file, wkt=grid_info.wkt)

    return make.Rule(action, [dem_filled_file, release_file], outputs)
