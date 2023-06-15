import numpy as np
import os
import matplotlib.pyplot as plt
from uafgi.util import gdalutil,wrfutil
from akramms import config,params
import findiff
import scipy.ndimage
import scipy.signal



# DEPRECATED
def compute_lapse_v1(ee, vv, dy, dx):
    """Compute a gridded lapse rate based on local finite differences
    ee:
        Elevations
    vv:
        A gridded value
    dx,dy:
        Size of gridcell
    """

    # Compute Jacobian (gradiant) of elevations and value
    d_dy = findiff.FinDiff(0, dy)
    d_dx = findiff.FinDiff(1, dx)
    de_dy = d_dy(ee)
    de_dx = d_dx(ee)
    dv_dy = d_dy(vv)
    dv_dx = d_dx(vv)

    # Lapse rate is (change in value) / (change in elevation)
    # Compute it for the x and y axis, and average
    lapse_y = dv_dy / de_dy
    lapse_x = dv_dx / de_dx

    # TODO: More cleverness can be used to handle cases where there is
    # just a lapse_y or lapse_x.  If no lapse_y (based on mask), set
    # equal to lapse_x.  And vice versa.

    return lapse_y, lapse_x
# -------------------------------------------------------------
# eq 3
Ox = np.array([
    [-1, -2, 0, 1, 2],
    [-4, -8, 0, 8, 4],
    [-6, -12, 0, 12, 6],
    [-4, -8, 0, 8, 4],
    [-1, -2, 0, 1, 2],
    ], dtype='d')
Oy = np.transpose(Ox)

def grad(val, dy, dx):
    Ty = scipy.signal.convolve2d(val, Oy, boundary='symm', mode='same') * (1. / (960. * dy))
    Tx = scipy.signal.convolve2d(val, Ox, boundary='symm', mode='same') * (1. / (960. * dx))
    return Ty,Tx



def compute_lapse(H, T, dy, dx):
    """Compute a gridded lapse rate based on local finite differences
    ee:
        Elevations
    vv:
        A gridded value
    dx,dy:
        Size of gridcell
    """

    # A New Methodology for Estimating the Surface Temperature Lapse
    # Rate Based on Grid Data and Its Application in China

    # Compute gradient of elevations and values
    Hy,Hx = grad(H, dy, dx)
    Ty,Tx = grad(T, dy, dx)

    return np.divide(
        Tx*Hx + Ty*Hy,
        Hx*Hx + Hy*Hy)

# -------------------------------------------------------------

    


def main():
    sx3_dir = config.roots.syspath('{DATA}/lader/sx3')
    wrf_geo_nc = os.path.join(sx3_dir, 'geo_southeast.nc')
    wrf_sx3_nc = os.path.join(sx3_dir, 'ccsm_sx3_2010.nc')


    gridA = wrfutil.wrf_info(wrf_geo_nc)
    wrfdemA,wrfdemA_nd = wrfutil.read_raw(
        os.path.join(sx3_dir, 'geo_southeast.nc'), 'HGT_M')
    wrfdemA = wrfdemA[0,:,:]    # Eliminate zombie dimension
    sx3_fname = os.path.join(sx3_dir, 'ccsm_sx3_2010.nc')
    print('sx3_fname ', sx3_fname)
    sx3A,sx3A_nd = wrfutil.read_raw(sx3_fname, 'sx3')

    print('wrfdemA: ', wrfdemA.shape)
    print('sx3A: ', sx3A.shape)


    # Approximate proper handling of unused cells.  Reduce errors in gaussian_filter below.
    # See icebin C++ and prototype Python code for correct treatment.
    # https://github.com/citibeth/icebin/blob/d09ba3a0da04bab65adacd0c5e2f4cb50e116a0b/slib/icebin/smoother.cpp
    sx3_mean = np.mean(sx3A[sx3A != sx3A_nd])
    sx3A[sx3A == sx3A_nd] = sx3_mean


    # Just take a few...
#    wrfdemA = wrfdemA[-10:,:]
#    sx3A = sx3A[-10:,:]


#    lapse_y, lapse_x = compute_lapse(wrfdemA, sx3A, 1., 1.)
#    lapse = 0.5 * (lapse_y + lapse_x)
    print('dy dx = {} {}'.format(gridA.dy, gridA.dx))
    lapse = compute_lapse(wrfdemA, sx3A, gridA.dy, gridA.dx)
    mask_out = np.logical_or.reduce((sx3A == sx3A_nd, sx3A <= 0, wrfdemA<200., np.isnan(lapse)))
    mask_out2 = np.logical_or.reduce((sx3A == sx3A_nd, sx3A <= 0, wrfdemA<200., np.isnan(lapse), lapse<0.))

    print('mask_out ', np.sum(mask_out))
    print('TOTAL cells ', mask_out.shape[0] * mask_out.shape[1])
    lapse_mean = np.mean(lapse[np.logical_not(mask_out2)])
    print('lapse_mean ', lapse_mean)
    lapse[mask_out2] = lapse_mean
#    lapse = scipy.ndimage.gaussian_filter(lapse, sigma=10)
    lapse[mask_out] = 0.


#    gdalutil.write_raster('lapse_y.tif', gridA, lapse, -999)
#    gdalutil.write_raster('lapse_x.tif', gridA, lapse, -999)
    gdalutil.write_raster('lapse.tif', gridA, lapse, -999.)
    return


#    print(sx3A.shape)
#    return

    wrfdemA1 = wrfdemA.reshape(-1)
    sx3A1 = sx3A.reshape(-1)

#    print('shape0: ', wrfdemA.shape, sx3A.shape)
#    print('shape1: ', wrfdemA1.shape, sx3A1.shape)
#    return

    # Make 1D vectors of the data for regression
    mask_in = np.logical_and.reduce((sx3A != sx3A_nd, sx3A > 0, wrfdemA>200.))

    mask_in1 = mask_in.reshape(-1)
    print('mask_in size: ', mask_in1.shape)
    wrfdemAx = wrfdemA1[mask_in1]
    sx3Ax = sx3A1[mask_in1]

    print(wrfdemAx.shape)
    plt.scatter(wrfdemAx, sx3Ax)
    plt.show()

main()
