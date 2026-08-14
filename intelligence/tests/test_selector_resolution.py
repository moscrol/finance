from __future__ import annotations

import copy
import json

import pytest

from intelligence.eval.selector_resolution import (
    CONTROLLED_INTENTS,
    SelectorSelection,
    analyze_selector_results,
    canonical_payload_hash,
    run_probe,
)


def _selection(
    companies: list[str],
    *,
    mode: str = "llm",
    hallucinated: int = 0,
    backfilled: int = 0,
) -> SelectorSelection:
    return SelectorSelection(
        question="fixture",
        companies=tuple(companies),
        telemetry={
            "mode": mode,
            "reason": "" if mode == "llm" else "provider_unavailable:timeout",
            "hallucinated": hallucinated,
            "backfilled": backfilled,
            "llm_selected": max(0, len(companies) - backfilled),
        },
    )


def test_pairwise_jaccard_top3_change_and_rank_overlap() -> None:
    report = analyze_selector_results(
        {
            "beneficiary": _selection(["宁德时代", "赣锋锂业", "当升科技"]),
            "expansion": _selection(["当升科技", "宁德时代", "亿纬锂能"]),
        }
    )

    pair = report.pairs[0]
    assert pair.jaccard == pytest.approx(0.5)
    assert pair.top3_changed == 3
    assert 0.0 <= pair.rank_overlap <= 1.0
    assert report.outcome == "discriminative"
    assert report.unique_ordered_lists == 2
    assert report.union_size == 4


def test_identical_lists_have_full_rank_overlap_and_are_indistinguishable() -> None:
    report = analyze_selector_results(
        {
            "a": _selection(["甲", "乙", "丙"]),
            "b": _selection(["甲", "乙", "丙"]),
        }
    )

    assert report.outcome == "indistinguishable"
    assert report.pairs[0].jaccard == 1.0
    assert report.pairs[0].rank_overlap == pytest.approx(1.0)
    assert report.pairs[0].top3_changed == 0


@pytest.mark.parametrize(
    "selection",
    [
        _selection(["甲"], mode="deterministic"),
        _selection(["甲"], hallucinated=1),
    ],
    ids=["provider-fallback", "hallucinated-name"],
)
def test_fallback_or_hallucination_makes_experiment_unjudgeable(
    selection: SelectorSelection,
) -> None:
    report = analyze_selector_results({"a": selection, "b": _selection(["乙"])})

    assert report.outcome == "unjudgeable"


def test_backfill_is_reported_but_does_not_fake_provider_fallback() -> None:
    report = analyze_selector_results(
        {
            "a": _selection(["甲", "乙"], backfilled=1),
            "b": _selection(["乙", "甲"], backfilled=1),
        }
    )

    assert report.outcome == "discriminative"
    assert report.telemetry_totals["backfilled"] == 2


class _FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def get_exposure_matches(self, term: str, limit: int = 12) -> dict:
        self.calls.append((term, limit))
        items = [
            {
                "company": f"公司{index:02d}",
                "concept": term,
                "strength": "core",
                "confidence": "high",
                "role": f"角色{index}",
                "score": 20,
            }
            for index in range(16)
        ]
        return {
            "found": True,
            "term": term,
            "items": items,
            "total_matched": len(items),
            "truncated": False,
            "evidence_coverage": {
                "indexed": True,
                "by_company": {f"公司{index:02d}": 100 - index for index in range(16)},
            },
            "warnings": [],
            "errors": [],
        }


def test_probe_freezes_one_pool_and_keeps_coverage_out_of_selector_prompt() -> None:
    adapter = _FakeAdapter()
    calls: list[list[dict]] = []

    def complete(messages, **kwargs):
        del kwargs
        calls.append(messages)
        offset = len(calls)
        return (
            json.dumps(
                {
                    "companies": [
                        f"公司{(offset + index) % 16:02d}" for index in range(12)
                    ]
                },
                ensure_ascii=False,
            ),
            type("Provider", (), {"name": "fixture-provider", "model": "fixture-model"})(),
            "",
        )

    artifact = run_probe(
        concept="固态电池",
        adapter=adapter,
        complete=complete,
        limit=12,
        model="fixture-model",
        code_revision="abc123",
        created_at="2026-08-01T00:00:00+00:00",
    )

    assert adapter.calls == [("固态电池", 100_000)]
    assert len(calls) == len(CONTROLLED_INTENTS) == 4
    assert len({result["candidate_pool_sha256"] for result in artifact["results"].values()}) == 1
    assert artifact["report"]["outcome"] == "discriminative"
    assert artifact["code_revision"] == "abc123"
    assert artifact["model"] == "fixture-model"
    assert set(artifact["providers"]) == {"fixture-provider"}
    assert artifact["candidate_pool"]["evidence_coverage"]["indexed"] is True
    prompt = json.dumps(calls, ensure_ascii=False)
    assert "evidence_coverage" not in prompt
    assert "100" not in prompt
    assert all(question in prompt for question in CONTROLLED_INTENTS.values())


def test_probe_artifact_hash_binds_frozen_results() -> None:
    adapter = _FakeAdapter()

    def complete(messages, **kwargs):
        del messages, kwargs
        return (
            json.dumps({"companies": [f"公司{index:02d}" for index in range(12)]}),
            type("Provider", (), {"name": "fixture", "model": "fixture-model"})(),
            "",
        )

    artifact = run_probe(
        concept="固态电池",
        adapter=adapter,
        complete=complete,
        model="fixture-model",
        code_revision="abc123",
        created_at="2026-08-01T00:00:00+00:00",
    )
    assert artifact["artifact_sha256"] == canonical_payload_hash(artifact)

    mutated = copy.deepcopy(artifact)
    mutated["results"]["beneficiary"]["companies"][0] = "篡改公司"
    assert mutated["artifact_sha256"] != canonical_payload_hash(mutated)
