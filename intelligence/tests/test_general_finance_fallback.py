"""通用金融问题 fallback assessment 与降级标签的回归测试。

覆盖两个改动：
  1. ``_general_finance_fallback_assessment``：agent loop 的 LLM 不可用但已有
     证据时，用证据摘要拼出最小可审计判断（否则「有 5 条证据仍出空白」）。
  2. ``_assessment_label_for_fallback``：按 fallback 种类分发降级标签。原实现
     用一个共用 bool，导致估值题复用 market_cause 写死的「周内结构化数据／
     外部触发因素」措辞——给出一个错误的降级理由比空白更糟，因为用户无法察觉。
"""

from __future__ import annotations

from intelligence.services import agent_research
from intelligence.services.ask import (
    _DEFAULT_ASSESSMENT_LABEL,
    _assessment_label_for_fallback,
    _general_finance_fallback_assessment,
)

_MARKET_CAUSE_WORDING = ("周内结构化数据", "外部触发因素")


def _ev(detail: str, title: str = "标题") -> agent_research.AgentEvidence:
    return agent_research.AgentEvidence(
        tool="kb_search",
        title=title,
        detail=detail,
        source="https://example.test/ev",
    )


# ─── fallback assessment 函数 ────────────────────────────────────────────────


def test_returns_evidence_summary_when_evidence_exists() -> None:
    ev = _ev("某公司 PE 约 30 倍，ROE 15%，近三年营收年复合 20%。")
    result = _general_finance_fallback_assessment([ev], query="超纯应材估值")
    assert "超纯应材估值" in result
    assert "PE" in result
    # 必须自我标注为未完成，不能让摘要看起来像模型给出的完整判断
    assert "仍需后续补全" in result


def test_returns_no_evidence_message_when_empty() -> None:
    result = _general_finance_fallback_assessment([], query="超纯应材估值")
    assert "超纯应材估值" in result
    assert "未取得" in result


def test_returns_no_evidence_message_when_all_details_blank() -> None:
    """detail 为空的 evidence 不能被算作可引用材料。

    变异测试：去掉 ``if item.detail.strip()`` 过滤后，本例会走进摘要分支，
    拼出一句只有标题、没有事实的「已检索到材料」——比明说没取得更糟。
    """
    ev = agent_research.AgentEvidence(
        tool="kb_search", title="空内容条目", detail="   ", source=""
    )
    result = _general_finance_fallback_assessment([ev], query="测试问题")
    assert "未取得" in result
    assert "空内容条目" not in result


def test_each_evidence_item_is_truncated() -> None:
    """单条 evidence 必须截断，否则 kb_search 的长正文会撑爆 assessment。

    变异测试：去掉 ``[:_MAX_ITEM_CHARS]`` 后，500 字的 detail 会整段进入
    assessment，本例的 ``"A" * 300`` 断言会失败。
    """
    ev = _ev("A" * 500)
    result = _general_finance_fallback_assessment([ev], query="q")
    assert "A" * 300 not in result
    assert "A" * 150 in result  # 截断后仍保留可读摘要


def test_at_most_three_evidence_items_in_summary() -> None:
    """只取前 3 条。

    变异测试：去掉 ``details[:3]`` 后第 4、5 条会进入摘要，本例会失败。
    """
    items = [_ev(f"第{i}条研报证据正文。", title=f"研报{i}") for i in range(5)]
    result = _general_finance_fallback_assessment(items, query="q")
    assert "第0条" in result
    assert "第3条" not in result
    assert "第4条" not in result


def test_summary_never_borrows_market_cause_wording() -> None:
    """通用题的 assessment 正文不得出现原因题专用措辞。"""
    ev = _ev("资金流出、板块同步走弱。")
    result = _general_finance_fallback_assessment([ev], query="本周大盘为何下跌")
    for wording in _MARKET_CAUSE_WORDING:
        assert wording not in result


# ─── 降级标签分发（P0 回归）───────────────────────────────────────────────────


def test_general_finance_label_is_not_market_cause_label() -> None:
    """核心回归：通用研究题不能显示原因题的降级标签。

    这是共用 bool 改成 kind 分发的原因。若退回共用 bool（两种 fallback 命中
    同一句话），本例会失败。
    """
    label = _assessment_label_for_fallback("general_finance")
    for wording in _MARKET_CAUSE_WORDING:
        assert wording not in label
    assert "深度分析仍待补全" in label


def test_market_cause_label_is_preserved() -> None:
    """修复不能顺手改掉 market_cause 原有的标签语义。"""
    label = _assessment_label_for_fallback("market_cause")
    for wording in _MARKET_CAUSE_WORDING:
        assert wording in label


def test_two_fallback_kinds_do_not_share_one_label() -> None:
    """两种 fallback 必须给出不同标签——这正是原实现的缺陷。"""
    assert _assessment_label_for_fallback(
        "general_finance"
    ) != _assessment_label_for_fallback("market_cause")


def test_no_fallback_uses_default_label() -> None:
    """未走 fallback（kind 为 None）时用常规标签，不得自称降级。"""
    label = _assessment_label_for_fallback(None)
    assert label == _DEFAULT_ASSESSMENT_LABEL
    for wording in _MARKET_CAUSE_WORDING:
        assert wording not in label
    assert "仍待补全" not in label


def test_unknown_kind_falls_back_to_default_label() -> None:
    """新增 fallback 种类而忘记登记标签时，退回常规标签而不是 KeyError。

    fail-safe 方向的选择：宁可少一句降级说明，也不能让标签查表把整轮回答炸掉。
    """
    assert _assessment_label_for_fallback("some_future_kind") == (
        _DEFAULT_ASSESSMENT_LABEL
    )
