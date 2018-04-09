import numpy
from distutils.core import setup
from Cython.Build import cythonize

setup(
    # need to use c++ to use libcpp.map
    ext_modules = cythonize([
        'gtfs/csa.pyx',
        'road/quadtree.pyx'
    ], language='c++'),
    include_dirs=[numpy.get_include()]
)
