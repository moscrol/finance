"""Claim-level current-state fidelity and historical replay evaluation.

Automatic checks only decide questions with deterministic evidence. Semantic
classification, event ordering, and causal support stay pending until a human
approves the corresponding gold file.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


CLAIM_TYPES = {
    "number",
    "entity",
    "classification",
    "fact",
    "inference",
    "forecast",
}
VERIFICATION_STATUSES = {
    "matched",
    "mismatch",
    "missing",
    "unverifiable",
    "needs_review",
}
REVIEW_STATUSES = {
    "pass",
    "fail",
    "pending",
    "not_applicable",
    "unverifiable",
}
RECOMMENDED_THRESHOLDS = {
    "numeric_match_rate": {"operator": ">=", "value": 0.99},
    "entity_classification_accuracy": {"operator": ">=", "value": 0.95},
    "evidence_coverage_rate": {"operator": ">=", "value": 0.95},
    "cutoff_violation_rate": {"operator": "==", "value": 0.0},
    "fact_inference_confusion_rate": {"operator": "<=", "value": 0.05},
}
FIXED_PILOT_DATES = (
    "2026-03-06",
    "2026-04-23",
    "2026-06-02",
    "2026-06-11",
    "2026-06-22",
    "2026-06-23",
    "2026-06-24",
    "2026-07-01",
    "2026-07-02",
    "2026-07-03",
)

_NUMBER = re.compile(
    r"(?<![\w.])([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
    r"\s*(%|％|万亿元|亿元|万元|亿|万|元|倍|家|只|个|板)?"
)
_DATE = re.compile(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?")
_TAG = re.compile(r"<[^>]+>")
_SENTENCE = re.compile(r"(?<=[。！？!?；;\n])")
_FORECAST = re.compile(
    r"(预计|预期|将会|明日|次日|T\+\d|若.+则|应继续|目标|预测|展望)",
    re.IGNORECASE,
)
_INFERENCE = re.compile(
    r"(因此|说明|意味着|表明|判断|阶段|主线|路径|可能|或为|偏向|推断|因果)",
    re.IGNORECASE,
)
_CAUSAL = re.compile(
    r"(因为|由于|导致|驱动|带来|使得|因此|所以|受益于|源于)",
    re.IGNORECASE,
)
_ENTITY_KEYS = {
    "entity",
    "entity_name",
    "name",
    "stock_name",
    "sector_name",
    "theme_name",
    "direction",
    "direction_ranking",
    "strong_stocks",
}
_CLASSIFICATION_KEYS = {
    "classification",
    "market_stage",
    "stage",
    "生命周期阶段",
    "阶段变化",
    "证据状态",
    "验证结论",
}
_UNIT_FACTORS = {
    None: 1.0,
    "": 1.0,
    "%": 0.01,
    "％": 0.01,
    "元": 1.0,
    "万": 10_000.0,
    "万元": 10_000.0,
    "亿": 100_000_000.0,
    "亿元": 100_000_000.0,
    "万亿元": 1_000_000_000_000.0,
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.lower() in {"script", "style", "template"}:
            self.hidden_depth += 1
        elif tag.lower() in {
            "br",
            "p",
            "div",
            "li",
            "tr",
            "h1",
            "h2",
            "h3",
            "h4",
        }:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "template"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        elif tag.lower() in {
            "p",
            "div",
            "li",
            "tr",
            "h1",
            "h2",
            "h3",
            "h4",
        }:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def _html_text(raw: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(raw)
    return unescape("".join(parser.parts))


def _read_json(path: Path) -> dict[str, object]:
    body = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(body, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return body


def _write_json(path: Path, body: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _claim_id(
    report_date: str,
    report_path: str,
    location: str,
    text: str,
) -> str:
    raw = "\x1f".join((report_date, report_path, location, text)).encode()
    return "claim-" + _sha256_bytes(raw)[:16]


def _date_text(value: object) -> str | None:
    text = str(value or "").strip()
    match = _DATE.search(text)
    if not match:
        return None
    normalized = (
        match.group(0)
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )
    parts = normalized.split("-")
    if len(parts) != 3:
        return None
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def _cutoff(report_date: str) -> str:
    return f"{report_date}T23:59:59+08:00"


def _path_key(location: str) -> str:
    return location.rsplit(".", maxsplit=1)[-1].split("[", maxsplit=1)[0]


def _declared_type(value: object) -> str:
    text = str(value or "").strip().lower()
    return {
        "observation": "fact",
        "prediction": "forecast",
    }.get(text, text if text in CLAIM_TYPES else "needs_review")


def _semantic_type(text: str, location: str) -> str:
    key = _path_key(location)
    if _FORECAST.search(text):
        return "forecast"
    if _INFERENCE.search(text):
        return "inference"
    if key in _CLASSIFICATION_KEYS:
        return "classification"
    if key in _ENTITY_KEYS:
        return "entity"
    return "fact"


def _source_time(evidence: dict[str, object]) -> str | None:
    for key in (
        "source_published_at",
        "source_time",
        "known_at",
        "published_at",
    ):
        value = evidence.get(key)
        if value:
            return str(value)
    return None


def _claim(
    *,
    report_date: str,
    report_path: str,
    location: str,
    text_span: str,
    claim_type: str,
    subject: str = "",
    predicate: str = "",
    value: object = None,
    unit: str | None = None,
    source_ref: object = None,
) -> dict[str, object]:
    status = "needs_review"
    if claim_type in {"number", "entity"}:
        status = "unverifiable"
    return {
        "claim_id": _claim_id(
            report_date,
            report_path,
            location,
            text_span,
        ),
        "report_date": report_date,
        "report_path": report_path,
        "location": location,
        "text_span": text_span,
        "claim_type": claim_type,
        "subject": subject,
        "predicate": predicate or location,
        "value": value,
        "unit": unit,
        "source_ref": source_ref,
        "cutoff_timestamp": _cutoff(report_date),
        "verification_status": status,
        "verification_reason": "",
    }


def _catalog(
    body: dict[str, object],
) -> dict[str, dict[str, object]]:
    raw = body.get("evidence_catalog")
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): value
        for key, value in raw.items()
        if isinstance(value, dict)
    }


def _explicit_claims(
    body: dict[str, object],
    report_date: str,
    report_path: str,
) -> list[dict[str, object]]:
    raw_claims = body.get("claims")
    if not isinstance(raw_claims, list):
        return []
    catalog = _catalog(body)
    claims: list[dict[str, object]] = []
    for index, raw in enumerate(raw_claims):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or raw.get("text_span") or "").strip()
        if not text:
            continue
        refs = [
            catalog[str(ref)]
            for ref in raw.get("evidence_refs", [])
            if str(ref) in catalog
        ]
        source_ref: object = None
        if len(refs) == 1:
            source_ref = {**refs[0], "scope": refs[0].get("scope", "claim")}
        elif refs:
            source_ref = [
                {**ref, "scope": ref.get("scope", "claim")} for ref in refs
            ]
        claim_type = _declared_type(
            raw.get("declared_type") or raw.get("claim_type")
        )
        if claim_type == "needs_review":
            claim_type = _semantic_type(text, f"claims[{index}]")
        claims.append(
            _claim(
                report_date=report_date,
                report_path=report_path,
                location=f"claims[{index}]",
                text_span=text,
                claim_type=claim_type,
                subject=str(raw.get("subject") or raw.get("entity") or ""),
                predicate=str(raw.get("predicate") or ""),
                value=raw.get("value"),
                unit=str(raw.get("unit")) if raw.get("unit") else None,
                source_ref=source_ref,
            )
        )
    return claims


def _walk_json(
    value: object,
    location: str = "$",
) -> Iterable[tuple[str, object]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_json(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_json(item, f"{location}[{index}]")
    elif value is not None:
        yield location, value


def _text_claims(
    text: str,
    *,
    report_date: str,
    report_path: str,
    location: str,
) -> list[dict[str, object]]:
    claims: list[dict[str, object]] = []
    clean = "\n".join(
        " ".join(line.split()) for line in text.splitlines() if line.strip()
    )
    if not clean:
        return claims
    for sentence_index, sentence in enumerate(_SENTENCE.split(clean)):
        sentence = sentence.strip()
        if not sentence:
            continue
        number_source = _DATE.sub("", sentence)
        number_matches = [
            match
            for match in _NUMBER.finditer(number_source)
            if not re.match(
                r"(?:\.[A-Za-z]{2,3}|[年月日])",
                number_source[match.end():],
            )
        ]
        if number_matches:
            for number_index, match in enumerate(number_matches):
                raw_value = match.group(1).replace(",", "")
                value = float(raw_value)
                if value.is_integer():
                    value = int(value)
                claims.append(
                    _claim(
                        report_date=report_date,
                        report_path=report_path,
                        location=(
                            f"{location}.sentence[{sentence_index}]"
                            f".number[{number_index}]"
                        ),
                        text_span=sentence,
                        claim_type="number",
                        predicate=location,
                        value=value,
                        unit=match.group(2),
                    )
                )
            continue
        claims.append(
            _claim(
                report_date=report_date,
                report_path=report_path,
                location=f"{location}.sentence[{sentence_index}]",
                text_span=sentence,
                claim_type=_semantic_type(sentence, location),
                predicate=location,
            )
        )
    return claims


def _markdown_claims(
    text: str,
    *,
    report_date: str,
    report_path: str,
) -> list[dict[str, object]]:
    claims: list[dict[str, object]] = []
    prose: list[str] = []
    headers: list[str] | None = None
    for line_index, raw_line in enumerate(text.splitlines()):
        line = raw_line.strip()
        if not line.startswith("|"):
            prose.append(raw_line)
            headers = None
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if headers is None:
            headers = cells
            continue
        if len(cells) != len(headers):
            prose.append(raw_line)
            continue
        row = dict(zip(headers, cells))
        subject = next(
            (
                row[key]
                for key in (
                    "股票",
                    "公司",
                    "名称",
                    "板块",
                    "行业",
                    "题材",
                )
                if row.get(key)
            ),
            "",
        )
        for column_index, (header, cell) in enumerate(zip(headers, cells)):
            location = f"$.table[{line_index}][{column_index}]"
            numeric = re.fullmatch(
                r"([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
                r"\s*(%|％|万亿元|亿元|万元|亿|万|元|倍|家|只|个|板)?",
                cell,
            )
            if numeric:
                value = float(numeric.group(1).replace(",", ""))
                if value.is_integer():
                    value = int(value)
                claims.append(
                    _claim(
                        report_date=report_date,
                        report_path=report_path,
                        location=location,
                        text_span=f"{subject or '报告'} {header}={cell}",
                        claim_type="number",
                        subject=subject,
                        predicate=header,
                        value=value,
                        unit=numeric.group(2),
                    )
                )
            elif any(
                keyword in header
                for keyword in ("行业", "板块", "题材", "分类")
            ):
                for value in re.split(r"[、,，/]", cell):
                    value = value.strip()
                    if not value or value in {"-", "—"}:
                        continue
                    claims.append(
                        _claim(
                            report_date=report_date,
                            report_path=report_path,
                            location=location,
                            text_span=f"{subject} 归属于 {value}",
                            claim_type="classification",
                            subject=subject,
                            predicate=header,
                            value=value,
                        )
                    )
            elif header in {"股票", "公司", "名称", "代码"} and cell:
                claims.append(
                    _claim(
                        report_date=report_date,
                        report_path=report_path,
                        location=location,
                        text_span=f"{header}={cell}",
                        claim_type="entity",
                        subject=cell,
                        predicate=header,
                    )
                )
    claims.extend(
        _text_claims(
            "\n".join(prose),
            report_date=report_date,
            report_path=report_path,
            location="$",
        )
    )
    return _deduplicate_claims(claims)


def _deduplicate_claims(
    claims: list[dict[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for claim in claims:
        key = (
            claim.get("claim_type"),
            claim.get("text_span"),
            claim.get("value"),
            claim.get("unit"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(claim)
    return result


def _daily_agent_claims(
    body: dict[str, object],
    report_date: str,
    report_path: str,
) -> list[dict[str, object]]:
    decision = body.get("decision")
    if not isinstance(decision, dict):
        return []
    claims: list[dict[str, object]] = []
    for bucket, raw_items in decision.items():
        if not isinstance(raw_items, list):
            continue
        for index, item in enumerate(raw_items):
            location = f"$.decision.{bucket}[{index}]"
            if not isinstance(item, dict):
                claims.extend(
                    _text_claims(
                        str(item),
                        report_date=report_date,
                        report_path=report_path,
                        location=location,
                    )
                )
                continue
            query = str(
                item.get("query")
                or item.get("matched_theme")
                or item.get("name")
                or bucket
            )
            classification = str(item.get("classification") or bucket)
            claims.append(
                _claim(
                    report_date=report_date,
                    report_path=report_path,
                    location=f"{location}.classification",
                    text_span=f"{query} 被归类为 {classification}",
                    claim_type="classification",
                    subject=query,
                    predicate="classification",
                    value=classification,
                )
            )
            for field in (
                "confidence",
                "priority_score",
                "涨停数",
                "新高数",
                "连续出现天数",
                "priority变化",
                "当前priority",
                "当前强势股数",
            ):
                value = item.get(field)
                if isinstance(value, (int, float)) and not isinstance(
                    value,
                    bool,
                ):
                    claims.append(
                        _claim(
                            report_date=report_date,
                            report_path=report_path,
                            location=f"{location}.{field}",
                            text_span=f"{query} {field}={value}",
                            claim_type="number",
                            subject=query,
                            predicate=field,
                            value=value,
                        )
                    )
            matched_theme = item.get("matched_theme")
            if matched_theme:
                claims.append(
                    _claim(
                        report_date=report_date,
                        report_path=report_path,
                        location=f"{location}.matched_theme",
                        text_span=f"{query} 对应题材 {matched_theme}",
                        claim_type="entity",
                        subject=str(matched_theme),
                        predicate="matched_theme",
                    )
                )
            stocks = item.get("strong_stocks")
            if isinstance(stocks, list):
                for stock_index, stock in enumerate(stocks):
                    claims.append(
                        _claim(
                            report_date=report_date,
                            report_path=report_path,
                            location=(
                                f"{location}.strong_stocks[{stock_index}]"
                            ),
                            text_span=f"{stock} 被列为 {query} 强势股",
                            claim_type="entity",
                            subject=str(stock),
                            predicate=f"strong_stock_of:{query}",
                        )
                    )
            counts = item.get("structured_counts")
            if isinstance(counts, dict):
                for field, value in counts.items():
                    if isinstance(value, (int, float)) and not isinstance(
                        value,
                        bool,
                    ):
                        claims.append(
                            _claim(
                                report_date=report_date,
                                report_path=report_path,
                                location=(
                                    f"{location}.structured_counts.{field}"
                                ),
                                text_span=f"{query} {field}={value}",
                                claim_type="number",
                                subject=query,
                                predicate=str(field),
                                value=value,
                            )
                        )
            lifecycle = item.get("logic_lifecycle")
            if isinstance(lifecycle, dict):
                for field in (
                    "生命周期阶段",
                    "阶段变化",
                    "证据状态",
                    "变化原因",
                ):
                    value = lifecycle.get(field)
                    if value:
                        claims.extend(
                            _text_claims(
                                str(value),
                                report_date=report_date,
                                report_path=report_path,
                                location=f"{location}.logic_lifecycle.{field}",
                            )
                        )
                for field in (
                    "连续出现天数",
                    "priority变化",
                    "强势股变化",
                    "触发信号变化",
                    "当前priority",
                    "当前强势股数",
                ):
                    value = lifecycle.get(field)
                    if isinstance(value, (int, float)) and not isinstance(
                        value,
                        bool,
                    ):
                        claims.append(
                            _claim(
                                report_date=report_date,
                                report_path=report_path,
                                location=(
                                    f"{location}.logic_lifecycle.{field}"
                                ),
                                text_span=f"{query} {field}={value}",
                                claim_type="number",
                                subject=query,
                                predicate=field,
                                value=value,
                            )
                        )
            validation = item.get("market_validation")
            if isinstance(validation, dict):
                for field in ("盘面验证强度", "验证结论"):
                    value = validation.get(field)
                    if value:
                        claims.extend(
                            _text_claims(
                                str(value),
                                report_date=report_date,
                                report_path=report_path,
                                location=(
                                    f"{location}.market_validation.{field}"
                                ),
                            )
                        )
            gaps = item.get("data_gaps")
            if isinstance(gaps, list):
                for gap_index, gap in enumerate(gaps):
                    claims.extend(
                        _text_claims(
                            str(gap),
                            report_date=report_date,
                            report_path=report_path,
                            location=f"{location}.data_gaps[{gap_index}]",
                        )
                    )
    return _deduplicate_claims(claims)


def extract_claims(
    report_path: str | Path,
    *,
    report_date: str,
    repo_root: str | Path,
) -> list[dict[str, object]]:
    """Extract deterministic candidate claims without adjudicating them."""
    root = Path(repo_root).expanduser().resolve()
    path = (root / report_path).resolve()
    relative = str(path.relative_to(root))
    if not path.is_file():
        return []
    if path.suffix.lower() == ".json":
        body = _read_json(path)
        explicit = _explicit_claims(body, report_date, relative)
        if explicit:
            return explicit
        daily_agent = _daily_agent_claims(body, report_date, relative)
        if daily_agent:
            return daily_agent
        claims: list[dict[str, object]] = []
        for location, value in _walk_json(body):
            if isinstance(value, bool):
                claims.append(
                    _claim(
                        report_date=report_date,
                        report_path=relative,
                        location=location,
                        text_span=f"{location}={value}",
                        claim_type="fact",
                        predicate=location,
                        value=value,
                    )
                )
            elif isinstance(value, (int, float)):
                claims.append(
                    _claim(
                        report_date=report_date,
                        report_path=relative,
                        location=location,
                        text_span=f"{location}={value}",
                        claim_type="number",
                        predicate=location,
                        value=value,
                    )
                )
            elif isinstance(value, str):
                claims.extend(
                    _text_claims(
                        value,
                        report_date=report_date,
                        report_path=relative,
                        location=location,
                    )
                )
        return _deduplicate_claims(claims)
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = _html_text(raw) if path.suffix.lower() == ".html" else raw
    if path.suffix.lower() in {".md", ".markdown"}:
        return _markdown_claims(
            text,
            report_date=report_date,
            report_path=relative,
        )
    return _deduplicate_claims(
        _text_claims(
            text,
            report_date=report_date,
            report_path=relative,
            location="$",
        )
    )


def normalize_number(value: object, unit: str | None) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric claim")
    numeric = float(str(value).replace(",", "").strip())
    if unit not in _UNIT_FACTORS:
        raise ValueError(f"unsupported unit: {unit}")
    return numeric * _UNIT_FACTORS[unit]


def numbers_match(
    report_value: object,
    report_unit: str | None,
    source_value: object,
    source_unit: str | None,
    *,
    relative_tolerance: float = 1e-6,
    absolute_tolerance: float = 1e-6,
    rounding_decimals: int | None = None,
) -> bool:
    left = normalize_number(report_value, report_unit)
    right = normalize_number(source_value, source_unit)
    if math.isnan(left) or math.isnan(right):
        return False
    if rounding_decimals is not None:
        left = round(left, rounding_decimals)
        right = round(right, rounding_decimals)
    return math.isclose(
        left,
        right,
        rel_tol=relative_tolerance,
        abs_tol=absolute_tolerance,
    )


def _snapshot_rows(
    snapshot: dict[str, object],
    table: str,
) -> list[dict[str, object]]:
    tables = snapshot.get("tables")
    if not isinstance(tables, dict):
        return []
    table_body = tables.get(table)
    if not isinstance(table_body, dict):
        return []
    rows = table_body.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _entity_matches(row: dict[str, object], entity: str) -> bool:
    if not entity or entity.lower() == "market":
        return True
    code = entity.split(".", maxsplit=1)[0]
    for key in ("stock_ts_code", "ts_code", "sector_ts_code", "code"):
        actual = str(row.get(key) or "")
        if actual and (
            actual == entity
            or actual.split(".", maxsplit=1)[0] == code
        ):
            return True
    return any(
        str(row.get(key) or "") == entity
        for key in (
            "stock_name",
            "sector_name",
            "theme_name",
            "entity_name",
            "name",
        )
    )


def _find_snapshot_value(
    snapshot: dict[str, object],
    evidence: dict[str, object],
) -> tuple[str, object, str]:
    table = str(evidence.get("source") or evidence.get("table") or "")
    field = str(evidence.get("field") or "")
    entity = str(evidence.get("entity") or "")
    source_date = str(
        evidence.get("valid_time")
        or evidence.get("source_time")
        or evidence.get("trade_date")
        or ""
    )[:10]
    if not table or not field or not source_date:
        return "unverifiable", None, "evidence 缺 table/field/valid_time"
    rows = [
        row
        for row in _snapshot_rows(snapshot, table)
        if str(row.get("trade_date") or row.get("valid_time") or "")[:10]
        == source_date
        and _entity_matches(row, entity)
    ]
    if len(rows) != 1:
        return "unverifiable", None, f"冻结快照源行数量={len(rows)}"
    if field not in rows[0]:
        return "unverifiable", None, f"冻结快照缺字段 {field}"
    return "matched", rows[0][field], ""


def _single_source_ref(claim: dict[str, object]) -> dict[str, object] | None:
    source_ref = claim.get("source_ref")
    if isinstance(source_ref, dict):
        return source_ref
    return None


def verify_claim(
    claim: dict[str, object],
    *,
    snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    result = dict(claim)
    source_ref = _single_source_ref(claim)
    claim_type = str(claim.get("claim_type") or "")
    if source_ref is None:
        result["verification_status"] = (
            "unverifiable"
            if claim_type in {"number", "entity"}
            else "needs_review"
        )
        result["verification_reason"] = "缺少逐声明 source_ref"
        return result
    if source_ref.get("scope") != "claim":
        result["verification_status"] = "missing"
        result["verification_reason"] = "报告级引用不能替代逐声明证据"
        return result
    source_time = _source_time(source_ref)
    cutoff = str(claim.get("cutoff_timestamp") or "")
    if not source_time:
        result["verification_status"] = "unverifiable"
        result["verification_reason"] = "证据缺 source_published_at/source_time"
        return result
    if cutoff and source_time > cutoff:
        result["verification_status"] = "mismatch"
        result["verification_reason"] = "证据发布时间越过 cutoff"
        result["cutoff_violation"] = True
        return result
    result["cutoff_violation"] = False
    if claim_type != "number":
        result["verification_status"] = "needs_review"
        result["verification_reason"] = "语义声明需人工金标准"
        return result
    if snapshot is None:
        result["verification_status"] = "unverifiable"
        result["verification_reason"] = "缺冻结 as_known_at 快照"
        return result
    status, actual, reason = _find_snapshot_value(snapshot, source_ref)
    if status != "matched":
        result["verification_status"] = status
        result["verification_reason"] = reason
        return result
    try:
        matched = numbers_match(
            claim.get("value"),
            str(claim.get("unit")) if claim.get("unit") else None,
            actual,
            str(source_ref.get("source_unit"))
            if source_ref.get("source_unit")
            else None,
            relative_tolerance=float(
                source_ref.get("relative_tolerance") or 1e-6
            ),
            absolute_tolerance=float(
                source_ref.get("absolute_tolerance") or 1e-6
            ),
            rounding_decimals=(
                int(source_ref["rounding_decimals"])
                if source_ref.get("rounding_decimals") is not None
                else None
            ),
        )
    except (TypeError, ValueError) as exc:
        result["verification_status"] = "unverifiable"
        result["verification_reason"] = str(exc)
        return result
    result["actual_value"] = actual
    result["verification_status"] = "matched" if matched else "mismatch"
    result["verification_reason"] = "" if matched else "报告数字与冻结快照不一致"
    return result


def verify_entity_version(
    *,
    subject: str,
    classification: str,
    report_date: str,
    history: list[dict[str, object]],
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    subject_code = subject.split(".", maxsplit=1)[0]
    for record in history:
        valid_from = str(record.get("valid_from") or "")
        valid_to = str(record.get("valid_to") or "9999-12-31")
        if not valid_from or not (valid_from <= report_date <= valid_to):
            continue
        aliases = record.get("aliases")
        names = {str(record.get("name") or "")}
        if isinstance(aliases, list):
            names.update(
                str(alias) for alias in aliases if isinstance(alias, str)
            )
        code = str(record.get("code") or "").split(".", maxsplit=1)[0]
        if subject in names or (subject_code and subject_code == code):
            candidates.append(record)
    if not candidates:
        return {
            "status": "unverifiable",
            "reason": "缺当日有效的实体/成分版本，不能使用当前版本反推",
        }
    if len(candidates) > 1:
        return {"status": "needs_review", "reason": "同名实体在当日版本中不唯一"}
    expected = str(candidates[0].get("classification") or "")
    if not expected:
        return {"status": "unverifiable", "reason": "历史版本缺分类字段"}
    return {
        "status": "matched" if expected == classification else "mismatch",
        "reason": "" if expected == classification else "历史分类不一致",
        "entity_id": candidates[0].get("entity_id"),
    }


def build_gold_candidate(
    report_date: str,
    report_sha256: str,
    claims: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": "claim-fidelity-gold-1.0",
        "report_date": report_date,
        "source_report_sha256": report_sha256,
        "gold_status": "candidate",
        "reviewer": None,
        "reviewed_at": None,
        "claims": {
            str(claim["claim_id"]): {
                "text_span": claim["text_span"],
                "expected_type": None,
                "entity_classification": "pending",
                "stage_feature": "pending",
                "timeline_event_id": None,
                "timeline_position": None,
                "causal_support": (
                    "pending"
                    if _CAUSAL.search(str(claim["text_span"]))
                    else "not_applicable"
                ),
                "notes": "",
            }
            for claim in claims
        },
        "instructions": {
            "rule": (
                "Only a human reviewer may set gold_status=approved. "
                "Evidence gaps remain pending or unverifiable."
            ),
            "review_statuses": sorted(REVIEW_STATUSES),
        },
    }


def write_gold_candidate(path: str | Path, body: dict[str, object]) -> None:
    target = Path(path).expanduser()
    if body.get("gold_status") != "candidate":
        raise ValueError("generated gold must remain candidate")
    if target.exists():
        existing = _read_json(target)
        if existing.get("gold_status") == "approved":
            raise FileExistsError("approved gold cannot be overwritten")
    _write_json(target, body)


def validate_approved_gold(gold: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if gold.get("gold_status") != "approved":
        errors.append("gold_status is not approved")
    if not gold.get("reviewer") or not gold.get("reviewed_at"):
        errors.append("approved gold requires reviewer and reviewed_at")
    claims = gold.get("claims")
    if not isinstance(claims, dict):
        errors.append("claims must be an object")
        return errors
    for claim_id, review in claims.items():
        if not isinstance(review, dict):
            errors.append(f"claims.{claim_id} must be an object")
            continue
        expected_type = review.get("expected_type")
        if expected_type is not None and expected_type not in CLAIM_TYPES:
            errors.append(f"claims.{claim_id}.expected_type is invalid")
        for field in (
            "entity_classification",
            "stage_feature",
            "causal_support",
        ):
            if review.get(field, "pending") not in REVIEW_STATUSES:
                errors.append(f"claims.{claim_id}.{field} is invalid")
    return errors


def _rate(
    numerator: int,
    denominator: int,
    pending: int = 0,
) -> dict[str, object]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "pending": pending,
        "value": round(numerator / denominator, 6) if denominator else None,
        "status": "measured" if denominator else "pending",
    }


def _accuracy(
    passed: int,
    checked: int,
    pending: int = 0,
) -> dict[str, object]:
    return {
        "passed": passed,
        "checked": checked,
        "pending": pending,
        "value": round(passed / checked, 6) if checked else None,
        "status": "measured" if checked else "pending",
    }


def score_claims(
    claims: list[dict[str, object]],
    gold: dict[str, object] | None,
) -> dict[str, object]:
    approved = gold is not None and not validate_approved_gold(gold)
    reviews = gold.get("claims") if approved and gold else {}
    if not isinstance(reviews, dict):
        reviews = {}

    numeric = [
        claim for claim in claims if claim.get("claim_type") == "number"
    ]
    numeric_checked = [
        claim
        for claim in numeric
        if claim.get("verification_status") in {"matched", "mismatch"}
        and not claim.get("cutoff_violation")
    ]
    numeric_matched = sum(
        claim.get("verification_status") == "matched"
        for claim in numeric_checked
    )
    factual = [
        claim
        for claim in claims
        if claim.get("claim_type")
        in {"number", "entity", "classification", "fact"}
    ]
    covered = sum(
        isinstance(claim.get("source_ref"), dict)
        and claim["source_ref"].get("scope") == "claim"
        for claim in factual
    )
    refs = [
        claim
        for claim in claims
        if isinstance(claim.get("source_ref"), dict)
    ]
    cutoff_checked = [
        claim for claim in refs if _source_time(claim["source_ref"])
    ]
    cutoff_violations = sum(
        bool(claim.get("cutoff_violation")) for claim in cutoff_checked
    )

    entity_passed = entity_checked = entity_pending = 0
    confusion = type_checked = type_pending = 0
    stage_passed = stage_checked = stage_pending = 0
    causal_counts = {
        "supported": 0,
        "unsupported": 0,
        "unverifiable": 0,
        "pending": 0,
    }
    timeline_pairs: list[tuple[int, int]] = []
    timeline_candidates = 0
    for claim in claims:
        review = reviews.get(str(claim.get("claim_id")))
        if not isinstance(review, dict):
            type_pending += 1
            if claim.get("claim_type") in {"entity", "classification"}:
                entity_pending += 1
            if claim.get("claim_type") in {"classification", "inference"}:
                stage_pending += 1
            if _CAUSAL.search(str(claim.get("text_span") or "")):
                causal_counts["pending"] += 1
            continue
        expected_type = review.get("expected_type")
        if expected_type in CLAIM_TYPES:
            type_checked += 1
            confusion += expected_type != claim.get("claim_type")
        else:
            type_pending += 1
        entity_status = review.get("entity_classification", "pending")
        if entity_status in {"pass", "fail"}:
            entity_checked += 1
            entity_passed += entity_status == "pass"
        elif entity_status != "not_applicable":
            entity_pending += 1
        stage_status = review.get("stage_feature", "pending")
        if stage_status in {"pass", "fail"}:
            stage_checked += 1
            stage_passed += stage_status == "pass"
        elif stage_status != "not_applicable":
            stage_pending += 1
        causal = review.get("causal_support", "pending")
        if causal == "pass":
            causal_counts["supported"] += 1
        elif causal == "fail":
            causal_counts["unsupported"] += 1
        elif causal == "unverifiable":
            causal_counts["unverifiable"] += 1
        elif causal != "not_applicable":
            causal_counts["pending"] += 1
        position = review.get("timeline_position")
        if isinstance(position, int):
            timeline_candidates += 1
            extracted_date = _date_text(claim.get("text_span"))
            if extracted_date:
                timeline_pairs.append(
                    (
                        int(extracted_date.replace("-", "")),
                        position,
                    )
                )

    ordered_pairs = len(timeline_pairs) * (len(timeline_pairs) - 1) // 2
    correct_pairs = sum(
        (left_date < right_date) == (left_position < right_position)
        for index, (left_date, left_position) in enumerate(timeline_pairs)
        for right_date, right_position in timeline_pairs[index + 1:]
        if left_date != right_date and left_position != right_position
    )
    comparable_pairs = sum(
        left_date != right_date and left_position != right_position
        for index, (left_date, left_position) in enumerate(timeline_pairs)
        for right_date, right_position in timeline_pairs[index + 1:]
    )
    timeline_precision = _rate(
        correct_pairs,
        comparable_pairs,
        timeline_candidates - len(timeline_pairs),
    )
    timeline_recall = _rate(
        len(timeline_pairs),
        timeline_candidates,
        0 if approved else len(claims),
    )
    timeline_precision["candidate_pair_count"] = ordered_pairs

    return {
        "numeric_match_rate": _accuracy(
            int(numeric_matched),
            len(numeric_checked),
            len(numeric) - len(numeric_checked),
        ),
        "entity_classification_accuracy": _accuracy(
            int(entity_passed),
            entity_checked,
            entity_pending,
        ),
        "evidence_coverage_rate": _rate(covered, len(factual)),
        "cutoff_violation_rate": _rate(
            int(cutoff_violations),
            len(cutoff_checked),
            len(refs) - len(cutoff_checked),
        ),
        "fact_inference_confusion_rate": _rate(
            int(confusion),
            type_checked,
            type_pending,
        ),
        "timeline_precision": timeline_precision,
        "timeline_recall": timeline_recall,
        "stage_feature_accuracy": _accuracy(
            int(stage_passed),
            stage_checked,
            stage_pending,
        ),
        "causal_statements": causal_counts,
        "gold_status": "approved" if approved else "pending",
    }


def audit_version_gaps(
    snapshot: dict[str, object] | None,
) -> dict[str, object]:
    requirements = {
        "valid_time": False,
        "known_at": False,
        "source_published_at": False,
        "revision_at": False,
        "price_adjustment_version": False,
        "constituent_version": False,
        "entity_history_version": False,
        "classification_rule_version": False,
        "trading_status_version": False,
    }
    if snapshot:
        for table_body in (
            snapshot.get("tables").values()
            if isinstance(snapshot.get("tables"), dict)
            else []
        ):
            if not isinstance(table_body, dict):
                continue
            rows = table_body.get("rows")
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for field in requirements:
                    requirements[field] = requirements[field] or field in row
    gaps = [
        {
            "field": field,
            "status": (
                "pending"
                if field != "source_published_at"
                else "unverifiable"
            ),
            "reason": f"snapshot does not prove {field}",
        }
        for field, available in requirements.items()
        if not available
    ]
    return {
        "requirements": requirements,
        "gaps": gaps,
        "blocking": bool(gaps),
    }


def _aggregate_metric(
    reports: list[dict[str, object]],
    metric_name: str,
) -> dict[str, object]:
    numerator = denominator = pending = 0
    for report in reports:
        metrics = report.get("metrics")
        metric = (
            metrics.get(metric_name)
            if isinstance(metrics, dict)
            else None
        )
        if not isinstance(metric, dict):
            continue
        numerator += int(
            metric.get("numerator", metric.get("passed", 0)) or 0
        )
        denominator += int(
            metric.get("denominator", metric.get("checked", 0)) or 0
        )
        pending += int(metric.get("pending") or 0)
    return _rate(numerator, denominator, pending)


def evaluate_registry(
    *,
    registry_path: str | Path,
    repo_root: str | Path,
    pit_dir: str | Path,
    out_dir: str | Path,
    gold_dir: str | Path | None = None,
) -> dict[str, object]:
    registry = _read_json(Path(registry_path).expanduser())
    entries = registry.get("reports")
    if not isinstance(entries, list):
        raise ValueError("registry.reports must be a list")
    root = Path(repo_root).expanduser().resolve()
    pit = Path(pit_dir).expanduser()
    output = Path(out_dir).expanduser()
    gold_root = Path(gold_dir).expanduser() if gold_dir else None
    reports: list[dict[str, object]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        report_date = str(entry.get("report_date") or "")
        report_path = str(entry.get("canonical_report_path") or "")
        source = root / report_path if report_path else None
        snapshot_path = pit / "as_known_at" / f"{report_date}.known.json"
        snapshot = (
            _read_json(snapshot_path) if snapshot_path.is_file() else None
        )
        if not source or not source.is_file():
            missing_candidate = build_gold_candidate(report_date, "", [])
            missing_candidate["report_status"] = "missing"
            write_gold_candidate(
                output / "gold-candidates" / f"{report_date}.gold.json",
                missing_candidate,
            )
            report_result = {
                "report_date": report_date,
                "canonical_report_path": report_path or None,
                "status": "missing",
                "claims": [],
                "metrics": score_claims([], None),
                "version_gap_audit": audit_version_gaps(snapshot),
                "decision_eligible": False,
            }
            reports.append(report_result)
            _write_json(
                output / "reports" / f"{report_date}.json",
                report_result,
            )
            continue
        raw = source.read_bytes()
        claims = extract_claims(
            report_path,
            report_date=report_date,
            repo_root=root,
        )
        verified = [
            verify_claim(claim, snapshot=snapshot) for claim in claims
        ]
        gold_path = (
            gold_root / f"{report_date}.gold.json" if gold_root else None
        )
        gold = (
            _read_json(gold_path)
            if gold_path and gold_path.is_file()
            else None
        )
        metrics = score_claims(verified, gold)
        candidate = build_gold_candidate(
            report_date,
            _sha256_bytes(raw),
            verified,
        )
        write_gold_candidate(
            output / "gold-candidates" / f"{report_date}.gold.json",
            candidate,
        )
        report_result = {
            "report_date": report_date,
            "canonical_report_path": report_path,
            "canonical_report_sha256": _sha256_bytes(raw),
            "status": "audited",
            "claim_count": len(verified),
            "claims": verified,
            "metrics": metrics,
            "version_gap_audit": audit_version_gaps(snapshot),
            "decision_eligible": False,
        }
        reports.append(report_result)
        _write_json(output / "reports" / f"{report_date}.json", report_result)

    metric_names = tuple(RECOMMENDED_THRESHOLDS)
    replay_names = (
        "timeline_precision",
        "timeline_recall",
        "stage_feature_accuracy",
    )
    summary = {
        "schema_version": "claim-fidelity-pilot-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dates": [report.get("report_date") for report in reports],
        "report_status_counts": {
            status: sum(report.get("status") == status for report in reports)
            for status in ("audited", "missing")
        },
        "metrics": {
            name: _aggregate_metric(reports, name) for name in metric_names
        },
        "historical_replay": {
            name: _aggregate_metric(reports, name) for name in replay_names
        },
        "recommended_thresholds": RECOMMENDED_THRESHOLDS,
        "blocking_version_gap_dates": [
            report["report_date"]
            for report in reports
            if isinstance(report.get("version_gap_audit"), dict)
            and report["version_gap_audit"].get("blocking")
        ],
        "decision_eligible": False,
        "phase_2_allowed": False,
        "reports": reports,
    }
    _write_json(output / "summary.json", summary)
    return summary


def assert_stable_signature(
    before: dict[str, int],
    after: dict[str, int],
) -> None:
    if before != after:
        raise RuntimeError("source database changed during claim evaluation")
