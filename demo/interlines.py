import numpy as np
import pandas as pd
import geopandas
import shapely.geometry

epsilon = 1e-14

def norm2(x0,y0,x1,y1):
    xx = x1-x0
    yy = y1-y0
    return np.sqrt(xx*xx + yy*yy)

def _one_axis_crossings(x0, y0, x1, y1, dij, xycols):

    # x coordinates crossed by the line
    x_crossings_x = np.arange(np.ceil(x0), x1 + epsilon)

    # (x-x0) = my (y - y0)
    m = (y1-y0) / (x1-x0)    # slope
    x_crossings_y = m * (x_crossings_x - x0) + y0

    # t = distance along the line
    x_crossings_t = norm2(x0, y0, x_crossings_x, x_crossings_y)
#    xx = x_crossings_x - x0
#    yy = x_crossings_y - y0
#    x_crossings_t = np.sqrt((xx * xx) + (yy * yy))

    df = pd.DataFrame({'t': x_crossings_t, dij[0]: 1, dij[1]: 0, xycols[0]: x_crossings_x, xycols[1]: x_crossings_y})
#    df.loc[dij[0],0] = np.floor(x0).astype(int)
    print(df)
    return df


def axis_crossings(x0, y0, x1, y1):
    if x1 > x0:
        dfx = _one_axis_crossings(x0, y0, x1, y1, ['di', 'dj'], ['x', 'y'])
    if y1 > y0:
        dfy = _one_axis_crossings(y0, x0, y1, x1, ['dj', 'di'], ['y', 'x'])

    # Beginning and ending points
    dfbe = pd.DataFrame([
        (0, 0, 0, x0, y0),
        (norm2(x0,y0,x1,y1), 0, 0, x1, y1),
        ], columns=['t', 'di', 'dj', 'x', 'y'])

    df = pd.concat([dfx, dfy, dfbe]).sort_values(['t']).reset_index(drop=True)
    print('AA2')
    print(df)
    df = df.groupby('t', as_index=False).agg({'di': 'sum', 'dj': 'sum', 'x': 'first', 'y': 'first'})    # Drop / sum duplicates

    df.iloc[0, df.columns.get_loc('di')] = np.floor(x0).astype(int)
    df.iloc[0, df.columns.get_loc('dj')] = np.floor(y0).astype(int)


    df['i'] = df.di.cumsum()
    df['j'] = df.dj.cumsum()

    print(df)

def main():

    # WLOG, x(t) and y(t) must be increasing functions
    x0,y0 = 5.1,11
    x1,y1 = 8.1,14

    df = axis_crossings(x0,y0,x1,y1)
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
