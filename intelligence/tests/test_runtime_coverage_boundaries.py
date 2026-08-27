"""P3 coverage audit: terminal writes and late-result isolation.

These tests pin *current* wiring. They are not a promise that the
uncovered paths are safe. Do not rewrite ``claim_terminal_run`` or
``QueryPublishGuard`` to make a test green.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from intelligence.runtime.conversation_orchestrator import TurnOrchestrator
from intelligence.services.episode_event_lanes import DURABLE_EVENT_KINDS, LIVE_EVENT_KINDS

_REPO = Path(__file__).resolve().parents[2]
_INTELLIGENCE = _REPO / "intelligence"
_PRODUCTION_ROOTS = (
    _INTELLIGENCE / "runtime",
    _INTELLIGENCE / "services",
    _INTELLIGENCE / "api",
    _INTELLIGENCE / "workbench_skills",
)


def _production_py_files() -> list[Path]:
    files: list[Path] = []
    for root in _PRODUCTION_ROOTS:
        files.extend(path for path in root.rglob("*.py") if path.name != "__pycache__")
    return files


def _index_after(source: str, needle: str) -> int:
    index = source.find(needle)
    assert index >= 0, f"{needle!r} missing from method source"
    return index


def test_late_result_discarded_is_not_a_registered_event_kind() -> None:
    """G6: 诊断 sidecar，不进 Durable / Live 事件表。"""

    assert "late_result_discarded" not in DURABLE_EVENT_KINDS
    assert "late_result_discarded" not in LIVE_EVENT_KINDS


def test_late_result_discarded_sidecar_lives_on_query_ledger_only() -> None:
    """Writer stays on QueryLedger. P4 SLO may read the count, not mint a kind."""

    hits = sorted(
        path.relative_to(_REPO).as_posix()
        for path in _production_py_files()
        if "late_result_discarded" in path.read_text(encoding="utf-8")
    )
    assert hits == [
        "intelligence/services/query_ledger.py",
        "intelligence/services/runtime_slo.py",
    ]


def test_query_publish_guard_is_constructed_only_in_tool_batch() -> None:
    """G6: 生产构造点只有工具批次。

    子研究协调器靠同步排空隔离晚到分支，不另开一扇 guard。repair 的工具
    批次走同一 ``episode_tool_batch`` 构造点。
    """

    constructors: list[str] = []
    for path in _production_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name == "QueryPublishGuard":
                constructors.append(path.relative_to(_REPO).as_posix())
    assert constructors == ["intelligence/runtime/episode_tool_batch.py"]


def test_terminal_publish_paths_claim_before_public_artifacts() -> None:
    """赢家：claim → 写公开文件。输家不得靠 finish_run 吞掉 claimed=False。

    不能给 ``add_artifact`` 加「终态即拒绝」——连续路径必须在 claim 之后落盘。
    """

    for method in (
        TurnOrchestrator._complete_continuous_turn,
        TurnOrchestrator._complete_lane_turn,
        TurnOrchestrator._cancel,
        TurnOrchestrator._fail,
        TurnOrchestrator._run_turn_ledgered,
    ):
        source = inspect.getsource(method)
        assert _index_after(source, "self._claim_terminal_run") < _index_after(
            source, "self.run_store.add_artifact"
        ), method.__name__
        assert "self.run_store.finish_run" not in source, method.__name__


def test_sub_research_coordinator_does_not_grow_a_second_publish_guard() -> None:
    source = (_INTELLIGENCE / "runtime" / "sub_research.py").read_text(
        encoding="utf-8"
    )
    assert "QueryPublishGuard" not in source
    assert "as_completed" in source
