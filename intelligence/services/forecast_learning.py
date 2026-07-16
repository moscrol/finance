"""Forecast verdict -> reflection -> approved lesson/rule feedback loop."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from intelligence.services import llm_refine


REFLECTION_SCHEMA_VERSION = "1.0"
LESSON_SCHEMA_VERSION = "1.0"
RULE_SCHEMA_VERSION = "1.0"
ACTIONABLE_VERDICTS = {"miss", "partial"}
ALLOWED_RULE_STATUSES = {"pending", "approved", "rejected"}
PLACEHOLDER_FAILURE_MODES = {"", "机判待人工归因"}
STREAM_TO_SOURCE = {"盘面": "duckdb", "晨汇": "briefing", "卖方": "sellside"}
ANNOTATION_HEADING = "## 8. 用户批注区"
VERDICT_MARKER = "<!-- BEGIN AUTO dual-blind-verdict"

LLMComplete = Callable[..., tuple[str | None, object | None, str]]


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def _append_jsonl_once(path: Path, record: dict[str, Any], *, key: str = "id") -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        rows = _read_jsonl(path)
        identity = str(record.get(key) or "")
        if identity and any(str(row.get(key) or "") == identity for row in rows):
            return False
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return True


def _stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _source_for(entry: dict[str, Any]) -> str:
    explicit = str(entry.get("source") or "").lower()
    if explicit in {"duckdb", "briefing", "sellside"}:
        return explicit
    return STREAM_TO_SOURCE.get(str(entry.get("stream") or "盘面"), "duckdb")


def _answer_for(
    ledger_dir: Path,
    *,
    date: str,
    agent: str,
    source: str,
    hypothesis_ids: set[str],
) -> tuple[Path | None, dict[str, Any] | None]:
    candidates = sorted(ledger_dir.glob(f"{date}.answer.{agent}*.json"))
    fallback: tuple[Path, dict[str, Any]] | None = None
    for path in candidates:
        payload = _read_json(path)
        if payload is None:
            continue
        payload_source = str(payload.get("source") or "duckdb").lower()
        if payload_source == source:
            return path, payload
        answer_ids = {
            str(item.get("id") or "")
            for item in payload.get("hypotheses") or []
            if isinstance(item, dict)
        }
        if hypothesis_ids & answer_ids:
            fallback = (path, payload)
    if fallback is not None:
        return fallback
    return None, None


def _category(hypothesis_id: str, hypothesis: dict[str, Any] | None) -> str:
    if hypothesis and hypothesis.get("category"):
        return str(hypothesis["category"])
    if hypothesis_id.startswith("target:"):
        return "target"
    if hypothesis_id.startswith("direction:") or hypothesis_id == "direction":
        return "direction"
    if hypothesis_id.startswith("market:") or hypothesis_id == "market":
        return "market"
    if hypothesis_id == "falsify":
        return "falsify"
    return "unknown"


def _bounded_context(
    answer: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    ids = {str(entry.get("id") or "") for entry in entries}
    hypotheses = [
        item
        for item in answer.get("hypotheses") or []
        if isinstance(item, dict) and str(item.get("id") or "") in ids
    ]
    refs = {
        str(ref)
        for hypothesis in hypotheses
        for ref in hypothesis.get("evidence_refs") or []
        if str(ref)
    }
    catalog = answer.get("evidence_catalog") or {}
    selected_catalog = {
        key: value
        for key, value in catalog.items()
        if str(key) in refs
    } if isinstance(catalog, dict) else {}
    return {
        "stage": answer.get("stage"),
        "main_judgment": answer.get("main_judgment"),
        "direction_ranking": list(answer.get("direction_ranking") or [])[:10],
        "thresholds": answer.get("thresholds") or {},
        "hypotheses": hypotheses,
        "relevant_evidence": selected_catalog,
        "verdicts": entries,
    }


def _reflection_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "你是A股双盲预测的事后反思器。只能使用给定的事前答卷与事后verdict，"
        "不得补写当时不可见的信息。逐条诊断 miss/partial，failure_mode 优先从 "
        "A1概率兑现偏差/A2信息集不全/A3逻辑链断裂/A4概率校准偏差/A5场景错位/"
        "A6执行偏差中选择。严格输出 JSON：{\"reflections\":[{\"id\":\"...\","
        "\"failure_mode\":\"A1-A6...\",\"diagnosis\":\"...\",\"missed_signal\":\"...\","
        "\"ranking_error\":\"...\",\"correction\":\"...\","
        "\"reusable_lesson\":\"...\",\"proposed_rule\":\"...\"}]}。"
        "找不到可修正信息时明确写‘随机性/证据不足，不新增规则’，防止事后过拟合。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
    ]


def _fallback_reflections(
    answer: dict[str, Any], entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    hypotheses = {
        str(item.get("id") or ""): item
        for item in answer.get("hypotheses") or []
        if isinstance(item, dict)
    }
    rows = []
    for entry in entries:
        hypothesis_id = str(entry.get("id") or "")
        rows.append(
            {
                "id": hypothesis_id,
                "category": _category(hypothesis_id, hypotheses.get(hypothesis_id)),
                "verdict": entry.get("verdict"),
                "actual": str(entry.get("actual") or "")[:1200],
                "failure_mode": (
                    "" if str(entry.get("failure_mode") or "") in PLACEHOLDER_FAILURE_MODES
                    else str(entry.get("failure_mode"))
                ),
                "diagnosis": "",
                "missed_signal": "",
                "ranking_error": "",
                "correction": "",
                "reusable_lesson": "",
                "proposed_rule": "",
                "review_status": "pending",
            }
        )
    return rows


def _merge_generated_reflections(
    base: list[dict[str, Any]], content: str | None
) -> tuple[list[dict[str, Any]], bool]:
    if not content:
        return base, False
    payload = llm_refine._extract_json(content)
    generated = payload.get("reflections") if isinstance(payload, dict) else None
    if not isinstance(generated, list):
        return base, False
    by_id = {
        str(item.get("id") or ""): item
        for item in generated
        if isinstance(item, dict) and item.get("id")
    }
    fields = (
        "failure_mode",
        "diagnosis",
        "missed_signal",
        "ranking_error",
        "correction",
        "reusable_lesson",
        "proposed_rule",
    )
    matched = False
    result = []
    for row in base:
        generated_row = by_id.get(str(row["id"]))
        merged = dict(row)
        if generated_row:
            matched = True
            for field in fields:
                value = str(generated_row.get(field) or "").strip()[:2000]
                if value or field != "failure_mode":
                    merged[field] = value
        result.append(merged)
    return result, matched


def sync_reflections(
    ledger_dir: str | Path,
    learning_dir: str | Path,
    *,
    dates: Iterable[str] | None = None,
    use_llm: bool = True,
    llm_complete: LLMComplete | None = None,
) -> dict[str, Any]:
    ledger = Path(ledger_dir)
    learning = Path(learning_dir)
    selected = set(dates or [])
    complete = llm_complete or llm_refine.complete
    summary = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "pending": 0,
        "orphaned": [],
        "errors": [],
    }
    for verdict_path in sorted(ledger.glob("*.verdict.json")):
        verdict = _read_json(verdict_path)
        if verdict is None:
            summary["errors"].append(f"{verdict_path.name}: unreadable")
            continue
        date = str(verdict.get("date") or verdict_path.name.split(".", 1)[0])
        if selected and date not in selected:
            continue
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for entry in verdict.get("verdicts") or []:
            if not isinstance(entry, dict) or entry.get("verdict") not in ACTIONABLE_VERDICTS:
                continue
            key = (str(entry.get("agent") or "unknown").lower(), _source_for(entry))
            grouped.setdefault(key, []).append(entry)
        for (agent, source), entries in grouped.items():
            answer_path, answer = _answer_for(
                ledger,
                date=date,
                agent=agent,
                source=source,
                hypothesis_ids={str(entry.get("id") or "") for entry in entries},
            )
            if answer_path is None or answer is None:
                summary["orphaned"].append(f"{date}/{agent}/{source}: answer missing")
                continue
            context = _bounded_context(answer, entries)
            fingerprint = hashlib.sha256(
                json.dumps(context, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            out_path = learning / "reflections" / f"{date}.reflection.{agent}.{source}.json"
            existing = _read_json(out_path)
            retry_pending = bool(
                existing
                and existing.get("status") == "pending_llm"
                and use_llm
            )
            if (
                existing
                and existing.get("source_fingerprint") == fingerprint
                and not retry_pending
            ):
                summary["skipped"] += 1
                continue
            rows = _fallback_reflections(answer, entries)
            content: str | None = None
            provider = None
            reason = "LLM disabled"
            if use_llm:
                content, provider, reason = complete(
                    _reflection_messages(context), timeout=60, temperature=0.1
                )
            rows, generated = _merge_generated_reflections(rows, content)
            status = "pending_review" if generated else "pending_llm"
            payload = {
                "schema_version": REFLECTION_SCHEMA_VERSION,
                "date": date,
                "agent": agent,
                "source": source,
                "status": status,
                "review_status": "pending",
                "source_fingerprint": fingerprint,
                "answer_ref": str(answer_path.relative_to(ledger.parent.parent.parent)),
                "verdict_ref": str(verdict_path.relative_to(ledger.parent.parent.parent)),
                "provider": getattr(provider, "name", None),
                "model": getattr(provider, "model", None),
                "degrade_reason": "" if generated else str(reason or "unparseable LLM output")[:500],
                "generated_at": _now(),
                "reflections": rows,
            }
            existed = out_path.exists()
            _atomic_json(out_path, payload)
            summary["updated" if existed else "created"] += 1
            if not generated:
                summary["pending"] += 1
    return summary


def approve_reflection(
    reflection_path: str | Path,
    lessons_path: str | Path,
    *,
    hypothesis_ids: Iterable[str] | None = None,
) -> dict[str, int]:
    path = Path(reflection_path)
    payload = _read_json(path)
    if payload is None:
        raise ValueError("reflection JSON 不可读")
    selected = set(hypothesis_ids or [])
    approved = skipped = 0
    for row in payload.get("reflections") or []:
        if not isinstance(row, dict):
            continue
        hypothesis_id = str(row.get("id") or "")
        if selected and hypothesis_id not in selected:
            continue
        lesson = str(row.get("reusable_lesson") or "").strip()
        if not lesson:
            raise ValueError(f"{hypothesis_id or 'unknown'} 尚无 reusable_lesson，不能批准")
        record = {
            "schema_version": LESSON_SCHEMA_VERSION,
            "id": _stable_id(
                "lesson",
                payload.get("source_fingerprint"),
                hypothesis_id,
            ),
            "status": "approved",
            "date": payload.get("date"),
            "agent": payload.get("agent"),
            "source": payload.get("source"),
            "hypothesis_id": hypothesis_id,
            "category": row.get("category"),
            "failure_mode": row.get("failure_mode"),
            "lesson": lesson[:2000],
            "rule": str(row.get("proposed_rule") or "").strip()[:2000],
            "reflection_ref": str(Path("reflections") / path.name),
            "approved_at": _now(),
        }
        if _append_jsonl_once(Path(lessons_path), record):
            approved += 1
        else:
            skipped += 1
    return {"approved": approved, "skipped": skipped}


def _annotation_tail(text: str) -> str:
    if ANNOTATION_HEADING not in text:
        return ""
    tail = text.split(ANNOTATION_HEADING, 1)[1]
    if VERDICT_MARKER in tail:
        tail = tail.split(VERDICT_MARKER, 1)[0]
    match = re.search(r"\n## (?!#)", tail)
    return tail[: match.start()] if match else tail


def extract_annotation_rules(path: str | Path) -> list[dict[str, str]]:
    md_path = Path(path)
    try:
        tail = _annotation_tail(md_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return []
    blocks = re.split(r"(?m)^###\s+批注\s+(\d+)\s*$", tail)
    rows: list[dict[str, str]] = []
    for index in range(1, len(blocks), 2):
        number, body = blocks[index], blocks[index + 1]
        values = {}
        for label, key in (
            ("问题", "issue"),
            ("应该改成", "correction"),
            ("下次硬规则", "rule"),
        ):
            match = re.search(rf"(?m)^-\s*{label}[：:]\s*(.+?)\s*$", body)
            values[key] = match.group(1).strip() if match else ""
        if values["rule"]:
            rows.append({"annotation": number, **values})
    return rows


def sync_rule_candidates(
    ledger_dir: str | Path,
    candidates_path: str | Path,
) -> dict[str, int]:
    ledger = Path(ledger_dir)
    target = Path(candidates_path)
    existing = {str(row.get("id") or "") for row in _read_jsonl(target)}
    created = skipped = 0
    for md_path in sorted(ledger.glob("20??-??-??.md")):
        date = md_path.name[:10]
        for row in extract_annotation_rules(md_path):
            candidate_id = _stable_id("rule", date, row["annotation"], row["rule"])
            if candidate_id in existing:
                skipped += 1
                continue
            record = {
                "schema_version": RULE_SCHEMA_VERSION,
                "id": candidate_id,
                "status": "pending",
                "date": date,
                "annotation": row["annotation"],
                "issue": row["issue"],
                "correction": row["correction"],
                "rule": row["rule"],
                "source_ref": str(md_path),
                "created_at": _now(),
            }
            if _append_jsonl_once(target, record):
                existing.add(candidate_id)
                created += 1
    return {"created": created, "skipped": skipped}


def set_rule_status(
    candidates_path: str | Path,
    candidate_id: str,
    status: str,
) -> dict[str, Any]:
    if status not in {"approved", "rejected"}:
        raise ValueError("规则状态只能是 approved/rejected")
    rows = _read_jsonl(Path(candidates_path))
    latest = next(
        (row for row in reversed(rows) if str(row.get("id") or "") == candidate_id),
        None,
    )
    if latest is None:
        raise ValueError(f"规则候选不存在：{candidate_id}")
    if latest.get("status") == status:
        return latest
    event = dict(latest)
    event["status"] = status
    event["updated_at"] = _now()
    event["event_id"] = _stable_id("rule-event", candidate_id, status, event["updated_at"])
    path = Path(candidates_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def render_learning_prompt(
    lessons_path: str | Path,
    rules_path: str | Path,
    *,
    limit: int = 5,
) -> str:
    lessons = [
        row for row in _read_jsonl(Path(lessons_path)) if row.get("status") == "approved"
    ][-max(0, limit):]
    latest_rules: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(Path(rules_path)):
        if row.get("id"):
            latest_rules[str(row["id"])] = row
    rules = [row for row in latest_rules.values() if row.get("status") == "approved"]
    rules = rules[-max(0, limit):]
    if not lessons and not rules:
        return "（暂无已批准的历史 lesson / 硬规则；不要读取 pending 候选。）"
    lines = ["【已批准的历史学习上下文｜仅作事前检查，不是市场事实】"]
    for row in lessons:
        lines.append(
            f"- Lesson {row.get('date')}/{row.get('agent')}/{row.get('hypothesis_id')}："
            f"{row.get('lesson')}"
        )
    for row in rules:
        lines.append(f"- 硬规则 {row.get('date')}：{row.get('rule')}")
    lines.append("只应用与今天题式相关的项；若当前证据冲突，说明冲突而不是机械套用。")
    return "\n".join(lines)
