import json
from datetime import date

from openttdlab import Savegame, run_experiment, local_file, remote_file, save_config, load_config


def test_run_experiment_local():
    results, config = run_experiment(
        days=365 * 5 + 1,
        seeds=range(2, 4),
        ais=(
            ('trAIns', local_file('./fixtures/54524149-trAIns-2.1.tar')),
        ),
    )

    assert len(results) == 118
    assert results[58] == {
        'seed': 2,
        'player': 'trAIns AI',
        'date': date(1954, 12, 1),
        'loan': 110000,
        'money': 6546,
    }
    assert results[117] == {
        'seed': 3,
        'player': 'trAIns AI',
        'date': date(1954, 12, 1),
        'loan': 300000,
        'money': 672573,
    }


def test_run_experiment_remote():
    results, config = run_experiment(
        days=365 + 1,
        seeds=range(2, 3),
        ais=(
            ('trAIns', remote_file('https://github.com/lhrios/trains/archive/refs/tags/2014_02_14.tar.gz')),
        ),
    )

    assert len(results) == 12
    assert results[10] == {
        'seed': 2,
        'player': 'trAIns AI',
        'date': date(1950, 12, 1),
        'loan': 300000,
        'money': 280615,
    }


def test_savegame_parser():
    with open('./fixtures/warbourne-cross-transport-2029-01-06.sav', 'rb') as f:
        game = Savegame()
        game.read(f)

    # There is a little bit of information loss in JSON encoding, e.g. lists and tuples both
    # get converted to lists. But I suspect it's acceptable to ignore.
    # (The dumping and loading here is to "normalise" into the post information loss form)
    with open('./fixtures/warbourne-cross-transport-2029-01-06-items.json','rb') as f:
        assert json.loads(json.dumps(game.items)) == json.loads(f.read())

    with open('./fixtures/warbourne-cross-transport-2029-01-06-tables.json','rb') as f:
        assert json.loads(json.dumps(game.tables)) == json.loads(f.read())


def test_save_config():
    save_config()


def test_load_config():
    load_config()
