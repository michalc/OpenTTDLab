import hashlib
import os.path
import platform
import subprocess

import httpx
import yaml
from platformdirs import user_cache_dir


def setup_experiment(
    base_url='https://cdn.openttd.org/openttd-releases/',
):
    def get(url):
        response = httpx.get(url)
        response.raise_for_status()
        return response.content

    def get_yaml(url):
        return yaml.safe_load(get(url))

    # Find latest OpenTTD
    latest_version = str(get_yaml(base_url + 'latest.yaml')['latest'][0]['version'])
    manifest = get_yaml(base_url + latest_version + '/manifest.yaml')

    # Find the name of the file to download for this platform
    system_machine_to_release_params = {
        ('Darwin', 'arm64'): ('macos', 'universal', 'dmg'),
        ('Darwin', 'amd64'): ('macos', 'universal', 'dmg'),
        ('Linux', 'x86_64'): ('linux-generic', 'amd64', 'tar.xz'),
    }
    uname = platform.uname()
    try:
        operating_system, architecture, extension = system_machine_to_release_params[(uname.system, uname.machine)]
    except KeyError:
        raise Exception("Unable to map platform to OpenTTD release", uname.system, uname.machine)

    files_by_id = {
        file['id']: file
        for file in manifest['files']
    }
    filename = f"{manifest['base']}{operating_system}-{architecture}.{extension}"
    try:
        file_details = files_by_id[filename]
    except KeyError:
        raise Exception("Unable to fine platform-specific file in OpenTTD release", filename)

    # Check if the file already exists
    cache_dir = user_cache_dir(appname='OpenTTDLab', ensure_exists=True)
    expected_file_location = os.path.join(cache_dir, filename)
    file_exists = os.path.exists(expected_file_location)

    # Download the file if necessary (avoiding loading it all into memory)
    if not os.path.exists(expected_file_location):
        with httpx.stream("GET", base_url + latest_version + '/' + filename) as r:
            r.raise_for_status()
            with open(expected_file_location, 'wb') as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    # Check the file matches the SHA256 in the manifest
    sha256 = hashlib.sha256()
    with open(expected_file_location, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)

    digest = sha256.hexdigest()
    if digest != file_details['sha256sum']:
        raise Exception(f"SHA256 of {expected_file_location} does not match its published value")

    # Extract the file
    subprocess.check_output(['7z', 'x', '-y', f'-o{expected_file_location}-{digest}', expected_file_location])

    def run_experiment():
        pass

    def get_config():
        pass

    return run_experiment, get_config

def save_config():
    pass


def load_config():
    pass
