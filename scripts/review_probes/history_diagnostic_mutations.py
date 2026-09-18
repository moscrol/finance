"""Falsify history delivery repairs without source edits or production DB access.

Default suite: diagnostics. --suite succession challenges status/qualifier
co-delivery, observation clocks and recovery. --suite expression challenges
historical intent across prompt, repair, receipt and checkpoint consumers.

Each fresh child changes one imported function in memory, then runs a narrow
regression against temporary fixtures. Exit 0 means every mutation was caught
by a test failure (not an import/setup error). This is author-side test-strength
evidence, not independent QC, model acceptance, or a source-security audit.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/test_history_tool_diagnostics.py"
KIND_TEST = "tests/test_history_argument_repair.py"
MUTATIONS = {
    "erase_diagnostic_delivery": {
        "module": "intelligence.services.research_tool_registry",
        "owner": "ResearchToolRegistry", "function": "execute",
        "old": "if run_result.diagnostics:", "new": "if False:",
        "test": f"{TEST}::test_real_strict_history_validation_diagnostic_can_repair_query",
    },
    "diagnostic_bypasses_fact_gate": {
        "module": "intelligence.services.research_tool_registry",
        "owner": "ResearchToolRegistry", "function": "execute",
        "old": "if history is not None and history.strict_window and spec.name not in {",
        "new": "if history is not None and history.strict_window and not run_result.diagnostics and spec.name not in {",
        "test": f"{TEST}::test_trusted_diagnostic_does_not_restore_disallowed_facts_or_prose",
    },
    "raw_exception_as_diagnostic": {
        "module": "intelligence.services.finance_query",
        "owner": None, "function": "validation_diagnostic",
        "old": 'safe_message = "查询参数未通过校验"', "new": "safe_message = message",
        "test": f"{TEST}::test_validation_diagnostic_does_not_echo_model_prose_or_unknown_error[exception]",
    },
    "silently_infer_market_kind": {
        "module": "intelligence.services.historical_research.query",
        "owner": "HistoryQuerySpec", "function": "from_arguments",
        "old": 'entity_kind = arguments.get("entity_kind", "sector")',
        "new": 'entity_kind = arguments.get("entity_kind", "market" if "000001.SH" in arguments.get("entity_codes", []) else "sector")',
        "test": f"{KIND_TEST}::test_omitted_kind_is_not_silently_inferred_from_code_or_features",
    },
}
DIAGNOSTIC_NAMES = tuple(MUTATIONS)
PAIR_TEST = "tests/test_history_succession_projection.py"
MUTATIONS.update({
    "erase_pair_projection": {
        "module": "intelligence.services.historical_research.episode",
        "owner": None, "function": "_model_projection",
        "old": 'if row.get("record_kind") == "sector_succession":', "new": "if False:",
        "test": f"{PAIR_TEST}::test_saved_live_pairs_deliver_atomic_status_reason_and_actual_observation_dates",
    },
    "immature_means_failed": {
        "module": "intelligence.services.historical_research.succession_projection",
        "owner": None, "function": "succession_atoms",
        "old": '_MEANINGS.get(status, "未知状态，不能判定成败；请核对原件。")',
        "new": '"接力失败，必须先回撤确认"',
        "test": f"{PAIR_TEST}::test_citing_only_pair_status_delivers_reason_to_actual_semantic_review_projection",
    },
    "require_peak_confirmation": {
        "module": "intelligence.services.historical_research.anatomy",
        "owner": None, "function": "_succession",
        "old": "if len(outcome_days) != 5:",
        "new": 'if len(outcome_days) != 5 or before["confirmation_date"] is None:',
        "test": f"{PAIR_TEST}::test_calculator_records_same_peak_next5_dates_without_confirmation_prerequisite",
    },
    "include_source_peak_in_returns": {
        "module": "intelligence.services.historical_research.anatomy",
        "owner": None, "function": "_succession",
        "old": "outcome_days = days[peak_i + 1 : peak_i + 6]", "new": "outcome_days = days[peak_i : peak_i + 5]",
        "test": f"{PAIR_TEST}::test_target_signal_window_excludes_peak_includes_fifth_but_not_sixth_date",
    },
    "target_signal_anchors_returns": {
        "module": "intelligence.services.historical_research.anatomy",
        "owner": None, "function": "_succession",
        "old": "                        outcome_days,\n                        [r for r in grouped[code] if r[\"trade_date\"] in outcome_days],\n                        market=[r for r in market if r[\"trade_date\"] in outcome_days],",
        "new": "                        days[days.index(after[\"signal_date\"]):days.index(after[\"signal_date\"]) + 5],\n                        [r for r in grouped[code] if r[\"trade_date\"] in days[days.index(after[\"signal_date\"]):days.index(after[\"signal_date\"]) + 5]],\n                        market=[r for r in market if r[\"trade_date\"] in days[days.index(after[\"signal_date\"]):days.index(after[\"signal_date\"]) + 5]],",
        "test": f"{PAIR_TEST}::test_calculator_records_same_peak_next5_dates_without_confirmation_prerequisite",
    },
    "missing_calendar_becomes_zero": {
        "module": "intelligence.services.historical_research.succession_projection",
        "owner": None, "function": "_saved_outcome_dates",
        "old": 'if not calendar or not all(isinstance(value, str) for value in (start, end, peak)):\n        return None',
        "new": 'if not calendar or not all(isinstance(value, str) for value in (start, end, peak)):\n        return []',
        "test": f"{PAIR_TEST}::test_legacy_calendar_absence_is_unknown_not_zero_and_later_dates_do_not_expand_window",
    },
    "erase_pair_recovery_priority": {
        "module": "intelligence.services.historical_research.recovery",
        "owner": None, "function": "recovery_evidence_priority",
        "old": "if pairs:", "new": "if False:",
        "test": f"{PAIR_TEST}::test_actual_recovery_retains_all_six_saved_pair_states_before_nav_and_members",
    },
})
SUCCESSION_NAMES = tuple(name for name in MUTATIONS if name not in DIAGNOSTIC_NAMES)
EXPRESSION_TEST = "tests/test_history_expression_contract_boundary.py"
EXPRESSION_MUTATIONS = {
    "drop_history_track_prompt": {
        "module": "intelligence.services.episode_protocol",
        "owner": None, "function": "_question_type_rules",
        "old": "task_frame.question_type,\n        history_intent=context.history_intent,",
        "new": "task_frame.question_type,\n        history_intent=None,",
        "test": f"{EXPRESSION_TEST}::test_original_four_turn_prompts_use_history_not_forward_contracts",
    },
    "drop_history_ranking_prompt": {
        "module": "intelligence.services.episode_protocol",
        "owner": None, "function": "_question_type_rules",
        "old": "conversation_context=context.conversation_context,\n        history_intent=context.history_intent,",
        "new": "conversation_context=context.conversation_context,\n        history_intent=None,",
        "test": f"{EXPRESSION_TEST}::test_original_four_turn_prompts_use_history_not_forward_contracts",
    },
    "drop_history_repair_scope": {
        "module": "intelligence.runtime.continuous_turn_adapter",
        "owner": None, "function": "_with_track_contract_gaps",
        "old": "    merged = merge_track_missing_outputs(",
        "new": "    context = replace(context, history_intent=None)\n    merged = merge_track_missing_outputs(",
        "test": f"{EXPRESSION_TEST}::test_repair_does_not_replace_history_evidence_gaps_with_forward_slots",
    },
    "drop_history_receipt_scope": {
        "module": "intelligence.runtime.continuous_turn_adapter",
        "owner": "ContinuousTurnAdapter", "function": "_run_episode",
        "old": "    artifact = {\n",
        "new": "    context = replace(context, history_intent=None)\n    artifact = {\n",
        "test": f"{EXPRESSION_TEST}::test_actual_adapter_receipts_and_repair_keep_history_missing",
    },
    "drop_history_checkpoint_context": {
        "module": "intelligence.runtime.conversation_orchestrator",
        "owner": "TurnOrchestrator", "function": "_complete_continuous_turn",
        "old": "history_intent=task_frame.history_intent,", "new": "history_intent=None,",
        "test": f"{EXPRESSION_TEST}::test_real_run_turn_passes_inherited_history_to_checkpoint_boundary",
    },
    "erase_history_checkpoint_gate": {
        "module": "intelligence.runtime.conversation_orchestrator",
        "owner": "TurnOrchestrator", "function": "_ingest_track_next_watch",
        "old": "if history_intent is not None:", "new": "if False:",
        "test": f"{EXPRESSION_TEST}::test_orchestrator_blocks_history_before_resolving_user_path_or_calling_writers",
    },
    "erase_history_track_boundary": {
        "module": "intelligence.services.track_contract",
        "owner": None, "function": "parse_track_intent",
        "old": "if history_intent is not None:", "new": "if False:",
        "test": f"{EXPRESSION_TEST}::test_both_checkpoint_writers_reject_history_even_with_registerable_answer[ingest_next_watch]",
    },
    "erase_history_ranking_boundary": {
        "module": "intelligence.services.ranking_contract",
        "owner": None, "function": "parse_ranking_intent",
        "old": "if history_intent is not None:", "new": "if False:",
        "test": f"{EXPRESSION_TEST}::test_both_checkpoint_writers_reject_history_even_with_registerable_answer[ingest_flip_conditions]",
    },
}
MUTATIONS.update(EXPRESSION_MUTATIONS)
SUITES = {"diagnostics": DIAGNOSTIC_NAMES, "succession": SUCCESSION_NAMES, "expression": tuple(EXPRESSION_MUTATIONS)}


def _child(name: str) -> int:
    import pytest

    mutation = MUTATIONS[name]
    module = importlib.import_module(mutation["module"])
    owner = getattr(module, mutation["owner"]) if mutation["owner"] else module
    original = getattr(owner, mutation["function"])
    source = textwrap.dedent(inspect.getsource(original))
    assert source.count(mutation["old"]) == 1, "mutation target drifted"
    source = source.replace(mutation["old"], mutation["new"])
    namespace = {}
    exec(compile(source, f"<mutation:{name}>", "exec"), module.__dict__, namespace)
    setattr(owner, mutation["function"], namespace[mutation["function"]])
    return int(pytest.main(["-q", mutation["test"], "--tb=short"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory; existing evidence is never overwritten")
    parser.add_argument("--child", choices=tuple(MUTATIONS), help=argparse.SUPPRESS)
    parser.add_argument("--suite", choices=tuple(SUITES), default="diagnostics")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    if args.child:
        return _child(args.child)
    if args.output is None:
        parser.error("--output is required")
    args.output.mkdir(parents=True, exist_ok=False)
    mutations = {name: MUTATIONS[name] for name in SUITES[args.suite]}
    source_paths = {
        ROOT / (mutation["module"].replace(".", "/") + ".py")
        for mutation in mutations.values()
    } | {ROOT / "intelligence/services/episode_tools.py", ROOT / TEST, ROOT / KIND_TEST, Path(__file__).resolve()}
    if args.suite == "succession":
        source_paths |= {ROOT / PAIR_TEST, ROOT / "scripts/history_anatomy_arithmetic.py",
                         ROOT / "tests/test_history_market_anatomy.py", ROOT / "tests/test_history_model_projection.py"}
    if args.suite == "expression":
        source_paths |= {ROOT / EXPRESSION_TEST, ROOT / "tests/test_history_live_seams.py",
                         ROOT / "intelligence/tests/test_ranking_contract.py",
                         ROOT / "intelligence/tests/test_research_intent_boundaries.py",
                         ROOT / "intelligence/tests/test_conversation_orchestrator.py"}
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source_paths)}
    results = []
    for name, mutation in mutations.items():
        run = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--child", name],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        log = args.output / f"{name}.txt"
        log.write_text(run.stdout)
        # pytest exit 1 also includes setup errors; require an actual failed test
        # and reject ERROR summaries rather than calling any nonzero exit a kill.
        caught = run.returncode == 1 and "\nFAILED " in run.stdout and "\nERROR " not in run.stdout
        results.append(dict(mutation=name, test=mutation["test"], exit_code=run.returncode,
                            caught=caught, log=log.name, sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
        print(name, "caught" if caught else "NOT CAUGHT / INVALID", flush=True)
    unchanged = all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in source_hashes.items())
    report = dict(
        suite=args.suite,
        scope="author-side in-memory mutation tests; no product source edits, independent QC or live-model claim",
        revision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        dirty_paths=subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).splitlines(),
        interpreter=sys.executable, source_sha256=source_hashes, source_unchanged=unchanged, mutations=results,
    )
    (args.output / "receipt.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return int(not unchanged or not all(result["caught"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
