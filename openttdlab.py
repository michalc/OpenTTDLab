import hashlib
import os
import os.path
import platform
import shutil
import stat
import subprocess
import tarfile
import textwrap
import uuid
import zipfile
from pathlib import Path

import httpx
import yaml
from platformdirs import user_cache_dir


# On release this is replaced by the release's corresponding git tag
__version__ = '0.0.0.dev0'


def run_experiment(
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

    # Choose platform-specific details
    extractors = {
        'dmg': extract_7z,
        'tar.xz': extract_tar_xz,
        'zip': extract_zip,
    }
    system_machine_to_release_params = {
        ('Darwin', 'arm64'): ('macos', 'universal', 'dmg', '{binary_dir}/openttd-{version}-macos-universal/OpenTTD.app/Contents/MacOS/openttd'),
        ('Darwin', 'amd64'): ('macos', 'universal', 'dmg', '{binary_dir}/openttd-{version}-macos-universal/OpenTTD.app/Contents/MacOS/openttd'),
        ('Linux', 'x86_64'): ('linux-generic', 'amd64', 'tar.xz', '{binary_dir}/openttd-{version}-linux-generic-amd64/openttd'),
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

    # Run the experiment
    experiment_id = uuid.uuid4().hex
    experiment_dir = os.path.join(cache_dir, 'experiments', experiment_id)
    experiment_baseset_dir = os.path.join(experiment_dir, 'baseset')
    Path(experiment_baseset_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy(opengfx_binary, experiment_baseset_dir)
    config_file = os.path.join(experiment_dir, 'openttdlab.cfg')
    with open(config_file, 'w') as f:
        f.write(textwrap.dedent('''
            [gui]
            autosave = daily
            keep_all_autosave = true
        ''')
    )
    subprocess.check_output(
        (openttd_binary,) + (
            # Start game immediately
            '-g',
            # Seed for random number generator
            '-G', str(1),
            # No sound
            '-snull',
            # No music
            '-mnull',
            # No video, with fixed number of "ticks" and then exit
            '-vnull:ticks=5000',
            # Config file
             '-c', config_file,
        ),
        cwd=experiment_dir,    # OpenTTD looks in the current working directory for files
    )
    # Not a long term plan, but so the tests can assert on something
    with open(os.path.join(experiment_dir, 'save', 'autosave', 'Spectator, 1950-02-01-autosave.sav'), 'rb') as f:
        return f.read(), None


def save_config():
    pass


def load_config():
    pass
