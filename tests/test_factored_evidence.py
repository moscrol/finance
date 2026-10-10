"""Reversible representation tests; no evidence selection or semantic grading."""
from __future__ import annotations

from copy import deepcopy
import random

import pytest

from intelligence.eval.factored_evidence import canonical, factor_packet, restore_packet, view_receipt


def packet_fixture():
    rows = [
        {"title": "same source date", "source": "official fixture", "source_date": "2026-09-22",
         "freshness": "current", "supports": [], "contradicts": ["counterevidence retained"],
         "content_hash": f"hash-{i}", "detail": f"row {i}: 0 is not NULL; a\u2028b\n  " + "value " * 30}
        for i in range(3)
    ]
    prose = "qualified preview only; " + " | ".join(row["detail"] for row in rows) + " END scope remains limited"
    return {"question": "Do not infer a full population.", "information_cutoff": "2026-09-22", "observations": [{
        "id": "O1", "tool": "fixture", "arguments": {"limit": 3},
        "result": {"status": "partial", "gaps": ["missing rows"], "query_basis": {"total": 9, "shown": 3},
                   "observation": prose, "evidence": rows, "unknown_new_field": {"must_keep": [0, None, False, ""]}},
    }]}


def test_factoring_preserves_all_text_metadata_and_unknown_fields():
    packet = packet_fixture()
    before = deepcopy(packet)
    view = factor_packet(packet)
    result = view["observations"][0]["result"]
    assert result["evidence_common"]["contradicts"] == ["counterevidence retained"]
    assert "source" not in result["evidence"][0]
    assert any(isinstance(part, dict) for part in result["observation_parts"])
    assert canonical(restore_packet(view)) == canonical(packet)
    assert packet == before
    receipt = view_receipt(packet, view)
    assert receipt["original_canonical_sha256"] == receipt["restored_canonical_sha256"]
    assert receipt["view_bytes"] < receipt["original_bytes"]
    assert receipt["content_quality"] == "UNREVIEWED"


@pytest.mark.parametrize("change", ["shared", "detail", "scope", "gap", "new_field"])
def test_any_changed_fact_or_qualifier_fails_roundtrip_receipt(change):
    packet = packet_fixture()
    view = factor_packet(packet)
    result = view["observations"][0]["result"]
    if change == "shared":
        result["evidence_common"]["source_date"] = "2099-01-01"
    elif change == "detail":
        result["evidence"][0]["detail"] += " changed"
    elif change == "scope":
        result["query_basis"]["total"] = 3
    elif change == "gap":
        result["gaps"] = []
    else:
        del result["unknown_new_field"]
    with pytest.raises(ValueError, match="changed"):
        view_receipt(packet, view)


@pytest.mark.parametrize("index", [-1, True, "0", 999])
def test_invalid_reference_cannot_silently_select_a_different_row(index):
    view = factor_packet(packet_fixture())
    view["observations"][0]["result"]["observation_parts"] = [{"evidence_detail": index}]
    with pytest.raises(ValueError):
        restore_packet(view)


def test_overlapping_and_repeated_literals_remain_exact():
    packet = packet_fixture()
    rows = packet["observations"][0]["result"]["evidence"]
    rows[0]["detail"] = "X" * 100
    rows[1]["detail"] = "prefix " + rows[0]["detail"] + " suffix"
    packet["observations"][0]["result"]["observation"] = rows[1]["detail"] * 2 + "different  spaces"
    assert restore_packet(factor_packet(packet)) == packet


def test_equal_python_values_with_different_json_types_are_not_shared():
    packet = packet_fixture()
    rows = packet["observations"][0]["result"]["evidence"]
    for row, value in zip(rows, (1, True, 1.0)):
        row["source"] = value
    view = factor_packet(packet)
    assert "source" not in view["observations"][0]["result"]["evidence_common"]
    assert canonical(restore_packet(view)) == canonical(packet)


@pytest.mark.parametrize("field", ["evidence_common", "observation_parts", "telemetry", "trace"])
def test_private_or_reserved_observation_keys_are_rejected(field):
    packet = packet_fixture()
    packet["observations"][0]["result"][field] = "do not silently drop this"
    with pytest.raises(ValueError):
        factor_packet(packet)


def test_colliding_shared_fields_and_two_prose_forms_are_rejected():
    view = factor_packet(packet_fixture())
    bad = deepcopy(view)
    bad["observations"][0]["result"]["evidence"][0]["source"] = "override"
    with pytest.raises(ValueError):
        restore_packet(bad)
    view["observations"][0]["result"]["observation"] = "competing prose"
    with pytest.raises(ValueError):
        restore_packet(view)


def test_missing_empty_and_nonstandard_rows_survive_without_invented_defaults():
    for evidence in ([], [None], [{"detail": "short"}], "unexpected but retained"):
        packet = packet_fixture()
        packet["observations"][0]["result"]["evidence"] = evidence
        assert restore_packet(factor_packet(packet)) == packet
    packet = packet_fixture()
    del packet["observations"][0]["result"]["evidence"]
    assert restore_packet(factor_packet(packet)) == packet


def test_many_deterministic_layouts_roundtrip_without_whitespace_normalization():
    randomizer = random.Random(20261010)
    for _ in range(30):
        packet = packet_fixture()
        rows = packet["observations"][0]["result"]["evidence"]
        for row in rows:
            row["detail"] += randomizer.choice([" 1 2 ", "12", "\n", "\t", "\u2028"])
            row["extra"] = randomizer.choice([0, False, None, [], {"n": 1}])
        packet["observations"][0]["result"]["observation"] = "\n".join(row["detail"] for row in reversed(rows))
        assert canonical(restore_packet(factor_packet(packet))) == canonical(packet)
