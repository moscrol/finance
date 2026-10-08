from __future__ import annotations

from datetime import date
import json
from types import SimpleNamespace

import pytest

from intelligence.services import review_evidence_handoff as handoff
from intelligence.services.research_contract import InformationCutoff
from intelligence.services.research_tool_registry import ResearchToolRegistry
from intelligence.services.river_review_history import review_history
from intelligence.services.run_store import RunStore
from tests.test_river_daily_review import payload, write


def _day(day, amount=100):
    data = payload(day)
    data["facts"]["total_amount"] = amount
    data["facts"]["top_amount_sw_l1"] = ["电子"]
    for section in data["sections"]:
        for block in section["blocks"]:
            if block["kind"] == "table" and len(block["columns"]) == 3:
                block["columns"][1:] = ["09-18", day[5:]]
    return data


def _archive(tmp_path):
    for day, amount in [("2026-09-21", 100), ("2026-09-22", 120), ("2026-09-24", 180)]:
        write(tmp_path, _day(day, amount))
    return review_history(tmp_path, end=date(2026, 9, 24), days=5, industry="电子")


def _ref(history, **overrides):
    body = {"schema": handoff.REF_SCHEMA, "end": history["end"], "days": history["requested_days"],
            "industry": history["industry"], "fingerprint": history["window_fingerprint"],
            "selected_date": "2026-09-22"}
    body.update(overrides)
    return handoff.ReviewEvidenceRef.from_payload(body)


def test_fingerprint_is_what_the_page_saw_and_rewrites_fail_closed(tmp_path):
    history = _archive(tmp_path)
    assert len(history["window_fingerprint"]) == 64
    assert handoff.verify_review_evidence(tmp_path, _ref(history))["points"] == history["points"]
    # The archive is regenerated after the user looked at it: refuse, name it.
    write(tmp_path, _day("2026-09-22", 999))
    with pytest.raises(handoff.ReviewEvidenceMismatch):
        handoff.verify_review_evidence(tmp_path, _ref(history))
    # A missing day that later appears is also a different window.
    history = review_history(tmp_path, end=date(2026, 9, 24), days=5, industry="电子")
    write(tmp_path, _day("2026-09-23"))
    with pytest.raises(handoff.ReviewEvidenceMismatch):
        handoff.verify_review_evidence(tmp_path, _ref(history))


@pytest.mark.parametrize("override", [
    {"schema": "review-evidence-ref/v0"}, {"days": 4}, {"days": 61}, {"industry": " "},
    {"fingerprint": "x" * 64}, {"end": "2026-13-01"}, {"selected_date": "nope"},
])
def test_ref_rejects_malformed_coordinates(tmp_path, override):
    history = _archive(tmp_path)
    with pytest.raises(ValueError):
        _ref(history, **override)


def test_cards_keep_missing_unknown_and_cutoff_explicit(tmp_path):
    history = _archive(tmp_path)
    cards = handoff.review_evidence_cards(history, information_cutoff=date(2026, 9, 22))
    contract, *days = cards
    assert contract.tool == handoff.EVIDENCE_TOOL and contract.evidence_tier == handoff.EVIDENCE_TIER
    assert [c.source_date for c in days] == ["2026-09-21", "2026-09-22"]
    assert "2026-09-18 缺结构化归档（不用别日替代）" in contract.detail
    assert "2026-09-23 晚于本轮资料截止" in contract.detail
    assert "2026-09-24 晚于本轮资料截止 2026-09-22" in contract.detail
    assert "解读方法是待执行的研究指导，不是行情事实" in contract.detail
    assert "缺失不是零" in contract.detail
    day = days[-1]
    assert day.freshness == "historical" and day.internal_locator.startswith("/points/")
    assert "较2026-09-21 +20亿元" in day.detail
    assert "市场成交额 120亿元" in day.detail and "涨家数 MA5 —" in day.detail
    assert "列入成交前三，第1位" in day.detail
    assert "芯片=-2.0%/-10.0/750" in day.detail  # own-day column value, verbatim
    assert "测试股" in day.detail
    assert "sha256" in day.source
    assert all(c.content_hash == handoff.agent_research.evidence_content_hash(c) for c in cards)
    assert handoff.review_evidence_cards(history, information_cutoff=date(2026, 9, 22)) == cards


def test_cards_budget_stays_contiguous_from_newest(tmp_path, monkeypatch):
    history = _archive(tmp_path)
    full = handoff.review_evidence_cards(history, information_cutoff=None)
    newest = full[-1]
    monkeypatch.setattr(handoff, "CARD_CHAR_BUDGET", len(newest.detail) + 1)
    contract, *days = handoff.review_evidence_cards(history, information_cutoff=None)
    assert [c.source_date for c in days] == ["2026-09-24"]
    assert "2026-09-22 超出本轮开场证据篇幅，未交付（不是无数据）" in contract.detail
    assert "2026-09-21 超出本轮开场证据篇幅" in contract.detail


