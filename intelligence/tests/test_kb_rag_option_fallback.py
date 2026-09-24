"""旧 CLI 兼容仅准降级非约束选项；证据过滤必须执行，不得删参洗成成功。"""

from __future__ import annotations

from intelligence.services import kb_rag


def test_filter_constraints_are_not_droppable() -> None:
    for option in ("--evidence-layer", "--fact-hardness", "--source-type", "--as-of"):
        assert option not in kb_rag._DROPPABLE_QUERY_OPTIONS


def test_evidence_chars_stays_droppable() -> None:
    """原有的 --evidence-chars 降级路径不能被这次泛化弄丢。"""
    assert "--evidence-chars" in kb_rag._DROPPABLE_QUERY_OPTIONS


def test_unsupported_option_is_detected_from_stderr() -> None:
    stderr = (
        "usage: rag_index.py query [-h] ...\n"
        "rag_index.py: error: unrecognized arguments: --evidence-layer L1\n"
    )

    assert kb_rag._unsupported_option(stderr, "--evidence-layer") is True
    assert kb_rag._unsupported_option(stderr, "--fact-hardness") is False


def test_without_option_removes_the_flag_and_its_value() -> None:
    cmd = [
        "python", "rag_index.py", "query", "固态电池",
        "--k", "6", "--evidence-layer", "L1", "--json",
    ]

    stripped = kb_rag._without_option(cmd, "--evidence-layer")

    assert "--evidence-layer" not in stripped
    assert "L1" not in stripped
    assert stripped[-1] == "--json"
    assert "固态电池" in stripped


def test_known_stale_index_reason_is_surfaced_with_a_remedy() -> None:
    """新鲜度守卫的原因必须带补救动作，而不是只留一句退出码。"""
    reason = kb_rag._stderr_reason(
        "[query] 索引过期，拒绝作为证据: indexed source has working-tree changes"
    )

    assert "working-tree changes" in reason
    assert "补救" in reason
    assert "提交" in reason


def test_unknown_stderr_is_not_leaked() -> None:
    """任意 stderr 不外泄：可能带查询原文/路径/traceback 且无操作价值。"""
    assert kb_rag._stderr_reason("ValueError: malformed query arguments") == ""
    assert kb_rag._stderr_reason("") == ""
    assert kb_rag._stderr_reason(None) == ""


def test_every_remedy_marker_resolves() -> None:
    for marker, _remedy in kb_rag._RAG_REMEDIES:
        assert kb_rag._stderr_reason(f"[query] 索引过期: {marker}").startswith(
            "索引不可用作证据"
        )
