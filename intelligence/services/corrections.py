"""纠偏回路：从「你纠正我」里学，而不是从点击里猜 (corrections.jsonl)。

用户不满意 foresight 的回答时会纠正它。把每次纠正记成一条高信号记录
append 到 ``users/<id>/corrections.jsonl``（每行一条 JSON，已 gitignore）：

- ``original``    它原来的说法 / 答错的点（可选）；
- ``correction``  我纠正成什么（必填）；
- ``principle``   从这次纠正抽象出的、可复用的原则（可选，最该被记住的部分）；
- ``themes``      关联题材（可选）。

下次 foresight 发问前会读最近 N 条纠偏注入系统提示词（「别再犯同类错误」），
让它在用户框架里越用越准——这条**不靠点击猜偏好**，只靠显式纠正学方法论。

本模块只用标准库，不依赖 duckdb / 联网，可离线运行、可独立单测。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from intelligence.services.memory_gate import (
    PromotionDecision,
    promotion_metadata,
)

DEFAULT_WINDOW = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def _clean_terms(values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        key = _norm(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def record_correction(
    path: str | Path,
    *,
    correction: str,
    original: str | None = None,
    principle: str | None = None,
    themes: list[str] | None = None,
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """把一条纠正 append 到 ``corrections.jsonl``，返回 ``(path, record)``。

    ``correction`` 为空（去空白后）时抛 ``ValueError``——一条纠偏至少要说清纠成什么。
    """
    corrected = str(correction or "").strip()
    if not corrected:
        raise ValueError("correction 不能为空：至少说清你把它纠正成什么")
    p = Path(path).expanduser()
    record: dict[str, Any] = {
        "ts": ts or _now().isoformat(timespec="seconds"),
        "correction": corrected,
        "themes": _clean_terms(themes),
    }
    if original and str(original).strip():
        record["original"] = str(original).strip()
    if principle and str(principle).strip():
        record["principle"] = str(principle).strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def record_validated_preference(
    path: str | Path,
    *,
    preference: str,
    decision: PromotionDecision,
    themes: list[str] | None = None,
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Append one explicit, gate-approved user preference or correction."""

    text = str(preference or "").strip()
    provenance = dict(decision.provenance)
    if (
        decision.reason != "explicit_user_correction"
        or provenance.get("record_type")
        not in {"user_correction", "user_preference"}
        or not provenance.get("correction_ts")
    ):
        raise ValueError("preference promotion requires correction authority")
    promotion = promotion_metadata(decision, text)
    record: dict[str, Any] = {
        "ts": ts or _now().isoformat(timespec="seconds"),
        "correction": text,
        "principle": text,
        "themes": _clean_terms(themes),
        "promotion": promotion,
    }
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def load_corrections(
    path: str | Path,
    window: int = DEFAULT_WINDOW,
) -> tuple[list[dict[str, Any]], str | None]:
    """读取最近 ``window`` 条纠偏记录（按出现顺序）。文件不存在时返回空列表。"""
    p = Path(path).expanduser()
    if not p.exists():
        return [], None
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        return [], f"纠偏记录读取失败：{exc}"
    raw: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if isinstance(rec, dict):
            raw.append(rec)
    # 记忆退出机制（memory_status）：先应用追加式状态覆盖（归档/撤销的不再召回），
    # 台账无状态行时行为不变。
    from intelligence.services.memory_status import apply_status_overrides

    records = [
        rec for rec in apply_status_overrides(raw)
        if str(rec.get("correction") or "").strip()
    ]
    if window and window > 0:
        records = records[-window:]
    return records, None


DEFAULT_RESIDENT_LIMIT = 5


def select_resident_principles(
    records: list[dict[str, Any]],
    *,
    limit: int = DEFAULT_RESIDENT_LIMIT,
) -> list[dict[str, Any]]:
    """常驻概览：带 principle 的纠偏每次都带着，不靠本轮题材标签命中。"""
    resident = [
        rec
        for rec in records
        if isinstance(rec, dict) and str(rec.get("principle") or "").strip()
    ]
    resident.sort(key=lambda rec: str(rec.get("ts") or ""), reverse=True)
    return resident[: max(0, int(limit))]


def render_for_prompt(records: list[dict[str, Any]]) -> str:
    """把纠偏记录渲染成注入系统提示词的要点列表（最近的在前，原则优先呈现）。"""
    lines: list[str] = []
    for rec in reversed(records):  # 最近的纠正放最前
        if not isinstance(rec, dict):
            continue
        correction = str(rec.get("correction") or "").strip()
        if not correction:
            continue
        principle = str(rec.get("principle") or "").strip()
        original = str(rec.get("original") or "").strip()
        parts: list[str] = []
        if principle:
            parts.append(f"原则：{principle}")
        if original:
            parts.append(f"别再说「{original}」")
        parts.append(f"应为：{correction}")
        themes = [str(t).strip() for t in (rec.get("themes") or []) if str(t).strip()]
        tag = f"（{'、'.join(themes)}）" if themes else ""
        lines.append(f"- {'；'.join(parts)}{tag}")
    return "\n".join(lines)
