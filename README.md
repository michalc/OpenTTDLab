<p align="center">
  <img alt="OpenTTDLab logo" width="256" height="254" src="https://raw.githubusercontent.com/michalc/OpenTTDLab/main/docs/assets/openttdlab-logo.svg">
</p>

<p align="center"><strong>OpenTTDLab</strong> - <em>Run reproducible experiments using OpenTTD</em></p>

<p align="center">
    <a href="https://pypi.org/project/OpenTTDLab/"><img alt="PyPI package" height="20" src="https://img.shields.io/pypi/v/OpenTTDLab?label=PyPI%20package"></a>
    <a href="https://github.com/michalc/OpenTTDLab/actions/workflows/test.yml"><img alt="Test suite" height="20" src="https://img.shields.io/github/actions/workflow/status/michalc/OpenTTDLab/test.yml?label=Test%20suite"></a>
    <a href="https://app.codecov.io/gh/michalc/OpenTTDLab"><img alt="Code coverage" height="20" src="https://img.shields.io/codecov/c/github/michalc/OpenTTDLab?label=Code%20coverage"></a>
</p>

OpenTTDLab is a Python framework for using [OpenTTD](https://github.com/OpenTTD/OpenTTD) to run reproducible experiments and extracting results from them, with as few manual steps as possible.

OpenTTDLab is based on [Patric Stout's OpenTTD Savegame Reader](https://github.com/TrueBrain/OpenTTD-savegame-reader).

---

### Contents

- [Installation](#installation)
- [Running an experiment](#running-an-experiment)
- [Plotting results](#plotting-results)
- [Reproducing an experiment](#reproducing-an-experiment)
- [Compatibility](#compatibility)
- [Licenses and attributions](#licenses-and-attributions)

---

> [!NOTE]
> Work in progress: only some of the features described here will work.

## Installation

OpenTTDLab is distributed via [PyPI](https://pypi.org/project/OpenTTDLab/), and so can usually be installed using pip.

```shell
python -m pip install OpenTTDLab
```

When run on macOS, OpenTTDLab has a dependency that pip does not install: [7-zip](https://www.7-zip.org/). To install 7-zip, first install [Homebrew](https://brew.sh/), and then use Homebrew to install the p7zip package that contains 7-zip.

```shell
brew install p7zip
```

You do not need to separately download or install OpenTTD (or [OpenGFX](https://github.com/OpenTTD/OpenGFX)) in order to use OpenTTDLab. OpenTTDLab itself handles downloading them.


## Running an experiment

The core function of OpenTTD is the `run_experiment` function.

```python
from openttdlab import run_experiment, bananas_file, save_config

# Run the experiment for a range of random seeds
results, metadata, config = run_experiment(
    days=365 * 4 + 1,
    seeds=range(0, 10),
    ais=(
        # 3 ways of using Ais
        # remote_file: takes a url of a .tar.gz AI file, e.g. a GitHub tag
        # local_file: takes a path to a local .tar AI file
        # bananas_file: takes the name and ID from https://bananas.openttd.org/package/ai
        ('trAIns', bananas_file('trAIns', '54524149')),
    ),
)

# Print the results: in-game values that should be exactly reproducible...
print(results)

# ... and metadata: such as number of processes, wallclock time and total CPU time
print(metadata)

# ... and config: to reproduce the results (but not metadata) exactly next time
print(config)

# ... which can be saved to a file and then shared (or archived)
save_config('my-experiment-{experiment_id}.yml', config)
```


## Plotting results

OpenTTD does not require any particular library for plotting results. However, [pandas](https://pandas.pydata.org/) and [Plotly Express](https://plotly.com/python/plotly-express/) are common options for plotting from Python. For example if you have a `results` object from `run_experiment` as in the above example, the following code

```python
import pandas as pd
import plotly.express as px

df = pd.DataFrame(results)
df = df.pivot(index='date', columns='seed', values='money')
fig = px.line(df)
fig.show()
```

should output a plot much like this one.

![A plot of money against time for 10 random seeds](https://raw.githubusercontent.com/michalc/OpenTTDLab/main/docs/assets/example-results.svg)


## Reproducing an experiment

If you have the config from a previous experiment, you can pass it into `run_experiment` to exactly reproduce. If for some reason it cannot be reproduced, it will error.

```python
from openttdlab import run_experiment, load_config

# Load the config from a file...
config = load_config('my-config-a5e95018.yml')

# ... and use it to run the same experiment
results, metadata, config = run_experiment(config=config)

print(results)
```


## Compatibility

- Linux (tested on Ubuntu 20.04), Windows (tested on Windows Server 2019), or macOS (tested on macOS 11)
- Python >= 3.8.0 (tested on 3.8.0 and 3.12.0)


## Licenses and attributions

### TL;DR

OpenTTDLab is licensed under the [GNU General Public License version 2.0](./LICENSE).

### In more detail

OpenTTDLab is based on [Patric Stout's OpenTTD Savegame Reader](https://github.com/TrueBrain/OpenTTD-savegame-reader), licensed under the GNU General Public License version 2.0.

The [OpenTTDLab logo](./docs/assets/openttdlab-logo.svg) is a modified version of the [OpenTTD logo](https://commons.wikimedia.org/wiki/File:Openttdlogo.svg), authored by the [OpenTTD team](https://github.com/OpenTTD/OpenTTD/blob/master/CREDITS.md). The OpenTTD logo is also licensed under the GNU General Public License version 2.0.

The [.gitignore](./.gitignore) file is based on [GitHub's Python .gitignore file](https://github.com/github/gitignore/blob/main/Python.gitignore). This was originally supplied under CC0 1.0 Universal. However, as part of OpenTTDLab it is licensed under GNU General Public License version 2.0.

[trAIns](./fixtures/54524149-trAIns-2.1.tar) is authored by Luis Henrique O. Rios, and licensed under the GNU General Public License version 2.0.

[OpenTTD](https://github.com/OpenTTD/OpenTTD) and [OpenGFX](https://github.com/OpenTTD/OpenGFX) are authored by the [OpenTTD team](https://github.com/OpenTTD/OpenTTD/blob/master/CREDITS.md). Both are licensed under the GNU General Public License version 2.0.
