# This file is part of OpenTTDLab.
# Copyright © Patric Stout: initial implementation of OpenTTD savegame parsing and converting to link graph
# Copyright © Michal Charemza: additions and changes to run OpenTTD to generate savegames, and to process parsed savegames further
# OpenTTDLab is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, version 2.
# OpenTTDLab is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with OpenTTDLab. If not, see <http://www.gnu.org/licenses/>.

import enum
import hashlib
import io
import json
import lzma
import os
import os.path
import platform
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import uuid
import zipfile
import zlib
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import httpx
import yaml
from platformdirs import user_cache_dir


# On release this is replaced by the release's corresponding git tag
__version__ = '0.0.0.dev0'


def run_experiment(
    ais=(),
    days=365 * 4 + 1,
    seeds=(1,),
    openttd_base_url='https://cdn.openttd.org/openttd-releases/',
    opengfx_base_url='https://cdn.openttd.org/opengfx-releases/',
):
    def get(url):
        response = httpx.get(url)
        response.raise_for_status()
        return response.content

    def get_yaml(url):
        return yaml.safe_load(get(url))

    def stream_to_file_if_necessary(source_url, target_location):
        file_exists = os.path.exists(target_location)

        if os.path.exists(target_location):
            return

        with httpx.stream("GET", source_url) as r:
            r.raise_for_status()
            with open(target_location, 'wb') as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def find_details(manifest, filename):
        files_by_id = {
            file['id']: file
            for file in manifest['files']
        }
        try:
            return files_by_id[filename]
        except KeyError:
            raise Exception("Unable to fine platform-specific file", filename)

    def check_sha_256(location, expected_sha_256):
        sha256 = hashlib.sha256()
        with open(location, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                sha256.update(chunk)

        digest = sha256.hexdigest()
        if digest != expected_sha_256:
            raise Exception(f"SHA256 of {location} does not match its published value")

    def extract_7z(archive_location, output_dir):
        subprocess.check_output(('7z', 'x', '-y', f'-o{output_dir}', f'{archive_location}'))

    def extract_tar_xz(archive_location, output_dir):
        with tarfile.open(archive_location, 'r:xz') as f_tar:
            for name in f_tar.getnames():
                if '..' in name or name.strip().startswith('/'):
                    raise Exception('Unsafe', archive_location)
            f_tar.extractall(output_dir)

    def extract_zip(archive_location, output_dir):
        with zipfile.ZipFile(archive_location, 'r') as f_zip:
            for name in f_zip.namelist():
                if '..' in name or name.strip().startswith('/'):
                    raise Exception('Unsafe', archive_location)
            f_zip.extractall(output_dir)

    def parse_savegame(seed, filename):
        with open(filename, 'rb') as f:
            game = Savegame()
            game.read(f)

            # Python (and indeed, the gregorian calendar) doesn't have a year zero,
            # and according to the OpenTTD source, year 1 was a leap year
            days_since_year_zero = game.items['DATE']['0']['date']
            days_since_year_one = days_since_year_zero - 366
            for index, player in game.items['PLYR'].items():
                yield {
                    'seed': seed,
                    'date': date(1, 1 , 1) + timedelta(days_since_year_one),
                    'player': player['name'],
                    'money': player['money'],
                    'loan': player['current_loan'],
                }

    # Choose platform-specific details
    extractors = {
        'dmg': extract_7z,
        'tar.xz': extract_tar_xz,
        'zip': extract_zip,
    }
    system_machine_to_release_params = {
        ('Darwin', 'arm64'): ('macos', 'universal', 'dmg', '{binary_dir}/openttd-{version}-macos-universal/OpenTTD.app/Contents/MacOS/openttd'),
        ('Darwin', 'x86_64'): ('macos', 'universal', 'dmg', '{binary_dir}/openttd-{version}-macos-universal/OpenTTD.app/Contents/MacOS/openttd'),
        ('Linux', 'x86_64'): ('linux-generic', 'amd64', 'tar.xz', '{binary_dir}/openttd-{version}-linux-generic-amd64/openttd'),
        ('Windows', 'AMD64'): ('windows', 'win64', 'zip', '{binary_dir}/openttd-{version}-windows-win64/openttd.exe'),
    }
    uname = platform.uname()
    try:
        operating_system, architecture, openttd_extension, openttd_binary_template = system_machine_to_release_params[(uname.system, uname.machine)]
    except KeyError:
        raise Exception("Unable to map platform to OpenTTD release", uname.system, uname.machine)

    # Find version and coresponding manifest
    openttd_version = str(get_yaml(openttd_base_url + 'latest.yaml')['latest'][0]['version'])
    opengfx_version = str(get_yaml(opengfx_base_url + 'latest.yaml')['latest'][0]['version'])
    openttd_manifest = get_yaml(openttd_base_url + openttd_version + '/manifest.yaml')
    opengfx_manifest = get_yaml(opengfx_base_url + opengfx_version + '/manifest.yaml')

    # Find file details in manifest
    openttd_filename = f"{openttd_manifest['base']}{operating_system}-{architecture}.{openttd_extension}"
    opengfx_filename = f"{opengfx_manifest['base']}all.zip"
    openttd_file_details = find_details(openttd_manifest, openttd_filename)
    opengfx_file_details = find_details(opengfx_manifest, opengfx_filename)

    # Download archives if necessary
    cache_dir = user_cache_dir(appname='OpenTTDLab', ensure_exists=True)
    openttd_archive_location = os.path.join(cache_dir, openttd_filename)
    opengfx_archive_location = os.path.join(cache_dir, opengfx_filename)
    stream_to_file_if_necessary(openttd_base_url + openttd_version + '/' + openttd_filename, openttd_archive_location)
    stream_to_file_if_necessary(opengfx_base_url + opengfx_version + '/' + opengfx_filename, opengfx_archive_location)
    check_sha_256(openttd_archive_location, openttd_file_details['sha256sum'])
    check_sha_256(opengfx_archive_location, opengfx_file_details['sha256sum'])

    # Extract the binaries
    openttd_binary_dir = f'{openttd_archive_location}-{openttd_file_details["sha256sum"]}'
    opengfx_binary_dir = f'{opengfx_archive_location}-{opengfx_file_details["sha256sum"]}'
    Path(openttd_binary_dir).mkdir(parents=True, exist_ok=True)
    Path(opengfx_binary_dir).mkdir(parents=True, exist_ok=True)
    extractors[openttd_extension](openttd_archive_location, openttd_binary_dir)
    extractors['zip'](opengfx_archive_location, opengfx_binary_dir)

    # Construct the location of the binaries
    openttd_binary = os.path.join(openttd_binary_dir, openttd_binary_template.format_map({
        'binary_dir': openttd_binary_dir,
        'version': openttd_version,
    }))
    opengfx_binary = os.path.join(opengfx_binary_dir, f'opengfx-{opengfx_version}.tar')

    # Ensure the OpenTTD binary is executable
    os.chmod(openttd_binary, os.stat(openttd_binary).st_mode | stat.S_IEXEC)

    def run(experiment_dir, i, seed):
        run_dir = os.path.join(experiment_dir, str(i))
        experiment_baseset_dir = os.path.join(run_dir, 'baseset')
        Path(experiment_baseset_dir).mkdir(parents=True)
        experiment_ai_dir = os.path.join(run_dir, 'ai')
        Path(experiment_ai_dir).mkdir(parents=True)

        # Populate run directory
        shutil.copy(opengfx_binary, experiment_baseset_dir)
        for ai_name, ai_file in ais:
            shutil.copy(os.path.join(experiment_dir, ai_name + '.tar'), experiment_ai_dir)
        config_file = os.path.join(run_dir, 'openttdlab.cfg')
        ai_players_config = '[ai_players]\n' + ''.join(
            f'{ai_name} = start_date=0\n' for ai_name, file in ais
        )
        with open(config_file, 'w') as f:
            f.write(textwrap.dedent('''
                [gui]
                autosave = monthly
                keep_all_autosave = true
                threaded_saves = false
                [difficulty]
                max_no_competitors = 1
            ''' + ai_players_config)
        )

        # Run the experiment
        ticks_per_day = 74
        ticks = str(ticks_per_day * days)
        subprocess.check_output(
            (openttd_binary,) + (
                '-g',                     # Start game immediately
                '-G', str(seed),          # Seed for random number generator
                '-snull',                 # No sound
                '-mnull',                 # No music
                '-vnull:ticks=' + ticks,  # No video, with fixed number of "ticks" and then exit
                 '-c', config_file,       # Config file
            ),
            cwd=run_dir,                  # OpenTTD looks in the current working directory for files
        )

        autosave_dir = os.path.join(run_dir, 'save', 'autosave')
        autosave_filenames = sorted(list(os.listdir(autosave_dir)))
        return [
            savegame_row
            for filename in autosave_filenames
            for savegame_row in parse_savegame(seed, os.path.join(autosave_dir, filename))
        ]

    experiment_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix=f'OpenTTDLab-{experiment_id}-') as experiment_dir:
        for ai_name, ai_file in ais:
            ai_file(ai_name, experiment_dir)
        return [
            savegame_row
            for i, seed in enumerate(seeds)
            for savegame_row in run(experiment_dir, i, seed)
        ], None


