"""JXE2JAR common class."""
# pylint: disable=W0212:
import errno
import os
import os.path
from io import IOBase

import bitstring


class StreamCursor:
    """StreamCursor object."""

    def __init__(self, stream, pos):
        self._stream_ = stream
        self._new_pos_ = pos
        self._old_pos_ = None

    def __enter__(self):
        self._old_pos_ = self._stream_.get()
        if self._new_pos_ < 0 or self._new_pos_ > self._stream_.len:
            raise EOFError
        self._stream_.set(self._new_pos_)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stream_.set(self._old_pos_)


class ReaderStream:
    """ReaderStream class."""

    def __init__(self, obj):
        if isinstance(obj, IOBase):
            self._file_object_ = obj
            self._bit_stream_ = bitstring.BitStream(self._file_object_)
        elif isinstance(obj, bitstring.BitArray):
            self._bit_stream_ = bitstring.BitStream()
            self._bit_stream_._append(obj)
        else:
            raise Exception("Invalid ReaderStream instance type")

    def get(self):
        return self._bit_stream_.bytepos

    def set(self, pos):
        self._bit_stream_.bytepos = pos

    def read_bytes(self, length):
        return self._bit_stream_.read(f"bytes:{length}")

    def read_u8(self):
        return self._bit_stream_.read("uintle:8")

    def read_u16(self):
        return self._bit_stream_.read("uintle:16")

    def read_u32(self):
        return self._bit_stream_.read("uintle:32")

    def read_i8(self):
        return self._bit_stream_.read("intle:8")

    def read_i16(self):
        return self._bit_stream_.read("intle:16")

    def read_i32(self):
        return self._bit_stream_.read("intle:32")

    def read_string(self):
        length = self.read_u16()
        return self.read_bytes(length).decode("utf-8")

    def read_relative(self):
        base = self.get()
        ptr = self.read_i32()
        return base + ptr

    def read_string_ref(self):
        ptr = self.read_relative()
        pos = self.get()
        self.set(ptr)
        value = self.read_string()
        self.set(pos)
        return value

    @property
    def bytes(self):
        return self._bit_stream_.bytes

    @property
    def len(self):
        return self._bit_stream_.length / 8

    @property
    def file_object(self):
        return self._file_object_

    @staticmethod
    def bytes_to_stream(value):
        return ReaderStream(bitstring.BitArray(bytes=value))


class WriterStream:
    """WriteStream class using bitstring."""

    def __init__(self, file_object):
        self._file_object_ = file_object
        self._bit_stream_ = bitstring.BitStream()

    def write(self):
        self._bit_stream_.tofile(self._file_object_)

    def write_raw_bytes(self, data):
        return self._bit_stream_._append(bitstring.BitArray(bytes=data))

    def write_u8(self, value):
        return self._bit_stream_._append(bitstring.pack("uintbe:8", value))

    def write_u16(self, value):
        return self._bit_stream_._append(bitstring.pack("uintbe:16", value))

    def write_u32(self, value):
        return self._bit_stream_._append(bitstring.pack("uintbe:32", value))

    def write_i8(self, value):
        return self._bit_stream_._append(bitstring.pack("intbe:8", value))

    def write_i16(self, value):
        return self._bit_stream_._append(bitstring.pack("intbe:16", value))

    def write_i32(self, value):
        return self._bit_stream_._append(bitstring.pack("intbe:32", value))


def create_file_path(filepath):
    if not os.path.exists(os.path.dirname(filepath)):
        try:
            os.makedirs(os.path.dirname(filepath))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
