"""Posterior rejudge ledger: replay unavailable judges offline.

Writes receipts only. Never mutates the published answer artifact.
Default index: ``~/.finance-runtime/rejudge-pending/index.jsonl``.
Override with ``FINANCE_REJUDGE_PENDING_INDEX``.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.services.judge_degrade import JUDGE_UNAVAILABLE

SCHEMA = "rejudge_pending.v1"
DEFAULT_INDEX = (
    Path.home() / ".finance-runtime" / "rejudge-pending" / "index.jsonl"
)
RECEIPT_DIR = Path("intelligence") / "eval" / "runs"


def pending_index_path(override: str | Path | None = None) -> Path:
    if override is not None:
        return Path(override)
    env = os.environ.get("FINANCE_REJUDGE_PENDING_INDEX", "").strip()
    if env:
        return Path(env)
    return DEFAULT_INDEX


def published_answer_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def artifact_pending_marker(semantic: Mapping[str, Any]) -> dict[str, Any]:
    """Compact marker stored on the private artifact / semantic dump."""

    return {
        "pending_rejudge": semantic.get("judge_status") == "unavailable",
        "degrade_class": (
            JUDGE_UNAVAILABLE
            if semantic.get("judge_status") == "unavailable"
            else semantic.get("degrade_class")
        ),
        "judge_status": semantic.get("judge_status"),
        "exc_class": semantic.get("exc_class"),
        "timeout_asked": semantic.get("timeout_asked"),
        "timeout_configured": semantic.get("timeout_configured"),
        "remaining_seconds_at_entry": semantic.get("remaining_seconds_at_entry"),
    }


def _should_skip_default_index_write() -> bool:
    return bool(
        os.environ.get("PYTEST_CURRENT_TEST")
        and not os.environ.get("FINANCE_REJUDGE_PENDING_INDEX")
    )


def append_pending(
    record: Mapping[str, Any],
    *,
    index_path: Path | None = None,
) -> Path | None:
    """Append one JSONL row. Returns the index path, or None if skipped."""

    path = pending_index_path(index_path)
    if index_path is None and _should_skip_default_index_write():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema": SCHEMA,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "pending",
        **dict(record),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def append_pending_from_artifact(
    artifact: Mapping[str, Any],
    *,
    index_path: Path | None = None,
    run_id: str | None = None,
    artifact_path: str | None = None,
) -> Path | None:
    semantic = artifact.get("semantic_verifier")
    if not isinstance(semantic, Mapping):
        semantic = artifact
    if semantic.get("judge_status") != "unavailable":
        return None
    published = str(
        artifact.get("published_answer")
        or semantic.get("public_answer")
        or ""
    )
    # R-20260829-04：行内自带可重放材料。此前行里只有 sha 指纹——adapter 调用
    # 点拿不到 run_id/artifact_path（双双落 None），judge_request 又不随行存，
    # 工件一旦被清理，积压行就永远重放不了（2026-08-29 清账实测 49/93 即此
    # 形状）。现在把 judge_request 与 published_answer 内联进行（行即夹具，
    # 独立于工件生命周期），episode_task_id 从 artifact 自带的 contract 里
    # 免费取（adapter 调用点零改动）。
    request = semantic.get("judge_request")
    contract = artifact.get("contract")
    episode_task_id = (
        str(contract.get("task_id") or "") if isinstance(contract, Mapping) else ""
    )
    row: dict[str, Any] = {
        **artifact_pending_marker(semantic),
        "run_id": run_id or artifact.get("run_id"),
        "episode_task_id": episode_task_id or None,
        "artifact_path": artifact_path,
        "published_answer_sha256": published_answer_sha256(published),
        # 语义收紧：True = 本行**自带**请求（可独立重放），不再是「工件里有」。
        "has_judge_request": isinstance(request, Mapping),
    }
    if isinstance(request, Mapping):
        row["judge_request"] = dict(request)
        row["published_answer"] = published
    return append_pending(row, index_path=index_path)


def replayable_pending_rows(
    index_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """把 pending 行分成（可重放, stale）两组，不改写索引。

    可重放 = 行内自带 ``judge_request``（新式行，行即夹具）；stale = 只剩
    sha 指纹的旧式行——如实标注，不硬清也不假装能重放。
    """

    path = pending_index_path(index_path)
    replayable: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    if not path.is_file():
        return replayable, stale
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("status") != "pending":
            continue
        if isinstance(row.get("judge_request"), Mapping):
            replayable.append(row)
        else:
            stale.append(row)
    return replayable, stale


def pending_row_slug(row: Mapping[str, Any]) -> str:
    """重放收据/夹具的稳定文件名：run_id > episode_task_id > sha 前缀。"""

    for key in ("run_id", "episode_task_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return f"sha-{str(row.get('published_answer_sha256') or 'unknown')[:12]}"


def _as_report(value: object) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "passed") and hasattr(value, "rejected_sentence_indexes"):
        return {
            "passed": bool(getattr(value, "passed")),
            "rejected_sentence_indexes": list(
                getattr(value, "rejected_sentence_indexes") or ()
            ),
            "issues": list(getattr(value, "issues") or ()),
        }
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, Mapping) else None
    return None


def rejudge_verdict(
    *,
    original_judge_status: str,
    report: Mapping[str, Any] | None,
) -> str:
    """``confirm`` / ``overturn`` / ``unavailable``.

    confirm: offline judge passed — content was fine, original was vendor jitter.
    overturn: offline judge rejected or narrowed — published answer would differ.
    unavailable: replay still produced no report.
    """

    if original_judge_status != "unavailable":
        raise ValueError("rejudge is only for judge_status=unavailable")
    if report is None:
        return "unavailable"
    rejected = report.get("rejected_sentence_indexes") or []
    passed = bool(report.get("passed"))
    if passed and not rejected:
        return "confirm"
    return "overturn"


def run_offline_rejudge(
    fixture: Mapping[str, Any],
    judge_fn: Callable[..., object],
    *,
    receipt_path: Path | None = None,
    published_answer_path: Path | None = None,
) -> dict[str, Any]:
    """Replay the stored judge request. Does not write the published answer."""

    original_status = str(fixture.get("judge_status") or "")
    published = str(fixture.get("published_answer") or "")
    before_sha = published_answer_sha256(published)
    request = fixture.get("judge_request")
    if not isinstance(request, Mapping):
        raise ValueError("fixture missing judge_request")
    report = _as_report(judge_fn(dict(request)))
    verdict = rejudge_verdict(
        original_judge_status=original_status,
        report=report,
    )
    if published_answer_path is not None and published_answer_path.is_file():
        after = published_answer_path.read_text(encoding="utf-8")
        after_sha = published_answer_sha256(after)
    else:
        after_sha = before_sha
    receipt = {
        "schema": SCHEMA,
        "run_id": fixture.get("run_id"),
        "original_judge_status": original_status,
        "rejudge_judge_status": (
            "passed"
            if verdict == "confirm"
            else "rejected"
            if verdict == "overturn"
            else "unavailable"
        ),
        "verdict": verdict,
        "overturn": verdict == "overturn",
        "published_answer_unchanged": after_sha == before_sha,
        "published_answer_sha256": before_sha,
        "report": dict(report) if report is not None else None,
        "exc_class": fixture.get("exc_class"),
        "timeout_asked": fixture.get("timeout_asked"),
        "timeout_configured": fixture.get("timeout_configured"),
        "remaining_seconds_at_entry": fixture.get("remaining_seconds_at_entry"),
    }
    if receipt_path is not None:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return receipt


def summarize_receipts(receipts: list[Mapping[str, Any]]) -> dict[str, Any]:
    confirm = sum(1 for row in receipts if row.get("verdict") == "confirm")
    overturn = sum(1 for row in receipts if row.get("verdict") == "overturn")
    still = sum(1 for row in receipts if row.get("verdict") == "unavailable")
    decided = confirm + overturn
    return {
        "schema": SCHEMA,
        "n": len(receipts),
        "confirm_count": confirm,
        "overturn_count": overturn,
        "still_unavailable_count": still,
        "overturn_rate": (overturn / decided) if decided else None,
    }


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload
