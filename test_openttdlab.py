import json
from datetime import date

import pytest

from openttdlab import parse_savegame, run_experiment, local_file, remote_file, bananas_file


def _basic_data(result_row):
    return {
        'seed': result_row['seed'],
        'date': result_row['date'],
        'openttd_version': result_row['openttd_version'],
        'opengfx_version': result_row['opengfx_version'],
        'name': result_row['chunks']['PLYR']['0']['name'],
        'money': result_row['chunks']['PLYR']['0']['money'],
        'current_loan': result_row['chunks']['PLYR']['0']['current_loan'],
    }


def test_run_experiment_local_ai_default_version():
    results = run_experiment(
        days=365 * 5 + 1,
        seeds=range(2, 4),
        ais=(
            ('trAIns', local_file('./fixtures/54524149-trAIns-2.1.tar')),
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
        'money': 6546,
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
        'money': 672573,
    }
    assert tuple(int(v) for v in results[117]['openttd_version'].split('.')) >= (13, 4)
    assert tuple(int(v) for v in results[117]['opengfx_version'].split('.')) >= (7, 1)


def test_run_experiment_local():
    results = run_experiment(
        days=365 * 5 + 1,
        seeds=range(2, 4),
        ais=(
            ('trAIns', local_file('./fixtures/54524149-trAIns-2.1.tar')),
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
    )

    assert len(results) == 118
    assert _basic_data(results[58]) == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 110000,
        'money': 6546,
    }
    assert _basic_data(results[117]) == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 3,
        'name': 'trAIns AI',
        'date': date(1954, 12, 1),
        'current_loan': 300000,
        'money': 672573,
    }


def test_run_experiment_remote():
    results = run_experiment(
        days=365 + 1,
        seeds=range(2, 3),
        ais=(
            ('trAIns', remote_file('https://github.com/lhrios/trains/archive/refs/tags/2014_02_14.tar.gz')),
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
    )

    assert len(results) == 12
    assert _basic_data(results[10]) == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1950, 12, 1),
        'current_loan': 300000,
        'money': 280615,
    }


def test_run_experiment_bananas():
    results = run_experiment(
        days=365 + 1,
        seeds=range(2, 3),
        ais=(
            ('trAIns', bananas_file('trAIns', '54524149')),
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
    )

    assert len(results) == 12
    assert _basic_data(results[10]) == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1950, 12, 1),
        'current_loan': 300000,
        'money': 280615,
    }


@pytest.mark.parametrize(
    "savegame_format",
    ("none", "zlib", "lzma"),
)
def test_savegame_formats(savegame_format):
    results = run_experiment(
        days=100,
        seeds=range(2, 3),
        base_openttd_config=f'[misc]\nsavegame_format={savegame_format}\n',
        ais=(
            ('trAIns', local_file('./fixtures/54524149-trAIns-2.1.tar')),
        ),
        openttd_version='13.4',
        opengfx_version='7.1',
    )

    assert len(results) == 3
    assert _basic_data(results[2]) == {
        'openttd_version': '13.4',
        'opengfx_version': '7.1',
        'seed': 2,
        'name': 'trAIns AI',
        'date': date(1950, 4, 1),
        'current_loan': 300000,
        'money': 284815,
    }


def test_savegame_parser():
    with open('./fixtures/warbourne-cross-transport-2029-01-06.sav', 'rb') as f:
        game = parse_savegame(iter(lambda: f.read(65536), b''))

    # There is a little bit of information loss in JSON encoding, e.g. lists and tuples both
    # get converted to lists. But I suspect it's acceptable to ignore.
    # (The dumping and loading here is to "normalise" into the post information loss form)
    with open('./fixtures/warbourne-cross-transport-2029-01-06.json','rb') as f:
        assert json.loads(json.dumps(game))['chunks'] == json.loads(f.read())['chunks']
