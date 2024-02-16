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
- [Examples](#examples)
- [API](#API)
- [Compatibility](#compatibility)
- [Licenses and attributions](#licenses-and-attributions)

---

## Features

- Allows you to easily run OpenTTD in a headless mode (i.e. without a graphical interface) over a variety of configurations.
- And allows you to do this from Python code - for example from a Jupyter Notebook.
- As is typical from Python code, it is cross platform - allowing to share code snippets between macOS, Windows, and Linux, even though details like how to install and start OpenTTD are different on each platform.
- Downloads (and caches) OpenTTD, OpenGFX, and AIs - no need to download these separately or through OpenTTD's built-in content browser.
- Transparently parallelises runs of OpenTTD, by default up to the number of CPUs. (Although with [fairly poor scaling properties](https://github.com/michalc/OpenTTDLab/blob/main/examples/02-openttdlab-scaling.ipynb).)
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
        # ... running specific AIs. In this case a single AI, with no
        # parameters, fetching it from https://bananas.openttd.org/package/ai
        bananas_file('54524149', 'trAIns', ai_params=()),
    ),
)
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


## Examples

A notebook of the above example and an example measuring the performance of OpenTTDLab are in the [examples](https://github.com/michalc/OpenTTDLab/tree/main/examples) folder.


## API

### Running experiments

#### `run_experiment(...)`

The core function of OpenTTDLab is the `run_experiment` function, used to run an experiment and return results extracted from the savegame files that OpenTTD produces. It has the following parameters and defaults.

- `ais=()`

   The list of AIs to run. See the [Fetching AIs](#fetching-ais) section for details on this parameter.

- `seeds=(1,)`

   An iterable of integers, where each is used to seed the random number generator in a run of OpenTTD.

- `days=365 * 4 + 1`

   The number of in-game days that each run of OpenTTD should last.

- `base_openttd_config=''`

   OpenTTD config to run each experiment under. This must be in the [openttd.cfg format](https://wiki.openttd.org/en/Archive/Manual/Settings/Openttd.cfg). This is added to by OpenTTDLab before being passed to OpenTTD.

- `max_workers=None`
 
   The maximum number of workers to use to run OpenTTD in parallel. If`None`, then `os.cpu_count()` defined how many workers run.

- `openttd_version=None`

   The version of OpenTTD to use. If `None`, the latest version available at `openttd_base_url` is used.

- `opengfx_version=None`

   The version of OpenGFX to use. If `None`, the latest version available at `opengfx_base_url` is used.

- `openttd_base_url='https://cdn.openttd.org/openttd-releases/`

   The base URL used to fetch the list of OpenTTD versions, and OpenTTD binaries.

- `opengfx_base_url='https://cdn.openttd.org/opengfx-releases/`

   The URL used to fetch the list of OpenGFX versions, and OpenGFX binaries.

- `get_http_client=lambda: httpx.Client(transport=httpx.HTTPTransport(retries=3)`

   The HTTP client used to make HTTP requests when fetching OpenTTD, OpenGFX, or AIs. Note that the `bananas_file` function uses a raw TCP connection in addition to HTTP requests, and so not all outgoing connections use the client specified by this.


### Fetching AIs

The `ais` parameter of `run_experiment` configures which AIs will run, how their code will be located, their names, and what parameters will be passed to each of them when they start. In more detail, the `ais`  parameter must be an iterable of the return value of any of the the following 4 functions.

> [!IMPORTANT]
> The `ai_name` argument passed to each of the following functions must exactly match the name of the corresponding AI as published. If it does not match, the AI will not be started.

> [!IMPORTANT]
> The return value of each of the following is opaque: it should not be used in client code, other than by passing into `run_experiment` as part of the `ais` parameter.

#### `bananas_file(unique_id, ai_name, ai_params=())`

Defines an AI by the `unique_id` and `ai_name` of an AI published through OpenTTD's content service at https://bananas.openttd.org/package/ai. This allows you to quickly run OpenTTDLab with a published AI. The `ai_params` parameter is an optional parameter of an iterable of `(key, value)` parameters passed to the AI on startup.

The `unique_id` is sometimes surfaced as the "Content Id", but it should not include its `ai/` prefix.

#### `local_folder(folder_path, ai_name, ai_params=()))`

Defines an AI by the `folder_path` to a local folder that contains the AI code of an AI with name `ai_name`. The `ai_params` parameter is an optional parameter of an iterable of `(key, value)` parameters passed to the AI on startup.

#### `local_file(path, ai_name, ai_params=())`

Defines an AI by the local path to a .tar AI file that contains the AI code. The `ai_params` parameter is an optional parameter of an iterable of `(key, value)` parameters passed to the AI on startup.

#### `remote_file(url, ai_name, ai_params=())`

Fetches the AI by the URL of a tar.gz file that contains the AI code. For example, a specific GitHub tag of a repository that contains its code. The `ai_params` parameter is an optional parameter of an iterable of `(key, value)` parameters passed to the AI on startup.


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
