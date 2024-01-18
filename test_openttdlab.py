from openttdlab import setup_experiment, save_config, load_config


def test_setup_experiment():
	run_experiment, get_config = setup_experiment()

	run_experiment()
	get_config()


def test_save_config():
	save_config()


def test_load_config():
	load_config()
