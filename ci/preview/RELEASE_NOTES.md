**Unofficial preview build. Not released or supported by the h5py project.**

h5py built from the `mt-chunk-io` branch of
[mattjala/h5py](https://github.com/mattjala/h5py/tree/mt-chunk-io), which adds
`h5py.set_internal_threads(n)` to use HDF5's internal thread pool for reading
chunked datasets. The h5py change has not been accepted upstream yet and its
API may change.

Each wheel bundles its own copy of HDF5, built from `develop` at
[HDFGroup/hdf5@ab5df552](https://github.com/HDFGroup/hdf5/commit/ab5df5526c96a03bf1d89cea59603b77a239eac0).
That snapshot reports itself as 2.3.0, but HDF5 2.3.0 has not been released.
Any HDF5 installed on the system is not used.

## Install

Download the wheel below that matches your Python version and platform
(e.g. `cp312` and `manylinux_2_28_x86_64` for Python 3.12 on x86-64 Linux)
and install it into a dedicated virtual environment, since it replaces any
h5py there:

```
pip install ./h5py-3.17.0.dev0-<tags of the file you downloaded>.whl
```

## Use

```python
import h5py
print(h5py.get_config().internal_threads)  # True
h5py.set_internal_threads(4)   # 0 turns it off again; off by default
```

- Only reads of chunked datasets use the pool, for chunks not already in the
  chunk cache.
- Not used for files opened with an MPI driver.
- A process created with `os.fork()` starts with the pool off.
- Errors raised in the worker threads may be printed to stderr instead of
  becoming Python exceptions.

## Building against your own HDF5

The source archive (`h5py-*.tar.gz`) builds against an HDF5 that has the
internal thread pool (currently only HDF5 `develop`), not built with
`HDF5_ENABLE_THREADSAFE`:

```
HDF5_DIR=/path/to/hdf5 pip install h5py-3.17.0.dev0.tar.gz
```
