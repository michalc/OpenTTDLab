import hashlib
import io
import lzma
import struct
import zlib

from collections import defaultdict

from .binreader import BinaryReader
from .exceptions import ValidationException


class PlainFile:
    @staticmethod
    def open(f):
        return f


class ZLibFile:
    @staticmethod
    def open(f):
        return ZLibFile(f)

    def __init__(self, file):
        self.file = file
        self.decompressor = zlib.decompressobj()
        self.uncompressed = bytearray()

    def close(self):
        pass

    def read(self, amount):
        while len(self.uncompressed) < amount:
            new_data = self.file.read(8192)
            if len(new_data) == 0:
                break
            self.uncompressed += self.decompressor.decompress(new_data)

        data = self.uncompressed[0:amount]
        self.uncompressed = self.uncompressed[amount:]
        return data


UNCOMPRESS = {
    b"OTTN": PlainFile,
    b"OTTZ": ZLibFile,
    b"OTTX": lzma,
    # Although OpenTTD supports lzo2, it is very difficult to load this in
    # Python. Additionally, no savegame ever uses this format (OTTN is
    # prefered over OTTD, which requires no additional libraries in the
    # OpenTTD client), unless a user specificly switches to it. As such,
    # it is reasonably enough to simply refuse this compression format.
    # b"OTTD": lzo2,
}


class Savegame:
    def __init__(self, filename):
        self.filename = filename
        self.md5sum = None
        self.savegame_version = None
        self.tables = defaultdict(lambda: {"header": {}, "items": {}})

    def _read_table(self, reader):
        fields = []
        size = 0
        while True:
            type = struct.unpack(">B", reader.read(1))[0]
            size += 1

            if type == 0:
                break

            key_length, index_size = reader.gamma()
            size += key_length + index_size
            key = reader.read(key_length)

            fields.append((type, key.decode()))

        return fields, size

    def _read_substruct(self, reader, tables, key):
        size = 0

        for field in tables[key]:
            if field[0] & 0xf == 11:
                tables[field[1]], sub_size = self._read_table(reader)
                size += sub_size
                size += self._read_substruct(reader, tables, field[1])

        return size

    def read_table(self, tag, reader):
        tables = {}

        tables["root"], size = self._read_table(reader)
        size += self._read_substruct(reader, tables, "root")

        header = {field[1]: f"{field[0]:02x}" for field in tables["root"]}
        self.tables[tag]["header"].update(header)

        return tables, size

    def read(self, fp):
        """
        Read savegame meta data.

        @param fp: Filepointer to read (should already be open)
        @type fp: File-like object
        """

        md5sum = hashlib.md5()
        reader = BinaryReader(fp, md5sum)

        compression = reader.read(4)
        self.savegame_version = reader.uint16(be=True)
        reader.uint16()

        decompressor = UNCOMPRESS.get(compression)
        if decompressor is None:
            raise ValidationException(f"Unknown savegame compression {compression}.")

        uncompressed = decompressor.open(reader)
        reader = BinaryReader(uncompressed)

        while True:
            tag = reader.read(4)
            if len(tag) == 0 or tag == b"\0\0\0\0":
                break
            if len(tag) != 4:
                raise ValidationException("Invalid savegame.")

            tag = tag.decode()

            m = reader.uint8()
            type = m & 0xF
            if type == 0:
                size = (m >> 4) << 24 | reader.uint24(be=True)
                self.read_item(tag, [], -1, reader.read(size))
            elif 1 <= type <= 4:
                if type >= 3:
                    size = reader.gamma()[0] - 1

                    tables, size_read = self.read_table(tag, reader)
                    if size_read != size:
                        raise ValidationException("Table header size mismatch.")
                else:
                    tables = {}

                index = -1
                while True:
                    size = reader.gamma()[0] - 1
                    if size < 0:
                        break
                    if type == 2 or type == 4:
                        index, index_size = reader.gamma()
                        size -= index_size
                    else:
                        index += 1
                    if size != 0:
                        self.read_item(tag, tables, index, reader.read(size))
            else:
                raise ValidationException("Unknown chunk type.")

        try:
            reader.uint8()
        except ValidationException:
            pass
        else:
            raise ValidationException("Junk at the end of file.")

        self.md5sum = md5sum.digest()

    def read_field(self, reader, tables, field, field_name):
        # Lists, with the exception of a string
        if field & 0x10 and (field & 0xf) != 10:
            length = reader.gamma()[0]
            return [self.read_field(reader, tables, field & 0xf, field_name) for _ in range(length)]

        if field == 1:
            return struct.unpack(">b", reader.read(1))[0]
        if field == 2:
            return struct.unpack(">B", reader.read(1))[0]
        if field == 3:
            return struct.unpack(">h", reader.read(2))[0]
        if field == 4:
            return struct.unpack(">H", reader.read(2))[0]
        if field == 5:
            return struct.unpack(">i", reader.read(4))[0]
        if field == 6:
            return struct.unpack(">I", reader.read(4))[0]
        if field == 7:
            return struct.unpack(">q", reader.read(8))[0]
        if field == 8:
            return struct.unpack(">Q", reader.read(8))[0]
        if field == 9:
            return struct.unpack(">H", reader.read(2))[0]
        if field == 10 | 0x10:
            length = reader.gamma()[0]
            return reader.read(length).decode()
        if field == 11:
            return self._read_item(reader, tables, field_name)

        raise ValidationException("Unknown field type.", field)

    def _read_item(self, reader, tables, key="root"):
        result = {}

        for field in tables[key]:
            res = self.read_field(reader, tables, field[0], field[1])
            result[field[1]] = res

        return result

    def read_item(self, tag, tables, index, data, key="root"):
        reader = BinaryReader(io.BytesIO(data))

        table_index = "0" if index == -1 else str(index)

        if tables:
            self.tables[tag]["items"][table_index] = self._read_item(reader, tables)
        else:
            self.tables[tag]["header"] = {"unsupported": ""}
