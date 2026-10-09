"""Model wire encoding preserves the complete JSON-compatible calculation object."""
from __future__ import annotations

import json
from itertools import product

import pytest
import yaml

from intelligence.services.market_regime_analogs import model_readout_block


@pytest.mark.parametrize("value", [
    None, True, False, 0, -1, 1.25, 1e-20, -0.0, "", "null", "true", "False",
    "2025-04-10", "001", "1e-9", "a,b", "a: b", "[a,b]", "{key: value}",
    "# note", "*alias", "!tag", "quoted \"value\"", "line\nnext", "\t", "source\\path",
])
def test_model_readout_keeps_json_types_values_and_nested_rows(value):
    payload = {"schema": "readout", "rows": [[value, None, False], [True, value, 0]],
               "source": {str(value): value}, "empty": [], "mapping": {}}
    block = model_readout_block(payload)
    parsed = yaml.safe_load(block.removeprefix("```yaml\n").removesuffix("\n```"))
    # Python equality would accept False == 0; canonical JSON must not.
    assert json.dumps(parsed, sort_keys=True) == json.dumps(payload, sort_keys=True)


def test_adjacent_flow_scalars_and_collections_are_lossless():
    values = [None, False, True, 0, 0.5, "null", "yes", "12:30", "a,b", [], {}, [None]]
    payload = {"rows": [list(row) for row in product(values, repeat=2)]}
    block = model_readout_block(payload)
    parsed = yaml.safe_load(block.removeprefix("```yaml\n").removesuffix("\n```"))
    assert json.dumps(parsed, sort_keys=True) == json.dumps(payload, sort_keys=True)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_values_are_not_rendered_as_model_evidence(value):
    with pytest.raises(ValueError):
        model_readout_block({"rows": [[value]]})
