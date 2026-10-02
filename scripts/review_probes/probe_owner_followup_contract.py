"""Diagnose a specialized follow-up rejected for a duplicate, unrecognized output ID.

Run with the workbench Python, from any directory:
    python scripts/review_probes/probe_owner_followup_contract.py --output <new-directory>

Uses the real in-process Workbench HTTP entry with isolated fixture/users, no
providers or Keychain, and a Python socket audit guard (including subprocesses).
Records frame inheritance, the owner contract and pre-fail-closed answer. A pure
counterfactual removes only direct_answer when its declared alias already exists;
it never changes the verdict returned to the application. This is backend diagnosis,
NOT browser E2E, semantic answer acceptance, or an OS-level network sandbox.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ("请个股深挖英维克的液冷业务", "那它的主要风险和下一步验证是什么？")


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = out / "fixture"
    shutil.copytree(ROOT / "intelligence/tests/fixtures/chat_workbench_repo", fixture)
    for key in list(os.environ):
        if key.endswith("API_KEY") or key in ("FWP_MODEL_PROFILE", "FWP_RESOURCE_PROFILE"):
            os.environ.pop(key, None)
    os.environ.update({
        "WORKBENCH_REPO_ROOT": str(fixture), "FINANCE_WS": str(fixture),
        "KB_VAULT": str(fixture / "wiki"), "FORESIGHT_USER": "default",
        "FORESIGHT_USERS_DIR": str(out / "users"), "FORESIGHT_EPISODE_STORE": str(out / "episodes"),
        "MARKET_FEATURE_STORE_DB": str(out / "absent-market.duckdb"),
        "WORKBENCH_TEST_RUN_DELAY_MS": "0", "FORESIGHT_LLM_KEYCHAIN": "0",
    })
    guard = out / "guard"
    guard.mkdir()
    network_log = out / "network-denials.jsonl"
    network_log.touch()
    guard_code = (
        "import json, os, sys\n"
        "def deny_network(event, args):\n"
        "    if event in {'socket.connect', 'socket.sendto', 'socket.getaddrinfo'}:\n"
        f"        with open({str(network_log)!r}, 'a', encoding='utf-8') as log:\n"
        "            log.write(json.dumps({'pid': os.getpid(), 'event': event}) + '\\n')\n"
        "        raise RuntimeError('offline owner probe: physical network denied')\n"
        "sys.addaudithook(deny_network)\n"
    )
    (guard / "sitecustomize.py").write_text(guard_code, encoding="utf-8")
    os.environ["PYTHONPATH"] = str(guard) + os.pathsep + str(ROOT)
    exec(compile(guard_code, str(guard / "sitecustomize.py"), "exec"), {})
    sys.path.insert(0, str(ROOT))
    from fastapi.testclient import TestClient
    from intelligence.api.app import create_app
    from intelligence.runtime import conversation_orchestrator as co
    from intelligence.services import llm_refine, task_fulfillment as tf, turn_controller as tc
    from intelligence.services.llm_settings import SessionLLMSettings

    assert llm_refine.detect_providers() == (), "provider configured: refusing replay"
    trace: list[dict] = []
    evaluations: list[dict] = []

    def observe_frame(stage, original):
        def observed(*args, **kwargs):
            result = original(*args, **kwargs)
            event = {"stage": stage, "result": result.to_dict()}
            if stage == "rebase_task_frame":
                event["input_frame"] = args[0].to_dict()
                event["required_outputs_argument"] = list(kwargs.get("required_outputs", ()))
            elif stage == "build_turn_intent":
                event["input_envelope_outputs"] = list(args[1].required_outputs)
                previous = kwargs.get("previous_intent")
                event["previous_intent"] = previous.to_dict() if previous else None
            trace.append(event)
            save(out / "contract-trace.json", trace)
            return result
        return observed

    original_owner_outputs = co._specialized_owner_required_outputs

    def owner_outputs(output, frame):
        result = original_owner_outputs(output, frame)
        contract = output.answer_contract if output else None
        trace.append({
            "stage": "specialized_owner_required_outputs", "frame": frame.to_dict(),
            "contract_outputs": list(contract.required_outputs) if contract else None,
            "contract_frame_hash": contract.task_frame_hash if contract else None,
            "evaluated_outputs": [item.output_id for item in result],
        })
        save(out / "contract-trace.json", trace)
        return result

    original_evaluate = tf.evaluate_answer_spec_fulfillment

    def evaluate(**kwargs):
        actual = original_evaluate(**kwargs)
        outputs = kwargs["required_outputs"]
        known = {item.output_id for item in outputs}
        deduplicated = tuple(
            item for item in outputs
            if item.output_id != "direct_answer"
            or co._LEGACY_OUTPUT_ALIASES.get("direct_answer") not in known
        )
        counterfactual = original_evaluate(**{**kwargs, "required_outputs": deduplicated})
        spec = kwargs["answer_spec"]
        claims = (*spec.summary, *spec.verified_facts, *spec.counter_evidence, *spec.gaps,
                  *spec.triggers, *spec.candidate_facts,
                  *(claim for company in spec.company_table for claim in company.claims))
        event = {
            "question": kwargs["question"], "answer_before_gate": kwargs["answer_text"],
            "answer_spec_before_gate": spec.to_dict(),
            "required_outputs": [asdict(item) for item in outputs],
            "candidate_ids": {item.output_id: [claim.claim_id for claim in tf._claim_candidates(
                item.output_id, claims)] for item in outputs},
            "actual": actual.to_dict(),
            "diagnostic_only_deduplicated": counterfactual.to_dict(),
        }
        evaluations.append(event)
        save(out / "gate-evaluations.json", evaluations)
        return actual  # Observation must not wash the real failure green.

    app = create_app(repo_root=fixture, llm_settings=SessionLLMSettings(credential_store=None))
    with (
        patch.object(tc, "build_task_frame", observe_frame("build_task_frame", tc.build_task_frame)),
        patch.object(tc, "build_turn_intent", observe_frame("build_turn_intent", tc.build_turn_intent)),
        patch.object(tc, "rebase_task_frame", observe_frame("rebase_task_frame", tc.rebase_task_frame)),
        patch.object(co, "_specialized_owner_required_outputs", owner_outputs),
        patch.object(tf, "evaluate_answer_spec_fulfillment", evaluate),
        TestClient(app) as client,
    ):
        response = client.post("/api/conversations", json={"user": "default"})
        response.raise_for_status()
        cid = response.json()["conversation_id"]
        for index, question in enumerate(QUESTIONS, 1):
            response = client.post(f"/api/conversations/{cid}/messages", json={
                "content": question, "user": "default", "skill_mode": "manual",
                "selected_skill_ids": ["stock-deep-dive"],
            })
            response.raise_for_status()
            save(out / f"post-{index}.json", response.json())
            deadline = time.monotonic() + 30
            while True:
                response = client.get(f"/api/conversations/{cid}/messages", params={"user": "default"})
                response.raise_for_status()
                messages = response.json()
                assistants = [message for message in messages if message["role"] == "assistant"]
                if len(assistants) == index and assistants[-1]["status"] in {"completed", "failed", "cancelled"}:
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError(f"turn {index} did not settle")
                time.sleep(0.05)
            save(out / f"messages-{index}.json", messages)
        last = assistants[-1]
    source_paths = (
        "intelligence/services/task_frame.py", "intelligence/services/turn_controller.py",
        "intelligence/services/research_contract.py", "intelligence/services/task_fulfillment.py",
        "intelligence/runtime/conversation_orchestrator.py", "intelligence/workbench_skills/research_owner.py",
    )
    result = {
        "head": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
        "dirty_status": subprocess.check_output(["git", "-C", str(ROOT), "status", "--short"], text=True),
        "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths},
        "scope": "instrumented offline ASGI backend; counterfactual never returned to application",
        "status": last["status"], "content": last.get("content"), "turn_intent": last.get("turn_intent"),
        "body_sha256": hashlib.sha256(last.get("content", "").encode()).hexdigest(),
        "network_denials": network_log.read_text(encoding="utf-8").splitlines(),
        "providers": [], "real_model_requests": 0,
        "actual_verdicts": [event["actual"] for event in evaluations],
        "diagnostic_only_verdicts": [event["diagnostic_only_deduplicated"] for event in evaluations],
    }
    save(out / "result.json", result)
    print(json.dumps({key: result[key] for key in (
        "head", "scope", "status", "body_sha256", "network_denials", "real_model_requests",
    )}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
