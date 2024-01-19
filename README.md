# OpenTTDLab • [![PyPI package](https://img.shields.io/pypi/v/OpenTTDLab?label=PyPI%20package)](https://pypi.org/project/OpenTTDLab/) [![Test suite](https://img.shields.io/github/actions/workflow/status/michalc/OpenTTDLab/test.yml?label=Test%20suite)](https://github.com/michalc/OpenTTDLab/actions/workflows/test.yml) [![Code coverage](https://img.shields.io/codecov/c/github/michalc/OpenTTDLab?label=Code%20coverage)](https://app.codecov.io/gh/michalc/OpenTTDLab)

Python framework for running reproducible experiments using OpenTTD. An _experiment_ in OpenTTDLab terms is the combination of:

- Exact version of OpenTTD, any AIs used, and OpenTTDLab itself
- Ranges of values for OpenTTD config settings, command line arguments and random seed
- Granularity of output

This can be configured/extracted for each experiment in either machine or human readable forms, for use in code or publishing respectively.

OpenTTDLab is based on [TrueBrain's OpenTTD Savegame Reader](https://github.com/TrueBrain/OpenTTD-savegame-reader), but it is not affiliated with OpenTTD.

> [!NOTE]
> Work in progress. This README serves as a rough design spec.


## Installation

```shell
python -m pip install OpenTTDLab
```

On macOS, OpenTTDLab requires [7-zip](https://www.7-zip.org/), but this is not installed automatically. To install 7-zip on macOS, first install [Homebrew](https://brew.sh/), and then use Homebrew to install the p7zip package that contains 7-zip.

```shell
brew install p7zip
```


## Running an experiment

The core function of OpenTTD is the `setup_experiment` function.

```python
from openttdlab import setup_experiment, save_config

# If necessary, this will download the latest OpenTTD
run_experiment, get_config = setup_experiment()

# Run the experiment and get results. This may take time
results = run_experiment()
print(results)

# The information needed to reproduce the experiment
config = get_config()
print(config)

# Which can be saved to a file and then shared
save_config('my-config.yml', config)
```


## Reproducing an experiment

If you have the config from a previous experiment, you can pass it into `setup_experiment` to exactly reproduce

```python
from openttdlab import setup_experiment, load_config

# Load the config from file
config = load_config('my-config.yml')

# allow_platform_difference=True will allow experiments from a platform other than the one
# the original experiments were performed on. Otherwise, setup_experiment may error because
# the exact same OpenTTD will not be able to be run on this platform
run_experiment, get_config = setup_experiment(config=config, allow_platform_difference=True)

# Run the experiment and get results
results = run_experiment()
print(results)
```


## API design considerations

- Mutability is avoided
- Impure functions are avoided
- In terms of the user-facing API, keeping it mostly OOP-free, and deliberately focused on key behaviour
- Designed so if type checking were in place and passes, API misuse should be close to impossible