def test_not_listed_and_engine_truncation_are_not_exit(tmp_path):
    data = payload()
    data["sections"][3]["blocks"][1]["rows"] *= 30
    write(tmp_path, data)
    history = review_history(tmp_path, end=date(2026, 9, 24), days=5, industry="机械设备")
    *_, day = handoff.review_evidence_cards(history, information_cutoff=None)
    assert "未列入成交前三（只说明未进这份榜单，不是零或消失）" in day.detail
    history = review_history(tmp_path, end=date(2026, 9, 24), days=5, industry="电子")
    *_, day = handoff.review_evidence_cards(history, information_cutoff=None)
    assert "列出20/30行，余下截断，不能判断个股退出" in day.detail


def test_opening_prefetch_renders_e_numbers_and_scope_narrowing_drops_cards(tmp_path):
    from intelligence.services.asof_prefetch import format_opening_prefetch_message

    history = _archive(tmp_path)
    cards = handoff.review_evidence_cards(history, information_cutoff=None)
    registry = ResearchToolRegistry(()).with_opening_prefetch(*cards)
    assert registry.opening_prefetch == cards
    message = format_opening_prefetch_message(registry.opening_prefetch)
    assert "[E1] 连续复盘证据说明" in message and "[E2] 复盘归档 2026-09-21" in message
    assert "不得说成当时可知" in message
    assert ResearchToolRegistry((), read_scope="local_only").with_opening_prefetch(*cards).opening_prefetch == ()


def test_registry_factory_delivers_verified_cards_or_degrades(tmp_path, monkeypatch):
    from intelligence.api import app as app_module

    history = _archive(tmp_path)
    monkeypatch.setattr(app_module, "_review_exports_root", lambda: tmp_path)
    store = RunStore("alice", root=tmp_path / "runs")
    run = store.create_run("ask", "复盘 电子")
    context = SimpleNamespace(information_cutoff=InformationCutoff(date(2026, 9, 24), "requested"), contract=None)
    base = lambda frame, ctx: ResearchToolRegistry(())  # noqa: E731
    assert app_module._with_review_evidence(base, run_store=store, run_id=run.run_id) is base
    store.save_review_evidence_ref(run.run_id, _ref(history).to_payload())
    factory = app_module._with_review_evidence(base, run_store=store, run_id=run.run_id)
    registry = factory(None, context)
    assert [c.source_date for c in registry.opening_prefetch[1:]] == ["2026-09-21", "2026-09-22", "2026-09-24"]
    assert json.loads((store.run_dir(run.run_id) / "review_evidence_ref.json").read_text())["industry"] == "电子"
    # Archive overwritten between acceptance and assembly: deliver nothing, record why.
    write(tmp_path, _day("2026-09-24", 1))
    assert store.has_review_evidence_receipt(run.run_id)
    assert factory(None, context).opening_prefetch == ()
    assert "review_evidence_changed_before_run" in store.load_run(run.run_id).degrades


def test_undelivered_review_evidence_is_disclosed(tmp_path):
    from intelligence.api import app as app_module

    history = _archive(tmp_path)
    store = RunStore("alice", root=tmp_path / "runs")
    run = store.create_run("ask", "复盘 电子")
    app_module._disclose_undelivered_review_evidence(store, run.run_id)
    assert store.load_run(run.run_id).degrades == []
    store.save_review_evidence_ref(run.run_id, _ref(history).to_payload())
    app_module._disclose_undelivered_review_evidence(store, run.run_id)
    assert "review_evidence_not_delivered" in store.load_run(run.run_id).degrades


def test_prefilled_handoff_message_is_one_question_with_the_window_as_market_target():
    """Mirrors buildReviewEvidenceHandoff (reviewEvidence.ts): the time contract must bind the
    window and the splitter must not turn the user's method into attached material."""
    from intelligence.services.temporal_contract import compile_temporal_contract
    from intelligence.services.user_task import split_user_message

    message = (
        "请复盘 2026-09-18 至 2026-09-24 的电子，以每日复盘归档为准（5 个计划交易日，其中 3 日有可读归档）。"
        " 这次想判断：电子在这段窗口里的变化，是否得到市场环境、行业位置、子板块和发动机名单的共同支持？"
        " 我的解读方法（研究指导，不是市场事实）：先看成交额与涨家数的 MA5，再看行业榜内顺位；按同日核对子板块双红、新高和发动机原表。"
        " 不能直接下结论的情况：缺归档不推断退潮；名单截断不判断股票退出；未列榜不当零。"
        " 回答依次写：覆盖与口径限制、按我的方法联立证据、支持与不支持的证据、仍不能判断的问题；引用交易日与证据编号。"
    )
    assert split_user_message(message).materials == ()
    contract = compile_temporal_contract(message, today=date(2026, 10, 8))
    assert (contract.market_target.start, contract.market_target.end) == ("2026-09-18", "2026-09-24")
    assert contract.errors == () and contract.information_cutoff is None
