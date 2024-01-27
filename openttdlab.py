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

    def get_savegame_row(seed, filename):
        with open(filename, 'rb') as f:
            game = parse_savegame(iter(lambda: f.read(65536), b''))

        # Python (and indeed, the gregorian calendar) doesn't have a year zero,
        # and according to the OpenTTD source, year 1 was a leap year
        days_since_year_zero = game['chunks']['DATE']['records']['0']['date']
        days_since_year_one = days_since_year_zero - 366
        for index, player in game['chunks']['PLYR']['records'].items():
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
            for savegame_row in get_savegame_row(seed, os.path.join(autosave_dir, filename))
        ]

    experiment_id = str(uuid.uuid4())
    with tempfile.TemporaryDirectory(prefix=f'OpenTTDLab-{experiment_id}-') as experiment_dir:
        for ai_name, ai_file in ais:
            ai_file(ai_name, experiment_dir)
        return [
            savegame_row
            for i, seed in enumerate(seeds)
            for savegame_row in run(experiment_dir, i, seed)
        ], None, None


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


def parse_savegame(chunks, chunk_size=65536):

    def get_readers(iterable):
        chunk = b''
        chunk_offset = 0
        offset = 0
        it = iter(iterable)

        def _num_iter(num):
            nonlocal chunk, chunk_offset, offset

            while num:
                if chunk_offset == len(chunk):
                    try:
                        chunk = next(it)
                    except StopIteration:
                        raise ValidationException("Unexpected end-of-file.")
                    chunk_offset = 0
                to_yield = min(num, len(chunk) - chunk_offset, chunk_size)
                num -= to_yield
                chunk_offset += to_yield
                offset += to_yield
                yield chunk[chunk_offset - to_yield:chunk_offset]

        def _read_iter():
            try:
                yield from _num_iter(float('inf'))
            except ValidationException:
                pass

        def _read(num):
            return b''.join(_num_iter(num))

        def _offset():
            return offset

        return _read, _read_iter, _offset

    def decompress_zlib(compressed_chunks):
        dobj = zlib.decompressobj()
        for compressed_chunk in compressed_chunks:
            if chunk := dobj.decompress(compressed_chunk, max_length=chunk_size):
                yield chunk

            while dobj.unconsumed_tail and not dobj.eof and (chunk := dobj.decompress(dobj.unconsumed_tail, max_length=chunk_size)):
                yield chunk

    def decompress_lzma(compressed_chunks):
        dobj = lzma.LZMADecompressor()
        for compressed_chunk in compressed_chunks:
            if chunk := dobj.decompress(compressed_chunk, max_length=chunk_size):
                yield chunk

            while not dobj.eof and (chunk := dobj.decompress(b'', max_length=chunk_size)):
                yield chunk

    def decompress_none(compressed_chunks):
        yield from compressed_chunks

    decompressors = {
        b"OTTN": decompress_none,
        b"OTTZ": decompress_zlib,
        b"OTTX": decompress_lzma,
        # According to https://github.com/OpenTTD/OpenTTD/blob/master/docs/savegame_format.md
        # only very old savegames will use this. Happy to not support that
        # b"OTTD": lzo2,
    }

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

    def _raise(e):
        raise e

    def gamma(read):
        """
        Read OTTD-savegame-style gamma value.
        """
        b = uint8(read)
        return \
            (b & 0x7F) if (b & 0x80) == 0 else \
            (b & 0x3F) << 8 | uint8(read) if (b & 0xC0) == 0x80 else \
            (b & 0x1F) << 16 | uint16(read) if (b & 0xE0) == 0xC0 else \
            (b & 0x0F) << 24 | uint24(read) if (b & 0xF0) == 0xE0 else \
            (b & 0x07) << 32 | uint32(read) if (b & 0xF8) == 0xF0 else \
            _raise(ValidationException("Invalid gamma encoding."))

    def gamma_str(read):
        """
        Read OTTD-savegame-style gamma string (SLE_STR).
        """
        return read(gamma(read)).decode()

    def int8(read):
        return struct.unpack(">b", read(1))[0]

    def uint8(read):
        return struct.unpack(">B", read(1))[0]

    def int16(read):
        return struct.unpack(">h", read(2))[0]

    def uint16(read):
        return struct.unpack(">H", read(2))[0]

    def uint24(read):
        return (uint16(read) << 8) | uint8(read)

    def int32(read):
        return struct.unpack(">l", read(4))[0]

    def uint32(read):
        return struct.unpack(">L", read(4))[0]

    def int64(read):
        return struct.unpack(">q", read(8))[0]

    def uint64(read):
        return struct.unpack(">Q", read(8))[0]

    readers = {
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

    def read_headers(read):
        """Reads the headers for a chunk."""

        def read_fields():
            while type := int8(read):
                yield (
                    FieldType(type & 0xf),  # Field type
                    bool(type & 0x10),      # Has length
                    gamma_str(read),        # Key
                )

        def read_substruct(header, parent_key):
            for field_type, has_length, sub_key in header:
                if field_type == FieldType.STRUCT:
                    sub_header = list(read_fields())
                    full_sub_key = f'{parent_key}.{sub_key}'
                    yield full_sub_key, sub_header
                    yield from read_substruct(sub_header, full_sub_key)

        root_header = list(read_fields())
        sub_headers = list(read_substruct(root_header, "root"))
        return {
            "root": root_header,
            **dict(sub_headers),
        }

    def read_record(read, headers):
        """Reads a record for a chunk."""

        def read_using_header_key(key):
            return {
                sub_key: \
                    read_list_of_fields(field_type, f'{key}.{sub_key}') if has_length and field_type != FieldType.STRING else \
                    read_field(field_type, f'{key}.{sub_key}')
                for field_type, has_length, sub_key in headers[key]
            }

        def read_list_of_fields(field_type, field_name):
            length = gamma(read)
            return [
                read_field(field_type, field_name)
                for _ in range(length)
            ]

        def read_field(field_type, field_name):
            return \
                read_using_header_key(field_name) if field_type == FieldType.STRUCT else \
                readers[field_type](read)

        return read_using_header_key("root")

    def read_records(read, offset, headers, tag, chunk_type):
        index = -1
        while size_plus_one := gamma(read):

            start_offset = inner_offset()
            if chunk_type == 4:
                index = gamma(read)
            else:
                index += 1
            end_offset = inner_offset()

            size = size_plus_one - 1 - (end_offset - start_offset)

            if size != 0:
                start_offset = inner_offset()
                record = read_record(read, headers)
                end_offset = inner_offset()

                # GSDT and AIPL are known chunk with garbage at the end
                if tag not in ("GSDT", "AIPL") and size != (end_offset - start_offset):
                    raise ValidationException(f"Junk at end of chunk {tag}")

                read(size - (end_offset - start_offset))

                yield str(index), record

    def read_chunks(read, offset):
        while (tag_bytes := read(4)) != b"\0\0\0\0":
            tag = tag_bytes.decode()

            m = uint8(read)
            chunk_type = m & 0xF

            if chunk_type == 0:
                size = (m >> 4) << 24 | uint24(read)
                read(size)
                headers = {"unsupported": ""}
                records = ()

            elif chunk_type in (1, 2):
                while size_plus_one := gamma(read):
                    read(size_plus_one - 1)
                headers = {"unsupported": ""}
                records = ()

            elif chunk_type in (3, 4):  # CH_TABLE or CH_SPARSE_TABLE
                size = gamma(read) - 1

                start_offset = inner_offset()
                headers = read_headers(read)
                end_offset = inner_offset()
                if size != (end_offset - start_offset):
                    raise ValidationException("Table header size mismatch.")

                records = read_records(read, offset, headers, tag, chunk_type)
            else:
                raise ValidationException("Unknown chunk type.")

            yield tag, headers, records

        # Check tail
        try:
            uint8(inner_read)
        except ValidationException:
            pass
        else:
            raise ValidationException(f"Junk at the end of file.")

    outer_read, outer_read_iter, _ = get_readers(chunks)
    compression = outer_read(4)
    savegame_version = uint16(outer_read)
    uint16(outer_read)

    try:
        decompressor = decompressors[compression]
    except KeyError:
        raise ValidationException(f"Unknown savegame compression {compression}.")

    inner_read, _, inner_offset = get_readers(decompressor(outer_read_iter()))

    return {
        'savegame_version': savegame_version,
        'chunks': {
            tag: {
                'headers': headers,
                'records': {
                    record_index: record
                    for record_index, record in records
                }
            }
            for tag, headers, records in read_chunks(inner_read, inner_offset)
        }
    }


class ValidationException(Exception):
    pass


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
