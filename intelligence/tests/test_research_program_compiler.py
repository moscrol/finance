"""P0-B B1/B2：compile_research_program 是 operators 唯一写入点。

接缝：
- ``compile_research_program`` → ``ResearchProgram``
- ``bind_research_program`` 对 market_watch 与 ``bind_market_watch_pack`` 逐字节回归（多一个 program 字段）
"""

from __future__ import annotations

import ast
from pathlib import Path

from intelligence.services.ask import bind_market_watch_pack, bind_research_program
from intelligence.services.ask_types import AskOptions
from intelligence.services.research_contract import (
    OPERATOR_AGGREGATE_COUNT,
    OPERATOR_CATALOG_PREFLIGHT,
    OPERATOR_CROSS_TABLE,
    OPERATOR_STRICT_DOUBLE_RED,
    ResearchProgram,
    compile_research_program,
)

_SERVICES = Path(__file__).resolve().parents[1] / "services"
_RUNTIME = Path(__file__).resolve().parents[1] / "runtime"


def test_compiler_is_the_only_production_writer_of_operators() -> None:
    found: set[str] = set()
    intelligence_root = Path(__file__).resolve().parents[1]
    for root in (_SERVICES, _RUNTIME):
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            rel = path.relative_to(intelligence_root)
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(fn):
                    if not isinstance(node, ast.Call):
                        continue
                    name = ""
                    if isinstance(node.func, ast.Name):
                        name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        name = node.func.attr
                    if name == "ResearchProgram":
                        found.add(f"{rel.as_posix()}::{fn.name}")
    assert found == {"services/research_contract.py::compile_research_program"}


def test_double_red_question_emits_strict_snapshot_operator() -> None:
    program = compile_research_program(
        "2026-07-23 哪些板块是双红",
        question_class="market_forecast",
    )
    assert OPERATOR_STRICT_DOUBLE_RED in program.operators
    assert program.question_class == "market_forecast"
    assert program.publication_policy == "verified"
    assert not hasattr(program, "synthesis_reserve")
    receipts = {item.definition_id for item in program.definition_receipts}
    assert "DOUBLE_RED_SQL" in receipts
    assert program.program_id
    again = compile_research_program(
        "2026-07-23 哪些板块是双红",
        question_class="market_forecast",
    )
    assert again.program_id == program.program_id


def test_count_question_emits_aggregate_not_detail() -> None:
    program = compile_research_program(
        "今天涨停家数有多少",
        question_class="market_forecast",
    )
    assert OPERATOR_AGGREGATE_COUNT in program.operators
    assert "market.detail_rows" not in program.operators
    intents = {item.intent for item in program.query_recipes}
    assert "aggregate" in intents


def test_cross_table_question_emits_intersection() -> None:
    program = compile_research_program(
        "既在主线又在双红的板块交集是哪些",
        question_class="theme_analysis",
    )
    assert OPERATOR_CROSS_TABLE in program.operators
    assert any(item.intent == "cross_table" for item in program.query_recipes)


def test_market_watch_bind_is_byte_identical_except_program(tmp_path) -> None:
    from intelligence.tests.test_market_watch_component_first import _db

    db = _db(tmp_path)
    options = AskOptions(
        query="2026-07-23 今天市场怎么样",
        market_db_path=db,
        compose=True,
        synthesize=True,
    )
    pack_bound = bind_market_watch_pack(options, frame=None)
    program_bound = bind_research_program(options, frame=None)
    assert program_bound.research_program is not None
    assert OPERATOR_CATALOG_PREFLIGHT in program_bound.research_program.operators
    assert OPERATOR_STRICT_DOUBLE_RED in program_bound.research_program.operators
    assert program_bound.date == pack_bound.date
    assert program_bound.compose == pack_bound.compose
    assert program_bound.synthesize == pack_bound.synthesize
    assert program_bound.supplemental_evidence == pack_bound.supplemental_evidence
    assert program_bound.market_watch_pack == pack_bound.market_watch_pack
    assert program_bound.research_program.fallback_policy == "empty_pool_one_shot"


def test_research_program_is_not_constructed_by_hand() -> None:
    program = compile_research_program("今日复盘", question_class="market_watch")
    assert isinstance(program, ResearchProgram)
    assert program.operators


def test_surface_signals_are_not_operator_ids() -> None:
    from intelligence.services.query_understanding import (
        SIGNAL_DOUBLE_RED,
        surface_research_signals,
    )

    signals = surface_research_signals(
        "2026-07-23 哪些板块是双红",
        question_class="market_forecast",
    )
    assert SIGNAL_DOUBLE_RED in signals
    assert all("." not in item for item in signals)


def test_query_understanding_does_not_write_program_operators() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "query_understanding.py"
    ).read_text(encoding="utf-8")
    assert "market.strict_double_red_snapshot" not in source
    assert "ResearchProgram(" not in source
    from intelligence.services.query_understanding import _research_operators

    old = _research_operators("和历史上类似阶段比，接下来怎么走")
    assert "history_analog" in old
    assert all(not item.startswith("market.") for item in old)


def test_strict_signal_pack_reuses_dual_red_bag(tmp_path) -> None:
    from intelligence.services.market_watch_pack import run_strict_signal_pack
    from intelligence.tests.test_market_watch_component_first import _db

    db = _db(tmp_path)
    program = compile_research_program(
        "2026-07-23 哪些板块是双红",
        question_class="theme_analysis",
    )
    hits = run_strict_signal_pack(
        program,
        query="2026-07-23 哪些板块是双红",
        market_db_path=db,
    )
    by_op = {item.operator: item for item in hits}
    assert OPERATOR_STRICT_DOUBLE_RED in by_op
    assert by_op[OPERATOR_STRICT_DOUBLE_RED].status in {"hit", "empty"}


def test_episode_merges_program_slots_as_advisory() -> None:
    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.task_frame import TaskFrame

    frame = TaskFrame(
        raw_question="2026-07-23 哪些板块是双红",
        user_goal="列出双红板块",
        question_type="theme_analysis",
        subject="双红",
        subject_kind="theme",
        market_scope="A股",
        timeframe="2026-07-23",
        required_outputs=("direct_assessment", "supporting_evidence"),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="theme_multi_layer_evidence",
        confidence=0.8,
    )
    context = build_episode_context(frame, task_id="program-slots")
    by_id = {item.output_id: item for item in context.contract.required_outputs}
    assert "dual_red_snapshot" in by_id
    assert by_id["dual_red_snapshot"].required is False
    assert "direct_assessment" in by_id


def test_production_program_path_does_not_import_switchboard() -> None:
    roots = (
        Path(__file__).resolve().parents[1] / "services",
        Path(__file__).resolve().parents[1] / "runtime",
    )
    watched = {
        "research_contract.py",
        "query_understanding.py",
        "ask.py",
        "market_watch_pack.py",
        "asof_prefetch.py",
        "episode_factory.py",
        "episode_tools.py",
        "conversation_orchestrator.py",
    }
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            if path.name not in watched:
                continue
            if "capability_switchboard" in path.read_text(encoding="utf-8"):
                offenders.append(path.name)
    assert offenders == []
