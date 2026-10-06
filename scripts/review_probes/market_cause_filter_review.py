"""Reproduce a filter review without mistaking a helper defect for a live-route defect.

Run explicitly from a checkout with the workbench interpreter:
    python scripts/review_probes/market_cause_filter_review.py --output-dir <new-dir>

This is a forensic probe, not a production regression gate. A successful exit
means the observations were captured, NOT that the answer filter is correct.
The Episode adapter is a scripted substitute; its delivery uses the real
TurnOrchestrator.run_turn and temporary stores. No model, production data,
network request, or production configuration is used or changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch


QUERY = "本周市场下跌的原因是什么？"
CASES = (
    ("cause_net_selling", QUERY, "机构净卖出增加，是本周市场下跌的原因之一。", "preserve"),
    ("cause_position", QUERY, "基金仓位下降，说明风险偏好回落。", "preserve"),
    ("unsolicited_reduce", QUERY, "建议减持并提高现金比例。", "suppress"),
    ("question_paraphrase", "为什么本周市场下跌？", "建议买入。", "suppress"),
    ("explicit_request", "本周市场下跌的原因是什么？也请给出仓位建议。", "仓位建议应取决于风险承受能力。", "preserve"),
    ("neutral_cause_control", QUERY, "主要原因是风险偏好收缩。", "preserve"),
    ("advice_control", QUERY, "建议买入。", "suppress"),
)


def run_probe(output: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(root))
    with tempfile.TemporaryDirectory(prefix="market-cause-review-") as tmp:
        state = Path(tmp)
        isolated_env = {
            "FINANCE_WS": str(state),
            "FINANCE_DATA_ROOT": str(state),
            "MARKET_FEATURE_STORE_DB": str(state / "absent.duckdb"),
            "FORESIGHT_USER": "review-probe",
            "FORESIGHT_USERS_DIR": str(state / "users"),
            "FORESIGHT_EPISODE_STORE": str(state / "episodes"),
            "SUBCONSCIOUS_VAULT": str(state / "vault"),
            "FINANCE_REJUDGE_PENDING_INDEX": str(state / "rejudge.jsonl"),
            "ENTITY_ANCHOR_SECURITIES_DB": "0",
        }
        with patch.dict(os.environ, isolated_env), patch(
            "socket.socket.connect", side_effect=AssertionError("probe must stay offline")
        ):
            from intelligence.runtime import conversation_orchestrator as co
            from intelligence.runtime.continuous_turn_adapter import ContinuousTurnResult
            from intelligence.services.conversation_store import ConversationStore
            from intelligence.services.research_contract import TurnIntent
            from intelligence.services.run_store import RunStore
            from intelligence.services.task_frame import TaskFrame
            from intelligence.services.turn_controller import TurnDecision

            observations = []
            for name, query, text, expectation in CASES:
                actual = co._sanitize_market_cause_answer_text(text, query)
                meets_expectation = actual == text if expectation == "preserve" else not actual
                observations.append({
                    "case": name, "query": query, "input": text,
                    "expected_behavior": expectation, "actual": actual,
                    "meets_expectation": meets_expectation,
                })

            text = "机构净卖出增加，是本周市场下跌的原因之一。\n基金仓位下降，说明风险偏好回落。"
            frame = TaskFrame(
                raw_question=QUERY, user_goal="解释市场下跌原因",
                question_type="market_cause", subject="A股市场",
                subject_kind="market_pattern", market_scope="A股", timeframe="本周",
                required_outputs=("direct_assessment", "evidence_boundary"),
                assumptions=(), ambiguities=(), clarification_question=None,
                evidence_policy="time_aligned_market_cause", confidence=1.0,
            )
            intent = TurnIntent(
                primary_subject=frame.subject, secondary_topics=(),
                question_type=frame.question_type, answer_owner=None,
                comparison_entities=(), inherited_from_turn=None,
                timeframe=frame.timeframe, required_outputs=frame.required_outputs,
                task_frame_hash=frame.task_frame_hash,
            )

            def controller(*_args, **_kwargs):
                return TurnDecision(
                    lane="research", needs_retrieval=True, needs_memory=False,
                    needs_template=False, question_type=frame.question_type,
                    capabilities=("market_news",), task_frame=frame, turn_intent=intent,
                )

            class ScriptedAdapter:
                def handle(self, *, frame, control):
                    assert frame.task_frame_hash == control.task_frame.task_frame_hash
                    return ContinuousTurnResult(
                        handled=True, status="completed", answer=text, as_of=None,
                        citations=(), warnings=(), private_artifact={}, events=(),
                    )

            conversations = ConversationStore("review-probe", root=state / "conversations")
            runs = RunStore("review-probe", root=state / "runs")
            conversation = conversations.create_conversation()
            run = runs.create_run(QUERY, "ask", session_id=conversation.conversation_id)
            conversations.append_message(conversation.conversation_id, "user", QUERY, run_id=run.run_id)
            assistant = conversations.append_message(
                conversation.conversation_id, "assistant", "", status="pending", run_id=run.run_id,
            )
            conversations.update_summary(conversation.conversation_id, "", last_run_id=run.run_id)

            def forbidden(*_args, **_kwargs):
                raise AssertionError("legacy path must not run when Episode handled the turn")

            orchestrator = co.TurnOrchestrator(
                repo_root=state, conversation_store=conversations, run_store=runs,
                answer_query_fn=forbidden, route_skills_fn=forbidden,
                lane_answer_fn=forbidden, turn_controller_fn=controller,
                continuous_turn_adapter=ScriptedAdapter(),
            )
            with patch.object(co, "_sanitize_market_cause_answer_text", side_effect=forbidden) as spy:
                result = orchestrator.run_turn(
                    conversation_id=conversation.conversation_id, run_id=run.run_id,
                    assistant_message_id=assistant.message_id, query=QUERY,
                    skill_mode="auto", selected_skill_ids=[],
                )
            saved = next(
                item for item in conversations.load_messages(conversation.conversation_id)
                if item.message_id == assistant.message_id
            )
            boundary = {
                "adapter": "scripted_handled_result_not_real_model",
                "question_type": frame.question_type,
                "legacy_filter_calls": spy.call_count,
                "status": result.status,
                "input": text,
                "delivered": result.content,
                "persisted": saved.content,
                "both_cause_statements_preserved": all(line in result.content for line in text.splitlines()),
            }
            assert boundary["legacy_filter_calls"] == 0
            assert boundary["both_cause_statements_preserved"]
            assert saved.content == result.content
            assert result.status == "completed"

    source = root / "intelligence/runtime/conversation_orchestrator.py"
    report = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "helper_behavior_and_scripted_episode_delivery_only",
        "checkout_status": subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"], text=True,
        ).splitlines(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "executable": sys.executable,
        "revision": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "python": sys.version, "cases": observations, "episode_delivery_boundary": boundary,
        "not_verified": ["natural_model_quality", "legacy_end_to_end_answer", "live_service_answer", "other_answer_gates"],
    }
    (output / "filter-results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    run_probe(parser.parse_args().output_dir)
