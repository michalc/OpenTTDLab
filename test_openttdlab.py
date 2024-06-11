import json
import os
import tarfile
import tempfile
from datetime import date

import pytest

from openttdlab import (
    parse_savegame,
    run_experiments,
    local_folder,
    local_file,
    remote_file,
    bananas_ai,
    bananas_ai_library,
    download_from_bananas,
)


def _basic_data(result_row):
    return [{
        'seed': result_row['experiment']['seed'],
        'date': result_row['date'],
        'openttd_version': result_row['openttd_version'],
        'opengfx_version': result_row['opengfx_version'],
        'name': result_row['chunks']['PLYR']['0']['name'],
        'money': result_row['chunks']['PLYR']['0']['money'],
        'current_loan': result_row['chunks']['PLYR']['0']['current_loan'],
        'terrain_type': result_row['chunks']['PATS']['0']['difficulty.terrain_type'],
        'error': result_row['error'],
    }]

# OpenTTD 14.0 changed the way autosave works which OpenTTDLab depended on
# It changes saving per X game time to per X real time. While this is being
# worked on/figured out, disabling the test
@pytest.mark.skip(reason='OpenTTDLab no longer works on OpenTTD 14.0')
def test_run_experiments_local_ai_default_version():
    results = run_experiments(
        experiments=(
            {
                'seed': seed,
                'ais': (
                    local_file('./fixtures/54524149-trAIns-2.1.tar', 'trAIns'),
                ),
                'days': 365 * 5 + 1,
            }
            for seed in range(2, 4)
        ),
    )

    assert len(results) == 118
    assert {
        key: value
        for key, value in _basic_data(results[58]).items()
        if key not in ('openttd_version', 'opengfx_version')
    } == {
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 110000,
        'money': 6371,
        'error': '',
    }
    assert tuple(int(v) for v in results[58]['openttd_version'].split('.')) >= (13, 4)
    assert tuple(int(v) for v in results[58]['opengfx_version'].split('.')) >= (7, 1)

    assert {
        key: value
        for key, value in _basic_data(results[117]).items()
        if key not in ('openttd_version', 'opengfx_version')
    } == {
        'seed': 3,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 300000,
        'money': 641561,
    }
    assert tuple(int(v) for v in results[117]['openttd_version'].split('.')) >= (13, 4)
    assert tuple(int(v) for v in results[117]['opengfx_version'].split('.')) >= (7, 1)


def test_run_experiments_local_ai_early_version_of_openttd():
    results = run_experiments(
        openttd_version='12.0',
        opengfx_version='7.1',
        experiments=(
            {
                'seed': seed,
                'ais': (
                    local_file('./fixtures/54524149-trAIns-2.1.tar', 'trAIns'),
                ),
                'days': 365 * 5 + 1,
            }
            for seed in range(2, 4)
        ),
        result_processor=_basic_data,
    )

    assert len(results) == 118
    assert results[117] == {
        'openttd_version': '12.0',
        'opengfx_version': '7.1',
        'seed': 3,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 300000,
        'money': 320011,
        'terrain_type': 1,
        'error': False,
    }


def test_run_experiments_local_folder_from_tar():

    with tempfile.TemporaryDirectory() as d:
        with tarfile.open('./fixtures/54524149-trAIns-2.1.tar', 'r') as f_tar:
            for name in f_tar.getnames():
                if '..' in name or name.strip().startswith('/'):
                    raise Exception('Unsafe', archive_location)
            f_tar.extractall(d)

        results = run_experiments(
            experiments=(
                {
                    'seed': seed,
                    'ais': (
                        local_folder(d, 'trAIns'),
                    ),
                    'days': 365 * 5 + 1,
                }
                for seed in range(2, 4)
            ),
            openttd_version='13.4',
            opengfx_version='7.1',
            result_processor=_basic_data,
        )

    assert len(results) == 118
    assert results[58] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 110000,
        'money': 6371,
        'terrain_type': 1,
        'error': False,
    }
    assert results[117] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 3,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 300000,
        'money': 641561,
        'terrain_type': 1,
        'error': False,
    }

def test_run_experiments_local_folder():
    results = run_experiments(
        experiments=(
            {
                'seed': seed,
                'ais': (
                    local_folder('./fixtures/NoOpAIImportingPathfinder-1', 'NoOpAIImportingPathfinder'),
                ),
                'days': 366 * 1 + 1,
            }
            for seed in range(0, 1)
        ),
        ai_libraries=(
            bananas_ai_library('5046524f', 'Pathfinder.Road'),
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
        result_processor=_basic_data,
    )

    assert len(results) == 12
    assert results[-1] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 0,
        'name': 'NoOpAIImportingPathfinder',
        'date': date(1951, 1, 1),
        'current_loan': 100000,
        'money': 97700,
        'terrain_type': 1,
        'error': False,
    }

