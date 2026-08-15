from __future__ import annotations

import json

from intelligence.services import llm_refine
from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
from intelligence.services.judge_source_recheck import (
    NumericClaim,
    compare_claim,
    extract_numeric_claims,
    recheck_draft,
    recheck_enabled,
)
from intelligence.services.research_contract import ResearchDeadline
from intelligence.tests.test_episode_semantic_verifier import (
    _RecordingJudgeModel,
    _structural,
)


def test_recheck_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("ASK_JUDGE_RECHECK", raising=False)
    assert recheck_enabled() is False


def test_extract_requires_one_number_and_a_date_token() -> None:
    claims = extract_numeric_claims(
        "今日半导体涨幅 3.2%。市场情绪偏弱。本月有两次加息。"
    )
    assert [item.number for item in claims] == [3.2]
    assert "今日" in claims[0].text


def test_compare_marks_mismatch_outside_tolerance() -> None:
    claim = NumericClaim("今日涨幅 9.9%", 9.9)
    assert compare_claim(claim, 9.88) == "match"
    assert compare_claim(claim, 1.2) == "mismatch"


def test_recheck_draft_mismatch_and_fail_open() -> None:
    def lookup(claim: NumericClaim) -> float | None:
        if "9.9" in claim.text:
            return 1.2
        raise RuntimeError("boom")

    rows = recheck_draft(
        "今日涨幅 9.9%。今日成交额 1.0 万亿。",
        lookup=lookup,
    )
    assert rows[0]["verdict"] == "mismatch"
    assert rows[0]["source_value"] == 1.2
    assert rows[1]["verdict"] == "recheck_unavailable"


def test_default_lookup_is_unavailable_without_workspace(monkeypatch) -> None:
    monkeypatch.delenv("FINANCE_WS", raising=False)
    rows = recheck_draft("今日涨幅 3.2%。")
    assert rows == [
        {
            "claim": "今日涨幅 3.2%",
            "source_value": None,
            "verdict": "recheck_unavailable",
        }
    ]


def test_recheck_draft_times_out_remaining_claims() -> None:
    calls = {"n": 0}

    def lookup(claim: NumericClaim) -> float:
        calls["n"] += 1
        return 1.0

    rows = recheck_draft(
        "今日涨幅 2.0%。昨天跌幅 1.0%。",
        lookup=lookup,
        total_seconds=0.0,
    )
    assert rows
    assert all(row["verdict"] == "recheck_unavailable" for row in rows)
    assert calls["n"] == 0


def test_judge_request_omits_recheck_when_off(monkeypatch) -> None:
    monkeypatch.delenv("ASK_JUDGE_RECHECK", raising=False)
    frame, structural = _structural("今日涨幅 9.9%。")
    model = _RecordingJudgeModel()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    request = json.loads(model.calls[0]["messages"][1]["content"])
    assert "source_recheck" not in request


def test_judge_request_injects_mismatch_when_on(monkeypatch) -> None:
    monkeypatch.setenv("ASK_JUDGE_RECHECK", "on")
    monkeypatch.setattr(
        "intelligence.services.episode_semantic_verifier.recheck_draft",
        lambda text: [
            {
                "claim": "今日涨幅 9.9%",
                "source_value": 1.2,
                "verdict": "mismatch",
            }
        ],
    )
    frame, structural = _structural("今日涨幅 9.9%。")
    model = _RecordingJudgeModel()
    monkeypatch.setattr(llm_refine, "judge_provider", lambda: None)
    SemanticEpisodeVerifier(primary_judge=model).verify(
        frame=frame,
        structurally_verified=structural,
        deadline=ResearchDeadline.from_timeout(5),
    )
    request = json.loads(model.calls[0]["messages"][1]["content"])
    assert request["source_recheck"] == [
        {
            "claim": "今日涨幅 9.9%",
            "source_value": 1.2,
            "verdict": "mismatch",
        }
    ]
