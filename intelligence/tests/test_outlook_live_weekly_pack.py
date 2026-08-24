"""Outlook live weekly + five-day pack. Offline fixtures only."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from intelligence import userspace
from intelligence.services import perspective_lab
from intelligence.services.asof_prefetch import collect_prefetch_items
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import _opening_prefetch_evidence
from intelligence.services.outlook_delivery_gate import strip_outlook_violations
from intelligence.services.perspective_live_weekly import (
    EXCERPT_CHARS,
    bind_live_weekly,
    is_live_weekly_evidence,
    live_weekly_evidence,
    retrieve_analog_snippets,
)
from intelligence.services.task_frame import TaskFrame
from intelligence.services.weekly_watch_pack import run_weekly_watch_pack

try:
    import duckdb
except Exception:  # pragma: no cover
    duckdb = None

pytestmark = pytest.mark.skipif(duckdb is None, reason="duckdb 不可用")

DAYS = (
    "2026-08-17",
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
)


def _us(tmp: Path, uid: str = "tester") -> userspace.UserSpace:
    root = tmp / uid
    return userspace.UserSpace(
        user_id=uid,
        root=root,
        profile_path=root / "profile.json",
        derived_path=root / "profile.derived.json",
        memory_path=root / "foresight_memory.jsonl",
        interactions_path=root / "interactions.jsonl",
        corrections_path=root / "corrections.jsonl",
        experience_cards_path=root / "experience_cards.jsonl",
        answer_scores_path=root / "answer_scores.jsonl",
        judgments_path=root / "judgments.jsonl",
        checkpoints_path=root / "checkpoints.jsonl",
        verdicts_path=root / "verdicts.jsonl",
        strategy_params_path=root / "strategy_params.json",
    )


def _week_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    con.execute(
        "create table fact_market_daily ("
        "trade_date date, total_amount double, volume_ratio double, "
        "amount_ma20 double, market_stage varchar, sh_index_pct_chg double)"
    )
    con.executemany(
        "insert into fact_market_daily values (?, ?, ?, ?, ?, ?)",
        [
            (DAYS[0], 23857.90, 101.19, 22000.0, "反弹", None),
            (DAYS[1], 24006.36, 103.03, 22100.0, "反弹", 0.4),
            (DAYS[2], 25108.68, 108.09, 22200.0, "分歧", -2.40),
            (DAYS[3], 20792.47, 89.73, 22100.0, "修复", 0.8),
            (DAYS[4], 18791.51, 81.19, 22000.0, "观望", 0.2),
            ("2026-08-24", 30000.0, 120.0, 23000.0, "库尖", 1.0),
        ],
    )
    con.execute(
        "create table fact_sector_daily ("
        "trade_date date, sector_name varchar, "
        "pct_chg double, diff_ratio double, amount double)"
    )
    # COUNT: 08-17=2, 08-18=1, 08-19=0 (rows exist), 08-20=1, 08-21=1
    con.executemany(
        "insert into fact_sector_daily values (?, ?, ?, ?, ?)",
        [
            (DAYS[0], "创新药", 3.0, 20.0, 800.0),
            (DAYS[0], "有色", 2.0, 15.0, 600.0),
            (DAYS[1], "创新药", 2.0, 12.0, 550.0),
            (DAYS[2], "创新药", -1.0, 2.0, 200.0),
            (DAYS[2], "有色", 0.5, 3.0, 180.0),
            (DAYS[3], "创新药", 4.0, 18.0, 900.0),
            (DAYS[4], "有色", 1.2, 11.0, 520.0),
        ],
    )
    con.execute(
        "create table fact_mainline_theme_daily ("
        "trade_date date, theme_name varchar, sector_count integer)"
    )
    con.executemany(
        "insert into fact_mainline_theme_daily values (?, ?, ?)",
        [
            (DAYS[0], "有色", 2),
            (DAYS[3], "创新药", 4),
            (DAYS[4], "医药", 2),
            (DAYS[4], "有色", 1),
        ],
    )
    con.execute(
        "create table fact_theme_limit_heat_daily ("
        "trade_date date, sector_name varchar, limit_up_count integer, market_share double)"
    )
    con.execute(
        "insert into fact_theme_limit_heat_daily values (?, ?, ?, ?)",
        [DAYS[3], "创新药", 12, 48.0],
    )
    con.close()
    return path


def _forecast_frame(question: str = "写一下本周行情的展望") -> TaskFrame:
    return TaskFrame(
        raw_question=question,
        user_goal="本周展望",
        question_type="market_forecast",
        subject=None,
        subject_kind="unknown",
        market_scope="A股",
        timeframe="本周",
        required_outputs=("direct_assessment", "scenario_paths"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="current_market_scenarios",
        confidence=0.9,
    )


def _seed_articles(tmp: Path) -> userspace.UserSpace:
    us = _us(tmp)
    perspective_lab.init_perspective(us, "sptfei", display_name="SPT", ptype="blogger")
    old = tmp / "old.md"
    old.write_text(
        "## 中观\n2026.23 讲 4060-4150 箱体，AI 硬件鱼尾，电解液类比。\n" + ("旧文填充 " * 80),
        encoding="utf-8",
    )
    live = tmp / "live.md"
    live.write_text(
        "## 中观\n药为 8/5 断代后的新主线，箱子 3880-3980，升级看 2.6 万亿一体两面。\n",
        encoding="utf-8",
    )
    perspective_lab.ingest_article(
        us, "sptfei", old, title="2026.23 箱体", date="2026-06-01"
    )
    perspective_lab.ingest_article(
        us, "sptfei", live, title="2026.34 药主线", date="2026-08-17"
    )
    return us


def test_audit_probe_identity_still_assembles_registry() -> None:
    from intelligence.services.episode_tools import build_episode_registry
    from intelligence.services.research_tool_registry import _DEFAULT_TOOL_METADATA

    frame = _forecast_frame()
    context = build_episode_context(
        frame,
        task_id="tool-reachability-audit",
        capabilities=tuple(sorted(_DEFAULT_TOOL_METADATA)),
    )
    registry = build_episode_registry(frame, context, memory_user="__audit_probe__")
    assert "memory_lookup" in registry.names()
    assert not any(is_live_weekly_evidence(item) for item in registry.opening_prefetch)


def test_bind_live_weekly_uses_max_date(tmp_path: Path) -> None:
    us = _seed_articles(tmp_path)
    receipt = bind_live_weekly(us, "sptfei", perspective_mode="single")
    assert receipt.status == "bound"
    assert receipt.date == "2026-08-17"
    assert receipt.title == "2026.34 药主线"
    assert "3880" in receipt.excerpt
    assert "4060" not in receipt.excerpt
    assert len(receipt.excerpt) <= EXCERPT_CHARS
    hashed = live_weekly_evidence(receipt)
    assert hashed
    assert all(str(item.content_hash or "").strip() for item in hashed)


def test_bind_live_weekly_missing_and_neutral(tmp_path: Path) -> None:
    us = _us(tmp_path)
    perspective_lab.init_perspective(us, "sptfei", display_name="SPT", ptype="blogger")
    missing = bind_live_weekly(us, "sptfei", perspective_mode="single")
    assert missing.status == "missing"
    skipped = bind_live_weekly(us, "sptfei", perspective_mode="neutral")
    assert skipped.status == "skipped"


def test_analog_is_older_than_live(tmp_path: Path) -> None:
    us = _seed_articles(tmp_path)
    hits = retrieve_analog_snippets(
        us,
        "sptfei",
        "4060 箱体 电解液 量能",
        live_date="2026-08-17",
    )
    assert hits
    assert all(item["date"] < "2026-08-17" for item in hits)
    assert all(item.get("analog") == "true" for item in hits)


def test_corrections_are_not_live_weekly() -> None:
    from intelligence.services.agent_research import AgentEvidence

    correction = AgentEvidence(
        tool="memory_lookup",
        title="用户纠偏原则",
        detail="SPT 量能 展望 纠偏",
        source="用户自己纠正过的方法论（先验，非市场事实）",
    )
    assert is_live_weekly_evidence(correction) is False


def test_weekly_pack_five_days_and_count(tmp_path: Path) -> None:
    db = _week_db(tmp_path / "week.duckdb")
    pack = run_weekly_watch_pack("2026-08-21", market_db_path=db, window=5)
    assert pack.days == DAYS
    assert pack.energy_for("2026-08-19") is not None
    assert pack.energy_for("2026-08-19").double_red_count == 0
    assert pack.energy_for("2026-08-17").double_red_count == 2
    thursday = pack.pack_for("2026-08-20")
    assert thursday is not None
    mainline = thursday.bag("mainline")
    assert mainline is not None and not mainline.empty
    assert any(row.get("theme_name") == "创新药" for row in mainline.rows)
    market = pack.pack_for("2026-08-21").bag("market_daily")
    assert market.requested_date == market.served_date == "2026-08-21"
    assert pack.energy_for("2026-08-21").volume_ratio == pytest.approx(81.19)


def test_prefetch_forecast_has_thursday_bag_general_does_not(tmp_path: Path) -> None:
    db = _week_db(tmp_path / "week.duckdb")
    forecast = collect_prefetch_items(
        question="写一下本周行情的展望",
        question_type="market_forecast",
        subject="",
        as_of=date(2026, 8, 21),
        market_db_path=db,
    )
    titles = [item.title for item in forecast]
    assert "先验周量能序列" in titles
    assert "2026-08-20 四袋" in titles
    thursday = next(item for item in forecast if item.title == "2026-08-20 四袋")
    assert "创新药" in thursday.detail
    assert thursday.source_date == "2026-08-20"
    general = collect_prefetch_items(
        question="写一下本周行情的展望",
        question_type="general_finance_qa",
        subject="",
        as_of=date(2026, 8, 21),
        market_db_path=db,
    )
    assert not any(item.title.endswith("四袋") for item in general)


def test_opening_evidence_includes_weekly_and_live(tmp_path: Path) -> None:
    db = _week_db(tmp_path / "week.duckdb")
    us = _seed_articles(tmp_path)
    frame = _forecast_frame()
    context = build_episode_context(
        frame,
        task_id="outlook-open",
        today="2026-08-24",
        latest_data_date="2026-08-21",
    )
    evidence = _opening_prefetch_evidence(
        frame,
        context,
        db,
        user_space=us,
        perspective_ids=("sptfei",),
        perspective_mode="single",
    )
    titles = [item.title for item in evidence]
    assert any("2026-08-20 四袋" in title for title in titles)
    live = next(item for item in evidence if is_live_weekly_evidence(item))
    assert live.source_date == "2026-08-17"
    assert "3880" in live.detail
    assert all(str(item.content_hash or "").strip() for item in evidence)


def test_neutral_skips_live_but_keeps_week_pack(tmp_path: Path) -> None:
    db = _week_db(tmp_path / "week.duckdb")
    us = _seed_articles(tmp_path)
    frame = _forecast_frame()
    context = build_episode_context(
        frame,
        task_id="outlook-neutral",
        today="2026-08-24",
        latest_data_date="2026-08-21",
    )
    evidence = _opening_prefetch_evidence(
        frame,
        context,
        db,
        user_space=us,
        perspective_ids=("sptfei",),
        perspective_mode="neutral",
    )
    assert any("2026-08-20 四袋" in item.title for item in evidence)
    assert not any(is_live_weekly_evidence(item) for item in evidence)


def test_delivery_gate_drops_verification_and_old_issue() -> None:
    text = (
        "新闻层已给部分验证。SPT 原文判断（2026.23）认为箱体还在。"
        "医药老主线继续兑现。结构类比 analog 可以提 2026.23。"
    )
    cleaned = strip_outlook_violations(
        text,
        live_date="2026-08-17",
        live_excerpt="药为断代后的新主线",
        last_mainline_names=("医药", "有色"),
        analog_issue_ids=("2026.23",),
    )
    assert "已给部分验证" not in cleaned
    assert "原文判断（2026.23）" not in cleaned
    assert "医药老主线" not in cleaned
    assert "结构类比" in cleaned
