import h5py
import numpy
import numpy.testing
import pytest

from .common import ut, TestCase


class TestWriteDirectChunk(TestCase):
    def test_write_direct_chunk(self):

        filename = self.mktemp().encode()
        with h5py.File(filename, "w") as filehandle:

            dataset = filehandle.create_dataset("data", (100, 100, 100),
                                                maxshape=(None, 100, 100),
                                                chunks=(1, 100, 100),
                                                dtype='float32')

            # writing
            array = numpy.zeros((10, 100, 100))
            for index in range(10):
                a = numpy.random.rand(100, 100).astype('float32')
                dataset.id.write_direct_chunk((index, 0, 0), a.tobytes(), filter_mask=1)
                array[index] = a


        # checking
        with h5py.File(filename, "r") as filehandle:
            for i in range(10):
                read_data = filehandle["data"][i]
                numpy.testing.assert_array_equal(array[i], read_data)


@ut.skipIf('gzip' not in h5py.filters.encode, "DEFLATE is not installed")
class TestReadDirectChunk(TestCase):
    def test_read_compressed_offsets(self):

        filename = self.mktemp().encode()
        with h5py.File(filename, "w") as filehandle:

            frame = numpy.arange(16).reshape(4, 4)
            frame_dataset = filehandle.create_dataset("frame",
                                                      data=frame,
                                                      compression="gzip",
                                                      compression_opts=9)
            dataset = filehandle.create_dataset("compressed_chunked",
                                                data=[frame, frame, frame],
                                                compression="gzip",
                                                compression_opts=9,
                                                chunks=(1, ) + frame.shape)
            filter_mask, compressed_frame = frame_dataset.id.read_direct_chunk((0, 0))
            # No filter must be disabled
            self.assertEqual(filter_mask, 0)

            for i in range(dataset.shape[0]):
                filter_mask, data = dataset.id.read_direct_chunk((i, 0, 0))
                self.assertEqual(compressed_frame, data)
                # No filter must be disabled
                self.assertEqual(filter_mask, 0)

    def test_read_uncompressed_offsets(self):

        filename = self.mktemp().encode()
        frame = numpy.arange(16).reshape(4, 4)
        with h5py.File(filename, "w") as filehandle:
            dataset = filehandle.create_dataset("frame",
                                                maxshape=(1,) + frame.shape,
                                                shape=(1,) + frame.shape,
                                                compression="gzip",
                                                compression_opts=9)
            # Write uncompressed data
            DISABLE_ALL_FILTERS = 0xFFFFFFFF
            dataset.id.write_direct_chunk((0, 0, 0), frame.tobytes(), filter_mask=DISABLE_ALL_FILTERS)

        # FIXME: Here we have to close the file and load it back else
        #     a runtime error occurs:
        #     RuntimeError: Can't get storage size of chunk (chunk storage is not allocated)
        with h5py.File(filename, "r") as filehandle:
            dataset = filehandle["frame"]
            filter_mask, compressed_frame = dataset.id.read_direct_chunk((0, 0, 0))

        # At least 1 filter is supposed to be disabled
        self.assertNotEqual(filter_mask, 0)
        self.assertEqual(compressed_frame, frame.tobytes())

    def test_read_write_chunk(self):

        filename = self.mktemp().encode()
        with h5py.File(filename, "w") as filehandle:

            # create a reference
            frame = numpy.arange(16).reshape(4, 4)
            frame_dataset = filehandle.create_dataset("source",
                                                      data=frame,
                                                      compression="gzip",
                                                      compression_opts=9)
            # configure an empty dataset
            filter_mask, compressed_frame = frame_dataset.id.read_direct_chunk((0, 0))
            dataset = filehandle.create_dataset("created",
                                                shape=frame_dataset.shape,
                                                maxshape=frame_dataset.shape,
                                                chunks=frame_dataset.chunks,
                                                dtype=frame_dataset.dtype,
                                                compression="gzip",
                                                compression_opts=9)

            # copy the data
            dataset.id.write_direct_chunk((0, 0), compressed_frame, filter_mask=filter_mask)

        # checking
        with h5py.File(filename, "r") as filehandle:
            dataset = filehandle["created"][...]
            numpy.testing.assert_array_equal(dataset, frame)


