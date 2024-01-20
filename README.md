<p align="center">
  <img alt="OpenTTDLab logo" width="256" height="254" src="https://raw.githubusercontent.com/michalc/OpenTTDLab/main/docs/assets/openttdlab-logo.svg">
</p>

<p align="center"><strong>OpenTTDLab</strong> - <em>Run reproducible experiments using OpenTTD</em></p>

<p align="center">
    <a href="https://pypi.org/project/OpenTTDLab/"><img alt="PyPI package" height="20" src="https://img.shields.io/pypi/v/OpenTTDLab?label=PyPI%20package"></a>
    <a href="https://github.com/michalc/OpenTTDLab/actions/workflows/test.yml"><img alt="Test suite" height="20" src="https://img.shields.io/github/actions/workflow/status/michalc/OpenTTDLab/test.yml?label=Test%20suite"></a>
    <a href="https://app.codecov.io/gh/michalc/OpenTTDLab"><img alt="Code coverage" height="20" src="https://img.shields.io/codecov/c/github/michalc/OpenTTDLab?label=Code%20coverage"></a>
</p>

---

OpenTTD is a Python framework for running reproducible experiments using OpenTTD, and extracting results from them. An _experiment_ in OpenTTDLab terms is the combination of:

- Exact version of OpenTTD, any AIs used, and OpenTTDLab itself
- Ranges of values for OpenTTD config settings, command line arguments and random seed

This can be configured/extracted for each experiment in either machine or human readable forms, for use in code or publishing respectively.

OpenTTDLab is based on [TrueBrain's OpenTTD Savegame Reader](https://github.com/TrueBrain/OpenTTD-savegame-reader), but it is not affiliated with OpenTTD.

> [!NOTE]
> Work in progress. This README serves as a rough design spec.


## Installation

OpenTTDLab is distributed via [PyPI](https://pypi.org/project/OpenTTDLab/), and so can usually be installed using pip.

```shell
python -m pip install OpenTTDLab
```

OenTTDLab itself requires additional binaries:

1. unzip
1. (Linux only) tar
2. (macOS only) 7-zip

The only one of these not likely to already be installed is [7-zip](https://www.7-zip.org/). To install 7-zip on macOS, first install [Homebrew](https://brew.sh/), and then use Homebrew to install the p7zip package that contains 7-zip.

```shell
brew install p7zip
```

You do not need to separately download or install OpenTTD (or [OpenGFX](https://github.com/OpenTTD/OpenGFX)) in order to use OpenTTDLab. OpenTTDLab handles downloading them, which is the reason OpenTTDLab requires the binaries mentioned above.


## Running an experiment

The core function of OpenTTD is the `run_experiment` function.

```python
from openttdlab import run_experiment, save_config

# Run the experiment and get results
results, config = run_experiment()

# Print the results...
print(results)

# ... and config
print(config)

# ... which can be saved to a file and then shared (or archived)
save_config('my-experiment-{experiment_id}.yml', config)
```


## Reproducing an experiment

If you have the config from a previous experiment, you can pass it into `run_experiment` to exactly reproduce. If for some reason it cannot be reproduced, it will error.

```python
from openttdlab import run_experiment, load_config

# Load the config from a file...
config = load_config('my-config-a5e95018.yml')

# ... and use it to run the same experiment
results, config = run_experiment(config=config)

print(results)
```
