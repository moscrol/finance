"""研究进展账（06 号单）的纯函数测试：计数、建议码、收口判据、分支摘要。"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from intelligence.runtime.research_progress import (
    REPEAT_QUERY_THRESHOLD,
    STALL_STEER_BATCHES,
    ResearchProgressTracker,
    ToolCallDigest,
    normalize_query,
    stall_finalize_batches,
)


def _batch(tracker: ResearchProgressTracker, *digests: ToolCallDigest):
    for digest in digests:
        tracker.record_call(digest)
    return tracker.close_batch()


def test_normalize_query_collapses_whitespace_and_reads_mapping_forms() -> None:
    assert normalize_query("  电网  设备\n双红 ") == "电网 设备 双红"
    assert normalize_query({"query": "A股 液冷"}) == "a股 液冷"
    assert normalize_query({"goals": ["长电", "通富"]}) == "长电 | 通富"
    assert normalize_query({}) == ""
    assert len(normalize_query("x" * 500)) == 120


def test_digest_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        ToolCallDigest("market_data", "q", "weird")


def test_new_evidence_resets_stall_and_duplicates_accumulate() -> None:
    tracker = ResearchProgressTracker(stall_finalize_batches=3)
    first = _batch(tracker, ToolCallDigest("kb_search", "光刻胶", "new", new_evidence=3, total_evidence=3))
    assert first is not None and first.new_evidence == 3
    assert tracker.stalled_batches == 0 and tracker.evidence_total == 3

    _batch(tracker, ToolCallDigest("kb_search", "光刻胶", "duplicate", total_evidence=3))
    assert tracker.stalled_batches == 1
    # 同一「工具 + 查询」第二次仍无新证据 → 记为重复查询、建议换查询。
    assert tracker.repeated_queries() == (
        {"tool": "kb_search", "query": "光刻胶", "attempts": REPEAT_QUERY_THRESHOLD},
    )
    assert "switch_query" in tracker.suggestions()
    assert "stalled" not in tracker.suggestions()

    _batch(tracker, ToolCallDigest("kb_search", "光刻胶 国产化", "empty"))
    assert tracker.stalled_batches == STALL_STEER_BATCHES
    codes = tracker.suggestions(available_tools=("kb_search", "web_search", "l3_lookup", "sub_research"))
    assert "stalled" in codes
    # kb_search 连续两次空手 / 重复 → 换工具，候选里不含它自己也不含 sub_research。
    assert "switch_tool:kb_search→web_search,l3_lookup" in codes
    assert not tracker.should_finalize()

    _batch(tracker, ToolCallDigest("web_search", "光刻胶 国产替代 2026", "new", new_evidence=2, total_evidence=4))
    assert tracker.stalled_batches == 0
    assert tracker.evidence_total == 5
    # 有了新证据，早先那条重复查询仍在记录里（历史事实），但 kb_search 的空手连击没有被 web_search 清掉。
    assert tracker.empty_tools() == (("kb_search", 2),)


def test_should_finalize_requires_evidence_and_threshold() -> None:
    tracker = ResearchProgressTracker(stall_finalize_batches=2)
    _batch(tracker, ToolCallDigest("web_search", "a", "empty"))
    _batch(tracker, ToolCallDigest("web_search", "b", "empty"))
    # 连续两批零证据但账上一条证据都没有：不收口，收口了没东西可写。
    assert tracker.stalled_batches == 2 and not tracker.should_finalize()

    tracker = ResearchProgressTracker(stall_finalize_batches=2)
    _batch(tracker, ToolCallDigest("web_search", "a", "new", new_evidence=1, total_evidence=1))
    _batch(tracker, ToolCallDigest("web_search", "a", "duplicate", total_evidence=1))
    assert not tracker.should_finalize()
    _batch(tracker, ToolCallDigest("web_search", "a", "duplicate", total_evidence=1))
    assert tracker.should_finalize()

    disabled = ResearchProgressTracker(stall_finalize_batches=0)
    _batch(disabled, ToolCallDigest("web_search", "a", "new", new_evidence=1, total_evidence=1))
    for _ in range(5):
        _batch(disabled, ToolCallDigest("web_search", "a", "duplicate", total_evidence=1))
    assert disabled.stalled_batches == 5 and not disabled.should_finalize()


def test_rejected_duplicate_counts_as_no_progress() -> None:
    tracker = ResearchProgressTracker(stall_finalize_batches=3)
    _batch(tracker, ToolCallDigest("market_data", "q", "new", new_evidence=1, total_evidence=1))
    _batch(tracker, ToolCallDigest("market_data", "q", "duplicate"))
    assert tracker.stalled_batches == 1
    assert tracker.repeated_queries()[0]["attempts"] == 2


def test_external_input_resets_stall_counter() -> None:
    tracker = ResearchProgressTracker(stall_finalize_batches=3)
    _batch(tracker, ToolCallDigest("market_data", "q", "new", new_evidence=1, total_evidence=1))
    _batch(tracker, ToolCallDigest("market_data", "q", "duplicate"))
    _batch(tracker, ToolCallDigest("market_data", "q2", "empty"))
    assert tracker.stalled_batches == 2
    tracker.note_external_input()
    assert tracker.stalled_batches == 0


@dataclass(frozen=True)
class _Branch:
    branch_id: str
    goal: str
    status: str
    evidence: tuple[str, ...]
    gaps: tuple[str, ...]
    error: str = ""


def test_branch_summary_shows_once_and_flags_failed_branch() -> None:
    tracker = ResearchProgressTracker(stall_finalize_batches=3)
    tracker.record_branches(
        (
            _Branch("branch-1", "长电客户", "partial", ("e1", "e2"), ("缺产能",)),
            _Branch("branch-2", "通富客户", "failed", (), ("x",), error="deadline_exhausted"),
        ),
        refused_reason="",
    )
    _batch(tracker, ToolCallDigest("sub_research", {"goals": ["长电客户", "通富客户"]}, "new", new_evidence=2, total_evidence=2))
    view = tracker.model_view(available_tools=("web_search",))
    assert view["branches"] == [
        {"branch_id": "branch-1", "goal": "长电客户", "status": "partial", "evidence": 2, "gaps": 1},
        {
            "branch_id": "branch-2",
            "goal": "通富客户",
            "status": "failed",
            "evidence": 0,
            "gaps": 1,
            "error": "deadline_exhausted",
        },
    ]
    assert "follow_up_divergences" in view["suggestion"]
    assert "branch_failed:branch-2" in view["suggestion"]
    assert "只对分支之间不一致" in view["instruction"]
    # 分支摘要只在紧接着的那一次视图里出现；之后不再重复占上下文。
    _batch(tracker, ToolCallDigest("web_search", "通富 客户", "new", new_evidence=1, total_evidence=1))
    later = tracker.model_view(available_tools=("web_search",))
    assert "branches" not in later and "suggestion" not in later


def test_model_view_shape_and_finalize_warning() -> None:
    tracker = ResearchProgressTracker(stall_finalize_batches=3)
    _batch(tracker, ToolCallDigest("kb_search", "A", "new", new_evidence=2, total_evidence=2))
    view = tracker.model_view(available_tools=("kb_search",))
    assert view["batch"] == 1 and view["new_evidence"] == 2 and view["evidence_total"] == 2
    assert view["stalled_batches"] == 0
    assert view["last_batch"] == [{"tool": "kb_search", "query": "a", "result": "new:2"}]
    assert "suggestion" not in view and "repeated_queries" not in view
    assert view["instruction"].startswith("research_progress 是底座按批记的事实")

    _batch(tracker, ToolCallDigest("kb_search", "A", "duplicate", total_evidence=2))
    _batch(tracker, ToolCallDigest("kb_search", "B", "empty"))
    view = tracker.model_view(
        available_tools=("kb_search", "web_search"),
        tools_short_of_window=("evidence_search",),
    )
    assert view["stalled_batches"] == 2
    assert view["repeated_queries"] == [{"tool": "kb_search", "query": "a", "attempts": 2}]
    assert view["tools_short_of_window"] == ["evidence_search"]
    assert set(view["suggestion"]) >= {"switch_query", "stalled", "switch_tool:kb_search→web_search"}
    assert "再一批没有新证据，研究阶段将自动关闭" in view["instruction"]
    assert "evidence_search 在剩余时间窗里装不下" in view["instruction"]


def test_stall_finalize_env_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", raising=False)
    # 缺省只提醒不收口：既有 loop 测试用固定 hash 假工具跑满预算，默认收口会改它们的账。
    assert stall_finalize_batches() == 0
    monkeypatch.setenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", "3")
    assert stall_finalize_batches() == 3
    monkeypatch.setenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", "abc")
    assert stall_finalize_batches() == 0
    monkeypatch.setenv("WORKBENCH_RESEARCH_STALL_FINALIZE_BATCHES", "-4")
    assert stall_finalize_batches() == 0
