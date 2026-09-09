"""00 · 真实能力基线：30 题真实工作题集（20 公开 + 10 密封）的加载、跑批、评审包与汇总。

任务合同：``docs/superpowers/plans/2026-09-09-capability-upgrade/00-capability-benchmark-goal-brief.md``。
评分规则：``docs/verification/2026-09-09-capability-benchmark-00-scoring-rules.md``。

三条硬约束（与规则文一致）：

1. 唯一入口是 Workbench 真实对话门 ``POST /api/conversations`` →
   ``POST /api/conversations/{id}/messages``；不走 CLI ``ask``、不走 ``/api/runs``。
   run 目录里没有 ``continuous-episode.json`` 的题记 ``engine_missing``，不计能力分。
2. 生产 8792 与保留端口一律拒绝；评测用户目录路径必须含 ``capability-benchmark-00``
   才允许从种子重置（防止误删真实用户台账）。
3. 判分要点密封在仓外，仓内只放 sha256；``seal-verify`` 验封失败即停。

子命令：``validate`` / ``overlap`` / ``seal`` / ``seal-verify`` / ``run`` / ``review-pack`` / ``aggregate``。
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import tarfile
import time
from typing import Any
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[2]
VISIBLE_RELATIVE = (
    "intelligence/eval/fixtures/capability-benchmark-2026-09-09.questions.json"
)
SEALED_MANIFEST_RELATIVE = (
    "intelligence/eval/fixtures/capability-benchmark-2026-09-09.sealed-manifest.json"
)
BENCHMARK_ID = "capability-benchmark-00"
SCHEMA_VERSION = 1

CATEGORIES: dict[str, str] = {
    "feel": "盘感翻译",
    "material": "材料理解",
    "calc": "财务计算",
    "compare": "跨公司比较",
    "chain": "产业传导",
    "analog": "历史类比",
    "scenario": "情景更新",
    "counter": "反例推翻",
    "continue": "跨日续研",
    "method": "方法验证",
}
VISIBLE_PER_CATEGORY = 2
HIDDEN_PER_CATEGORY = 1
VISIBLE_COUNT = VISIBLE_PER_CATEGORY * len(CATEGORIES)
HIDDEN_COUNT = HIDDEN_PER_CATEGORY * len(CATEGORIES)
TIERS = frozenset({"standard", "deep"})
RESERVED_PORTS = frozenset({8792, 8793, 8795, 8799, 8801})
USERS_DIR_GUARD = "capability-benchmark-00"
SECOND_REVIEW_RATIO = 0.2
TASK_COMPLETED = ("yes", "partial", "no")
TRI_STATE = ("yes", "no", "na")

# 与既有题集零重叠的比对面。heldout-v1 刻意不在此列：
# intelligence/tests/test_heldout_pool_isolation.py 禁止任何文件引用它。
EXISTING_SET_FILES: tuple[tuple[str, str], ...] = (
    ("acceptance_cases", "intelligence/eval/cases/acceptance_cases.json"),
    (
        "frozen_thirty",
        "intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json",
    ),
    ("uq15", "intelligence/eval/cases/uq15_questions.jsonl"),
    (
        "outlook_ten",
        "intelligence/eval/fixtures/outlook-ten-question-frozen-2026-08-16.questions.json",
    ),
    (
        "longtail_fifteen",
        "intelligence/eval/fixtures/longtail-baseline-frozen-15-2026-08-16.questions.json",
    ),
    ("knevo_bench6_v2", "intelligence/eval/cases/knevo_bench6_v2.json"),
)


class CapabilityBenchmarkError(ValueError):
    """题集、密封清单或评审输入不满足约束。"""


# --------------------------------------------------------------------------- 加载与校验


def default_visible_path() -> Path:
    return REPO_ROOT / VISIBLE_RELATIVE


def default_manifest_path() -> Path:
    return REPO_ROOT / SEALED_MANIFEST_RELATIVE


def _iso_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def validate_case(case: Mapping[str, Any], *, visible: bool) -> None:
    case_id = str(case.get("id") or "")
    if not case_id.startswith("cb00-"):
        raise CapabilityBenchmarkError(f"case id must start with cb00-: {case_id!r}")
    category = str(case.get("category") or "")
    if category not in CATEGORIES:
        raise CapabilityBenchmarkError(f"{case_id}: unknown category {category!r}")
    if not case_id.startswith(f"cb00-{category}-"):
        raise CapabilityBenchmarkError(
            f"{case_id}: id prefix must match category {category}"
        )
    suffix = case_id.rsplit("-", 1)[-1]
    if visible and suffix.startswith("h"):
        raise CapabilityBenchmarkError(f"{case_id}: hidden-style id in visible set")
    if not visible and not suffix.startswith("h"):
        raise CapabilityBenchmarkError(f"{case_id}: hidden case id must end with -hN")
    if str(case.get("tier") or "") not in TIERS:
        raise CapabilityBenchmarkError(
            f"{case_id}: tier must be one of {sorted(TIERS)}"
        )
    question = case.get("question")
    if not isinstance(question, str) or len(question.strip()) < 20:
        raise CapabilityBenchmarkError(f"{case_id}: question too short")
    if not _iso_date(case.get("as_of")):
        raise CapabilityBenchmarkError(f"{case_id}: as_of must be ISO date")
    timeout = case.get("timeout")
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise CapabilityBenchmarkError(f"{case_id}: timeout must be positive number")
    deliverable = case.get("deliverable")
    if not isinstance(deliverable, str) or not deliverable.strip():
        raise CapabilityBenchmarkError(f"{case_id}: deliverable required")
    required = case.get("required_data")
    if (
        not isinstance(required, list)
        or not required
        or not all(isinstance(item, str) and item.strip() for item in required)
    ):
        raise CapabilityBenchmarkError(
            f"{case_id}: required_data must be non-empty list[str]"
        )
    context = case.get("conversation_context")
    if not isinstance(context, list):
        raise CapabilityBenchmarkError(
            f"{case_id}: conversation_context must be a list"
        )
    for turn in context:
        if not isinstance(turn, Mapping) or turn.get("role") not in {
            "user",
            "assistant",
        }:
            raise CapabilityBenchmarkError(f"{case_id}: bad conversation_context turn")
        if not isinstance(turn.get("content"), str) or not turn["content"].strip():
            raise CapabilityBenchmarkError(
                f"{case_id}: empty conversation_context content"
            )
    if category == "continue" and not any(t.get("role") == "user" for t in context):
        raise CapabilityBenchmarkError(
            f"{case_id}: continue cases need a prior user turn"
        )


def _validate_cases(
    cases: Sequence[Mapping[str, Any]],
    *,
    visible: bool,
    expected: int,
    per_category: int,
) -> list[str]:
    if len(cases) != expected:
        raise CapabilityBenchmarkError(f"expected {expected} cases, got {len(cases)}")
    ids = [str(case.get("id") or "") for case in cases]
    if len(set(ids)) != len(ids):
        raise CapabilityBenchmarkError("duplicate case ids")
    counts = dict.fromkeys(CATEGORIES, 0)
    for case in cases:
        validate_case(case, visible=visible)
        counts[str(case["category"])] += 1
    if any(count != per_category for count in counts.values()):
        raise CapabilityBenchmarkError(
            f"category counts must be {per_category} each, got {counts}"
        )
    return ids


def load_visible_set(path: Path | None = None) -> dict[str, Any]:
    target = path if path is not None else default_visible_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise CapabilityBenchmarkError("question set must be an object")
    if payload.get("benchmark") != BENCHMARK_ID:
        raise CapabilityBenchmarkError("benchmark id mismatch")
    if not _iso_date(payload.get("default_as_of")):
        raise CapabilityBenchmarkError("default_as_of must be ISO date")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise CapabilityBenchmarkError("cases must be a list")
    ids = _validate_cases(
        cases, visible=True, expected=VISIBLE_COUNT, per_category=VISIBLE_PER_CATEGORY
    )
    return {
        "path_name": target.name,
        "case_count": len(cases),
        "case_ids": ids,
        "default_as_of": payload["default_as_of"],
        "data_prerequisites": payload.get("data_prerequisites") or {},
        "cases": cases,
    }


def load_hidden_set(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("benchmark") != BENCHMARK_ID:
        raise CapabilityBenchmarkError(
            "hidden set must be an object with the benchmark id"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise CapabilityBenchmarkError("hidden cases must be a list")
    ids = _validate_cases(
        cases, visible=False, expected=HIDDEN_COUNT, per_category=HIDDEN_PER_CATEGORY
    )
    return {
        "path_name": path.name,
        "case_count": len(cases),
        "case_ids": ids,
        "cases": cases,
    }


def load_sealed_manifest(path: Path | None = None) -> dict[str, Any]:
    target = path if path is not None else default_manifest_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("benchmark") != BENCHMARK_ID:
        raise CapabilityBenchmarkError("sealed manifest must carry the benchmark id")
    if payload.get("hash_algo") != "sha256":
        raise CapabilityBenchmarkError("hash_algo must be sha256")
    files = payload.get("files")
    rubrics = payload.get("rubrics")
    hidden_ids = payload.get("hidden_case_ids")
    if not isinstance(files, Mapping) or not isinstance(rubrics, Mapping):
        raise CapabilityBenchmarkError("manifest needs files and rubrics maps")
    hex64 = re.compile(r"^[0-9a-f]{64}$")
    for name, digest in list(files.items()) + list(rubrics.items()):
        if not isinstance(digest, str) or not hex64.match(digest):
            raise CapabilityBenchmarkError(f"bad sha256 for {name}")
    if not isinstance(hidden_ids, list) or len(hidden_ids) != HIDDEN_COUNT:
        raise CapabilityBenchmarkError(
            f"manifest must list {HIDDEN_COUNT} hidden case ids"
        )
    if len(rubrics) != VISIBLE_COUNT + HIDDEN_COUNT:
        raise CapabilityBenchmarkError("manifest must hash a rubric for all 30 cases")
    if "hidden.questions.json" not in files or "rubrics.json" not in files:
        raise CapabilityBenchmarkError(
            "manifest must hash hidden.questions.json and rubrics.json"
        )
    return dict(payload)


def normalize_question(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", str(text)).lower()


def _existing_questions(root: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for label, rel in EXISTING_SET_FILES:
        path = root / rel
        if not path.is_file():
            continue
        texts: list[str] = []
        if path.suffix == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                if isinstance(item, Mapping) and item.get("question"):
                    texts.append(str(item["question"]))
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cases = payload.get("cases") if isinstance(payload, Mapping) else payload
            for item in cases or []:
                if not isinstance(item, Mapping):
                    continue
                for key in ("question", "query"):
                    if item.get(key):
                        texts.append(str(item[key]))
        found[label] = texts
    return found


def overlap_report(
    cases: Iterable[Mapping[str, Any]], *, root: Path | None = None
) -> dict[str, Any]:
    root = root if root is not None else REPO_ROOT
    existing = _existing_questions(root)
    normalized_existing = {
        label: {normalize_question(t) for t in texts}
        for label, texts in existing.items()
    }
    duplicates: list[dict[str, str]] = []
    for case in cases:
        norm = normalize_question(str(case.get("question") or ""))
        for label, bucket in normalized_existing.items():
            if norm in bucket:
                duplicates.append(
                    {"case_id": str(case.get("id")), "existing_set": label}
                )
    return {
        "compared_sets": {label: len(texts) for label, texts in existing.items()},
        "duplicates": duplicates,
        "zero_overlap": not duplicates,
    }


# --------------------------------------------------------------------------- 密封


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_rubrics(rubrics_path: Path) -> dict[str, Any]:
    """rubrics.json：case_id → 判分要点；以下划线开头的键（如 ``_meta``）是说明，不参与哈希。"""

    payload = json.loads(rubrics_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise CapabilityBenchmarkError("rubrics.json must map case_id -> rubric")
    return {str(k): v for k, v in payload.items() if not str(k).startswith("_")}


def build_sealed_manifest(sealed_dir: Path, *, created: str) -> dict[str, Any]:
    hidden_path = sealed_dir / "hidden.questions.json"
    rubrics_path = sealed_dir / "rubrics.json"
    hidden = load_hidden_set(hidden_path)
    rubrics = _load_rubrics(rubrics_path)
    visible_ids = set(load_visible_set()["case_ids"])
    hidden_ids = set(hidden["case_ids"])
    if visible_ids & hidden_ids:
        raise CapabilityBenchmarkError("visible and hidden ids overlap")
    expected = visible_ids | hidden_ids
    if set(rubrics.keys()) != expected:
        missing = sorted(expected - set(rubrics.keys()))
        extra = sorted(set(rubrics.keys()) - expected)
        raise CapabilityBenchmarkError(
            f"rubric ids mismatch missing={missing} extra={extra}"
        )
    return {
        "benchmark": BENCHMARK_ID,
        "schema_version": SCHEMA_VERSION,
        "created": created,
        "hash_algo": "sha256",
        "sealed_location_hint": (
            "密封本体在用户本地保管目录（仓外）；建设者不得读取；判分完成后按 uq15 协议入仓公开。"
        ),
        "verify_cmd": (
            "python3 -m intelligence.eval.capability_benchmark seal-verify --sealed-dir <dir>"
        ),
        "hidden_case_ids": sorted(hidden_ids),
        "files": {
            "hidden.questions.json": sha256_file(hidden_path),
            "rubrics.json": sha256_file(rubrics_path),
        },
        "rubrics": {
            case_id: sha256_bytes(canonical_json(rubrics[case_id]).encode("utf-8"))
            for case_id in sorted(expected)
        },
    }


def verify_sealed_dir(sealed_dir: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    mismatches: list[str] = []
    for name, digest in manifest["files"].items():
        path = sealed_dir / name
        if not path.is_file():
            mismatches.append(f"missing:{name}")
        elif sha256_file(path) != digest:
            mismatches.append(f"changed:{name}")
    rubrics_path = sealed_dir / "rubrics.json"
    if rubrics_path.is_file():
        rubrics = _load_rubrics(rubrics_path)
        for case_id, digest in manifest["rubrics"].items():
            if case_id not in rubrics:
                mismatches.append(f"rubric_missing:{case_id}")
            elif (
                sha256_bytes(canonical_json(rubrics[case_id]).encode("utf-8")) != digest
            ):
                mismatches.append(f"rubric_changed:{case_id}")
    return {"ok": not mismatches, "mismatches": mismatches}


# --------------------------------------------------------------------------- 跑批


def _post(
    url: str, payload: Mapping[str, Any], timeout: float = 30.0
) -> dict[str, Any]:
    body = json.dumps(dict(payload)).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _get(url: str, timeout: float = 30.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def _port_of(base: str) -> int | None:
    match = re.search(r":(\d+)(?:/|$)", base)
    return int(match.group(1)) if match else None


def guard_base(base: str) -> None:
    port = _port_of(base)
    if port in RESERVED_PORTS:
        raise CapabilityBenchmarkError(f"refusing reserved/production port {port}")


def guard_users_dir(users_dir: Path) -> None:
    if USERS_DIR_GUARD not in str(users_dir):
        raise CapabilityBenchmarkError(
            f"users_dir must contain {USERS_DIR_GUARD!r} before any reset: {users_dir}"
        )


def reset_user_from_seed(users_dir: Path, user: str, seed_tgz: Path) -> str:
    guard_users_dir(users_dir)
    target = users_dir / user
    if target.exists():
        shutil.rmtree(target)
    users_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(seed_tgz, "r:gz") as tar:
        members = tar.getmembers()
        top = {member.name.split("/", 1)[0] for member in members}
        if len(top) != 1:
            raise CapabilityBenchmarkError(
                "seed tarball must contain exactly one top directory"
            )
        root_name = top.pop()
        for member in members:
            if member.name.startswith("/") or ".." in member.name.split("/"):
                raise CapabilityBenchmarkError(f"unsafe member in seed: {member.name}")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(users_dir, filter="data")
        else:  # pragma: no cover - 老 Python
            tar.extractall(users_dir)
    extracted = users_dir / root_name
    if extracted != target:
        extracted.rename(target)
    return sha256_file(seed_tgz)


def preflight(base: str, *, users_dir: Path) -> dict[str, Any]:
    guard_base(base)
    health = _get(f"{base}/api/health")
    runtime = health.get("runtime") if isinstance(health, Mapping) else None
    if not isinstance(runtime, Mapping):
        raise CapabilityBenchmarkError("health payload has no runtime block")
    problems: list[str] = []
    if health.get("status") != "healthy":
        problems.append(f"status={health.get('status')}")
    if not runtime.get("source_revision"):
        problems.append("source_revision empty")
    if runtime.get("source_dirty") is not False:
        problems.append(f"source_dirty={runtime.get('source_dirty')}")
    if runtime.get("code_matches_repo") is not True:
        problems.append(f"code_matches_repo={runtime.get('code_matches_repo')}")
    served_users_dir = runtime.get("users_dir")
    if (
        served_users_dir
        and Path(str(served_users_dir)).resolve() != users_dir.resolve()
    ):
        problems.append(
            f"users_dir mismatch server={served_users_dir} client={users_dir}"
        )
    llm = _get(f"{base}/api/llm/config")
    if isinstance(llm, Mapping) and llm.get("ready") is not True:
        problems.append("llm not ready")
    return {
        "ok": not problems,
        "problems": problems,
        "source_revision": runtime.get("source_revision"),
        "source_dirty": runtime.get("source_dirty"),
        "code_matches_repo": runtime.get("code_matches_repo"),
        "code_root": runtime.get("code_root"),
        "finance_root": runtime.get("finance_root"),
        "knowledge_wiki": runtime.get("knowledge_wiki"),
        "users_dir": served_users_dir,
        "llm_config": {
            key: value
            for key, value in (llm.items() if isinstance(llm, Mapping) else [])
            if "key" not in str(key).lower()
        },
    }


@dataclass
class TurnRecord:
    turn_index: int
    question: str
    status: str = "pending"
    error: str | None = None
    run_id: str | None = None
    answer: str | None = None
    elapsed_s: float | None = None
    engine: str = "unknown"
    served_models: dict[str, int] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    llm_calls: int | None = None
    tool_calls: int | None = None
    invalid_actions: int | None = None
    tools_called: list[str] = field(default_factory=list)
    structural_status: str | None = None
    semantic_status: str | None = None
    judge_status: str | None = None
    stop_reason: str | None = None
    gaps: int | None = None
    allowed_capabilities: list[str] = field(default_factory=list)
    research_tier: str | None = None
    degrades: list[str] = field(default_factory=list)
    run_dir: str | None = None


@dataclass
class CaseResult:
    case_id: str
    category: str
    tier: str
    as_of: str
    conversation_id: str | None = None
    turns: list[TurnRecord] = field(default_factory=list)
    final_answer: str | None = None
    execution_status: str = "pending"
    total_elapsed_s: float | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None


def _sum_optional(values: Iterable[int | None]) -> int | None:
    total = 0
    seen = False
    for value in values:
        if value is None:
            continue
        total += value
        seen = True
    return total if seen else None


def read_episode(run_dir: Path, record: TurnRecord) -> None:
    episode_path = run_dir / "continuous-episode.json"
    record.run_dir = str(run_dir)
    if not episode_path.is_file():
        record.engine = "engine_missing"
        return
    episode = json.loads(episode_path.read_text(encoding="utf-8"))
    record.engine = (
        "A" if episode.get("execution_kind") == "continuous_episode" else "unknown"
    )
    outcome = episode.get("outcome") or {}
    usage = outcome.get("usage") or {}
    record.input_tokens = usage.get("input_tokens")
    record.output_tokens = usage.get("output_tokens")
    record.llm_calls = usage.get("llm_calls")
    record.tool_calls = usage.get("tool_calls")
    record.invalid_actions = usage.get("invalid_actions")
    record.stop_reason = outcome.get("stop_reason")
    gaps = outcome.get("gaps")
    record.gaps = len(gaps) if isinstance(gaps, list) else None
    served: dict[str, int] = {}
    tools: list[str] = []
    for event in episode.get("events") or []:
        if not isinstance(event, Mapping):
            continue
        payload = event.get("payload") or {}
        if event.get("kind") == "model_turn" and isinstance(payload, Mapping):
            name = str(payload.get("served_model") or "")
            if name:
                served[name] = served.get(name, 0) + 1
        if event.get("kind") == "tool_request" and isinstance(payload, Mapping):
            tool = str(payload.get("name") or "")
            if tool:
                tools.append(tool)
    record.served_models = served
    record.tools_called = tools
    structural = episode.get("structural_verifier") or {}
    record.structural_status = structural.get("verified_status")
    semantic = episode.get("semantic_verifier") or {}
    if isinstance(semantic, Mapping):
        record.semantic_status = semantic.get("status")
        record.judge_status = semantic.get("judge_status")
    contract = episode.get("contract") or {}
    caps = contract.get("allowed_capabilities")
    record.allowed_capabilities = (
        [str(c) for c in caps] if isinstance(caps, list) else []
    )
    record.research_tier = contract.get("research_tier")
    run_json = run_dir / "run.json"
    if run_json.is_file():
        run = json.loads(run_json.read_text(encoding="utf-8"))
        degrades = run.get("degrades")
        record.degrades = (
            [str(d) for d in degrades] if isinstance(degrades, list) else []
        )
        created, finished = run.get("created_at"), run.get("finished_at")
        if isinstance(created, str) and isinstance(finished, str):
            try:
                record.elapsed_s = round(
                    (
                        datetime.fromisoformat(finished)
                        - datetime.fromisoformat(created)
                    ).total_seconds(),
                    1,
                )
            except ValueError:
                pass


def wait_for_assistant(
    base: str,
    conv_id: str,
    user: str,
    *,
    timeout: float,
    poll_seconds: float,
    after_count: int,
) -> tuple[dict[str, Any] | None, str | None]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(poll_seconds)
        msgs = _get(f"{base}/api/conversations/{conv_id}/messages?user={user}")
        items = msgs if isinstance(msgs, list) else msgs.get("messages", [])
        assistant = [
            m for m in items if isinstance(m, Mapping) and m.get("role") == "assistant"
        ]
        if len(assistant) <= after_count:
            continue
        last = assistant[-1]
        if last.get("status") in {"pending", "running", None}:
            continue
        return dict(last), None
    return None, f"timeout after {timeout}s"


def run_case(
    base: str,
    user: str,
    case: Mapping[str, Any],
    *,
    users_dir: Path,
    poll_seconds: float,
) -> CaseResult:
    result = CaseResult(
        case_id=str(case["id"]),
        category=str(case["category"]),
        tier=str(case["tier"]),
        as_of=str(case["as_of"]),
    )
    timeout = float(case.get("timeout") or 900.0)
    prior_user_turns = [
        str(turn["content"])
        for turn in case.get("conversation_context") or []
        if turn.get("role") == "user"
    ]
    questions = prior_user_turns + [str(case["question"])]
    started = time.monotonic()
    try:
        conv = _post(
            f"{base}/api/conversations", {"title": result.case_id, "user": user}
        )
        conv_id = conv.get("conversation_id") or conv.get("id")
        if not conv_id:
            result.execution_status = "error"
            result.turns.append(
                TurnRecord(0, questions[0], status="error", error=str(conv))
            )
            return result
        result.conversation_id = str(conv_id)
        for index, question in enumerate(questions):
            record = TurnRecord(index, question)
            result.turns.append(record)
            turn_started = time.monotonic()
            _post(
                f"{base}/api/conversations/{conv_id}/messages",
                {"content": question, "skill_mode": "auto", "user": user},
            )
            last, error = wait_for_assistant(
                base,
                str(conv_id),
                user,
                timeout=timeout,
                poll_seconds=poll_seconds,
                after_count=index,
            )
            if last is None:
                record.status = "timeout"
                record.error = error
                result.execution_status = "timeout"
                return result
            record.status = str(last.get("status") or "unknown")
            record.answer = last.get("content")
            record.run_id = last.get("run_id")
            wall = round(time.monotonic() - turn_started, 1)
            if record.run_id:
                run_dir = users_dir / user / "runs" / str(record.run_id)
                for attempt in range(6):
                    if (run_dir / "continuous-episode.json").is_file():
                        break
                    time.sleep(0.5 * (attempt + 1))
                read_episode(run_dir, record)
            if record.elapsed_s is None:
                record.elapsed_s = wall
        result.final_answer = result.turns[-1].answer
        result.execution_status = (
            "completed"
            if all(t.engine == "A" for t in result.turns)
            else "engine_missing"
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result.execution_status = "error"
        if result.turns:
            result.turns[-1].status = "error"
            result.turns[-1].error = str(exc)
        else:
            result.turns.append(
                TurnRecord(0, questions[0], status="error", error=str(exc))
            )
    result.total_elapsed_s = round(time.monotonic() - started, 1)
    result.total_input_tokens = _sum_optional(t.input_tokens for t in result.turns)
    result.total_output_tokens = _sum_optional(t.output_tokens for t in result.turns)
    return result


def market_data_date(finance_root: Path | None) -> str | None:
    if finance_root is None:
        return None
    db_path = finance_root / "db" / "market_feature_store.duckdb"
    if not db_path.is_file():
        return None
    try:
        import duckdb  # 延迟导入：跑批机之外不强依赖
    except ImportError:
        return None
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        row = con.execute("select max(trade_date) from fact_market_daily").fetchone()
    finally:
        con.close()
    return str(row[0]) if row and row[0] is not None else None


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_benchmark(
    *,
    base: str,
    user: str,
    users_dir: Path,
    cases: Sequence[Mapping[str, Any]],
    output: Path,
    arm_label: str,
    poll_seconds: float = 3.0,
    seed_tgz: Path | None = None,
    finance_root: Path | None = None,
    case_filter: Sequence[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if output.exists():
        raise CapabilityBenchmarkError(f"refusing to overwrite {output}")
    pre = preflight(base, users_dir=users_dir)
    if not pre["ok"] and not force:
        raise CapabilityBenchmarkError(f"preflight failed: {pre['problems']}")
    seed_sha = reset_user_from_seed(users_dir, user, seed_tgz) if seed_tgz else None
    selected = [c for c in cases if not case_filter or str(c["id"]) in set(case_filter)]
    artifact: dict[str, Any] = {
        "benchmark": BENCHMARK_ID,
        "schema_version": SCHEMA_VERSION,
        "arm_label": arm_label,
        "generated_at": utc_stamp(),
        "entry": "POST /api/conversations -> POST /api/conversations/{id}/messages (skill_mode=auto)",
        "base": base,
        "user": user,
        "users_dir": str(users_dir),
        "seed_sha256": seed_sha,
        "preflight": pre,
        "market_data_date": market_data_date(finance_root),
        "case_count": len(selected),
        "cases": [],
        "summary": {},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    for case in selected:
        result = run_case(
            base, user, case, users_dir=users_dir, poll_seconds=poll_seconds
        )
        artifact["cases"].append(asdict(result))
        artifact["summary"] = summarize_artifact(artifact["cases"])
        output.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return artifact


def summarize_artifact(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    served: dict[str, int] = {}
    structural: dict[str, int] = {}
    semantic: dict[str, int] = {}
    elapsed: list[float] = []
    tokens_in = tokens_out = 0
    invalid = 0
    for case in cases:
        status = str(case.get("execution_status"))
        statuses[status] = statuses.get(status, 0) + 1
        if isinstance(case.get("total_elapsed_s"), (int, float)):
            elapsed.append(float(case["total_elapsed_s"]))
        tokens_in += int(case.get("total_input_tokens") or 0)
        tokens_out += int(case.get("total_output_tokens") or 0)
        for turn in case.get("turns") or []:
            for name, count in (turn.get("served_models") or {}).items():
                served[name] = served.get(name, 0) + int(count)
            key = str(turn.get("structural_status"))
            structural[key] = structural.get(key, 0) + 1
            key = str(turn.get("semantic_status"))
            semantic[key] = semantic.get(key, 0) + 1
            invalid += int(turn.get("invalid_actions") or 0)
    elapsed.sort()
    median = elapsed[len(elapsed) // 2] if elapsed else None
    return {
        "execution_status": statuses,
        "served_models": served,
        "structural_status": structural,
        "semantic_status": semantic,
        "median_case_elapsed_s": median,
        "total_elapsed_s": round(sum(elapsed), 1),
        "total_input_tokens": tokens_in,
        "total_output_tokens": tokens_out,
        "invalid_actions": invalid,
    }


# --------------------------------------------------------------------------- 评审包


def _shuffle_labels(seed: str, case_id: str, labels: Sequence[str]) -> list[str]:
    rng = random.Random(f"{seed}:{case_id}")
    order = list(labels)
    rng.shuffle(order)
    return order


def pick_second_review(case_ids: Sequence[str], seed: str) -> list[str]:
    count = max(1, -(-len(case_ids) * SECOND_REVIEW_RATIO // 1))
    rng = random.Random(f"{seed}:second-review")
    return sorted(rng.sample(list(case_ids), int(count)))


def build_review_pack(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    visible_cases: Sequence[Mapping[str, Any]],
    hidden_cases: Sequence[Mapping[str, Any]] | None,
    output_dir: Path,
    seed: str,
    decoy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CapabilityBenchmarkError(f"review dir not empty: {output_dir}")
    labels = [str(a.get("arm_label")) for a in artifacts]
    if len(set(labels)) != len(labels):
        raise CapabilityBenchmarkError("arm labels must be unique")
    by_case: dict[str, dict[str, Mapping[str, Any]]] = {}
    for artifact in artifacts:
        for case in artifact.get("cases") or []:
            by_case.setdefault(str(case["case_id"]), {})[str(artifact["arm_label"])] = (
                case
            )
    case_meta = {
        str(c["id"]): c for c in list(visible_cases) + list(hidden_cases or [])
    }
    (output_dir / "sheets").mkdir(parents=True, exist_ok=True)
    mapping: dict[str, dict[str, str]] = {}
    letters = "XYZWV"
    for case_id in sorted(by_case):
        arms = by_case[case_id]
        arm_labels = sorted(arms)
        shuffled = _shuffle_labels(seed, case_id, arm_labels)
        blind = {letters[i]: label for i, label in enumerate(shuffled)}
        answers = {
            blind_key: arms[label].get("final_answer")
            for blind_key, label in blind.items()
        }
        # 多轮题：前序轮由系统真实作答，评审要看见它才能判「本轮有没有增量、有没有重复」。
        prior_turns = {
            blind_key: [
                {"question": turn.get("question"), "answer": turn.get("answer")}
                for turn in sorted(
                    arms[label].get("turns") or [],
                    key=lambda t: int(t.get("turn_index") or 0),
                )
                if int(turn.get("turn_index") or 0)
                < len(arms[label].get("turns") or []) - 1
            ]
            for blind_key, label in blind.items()
        }
        if decoy and decoy.get("case_id") == case_id:
            decoy_key = letters[len(blind)]
            blind[decoy_key] = "decoy"
            answers[decoy_key] = str(decoy.get("answer") or "")
        mapping[case_id] = blind
        meta = case_meta.get(case_id, {})
        sheet = {
            "case_id": case_id,
            "category": meta.get("category"),
            "question": meta.get("question"),
            "deliverable": meta.get("deliverable"),
            "as_of": meta.get("as_of"),
            "conversation_context": meta.get("conversation_context") or [],
            "prior_turns": prior_turns,
            "answers": answers,
            "score_template": {
                "reviewer": "",
                "arms": {
                    key: {
                        "task_completed": "yes|partial|no",
                        "correct_useful_points": 0,
                        "wrong_facts": 0,
                        "calc_correct": "yes|no|na",
                        "ranking_with_conditions": "yes|no|na",
                        "followup_advances": "yes|no|na",
                        "over_refusal": False,
                        "time_leakage": False,
                        "notes": "",
                    }
                    for key in answers
                },
                "pair_verdict": "X|Y|tie|null",
                "verdict_reason": "",
            },
        }
        (output_dir / "sheets" / f"{case_id}.json").write_text(
            json.dumps(sheet, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    mapping_json = canonical_json(mapping)
    (output_dir / "mapping.sealed.json").write_text(mapping_json, encoding="utf-8")
    pack = {
        "benchmark": BENCHMARK_ID,
        "seed": seed,
        "arms": labels,
        "case_count": len(mapping),
        "mapping_sha256": sha256_bytes(mapping_json.encode("utf-8")),
        "second_review_case_ids": pick_second_review(sorted(mapping), seed),
        "decoy_case_id": decoy.get("case_id") if decoy else None,
        "instructions": (
            "评审只看 sheets/ 下的问题与匿名答案；不得打开 mapping.sealed.json。"
            "把 score_template 填好另存为 scores/<case_id>.json。"
            "优先序：正确完成任务 > 研究增量 > 速度与费用；可核验要点有错数不得凭流畅度获胜。"
        ),
    }
    (output_dir / "pack.json").write_text(
        json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return pack


# --------------------------------------------------------------------------- 汇总


def _load_scores(review_dir: Path) -> dict[str, dict[str, Any]]:
    scores_dir = review_dir / "scores"
    scores: dict[str, dict[str, Any]] = {}
    if not scores_dir.is_dir():
        return scores
    for path in sorted(scores_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping) and payload.get("case_id"):
            scores[str(payload["case_id"])] = dict(payload)
    return scores


def _validate_arm_score(case_id: str, key: str, arm: Mapping[str, Any]) -> None:
    if arm.get("task_completed") not in TASK_COMPLETED:
        raise CapabilityBenchmarkError(f"{case_id}/{key}: task_completed invalid")
    for name in ("calc_correct", "ranking_with_conditions", "followup_advances"):
        if arm.get(name) not in TRI_STATE:
            raise CapabilityBenchmarkError(f"{case_id}/{key}: {name} invalid")
    for name in ("correct_useful_points", "wrong_facts"):
        if not isinstance(arm.get(name), int) or arm[name] < 0:
            raise CapabilityBenchmarkError(f"{case_id}/{key}: {name} must be int >= 0")
    for name in ("over_refusal", "time_leakage"):
        if not isinstance(arm.get(name), bool):
            raise CapabilityBenchmarkError(f"{case_id}/{key}: {name} must be bool")


def aggregate(
    review_dir: Path, *, artifacts: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    pack = json.loads((review_dir / "pack.json").read_text(encoding="utf-8"))
    mapping_text = (review_dir / "mapping.sealed.json").read_text(encoding="utf-8")
    if sha256_bytes(mapping_text.encode("utf-8")) != pack.get("mapping_sha256"):
        raise CapabilityBenchmarkError(
            "mapping.sealed.json does not match pack.mapping_sha256"
        )
    mapping = json.loads(mapping_text)
    scores = _load_scores(review_dir)
    per_arm: dict[str, dict[str, Any]] = {}
    pair_tally: dict[str, int] = {}
    decoy_wins: list[str] = []
    second_reviews: list[dict[str, Any]] = []
    scored_cases: list[str] = []
    for case_id, blind in mapping.items():
        score = scores.get(case_id)
        if not score:
            continue
        scored_cases.append(case_id)
        arms = score.get("arms") or {}
        for key, label in blind.items():
            arm = arms.get(key)
            if not isinstance(arm, Mapping):
                raise CapabilityBenchmarkError(
                    f"{case_id}: missing score for arm {key}"
                )
            _validate_arm_score(case_id, key, arm)
            bucket = per_arm.setdefault(
                label,
                {
                    "cases": 0,
                    "task_completed": dict.fromkeys(TASK_COMPLETED, 0),
                    "correct_useful_points": 0,
                    "wrong_facts": 0,
                    "calc_correct": dict.fromkeys(TRI_STATE, 0),
                    "ranking_with_conditions": dict.fromkeys(TRI_STATE, 0),
                    "followup_advances": dict.fromkeys(TRI_STATE, 0),
                    "over_refusal": 0,
                    "time_leakage": 0,
                    "pair_wins": 0,
                    "pair_ties": 0,
                    "pair_losses": 0,
                },
            )
            bucket["cases"] += 1
            bucket["task_completed"][arm["task_completed"]] += 1
            bucket["correct_useful_points"] += arm["correct_useful_points"]
            bucket["wrong_facts"] += arm["wrong_facts"]
            for name in (
                "calc_correct",
                "ranking_with_conditions",
                "followup_advances",
            ):
                bucket[name][arm[name]] += 1
            bucket["over_refusal"] += int(arm["over_refusal"])
            bucket["time_leakage"] += int(arm["time_leakage"])
        verdict = score.get("pair_verdict")
        if verdict in blind:
            winner = blind[verdict]
            pair_tally[winner] = pair_tally.get(winner, 0) + 1
            if winner == "decoy":
                decoy_wins.append(case_id)
            for key, label in blind.items():
                if label == "decoy":
                    continue
                if key == verdict:
                    per_arm[label]["pair_wins"] += 1
                else:
                    per_arm[label]["pair_losses"] += 1
        elif verdict == "tie":
            for label in blind.values():
                if label != "decoy":
                    per_arm[label]["pair_ties"] += 1
        second = score.get("second_reviewer")
        if isinstance(second, Mapping) and second.get("pair_verdict") is not None:
            second_reviews.append(
                {
                    "case_id": case_id,
                    "agree": second.get("pair_verdict") == verdict,
                    "first": verdict,
                    "second": second.get("pair_verdict"),
                }
            )
    appendix = {
        str(artifact.get("arm_label")): {
            "execution_status": (artifact.get("summary") or {}).get("execution_status"),
            "invalid_actions": (artifact.get("summary") or {}).get("invalid_actions"),
            "median_case_elapsed_s": (artifact.get("summary") or {}).get(
                "median_case_elapsed_s"
            ),
            "total_elapsed_s": (artifact.get("summary") or {}).get("total_elapsed_s"),
            "total_input_tokens": (artifact.get("summary") or {}).get(
                "total_input_tokens"
            ),
            "total_output_tokens": (artifact.get("summary") or {}).get(
                "total_output_tokens"
            ),
            "served_models": (artifact.get("summary") or {}).get("served_models"),
            "source_revision": (artifact.get("preflight") or {}).get("source_revision"),
            "market_data_date": artifact.get("market_data_date"),
        }
        for artifact in artifacts
    }
    agreement = (
        round(sum(1 for r in second_reviews if r["agree"]) / len(second_reviews), 3)
        if second_reviews
        else None
    )
    return {
        "benchmark": BENCHMARK_ID,
        "generated_at": utc_stamp(),
        "scored_case_count": len(scored_cases),
        "unscored_case_ids": sorted(set(mapping) - set(scored_cases)),
        "main_table": per_arm,
        "pair_tally": pair_tally,
        "decoy_check": {
            "decoy_present": pack.get("decoy_case_id") is not None,
            "decoy_won": bool(decoy_wins),
            "cases": decoy_wins,
        },
        "second_review": {
            "required_case_ids": pack.get("second_review_case_ids"),
            "reviewed": second_reviews,
            "agreement_rate": agreement,
        },
        "appendix": appendix,
        "significance_note": (
            "单跑基线不做显著性宣称；ab_sample_design 锁定 v=0.1375，30 题需 15 次重复才分辨 5pp。"
        ),
    }


def render_summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [f"# {BENCHMARK_ID} · 汇总（{summary.get('generated_at')}）", ""]
    lines.append(f"- 已评分题数：{summary.get('scored_case_count')}")
    if summary.get("unscored_case_ids"):
        lines.append(f"- 未评分：{', '.join(summary['unscored_case_ids'])}")
    decoy = summary.get("decoy_check") or {}
    lines.append(
        f"- 反向验证：decoy_present={decoy.get('decoy_present')} decoy_won={decoy.get('decoy_won')}"
    )
    lines.append("")
    lines.append(
        "| 臂 | 题数 | 完成 yes/partial/no | 正确有用点 | 错误事实 | 计算对 | 排序+条件 | 续研推进 | 过度拒答 | 胜/平/负 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for label, row in (summary.get("main_table") or {}).items():
        tc = row["task_completed"]
        lines.append(
            f"| {label} | {row['cases']} | {tc['yes']}/{tc['partial']}/{tc['no']} | "
            f"{row['correct_useful_points']} | {row['wrong_facts']} | {row['calc_correct']['yes']} | "
            f"{row['ranking_with_conditions']['yes']} | {row['followup_advances']['yes']} | "
            f"{row['over_refusal']} | {row['pair_wins']}/{row['pair_ties']}/{row['pair_losses']} |"
        )
    lines.append("")
    lines.append("## 附录（执行状态 / 无效工具调用 / 时间 / token）")
    lines.append("")
    for label, row in (summary.get("appendix") or {}).items():
        lines.append(
            f"- **{label}** @ {row.get('source_revision')} 数据截止 {row.get('market_data_date')}："
        )
        lines.append(
            f"  执行 {row.get('execution_status')}；无效工具调用 {row.get('invalid_actions')}；"
            f"中位耗时 {row.get('median_case_elapsed_s')} s，总耗时 {row.get('total_elapsed_s')} s；"
            f"token 入 {row.get('total_input_tokens')} / 出 {row.get('total_output_tokens')}；模型 {row.get('served_models')}"
        )
    lines.append("")
    lines.append(f"> {summary.get('significance_note')}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- CLI


def _load_artifacts(paths: Sequence[str]) -> list[dict[str, Any]]:
    return [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]


def cmd_validate(args: argparse.Namespace) -> int:
    loaded = load_visible_set(Path(args.questions) if args.questions else None)
    manifest = load_sealed_manifest(Path(args.manifest) if args.manifest else None)
    print(
        json.dumps(
            {
                "visible": loaded["case_count"],
                "hidden": len(manifest["hidden_case_ids"]),
                "rubrics_hashed": len(manifest["rubrics"]),
                "default_as_of": loaded["default_as_of"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def cmd_overlap(args: argparse.Namespace) -> int:
    loaded = load_visible_set(Path(args.questions) if args.questions else None)
    cases = list(loaded["cases"])
    if args.sealed_dir:
        cases += load_hidden_set(Path(args.sealed_dir) / "hidden.questions.json")[
            "cases"
        ]
    report = overlap_report(cases)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["zero_overlap"] else 1


def cmd_seal(args: argparse.Namespace) -> int:
    manifest = build_sealed_manifest(Path(args.sealed_dir), created=args.created)
    target = Path(args.output) if args.output else default_manifest_path()
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({"written": str(target), "hidden": len(manifest["hidden_case_ids"])})
    )
    return 0


def cmd_seal_verify(args: argparse.Namespace) -> int:
    manifest = load_sealed_manifest(Path(args.manifest) if args.manifest else None)
    report = verify_sealed_dir(Path(args.sealed_dir), manifest)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


def cmd_run(args: argparse.Namespace) -> int:
    users_dir = Path(args.users_dir).expanduser().resolve()
    env_users_dir = os.environ.get("FORESIGHT_USERS_DIR")
    if env_users_dir and Path(env_users_dir).expanduser().resolve() != users_dir:
        raise CapabilityBenchmarkError(
            f"FORESIGHT_USERS_DIR={env_users_dir} disagrees with --users-dir {users_dir}"
        )
    cases = list(
        load_visible_set(Path(args.questions) if args.questions else None)["cases"]
    )
    if args.sealed_dir:
        manifest = load_sealed_manifest(Path(args.manifest) if args.manifest else None)
        check = verify_sealed_dir(Path(args.sealed_dir), manifest)
        if not check["ok"]:
            raise CapabilityBenchmarkError(
                f"sealed dir failed verification: {check['mismatches']}"
            )
        cases += load_hidden_set(Path(args.sealed_dir) / "hidden.questions.json")[
            "cases"
        ]
    artifact = run_benchmark(
        base=args.base.rstrip("/"),
        user=args.user,
        users_dir=users_dir,
        cases=cases,
        output=Path(args.output),
        arm_label=args.arm_label,
        poll_seconds=args.poll_seconds,
        seed_tgz=Path(args.seed_tgz).expanduser() if args.seed_tgz else None,
        finance_root=Path(args.finance_root).expanduser()
        if args.finance_root
        else None,
        case_filter=args.case or None,
        force=args.force,
    )
    print(json.dumps(artifact["summary"], ensure_ascii=False, indent=1))
    statuses = artifact["summary"].get("execution_status") or {}
    return 0 if set(statuses) <= {"completed"} else 2


def cmd_review_pack(args: argparse.Namespace) -> int:
    artifacts = _load_artifacts(args.artifact)
    visible = load_visible_set(Path(args.questions) if args.questions else None)[
        "cases"
    ]
    hidden = (
        load_hidden_set(Path(args.sealed_dir) / "hidden.questions.json")["cases"]
        if args.sealed_dir
        else None
    )
    decoy = None
    if args.decoy_case and args.decoy_answer_file:
        decoy = {
            "case_id": args.decoy_case,
            "answer": Path(args.decoy_answer_file).read_text(encoding="utf-8"),
        }
    pack = build_review_pack(
        artifacts,
        visible_cases=visible,
        hidden_cases=hidden,
        output_dir=Path(args.output_dir),
        seed=args.seed,
        decoy=decoy,
    )
    print(json.dumps(pack, ensure_ascii=False, indent=1))
    return 0


def cmd_aggregate(args: argparse.Namespace) -> int:
    artifacts = _load_artifacts(args.artifact)
    summary = aggregate(Path(args.review_dir), artifacts=artifacts)
    out_json = Path(args.output)
    if out_json.exists():
        raise CapabilityBenchmarkError(f"refusing to overwrite {out_json}")
    out_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    out_json.with_suffix(".md").write_text(
        render_summary_markdown(summary), encoding="utf-8"
    )
    print(json.dumps({"written": str(out_json), "decoy_check": summary["decoy_check"]}))
    return 3 if summary["decoy_check"]["decoy_won"] else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capability_benchmark", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate", help="校验公开题集与密封清单结构")
    p.add_argument("--questions")
    p.add_argument("--manifest")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("overlap", help="与既有题集逐题比对（必须零重叠）")
    p.add_argument("--questions")
    p.add_argument("--sealed-dir")
    p.set_defaults(func=cmd_overlap)

    p = sub.add_parser("seal", help="从密封目录生成 sha256 清单（出题人用）")
    p.add_argument("--sealed-dir", required=True)
    p.add_argument("--created", required=True)
    p.add_argument("--output")
    p.set_defaults(func=cmd_seal)

    p = sub.add_parser("seal-verify", help="验封：密封目录 vs 仓内清单")
    p.add_argument("--sealed-dir", required=True)
    p.add_argument("--manifest")
    p.set_defaults(func=cmd_seal_verify)

    p = sub.add_parser("run", help="走 Workbench 真实对话门跑题并落 artifact")
    p.add_argument("--base", required=True)
    p.add_argument("--user", required=True)
    p.add_argument("--users-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--arm-label", required=True)
    p.add_argument("--questions")
    p.add_argument("--manifest")
    p.add_argument("--sealed-dir", help="给了就把 10 道隐藏题一起跑（先验封）")
    p.add_argument("--seed-tgz", help="开跑前从种子重置评测用户台账")
    p.add_argument("--finance-root", help="用于记录 DuckDB 数据截止")
    p.add_argument("--case", action="append", help="只跑指定题号，可重复")
    p.add_argument("--poll-seconds", type=float, default=3.0)
    p.add_argument(
        "--force", action="store_true", help="前置检查未过也强跑（记录在 artifact）"
    )
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("review-pack", help="生成匿名配对评审包")
    p.add_argument("--artifact", action="append", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--seed", required=True)
    p.add_argument("--questions")
    p.add_argument("--sealed-dir")
    p.add_argument("--decoy-case")
    p.add_argument("--decoy-answer-file")
    p.set_defaults(func=cmd_review_pack)

    p = sub.add_parser("aggregate", help="汇总评审结果：主表 + 附录 + 反向验证")
    p.add_argument("--review-dir", required=True)
    p.add_argument("--artifact", action="append", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_aggregate)

    args = parser.parse_args(list(argv) if argv is not None else None)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
