"""事实行预算按模块轮转分配，位置不决定一个证据层是否可见。

真实咬过一次：日报 skill 自己的 4 个模块就能填满 16 条预算，后追加的知识库锚点
模块于是整块消失——模块在 output.modules 里、引用在 citations 里、answer_spec
里一条都没有，答案正文一个字都不提，而且没有任何告警。
"""
from __future__ import annotations

from intelligence.workbench_skills.contracts import (
    _FACT_LINE_BUDGET,
    _select_fact_lines,
)


def _module(module_id: str, count: int) -> dict:
    return {
        "module_id": module_id,
        "items": [
            {"title": f"{module_id}-{i}", "summary": f"{module_id} 第 {i} 条"}
            for i in range(count)
        ],
    }


def test_a_late_module_still_gets_represented() -> None:
    """前面的模块填满预算时，最后一个模块不能整块消失。"""
    modules = [_module("verbose", 40), _module("anchor", 4)]

    selected = _select_fact_lines(modules)

    assert len(selected) == _FACT_LINE_BUDGET
    assert any("anchor" in line for line in selected)


def test_every_module_contributes_before_any_module_repeats() -> None:
    modules = [_module("a", 5), _module("b", 5), _module("c", 5)]

    selected = _select_fact_lines(modules, limit=3)

    assert [line[0] for line in selected] == ["a", "b", "c"]


def test_budget_is_never_exceeded() -> None:
    modules = [_module(f"m{i}", 20) for i in range(5)]

    assert len(_select_fact_lines(modules)) == _FACT_LINE_BUDGET


def test_duplicate_lines_are_not_counted_twice() -> None:
    same = {"module_id": "x", "summary": "同一句话"}

    selected = _select_fact_lines([same, dict(same, module_id="y")])

    assert selected == ["同一句话"]


def test_short_modules_do_not_waste_budget() -> None:
    """一个模块只有 1 条时，剩下的预算要让给还有内容的模块。"""
    modules = [_module("short", 1), _module("long", 30)]

    selected = _select_fact_lines(modules)

    assert len(selected) == _FACT_LINE_BUDGET
    assert sum(1 for line in selected if "long" in line) == _FACT_LINE_BUDGET - 1
