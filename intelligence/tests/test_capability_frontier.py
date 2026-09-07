"""能力 frontier 向量：七个轴从落盘工件投影，缺件留 None 不写 0（同题重跑六遍的形状钉在这里）。"""

from __future__ import annotations

import json
from pathlib import Path

from intelligence.eval.capability_frontier import (
    frontier_vector,
    main,
    render_markdown,
)


def _event(sequence: int, kind: str, at: str, **payload: object) -> dict[str, object]:
    return {"sequence": sequence, "kind": kind, "payload": {"at": at, **payload}}


def _write_run(
    tmp_path: Path,
    *,
    run_id: str = "run_1",
    with_branch_trace: bool = True,
    stop_reason: str = "model_finish",
    ledger_left: float = 350.0,
    with_report: bool = True,
) -> Path:
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    branch_payload: dict[str, object] = {
        "branch_id": "branch-1",
        "goal": "甲",
        "status": "partial",
        "evidence_count": 20,
        "gap_count": 2,
        "llm_calls": 4,
        "tool_calls": 9,
        "origin": "tool",
    }
    if with_branch_trace:
        branch_payload.update(
            {
                "stop_reason": "invalid_model_finish",
                "budget": {
                    "allocated_calls": 10, "consumed_calls": 9, "allocated_seconds": 150.0,
                    "remaining_seconds": 71.4, "batch_call_cap": 4,
                },
                "batches": [
                    {"index": 1, "requested": 5, "succeeded": 4, "rejected_by_cap": 1, "timed_out": 0,
                     "errored": 0, "rejected_other": 0, "tools": ["news_search", "web_search", "kb_search", "l3_lookup", "graph_lookup"]},
                    {"index": 2, "requested": 5, "succeeded": 4, "rejected_by_cap": 1, "timed_out": 0,
                     "errored": 0, "rejected_other": 0, "tools": ["web_fetch"] * 5},
                ],
                "invalid_actions": [
                    {"reason": "unknown required output: window_progress", "code": "unknown_output",
                     "kind": "integrity", "disposition": "integrity_violation"}
                ],
            }
        )
    telemetry: dict[str, object] = {"refused_reason": "", "branches": [branch_payload]}
    if with_branch_trace:
        telemetry["root_budget"] = {
            "before": {"remaining_calls": 40, "remaining_seconds": 530.0},
            "after_branches": {"remaining_calls": 30, "remaining_seconds": 530.0},
        }
    episode = {
        "contract": {"allowed_capabilities": ["finance_query", "news_search", "web_search", "sub_research"]},
        "outcome": {
            "status": "completed" if stop_reason != "deadline_exhausted" else "partial",
            "stop_reason": stop_reason,
            "evidence": [{"content_hash": f"h{i}"} for i in range(30)],
            "bindings": [
                {"output_id": "a", "evidence_hashes": ["h1", "h2"]},
                {"output_id": "b", "evidence_hashes": ["h2", "h3"]},
            ],
            "usage": {"llm_calls": 4, "tool_calls": 11, "input_tokens": 400000, "output_tokens": 9000},
        },
        "events": [
            _event(1, "task", "2026-09-07T10:56:56.000+08:00"),
            _event(2, "model_turn", "2026-09-07T10:57:06.000+08:00", tool_calls=[{}, {}]),
            _event(3, "branch_started", "2026-09-07T10:57:06.100+08:00", branch_id="branch-1"),
            _event(4, "branch_completed", "2026-09-07T10:58:58.000+08:00", **branch_payload),
            _event(5, "tool_request", "2026-09-07T10:58:58.100+08:00", name="finance_query"),
            _event(6, "tool_result", "2026-09-07T10:58:58.200+08:00", tool="finance_query"),
            _event(7, "tool_request", "2026-09-07T10:58:58.300+08:00", name="sub_research"),
            _event(8, "tool_result", "2026-09-07T10:58:58.400+08:00", tool="sub_research",
                   elapsed_ms=111757.9, telemetry=telemetry),
            _event(9, "finish", "2026-09-07T11:00:06.600+08:00", status="completed", stop_reason=stop_reason),
        ],
        "phase_trace": {"transitions": [{"to_phase": "completed", "remaining_seconds": ledger_left}]},
        "repair_attempts": 1,
        "repair_cycles": 1,
        "structural_verifier": {"verified_status": "completed"},
        "semantic_verifier": {"judge_status": "repaired"},
    }
    (run_dir / "continuous-episode.json").write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (run_dir / "run.json").write_text(json.dumps({"run_id": run_id, "status": "completed"}), encoding="utf-8")
    if with_report:
        (run_dir / "report.json").write_text(
            json.dumps({"gate_receipt": {"rev": "1010970acc8560df", "judge_status": "repaired",
                                         "judge_unavailable_count": 0, "content_degraded_count": 0,
                                         "verified_status": "completed"}}),
            encoding="utf-8",
        )
    return run_dir


