# OpenTTDLab

Python framework for running reproducible experiments using OpenTTD.

Based on [TrueBrain's OpenTTD Savegame Reader](https://github.com/TrueBrain/OpenTTD-savegame-reader).

> Work in progress. This README serves as a rough design spec.


## Installation

```shell
pip install OpenTTDLab
```


## Usage


```python
from openttdlab import experiment

results, reproducibility = experiment()

# The actual results
print(results)

# The information needed to reproduce the experiment
print(reproducibility)
```
