"""Common class."""
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
            raise TypeError("Invalid ReaderStream instance type")

    def get(self) -> int:
        """Returns current file stream cursor position."""
        return self._bit_stream_.bytepos

    def set(self, pos: int) -> None:
        """Sets current file stream cursor position."""
        self._bit_stream_.bytepos = pos

    def read_bytes(self, length: int):
        """Reads n bytes from file stream."""
        return self._bit_stream_.read(f"bytes:{length}")

    def read_u8(self) -> int:
        """Reads uint8 le from file stream."""
        return self._bit_stream_.read("uintle:8")

    def read_u16(self) -> int:
        """Reads uint16 le from file stream."""
        return self._bit_stream_.read("uintle:16")

    def read_u32(self) -> int:
        """Reads uint32 le from file stream."""
        return self._bit_stream_.read("uintle:32")

    def read_i8(self) -> int:
        """Reads int8 le from file stream."""
        return self._bit_stream_.read("intle:8")

    def read_i16(self) -> int:
        """Reads int16 le from file stream."""
        return self._bit_stream_.read("intle:16")

    def read_i32(self) -> int:
        """Reads int32 le from file stream."""
        return self._bit_stream_.read("intle:32")

    def read_string(self) -> str:
        """Reads string (u16) from file stream as utf-8."""
        length = self.read_u16()
        return self.read_bytes(length).decode("utf-8")

    def read_relative(self):
        """Reads int32 from file stream using relative position."""
        base = self.get()
        ptr = self.read_i32()
        return base + ptr

    def read_string_ref(self) -> str:
        """Reads string ref from file stream."""
        ptr = self.read_relative()
        pos = self.get()
        self.set(ptr)
        value = self.read_string()
        self.set(pos)
        return value

    @property
    def bytes(self) -> bytes:
        """Returns bytes from BitArray stream."""
        return self._bit_stream_.bytes

    @property
    def len(self) -> int:
        """Returns BitArray length"""
        return self._bit_stream_.length / 8

    @property
    def file_object(self) -> IOBase:
        """Retursn file object."""
        return self._file_object_

    @staticmethod
    def bytes_to_stream(value: bytes):
        """Returns ReaderStream from bytes."""
        return ReaderStream(bitstring.BitArray(bytes=value))


class WriterStream:
    """WriteStream class using bitstring."""

    def __init__(self, file_object):
        self._file_object_ = file_object
        self._bit_stream_ = bitstring.BitStream()

    def write(self) -> None:
        """Writes BitStream to file object."""
        self._bit_stream_.tofile(self._file_object_)

    def write_raw_bytes(self, data: bytes) -> None:
        """Writes raw bytes to BitArray stream."""
        self._bit_stream_.append(bitstring.BitArray(bytes=data))

    def write_u8(self, value: int) -> None:
        """Writes uint8 be to BitArray stream."""
        self._bit_stream_.append(bitstring.pack("uintbe:8", value))

    def write_u16(self, value: int) -> None:
        """Writes uint16 be to BitArray stream."""
        self._bit_stream_.append(bitstring.pack("uintbe:16", value))

    def write_u32(self, value: int) -> None:
        """Writes uint32 be to BitArray stream."""
        self._bit_stream_.append(bitstring.pack("uintbe:32", value))

    def write_i8(self, value: int) -> None:
        """Writes int8 be to BitArray stream."""
        self._bit_stream_.append(bitstring.pack("intbe:8", value))

    def write_i16(self, value: int) -> None:
        """Writes int16 be to BitArray stream."""
        self._bit_stream_.append(bitstring.pack("intbe:16", value))

    def write_i32(self, value: int) -> None:
        """Writes int32 be to BitArray stream."""
        self._bit_stream_.append(bitstring.pack("intbe:32", value))


def create_file_path(filepath: str) -> None:
    """Creates file path directories."""
    if not os.path.exists(os.path.dirname(filepath)):
        try:
            os.makedirs(os.path.dirname(filepath))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
