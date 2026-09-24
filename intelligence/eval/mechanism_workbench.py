"""Bounded two-conversation observation through the real 8792 product API.

No provider calls, server configuration changes, or automatic message retries.
The server owns research budgets. The client records failures without resampling.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode

from intelligence.eval.live_probe import _request_json, ProbeBlocked, wait_for_run
from intelligence.eval.mechanism_pilot import _read, _store, _write
from intelligence.services.research_validation.contracts import digest

BASE = "http://127.0.0.1:8792"
QUESTION = (
    "请研究中际旭创（300308）：截至2026年9月16日，最近两期已披露的定期报告中，"
    "收入和利润增长是否兑现为经营现金流？应收账款、存货和回款证据支持还是削弱经营质量改善的判断？"
    "请使用实际可获取的公告、财务数据和知识库资料，先说明数据截止期与缺口，"
    "口径不一致不能直接比较，不编造材料没有给出的数据或正常阈值，不提供买卖建议。"
    "输出当前判断、支持证据与关键反证、最值得优先补查的一条证据，以及什么观察会改变判断；"
    "关键数字给出来源和报告期，事实与解释分开。不要把本次研究登记为长期跟踪或投资观点。"
)
INSTRUCTIONS = {
    "summary": "请按事实条目逐条整理，再形成判断和下一步。",
    "mechanism": "请按关键变量之间的传导关系组织，明确主解释、竞争解释、用于区分的观察变量和适用边界，再形成判断和下一步。",
}
ID = re.compile(r"[a-zA-Z0-9_-]+")
FILES = (
    "run.json", "report.json", "answer.md", "trace.jsonl", "summary.json",
    "continuous-episode.json", "llm-context.json", "llm-context.jsonl",
)


def _copy_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def health() -> dict:
    result = _request_json("GET", BASE + "/api/health", timeout=15)
    runtime = result["runtime"]
    if result["status"] != "healthy" or not runtime["code_matches_repo"]:
        raise ValueError("server health/code identity not ready")
    if not runtime["agent_runtime"]["ready"]:
        raise ValueError("agent runtime is not ready")
    return result


def prepare(directory: Path, experiment_id: str) -> dict:
    if not re.fullmatch(r"R-\d{8}-\d{2}", experiment_id):
        raise ValueError("invalid claimed experiment id")
    h = health()
    user_prefix = "mechanism-" + experiment_id.lower()
    users = {arm: user_prefix + "-" + arm for arm in INSTRUCTIONS}
    users_root = Path(h["runtime"]["users_dir"])
    if any((users_root / user).exists() for user in users.values()):
        raise ValueError("fresh isolated users required")
    protocol = {
        "schema_version": "mechanism-workbench/v1", "experiment_id": experiment_id,
        "created_at": datetime.now(timezone.utc).isoformat(), "base_url": BASE,
        "health_before": h, "users": users, "order": ["summary", "mechanism"],
        "messages": {arm: QUESTION + "\n" + instruction for arm, instruction in INSTRUCTIONS.items()},
        "request_options": {"skill_mode": "auto", "perspective_mode": "neutral"},
        "max_initial_messages": 2, "clarification_replies": 0,
        "per_run_client_wait_seconds": 900,
        "runtime_budget": "unchanged_server_default; record_actual_budget_from_artifacts",
        "review_dimensions": ["dated_source_grounding", "counterevidence", "unsupported_thresholds",
                              "next_check_discriminates_explanations", "change_condition", "tool_and_evidence_trace"],
        "limitations": ["one_question", "not_blinded", "retrieval_inputs_not_frozen",
                        "new_test_users_not_personalized", "order_not_counterbalanced"],
        "decision_eligible": False, "promotion_eligible": False,
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    _write(_store(directory), "protocol.json", protocol)
    return protocol


def _token(value: str) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("invalid server identifier")
    return value


def _same_server(protocol: dict) -> dict:
    current = health()
    before = protocol["health_before"]["runtime"]
    for key in ("source_revision", "loaded_tree_fingerprint", "users_dir", "agent_runtime"):
        if current["runtime"][key] != before[key]:
            raise ValueError("server identity changed: " + key)
    return current


def run(directory: Path) -> list[dict]:
    store = _store(directory)
    protocol = _read(store, "protocol.json")
    if protocol["base_url"] != BASE or protocol["implementation_sha256"] != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise ValueError("protocol/code binding changed")
    receipts = []
    for arm in protocol["order"]:
        if (store.root / arm / "receipt.json").exists():
            receipts.append(_read(store, arm + "/receipt.json"))
            continue
        before = _same_server(protocol)
        user = _token(protocol["users"][arm])
        if not _write(store, arm + "/attempt.json", {"protocol_sha256": digest(protocol), "arm": arm}):
            raise ValueError("attempt already claimed; inspect existing run, never repost")
        conversation = _request_json("POST", BASE + "/api/conversations", payload={
            "user": user, "title": protocol["experiment_id"] + " " + arm + " 现金兑现",
        })
        _write(store, arm + "/conversation.json", conversation)
        if conversation.get("user_id") != user:
            raise ValueError("server did not preserve isolated user")
        cid = _token(conversation["conversation_id"])
        started = time.monotonic()
        submitted = _request_json("POST", BASE + f"/api/conversations/{cid}/messages", payload={
            "user": user, "content": protocol["messages"][arm], **protocol["request_options"],
        }, timeout=60)
        _write(store, arm + "/submission.json", submitted)
        rid = _token(submitted["run_id"])
        print(json.dumps({"arm": arm, "conversation_id": cid, "run_id": rid, "status": "submitted"}), flush=True)
        try:
            terminal = wait_for_run(BASE, rid, user=user, timeout=protocol["per_run_client_wait_seconds"])
        except ProbeBlocked:
            cancel = _request_json("POST", BASE + f"/api/runs/{rid}/cancel?" + urlencode({"user": user}))
            _write(store, arm + "/client_timeout_cancel.json", cancel)
            terminal = wait_for_run(BASE, rid, user=user, timeout=120)
        _write(store, arm + "/terminal.json", terminal)
        users_root = Path(before["runtime"]["users_dir"])
        source = users_root / user / "runs" / rid
        hashes = {}
        for name in FILES:
            path = source / name
            if path.is_file() and not path.is_symlink():
                data = path.read_bytes()
                _copy_once(store.root / arm / "artifacts" / name, data)
                hashes[name] = hashlib.sha256(data).hexdigest()
        messages = users_root / user / "conversations" / cid / "messages.jsonl"
        if messages.is_file() and not messages.is_symlink():
            data = messages.read_bytes()
            _copy_once(store.root / arm / "messages.jsonl", data)
            hashes["messages.jsonl"] = hashlib.sha256(data).hexdigest()
        event_path = source / "continuous-episode.json"
        events = json.loads(event_path.read_text()).get("events", []) if event_path.is_file() else []
        tools = Counter(e.get("payload", {}).get("tool", "unknown") for e in events if e.get("kind") == "tool_result")
        after = health()
        receipt = {
            "protocol_sha256": digest(protocol), "arm": arm, "user": user,
            "conversation_id": cid, "run_id": rid, "status": terminal["status"],
            "elapsed_seconds": time.monotonic() - started, "source_directory": str(source),
            "artifact_sha256": hashes, "event_counts": dict(Counter(e.get("kind") for e in events)),
            "tool_results": dict(tools), "health_after": after,
            "same_server_revision": before["runtime"]["source_revision"] == after["runtime"]["source_revision"],
            "decision_eligible": False, "promotion_eligible": False,
        }
        _write(store, arm + "/receipt.json", receipt)
        receipts.append(receipt)
        print(json.dumps({k: receipt[k] for k in ("arm", "run_id", "status", "elapsed_seconds", "tool_results")}), flush=True)
        if terminal["status"] != "completed":
            break
    return receipts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--experiment-id", default="R-20260916-05")
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.directory, args.experiment_id)
        print(json.dumps({"status": "prepared", "protocol_sha256": digest(result)}))
    else:
        run(args.directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