def test_vector_projects_seven_axes_from_persisted_artifacts(tmp_path: Path) -> None:
    vector = frontier_vector(_write_run(tmp_path))

    assert vector.run_id == "run_1" and vector.revision == "1010970acc85"
    # 工具发现：父臂 2 个 + 分支 6 个（去重后 web_fetch 只算一次）= 8 / 提供 4 → 用了比提供还多？
    # 不会——分支用的工具不在父臂契约里也算「用过」，分母是父臂契约；比值 >1 就是分支扩了工具面。
    assert vector.tool_discovery.parent_used == ("finance_query", "sub_research")
    assert vector.tool_discovery.branch_used == ("news_search", "web_search", "kb_search", "l3_lookup", "graph_lookup", "web_fetch")
    assert (vector.tool_discovery.used_distinct, vector.tool_discovery.offered) == (8, 4)
    assert vector.tool_discovery.used_ratio == 2.0
    # 证据产出：父臂 30 条、分支 20 条、绑上 3 个不同 hash。
    assert (vector.evidence_yield.parent_evidence, vector.evidence_yield.branch_evidence, vector.evidence_yield.bound_hashes) == (30, 20, 3)
    # 上下文效率。
    assert vector.context_efficiency.input_tokens_per_llm_call == 100000.0
    # 修复恢复 / 验证完整性。
    assert (vector.repair_recovery.repair_attempts, vector.repair_recovery.finish_accepted) == (1, True)
    assert (vector.verification.judge_status, vector.verification.judge_unavailable_count) == ("repaired", 0)
    # 墙钟：task→finish 190.6s；sub_research 111.8s；账本收尾剩 350；分支让父账本少了 0 秒（口径 C）。
    assert vector.wall_clock.episode_seconds == 190.6
    assert vector.wall_clock.sub_research_seconds == 111.8
    assert vector.wall_clock.ledger_remaining_seconds_at_finish == 350.0
    assert vector.wall_clock.branches_charged_parent_seconds == 0.0
    # 分支健康度：1 支 partial、收尾被拒（invalid 1，码 unknown_output）、帽拒 2/10、9/10 次。
    health = vector.branch_health
    assert (health.count, health.partial, health.finish_accepted, health.invalid_actions) == (1, 1, 0, 1)
    assert (health.rejected_by_cap, health.requested, health.consumed_calls, health.allocated_calls) == (2, 10, 9, 10)
    assert health.remaining_seconds == (71.4,) and health.invalid_action_codes == ("unknown_output",)
    assert vector.notes == (
        "branch finish rejected: unknown_output",
        "branch stop_reasons not accepted: invalid_model_finish",
    )
    assert "(父 2 · 支 6)" in render_markdown([vector])
    payload = vector.to_dict()
    assert payload["wall_clock"]["branches_charged_parent_seconds"] == 0.0
    assert payload["tool_discovery"]["used_ratio"] == 2.0


def test_missing_trace_fields_stay_none_instead_of_zero(tmp_path: Path) -> None:
    """09-07 之前的 run 没有 batches / budget / invalid_actions / root_budget：一律 None，不伪装成 0。"""

    vector = frontier_vector(_write_run(tmp_path, run_id="old_run", with_branch_trace=False, with_report=False))

    health = vector.branch_health
    assert health.count == 1 and health.partial == 1
    assert (health.finish_accepted, health.invalid_actions, health.requested, health.rejected_by_cap) == (None, None, None, None)
    assert (health.allocated_calls, health.consumed_calls, health.remaining_seconds) == (None, None, ())
    assert vector.wall_clock.branches_charged_parent_seconds is None
    assert vector.revision is None
    # 没有 report.json 时验证轴回落到 episode 里的 verifier 字段。
    assert (vector.verification.verified_status, vector.verification.judge_status) == ("completed", "repaired")
    assert vector.verification.judge_unavailable_count is None
    assert "—" in render_markdown([vector])


def test_ledger_exhaustion_with_wall_clock_left_is_called_out(tmp_path: Path) -> None:
    """第 2 遍的形状：stop_reason=deadline_exhausted 而账本秒为 0——向量要在 notes 里点名，别让它躲在 partial 后面。"""

    vector = frontier_vector(_write_run(tmp_path, run_id="run_2", stop_reason="deadline_exhausted", ledger_left=0.0))

    assert vector.repair_recovery.finish_accepted is False
    assert any("ledger seconds exhausted" in note for note in vector.notes)


def test_cli_renders_markdown_and_json(tmp_path: Path, capsys) -> None:
    run_dir = _write_run(tmp_path)
    assert main([str(run_dir), "--format", "md"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("| run | rev |")
    assert "run_1" in out and "0/1/0 · 0 · 1 · 2/10" in out
    assert main([str(run_dir), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["run_id"] == "run_1"
    assert payload[0]["branch_health"]["invalid_action_codes"] == ["unknown_output"]
