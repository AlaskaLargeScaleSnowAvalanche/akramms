import numpy as np
import pandas as pd
import geopandas
import shapely
import shapely.geometry
from uafgi.util import shapelyutil
import gzip,pickle
import shapely.affinity

epsilon = 1e-14

class ScaledNorm:
    """Computes L2 norms for values in pixel coordinates, but outputs
    lengths in geographic coordinates"""
    def __init__(self, dx, dy):
        self.dx2 = dx*dx
        self.dy2 = dy*dy

    def __call__(self, x0,y0,x1,y1):
        xx = x1-x0
        yy = y1-y0
        return np.sqrt(xx * xx * self.dx2 + yy * yy * self.dy2)

def axis_crossings(x0, y0, x1, y1, xycols, norm_fn):

    # x coordinates crossed by the line
    x_crossings_x = np.arange(np.ceil(x0), x1 + epsilon)

    # (x-x0) = my (y - y0)
    m = (y1-y0) / (x1-x0)    # slope
    x_crossings_y = m * (x_crossings_x - x0) + y0

    # t = distance along the line
    x_crossings_t = norm_fn(x0, y0, x_crossings_x, x_crossings_y)

    df = pd.DataFrame({'t': x_crossings_t, xycols[0]: x_crossings_x, xycols[1]: x_crossings_y})
#    print(df)
    return df


def _make_positive(nx, x0, x1):
    if x1 > x0:
        return x0, x1, False
    else:
        return nx-x0, nx-x1, True


def pixel_crossings(val_grid, x0, y0, x1, y1, drop_end=True):
    """drop_end:
        If True, drop the last point in the dataframe.
        This results in one line per line segment, but without
        explicit record of the ending point.
    """
#    print('***** pixel_crossings ', x0, y0, x1, y1)
    x0, x1, flipx = _make_positive(val_grid.nx, x0, x1)
    y0, y1, flipy = _make_positive(val_grid.ny, y0, y1)
#    print('***** pixel_crossings ', x0, y0, x1, y1)


    normxy = ScaledNorm(val_grid.dx, val_grid.dy)
    if x1 != x0:
        dfx = axis_crossings(x0, y0, x1, y1, ['x', 'y'], normxy)
    if y1 != y0:
        normyx = ScaledNorm(val_grid.dy, val_grid.dx)
        dfy = axis_crossings(y0, x0, y1, x1, ['y', 'x'], normyx)

    # Beginning and ending points
    dfbe = pd.DataFrame([
        (0, x0, y0),
        (normxy(x0,y0,x1,y1), x1, y1),
        ], columns=['t', 'x', 'y'])

    df = pd.concat([dfx, dfy, dfbe]).sort_values(['t']).reset_index(drop=True)
    df = df.groupby('t', as_index=False).agg({'x': 'first', 'y': 'first'})    # Drop / sum duplicates

    df['len'] = -df.t.diff(periods=-1)

    # Account for the flip(s) in the answer
    if flipx:
        df['x'] = df.x.map(lambda x: val_grid.nx - x)
    df['i'] = df.x.map(int)
    if flipx:
         df['i'] = df.i.shift(-1, fill_value=-1)

    if flipy:
        df['y'] = df.y.map(lambda y: val_grid.ny - y)
    df['j'] = df.y.map(int)
    if flipy:
         df['j'] = df.j.shift(-1, fill_value=-1)


    # Remove end point, so dataframe is number of segments
    if drop_end:
        df = df.iloc[:-1]
    return df

# ------------------------------------------------------------------------------
def iterate_ls(ls):

    """
    ls:
        LineString or MultiLineString
    yields:
        x0,y0,x1,y1
    """
    if isinstance(ls, shapely.geometry.LineString):
        for p0,p1 in zip(ls.coords[:-1], ls.coords[1:]):
            yield p0[0], p0[1], p1[0], p1[1]
    elif isinstance(ls, shapely.geometry.MultiLineString):
        for part in ls.geoms:
            for p0, p1 in zip(part.coords[:-1], part.coords[1:]):
                yield p0[0], p0[1], p1[0], p1[1]
    else:
        raise TypeError(f'I do not know how to iterate over {ls}')


def linestrings_crossings(lss, val_grid, val_data):
    """
    lss: Serieds[Shapely LineString, ...]
        Column from geo dataframe (with index)
    tile_grid:
        The grid defining the current tile (no margin)
    """

#    # DEBUG
#    lengths = [ls.length for ls in lss]
#    print('========= lengths ', lengths)

    # Convert to ij coordinates (ir, jr) are real numbers
    dfs = list()
    geoinv_affine = shapelyutil.to_affine(val_grid.geoinv)
    bbox = shapely.affinity.affine_transform(val_grid.bounding_box(), geoinv_affine)
    bbox = shapely.orient_polygons(bbox, exterior_cw=False)     # Might be needed...

    # Clip to bounding box
    lss = lss.map(lambda ls: shapely.intersection(ls, bbox))

    # Consider each segment
    for lsix,ls in lss.items():    # ix = Index value
        for xyxy in iterate_ls(ls):
            # Flip line segment to slope-positive
            df = pixel_crossings(val_grid, *xyxy)
            df['lsix'] = lsix
            dfs.append(df)

    df = pd.concat(dfs)

    # Select out raster values and multiply by len for integration
    df['i'] = df.x.map(int)
    df['j'] = df.y.map(int)

    return df
# ---------------------------------------------------------------------


