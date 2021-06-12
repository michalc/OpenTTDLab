import io
import struct

from .exceptions import ValidationException


class BinaryReader:
    """
    Read binary data.
    """

    def read(self, amount):
        raise NotImplementedError

    def str(self):
        """
        Read zero-terminated string.
        """
        result = bytearray()
        while True:
            b = self.uint8()
            if b == b"\0":
                break
            else:
                result.extend(b)
        return result

    def skip(self, amount):
        self.read(amount)

    def uint_ext(self):
        """
        Read NewGRF-style extended byte.
        """
        b = self.uint8()
        if b == 0xFF:
            b = self.uint16()
        return b

    def gamma(self):
        """
        Read OTTD-savegame-style gamma value.
        """
        b = self.uint8()
        if (b & 0x80) == 0:
            return (b & 0x7F, 1)
        elif (b & 0xC0) == 0x80:
            return ((b & 0x3F) << 8 | self.uint8(), 2)
        elif (b & 0xE0) == 0xC0:
            return ((b & 0x1F) << 16 | self.uint16(be=True), 3)
        elif (b & 0xF0) == 0xE0:
            return ((b & 0x0F) << 24 | self.uint24(be=True), 4)
        elif (b & 0xF8) == 0xF0:
            return ((b & 0x07) << 32 | self.uint32(be=True), 5)
        else:
            raise ValidationException("Invalid gamma encoding.")

    def gamma_str(self):
        """
        Read OTTD-savegame-style gamma string (SLE_STR).
        """
        size = self.gamma()[0]
        return self.read(size)

    def int8(self):
        try:
            return struct.unpack(">b", self.read(1))[0]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint8(self):
        try:
            return struct.unpack(">B", self.read(1))[0]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def int16(self):
        try:
            return struct.unpack(">h", self.read(2))[0]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint16(self):
        try:
            return struct.unpack(">H", self.read(2))[0]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint24(self):
        return (self.uint16() << 8) | self.uint8()

    def int32(self):
        try:
            return struct.unpack(">l", self.read(4))[0]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint32(self):
        try:
            return struct.unpack(">L", self.read(4))[0]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def int64(self):
        try:
            return struct.unpack(">q", self.read(8))[0]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint64(self):
        try:
            return struct.unpack(">Q", self.read(8))[0]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")


class BinaryReaderFile(BinaryReader):
    """
    Read binary data from file.
    """

    def __init__(self, file):
        self._file = file

    def read(self, amount):
        return self._file.read(amount)


class BinaryReaderFileBlockMode(BinaryReader):
    """
    Read binary data from file in blocks of at least 1024 bytes.
    """

    def __init__(self, file):
        self._file = file
        self._buffer = b""

    def read(self, amount):
        # Read in chunks, to improve performance.
        if len(self._buffer) < amount:
            self._buffer += self._file.read(1024 + amount)

        if len(self._buffer) < amount:
            raise ValidationException("Unexpected end-of-file.")

        data = self._buffer[:amount]
        self._buffer = self._buffer[amount:]
        return data
