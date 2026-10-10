"""Test source compilation and rendering through the two public entry points."""

from copy import deepcopy
from dataclasses import replace
from datetime import date
import json

import pytest

from intelligence.services.owned_results import OwnedResultError, compile_owned_results, render_owned_parts
from intelligence.services.research_contract import InformationCutoff
from intelligence.tests.owned_result_support import IMMUNE_KEY, frame_context, source_fixture


def test_actual_d4_false_is_owned_and_preview_cannot_certify_market_uniqueness():
    source = source_fixture()
    _, context = frame_context()
    catalogue = compile_owned_results(source, context)
    ref = catalogue.ref_for(IMMUNE_KEY, "strict_double_red")
    rendered = render_owned_parts([{"result_ref": ref}], catalogue)
    assert rendered.free_blocks == 0
    assert rendered.owned_blocks[0].value is False
    assert "免疫治疗" in rendered.draft
    assert "不满足严格双红" in rendered.draft
    assert next(r["sector_amount"] for r in catalogue.witness["query_basis"]["price_volume_signals"]
                if (r["trade_date"], r["theme_code"], r["sector_ts_code"]) == IMMUNE_KEY) == 349.327
    assert "LM002.LOCAL" not in rendered.draft and "990080.FP" not in rendered.draft
    block = rendered.owned_blocks[0]
    assert rendered.draft[block.start:block.end] == block.text
    assert catalogue.unavailable("unregistered_aggregate")
    scope = render_owned_parts([{"result_ref": catalogue.ref_for((), "scope")}], catalogue)
    assert "4主题、68行" in scope.draft and "24" in scope.draft and "44" in scope.draft
    assert rendered.receipt["free_blocks"] == 0


def test_real_true_signals_keep_their_fact_keys_and_local_rule_role():
    catalogue = compile_owned_results(source_fixture(), frame_context()[1])
    # Original D4: innovation drug, chemical pharmacy, AI medical.
    keys = [("2026-09-30", "LM001.LOCAL", "990098.FP"),
            ("2026-09-30", "LM002.LOCAL", "990005.FP"),
            ("2026-09-30", "LM002.LOCAL", "990105.FP")]
    for key in keys:
        result = render_owned_parts([{"result_ref": catalogue.ref_for(key, "strict_double_red")}], catalogue)
        assert result.owned_blocks[0].value is True
        assert "不满足" not in result.draft and "满足严格双红" in result.draft
    rule = render_owned_parts([{"result_ref": catalogue.ref_for((), "rule_definition")}], catalogue)
    assert "大于 10" in rule.draft and "大于 500 亿" in rule.draft
    assert "本地量价规则" in rule.draft and "market_feature_store" not in rule.draft
    assert rule.owned_blocks[0].role == "rule_definition"
    assert catalogue.unavailable("incomplete_population") and catalogue.unavailable("unsupported_calculation")


@pytest.mark.parametrize("amount,diff,pct,truth", [(500, 11, 1, False), (501, 11, 1, True),
                                                  (501, 10, 1, False), (501, 11, 0, False),
                                                  (None, 11, 1, None)])
def test_strict_boundaries_and_null_are_not_canonical_false(amount, diff, pct, truth):
    source = source_fixture()
    basis = deepcopy(source.query_basis)
    row = next(r for r in basis["price_volume_signals"] if tuple(r[k] for k in
               ("trade_date", "theme_code", "sector_ts_code")) == IMMUNE_KEY)
    row.update(sector_amount=amount, diff_ratio=diff, sector_pct=pct, strict_double_red=truth,
               inputs_complete=amount is not None, missing_inputs=[] if amount is not None else ["sector_amount"])
    catalogue = compile_owned_results(replace(source, query_basis=basis), frame_context()[1])
    rendered = render_owned_parts([{"result_ref": catalogue.ref_for(IMMUNE_KEY, "strict_double_red")}], catalogue)
    assert rendered.owned_blocks[0].value is truth
    assert ("资格未知" in rendered.draft) == (truth is None)
    # Reusing the immutable original ref with a different input snapshot fails.
    old = compile_owned_results(source, frame_context()[1]).ref_for(IMMUNE_KEY, "strict_double_red")
    with pytest.raises(OwnedResultError, match="unknown_result_ref"):
        render_owned_parts([{"result_ref": old}], catalogue)


