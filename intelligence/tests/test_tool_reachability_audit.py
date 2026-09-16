"""工具可达性审计的 pytest 侧复挂（spec §7.2 验收第 2 条）。

pre-commit 那条 hook 依赖主树 venv 解释器的绝对路径，换机会挂；测试跑在 venv 里
没有这个问题。同一判据挂两处，是因为它保护的东西（生产装配漏接一根线，
而所有测试仍然全绿）恰恰是那种没人会主动去查的故障。
"""

from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from scripts.audit_tool_reachability import audit  # noqa: E402
from scripts import audit_tool_reachability as reachability  # noqa: E402


def test_no_declared_tool_is_structurally_unreachable() -> None:
    """声明了却装配不出来 = 生产里永远调不到。"""

    declared, assembled, unreachable, conditional = audit()

    assert unreachable == [], (
        f"以下工具声明了但生产装配够不着：{unreachable}。"
        "它们在生产里永远不会被调起，而其它测试不会发现——"
        "测试注册表是各测试自己拼的，不走 build_episode_registry。"
    )
    # 声明的每一个要么无条件装配、要么条件装配，没有第三种
    assert set(declared) == set(assembled) | set(conditional)


def test_audit_is_not_a_tautology() -> None:
    """判据必须取自独立于声明的那一侧。

    初版拿声明本身合成装配输入，unreachable 恒空、永不报警，还报过一次
    「12/12 一致」的假绿。这条钉住的是：装配名单**能够**与声明不同。
    memory_lookup 需要 memory_user 才装配得出来，所以无条件装配那档
    必然真子集于声明——恒真式做不到这一点。
    """

    declared, assembled, _unreachable, conditional = audit()

    assert conditional, "条件装配档为空，判据可能又退化成照镜子了"
    assert set(assembled) < set(declared), "无条件装配应是声明的真子集"


def test_history_requires_intent_then_session_in_real_assembly(tmp_path) -> None:
    without, _context, session = reachability._history_probe(
        tmp_path / "without", with_session=False
    )
    assert session is None
    assert "history_query" in without.names()
    assert "read_history_result" not in without.names()
    assert "save_history_research" not in without.names()
    with_session, context, session = reachability._history_probe(
        tmp_path / "with", with_session=True
    )
    assert session is not None
    assert context.history_intent is not None
    assert {"history_query", "read_history_result", "save_history_research"} <= set(
        with_session.names()
    )
    report = reachability.audit_report()
    assert report["capability_by_tool"]["history_query"] == "finance_query"
    assert "history_intent" in report["conditional_requirements"]["history_query"]
    assert "HistorySession" in report["conditional_requirements"]["read_history_result"]


def test_history_tools_execute_through_production_registry_on_local_fixture(
    tmp_path,
) -> None:
    registry, context, session = reachability._history_probe(
        tmp_path, with_session=True
    )
    queried = registry.execute(
        "history_query",
        {
            "operation": "compute_history",
            "entity_codes": ["AUDIT.FP"],
            "start": "2026-08-03",
            "end": "2026-08-04",
            "features": ["return_pct"],
        },
        context=context,
        step_id="query",
    )
    assert queried.trace.status == "success"
    ref = queried.telemetry["result_ref"]
    assert session.read(ref)["rows"][0]["entity_code"] == "AUDIT.FP"
    read = registry.execute(
        "read_history_result", {"result_ref": ref}, context=context, step_id="read"
    )
    assert read.trace.status == "success"
    saved = registry.execute(
        "save_history_research",
        {
            "draft": {
                "question": "装配历史研究候选",
                "purpose": "retrospective_discovery",
                "entity_ids": ["AUDIT.FP"],
                "source_refs": [queried.telemetry["query_id"]],
                "hypotheses": [
                    {
                        "hypothesis_id": "audit-h1",
                        "statement": "保留候选观察",
                        "source_case_refs": [ref],
                    }
                ],
            }
        },
        context=context,
        step_id="save",
    )
    assert saved.trace.status == "success"
    assert (
        session.read(saved.telemetry["result_ref"])["draft"]["hypotheses"][0][
            "hypothesis_id"
        ]
        == "audit-h1"
    )


def test_audit_still_detects_declared_but_unwired_tool(monkeypatch) -> None:
    monkeypatch.setitem(
        reachability._DEFAULT_TOOL_METADATA,
        "unwired_audit_probe",
        (
            "finance_query",
            "declared without a production runner",
            "historical",
            frozenset(),
        ),
    )
    assert "unwired_audit_probe" in reachability.audit_report()["unreachable"]
