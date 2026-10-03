"""Keep inherited harness mutation probes executable after source integration.

These static checks catch stale/ambiguous anchors early. They do not substitute
for running the mutated behavior red and the restored behavior green.
"""
import ast
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEFINITION_NAMES = (
    "harness_plan_ownership",
    "request_interpretation",
    "output_provenance",
    "expression_advisory",
)


def _definitions():
    for name in DEFINITION_NAMES:
        path = ROOT / "scripts" / "review_probes" / f"{name}_mutations.json"
        for mutation in json.loads(path.read_text(encoding="utf-8")):
            yield pytest.param(mutation, id=f"{name}:{mutation['id']}")


@pytest.mark.parametrize("mutation", tuple(_definitions()))
def test_harness_mutation_has_unique_current_anchor_and_compiles(mutation):
    path = (ROOT / mutation["path"]).resolve()
    assert path.is_relative_to(ROOT)
    source = path.read_text(encoding="utf-8")
    assert source.count(mutation["old"]) == 1
    assert mutation["new"] != mutation["old"]
    changed = source.replace(mutation["old"], mutation["new"], 1)
    ast.parse(changed, filename=mutation["path"])
    assert mutation["targets"]