@pytest.mark.parametrize("mutation,reason", [
    (lambda b: b["price_volume_signals"][0].update(strict_double_red=True), "source_truth_conflict"),
    (lambda b: b["price_volume_signals"][0].update(inputs_complete=False), "source_completeness_conflict"),
    (lambda b: b["price_volume_signals"][0].update(missing_inputs=["sector_pct"]), "source_completeness_conflict"),
    (lambda b: b["price_volume_signals"][0].update(sector_amount=True), "source_numeric_conflict"),
    (lambda b: b["price_volume_signals"][0].update(trade_date="2026-09-29"), "source_key_conflict"),
    (lambda b: b["price_volume_signals"][0].update(sector_ts_code="OTHER"), "source_key_scope_conflict"),
    (lambda b: b["metric_semantics"].update(sector_amount="元"), "source_definition_conflict"),
    (lambda b: b["metric_semantics"].update(strict_double_red=">=500"), "source_definition_conflict"),
    (lambda b: b.update(total_rows=69), "source_scope_conflict"),
])
def test_known_source_conflicts_do_not_render(mutation, reason):
    source = source_fixture()
    basis = deepcopy(source.query_basis)
    mutation(basis)
    with pytest.raises(OwnedResultError, match=reason):
        compile_owned_results(replace(source, query_basis=basis), frame_context()[1])


@pytest.mark.parametrize("part", [{"result_ref": "unknown"}, {"result_ref": "known", "value": False},
                                  {"result_ref": "known", "unit": "元"}, [["nested"]], 0, False])
def test_author_cannot_override_results_or_use_undeclared_refs(part):
    catalogue = compile_owned_results(source_fixture(), frame_context()[1])
    with pytest.raises(OwnedResultError):
        render_owned_parts([part], catalogue)


@pytest.mark.parametrize("mutation", [
    lambda counts: counts.update(price_up=-1),
    lambda counts: counts.update(turnover_up=True),
    lambda counts: counts.update(double_red=0),
    lambda counts: counts.update(distinct_sector_codes=999),
    lambda counts: counts.update(unknown_field=1),
])
def test_invalid_optional_group_counts_cannot_grant_owned_results(mutation):
    source = source_fixture()
    basis = deepcopy(source.query_basis)
    group = basis["groups"][0]
    total = group["total_rows"]
    group["full_group_counts"] = {
        "distinct_sector_codes": total,
        "price_up": total, "price_down": 0, "price_flat": 0, "price_unknown": 0,
        "turnover_up": total, "turnover_down": 0, "turnover_flat": 0, "turnover_unknown": 0,
        "double_red": total, "not_double_red": 0, "double_red_unknown": 0,
    }
    catalogue = compile_owned_results(replace(source, query_basis=basis), frame_context()[1])
    assert catalogue.unavailable("full_group_counts"), "new metadata does not grant new owned text roles"
    mutation(group["full_group_counts"])
    with pytest.raises(OwnedResultError, match="source_scope_conflict"):
        compile_owned_results(replace(source, query_basis=basis), frame_context()[1])


def test_none_keeps_bad_legacy_prose_and_neighbor_free_text_unassessed():
    draft = "免疫治疗同样双红确认。"
    catalogue = compile_owned_results(source_fixture(), frame_context()[1])
    legacy = render_owned_parts(None, catalogue, legacy_draft=draft)
    assert legacy.draft == draft and legacy.receipt is None
    mixed = render_owned_parts([draft, {"result_ref": catalogue.ref_for(IMMUNE_KEY, "strict_double_red")},
                                "上述结果并非如此，持续5天才算确认。"], catalogue)
    assert mixed.free_blocks == 2 and mixed.receipt["qualification"] == "partially_owned"
    assert mixed.draft.startswith(draft + "\n\n")
    assert mixed.owned_blocks[0].start == len(draft) + 2


def test_stability_excludes_runtime_prose_telemetry_and_respects_source_permission():
    source = source_fixture()
    context = frame_context()[1]
    catalogue = compile_owned_results(source, context)
    later = compile_owned_results(replace(source, observation="unrelated appended event", telemetry={"runtime_budget": 99}), context)
    assert catalogue.source_digest == later.source_digest
    assert catalogue.ref_for(IMMUNE_KEY, "strict_double_red") == later.ref_for(IMMUNE_KEY, "strict_double_red")
    with pytest.raises(OwnedResultError, match="source_after_cutoff"):
        compile_owned_results(source, replace(context, information_cutoff=InformationCutoff(date(2026, 9, 29), "requested")))
    with pytest.raises(OwnedResultError, match="source_not_authorized"):
        compile_owned_results(source, replace(context, contract=replace(context.contract, allowed_capabilities=())))


def test_unapproved_cards_and_raw_withheld_metadata_never_grant_refs():
    source = source_fixture()
    context = frame_context()[1]
    assert not compile_owned_results(replace(source, evidence=()), None).blocks
    assert not compile_owned_results(replace(source, trace=replace(source.trace, status="request_error")), context).blocks
    assert not compile_owned_results(replace(source, query_basis={}), context).blocks
    immune = next(c for c in source.evidence if tuple(json.loads(c.independent_key)) == IMMUNE_KEY)
    partial = compile_owned_results(replace(source, evidence=tuple(c for c in source.evidence if c != immune),
                                            telemetry={"temporal_withheld": [immune.to_observation("x")]}), context)
    with pytest.raises(OwnedResultError, match="unknown_result_ref"):
        partial.ref_for(IMMUNE_KEY, "strict_double_red")
    assert len([b for b in partial.blocks if b.role == "strict_double_red"]) == 23
