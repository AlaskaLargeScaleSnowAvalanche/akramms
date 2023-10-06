import numpy

'''
    setup.py file for spammodule.c

    Calling
    $python setup.py build_ext --inplace
    will build the extension library in the current file.

    Calling
    $python setup.py build
    will build a file that looks like ./build/lib*, where
    lib* is a file that begins with lib. The library will
    be in this file and end with a C library extension,
    such as .so

    Calling
    $python setup.py install
    will install the module in your site-packages file.

    See the distutils section of
    'Extending and Embedding the Python Interpreter'
    at docs.python.org for more information.
'''


from distutils.core import setup, Extension

d8graph_mod = Extension('d8graph',
    sources=['akramms/d8graph.cpp', 'akramms/mbr.cpp'],
    include_dirs=[numpy.get_include(), '.'],
    extra_compile_args=['-std=c++17']
)

_smoother_mod = Extension('smoother',
    sources=['akramms/raster.cpp', 'akramms/smoother.cpp'],
    include_dirs=[numpy.get_include(), '.'],
    extra_compile_args=['-std=c++17']
)

_mosaic_mod = Extension('smoother',
    sources=['akramms/_mosaic.cpp'],
    include_dirs=[numpy.get_include(), '.'],
    extra_compile_args=['-std=c++17']
)

setup(name = 'akramms',
        description='Alaska Large Scale Avalanche Simulations',
        ext_modules = [d8graph_mod, _smoother_mod, _mosaic_mod])
