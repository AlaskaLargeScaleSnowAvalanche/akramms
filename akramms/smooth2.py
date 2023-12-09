import math,pathlib
import numpy as np
import scipy.signal

# From: https://numbersmithy.com/2d-convolution-with-missing-data/
def convolve_fft_missing(slab,kernel,max_missing=1.0):
    '''2D convolution using fft, allowing for missing data

    slab:
        N-dimensional array of values.
        Unused values set to np.nan
    kernel:
        N-dimensional array, convolution kernel.
    max_missing:
        real, max tolerable percentage of missings within any
                   convolution window.
                   E.g. if <max_missing> is 0.5, when over 50% of values
                   within a given element are missing, the center will be
                   set as missing (<res>=0, <resmask>=1). If only 40% is
                   missing, center value will be computed using the remaining
                   60% data in the element.
                   NOTE that out-of-bound grids are counted as missings, this
                   is different from convolve2D(), where the number of valid
                   values at edges drops as the kernel approaches the edge.

    Return <result>: 2d convolution.
    '''
#    from scipy import signal

#    assert np.ndim(slab)==2, "<slab> needs to be 2D."
#    assert np.ndim(kernel)==2, "<kernel> needs to be 2D."
#    assert kernel.shape[0]<=slab.shape[0], "<kernel> size needs to <= <slab> size."
#    assert kernel.shape[1]<=slab.shape[1], "<kernel> size needs to <= <slab> size."

    #--------------Get mask for missings--------------
    slabcount=1-np.isnan(slab)

    # this is to set np.nan to a float, this won't affect the result as
    # masked values are not used in convolution. Otherwise, nans will
    # affect convolution in the same way as scipy.signal.convolve()
    # and the result will contain nans.
    slab=np.where(slabcount==1,slab,0)
    kernelcount=np.where(kernel==0,0,1)

    result = scipy.signal.fftconvolve(slab,kernel,mode='same')
    result_mask = scipy.signal.oaconvolve(slabcount,kernelcount,mode='same')

    # Blank out cells with too many missing contributors
    if max_missing < 1.0:
        valid_threshold=(1.-max_missing)*np.sum(kernelcount)
        result=np.where(result_mask<valid_threshold,result,np.nan)

    #NOTE: the number of valid point counting is different from convolve2D(),
    #where the total number of valid points drops as the kernel moves to the
    #edges. This can be replicated here by:
    # totalcount = scipy.signal.fftconvolve(np.ones(slabcount.shape),kernelcount,
    # mode='same')
    # valid_threshold=(1.-max_missing)*totalcount
    #But will involve doing 1 more convolution.
    #Another way is to convolve a small matrix (big enough to get the drop
    #at the edges, and set the same numbers to the totalcount.

    return result

# -----------------------------------------------------------------
def gaussian(sigma, dx, cutoff=2.0):
    """Generates a Gaussian kernel for a particular (vector) sigma.

    sigma: [sigma0, sigma1, ...]
        Sigma in each dimension
    dx: [dx, dy, ...]
        Gridcell spacing in each dimension
    cutoff: float
        How many sigmas out to go
    """

    sigma = np.array(sigma)
    dx = np.array(dx)

    # Determine grid size
    nx_half = np.round(cutoff*sigma / dx).astype(int)
    nx =  2*nx_half + 1
    print('nx ', nx, type(nx))
    kernel = np.zeros(nx)
    print('kernel shape ', kernel.shape)

    # Iterate through the array and evaluate the Gaussian function.
    # No need to normalize analytically, since we are cutting off the tails.
    # Normalize after-the-fact, numerically.
    # https://en.wikipedia.org/wiki/Gaussian_function
    #by_2s2 = 1. / (2. * np.sum(sigma*sigma))
    by_sigma2 = 1./np.sum(sigma*sigma)    # 1/sigma^2
    for ii in np.ndindex(kernel.shape):
        # Convert from gridcell to x,y,z in Cartesian space
        xx = (ii - nx_half) * dx
#        print(ii, xx)
        xs = xx / sigma
        kernel[ii] = np.exp(-np.sum(xs*xs))

    # Normalize
    kernel /= np.sum(kernel)

    return kernel

# -----------------------------------------------------------------
def zsmooth(imgI, elevI, sigma3d, dxI, cutoff=2.0):

    # Determine spacing of elevation classes (dz)
    sigmaz = sigma3d[-1]
    dz = sigmaz / 2.    # /2. is an arbitrary constant here

    # Determine number of elevation classes (nk)
    k0 = math.floor(np.min(elevI) / dz)
    k1 = math.ceil(np.max(elevI) / dz) + 1
    nk = k1 - k0

    # Get k coordinate of each gridcell in 2D
    kI = k0 + np.floor(elevI / dz)

    # Project 2D into 3D
    # K grid = I grid + 3d dimension of size nk
    shapeK = tuple(list(imgI.shape) + [nk])
    imgK = np.zeros(shapeK) + np.nan
    ndim0 = len(imgI.shape)
    iiss = [    # [ [i,...], [j,...] ] indices of all gridcells
        [q[d] for q in np.ndindex(imgI.shape)]
        for d in range(ndim)]
    iissK = iiss + [kI[*iiss]]    # # [ [i,...], [j,...], [k,...] ] indices of all gridcells
    imgK[*iissK] = imgI[*iiss]

    # Get the Gaussian kernel
    dxK = tuple(list(dxI) + [dz])
    kernel = gaussian(sigma3d, dxK)

    # Convolve!
    imgKc = convolve_fft_missing(imgK, kernel)    # imgKc = imgK-convolved

    # Remove extra dimension
    imgIc[*iiss] = imgKc[*iissK]
    return imgIc
# -----------------------------------------------------------------
# -----------------------------------------------------------------

dir = pathlib.Path('/Users/eafischer2/tmp/maps')
imgI_file = dir / 'ak_ccsm_1981_1990_lapse_113_045.tif'
elevI_file = dir / 'ak_dem_113_045_filled.tif'

def main():
    import PIL

    # Read sample images
    with PIL.Image.open(imgI_file) as fin:
        imgI = np.array(fin)    # Should be dtype='d' already
    with PIL.Image.open(elevI_file) as fin:
        elevI = np.array(fin)
    size = 400
    imgI = imgI[:size,:size]
    elevI = elevI[:size,:size]


    # Smooth
    imgIc = zsmooth(imgI, elevI, (100,100,50), (10.,10.))

    # Store
    imgIc_tif = PIL.Image.fromarray(imgIc)
    imgIc_tif.show()

main()

