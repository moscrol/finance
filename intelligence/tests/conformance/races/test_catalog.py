"""目录表与夹具互锁：表里每条竞态都有对应模块，模块里两序各至少一个测试。

删夹具不删行、加行不写夹具，这里红——目录不能只是一张好看的表。
"""

from __future__ import annotations

import ast
from pathlib import Path

from intelligence.runtime.agent_episode import STEP_PHASES
from intelligence.tests.conformance.races.catalog import RACES, RACES_BY_KEY

_HERE = Path(__file__).resolve().parent


def _test_names(module: str) -> set[str]:
    source = (_HERE / f"{module}.py").read_text(encoding="utf-8")
    return {
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


def test_catalog_has_at_least_eight_races_with_distinct_legal_histories() -> None:
    assert len(RACES) >= 8
    assert len(RACES_BY_KEY) == len(RACES), "key 重复"
    for race in RACES:
        assert race.order_a != race.order_b, race.key
        assert race.legal_history_a != race.legal_history_b, race.key


def test_every_race_has_a_module_with_both_orders() -> None:
    for race in RACES:
        path = _HERE / f"{race.module}.py"
        assert path.exists(), f"{race.key} 没有夹具文件 {race.module}.py"
        names = _test_names(race.module)
        assert any(name.startswith("test_order_a_") for name in names), f"{race.key} 缺 A 序夹具"
        assert any(name.startswith("test_order_b_") for name in names), f"{race.key} 缺 B 序夹具"


def test_every_race_module_is_in_the_catalog() -> None:
    modules = {path.stem for path in _HERE.glob("test_race_*.py")}
    assert modules == {race.module for race in RACES}


def test_step_phases_cover_the_five_effect_boundaries() -> None:
    assert STEP_PHASES == (
        "model_pending",
        "model_settled",
        "before_tool_dispatch",
        "tools_settled",
        "before_finish",
    )
