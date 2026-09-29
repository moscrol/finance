"""The rejected excerpt experiment must not reactivate through a stale flag."""
from copy import deepcopy
import json

import pytest

from intelligence.services.episode_protocol import finish_json_schema, validate_episode_finish
from intelligence.services.material_answer_authoring import material_author_payload
from intelligence.tests.test_material_answer_authoring import compact_finish, history_setup, legacy_finish


@pytest.mark.parametrize("flag", [None, "0", "1"])
def test_retired_excerpt_flag_cannot_change_author_view_or_schema(monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("FINANCE_MATERIAL_SOURCE_EXCERPTS", raising=False)
    else:
        monkeypatch.setenv("FINANCE_MATERIAL_SOURCE_EXCERPTS", flag)
    _, context = history_setup()
    author = material_author_payload(context.contract)
    assert author["finish_format"]["format"] == "material_claims_v1"
    assert json.loads(author["finish_format"]["wire_template"])["format"] == "material_claims_v1"
    assert all("text" in source and "excerpts" not in source for source in author["sources"])
    assert finish_json_schema(context.contract)["properties"]["format"]["enum"] == ["material_claims_v1"]


@pytest.mark.parametrize("flag", ["0", "1"])
def test_retired_v2_finish_is_rejected_without_mutating_input(monkeypatch, flag):
    monkeypatch.setenv("FINANCE_MATERIAL_SOURCE_EXCERPTS", flag)
    _, context = history_setup()
    value = compact_finish()
    value["format"] = "material_claims_v2"
    value["answers"][0]["claims"][0]["sources"] = ["H1.X1"]
    value["answers"][1]["claims"][0]["sources"] = ["M1.X1"]
    saved = deepcopy(value)
    with pytest.raises(ValueError) as error:
        validate_episode_finish(value, context=context, evidence=())
    assert error.value.code == "bad_claim_binding"
    assert value == saved


def test_retirement_preserves_v1_and_legacy_source_identity(monkeypatch):
    monkeypatch.setenv("FINANCE_MATERIAL_SOURCE_EXCERPTS", "1")
    _, context = history_setup()
    parsed = validate_episode_finish(compact_finish(), context=context, evidence=())
    assert parsed == validate_episode_finish(legacy_finish(context), context=context, evidence=())
    assert parsed.bindings[0].claims[0].basis == "assistant_judgment"
    assert not any(binding.evidence_hashes for binding in parsed.bindings)
    assert not context.contract.allowed_capabilities
