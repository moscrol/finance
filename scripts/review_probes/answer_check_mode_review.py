"""Observe answer-check flags without calling a model or changing production.

Prevents treating ``ASK_SEMANTIC_JUDGE=off`` as "no checks", or numeric marking
as a whole-verifier "annotate, ask the author once, never delete" experiment.
Runs the real structural/semantic verifier on synthetic, already-seen fixtures.
The injected judge always passes; it is NOT evidence of natural-model quality.

    .venv-workbench/bin/python scripts/review_probes/answer_check_mode_review.py \
        --output-dir <new-private-directory>

Exit zero means observations were captured, not that the checks improve quality.
The output directory and isolated state are retained. Production databases are
not opened; SQLite is allowed only at two fresh, isolated Workbench store paths.
No service is started. Unexpected database/network attempts are blocked/counted.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from unittest.mock import patch


CASES = (
    ("unsupported_threshold", "若成交额跌破1800亿则量能失效。", "现金流仍待核实。"),
    ("wrong_weekday", "7月17日（周四），上证下跌约3.05%。", "2026-07-17 上证指数下跌约3.05%。"),
    ("correct_weekday", "7月17日（周五），上证下跌约3.05%。", "2026-07-17 上证指数下跌约3.05%。"),
    (
        "false_monotonic_path",
        "回看最近5个交易日，成交额从26547.43亿元一路滑落至21949.97亿元。",
        "2026-07-17：成交26547.43亿；2026-07-20：成交27019.21亿；"
        "2026-07-21：成交29569.03亿；2026-07-22：成交26531.66亿；2026-07-23：成交21949.97亿。",
    ),
    ("private_token", "内部标识HASH_PRIVATE_SENTINEL不得外发。", "市场成交额与结构观察。"),
)
SOURCES = (
    "intelligence/services/episode_semantic_verifier.py",
    "intelligence/services/episode_verifier.py",
    "intelligence/services/judge_mode.py",
    "intelligence/services/research_contract.py",
    "intelligence/services/task_fulfillment.py",
    "intelligence/runtime/continuous_turn_adapter.py",
    "intelligence/runtime/conversation_orchestrator.py",
    "intelligence/services/outlook_delivery_gate.py",
    "intelligence/services/public_delivery_gate.py",
    "intelligence/services/stance_pack.py",
    "intelligence/services/conversation_store.py",
    "intelligence/services/run_store.py",
    "intelligence/services/workbench_db.py",
)


def scripted_delivery(state: Path, frame) -> dict[str, object]:
    """Prove the late gate's reachability, not natural routing or author quality."""
    from intelligence.runtime import conversation_orchestrator as co
    from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
    from intelligence.services.conversation_store import ConversationStore
    from intelligence.services.research_contract import TurnIntent
    from intelligence.services.run_store import RunStore
    from intelligence.services.turn_controller import TurnDecision

    text = (
        "直接判断：短期反弹仍需观察后续成交额和市场结构，当前证据尚不足以确认行情反转。\n"
        "不能说已经验证了剧本。\n"
        "证据边界：本探针仅用合成材料，不代表当前市场事实。"
    )
    intent = TurnIntent(
        primary_subject=frame.subject, secondary_topics=(), question_type=frame.question_type,
        answer_owner=None, comparison_entities=(), inherited_from_turn=None,
        timeframe=frame.timeframe, required_outputs=frame.required_outputs,
        task_frame_hash=frame.task_frame_hash,
    )

    def controller(*_args, **_kwargs):
        return TurnDecision(
            lane="research", needs_retrieval=True, needs_memory=False, needs_template=False,
            question_type=frame.question_type, capabilities=("market_data",),
            task_frame=frame, turn_intent=intent,
        )

    class Adapter:
        def handle(self, *, frame, control):
            assert frame.task_frame_hash == control.task_frame.task_frame_hash
            return ContinuousTurnResult(
                handled=True, status="completed", answer=text, as_of=None,
                citations=(), warnings=(), private_artifact={}, events=(),
            )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("legacy or model paths must not run for scripted handled result")

    conversations = ConversationStore("answer-check-review", root=state / "conversations")
    runs = RunStore("answer-check-review", root=state / "runs")
    conversation = conversations.create_conversation()
    cid = conversation.conversation_id
    run = runs.create_run(frame.raw_question, "ask", session_id=cid)
    conversations.append_message(cid, "user", frame.raw_question, run_id=run.run_id)
    message = conversations.append_message(cid, "assistant", "", status="pending", run_id=run.run_id)
    conversations.update_summary(cid, "", last_run_id=run.run_id)
    orchestrator = co.TurnOrchestrator(
        repo_root=state, conversation_store=conversations, run_store=runs,
        answer_query_fn=forbidden, route_skills_fn=forbidden, lane_answer_fn=forbidden,
        turn_controller_fn=controller, continuous_turn_adapter=Adapter(),
    )
    with patch.object(co, "apply_outlook_delivery_gate", wraps=co.apply_outlook_delivery_gate) as gate, patch.object(
        co, "_sanitize_market_cause_answer_text", side_effect=forbidden,
    ) as legacy:
        result = orchestrator.run_turn(
            conversation_id=cid, run_id=run.run_id, assistant_message_id=message.message_id,
            query=frame.raw_question, skill_mode="auto", selected_skill_ids=[],
        )
    saved = next(m for m in conversations.load_messages(cid) if m.message_id == message.message_id)
    return {
        "scope": "scripted_adapter_and_controller_real_orchestrator_not_http_or_natural_model",
        "judge_setting": os.environ["ASK_SEMANTIC_JUDGE"],
        "numeric_mark_setting": os.environ["FINANCE_NUMERIC_CONDITION_MARK"],
        "conversation_id": cid, "run_id": run.run_id, "input": text,
        "delivered": result.content, "persisted": saved.content,
        "status": result.status, "message_status": saved.status,
        "outlook_gate_calls": gate.call_count, "legacy_filter_calls": legacy.call_count,
        "degrades": runs.load_run(run.run_id).degrades,
    }


