import numpy
from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize

# OpenMP: http://docs.cython.org/en/latest/src/userguide/parallelism.html#compiling
ext_modules = [
    Extension(
        'gtfs.csa',
        ['gtfs/csa.pyx'],
        extra_compile_args=['-fopenmp'],
        extra_link_args=['-fopenmp'],
    ),
    Extension(
        'road.quadtree',
        ['road/quadtree.pyx']
    )
]

setup(
    # need to use c++ to use libcpp.map
    ext_modules = cythonize(ext_modules, language='c++'),
    include_dirs=[numpy.get_include()]
)
