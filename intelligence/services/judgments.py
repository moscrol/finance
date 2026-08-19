"""核心判断台账：把你深挖时的「核心判断」沉淀成机器可读账本 (judgments.jsonl)。

潜意识模式里你深挖一个题材后，会用 ``subconscious note --memo`` 压一段「核心判断 +
可证伪点」。这段以前只进 Obsidian 日志（人类层）给你读，机器读不回来。本账本把它
在 ``commit`` 时同步 append 到 ``users/<id>/judgments.jsonl``（每行一条 JSON，已
gitignore），让 foresight 下次发问能**站在你旧判断上往前推一层**，而不是每轮从零重述：

- ``memo``        这段核心判断正文（必填）；
- ``themes``      这段判断关联的题材（可选）；
- ``stocks``      关联个股（可选）；
- ``session_id``  来自哪轮潜意识会话（可选，便于回溯）。

下次 foresight 发问前读最近 N 条核心判断注入系统提示词，让新追问承接你的既有判断、
往前推一层或找它的反例，而不是重复你已经想清楚的东西。

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
from intelligence.services.memory_status import memory_record_id

DEFAULT_WINDOW = 10


def _is_recallable_judgment(rec: dict[str, Any]) -> bool:
    """pending 前瞻判断还没入账，不能当已确认核心判断召回。"""
    if rec.get("status") == "pending":
        return False
    if rec.get("record_type") == "foresight_judgment" and rec.get("status") != "accepted":
        return False
    return bool(str(rec.get("memo") or rec.get("claim") or "").strip())

# 记录身份（Q3）：新增行写稳定 id=sha256(kind+ts+content)[:12]，同秒并发不碰撞；
# 存量旧行不回填，仍按 ts 退出（见 memory_status 模块迁移说明）。
_RECORD_KIND = "judgment"


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


def record_judgment(
    path: str | Path,
    *,
    memo: str,
    themes: list[str] | None = None,
    stocks: list[str] | None = None,
    session_id: str | None = None,
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """把一段核心判断 append 到 ``judgments.jsonl``，返回 ``(path, record)``。

    ``memo`` 为空（去空白后）时抛 ``ValueError``——一条核心判断至少要有正文。
    """
    text = str(memo or "").strip()
    if not text:
        raise ValueError("memo 不能为空：核心判断至少要有正文")
    p = Path(path).expanduser()
    record_ts = ts or _now().isoformat(timespec="seconds")
    record: dict[str, Any] = {
        "ts": record_ts,
        "id": memory_record_id(_RECORD_KIND, record_ts, text),
        "memo": text,
        "themes": _clean_terms(themes),
        "stocks": _clean_terms(stocks),
    }
    if session_id and str(session_id).strip():
        record["session_id"] = str(session_id).strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def record_validated_judgment(
    path: str | Path,
    *,
    memo: str,
    decision: PromotionDecision,
    themes: list[str] | None = None,
    stocks: list[str] | None = None,
    session_id: str | None = None,
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Append one gate-approved lesson bound to exact reviewed content."""

    text = str(memo or "").strip()
    provenance = dict(decision.provenance)
    if (
        decision.reason != "reviewed_checkpoint_lesson"
        or not provenance.get("checkpoint_id")
        or provenance.get("verdict") not in {"hit", "partial", "miss"}
    ):
        raise ValueError("judgment promotion requires checkpoint lesson authority")
    promotion = promotion_metadata(decision, text)
    record_ts = ts or _now().isoformat(timespec="seconds")
    record: dict[str, Any] = {
        "ts": record_ts,
        "id": memory_record_id(_RECORD_KIND, record_ts, text),
        "memo": text,
        "themes": _clean_terms(themes),
        "stocks": _clean_terms(stocks),
        "promotion": promotion,
    }
    if session_id and str(session_id).strip():
        record["session_id"] = str(session_id).strip()
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def load_judgments(
    path: str | Path,
    window: int = DEFAULT_WINDOW,
) -> tuple[list[dict[str, Any]], str | None]:
    """读取最近 ``window`` 条核心判断（按出现顺序）。文件不存在时返回空列表。"""
    p = Path(path).expanduser()
    if not p.exists():
        return [], None
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        return [], f"核心判断台账读取失败：{exc}"
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
        if _is_recallable_judgment(rec)
    ]
    if window and window > 0:
        records = records[-window:]
    return records, None


def render_for_prompt(
    records: list[dict[str, Any]],
    *,
    as_of: str | None = None,
) -> str:
    """把核心判断渲染成注入系统提示词的要点列表（最近的在前，带题材/日期标签）。"""
    from intelligence.services.track_contract import downgrade_expired_text

    lines: list[str] = []
    for rec in reversed(records):  # 最近的判断放最前
        if not isinstance(rec, dict):
            continue
        memo = str(rec.get("memo") or "").strip()
        if not memo:
            continue
        memo = downgrade_expired_text(
            memo,
            valid_until=str(rec.get("valid_until") or "") or None,
            as_of=as_of,
        )
        tags = [str(t).strip() for t in (rec.get("themes") or []) if str(t).strip()]
        tags += [str(s).strip() for s in (rec.get("stocks") or []) if str(s).strip()]
        date = str(rec.get("ts") or "")[:10]
        head = "、".join(tags) if tags else ""
        suffix = f"（{date}）" if date else ""
        if head:
            lines.append(f"- {head}：{memo}{suffix}")
        else:
            lines.append(f"- {memo}{suffix}")
    return "\n".join(lines)
