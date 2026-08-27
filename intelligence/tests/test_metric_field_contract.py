"""§9.3 指标 ↔ 产物字段的对表门禁。

**单一真源是 spec §9.3 的正文**，本测试从 spec 解析指标清单，
与 `metric_field_contract.CONTRACT` 逐条对齐——spec 加一条而契约没登记即红。
起因是 2026-08-17 一天三次「分析做到一半发现数据不在产物里」。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from intelligence.eval.metric_field_contract import (
    CONTRACT,
    blocking_gaps,
    by_spec_name,
)

_SPEC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-08-15-agent-base-dsh-absorption-design.md"
)


def _spec_metrics() -> list[str]:
    text = _SPEC.read_text(encoding="utf-8")
    m = re.search(r"^### 9\.3 观测指标\n(.*?)^### 9\.4 ", text, re.S | re.M)
    assert m, "spec §9.3 没找到——章节号变了就来改这里，别把门禁删掉"
    return [
        line.strip().lstrip("- ").rstrip("；。")
        for line in m.group(1).splitlines()
        if line.strip().startswith("- ")
    ]


def test_every_spec_metric_is_declared() -> None:
    """spec §9.3 列了、契约没登记 → 红。这是本门禁的主断言。"""

    spec = _spec_metrics()
    assert spec, "解析出 0 条指标，正则或 spec 结构变了"
    declared = by_spec_name()
    missing = [name for name in spec if name not in declared]
    assert missing == [], (
        f"§9.3 新增指标未登记到 metric_field_contract：{missing}。"
        "登记时必须写清 status / locator / 是否 blocks_window。"
    )


def test_no_declaration_without_spec_entry() -> None:
    """反方向：契约里凭空多出一条 spec 没有的 → 红（防止对表自己长出私货）。"""

    spec = set(_spec_metrics())
    extra = [m.spec_name for m in CONTRACT if m.spec_name not in spec]
    assert extra == [], f"契约声明了 §9.3 没有的指标：{extra}"


def test_unavailable_entries_carry_a_reason() -> None:
    """标 unavailable 就必须说明为什么，否则「缺数据」会被读成「已覆盖」。"""

    silent = [
        m.spec_name
        for m in CONTRACT
        if m.status == "unavailable" and not (m.locator.strip() or m.note.strip())
    ]
    assert silent == [], f"unavailable 但没写理由：{silent}"


def test_available_entries_have_a_resolver() -> None:
    status_ok = {"top_level", "derived_from_events"}
    broken = [m.spec_name for m in CONTRACT if m.status in status_ok and m.resolver is None]
    assert broken == [], f"声明可取但没有 resolver：{broken}"


@pytest.mark.parametrize(
    "metric",
    [m for m in CONTRACT if m.resolver is not None],
    ids=lambda m: m.spec_name[:28],
)
def test_resolver_survives_an_empty_arm(metric) -> None:
    """空记录不得抛异常，且**不得把「没数据」返回成 False/0**。

    崩溃臂事件为空时，`0 == 0 + 0` 曾让 Trace 对账假通过——这条钉的就是那个。
    """

    value = metric.resolver({})
    assert value is None or value in (0.0, 1.0) or isinstance(value, (int, float, str, bool)), (
        f"{metric.spec_name} 对空记录返回了意外类型：{value!r}"
    )


def test_empty_arm_never_reports_reconciled_or_recovered() -> None:
    """两条易假绿的必须对空记录返回 None，不是 False/True。"""

    declared = by_spec_name()
    for name in ("Trace 与事件对账完整率", "repair recovery rate", "first model turn timeout rate"):
        resolver = declared[name].resolver
        assert resolver is not None
        assert resolver({}) is None, f"{name} 对空记录不该给出判定"


def test_blocking_gaps_are_explicit() -> None:
    """开窗前必须补的项要能一句话列出来，且不为空时每条都有说明。"""

    gaps = blocking_gaps()
    assert gaps, "若真的一条都不缺，改这条断言并在 PR 里说明依据"
    for m in gaps:
        assert m.note.strip(), f"{m.spec_name} 标了 blocks_window 却没写缺什么"