def _calc_integrations(df1):
    total_len = df1.len.sum()    # Divide by this when computing means...
    return pd.Series({
        'max_velocity': df1.max_velocity.max(),
        'length': df1.len.sum(),
        'mean_deposition': (df1.len * df1.deposition).sum() / total_len,
        'max_deposition': df1.deposition.max(),
    })    

def r_integrate(expmod, combo):
    ifname = expmod.root_dir / f'roadcover/{expmod.name}-{combo.base_str()}/{expmod.name}-{repr(combo)}-roadcover.pik.gz'
    ofname = expmod.root_dir / f'roadcover/{expmod.name}-{combo.base_str()}/{expmod.name}-{repr(combo)}-roadstats.shp'


    vnames = ['max_velocity', 'deposition']
    val_tifs = [
        expmod.root_dir / 'publish' / f'{expmod.name}-{repr(combo)}' / vname / f'{expmod.name}-{repr(combo)}-F-{vname}.tif'
        for vname in vnames]


    def action(tdir):


        # Read road segments that intersect with one or more avalanches
        with gzip.open(ifname) as fin:
            rdf = pickle.load(fin)

        # Read raster to integrate over
#        val_grid, val_data, val_nd = gdalutil.read_raster(val_tif)
        val_grid, _, _ = gdalutil.read_raster(val_tifs[0], False)

        # Clip to within the margin
        bbox = val_grid.bounding_box()
        rdf['geometry'] = [shapely.intersection(ls, bbox) for ls in rdf.geometry]


        # Group together by Route_ID
        # (Because one road segment can intersect multiple avalanche extents)
        rows = list()
        for Route_ID, xdf in rdf.groupby('Route_ID'):
            ls = shapely.unary_union(xdf.geometry)
            Avalanche_Ids = tuple(xdf.Id)    # AKRAMMS avlanache IDs for this combo
            rows.append((Route_ID, ls))
        rdf = geopandas.GeoDataFrame(rows, columns=('Route_ID', 'geometry'), geometry='geometry', crs=expmod.wkt)

        # Find line segment crossings, raster coordinates and lengths
        ijdf = linestrings_crossings(rdf.geometry, val_grid, val_data)

        # =============== Compute functions on rasters
        cols = dict()

        # Load rasters to integrate over
        for vname,ifname in zip(vnames, val_tifs):
            val_grid, val_data, val_nd = gdalutil.read_raster(ifname)
            ijdf[vname] = val_data[ijdf.i, ijdf.j]

        # Do the integration
        statsdf = ijdf.groupby('Route_ID').apply(_calc_integration, include_groups=False)
        statsdf = statsdf.merge(rdf, on='Route_ID')
        statsdf = geopandas.GeoDataFrame(statsdf, crs=expmod.wkt)

        # Write it out
        statsdf.to_file(ofname)    # Implied driver='ERSI Shapefile'

    return make.Rule(action, [ifname] + _vnames, [ofname])



def main():
    import akramms.experiment.aksc5 as expmod
    from uafgi.util import gdalutil

#    rdf = geopandas.read_file(expmod.root_dir / 'roadcover' / f'{expmod.name}_roadcover.gpkg')
#    print(rdf)

    combo = expmod.Combo('ccsm', 'past', 'sclapse', 'NoFor', 30, 91, 41)

    ifname = f'/home/efischer/prj/aksc5/roadcover/aksc5-ccsm-past-sclapse-NoFor-30/{expmod.name}-{repr(combo)}-roadcover.pik.gz'

    with gzip.open(ifname) as fin:
        rdf = pickle.load(fin)
    rdf = rdf.sort_values('Id')
    print(rdf[['Id', 'Route_ID']])
    print(rdf.iloc[0])
    return


    # Clip to within the margin
    bbox = val_grid.bounding_box()
    rdf['geometry'] = [shapely.intersection(ls, bbox) for ls in rdf.geometry]


    rows = list()
    for Route_ID, xdf in rdf.groupby('Route_ID'):
        ls = shapely.unary_union(xdf.geometry)
        Avalanche_Ids = tuple(xdf.Id)    # AKRAMMS avlanache IDs for this combo
        rows.append((Route_ID, ls))



    print(sum(x.length for x in rdf.geometry))
    ls = shapely.unary_union(rdf.geometry)
    print(ls.length)
#    print(rdf)
#    return


#    for tup in rdf.itertuples(index=False):
#        print(tup)
#        print(tup.geometry)
#        print(combo.idom,combo.jdom)
    if True:
#        lss = [shapely.unary_union(rdf.geometry)]
        lss = list(rdf.geometry)
        lss = [shapely.force_2d(ls) for ls in lss]

        val_tif = expmod.root_dir / 'publish.v6/aksc5-ccsm-past-sclapse-All-300/max_pressure' / f'aksc5-ccsm-past-sclapse-All-300-{combo.idom:03d}-{combo.jdom:03d}-F-max_pressure.tif'
        val_grid, val_data, val_nd = gdalutil.read_raster(val_tif)
        dfs = integrate_linestrings(lss, val_grid, val_data)
        print('=========== len = ', dfs.vallen[0])
#        print(tup)


#        break

    return

    # WLOG, x(t) and y(t) must be increasing functions
#    x0,y0 = 5.1,11
#    x1,y1 = 8.1,14
    x0,y0 = 1.1,1
    x1,y1 = 4.1,4

    df = pixel_crossings(x0,y0,x1,y1)
    print(df)




main()
