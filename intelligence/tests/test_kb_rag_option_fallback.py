"""CLI 拒收的查询选项必须降级重试，而不是把召回打成空集。

回归：知识库的 rag_index.py query 只支持
--model/--include-raw/--k/--mode/--reranker/--json/--evidence-chars/--stale-policy，
不支持工作台一直下发的 --evidence-layer/--fact-hardness/--source-type。每一次分层
证据检索都以 "unrecognized arguments" rc=2 收场、返回空集，表面只留一句
"检索器返回告警"。改 KB 的 CLI 属跨仓改动，所以在工作台侧丢弃选项后重试。
"""

from __future__ import annotations

from intelligence.services import kb_rag


def test_all_filter_options_are_droppable() -> None:
    for option in ("--evidence-layer", "--fact-hardness", "--source-type"):
        assert option in kb_rag._DROPPABLE_QUERY_OPTIONS


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
