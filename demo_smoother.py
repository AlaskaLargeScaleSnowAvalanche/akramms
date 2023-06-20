import smoother
import importlib
import matplotlib.pyplot as plt
import numpy as np
import PIL

# Sample came from https://web.stanford.edu/class/ee398a/samples.htm
with PIL.Image.open('airfield512x512.tif') as img:
    img = np.array(img).astype('d')
print('Image shape ', img.shape)
print(img)

elev = np.zeros(img.shape, dtype='d')
print(elev)

sigma = 2.
img2 = smoother.smooth(img.shape[0], img.shape[1], 1.,1., elev, [sigma,sigma,sigma], img)
img2_tif = PIL.Image.fromarray(np.uint8(img2))

img2_tif.show()
print(img2)
