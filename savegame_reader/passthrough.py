import struct

from .enums import FieldType
from .exceptions import ValidationException


class PassthroughReader:
    def read_gamma(self, data):
        try:
            b = struct.unpack_from(">B", data, 0)[0]
            if (b & 0x80) == 0:
                return b & 0x7F, data[1:]
            if (b & 0xC0) == 0x80:
                return (b & 0x3F) << 8 | struct.unpack_from(">B", data, 1)[0], data[2:]
            if (b & 0xE0) == 0xC0:
                return (b & 0x1F) << 16 | struct.unpack_from(">H", data, 1)[0], data[3:]
            if (b & 0xF0) == 0xE0:
                length = struct.unpack_from(">H", data, 1)[0] << 8
                length |= struct.unpack_from(">B", data, 3)[0]
                return (b & 0x0F) << 24 | self.uint24(), data[4:]
            if (b & 0xF8) == 0xF0:
                return (b & 0x07) << 32 | struct.unpack_from(">I", data, 1)[0], data[5:]

            raise ValidationException("Invalid gamma encoding.")
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def read_string(self, data):
        length, data = self.read_gamma(data)
        return data[0:length].tobytes().decode(), data[length:]

    def read_int8(self, data):
        try:
            return struct.unpack_from(">b", data, 0)[0], data[1:]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def read_uint8(self, data):
        try:
            return struct.unpack_from(">B", data, 0)[0], data[1:]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def read_int16(self, data):
        try:
            return struct.unpack_from(">h", data, 0)[0], data[2:]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def read_uint16(self, data):
        try:
            return struct.unpack_from(">H", data, 0)[0], data[2:]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def read_int32(self, data):
        try:
            return struct.unpack_from(">i", data, 0)[0], data[4:]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def read_uint32(self, data):
        try:
            return struct.unpack_from(">I", data, 0)[0], data[4:]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def read_int64(self, data):
        try:
            return struct.unpack_from(">q", data, 0)[0], data[8:]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def read_uint64(self, data):
        try:
            return struct.unpack_from(">Q", data, 0)[0], data[8:]
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    READERS = {
        FieldType.I8: read_int8,
        FieldType.U8: read_uint8,
        FieldType.I16: read_int16,
        FieldType.U16: read_uint16,
        FieldType.I32: read_int32,
        FieldType.U32: read_uint32,
        FieldType.I64: read_int64,
        FieldType.U64: read_uint64,
        FieldType.STRINGID: read_uint16,
        FieldType.STRING: read_string,
    }