def local_file(filename):
    def _copy(ai_name, target):
        shutil.copy(filename, os.path.join(target, ai_name + '.tar'))

    return _copy


def remote_file(url):
    def gz_decompress(compressed_chunks):
        dec = zlib.decompressobj(32 + zlib.MAX_WBITS)
        for compressed_chunk in compressed_chunks:
            chunk = dec.decompress(compressed_chunk)
            if chunk:
                yield chunk
        chunk = dec.flush()
        if chunk:
            yield chunk

    def _download(ai_name, target):
        with httpx.stream("GET", url, follow_redirects=True) as r:
            r.raise_for_status()
            with open(os.path.join(target, ai_name + '.tar'), 'wb') as f:
                for chunk in gz_decompress(r.iter_bytes()):
                    f.write(chunk)

    return _download


def save_config():
    pass


def load_config():
    pass


class FieldType(enum.IntEnum):
    END = 0
    I8 = 1
    U8 = 2
    I16 = 3
    U16 = 4
    I32 = 5
    U32 = 6
    I64 = 7
    U64 = 8
    STRINGID = 9
    STRING = 10
    STRUCT = 11


class BinaryReader:
    """
    Read binary data.
    """

    def read(self, amount):
        raise NotImplementedError

    def gamma(self):
        """
        Read OTTD-savegame-style gamma value.
        """
        b = self.uint8()[0]
        if (b & 0x80) == 0:
            return (b & 0x7F, 1)
        elif (b & 0xC0) == 0x80:
            return ((b & 0x3F) << 8 | self.uint8()[0], 2)
        elif (b & 0xE0) == 0xC0:
            return ((b & 0x1F) << 16 | self.uint16()[0], 3)
        elif (b & 0xF0) == 0xE0:
            return ((b & 0x0F) << 24 | self.uint24()[0], 4)
        elif (b & 0xF8) == 0xF0:
            return ((b & 0x07) << 32 | self.uint32()[0], 5)
        else:
            raise ValidationException("Invalid gamma encoding.")

    def gamma_str(self):
        """
        Read OTTD-savegame-style gamma string (SLE_STR).
        """
        size, _size = self.gamma()
        string = self.read(size).decode()
        return string, size + _size

    def int8(self):
        try:
            return struct.unpack(">b", self.read(1))[0], 1
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint8(self):
        try:
            return struct.unpack(">B", self.read(1))[0], 1
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def int16(self):
        try:
            return struct.unpack(">h", self.read(2))[0], 2
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint16(self):
        try:
            return struct.unpack(">H", self.read(2))[0], 2
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint24(self):
        return (self.uint16()[0] << 8) | self.uint8()[0], 3

    def int32(self):
        try:
            return struct.unpack(">l", self.read(4))[0], 4
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint32(self):
        try:
            return struct.unpack(">L", self.read(4))[0], 4
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def int64(self):
        try:
            return struct.unpack(">q", self.read(8))[0], 8
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    def uint64(self):
        try:
            return struct.unpack(">Q", self.read(8))[0], 8
        except struct.error:
            raise ValidationException("Unexpected end-of-file.")

    READERS = {
        FieldType.I8: int8,
        FieldType.U8: uint8,
        FieldType.I16: int16,
        FieldType.U16: uint16,
        FieldType.I32: int32,
        FieldType.U32: uint32,
        FieldType.I64: int64,
        FieldType.U64: uint64,
        FieldType.STRINGID: uint16,
        FieldType.STRING: gamma_str,
    }


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


