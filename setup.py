from distutils.core import setup
from Cython.Build import cythonize

setup(
    # need to use c++ to use libcpp.map
    ext_modules = cythonize('gtfs/csa.pyx', language='c++')
)
