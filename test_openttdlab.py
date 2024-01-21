from openttdlab import run_experiment, save_config, load_config


def test_run_experiment():
    results, config = run_experiment(
        days=365 * 5 + 1,
        ais=(
            ('trAIns', './fixtures/54524149-trAIns-2.1.tar'),
        ),
    )

    assert len(results) == 51
    assert results[0]['PLYR']['0']['name'] == 'trAIns AI'


def test_save_config():
    save_config()


def test_load_config():
    load_config()
