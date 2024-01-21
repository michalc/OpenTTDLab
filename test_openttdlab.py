from datetime import date

from openttdlab import run_experiment, local_file, save_config, load_config


def test_run_experiment():
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


def test_save_config():
    save_config()


def test_load_config():
    load_config()
