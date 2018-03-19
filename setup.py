from distutils.core import setup
from Cython.Build import cythonize

setup(
    # need to use c++ to use libcpp.map
    ext_modules = cythonize('csac.pyx', language='c++')
)