def test_run_experiments_multiple_local_folder():
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open('./fixtures/54524149-trAIns-2.1.tar', 'r') as f_tar:
            for name in f_tar.getnames():
                print('name', name)
                if '..' in name or name.strip().startswith('/'):
                    raise Exception('Unsafe', archive_location)
            f_tar.extractall(d)

        results = run_experiments(
            experiments=(
                {
                    'seed': seed,
                    'ais': (
                        local_folder(os.path.join(d, 'trAIns-2.1'), 'trAIns'),
                        local_folder('./fixtures/NoOpAIImportingPathfinder-1', 'NoOpAIImportingPathfinder'),
                    ),
                    'days': 366 * 1 + 1,
                }
                for seed in range(0, 1)
            ),
            ai_libraries=(
                bananas_ai_library('5046524f', 'Pathfinder.Road'),
            ),
            openttd_version='13.4',
            opengfx_version='7.1',
        )

    assert len(results) == 12
    assert results[-1]['chunks']['PLYR']['0']['name'] == 'trAIns AI'
    assert results[-1]['chunks']['PLYR']['1']['name'] == 'NoOpAIImportingPathfinder'


def test_run_experiments_with_error():
    # This particular seed is known to make this version of trAINs error

    results = run_experiments(
        openttd_version='13.4',
        opengfx_version='7.1',
        experiments=(
            {
                'seed': seed,
                'ais': (
                    bananas_ai('54524149', 'trAIns'),
                    bananas_ai('41444d4c', 'AdmiralAI', ai_params=(
                        ('use_trains', '1'),
                        ('use_busses', '0'),
                        ('use_trucks', '0'),
                        ('use_planes', '0'),
                    )),
                ),
                'days': 365 * 10 + 1,
                'openttd_config': f'''
                    [game_creation]
                    starting_year=1960
                ''',
            }
            for seed in range(18, 19)
        ),
        max_workers=4,
        result_processor=lambda result: ({
            'error': result['error'],
            'output': result['output'],
        },),
    )
    assert "trains" in results[-1]['output']
    assert "the index 'exit_tile' does not exist" in results[-1]['output']
    assert results[-1]['error'] == True


def test_run_experiments_local_file():

    results = run_experiments(
        experiments=(
            {
                'seed': seed,
                'ais': (
                    local_file('./fixtures/54524149-trAIns-2.1.tar', 'trAIns',),
                ),
                'days': 365 * 5 + 1,
            }
            for seed in range(2, 4)
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
        result_processor=_basic_data,
    )

    assert len(results) == 118
    assert results[58] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 110000,
        'money': 6371,
        'terrain_type': 1,
        'error': False,
    }
    assert results[117] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 3,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 300000,
        'money': 641561,
        'terrain_type': 1,
        'error': False,
    }


def test_run_experiments_local_file_different_config():
    results = run_experiments(
        experiments=(
            {
                'seed': seed,
                'ais': (
                    local_file('./fixtures/54524149-trAIns-2.1.tar', 'trAIns',),
                ),
                'days': 365 * 1 + 1,
                'openttd_config': f'[difficulty]\nterrain_type = {terrain_type}\n',
            }
            for seed in range(2, 3)
            for terrain_type in [1, 3]
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
        result_processor=_basic_data,
    )

    assert len(results) == 24
    assert results[1] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1950, 3, 1),
        'current_loan': 300000,
        'money': 285340,
        'terrain_type': 1,
        'error': False,
    }
    assert results[23] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1951, 1, 1),
        'current_loan': 180000,
        'money': 5855,
        'terrain_type': 3,
        'error': False,
    }


def test_run_experiments_remote():
    results = run_experiments(
        experiments=(
            {
                'seed': seed,
                'ais': (
                    remote_file('https://github.com/lhrios/trains/archive/refs/tags/2014_02_14.tar.gz', 'trAIns'),
                ),
                'days': 365 + 1,
            }
            for seed in range(2, 3)
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
        result_processor=_basic_data,
    )

    assert len(results) == 12
    assert results[10] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1950, 12, 1),
        'current_loan': 300000,
        'money': 280615,
        'terrain_type': 1,
        'error': False,
    }


def test_run_experiments_bananas_without_deps():
    results = run_experiments(
        experiments=(
            {
                'seed': seed,
                'ais': (
                    bananas_ai('54524149', 'trAIns'),
                ),
                'days': 365 + 1,
            }
            for seed in range(2, 3)
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
        result_processor=_basic_data,
    )

    assert len(results) == 12
    assert results[10] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1950, 12, 1),
        'current_loan': 300000,
        'money': 280615,
        'terrain_type': 1,
        'error': False,
    }


