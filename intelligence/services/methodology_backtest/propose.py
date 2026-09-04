"""「纠偏 → 候选规则」的人工登记入口（设计稿 §3.4 P1 第三行）。

一次纠偏是一行 ``corrections.jsonl``；要让它能被历史检验，得先翻译成一条声明式规则。这里不做
自动翻译（那是 LLM 的不确定性进度量本身），只把人写的谓词短句解析成规则 JSON、过一遍白名单校验、
把纠偏记录的 id / ts / 原文钉进 ``provenance``，然后落 ``methodology/rules/<rule_id>.v<version>.json``。

谓词短句语法（一个 ``--pred`` 一条）::

    dual_red_strict == true
    dual_red_streak >= 3
    dual_red_streak@1 >= 2            # @lag：之前第 1 个交易日
    market:market_stage in 主升阶段,主升   # entity:label；in / not_in 用逗号分列表
    market:volume_surge@1 == true

值的类型只按字面猜（true/false → 布尔，数字 → 数值，其余 → 文本或列表），合法性交给 ``rules.validate_rule``。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .rules import (
    DEFAULT_MIN_N,
    METRICS,
    SCOPE_ENTITY_TYPES,
    UNIVERSES,
    Rule,
    RuleError,
    RuleValidationError,
    parse_rule,
)

_PRED_RE = re.compile(
    r"^\s*(?:(?P<entity>[a-z]+):)?(?P<label>[a-z][a-z0-9_]*)(?:@(?P<lag>\d+))?\s+"
    r"(?P<op>==|!=|>=|<=|>|<|in|not_in)\s+(?P<value>.+?)\s*$"
)
_SUCCESS_RE = re.compile(r"^\s*(?P<metric>[a-z_]+)\s+(?P<horizon>\d+)\s+(?P<op>>=|<=|>|<)\s+(?P<value>-?\d+(?:\.\d+)?)\s*$")


def _scalar(text: str) -> Any:
    t = text.strip()
    low = t.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        if re.fullmatch(r"-?\d+", t):
            return int(t)
        return float(t)
    except ValueError:
        return t


def parse_predicate(text: str) -> dict[str, Any]:
    """把一条谓词短句解析成规则 JSON 里的谓词对象。语法错抛 ValueError（白名单校验在后面）。"""
    m = _PRED_RE.match(text or "")
    if not m:
        raise ValueError(f"谓词短句不合语法：{text!r}（形如 `dual_red_streak@1 >= 3` 或 `market:market_stage in 主升阶段,主升`）")
    op = m.group("op")
    raw = m.group("value")
    if op in ("in", "not_in"):
        value: Any = [_scalar(part) for part in raw.split(",") if part.strip()]
    else:
        value = _scalar(raw)
    pred: dict[str, Any] = {"label": m.group("label"), "op": op, "value": value, "lag": int(m.group("lag") or 0)}
    if m.group("entity"):
        pred["entity"] = m.group("entity")
    return pred


def parse_success(text: str) -> dict[str, Any]:
    """``fwd_return 5 > 0`` → success 对象。"""
    m = _SUCCESS_RE.match(text or "")
    if not m:
        raise ValueError(f"success 短句不合语法：{text!r}（形如 `fwd_return 5 > 0`）")
    return {"metric": m.group("metric"), "horizon": int(m.group("horizon")), "op": m.group("op"), "value": float(m.group("value"))}


def correction_provenance(record: dict[str, Any], *, user: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """从一条 corrections.jsonl 记录抽溯源块：id 优先、其次 ts；正文取 principle 否则 correction。"""
    ref = str(record.get("id") or record.get("ts") or "").strip()
    if not ref:
        raise ValueError("纠偏记录没有 id 也没有 ts，无法溯源")
    text = str(record.get("principle") or record.get("correction") or "").strip()
    ts = now or datetime.now(timezone.utc)
    prov: dict[str, Any] = {
        "kind": "correction",
        "ref": ref,
        "ts": str(record.get("ts") or ""),
        "text": text[:500],
        "registered_at": ts.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }
    if user:
        prov["user"] = str(user)
    return prov


def find_correction(records: list[dict[str, Any]], ref: str) -> dict[str, Any] | None:
    """按 id 或 ts 精确匹配一条纠偏记录（先 id 再 ts）。"""
    key = str(ref or "").strip()
    if not key:
        return None
    for rec in records:
        if str(rec.get("id") or "") == key:
            return rec
    for rec in records:
        if str(rec.get("ts") or "") == key:
            return rec
    return None


def build_rule_doc(
    *,
    rule_id: str,
    title: str,
    entity_type: str,
    predicates: list[dict[str, Any]],
    success: dict[str, Any],
    horizons: list[int] | None = None,
    metrics: list[str] | None = None,
    min_n: int = DEFAULT_MIN_N,
    version: int = 1,
    notes: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Rule]:
    """组装规则文档并校验；不合法抛 RuleValidationError（带字段路径）。返回 (文档, 解析后的 Rule)。

    universe 取该实体类型白名单里的第一个（每类目前只有一个：sector=published_snapshot /
    theme=heat_final / stock=limit_high_union）。
    """
    if entity_type not in UNIVERSES:
        raise RuleValidationError(
            [RuleError("scope.entity_type", f"必须在 {SCOPE_ENTITY_TYPES}，得到 {entity_type!r}")]
        )
    universe = UNIVERSES[entity_type][0]
    hs = sorted({int(h) for h in (horizons or [3, 5, 7, 10])})
    if int(success.get("horizon", 0)) not in hs:
        hs = sorted({*hs, int(success["horizon"])})
    doc: dict[str, Any] = {
        "rule_id": rule_id,
        "version": int(version),
        "title": title,
        "scope": {"entity_type": entity_type, "universe": universe},
        "condition": {"all": list(predicates)},
        "outcome": {
            "target": "pct_chg",
            "horizons": hs,
            "metrics": list(metrics or METRICS),
            "success": dict(success),
        },
        "baseline": {"kind": "same_universe_all_days"},
        "min_n": int(min_n),
    }
    if notes:
        doc["notes"] = str(notes)
    if provenance:
        doc["provenance"] = dict(provenance)
    rule = parse_rule(doc, source=f"propose:{rule_id}")
    return doc, rule


def write_rule_file(rules_dir: str | Path, doc: dict[str, Any]) -> Path:
    """落 ``<rules_dir>/<rule_id>.v<version>.json``；已存在则拒绝（规则文件是版本化真本源，不覆盖）。"""
    folder = Path(rules_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{doc['rule_id']}.v{doc['version']}.json"
    if path.exists():
        raise FileExistsError(f"{path} 已存在：改口径请升 version，不要覆盖旧版本")
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
