from openttdlab import run_experiment, save_config, load_config


def test_run_experiment():
    results, config = run_experiment()

    assert results


def test_save_config():
    save_config()


def test_load_config():
    load_config()
