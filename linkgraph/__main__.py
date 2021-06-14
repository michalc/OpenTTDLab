"""
Script to read in the JSON from savegame_reader, and export the linkgraph
only. Linkgraphs are stored in an efficient way on disk, which makes them
slightly less usable for automation. This script is meant as inspiration how
to deal with the linkgraph to get a proper linkgraph out of it.

On the root is a list of cargos. For each cargo there is [from][to] containing
all the edges. "from" and "to" are stationIDs.
"""

import json
import sys

from collections import defaultdict

result = defaultdict(lambda: defaultdict(lambda: dict()))

data = json.load(sys.stdin)

for lgrp in data["chunks"]["LGRP"].values():
    i = -1
    nodes = {}
    edges = {}

    for node in lgrp["nodes"]:
        i += 1
        nodes[i] = node["station"]

        to = i
        for edge in node["edges"]:
            edges[(i, to)] = (edge["capacity"], edge["usage"])
            to = edge["next_edge"]

    for (i, to), (c, u) in edges.items():
        if c == 0:
            continue

        i = nodes[i]
        to = nodes[to]

        result[lgrp["cargo"]][i][to] = {"capacity": c, "usage": u}

print(json.dumps(result))
