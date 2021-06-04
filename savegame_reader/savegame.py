import hashlib
import io
import lzma
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
        self.tables = defaultdict(dict)

    def read_table(self, tag, reader):
        fields = []
        size = 0
        while True:
            type = reader.read(1)
            size += 1
            if type == b"\x00":
                break

            length, index_size = reader.gamma()
            size += length + index_size
            key = reader.read(length)

            fields.append((type, key.decode()))

        header = {field[1]: int.from_bytes(field[0], "big") for field in fields}
        if "header" in self.tables[tag]:
            self.tables[tag]["header"].update(header)
        else:
            self.tables[tag] = {"header": header}

        return fields, size

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

                    tables = []
                    while size > 0:
                        table, length = self.read_table(tag, reader)
                        size -= length
                        tables.append(table)
                else:
                    tables = []

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

    def read_field(self, field, reader):
        if field == b"\x01":
            return int.from_bytes(reader.read(1), "big", signed=True)
        if field == b"\x02":
            return int.from_bytes(reader.read(1), "big", signed=False)
        if field == b"\x03":
            return int.from_bytes(reader.read(2), "big", signed=True)
        if field == b"\x04":
            return int.from_bytes(reader.read(2), "big", signed=False)
        if field == b"\x05":
            return int.from_bytes(reader.read(4), "big", signed=True)
        if field == b"\x06":
            return int.from_bytes(reader.read(4), "big", signed=False)
        if field == b"\x07":
            return int.from_bytes(reader.read(8), "big", signed=True)
        if field == b"\x08":
            return int.from_bytes(reader.read(8), "big", signed=False)
        if field == b"\x09":
            return int.from_bytes(reader.read(2), "big", signed=False)
        if field == b"\x0a":
            length = reader.gamma()[0]
            return reader.read(length).decode()

        raise ValidationException("Unknown field type.")

    def read_item(self, tag, tables, index, data):
        reader = BinaryReader(io.BytesIO(data))

        table_index = "0" if index == -1 else str(index)

        if index == -1 and tag == "PATS" and self.savegame_version >= 292:
            fields, _ = self.read_table(tag, reader)
            self.tables[tag][table_index] = {}

            for field in fields:
                res = self.read_field(field[0], reader)
                self.tables[tag][table_index][field[1]] = res

            return
        elif tables:
            self.tables[tag][table_index] = {}

            for table in tables:
                for field in table:
                    res = self.read_field(field[0], reader)
                    self.tables[tag][table_index][field[1]] = res
        else:
            self.tables[tag][table_index] = {"unsupported": ""}
