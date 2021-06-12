import lzma
import zlib


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
