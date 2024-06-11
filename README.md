<p align="center">
  <img alt="OpenTTDLab logo" width="256" height="254" src="https://raw.githubusercontent.com/michalc/OpenTTDLab/main/docs/assets/openttdlab-logo.svg">
</p>

<p align="center"><strong>OpenTTDLab</strong> - <em>Run reproducible experiments using OpenTTD</em></p>

<p align="center">
    <a href="https://pypi.org/project/OpenTTDLab/"><img alt="PyPI package" height="20" src="https://img.shields.io/pypi/v/OpenTTDLab?label=PyPI%20package"></a>
    <a href="https://github.com/michalc/OpenTTDLab/actions/workflows/test.yml"><img alt="Test suite" height="20" src="https://img.shields.io/github/actions/workflow/status/michalc/OpenTTDLab/test.yml?label=Test%20suite"></a>
    <a href="https://app.codecov.io/gh/michalc/OpenTTDLab"><img alt="Code coverage" height="20" src="https://img.shields.io/codecov/c/github/michalc/OpenTTDLab?label=Code%20coverage"></a>
</p>

OpenTTDLab is a Python framework for using [OpenTTD](https://github.com/OpenTTD/OpenTTD) to run reproducible experiments and extracting results from them, with as few manual steps as possible. OpenTTDLab can also be used to help run regression tests of OpenTTD AIs, parse OpenTTD savegame files, and download content from [BaNaNaS](https://bananas.openttd.org/).

OpenTTDLab is based on [Patric Stout's OpenTTD Savegame Reader](https://github.com/TrueBrain/OpenTTD-savegame-reader).

> [!CAUTION]
> OpenTTDLab currently does not work with OpenTTD 14.0 or later. The latest version of OpenTTD known to work is 13.4.

---

### Contents

- [Features](#features)
- [Installation](#installation)
- [Running experiments](#running-experiments)
- [Plotting results](#plotting-results)
- [Examples](#examples)
- [API](#API)
  - [Core function](#core-function)
  - [Configuring AIs](#configuring-ais)
  - [Configuring AI libraries](#configuring-ai-libraries)
  - [Parsing savegame files](#parsing-savegame-files)
  - [Downloading from BaNaNaS](#downloading-from-bananas)
- [Compatibility](#compatibility)
- [Licenses and attributions](#licenses-and-attributions)

---

## Features

- Allows you to easily run OpenTTD in a headless mode (i.e. without a graphical interface) over a variety of configurations.
- And allows you to do this from Python code - for example from a Jupyter Notebook.
- As is typical from Python code, it is cross platform - allowing to share code snippets between macOS, Windows, and Linux, even though details like how to install and start OpenTTD are different on each platform.
- Downloads (and caches) OpenTTD, OpenGFX, AIs, and AI libraries - no need to download these separately or through OpenTTD's built-in content browser.
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


## Running experiments

The core function of OpenTTD is the `run_experiments` function.

```python
from openttdlab import run_experiments, bananas_ai

# Run experiments...
results = run_experiments(
    openttd_version='13.4',  # ... for a specific versions of OpenTTD
    opengfx_version='7.1',   # ... and a specific versions of OpenGFX
    experiments=(
       {
         # ... for random seeds
         'seed': seed,
         # ... running specific AIs. In this case a single AI, with no
         # parameters, fetching it from https://bananas.openttd.org/package/ai
         'ais': (
             bananas_ai('54524149', 'trAIns', ai_params=()),
         ),
         # ... each for a number of (in game) days
         'days': 365 * 4 + 1,
       }
       for seed in range(0, 10)
    ),
)
```


## Plotting results

OpenTTD does not require any particular library for plotting results. However, [pandas](https://pandas.pydata.org/) and [Plotly Express](https://plotly.com/python/plotly-express/) are common options for plotting from Python. For example if you have a `results` object from `run_experiments` as in the above example, the following code

```python
import pandas as pd
import plotly.express as px

df = pd.DataFrame(
    {
        'seed': row['experiment']['seed'],
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

A few examples are available:

- [A Jupyter notebook of the above example, briefly exploring the performance of trAIns](https://github.com/michalc/OpenTTDLab/blob/main/examples/01-single-ai.ipynb)
- [A Jupyter notebook showing how the performance of OpenTTDLab scales with the number of workers](https://github.com/michalc/OpenTTDLab/blob/main/examples/02-openttdlab-scaling.ipynb)
- [A pytest .py file using OpenTTDLab as a test harness for an OpenTTD AI](https://github.com/michalc/ParameterisedAI/blob/main/test_parameterised_ai.py), run automatically using [a GitHub action workflow](https://github.com/michalc/ParameterisedAI/blob/main/.github/workflows/test.yml)


## API

### Core function

#### `run_experiments(...)`

The core function of OpenTTDLab is the `run_experiments` function, used to run an experiment and return results extracted from the savegame files that OpenTTD produces. It has the following parameters and defaults.

- `experiments=()`

   An iterable of the experiments to run. Each experiment should be a dictionary with the (string) keys:

   - `'ais'`

      The list of AIs to run in this experiment. See the [Fetching AIs](#fetching-ais) section for details on this parameter.

   - `'seed'`

      The integer seed of the random number generator for this experiment.

   - `'days'`

      The integer number of in-game days that this experiment will run for.

   - `openttd_config=''`

      OpenTTD config to run each experiment under. This must be in the [openttd.cfg format](https://wiki.openttd.org/en/Archive/Manual/Settings/Openttd.cfg). This is added to by OpenTTDLab before being passed to OpenTTD.

- `ais_libraries=()`

   The list of AI libraries to have available to AI code. See the [Fetching AI libraries](#fetching-ai-libraries) section for details on this parameter.

- `result_processor=lambda r: (r,)`

   A function that takes a single result row, which is a parsed save game file from an experiment, alongside other metadata describing the experiment, and returns it processed in some way. The function should return an iterable of zero or more rows that will appear in the the return value of `run_experiments`.

   This is typically used to reduce memory usage with high numbers of experiments where only a small amount of data is needed for analysis.

- `final_screenshot_directory=None`

   The directory to save a PNG screenshot of the entire map at the end of each run. Each is named in the format `<seed>.png`, where `<seed>` is the experiment's seed of the random number generator. If `None`, then no screenshots are saved.

   For technical reasons, a window will briefly appear while each screenshot is being saved. This can be avoided when running on Linux if `xvfb-run` is installed and available in the path.

- `max_workers=None`
 
   The maximum number of workers to use to run OpenTTD in parallel. If`None`, then `os.cpu_count()` defined how many workers run.

- `openttd_version=None`

   The version of OpenTTD to use. If `None`, the latest version available at `openttd_base_url` is used.

   > **Caution**
   > OpenTTDLab currently does not work with OpenTTD 14.0 or later. The latest version of OpenTTD known to work is 13.4.

- `opengfx_version=None`

   The version of OpenGFX to use. If `None`, the latest version available at `opengfx_base_url` is used.

- `openttd_base_url='https://cdn.openttd.org/openttd-releases/`

   The base URL used to fetch the list of OpenTTD versions, and OpenTTD binaries.

- `opengfx_base_url='https://cdn.openttd.org/opengfx-releases/`

   The URL used to fetch the list of OpenGFX versions, and OpenGFX binaries.

- `get_http_client=lambda: httpx.Client(transport=httpx.HTTPTransport(retries=3)`

   The HTTP client used to make HTTP requests when fetching OpenTTD, OpenGFX, or AIs. Note that the `bananas_ai` function uses a raw TCP connection in addition to HTTP requests, and so not all outgoing connections use the client specified by this.


### Configuring AIs

The value of the `ais` key of each dictionary in the `experiments` parameter configures which AIs will run, how their code will be located, their names, and what parameters will be passed to each of them when they start. In more detail, the `ais`  parameter must be an iterable of the return value of any of the the following 4 functions.

> [!IMPORTANT]
> The `ai_name` argument passed to each of the following functions must exactly match the name of the corresponding AI as published. If it does not match, the AI will not be started.

> [!IMPORTANT]
> The return value of each of the following is opaque: it should not be used in client code, other than by passing into `run_experiments` as part of the `ais` parameter.

#### `bananas_ai(unique_id, ai_name, ai_params=())`

Defines an AI by the `unique_id` and `ai_name` of an AI published through OpenTTD's content service at https://bananas.openttd.org/package/ai. This allows you to quickly run OpenTTDLab with a published AI. The `ai_params` parameter is an optional parameter of an iterable of `(key, value)` parameters passed to the AI on startup.

The `unique_id` is sometimes surfaced as the "Content Id", but it should not include its `ai/` prefix.

#### `local_folder(folder_path, ai_name, ai_params=()))`

Defines an AI by the `folder_path` to a local folder that contains the AI code of an AI with name `ai_name`. The `ai_params` parameter is an optional parameter of an iterable of `(key, value)` parameters passed to the AI on startup.

#### `local_file(path, ai_name, ai_params=())`

Defines an AI by the local path to a .tar AI file that contains the AI code. The `ai_params` parameter is an optional parameter of an iterable of `(key, value)` parameters passed to the AI on startup.

#### `remote_file(url, ai_name, ai_params=())`

Fetches the AI by the URL of a tar.gz file that contains the AI code. For example, a specific GitHub tag of a repository that contains its code. The `ai_params` parameter is an optional parameter of an iterable of `(key, value)` parameters passed to the AI on startup.


### Configuring AI libraries

The `ai_libraries` parameter of `run_experiments` ensures that AI libraries are available to the AIs running. In more detail, the `ais_libraries` parameter must be an iterable, where each item the the return value of the `bananas_ai_library` function described below.

Note that for AIs specified by `bananas_ai` OpenTTDLab automatically downloads all of their AI library dependencies without them having to be specified through the `ai_libraries` parameter. This includes all transitive AI library dependencies - AI libraries needed by AI libraries needed by AIs, and so on.

Similarly for AI libraries specified by `bananas_ai_library` - OpenTTDLab automatically downloads of their AI library dependencies.

#### `bananas_ai_library(unique_id, ai_library_name)`

Fetches the AI library defined by `unique_id` and `ai_name` of a library published through OpenTTD's content service at https://bananas.openttd.org/package/ai-library.

The `unique_id` is sometimes surfaced as the "Content Id", but it should not include its `ai-library/` prefix.


### Parsing savegame files

#### `parse_savegame(chunks: Iterable[bytes])`

Under the hood the `run_experiments` handles the generation and parsing of savegame files, but if you have your own savegame files generated separately, the `parse_savegame` function is exposed that can extract data from them.

It takes an iterable of `bytes` instances of a savegame file, and returns a nested dictionary of parsed data.

```python
from openttdlab import parse_savegame

with open('my.sav') as f:
   parsed_savegame = parse_savegame(iter(lambda: f.read(65536), b''))
```


### Downloading from BaNaNaS

> [!IMPORTANT]
> Please do not use this to try to download all content from BaNaNaS. See this [discussion about writing a client for BaNaNaS](https://github.com/OpenTTD/OpenTTD/discussions/11863#discussioncomment-8201505) for more details.

#### `download_from_bananas(content_id: str)`

This function is essentially a Python BaNaNaS client for downloading the latest version of content from [BaNaNaS](https://bananas.openttd.org/). Given a content id, it returns an iterable of that content and all of its direct and transitive dependencies.

```python
from openttdlab import download_from_bananas

with download_from_bananas('ai/41444d4c') as files:
    for content_id, filename, md5_partial, get_data in files:
        with get_data() as chunks:
            with open(filename, 'wb') as f:
                for chunk in chunks:
                    f.write(chunk)
```

Each `chunks` iterable are the binary chunks of the non-compressed `.tar` file of the content. Also, under the hood `download_from_bananas` transparently caches content where possible. This is the main reason for using context managers as in the above example - they allow for robust cleanup of resources and caching of data once the data has been iterated over.

Note that the function `run_experiments` that uses `bananas_ai` or `bananas_ai_library` will handle automatically downloading from BaNaNaS, so this function is usually only useful if you would like to run experiments without using the `bananas_*` functions, or report on the filename (which includes the version of each piece of content) or the (partial) MD5 sum of the file.


## Compatibility

- OpenTTD versions between 12.0 and 13.4 (OpenTTD >= 14.0 is not currently supported. See this [discussion on the changes in OpenTTD 14.0](https://github.com/OpenTTD/OpenTTD/discussions/12496).)
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
