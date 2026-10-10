"""Reversible public-evidence factoring, not summarization or semantic filtering.

Unlike online noise pruning, no field or unique text disappears. Common row
metadata is inherited; repeated prose is an exact concatenation of literal
segments and evidence-detail references. Decoding must reproduce canonical JSON.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

FORMAT = "factored_public_evidence_v1"
NOTES = (
    "每个result中的evidence_common字段对该result的每一条evidence记录都生效，与行内字段合并。"
    "observation_parts按顺序连接：字符串原样保留，{evidence_detail: i}引用该result中第i条evidence的detail，索引从0开始。"
    "这只是相同内容的可逆去重，不是删减事实、缩短范围或增加来源。缺口、日期、反证与原始数据仍适用。"
)
_COMMON_FIELDS = ("tool", "title", "source", "source_date", "evidence_tier", "independent_key",
                  "freshness", "io_effect", "supports", "contradicts")
_RESERVED = {"evidence_common", "observation_parts"}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _prose_parts(text: str, rows: list[dict]) -> list:
    matches = []
    seen_details = set()
    for index, row in enumerate(rows):
        detail = row.get("detail")
        if not isinstance(detail, str) or len(detail) < 80 or detail in seen_details:
            continue
        seen_details.add(detail)
        start = text.find(detail)
        while start >= 0:
            matches.append((start, -len(detail), index))
            start = text.find(detail, start + len(detail))
    parts, cursor = [], 0
    for start, negative_length, index in sorted(matches):
        if start < cursor:
            continue
        if start > cursor:
            parts.append(text[cursor:start])
        parts.append({"evidence_detail": index})
        cursor = start - negative_length
    if cursor < len(text):
        parts.append(text[cursor:])
    return parts


def factor_packet(packet: dict) -> dict:
    if {"_encoding", "_encoding_notes"} & packet.keys():
        raise ValueError("packet uses reserved encoding fields")
    out = {"_encoding": FORMAT, "_encoding_notes": NOTES, **deepcopy(packet)}
    for record in out["observations"]:
        result = record["result"]
        if (_RESERVED | {"trace", "telemetry"}) & result.keys():
            raise ValueError("public observation uses reserved or private fields")
        rows = result.get("evidence")
        if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
            continue
        common = {key: deepcopy(rows[0][key]) for key in _COMMON_FIELDS if key in rows[0]
                  and len(rows) > 1 and all(key in row and canonical(row[key]) == canonical(rows[0][key]) for row in rows)}
        prose = result.get("observation")
        if isinstance(prose, str):
            parts = _prose_parts(prose, rows)
            if any(isinstance(part, dict) for part in parts) and len(canonical(parts)) < len(canonical(prose)):
                del result["observation"]
                result["observation_parts"] = parts
        if common:
            result["evidence"] = [{key: value for key, value in row.items() if key not in common} for row in rows]
            record["result"] = {"evidence_common": common, **result}
    if canonical(restore_packet(out)) != canonical(packet):
        raise ValueError("factoring did not preserve the public packet")
    return out


def restore_packet(view: dict) -> dict:
    if view.get("_encoding") != FORMAT or view.get("_encoding_notes") != NOTES:
        raise ValueError("unknown evidence encoding")
    packet = deepcopy(view)
    del packet["_encoding"]
    del packet["_encoding_notes"]
    for record in packet["observations"]:
        result = record["result"]
        if "evidence_common" in result:
            common = result.pop("evidence_common")
            rows = result.get("evidence")
            if not isinstance(common, dict) or not isinstance(rows, list):
                raise ValueError("malformed shared evidence fields")
            if any(not isinstance(row, dict) or common.keys() & row.keys() for row in rows):
                raise ValueError("ambiguous shared evidence fields")
            result["evidence"] = [{**deepcopy(common), **row} for row in rows]
        if "observation_parts" not in result:
            continue
        if "observation" in result or not isinstance(result["observation_parts"], list):
            raise ValueError("ambiguous observation prose")
        text = []
        for part in result.pop("observation_parts"):
            if isinstance(part, str):
                text.append(part)
                continue
            if not isinstance(part, dict) or set(part) != {"evidence_detail"}:
                raise ValueError("invalid prose reference")
            index = part["evidence_detail"]
            rows = result.get("evidence", [])
            if (not isinstance(rows, list) or type(index) is not int or not 0 <= index < len(rows)
                    or not isinstance(rows[index], dict) or not isinstance(rows[index].get("detail"), str)):
                raise ValueError("prose reference does not identify a delivered detail")
            text.append(rows[index]["detail"])
        result["observation"] = "".join(text)
    return packet


def view_receipt(packet: dict, view: dict) -> dict:
    original, encoded, restored = canonical(packet).encode(), canonical(view).encode(), canonical(restore_packet(view)).encode()
    if original != restored:
        raise ValueError("evidence view changed a public value or text")
    return {
        "schema": FORMAT, "original_canonical_sha256": sha256(original).hexdigest(),
        "view_canonical_sha256": sha256(encoded).hexdigest(), "restored_canonical_sha256": sha256(restored).hexdigest(),
        "original_bytes": len(original), "view_bytes": len(encoded),
        "roundtrip_equal": True, "content_quality": "UNREVIEWED",
    }