def run_probe(output: Path) -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    output = output.expanduser().resolve()
    if output == root or root in output.parents:
        raise ValueError("keep forensic output outside the checkout")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    state = output / "isolated-state"
    state.mkdir(mode=0o700)
    sys.path.insert(0, str(root))

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    def fingerprints() -> dict[str, str]:
        return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES}

    revision = git("rev-parse", "HEAD")
    status = git("status", "--porcelain")
    source_before = fingerprints()
    probe_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    attempts: list[str] = []
    sqlite_connect = sqlite3.connect
    isolated_database_opens: list[str] = []
    allowed_databases = {state / name / "workbench.sqlite3" for name in ("conversations", "runs")}

    def isolated_sqlite(database, *args, **kwargs):
        if not isinstance(database, (str, Path)) or Path(database).resolve() not in allowed_databases:
            return blocked_database()
        isolated_database_opens.append(str(Path(database).resolve()))
        return sqlite_connect(database, *args, **kwargs)

    def blocked_connect(*_args, **_kwargs):
        attempts.append("socket_connection_blocked")
        raise AssertionError("answer-check review must remain offline")

    def blocked_database(*_args, **_kwargs):
        attempts.append("database_open_blocked")
        raise AssertionError("answer-check review must not open a database")

    environment = {key: value for key, value in os.environ.items() if key in {"PATH", "LANG", "LC_ALL"}}
    environment.update({
        "HOME": str(state),
        "FINANCE_WS": str(state),
        "FINANCE_DATA_ROOT": str(state),
        "MARKET_FEATURE_STORE_DB": str(state / "absent.duckdb"),
        "FORESIGHT_USERS_DIR": str(state / "users"),
        "FORESIGHT_USER": "answer-check-review",
        "FORESIGHT_EPISODE_STORE": str(state / "episodes"),
        "SUBCONSCIOUS_VAULT": str(state / "vault"),
        "FINANCE_REJUDGE_PENDING_INDEX": str(state / "rejudge.jsonl"),
        "ENTITY_ANCHOR_SECURITIES_DB": "0",
    })
    rows = []
    delivery_rows = []
    with patch.dict(os.environ, environment, clear=True), patch(
        "socket.socket.connect", side_effect=blocked_connect,
    ), patch("socket.socket.connect_ex", side_effect=blocked_connect), patch(
        "duckdb.connect", side_effect=blocked_database,
    ), patch("sqlite3.connect", side_effect=isolated_sqlite):
        from intelligence.services.agent_research import AgentEvidence
        from intelligence.services.agent_runtime import AgentOutcome, AgentUsage, EpisodeEvent, OutputEvidenceBinding
        from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier, semantic_repair_feedback
        from intelligence.services.episode_verifier import verify_episode_outcome
        from intelligence.services.outlook_delivery_gate import (
            apply_market_watch_delivery_gate, apply_outlook_delivery_gate,
        )
        from intelligence.services.research_contract import RequiredOutput, ResearchDeadline, ResearchTaskContract
        from intelligence.services.task_frame import TaskFrame

        frame = TaskFrame(
            raw_question="当前市场怎么看？", user_goal="判断当前市场结构",
            question_type="market_forecast", subject="A股市场", subject_kind="market_pattern",
            market_scope="A股", timeframe="当前", required_outputs=("direct_assessment",),
            assumptions=(), ambiguities=(), clarification_question=None,
            evidence_policy="current_market_scenarios", confidence=0.95,
        )
        contract = ResearchTaskContract(
            task_id="answer-check-review", question=frame.raw_question, subject=frame.subject,
            subject_kind=frame.subject_kind, question_type=frame.question_type,
            required_outputs=(RequiredOutput("direct_assessment", "直接判断", ("market_data",), True),),
            allowed_capabilities=("market_data",), task_frame_hash=frame.task_frame_hash,
        )
        for judge_mode in ("off", "llm"):
            for mark_mode in ("1", "0"):
                os.environ["ASK_SEMANTIC_JUDGE"] = judge_mode
                os.environ["FINANCE_NUMERIC_CONDITION_MARK"] = mark_mode
                for name, sentence, detail in CASES:
                    draft = "直接判断：反弹仍处于短周期窗口。\n" + sentence
                    evidence = AgentEvidence(
                        tool="market_data", title="A股市场快照", detail=detail, source="合成行情材料",
                        source_date="2026-07-17" if "weekday" in name else "2026-07-23",
                        content_hash="HASH_PRIVATE_SENTINEL",
                    )
                    original = AgentOutcome(
                        task_frame_hash=frame.task_frame_hash, status="completed", draft=draft,
                        evidence=(evidence,), traces=(), gaps=(), stop_reason="model_finish",
                        events=(EpisodeEvent(1, "task", {"task_frame_hash": frame.task_frame_hash}),),
                        bindings=(OutputEvidenceBinding("direct_assessment", (evidence.content_hash,)),),
                        # Synthetic metadata, not real consumed calls.
                        usage=AgentUsage(llm_calls=1, tool_calls=1),
                    )
                    structural = verify_episode_outcome(contract, original)
                    calls: list[object] = []

                    def passing_judge(request):
                        calls.append(request)
                        return {"passed": True, "rejected_sentence_indexes": [], "issues": []}

                    result = SemanticEpisodeVerifier(judge_fn=passing_judge).verify(
                        frame=frame, structurally_verified=structural,
                        deadline=ResearchDeadline.from_timeout(30),
                    )
                    rows.append({
                        "case": name, "judge_setting": judge_mode, "numeric_mark_setting": mark_mode,
                        "input_draft": draft, "synthetic_evidence": detail,
                        "structural_status": structural.verified_status,
                        "public_answer": result.public_answer,
                        "input_sentence_verbatim_present": sentence in result.public_answer,
                        "verified_draft": result.verified.outcome.draft,
                        "status": result.status, "judge_status": result.judge_status,
                        "judge_mode_recorded": result.judge_mode, "injected_judge_calls": len(calls),
                        "sentence_verdicts": list(result.sentence_verdicts),
                        "review_feedback": list(semantic_repair_feedback(result)),
                        "issues": list(result.issues),
                    })
                # These helper observations do not claim the full delivery path was run.
                for name, text, question_type in (
                    ("forecast_verification_assertion", "已经验证了剧本。", "market_forecast"),
                    ("forecast_negated_verification", "不能说已经验证了剧本。", "market_forecast"),
                    ("nonforecast_control", "不能说已经验证了剧本。", "company_research"),
                ):
                    receipt = apply_outlook_delivery_gate(text, question_type=question_type)
                    delivery_rows.append({
                        "case": name, "gate": "apply_outlook_delivery_gate",
                        "judge_setting": judge_mode, "numeric_mark_setting": mark_mode,
                        "input": text, "question_type": question_type, **asdict(receipt),
                    })
                for name, grid in (("watch_unregistered", ""), ("watch_registered", "MA20")):
                    text = "按MA20观察趋势。"
                    receipt = apply_market_watch_delivery_gate(text, question_type="market_watch", grid_text=grid)
                    delivery_rows.append({
                        "case": name, "gate": "apply_market_watch_delivery_gate",
                        "judge_setting": judge_mode, "numeric_mark_setting": mark_mode,
                        "input": text, "grid_text": grid, **asdict(receipt),
                    })
        os.environ["ASK_SEMANTIC_JUDGE"] = "off"
        os.environ["FINANCE_NUMERIC_CONDITION_MARK"] = "1"
        delivery = scripted_delivery(state, frame)
    revision_after = git("rev-parse", "HEAD")
    status_after = git("status", "--porcelain")
    source_after = fingerprints()
    probe_after = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "synthetic_same_draft_flag_observations_not_a_quality_experiment",
        "revision": revision, "revision_after": revision_after,
        "status_before": status, "status_after": status_after,
        "identity_stable": (revision == revision_after and status == status_after
                            and source_before == source_after and probe_before == probe_after),
        "executable": sys.executable, "python": sys.version,
        "source_sha256": source_before, "source_sha256_after": source_after,
        "probe_sha256": probe_before, "probe_sha256_after": probe_after,
        "blocked_network_attempts": attempts.count("socket_connection_blocked"),
        "blocked_database_attempts": attempts.count("database_open_blocked"), "real_model_calls": 0,
        "isolated_database_opens": len(isolated_database_opens),
        "isolated_database_paths": sorted(set(isolated_database_opens)),
        "judge_substitute": "injected always-pass function; no author revision performed",
        "rows": rows, "delivery_helper_rows": delivery_rows, "scripted_delivery": delivery,
        "not_verified": ["natural_model_revision", "workbench_http_delivery", "live_configuration",
                         "financial_quality_gain", "all_postprocessing_paths", "other_pr_heads"],
    }
    (output / "mode-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    if attempts or not report["identity_stable"]:
        raise RuntimeError("probe identity drift or unexpected IO attempt; retain failed evidence")
    print(json.dumps({key: report[key] for key in (
        "observed_at", "revision", "identity_stable", "blocked_network_attempts", "blocked_database_attempts",
        "real_model_calls",
    )}, ensure_ascii=False))
    print(f"{len(rows)} verifier + {len(delivery_rows)} helper + 1 scripted delivery at {output / 'mode-results.json'}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    run_probe(parser.parse_args().output_dir)
