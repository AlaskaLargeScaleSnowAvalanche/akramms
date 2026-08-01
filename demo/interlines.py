import numpy as np
import pandas as pd
import geopandas
import shapely.geometry

epsilon = 1e-14

def norm2(x0,y0,x1,y1):
    xx = x1-x0
    yy = y1-y0
    return np.sqrt(xx*xx + yy*yy)

def axis_crossings(x0, y0, x1, y1, xycols):

    # x coordinates crossed by the line
    x_crossings_x = np.arange(np.ceil(x0), x1 + epsilon)

    # (x-x0) = my (y - y0)
    m = (y1-y0) / (x1-x0)    # slope
    x_crossings_y = m * (x_crossings_x - x0) + y0

    # t = distance along the line
    x_crossings_t = norm2(x0, y0, x_crossings_x, x_crossings_y)

    df = pd.DataFrame({'t': x_crossings_t, xycols[0]: x_crossings_x, xycols[1]: x_crossings_y})
#    print(df)
    return df


def pixel_crossings(x0, y0, x1, y1):
    if x1 > x0:
        dfx = axis_crossings(x0, y0, x1, y1, ['x', 'y'])
    if y1 > y0:
        dfy = axis_crossings(y0, x0, y1, x1, ['y', 'x'])

    # Beginning and ending points
    dfbe = pd.DataFrame([
        (0, x0, y0),
        (norm2(x0,y0,x1,y1), x1, y1),
        ], columns=['t', 'x', 'y'])

    df = pd.concat([dfx, dfy, dfbe]).sort_values(['t']).reset_index(drop=True)
    print(df)
    df = df.groupby('t', as_index=False).agg({'x': 'first', 'y': 'first'})    # Drop / sum duplicates

#    df['i'] = df.x.map(int)
#    df['j'] = df.y.map(int)
    df['len'] = -df.t.diff(periods=-1)
    df = df[:-1]    # Drop last row, it is just endpoint of last segment
    print(df)

# ------------------------------------------------------------------------------
def iterate_ls(ls):
    """
    ls:
        LineString or MultiLineString
    yields:
        x0,y0,x1,y1
    """
    if isinstance(shapely.geometry.LineString):
        for p0,p1 in zip(line.coords[:-1], line.coords[1:]):
            yield p0[0], p0[1], p1[0], p1[1]
    elif isinstance(shapely.geometry.MultiLineStinrg):
        for part in multi_line.geoms:
            for p0, p1 in zip(part.coords[:-1], part.coords[1:]):
                yield p0[0], p0[1], p1[0], p1[1]
    else:
        raise TypeError(f'I do not know how to iterate over {ls}')

def _make_positive(x0, x1):
    if x1 > x0:
        return x0, x1, False
    else:
        return x1, x0, True

def transform_xyxy(x0,y0,x1,y1):
    """Makes xyxy have positive slope and going to the right.  Shares
    which dimensions had to be flipped to do so."""

    x0, x1, flipx = _make_positive(x0, x1)
    y0, y1, flipy = _make_positive(y0, y1)
    return (x0,y0,x1,y1), (flipx, flipy)


def integrate_linestrings(lss, val_grid, val_data, val_raster):
    """
    lss: [Shapely LineString, ...]
    tile_grid:
        The grid defining the current tile (no margin)
    """
    dfs = list()
    bbox = val_grid.bounding_box()

    lss_clipped = [shapely.intersection(ls, bbox) for ls in lss]
    for lsix,ls in enumerate(lss_clipped):
        for xyxy in iterate_ls(ls):
            # Flip line segment to slope-positive
            xyxy1,flips = transform_xyxy(*xyxy)
            df = pixel_crossings(xyxy1)

            # Account for the flip(s) in the answer
            if flips[0]:
                df['x'] = df.x.map(lambda x: val_grid.nx - x)
            if flips[1]:
                df['y'] = df.y.map(lambda y: val_grid.ny - y)

            df['lsix'] = lsix    # Line segment index
            dfs.append(df)

    df = pd.concat(dfs)

    # Select out raster values and multiply by len for integration
    ii = df.x.map(int)
    jj = df.y.map(int)
    vals = val_data[ii, jj]
    df['vallen'] = vals * df.len

    # Sum by linestring
    dfs = df[['lsix', 'vallen']].groupby('lsix').sum()
    print(dfs)
    return dfs


def main():

    # WLOG, x(t) and y(t) must be increasing functions
#    x0,y0 = 5.1,11
#    x1,y1 = 8.1,14
    x0,y0 = 1.1,1
    x1,y1 = 4.1,4

    df = pixel_crossings(x0,y0,x1,y1)
    print(df)



def mainx():

    nx = 10
    ny = 10

    # TODO: Clip to overall box before beginning, then scale to pixel size = 1
    # (This only works for dx = dy, which is OK)
    # TODO: Account for horizontal or vertical lines

    # WLOG, x(t) and y(t) must be increasing functions
    x0,y0 = 0.2,0
    x1,y1 = 3,3


    # x coordinates crossed by the line
    x_crossings_x = np.array(np.arange(np.ceil(x0), x1 + epsilon))

    # (x-x0) = my (y - y0)
    m = (y1-y0) / (x1-x0)    # slope
    x_crossings_y = m * (x_crossings_x - x0) + y0

    # t = distance along the line
    xx = x_crossings_x - x0
    yy = x_crossings_y - x0
    x_crossings_t = np.sqrt((xx * xx) + (yy * yy))



    print(x_crossings_t)




    print(list(zip(x_crossings_x, x_crossings_y)))
    return






    y_crossings_y = np.array(np.arange(np.ceil(y0), y1 + epsilon))


    print(x_crossings)
    print(y_crossings)

    

    # y = my x + bx
    m = (y1-y0) / (x1-x0)



main()
