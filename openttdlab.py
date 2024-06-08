# This file is part of OpenTTDLab.
# Copyright © Patric Stout: initial implementation of OpenTTD savegame parsing and converting to link graph
# Copyright © Michal Charemza: additions and changes to run OpenTTD to generate savegames, and to process parsed savegames further
# OpenTTDLab is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, version 2.
# OpenTTDLab is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with OpenTTDLab. If not, see <http://www.gnu.org/licenses/>.

import contextlib
import enum
import hashlib
import itertools
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
import socket
import sys
import tarfile
import tempfile
import textwrap
import uuid
import zipfile
import zlib
from collections import defaultdict, deque
from datetime import date, timedelta
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from urllib.parse import urlparse
from rich.progress import MofNCompleteColumn, BarColumn, SpinnerColumn, TextColumn, Progress

import httpx
import yaml
from dill import dumps, loads
from platformdirs import user_cache_dir


# On release this is replaced by the release's corresponding git tag
__version__ = '0.0.0.dev0'


CONTENT_TYPE_AI = 3
CONTENT_TYPE_AI_LIBRARY = 4


def run_experiments(
    experiments=(),
    ai_libraries=(),
    final_screenshot_directory=None,
    max_workers=None,
    openttd_version=None,
    opengfx_version=None,
    openttd_base_url='https://cdn.openttd.org/openttd-releases/',
    opengfx_base_url='https://cdn.openttd.org/opengfx-releases/',
    result_processor=lambda x: (x,),
    get_http_client=lambda: httpx.Client(transport=httpx.HTTPTransport(retries=3)),
):
    def get(client, url):
        response = client.get(url)
        response.raise_for_status()
        return response.content

    def get_yaml(client, url):
        return yaml.safe_load(get(client, url))

    def stream_to_file_if_necessary(client, source_url, target_location):
        file_exists = os.path.exists(target_location)

        if os.path.exists(target_location):
            return

        with client.stream("GET", source_url) as r:
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

    with get_http_client() as client:

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
        if openttd_version is None:
            openttd_version = str(get_yaml(client, openttd_base_url + 'latest.yaml')['latest'][0]['version'])
        if opengfx_version is None:
            opengfx_version = str(get_yaml(client, opengfx_base_url + 'latest.yaml')['latest'][0]['version'])
        openttd_manifest = get_yaml(client, openttd_base_url + openttd_version + '/manifest.yaml')
        opengfx_manifest = get_yaml(client, opengfx_base_url + opengfx_version + '/manifest.yaml')

        # Find file details in manifest
        openttd_filename = f"{openttd_manifest['base']}{operating_system}-{architecture}.{openttd_extension}"
        opengfx_filename = f"{opengfx_manifest['base']}all.zip"
        openttd_file_details = find_details(openttd_manifest, openttd_filename)
        opengfx_file_details = find_details(opengfx_manifest, opengfx_filename)

        # Download archives if necessary
        cache_dir = user_cache_dir(appname='OpenTTDLab', ensure_exists=True)
        openttd_archive_location = os.path.join(cache_dir, openttd_filename)
        opengfx_archive_location = os.path.join(cache_dir, opengfx_filename)
        stream_to_file_if_necessary(client, openttd_base_url + openttd_version + '/' + openttd_filename, openttd_archive_location)
        stream_to_file_if_necessary(client, opengfx_base_url + opengfx_version + '/' + opengfx_filename, opengfx_archive_location)
        check_sha_256(openttd_archive_location, openttd_file_details['sha256sum'])
        check_sha_256(opengfx_archive_location, opengfx_file_details['sha256sum'])

        # Check if we can use xvfb_run to avoid windows popping up when taking a screenshot
        xvfb_run_available = subprocess.call("type xvfb-run", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

        def run_done(progress, task, _):
            progress.update(task, advance=1)
            progress.refresh()

        run_id = str(uuid.uuid4())
        experiments_list = list(experiments)
        with tempfile.TemporaryDirectory(prefix=f'OpenTTDLab-{run_id}-') as run_dir:
            # Extract the binaries into the run dir
            openttd_binary_dir = os.path.join(run_dir, f'{openttd_filename}-{openttd_file_details["sha256sum"]}')
            opengfx_binary_dir = os.path.join(run_dir, f'{opengfx_filename}-{opengfx_file_details["sha256sum"]}')
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

            # Make sure to only make any internet connections for AIs at most once for
            # each AI, even if referenced in multiple experiments
            ai_copy_functions = {
                ai_name: ai_copy
                for experiment in experiments_list
                for ai_name, _, ai_copy in experiment.get('ais', [])
            }
            ai_and_library_filenames = [
                ai_filename
                for _, ai_copy in ai_copy_functions.items()
                for ai_filename in ai_copy(client, cache_dir, run_dir)
            ] + [
                ai_library_filename
                for _, ai_library_copy in ai_libraries
                for ai_library_filename in ai_library_copy(client, cache_dir, run_dir)
            ]

            max_workers = \
                max_workers if max_workers is not None else \
                (os.cpu_count() or 1)
            with \
                    Progress(
                        SpinnerColumn(finished_text='[green]✔'),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        MofNCompleteColumn(),
                    ) as progress:
                pool = Pool(processes=max_workers)
                try:
                    task = progress.add_task("Running experiments...", total=len(experiments_list))
                    async_results = [
                        pool.apply_async(
                            _run_experiment,
                            args=(
                                opengfx_binary, openttd_binary, final_screenshot_directory,
                                openttd_version, opengfx_version, dumps(result_processor),
                                run_dir, i, dumps(experiment), ai_and_library_filenames,
                                xvfb_run_available,
                            ),
                            callback=partial(run_done, progress, task),
                        )
                        for i, experiment in enumerate(experiments_list)
                    ]

                    return [
                        savegame_row
                        for savegame_rows_async_result in async_results
                        for savegame_row in loads(savegame_rows_async_result.get())
                    ]
                finally:
                    # Not calling these explicitly can result in code coverage not measuring
                    # subprocesses. Even using Pool as a context manager doesn't call these
                    pool.close()
                    pool.join()


def _run_experiment(
        opengfx_binary, openttd_binary, final_screenshot_directory,
        openttd_version, opengfx_version, result_processor,
        run_dir, i, experiment, ai_and_library_filenames,
        xvfb_run_available,
):
    result_processor = loads(result_processor)
    experiment = loads(experiment)

    def get_savegame_row(openttd_version, opengfx_version, experiment, filename, output):
        with open(filename, 'rb') as f:
            game = parse_savegame(iter(lambda: f.read(65536), b''))

        # Python (and indeed, the gregorian calendar) doesn't have a year zero,
        # and according to the OpenTTD source, year 1 was a leap year
        days_since_year_zero = game['chunks']['DATE']['records']['0']['date']
        days_since_year_one = days_since_year_zero - 366
        return result_processor({
            'openttd_version': openttd_version,
            'opengfx_version': opengfx_version,
            'savegame_version': game['savegame_version'],
            'experiment': experiment,
            'date': date(1, 1 , 1) + timedelta(days_since_year_one),
            'error': 'The script died unexpectedly' in output,
            'output': output,
            'chunks': {
                tag: chunk['records'] for tag, chunk in game['chunks'].items()
            },
        })

    experiment_dir = os.path.join(run_dir, str(i))
    experiment_baseset_dir = os.path.join(experiment_dir, 'baseset')
    Path(experiment_baseset_dir).mkdir(parents=True)
    experiment_ai_dir = os.path.join(experiment_dir, 'ai')
    Path(experiment_ai_dir).mkdir(parents=True)
    experiment_ai_library_dir = os.path.join(experiment_dir, 'ai/library')
    Path(experiment_ai_library_dir).mkdir(parents=True)
    experiment_script_dir = os.path.join(experiment_dir, 'scripts')
    Path(experiment_script_dir).mkdir(parents=True)

    openttd_config = experiment.get('openttd_config', '')
    days = experiment['days']
    seed = experiment['seed']

    # Populate run directory
    shutil.copy(opengfx_binary, experiment_baseset_dir)
    for path, ai_or_library_filename in ai_and_library_filenames:
        shutil.copy(
            os.path.join(run_dir, ai_or_library_filename),
            os.path.join(experiment_dir, *path, ai_or_library_filename),
        )
    config_file = os.path.join(experiment_dir, 'openttdlab.cfg')

    with open(os.path.join(experiment_script_dir, 'game_start.scr'), 'w') as f:
        f.write(''.join(
            f'start_ai {ai_name}' + (' ' + ','.join(f'{key}={value}' for key, value in ai_params) if ai_params else '') + '\n'
            for ai_name, ai_params, _ in experiment.get('ais', [])
        ))
    with open(config_file, 'w') as f:
        f.write(textwrap.dedent(openttd_config) + textwrap.dedent('''
            [gui]
            autosave = monthly
            keep_all_autosave = true
            threaded_saves = false
        ''')
    )

    # Run the experiment
    ticks_per_day = 74
    ticks = str(ticks_per_day * days)
    output = subprocess.check_output(
        (openttd_binary,) + (
            '-g',                     # Start game immediately
            '-G', str(seed),          # Seed for random number generator
            '-snull',                 # No sound
            '-mnull',                 # No music
            '-vnull:ticks=' + ticks,  # No video, with fixed number of "ticks" and then exit
             '-c', config_file,       # Config file
        ),
        cwd=experiment_dir,                  # OpenTTD looks in the current working directory for files
        stderr=subprocess.STDOUT,
        text=True,
    )

    autosave_dir = os.path.join(experiment_dir, 'save', 'autosave')
    autosave_filenames = sorted(list(os.listdir(autosave_dir)))

    if final_screenshot_directory is not None:
        with open(os.path.join(experiment_script_dir, 'game_start.scr'), 'w') as f:
            f.write('screenshot giant\n')
            f.write('quit\n')

        subprocess.check_output(
            (('xvfb-run', '-a',) if xvfb_run_available else ()) + (openttd_binary,) + (
                '-g', os.path.join(autosave_dir, autosave_filenames[-1]),
                '-G', str(seed),          # Seed for random number generator
                '-snull',                 # No sound
                '-mnull',                 # No music
                 '-c', config_file,       # Config file
            ),
            cwd=experiment_dir,                  # OpenTTD looks in the current working directory for files
        )
        screenshot_file = os.listdir(os.path.join(experiment_dir, 'screenshot'))[0]
        shutil.copyfile(
            os.path.join(experiment_dir, 'screenshot', screenshot_file),
            os.path.join(final_screenshot_directory, str(seed) + '.png'),
        )

    return dumps([
        result_row
        for filename in autosave_filenames
        for result_row in get_savegame_row(openttd_version, opengfx_version, experiment, os.path.join(autosave_dir, filename), output)
    ])


def _gz_decompress(compressed_chunks):
    dec = zlib.decompressobj(32 + zlib.MAX_WBITS)
    for compressed_chunk in compressed_chunks:
        chunk = dec.decompress(compressed_chunk)
        if chunk:
            yield chunk
    chunk = dec.flush()
    if chunk:
        yield chunk


def local_file(file_path, ai_name, ai_params=()):
    def _copy(client, cache_dir, target):
        shutil.copy(file_path, os.path.join(target, ai_name + '.tar'))
        return ((('ai',), ai_name + '.tar'),)

    return ai_name, ai_params, _copy


def local_folder(folder_path, ai_name, ai_params=()):
    def _copy(client, cache_dir, target):
        with tarfile.open(os.path.join(target, ai_name + '.tar'), 'w') as tar:
            # Arcname adds the folder to a folder in the root of the tar. Doesn't seem to
            # matter what the folder is called, as long as there is one
            tar.add(folder_path, arcname='local-ai')
        return ((('ai',), ai_name + '.tar'),)

    return ai_name, ai_params, _copy


def remote_file(url, ai_name, ai_params=()):
    def _download(client, cache_dir, target):
        with client.stream("GET", url, follow_redirects=True) as r:
            r.raise_for_status()
            with open(os.path.join(target, ai_name + '.tar'), 'wb') as f:
                for chunk in _gz_decompress(r.iter_bytes()):
                    f.write(chunk)
        return ((('ai',), ai_name + '.tar'),)

    return ai_name, ai_params, _download


def _bananas_download(bananas_type_id, bananas_type_str, unique_id, content_name):

    def _download(client, cache_dir, target):
        @contextlib.contextmanager
        def tcp_connection(address):

            def recv_iter(length):
                while length:
                    chunk = s.recv(length)
                    if not chunk:
                        raise Exception("Connection ended")
                    length -= len(chunk)
                    yield chunk

            def recv_bytes(length):
                return b''.join(recv_iter(length))

            def send_bytes(bytes_to_send):
                s.sendall(bytes_to_send)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    s.settimeout(10.0)
                    s.connect(("content.openttd.org", 3978))
                    yield recv_bytes, send_bytes
                finally:
                    try:
                        s.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

        def final_location_path(bananas_type_id):
            return {
                CONTENT_TYPE_AI: ('ai',),
                CONTENT_TYPE_AI_LIBRARY: ('ai', 'library',),
            }[bananas_type_id]

        def get_tcp_content_ids(bananas_type_id, unique_id, md5sum=None):

            def reader(b):
                i = 0

                def read_num(num):
                    nonlocal i
                    i += num
                    return b[i-num:i]

                def _next_null():
                    j = i
                    while b[j] != 0:
                        j += 1
                    return j

                def read_until_null():
                    nonlocal i
                    start = i
                    end = _next_null()
                    i = end + 1
                    return b[start:end]

                return read_num, read_until_null
                
            # Convert unique ID to content ID from the Bananas TCP server, and get its expected filesize
            with tcp_connection(("content.openttd.org", 3978)) as (recv_bytes, send_bytes):
                PACKET_CONTENT_CLIENT_INFO_EXTID = 2
                PACKET_CONTENT_CLIENT_INFO_EXTID_MD5 = 3
                request_type = \
                    PACKET_CONTENT_CLIENT_INFO_EXTID if md5sum is None else\
                    PACKET_CONTENT_CLIENT_INFO_EXTID_MD5
                packet_body = \
                    struct.pack("<B", request_type) + \
                    struct.pack("<B", 1) + \
                    struct.pack("<B", bananas_type_id) + \
                    struct.pack("4s", bytes.fromhex(unique_id)) + \
                    (struct.pack("16s", bytes.fromhex(md5sum)) if md5sum is not None else b'')
                send_bytes(struct.pack("<H", len(packet_body) + 2) + packet_body)

                PACKET_CONTENT_SERVER_INFO = 4
                packet_size = struct.unpack("<H", recv_bytes(2))[0]
                if packet_size < 12:
                    raise Exception('Response is too small')
                packet_read_num, packet_read_until_null = reader(recv_bytes(packet_size - 2))
                tcp_packet_type = struct.unpack("<B", packet_read_num(1))[0]
                tcp_content_type = struct.unpack("<B", packet_read_num(1))[0]
                tcp_content_id = struct.unpack("<I", packet_read_num(4))[0]
                tcp_file_size = struct.unpack("<I", packet_read_num(4))[0]
                tcp_name = packet_read_until_null()
                tcp_version = packet_read_until_null()
                tcp_url = packet_read_until_null()
                tcp_description = packet_read_until_null()
                tcp_unique_id = packet_read_num(4)
                tcp_md5sum = packet_read_num(16)
                tcp_num_dependencies = packet_read_num(1)[0]
                tcp_dependency_content_ids = tuple(
                    struct.unpack("<I", packet_read_num(4))[0]
                    for _ in range(0, tcp_num_dependencies)
                )

                return tcp_content_id, tcp_dependency_content_ids

        # Confirm via HTTPs that this name/unique ID pair exists
        api_resp = client.get(f'https://bananas-api.openttd.org/package/{bananas_type_str}/{unique_id}')
        api_resp.raise_for_status()
        api_dict = api_resp.json()
        api_dict_latest_version = max(api_dict['versions'], key=lambda version: version['version'].split('.'))

        # Check if we already have this version cached, and all its dependencies
        content_cache_dir = os.path.join(cache_dir, 'bananas')
        Path(content_cache_dir).mkdir(parents=True, exist_ok=True)
        filename = f'{unique_id}-{api_dict["name"]}-{api_dict_latest_version["version"]}.tar'
        cached_file = os.path.join(content_cache_dir, filename)
        cached_dependency_file = cached_file + '_dependencies'
        if os.path.exists(cached_file) and os.path.exists(cached_dependency_file):
            with open(cached_dependency_file, 'r', encoding='utf-8') as f:
                contents = f.read()
            dependency_filenames = [
                (tuple(line.split(',')[0].split('/')), line.split(',')[1])
                for line in contents.splitlines()
            ] if contents else []
            for path,dependency_filename in dependency_filenames:
                shutil.copy(os.path.join(content_cache_dir, dependency_filename), os.path.join(target, dependency_filename))

            shutil.copy(cached_file, os.path.join(target, filename))
            return [(final_location_path(bananas_type_id),filename),] + dependency_filenames

        # Check name is what client code expected
        if api_dict['name'] != content_name:
            raise Exception("Mismatched name")

        # Get content ID of the primary content requested from client code, and the content IDs
        # of all its dependencies. We treat them slightly differently because we have already
        # found the dependencies of the primary content, but will still need to find the dependencies
        # of the dependencies later
        primary_content_id, dependency_content_ids = get_tcp_content_ids(bananas_type_id, unique_id)

        # Download and cache content, and and all transitive dependencies. Note that transitive
        # dependencies can be specified by exact version, and to download those we need the MD5 sum
        # of the dependency, which we only know by finding the link to it, so it's a bit of a dance
        filenames = []
        to_download = deque()
        to_download.append((False, primary_content_id))
        for content_id in dependency_content_ids:
            to_download.append((True, content_id))
        while to_download:
            find_transitive, content_id = to_download.popleft()
            response = client.post('https://binaries.openttd.org/bananas', content=str(content_id).encode() + b'\n')
            response.raise_for_status()
            binaries_content_id, binaries_content_type, binaries_filesize, binaries_link = response.text.strip().split(',')
            binaries_md5sum = urlparse(binaries_link).path.split('/')[3]
            binaries_unique_id = urlparse(binaries_link).path.split('/')[2]
            filename = urlparse(binaries_link).path.split('/')[-1][:-3]  # Withouth .gz extension

            # Download from CDN URL
            with client.stream("GET", binaries_link) as response:
                response.raise_for_status()
                if response.headers['content-length'] != binaries_filesize:
                    raise Exception('Mismatched filesize')

                with open(os.path.join(target, filename), 'wb') as f:
                    for chunk in _gz_decompress(response.iter_bytes()):
                        f.write(chunk)

                cached_file = os.path.join(content_cache_dir, filename)
                shutil.copy(os.path.join(target, filename), cached_file)
                filenames.append((final_location_path(int(binaries_content_type)), filename),)

            if find_transitive:
                _, transitive_content_ids = get_tcp_content_ids(int(binaries_content_type), binaries_unique_id, md5sum=binaries_md5sum)
                for transitive_content_id in transitive_content_ids:
                    to_download.append((True, transitive_content_id))

        # Write dependency file - simple text file
        with open(cached_dependency_file, 'w', encoding='utf-8') as f:
            for path, filename in filenames[1:]:
                f.write('/'.join(path) + ',' + filename + '\n')

        return filenames

    return _download


def bananas_ai(unique_id, ai_name, ai_params=()):
    return ai_name, ai_params, _bananas_download(CONTENT_TYPE_AI, 'ai', unique_id, ai_name)


def bananas_ai_library(unique_id, ai_library_name):
    return ai_library_name, _bananas_download(CONTENT_TYPE_AI_LIBRARY, 'ai-library', unique_id, ai_library_name)


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
        # only very old savegames will use OTTD by default. However from testing you _can_
        # configure current OpenTTD by specifing savegame_format=lzo in config, but then it seems
        # very tricky to decompress this from Python, especially in a streaming way. Maybe one day...
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

    def read_table_headers(read):
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

    def read_table_record(read, headers):
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

    def read_table_records(read, offset, headers, tag, chunk_type):
        counter = iter(itertools.count())

        while size_plus_one := gamma(read):

            start_offset = offset()
            index = \
                gamma(read) if chunk_type == 4 else \
                next(counter)
            end_offset = offset()

            size = size_plus_one - 1 - (end_offset - start_offset)

            if size == 0:
                continue

            start_offset = offset()
            record = read_table_record(read, headers)
            end_offset = offset()

            # GSDT and AIPL are known chunk with garbage at the end
            if tag not in ("GSDT", "AIPL") and size != (end_offset - start_offset):
                raise ValidationException(f"Junk at end of chunk {tag}")

            read(size - (end_offset - start_offset))

            yield str(index), record

    def read_chunks(read, offset):

        def read_riff_chunk():
            size = (m >> 4) << 24 | uint24(read)
            read(size)
            headers = {"unsupported": ""}
            records = ()
            return headers, records

        def read_array_chunk():
            while size_plus_one := gamma(read):
                read(size_plus_one - 1)
            headers = {"unsupported": ""}
            records = ()
            return headers, records

        def read_table_chunk(tag, chunk_type):
            size = gamma(read) - 1

            start_offset = offset()
            headers = read_table_headers(read)
            end_offset = offset()

            if size != (end_offset - start_offset):
                raise ValidationException("Table header size mismatch.")

            return headers, read_table_records(read, offset, headers, tag, chunk_type)

        while (tag_bytes := read(4)) != b"\0\0\0\0":
            tag = tag_bytes.decode()

            m = uint8(read)
            chunk_type = m & 0xF

            if chunk_type not in (0, 1, 2, 3, 4):
                raise ValidationException("Unknown chunk type.")

            yield (tag,) + (
                read_riff_chunk() if chunk_type == 0 else \
                read_array_chunk() if chunk_type in (1, 2) else \
                read_table_chunk(tag, chunk_type)
            )

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