FIELD_TYPE_HAS_LENGTH_FIELD = 0x10


class ValidationException(Exception):
    pass


class Savegame():

    def __init__(self):
        self.savegame_version = None
        self.tables = {}
        self.items = defaultdict(dict)

    def read_all_tables(self, reader):
        """Read all the tables from the header."""

        def read_fields_sizes():
            while True:
                type = struct.unpack(">b", reader.read(1))[0]
                yield None, 1

                if type == 0:
                    break

                key_length, index_size = reader.gamma()
                yield None, index_size

                key = reader.read(key_length)
                yield None, key_length

                field_type = FieldType(type & 0xf)
                yield (
                    field_type,
                    True if type & FIELD_TYPE_HAS_LENGTH_FIELD else False,
                    key.decode(),
                ), 0

        def read_table():
            """Read a single table from the header."""

            fields_sizes = list(read_fields_sizes())

            return [field for field, _ in fields_sizes if field is not None], sum(size for _, size in fields_sizes)

        def read_substruct(table):
            for field_type, is_list, sub_key in table:
                if field_type == FieldType.STRUCT:
                    sub_table, sub_size = read_table()
                    yield sub_key, sub_table, sub_size
                    yield from read_substruct(sub_table)

        root_table, root_size = read_table()
        sub_key_tables_sizes = list(read_substruct(root_table))

        tables = {
            "root": root_table,
            **({
                sub_key: sub_table
                for sub_key, sub_table, _ in sub_key_tables_sizes
            }),
        }
        size = root_size + sum(sub_size for _, _, sub_size in sub_key_tables_sizes)

        return tables, size

    def _check_tail(self, reader, item):
        try:
            reader.uint8()
        except ValidationException:
            pass
        else:
            raise ValidationException(f"Junk at the end of {item}.")

    def read(self, fp):
        """Read the savegame."""

        reader = BinaryReaderFile(fp)

        compression = reader.read(4)
        self.savegame_version = reader.uint16()[0]
        reader.uint16()

        decompressor = UNCOMPRESS.get(compression)
        if decompressor is None:
            raise ValidationException(f"Unknown savegame compression {compression}.")

        uncompressed = decompressor.open(fp)
        reader = BinaryReaderFileBlockMode(uncompressed)

        while True:
            tag = reader.read(4)
            if len(tag) == 0 or tag == b"\0\0\0\0":
                break
            if len(tag) != 4:
                raise ValidationException("Invalid savegame.")

            tag = tag.decode()

            m = reader.uint8()[0]
            type = m & 0xF
            if type == 0:
                size = (m >> 4) << 24 | reader.uint24()[0]
                self.read_item(tag, {}, -1, size, reader)
            elif 1 <= type <= 4:
                if type >= 3:  # CH_TABLE or CH_SPARSE_TABLE
                    size = reader.gamma()[0] - 1

                    tables, size_read = self.read_all_tables(reader)
                    if size_read != size:
                        raise ValidationException("Table header size mismatch.")

                    self.tables[tag] = tables
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
                        self.read_item(tag, tables, index, size, reader)
            else:
                raise ValidationException("Unknown chunk type.")

        self._check_tail(reader, "file")

    def _read_item(self, reader, tables, key="root"):
        size = 0
        result = {}

        for field in tables[key]:
            res, _size = self.read_field(reader, tables, field[0], field[1], field[2])
            size += _size
            result[field[2]] = res

        return result, size

    def read_field(self, reader, tables, field, is_list, field_name):
        if is_list and field != FieldType.STRING:
            length, size = reader.gamma()

            res = []
            for _ in range(length):
                item, _size = self.read_field(reader, tables, field, False, field_name)
                size += _size
                res.append(item)
            return res, size

        if field == FieldType.STRUCT:
            return self._read_item(reader, tables, field_name)

        return reader.READERS[field](reader)

    def read_item(self, tag, tables, index, expected_size, reader):
        table_index = "0" if index == -1 else str(index)
        size = 0

        if tables:
            self.items[tag][table_index], size = self._read_item(reader, tables)
            if tag not in ("GSDT", "AIPL"):  # Known chunk with garbage at the end
                if size != expected_size:
                    raise ValidationException(f"Junk at end of chunk {tag}")
        else:
            self.tables[tag] = {"unsupported": ""}

        reader.read(expected_size - size)


"""
Script to read in the JSON from savegame_reader, and export the linkgraph
only. Linkgraphs are stored in an efficient way on disk, which makes them
slightly less usable for automation. This script is meant as inspiration how
to deal with the linkgraph to get a proper linkgraph out of it.

On the root is a list of cargos. For each cargo there is [from][to] containing
all the edges. "from" and "to" are stationIDs.
"""


def linkgraph():
    result = defaultdict(lambda: defaultdict(lambda: dict()))

    data = json.load(sys.stdin)

    for lgrp in data["chunks"]["LGRP"].values():
        i = -1
        nodes = {}
        edges = {}

        for node in lgrp["nodes"]:
            i += 1
            nodes[i] = node["station"]

            to = i
            for edge in node["edges"]:
                edges[(i, to)] = (edge["capacity"], edge["usage"])
                to = edge["next_edge"]

        for (i, to), (c, u) in edges.items():
            if c == 0:
                continue

            i = nodes[i]
            to = nodes[to]

            result[lgrp["cargo"]][i][to] = {"capacity": c, "usage": u}

    print(json.dumps(result))
