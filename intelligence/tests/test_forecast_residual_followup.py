"""P2：首轮露出未核验格；追问补格不重跑五日包。"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from intelligence.services.forecast_residual_budget import forecast_opening_pack_ready
from intelligence.services.forecast_residual_followup import (
    append_unverified_forecast_grids,
    is_forecast_grid_followup,
    should_skip_weekly_pack,
)
from intelligence.services.followups import compose_followups, project_continuous_state
from intelligence.services.query_resolution import classify_reference
from intelligence.services.turn_controller import decide_turn


def _no_llm(*_args, **_kwargs):
    raise AssertionError("P2 夹具不得走模型")


def test_first_round_public_answer_names_unverified_grids_in_user_language() -> None:
    text = append_unverified_forecast_grids(
        "量能还在收缩，短线先看修复。",
        question_type="market_forecast",
        open_gaps=("列出判断继续成立的可核验条件",),
    )
    assert "量能还在收缩" in text
    assert "这次还核验不了" in text
    assert "续走条件" in text
    assert "【质检" not in text
    assert "【结构缺口】" not in text


def test_non_forecast_answer_does_not_grow_unverified_grids() -> None:
    body = "液冷服务器当日跌 1.11%。"
    assert (
        append_unverified_forecast_grids(
            body,
            question_type="theme_analysis",
            open_gaps=("列出判断继续成立的可核验条件",),
        )
        == body
    )


def test_compose_followups_exposes_forecast_gap_without_qc_heading() -> None:
    state = project_continuous_state(
        subject="本周行情",
        question="写一下本周行情的展望",
        open_gaps=("列出判断继续成立的可核验条件",),
        status="partial",
        question_type="market_forecast",
    )
    result = compose_followups(state, polish=False)
    gap_chips = [item for item in result.followups if item.type == "gap"]
    assert gap_chips
    prompt = gap_chips[0].full_prompt
    assert "列出判断继续成立的可核验条件" in prompt
    assert "【质检" not in prompt
    assert classify_reference(prompt) == "continuation"


def test_typed_continuation_followup_inherits_forecast_seat() -> None:
    first = decide_turn("写一下本周行情的展望", llm_complete=_no_llm)
    assert first.question_type == "market_forecast"
    assert first.turn_intent is not None

    second = decide_turn(
        "把续走条件写具体",
        previous_intent=first.turn_intent,
        previous_turn_id="msg-forecast-1",
        llm_complete=_no_llm,
    )
    assert second.question_type == "market_forecast"
    assert second.turn_intent is not None
    assert second.turn_intent.inherited_from_turn == "msg-forecast-1"


def test_gap_mirror_prompt_inherits_forecast_seat() -> None:
    first = decide_turn("写一下本周行情的展望", llm_complete=_no_llm)
    prompt = (
        "关于本周行情，上一轮「列出判断继续成立的可核验条件」未完成核验："
        "请只针对这一项补齐证据，给出可核对的来源与数据日期。"
    )
    second = decide_turn(
        prompt,
        previous_intent=first.turn_intent,
        previous_turn_id="msg-forecast-1",
        llm_complete=_no_llm,
    )
    assert classify_reference(prompt) == "continuation"
    assert second.question_type == "market_forecast"


def test_followup_prefetch_does_not_rerun_weekly_pack(tmp_path) -> None:
    assert is_forecast_grid_followup("把续走条件写具体")
    assert should_skip_weekly_pack(
        question="把续走条件写具体",
        question_type="market_forecast",
    )
    assert not should_skip_weekly_pack(
        question="写一下本周行情的展望",
        question_type="market_forecast",
    )

    from intelligence.services.asof_prefetch import collect_prefetch_items

    with patch(
        "intelligence.services.weekly_watch_pack.run_weekly_watch_pack",
        side_effect=AssertionError("五日包不得当新菜重跑"),
    ):
        items = collect_prefetch_items(
            question="把续走条件写具体",
            question_type="market_forecast",
            subject="",
            as_of=date(2026, 8, 21),
            market_db_path=tmp_path / "unused.duckdb",
        )
    titles = [item.title for item in items]
    assert not any(title.endswith("四袋") for title in titles)
    assert "先验周量能序列" not in titles
    assert any("沿用上轮" in item.title or "不重跑" in item.detail for item in items)
    assert forecast_opening_pack_ready(items) is False


def test_first_round_forecast_still_requests_weekly_pack(tmp_path) -> None:
    from intelligence.services.asof_prefetch import collect_prefetch_items

    called = {"n": 0}

    def _fake_pack(*_args, **_kwargs):
        called["n"] += 1
        raise RuntimeError("夹具停在委托处即可")

    with patch(
        "intelligence.services.weekly_watch_pack.run_weekly_watch_pack",
        side_effect=_fake_pack,
    ):
        collect_prefetch_items(
            question="写一下本周行情的展望",
            question_type="market_forecast",
            subject="",
            as_of=date(2026, 8, 21),
            market_db_path=tmp_path / "unused.duckdb",
        )
    assert called["n"] == 1


def test_theme_followup_does_not_inherit_via_forecast_skip_helper() -> None:
    assert not should_skip_weekly_pack(
        question="把续走条件写具体",
        question_type="theme_analysis",
    )
