"""越用越懂：用户反馈回路 (interactions.jsonl) + 题材/个股亲和度。

「猜你想问」生成问题后，用户会点开 / 追问 / 喜欢 / 忽略 / 打分。把这些反馈
append 到 ``users/<id>/interactions.jsonl``（每行一条 JSON，已 gitignore），
就是「越用越懂你」的燃料：

1. :func:`record_interaction` —— 落一条反馈（CLI ``record-interaction`` 调用）。
2. :func:`load_interactions` —— 读最近 N 条反馈。
3. :func:`compute_affinity` —— 把反馈按「时间衰减 + 权重」聚合成每个题材/个股的
   亲和度分数，供 foresight 排序加一项**可解释**加成（近期被正向互动的题材/票排更前，
   被忽略/打低分的降权）。

本模块只用标准库，不依赖 duckdb / 联网，可离线运行、可独立单测。
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 反馈类型 -> 默认权重（正向 > 0 升权，负向 < 0 降权）。可被 --weight / --rating 覆盖。
KIND_WEIGHTS: dict[str, float] = {
    "pin": 2.0,
    "like": 1.5,
    "follow": 1.5,
    "ask": 1.2,
    "click": 1.0,
    "open": 1.0,
    "view": 0.3,
    "impression": 0.1,
    "skip": -0.5,
    "ignore": -0.8,
    "dismiss": -1.0,
    "mute": -1.5,
    "dislike": -1.5,
    "rate": 0.0,  # rate 用 --rating 映射，见 rating_to_weight
}
KNOWN_KINDS = tuple(KIND_WEIGHTS.keys())

DEFAULT_WINDOW = 200
DEFAULT_HALF_LIFE_DAYS = 14.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(text: Any) -> str:
    """归一化用于匹配：去空白 + 小写（保留中英文字符与数字本体）。"""
    return re.sub(r"\s+", "", str(text or "")).lower()


def rating_to_weight(rating: Any) -> float:
    """把 1~5 星评分映射到 [-1, 1]：(r-3)/2，越界裁剪。"""
    try:
        r = float(rating)
    except (TypeError, ValueError):
        return 0.0
    return max(-1.0, min(1.0, (r - 3.0) / 2.0))


def resolve_weight(kind: str, *, weight: Any = None, rating: Any = None) -> float:
    """决定一条反馈的最终权重：显式 ``weight`` > ``rating`` 映射 > ``kind`` 默认。"""
    if weight is not None:
        try:
            return float(weight)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass
    if rating is not None:
        # rate 满分 ≈ like 量级（×1.5）。
        return round(rating_to_weight(rating) * 1.5, 4)
    return KIND_WEIGHTS.get(str(kind or "").strip().lower(), 0.0)


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


def record_interaction(
    path: str | Path,
    *,
    kind: str,
    question: str | None = None,
    themes: list[str] | None = None,
    stocks: list[str] | None = None,
    weight: float | None = None,
    rating: float | None = None,
    note: str | None = None,
    ts: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """把一条反馈 append 到 ``interactions.jsonl``，返回 ``(path, record)``。"""
    p = Path(path).expanduser()
    record: dict[str, Any] = {
        "ts": ts or _now().isoformat(timespec="seconds"),
        "kind": str(kind or "").strip().lower(),
        "weight": resolve_weight(kind, weight=weight, rating=rating),
        "themes": _clean_terms(themes),
        "stocks": _clean_terms(stocks),
    }
    if rating is not None:
        try:
            record["rating"] = float(rating)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            pass
    if question and str(question).strip():
        record["question"] = str(question).strip()
    if note and str(note).strip():
        record["note"] = str(note).strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return p, record


def load_interactions(
    path: str | Path,
    window: int = DEFAULT_WINDOW,
) -> tuple[list[dict[str, Any]], str | None]:
    """读取最近 ``window`` 条反馈记录（按出现顺序）。文件不存在时返回空列表。"""
    p = Path(path).expanduser()
    if not p.exists():
        return [], None
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception as exc:  # pragma: no cover - defensive
        return [], f"反馈记录读取失败：{exc}"
    records: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    if window and window > 0:
        records = records[-window:]
    return records, None


@dataclass(frozen=True)
class Affinity:
    """单个题材/个股的亲和度。``kind`` 取 ``theme`` 或 ``stock``。"""

    label: str
    norm: str
    kind: str
    score: float


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _decay(age_days: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        return 1.0
    if age_days <= 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def compute_affinity(
    records: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> list[Affinity]:
    """把反馈聚合成每个题材/个股的亲和度（时间衰减加权求和），按分数降序返回。

    分数 = Σ over 反馈 ``weight * 0.5^(age_days / half_life_days)``。正分代表近期
    正向互动（升权），负分代表近期被忽略/打低分（降权）。``now`` 显式传入即可
    确定性复现。
    """
    ref = now or _now()
    # (kind, norm) -> [score_acc, label]
    acc: dict[tuple[str, str], list[Any]] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        try:
            weight = float(rec.get("weight", 0.0))
        except (TypeError, ValueError):
            continue
        if weight == 0.0:
            continue
        ts = _parse_ts(rec.get("ts"))
        age_days = (ref - ts).total_seconds() / 86400.0 if ts else 0.0
        factor = weight * _decay(age_days, half_life_days)
        if factor == 0.0:
            continue
        for kind, field in (("theme", "themes"), ("stock", "stocks")):
            for term in rec.get(field) or []:
                label = str(term).strip()
                norm = _norm(label)
                if not norm:
                    continue
                slot = acc.setdefault((kind, norm), [0.0, label])
                slot[0] += factor
                slot[1] = label  # keep latest spelling
    out = [
        Affinity(label=label, norm=norm, kind=kind, score=round(score, 4))
        for (kind, norm), (score, label) in acc.items()
        if round(score, 4) != 0.0
    ]
    out.sort(key=lambda a: (-a.score, a.kind, a.label))
    return out