def test_run_experiments_bananas_with_deps():
    results = run_experiments(
        experiments=(
            {
                'seed': seed,
                'ais': (
                    bananas_ai('41444d4c', 'AdmiralAI'),
                ),
                'days': 365 + 1,
            }
            for seed in range(2, 3)
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
        result_processor=_basic_data,
    )

    assert len(results) == 12
    assert results[10] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'AdmiralAI and co.',
        'date': date(1950, 12, 1),
        'current_loan': 300000,
        'money': 69995,
        'terrain_type': 1,
        'error': False,
    }


def test_run_experiments_bananas_as_library():
    # Run multiple time to check caching behavior
    for _ in range(0, 2):
        results = run_experiments(
            experiments=(
                {
                    'seed': seed,
                    'ais': (
                        local_file('./fixtures/NoOpAIImportingPathfinder-1.tar', 'NoOpAIImportingPathfinder'),
                    ),
                    'days': 365 + 1,
                }
                for seed in range(2, 3)
            ),
            ai_libraries=(
                bananas_ai_library('5046524f', 'Pathfinder.Road'),
            ),
            openttd_version='13.4',
            opengfx_version='7.1',
            result_processor=_basic_data,
        )

        assert len(results) == 12
        assert results[10] == {
            'openttd_version': '13.4',
            'opengfx_version': '7.1',
            'seed': 2,
            'name': 'NoOpAIImportingPathfinder',
            'date': date(1950, 12, 1),
            'current_loan': 100000,
            'money': 97891,
            'terrain_type': 1,
            'error': False,
        }


def test_run_experiments_screenshots():
    def read_header(file):
        with open(file, 'rb') as f:
            return f.read(32)

    with tempfile.TemporaryDirectory(prefix=f'OpenTTD-screenshots-') as screenshot_dir:
        results = run_experiments(
            experiments=(
                {
                    'seed': seed,
                    'ais': (
                        bananas_ai('54524149', 'trAIns'),
                    ),
                    'days': 365 + 1,
                }
                for seed in range(2, 4)
            ),
            final_screenshot_directory=screenshot_dir,
            openttd_version='13.4',
            opengfx_version='7.1',
            result_processor=_basic_data,
        )
        screenshots = list(sorted(os.listdir(screenshot_dir)))
        screenshots_are_pngs = all(
            read_header(os.path.join(screenshot_dir, screenshot)).startswith(b'\x89PNG\r\n\x1A\n')
            for screenshot in screenshots
        )
        screenshot_sizes_big = [
            os.path.getsize(os.path.join(screenshot_dir, screenshot)) > 10000000
            for screenshot in screenshots
        ]

    assert len(results) == 24
    assert results[10] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1950, 12, 1),
        'current_loan': 300000,
        'money': 280615,
        'terrain_type': 1,
        'error': False,
    }
    assert screenshots == ['2.png', '3.png']
    assert screenshots_are_pngs
    assert screenshot_sizes_big


@pytest.mark.parametrize(
    "savegame_format",
    ("none", "zlib", "lzma"),
)
def test_savegame_formats(savegame_format):
    results = run_experiments(
        experiments=(
            {
                'openttd_config': f'[misc]\nsavegame_format={savegame_format}\n',
                'seed': seed,
                'ais': (
                    local_file('./fixtures/54524149-trAIns-2.1.tar', 'trAIns'),
                ),
                'days': 100,
            }
            for seed in range(2, 3)
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
        result_processor=_basic_data,
    )

    assert len(results) == 3
    assert results[2] == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1950, 4, 1),
        'current_loan': 300000,
        'money': 284815,
        'terrain_type': 1,
        'error': False,
    }


def test_savegame_parser():
    with open('./fixtures/warbourne-cross-transport-2029-01-06.sav', 'rb') as f:
        game = parse_savegame(iter(lambda: f.read(65536), b''))

    # There is a little bit of information loss in JSON encoding, e.g. lists and tuples both
    # get converted to lists. But I suspect it's acceptable to ignore.
    # (The dumping and loading here is to "normalise" into the post information loss form)
    with open('./fixtures/warbourne-cross-transport-2029-01-06.json','rb') as f:
        assert json.loads(json.dumps(game))['chunks'] == json.loads(f.read())['chunks']


def test_bananas_download():

    file_details = []
    with download_from_bananas('ai/505a4c41') as files:
        for content_id, filename, md5sum, get_data in files:
            file_details.append((content_id, filename, md5sum))
            with get_data() as chunks:
                for chunk in chunks:
                    pass

    assert len(file_details) == 3
    for content_id, filename, md5sum in file_details:
        assert len(md5sum) == 8
    assert file_details[0][0] == 'ai/505a4c41'
    assert file_details[1][0] == 'ai-library/4752412a'
    assert file_details[2][0] == 'ai-library/51554248'

    assert file_details[0][1].startswith('505a4c41-PathZilla')
    assert file_details[1][1].startswith('4752412a-Graph.AyStar')
    assert file_details[2][1].startswith('51554248-Queue.BinaryHeap')