class TestReadDirectChunkToOut:

    def test_uncompressed_data(self, writable_file):
        ref_data = numpy.arange(16).reshape(4, 4)
        dataset = writable_file.create_dataset(
            "uncompressed", data=ref_data, chunks=ref_data.shape)

        out = bytearray(ref_data.nbytes)
        filter_mask, chunk = dataset.id.read_direct_chunk((0, 0), out=out)

        assert numpy.array_equal(
            numpy.frombuffer(out, dtype=ref_data.dtype).reshape(ref_data.shape),
            ref_data,
        )
        assert filter_mask == 0
        assert len(chunk) == ref_data.nbytes

    @pytest.mark.skipif(
        h5py.version.hdf5_version_tuple < (1, 10, 5),
        reason="chunk info requires HDF5 >= 1.10.5",
    )
    @pytest.mark.skipif(
        'gzip' not in h5py.filters.encode,
        reason="DEFLATE is not installed",
    )
    def test_compressed_data(self, writable_file):
        ref_data = numpy.arange(16).reshape(4, 4)
        dataset = writable_file.create_dataset(
            "gzip",
            data=ref_data,
            chunks=ref_data.shape,
            compression="gzip",
            compression_opts=9,
        )
        chunk_info = dataset.id.get_chunk_info(0)

        out = bytearray(chunk_info.size)
        filter_mask, chunk = dataset.id.read_direct_chunk(
            chunk_info.chunk_offset,
            out=out,
        )
        assert filter_mask == chunk_info.filter_mask
        assert len(chunk) == chunk_info.size
        assert out == dataset.id.read_direct_chunk(chunk_info.chunk_offset)[1]

    def test_fail_buffer_too_small(self, writable_file):
        ref_data = numpy.arange(16).reshape(4, 4)
        dataset = writable_file.create_dataset(
            "uncompressed", data=ref_data, chunks=ref_data.shape)

        out = bytearray(ref_data.nbytes // 2)
        with pytest.raises(ValueError):
            dataset.id.read_direct_chunk((0, 0), out=out)

    def test_fail_buffer_readonly(self, writable_file):
        ref_data = numpy.arange(16).reshape(4, 4)
        dataset = writable_file.create_dataset(
            "uncompressed", data=ref_data, chunks=ref_data.shape)

        out = bytes(ref_data.nbytes)
        with pytest.raises(BufferError):
            dataset.id.read_direct_chunk((0, 0), out=out)

    def test_fail_buffer_not_contiguous(self, writable_file):
        ref_data = numpy.arange(16).reshape(4, 4)
        dataset = writable_file.create_dataset(
            "uncompressed", data=ref_data, chunks=ref_data.shape)

        array = numpy.empty(ref_data.shape + (2,), dtype=ref_data.dtype)
        out = array[:, :, ::2]  # Array is not contiguous
        with pytest.raises(ValueError):
            dataset.id.read_direct_chunk((0, 0), out=out)


@ut.skipIf(h5py.version.hdf5_version_tuple < (1, 14, 0),
           "read_multi requires HDF5 >= 1.14.0")
class TestReadMulti(TestCase):
    def test_read_multi_one_dataset(self):
        filename = self.mktemp().encode()
        with h5py.File(filename, "w") as filehandle:
            shape = (10, 10, 10)
            dt = numpy.int32

            # Write data
            data_in = numpy.reshape(numpy.arange(numpy.prod(shape)), shape)
            dataset = filehandle.create_dataset("data", shape,
                                                dtype=dt, data=data_in)

            self.assertTrue(numpy.array_equal(data_in, dataset[...]))

            mspace_id = h5py.h5s.create_simple(shape)
            fspace_id = h5py.h5s.create_simple(shape)
            type_id = dataset.id.get_type()
            data_out = numpy.zeros(shape=shape, dtype=dt)

            # Read back data and verify
            h5py.h5d.read_multi(1, [dataset.id.id], [mspace_id.id],
                                [fspace_id.id], [type_id.id], [data_out],
                                None)

            self.assertTrue(numpy.array_equal(data_in, data_out))

    def test_read_multi_many_datasets(self):
        filename = self.mktemp().encode()
        with h5py.File(filename, "w") as filehandle:
            shape = (2, 2, 2)
            dt = numpy.int32
            count = 3
            data = numpy.reshape(numpy.arange(numpy.prod(shape)), shape)
            data_in = []
            data_out = []

            datasets = []
            mspaces = []
            fspaces = []
            types = []

            for i in range(count):
                # Write data
                data_in.append(data + i)
                dataset = filehandle.create_dataset("data" + str(i), shape,
                                                    dtype=dt, data=data_in[i])

                self.assertTrue(numpy.array_equal(data_in[i], dataset[...]))

                datasets.append(dataset.id)
                mspaces.append(h5py.h5s.create_simple(shape))
                fspaces.append(h5py.h5s.create_simple(shape))
                types.append(dataset.id.get_type())

                data_out.append(numpy.zeros(shape=shape, dtype=dt))

            dataset_ids = [d.id for d in datasets]
            mspace_ids = [m.id for m in mspaces]
            fspace_ids = [f.id for f in fspaces]
            type_ids = [t.id for t in types]

            # Read back data and verify
            h5py.h5d.read_multi(count, dataset_ids, mspace_ids,
                                fspace_ids, type_ids, data_out,
                                None)

            for i in range(count):
                self.assertTrue(numpy.array_equal(data_in[i], data_out[i]))
