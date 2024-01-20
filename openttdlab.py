import hashlib
import os
import os.path
import platform
import shutil
import stat
import subprocess
import textwrap
import uuid
from pathlib import Path

import httpx
import yaml
from platformdirs import user_cache_dir


def setup_experiment(
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

    def extract(template, archive_location, output_dir):
        subprocess.check_output([
            arg.format_map({
                'archive_location': archive_location,
                'output_dir': output_dir,
            })
            for arg in template
        ])

    # Choose platform-specific details
    extract_templates = {
        'dmg': ('7z', 'x', '-y', '-o{output_dir}', '{archive_location}'),
        'tar.xz': ('tar', 'xf', '{archive_location}', '-C', '{output_dir}'),
        'zip': ('unzip', '-o', '{archive_location}', '-d', '{output_dir}'),
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
    extract(extract_templates[openttd_extension], openttd_archive_location, openttd_binary_dir)
    extract(extract_templates['zip'], opengfx_archive_location, opengfx_binary_dir)

    openttd_binary = os.path.join(openttd_binary_dir, openttd_binary_template.format_map({
        'binary_dir': openttd_binary_dir,
        'version': openttd_version,
    }))
    opengfx_binary = os.path.join(opengfx_binary_dir, f'opengfx-{opengfx_version}.tar')
    os.chmod(openttd_binary, os.stat(openttd_binary).st_mode | stat.S_IEXEC)

    def run_experiment():
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
            return f.read()

    def get_config():
        pass

    return run_experiment, get_config

def save_config():
    pass


def load_config():
    pass
