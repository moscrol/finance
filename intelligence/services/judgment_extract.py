"""KC-09：前瞻判断抽取。只提案，不直写入账。

Knevo 八字段：判断原文 / 前提假设 / 情景分支 / verify_by / 推翻条件 /
置信度 / 依据 / 上下文快照。写入现有 ``judgments.jsonl``（pending），
可证伪那一刀在用户批处理 accept 后登记进 ``checkpoints.jsonl``。
禁止再开 ``judgments-ledger.jsonl``。置信度只准 高/中/低。
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.services.checkpoints import register_checkpoint
from intelligence.services.memory_status import memory_record_id

CONFIDENCE_LEVELS = ("高", "中", "低")
RECORD_TYPE = "foresight_judgment"
SOURCE = "foresight_judgment"
_RECORD_KIND = "foresight_judgment"

_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_Q_RE = re.compile(r"Q([1-4])")
_COND_RE = re.compile(r"若([^。\n]{2,80})则([^。\n]{2,80})")
_UPGRADE_RE = re.compile(r"判断升级需要：\s*([^\n]+)")
_REVIEW_RE = re.compile(r"建议\s*(\d+)\s*天内复查（至\s*(20\d{2}-\d{2}-\d{2})）")
_HIGH_CONF_RE = re.compile(r"高置信")
_LOW_CONF_RE = re.compile(r"低置信")
_CITATION_RE = re.compile(r"\[([A-Z]\d+)\]")


@dataclass(frozen=True)
class VerifyBy:
    due: str
    criterion: str

    def to_dict(self) -> dict[str, str]:
        return {"due": self.due, "criterion": self.criterion}


@dataclass(frozen=True)
class EvidenceCite:
    ref: str
    hash: str

    def to_dict(self) -> dict[str, str]:
        return {"ref": self.ref, "hash": self.hash}


@dataclass(frozen=True)
class ForesightJudgment:
    claim: str
    assumptions: tuple[str, ...]
    scenarios: tuple[str, ...]
    verify_by: VerifyBy
    invalidation: str
    confidence: str
    evidence: tuple[EvidenceCite, ...]
    context_snapshot: tuple[tuple[str, str], ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "assumptions": list(self.assumptions),
            "scenarios": list(self.scenarios),
            "verify_by": self.verify_by.to_dict(),
            "invalidation": self.invalidation,
            "confidence": self.confidence,
            "evidence": [item.to_dict() for item in self.evidence],
            "context_snapshot": dict(self.context_snapshot),
        }


def extract_foresight_judgments(
    text: str,
    *,
    as_of: str | None,
    query: str,
    citations: Sequence[tuple[str, str, str]] = (),
    theme: str | None = None,
) -> tuple[ForesightJudgment, ...]:
    """确定性抽取。没有 verify_by（日期或季度）的前瞻句不建档。"""
    body = str(text or "")
    found: list[ForesightJudgment] = []
    seen: set[str] = set()
    cite_map = {tag: (source, detail) for tag, source, detail in citations}
    for match in _COND_RE.finditer(body):
        condition = match.group(1).strip()
        outcome = match.group(2).strip()
        claim = f"若{condition}则{outcome}"
        due = _verify_due(condition + outcome + match.group(0), as_of)
        if due is None:
            continue
        item = _build(
            claim=claim,
            criterion=condition,
            due=due,
            as_of=as_of,
            query=query,
            theme=theme,
            cite_map=cite_map,
            raw=match.group(0),
        )
        key = _content_key(item)
        if key not in seen:
            seen.add(key)
            found.append(item)
    upgrade = _UPGRADE_RE.search(body)
    review = _REVIEW_RE.search(body)
    if upgrade and review:
        criterion = _clean_markup(upgrade.group(1))
        due = review.group(2)
        claim = f"判断升级需要：{criterion}"
        item = _build(
            claim=claim,
            criterion=criterion,
            due=due,
            as_of=as_of,
            query=query,
            theme=theme,
            cite_map=cite_map,
            raw=claim,
        )
        key = _content_key(item)
        if key not in seen:
            seen.add(key)
            found.append(item)
    return tuple(found)


def propose_judgments(
    judgments_path: str | Path,
    items: Sequence[ForesightJudgment],
    *,
    ts: str | None = None,
) -> list[dict[str, Any]]:
    """只写 pending。已有相同内容键的 pending/accepted 不再写。"""
    path = Path(judgments_path).expanduser()
    existing = _load_raw(path)
    known = {
        str(row.get("content_key") or "")
        for row in existing
        if row.get("record_type") == RECORD_TYPE
    }
    written: list[dict[str, Any]] = []
    for item in items:
        key = _content_key(item)
        if key in known:
            continue
        record_ts = ts or _now_iso()
        payload = item.to_record()
        record = {
            "ts": record_ts,
            "id": memory_record_id(_RECORD_KIND, record_ts, item.claim),
            "record_type": RECORD_TYPE,
            "status": "pending",
            "content_key": key,
            "memo": item.claim,
            **payload,
        }
        _append(path, record)
        known.add(key)
        written.append(record)
    return written


def list_pending(judgments_path: str | Path) -> list[dict[str, Any]]:
    return [
        row
        for row in _load_raw(judgments_path)
        if row.get("record_type") == RECORD_TYPE and row.get("status") == "pending"
    ]


def accept_judgments(
    judgments_path: str | Path,
    checkpoints_path: str | Path,
    *,
    ids: Sequence[str] | None = None,
    accept_all: bool = False,
    ts: str | None = None,
) -> list[dict[str, Any]]:
    """批处理入账：pending → accepted，并登记 checkpoint。无直写 accepted 的抽取入口。"""
    if not accept_all and not ids:
        return []
    wanted = {str(item) for item in (ids or ())}
    pending = list_pending(judgments_path)
    existing = _load_raw(judgments_path)
    accepted_keys = {
        str(row.get("source_pending_id") or "")
        for row in existing
        if row.get("record_type") == RECORD_TYPE and row.get("status") == "accepted"
    }
    written: list[dict[str, Any]] = []
    for row in pending:
        if not accept_all and row["id"] not in wanted:
            continue
        if row["id"] in accepted_keys:
            continue
        record_ts = ts or _now_iso()
        accepted = {
            **row,
            "ts": record_ts,
            "id": memory_record_id(_RECORD_KIND, record_ts, f"accepted:{row['id']}"),
            "status": "accepted",
            "source_pending_id": row["id"],
        }
        accepted["confidence"] = _bound_confidence(accepted.get("confidence"))
        _append(judgments_path, accepted)
        verify = accepted.get("verify_by") or {}
        register_checkpoint(
            checkpoints_path,
            claim=str(verify.get("criterion") or accepted.get("claim") or ""),
            due=str(verify.get("due") or ""),
            category="前瞻判断",
            source=SOURCE,
            source_judgment_ts=record_ts,
            session_id=accepted.get("id"),
            metric={"type": "manual"},
            ts=record_ts,
        )
        written.append(accepted)
    return written


def propose_from_answer(
    *,
    judgments_path: str | Path,
    query: str,
    answer: str,
    as_of: str | None,
    theme: str | None = None,
    citations: Sequence[Any] = (),
) -> list[dict[str, Any]]:
    packed: list[tuple[str, str, str]] = []
    for item in citations or ():
        tag = str(getattr(item, "tag", "") or "")
        source = str(getattr(item, "source", "") or "")
        detail = str(getattr(item, "detail", "") or "")
        if tag:
            packed.append((tag, source, detail))
    return propose_judgments(
        judgments_path,
        extract_foresight_judgments(
            answer,
            as_of=as_of,
            query=query,
            citations=packed,
            theme=theme,
        ),
    )


def _build(
    *,
    claim: str,
    criterion: str,
    due: str,
    as_of: str | None,
    query: str,
    theme: str | None,
    cite_map: dict[str, tuple[str, str]],
    raw: str,
) -> ForesightJudgment:
    tags = _CITATION_RE.findall(raw) or list(cite_map)
    evidence: list[EvidenceCite] = []
    for tag in dict.fromkeys(tags):
        source, detail = cite_map.get(tag, ("", ""))
        digest = hashlib.sha256(f"{source}|{detail}".encode("utf-8")).hexdigest()[:16]
        evidence.append(EvidenceCite(ref=tag, hash=digest))
    snapshot = (("query", query),)
    if theme:
        snapshot = snapshot + (("theme", theme),)
    if as_of:
        snapshot = snapshot + (("as_of", as_of),)
    return ForesightJudgment(
        claim=claim,
        assumptions=(),
        scenarios=(),
        verify_by=VerifyBy(due=due, criterion=criterion),
        invalidation="",
        confidence=_confidence_from_text(raw),
        evidence=tuple(evidence),
        context_snapshot=snapshot,
    )


def _clean_markup(text: str) -> str:
    return str(text or "").strip().strip("*").strip().rstrip("。")


def _verify_due(text: str, as_of: str | None) -> str | None:
    dated = _DATE_RE.search(text)
    if dated:
        return dated.group(1)
    quarter = _Q_RE.search(text)
    if quarter is None:
        return None
    year = _year_from(as_of)
    if year is None:
        return None
    last_day = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}[int(quarter.group(1))]
    return f"{year}-{last_day}"


def _year_from(as_of: str | None) -> int | None:
    match = _DATE_RE.search(str(as_of or ""))
    if match:
        return int(match.group(1)[:4])
    return None


def _confidence_from_text(text: str) -> str:
    if _HIGH_CONF_RE.search(text):
        return "高"
    if _LOW_CONF_RE.search(text):
        return "低"
    return "中"


def _bound_confidence(raw: Any) -> str:
    text = str(raw or "").strip()
    if text in CONFIDENCE_LEVELS:
        return text
    return "中"


def _content_key(item: ForesightJudgment) -> str:
    payload = f"{item.claim}|{item.verify_by.due}|{item.verify_by.criterion}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _load_raw(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def _append(path: str | Path, record: dict[str, Any]) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
