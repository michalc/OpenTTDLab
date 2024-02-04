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

- [Features](#features)
- [Installation](#installation)
- [Running an experiment](#running-an-experiment)
- [Plotting results](#plotting-results)
- [API](#API)
- [Compatibility](#compatibility)
- [Licenses and attributions](#licenses-and-attributions)

---

## Features

- Allows you to easily run OpenTTD in a headless mode (i.e. without a graphical interface) over a variety of configurations.
- And allows you to do this from Python code - for example from a Jupyter Notebook.
- As is typical from Python code, it is cross platform - allowing to share code snippets between macOS, Windows, and Linux, even though details like how to install and start OpenTTD are different on each platform.
- Downloads (and caches) OpenTTD, OpenGFX, and AIs - no need to download these separately or through OpenTTD's built-in content browser.
- Transparently parallelises runs of OpenTTD, by default up to the number of CPUs.
- Results are extracted from OpenTTD savegames as plain Python dictionaries and lists - reasonably convenient for importing into tools such as pandas for analysis or visualisation.


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
from openttdlab import run_experiment, bananas_file

# Run experiments...
results = run_experiment(
    openttd_version='13.4',  # ... for a specific versions of OpenTTD
    opengfx_version='7.1',   # ... and a specific versions of OpenGFX
    seeds=range(0, 10),      # ... for a range of random seeds
    days=365 * 4 + 1,        # ... each for a number of (in game) days
    ais=(
        # ... running specific AIs. In this case, fetching AI code from
        #     https://bananas.openttd.org/package/ai
        ('trAIns', bananas_file('trAIns', '54524149')),
    ),
)

# Print the results
print(results)
```


## Plotting results

OpenTTD does not require any particular library for plotting results. However, [pandas](https://pandas.pydata.org/) and [Plotly Express](https://plotly.com/python/plotly-express/) are common options for plotting from Python. For example if you have a `results` object from `run_experiment` as in the above example, the following code

```python
import pandas as pd
import plotly.express as px

df = pd.DataFrame(
    {
        'seed': row['seed'],
        'date': row['date'],
        'money': row['chunks']['PLYR']['0']['money'],
    }
    for row in results
)
df = df.pivot(index='date', columns='seed', values='money')
fig = px.line(df)
fig.show()
```

should output a plot much like this one.

![A plot of money against time for 10 random seeds](https://raw.githubusercontent.com/michalc/OpenTTDLab/main/docs/assets/example-results.svg)


## API

### Fetching AIs

The `ais` parameter of `run_experiment` configures which AIs will run, and how their code will be located. Specifically, the `ais`  parameter must be an iterable of `(name, ai)` pairs, where `name` is the name of the AI, and `ai` must be the return value of any of the following 3 functions.

- `bananas_file(name, id)`

   Defines an AI by the `name` and `id` of an AI published through OpenTTD's content service at https://bananas.openttd.org/package/ai. This allows you to quickly run OpenTTD with a published AI.

- `local_file(path)`

  Defines an AI by the local path to a .tar AI file that contains the AI code.

- `remote_file(url)`

  Fetches the AI by the URL of a tar.gz file that contains the AI code. For example, a specific GitHub tag of a repository that contains its code.

The return value of each is opaque: it should not be used in client code, other than by passing into `run_experiment` as its `ais` parameter.


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
