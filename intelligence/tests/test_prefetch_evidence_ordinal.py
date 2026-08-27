"""进场预取行必须带 E 号递给模型：离线锁，不打生产库。

失败形状（2026-08-21 Gate 1，创新药发酵题 `run_20260821_015459_794701`）：
预取把 2026-06-29..08-07 全窗口逐日行摆上桌，且它们**先**进证据账本，
按 ``evidence_ordinal_table`` 稳拿 ``E1``/``E2``——但
``format_opening_prefetch_message`` 只拼 ``title + detail``，把号丢了。
模型于是写「预取，无证据序号」，判官按「数字必须有 evidence_id」
把 6-29 / 7-15 这些**真话**判成「发明历史行情」逐句删掉，
一道要求回溯发酵的题只剩最后 4 天。

修的是呈现层（号本来就有，只是没写给模型看），
**不动**判官那条「数字要有出处」的规矩——那条是对的。
"""

from __future__ import annotations

import re

from intelligence.services.agent_research import AgentEvidence, evidence_content_hash
from intelligence.services.asof_prefetch import (
    PrefetchItem,
    evidence_from_prefetch,
    format_opening_prefetch_message,
)
from intelligence.services.episode_protocol import (
    evidence_ordinal_table,
    resolve_evidence_refs,
)

_AXIS = PrefetchItem(
    tool="finance_query",
    title="创新药 双红时间轴",
    detail=(
        "板块=创新药；窗口 2026-06-29..2026-08-07；"
        "口径 pct_chg>0 且 diff_ratio>10 且 amount>500\n"
        "交易日=2026-06-29；涨跌幅=6.08；成交额亿=1239.13；边际量=57.95；双红=是\n"
        "交易日=2026-08-07；涨跌幅=4.86；成交额亿=1396.3；边际量=46.08；双红=是"
    ),
    source_date="2026-08-07",
)
_MAINLINE = PrefetchItem(
    tool="mainline_context",
    title="主线总览降级说明",
    detail="问句日 2026-08-07 未预取 runtime 当日主线总览；已用 创新药 双红时间轴替代。",
    source_date="2026-08-07",
)


def _tool_evidence(detail: str) -> AgentEvidence:
    """模拟模型自己跑 finance_query 拿到的行，排在预取之后。"""

    item = AgentEvidence(
        tool="finance_query",
        title="板块日频行情",
        detail=detail,
        source="本地结构化数据 · 板块日频行情",
        source_date="2026-08-07",
        evidence_tier="L4_structured",
    )
    return AgentEvidence(**{**item.__dict__, "content_hash": evidence_content_hash(item)})


def _labelled(message: str) -> dict[str, str]:
    """从开场消息里抽 ``标题 → E 号``。"""

    found: dict[str, str] = {}
    for line in message.splitlines():
        match = re.match(r"^\[(E[1-9][0-9]{0,2})\]\s*(.+)$", line.strip())
        if match:
            found[match.group(2).strip()] = match.group(1)
    return found


def test_opening_message_labels_each_prefetch_item_with_ordinal() -> None:
    """每条预取行都要带号，模型才引用得到。这是修前会红的那条。"""

    evidence = evidence_from_prefetch((_AXIS, _MAINLINE))
    message = format_opening_prefetch_message(evidence)

    labels = _labelled(message)
    assert labels.get("创新药 双红时间轴") == "E1"
    assert labels.get("主线总览降级说明") == "E2"


def test_opening_ordinals_match_registry_after_tool_evidence_appends() -> None:
    """开场看到的号 == 终局注册表里的号。禁止第二套编号来源。"""

    prefetch = evidence_from_prefetch((_AXIS, _MAINLINE))
    full = prefetch + (
        _tool_evidence("交易日=2026-08-07；涨跌幅=4.86"),
        _tool_evidence("交易日=2026-08-06；涨跌幅=-0.15"),
    )

    table = evidence_ordinal_table(full)
    labels = _labelled(format_opening_prefetch_message(prefetch))

    for item in prefetch:
        assert labels[item.title] == table[item.content_hash]
    # 工具证据仍排在预取之后，预取不被挤号
    assert table[full[2].content_hash] == "E3"


def test_model_can_cite_prefetch_ordinal_and_judge_resolves_it() -> None:
    """模型写 E1 时，绑定解析必须落到预取那条 hash 上（判官因此不再判无出处）。"""

    prefetch = evidence_from_prefetch((_AXIS, _MAINLINE))
    full = prefetch + (_tool_evidence("交易日=2026-08-07；涨跌幅=4.86"),)

    labels = _labelled(format_opening_prefetch_message(prefetch))
    cited = labels["创新药 双红时间轴"]

    resolved = resolve_evidence_refs([cited], full)
    assert resolved == (_AXIS.to_evidence().content_hash,)


def test_message_still_declares_prefetch_is_not_a_tool_call() -> None:
    """带号之后仍要说明它不是工具调用，别让模型当成自己跑过的收据。"""

    message = format_opening_prefetch_message(evidence_from_prefetch((_AXIS,)))
    assert "不是工具调用" in message


def test_items_without_hash_do_not_get_a_fabricated_ordinal() -> None:
    """认不出来就不发号（fail closed），绝不自己编一个号。"""

    message = format_opening_prefetch_message((_AXIS, _MAINLINE))
    assert _labelled(message) == {}
    assert "创新药 双红时间轴" in message
