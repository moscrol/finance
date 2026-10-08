"""Read-only, exact-date navigation over the canonical daily-review JSON.

No HTML scraping, formula reimplementation, report generation, database writes,
or nearest-day substitution. Matrix cells remain the report's original values.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA = "daily-review/v1"
MAX_BYTES = 5 * 1024 * 1024
SUFFIX = "-daily-review.json"


def available_dates(exports: Path) -> list[str]:
    result = []
    for path in exports.glob(f"*{SUFFIX}"):
        value = path.name.removesuffix(SUFFIX)
        try:
            if date.fromisoformat(value).isoformat() == value and path.is_file() and path.resolve().parent == exports.resolve():
                result.append(value)
        except ValueError:
            continue
    return sorted(result)


def _validate(payload: Any, day: str) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA or payload.get("trade_date") != day:
        raise ValueError("日报归档版本或交易日不匹配；未用其他日期替代。")
    if not isinstance(payload.get("facts"), dict) or not isinstance(payload.get("sections"), list):
        raise ValueError("日报归档缺少 facts / sections。")
    for key in ("focus_sw_l1", "top_amount_sw_l1"):
        values = payload["facts"].get(key, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError("日报行业分组无效。")
    for key in ("double_red_count", "single_red_count", "stock_high_120d_count", "top3_industry_ratio", "top3_industry_ratio_delta_pp", "sh_deviation_pct", "volume_ratio", "advancers_ma5"):
        value = payload["facts"].get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)):
            raise ValueError("日报摘要数值无效。")
    warnings = payload.get("warnings", [])
    if not isinstance(warnings, list) or not all(isinstance(w, str) for w in warnings):
        raise ValueError("日报告警结构无效。")
    if payload.get("generated_at") is not None and not isinstance(payload["generated_at"], str):
        raise ValueError("日报生成时间无效。")
    seen = set()
    for section in payload["sections"]:
        if not isinstance(section, dict) or not isinstance(section.get("id"), str) or section["id"] in seen:
            raise ValueError("日报章节结构无效或重复。")
        seen.add(section["id"])
        if not isinstance(section.get("title"), str) or not isinstance(section.get("blocks"), list):
            raise ValueError("日报章节标题或 blocks 无效。")
        for block in section["blocks"]:
            if not isinstance(block, dict) or block.get("kind") not in {"heading", "table", "note", "text", "conclusion", "chart"}:
                raise ValueError("日报 block 类型无效。")
            if block["kind"] == "table":
                columns, rows = block.get("columns"), block.get("rows")
                if not isinstance(columns, list) or not columns or not all(isinstance(c, str) for c in columns) or not isinstance(rows, list):
                    raise ValueError("日报表格缺少列或行。")
                for row in rows:
                    if not isinstance(row, list) or len(row) != len(columns) or any(
                        not (cell is None or isinstance(cell, (str, int, float)))
                        or (isinstance(cell, float) and not math.isfinite(cell)) for cell in row
                    ):
                        raise ValueError("日报表格存在无效单元格或错位行。")
    return payload


def _matrix_dates(columns: list[str], day: date) -> list[str] | None:
    """Resolve MM-DD headers backwards from the report date, including year rollovers.

    Only date metadata is interpreted. Formatted metric strings are never parsed.
    """
    if len(columns) < 2 or not all(re.fullmatch(r"\d{2}-\d{2}", c) for c in columns[1:]):
        return None
    upper = day
    result = []
    for label in reversed(columns[1:]):
        try:
            value = date.fromisoformat(f"{upper.year}-{label}")
            if value > upper:
                value = date.fromisoformat(f"{upper.year - 1}-{label}")
        except ValueError as exc:
            raise ValueError("日报矩阵日期无效。") from exc
        if (day - value).days > 100 or (result and value >= date.fromisoformat(result[-1])):
            raise ValueError("日报矩阵日期不递增或超出近15日窗口。")
        result.append(value.isoformat())
        upper = value
    return list(reversed(result))


def _matrices(section: dict, industries: list[str], day: date) -> list[dict]:
    grouped: dict[str, dict] = {}
    heading = ""
    for block in section.get("blocks", []):
        if block["kind"] == "heading":
            heading = str(block.get("text", ""))
        elif block["kind"] == "table":
            dates = _matrix_dates(block["columns"], day)
            if dates is not None:
                industry = str(block.get("title") or heading or "未分组")
                if industry in grouped:
                    raise ValueError("日报矩阵行业重复。")
                grouped[industry] = {"industry": industry, "dates": dates, "rows": block["rows"], "status": "available" if block["rows"] else "empty"}
    return [grouped.get(name, {"industry": name, "dates": [], "rows": [], "status": "empty"})
            for name in dict.fromkeys([*industries, *grouped])]


def project_review(payload: dict, day: date) -> dict:
    """Interactive view metadata over the same sections consumed by daily_reports.py.

    The existing Workbench projection groups tables into lenses; this additional
    navigation preserves industry headings and date columns needed for selection.
    """
    _validate(payload, day.isoformat())
    facts = payload["facts"]
    sections = {section["id"]: section for section in payload["sections"]}
    industries = list(dict.fromkeys(x for key in ("focus_sw_l1", "top_amount_sw_l1")
                                   for x in facts.get(key, []) if isinstance(x, str) and x))
    matrices = {key: _matrices(sections.get(section_id, {}), industries, day)
                for key, section_id in (("double_red", "double_red_matrix"), ("stock_highs", "stock_highs"), ("limit_up", "limit_up"))}
    engines = []
    heading = ""
    for block in sections.get("industry_engines", {}).get("blocks", []):
        if block["kind"] == "heading":
            heading = str(block.get("text", ""))
        elif block["kind"] == "table":
            engines.append({"industry": str(block.get("title") or heading), "columns": block["columns"], "rows": block["rows"]})
    diagnostics = []
    if facts.get("double_red_count") == 0:
        diagnostics.append("当日双红为 0；历史矩阵中的双红不代表当日信号。原日报若写“均未映射”，不能据此判断映射失败。")
    if facts.get("stock_high_120d_count") and not any(m["rows"] for m in matrices["stock_highs"]):
        diagnostics.append(f"当日记录 {facts['stock_high_120d_count']} 只120日新高，但重点行业矩阵未提供可用映射；空矩阵不等于这些行业新高为 0。")
    if any(str(cell).startswith("-/") for matrix in matrices["double_red"] for row in matrix["rows"][:1] for cell in row[1:]):
        diagnostics.append("部分母行业单元格缺少成交占比；与成交前三行业摘要的来源字段不同，保留原值，不相互填补。")
    return {"facts": facts, "industries": industries, "matrices": matrices, "engines": engines,
            "sections": payload["sections"], "diagnostics": diagnostics,
            "warnings": [str(w) for w in payload.get("warnings", [])],
            "core_board": payload.get("core_board", [])}


def daily_review_snapshot(exports: Path, *, as_of: date, include_available_dates: bool = True) -> dict:
    day = as_of.isoformat()
    base = {"schema_version": 1, "trade_date": day, "available_dates": available_dates(exports) if include_available_dates else [],
            "knowledge_mode": "archived_report_not_as_known", "status": "missing", "report": None}
    path = exports / f"{day}{SUFFIX}"
    if not path.exists():
        return {**base, "message": "所选交易日没有结构化日报归档；未用最新日报或昨日数据替代。"}
    if path.resolve().parent != exports.resolve():
        raise ValueError("日报归档路径超出导出目录。")
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("日报归档超出大小限制。")
        payload = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid number: {value}")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("日报归档不可读或 JSON 损坏；未降级为其他交易日。") from exc
    report = project_review(payload, as_of)
    return {**base, "status": "available", "report": report,
            "provenance": {"source_path": f"market_feature_store/exports/{path.name}",
                           "generated_at": payload.get("generated_at"),
                           "sha256": hashlib.sha256(raw).hexdigest(),
                           "note": "复用原 daily JSON；指标不重算。归档可能在交易日后生成，不代表当时已知。"}}
