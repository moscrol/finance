"""Deterministic checks on typed, already-delivered D4 data, not a prose judge.

The existing owned-results compiler validates row identity and canonical rule
qualification. This adapter neither parses evidence prose nor reads private
receipts, files, databases or models. Its output grants no publication authority.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.owned_results import compile_owned_results
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import ToolObservation


def _digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def _direction(value: int | float | None) -> str:
    if value is None:
        return "unknown"
    return "up" if value > 0 else "down" if value < 0 else "flat"


def _percent(numerator: int, denominator: int) -> str | None:
    if denominator == 0:
        return None
    return str((Decimal(numerator) * 100 / Decimal(denominator)).quantize(Decimal("0.0001")))


def _group_summary(group: dict) -> dict:
    summary = {key: group[key] for key in ("theme_name", "total_rows", "preview_rows", "omitted_rows")}
    counts = group.get("full_group_counts")
    if counts is None:
        return {**summary, "full_counts_available": False}
    total = group["total_rows"]
    low = counts["price_up"]
    high = low + counts["price_unknown"]
    majority = "unknown" if not total else "yes" if low * 2 > total else "no" if high * 2 <= total else "unknown"
    return {
        **summary, "full_counts_available": True, "counts": dict(counts),
        "count_unit": "theme_sector_records", "distinct_sectors_equal_records": counts["distinct_sector_codes"] == total,
        "price_up_count_bounds": [low, high], "price_up_majority_of_records": majority,
        "price_up_share_pct_bounds": [_percent(low, total), _percent(high, total)],
        "double_red_share_pct_bounds": [_percent(counts["double_red"], total),
                                         _percent(counts["double_red"] + counts["double_red_unknown"], total)],
        "double_red_unknown_count": counts["double_red_unknown"],
    }


def compile_numeric_checks(packet: dict) -> dict:
    cutoff = date.fromisoformat(packet["information_cutoff"])
    seen = set()
    checks, unsupported = [], []
    for record in packet["observations"]:
        ref = record["id"]
        if not isinstance(ref, str) or not ref or ref in seen:
            raise ValueError("observation references must be unique nonempty strings")
        seen.add(ref)
        public = record["result"]
        if {"telemetry", "trace"} & public.keys():
            raise ValueError("numeric checks accept only public observations")
        if (record["tool"] != "mainline_context" or public.get("tool") != "mainline_context"
                or public.get("ok") is not True or public.get("status") != "success"):
            unsupported.append({"observation_ref": ref, "reason": "no_supported_typed_numeric_contract"})
            continue
        basis = public.get("query_basis", {})
        if basis.get("schema") != "d4_mainline_snapshot_v1":
            unsupported.append({"observation_ref": ref, "reason": "unrecognized_mainline_contract"})
            continue
        if date.fromisoformat(basis["requested_as_of"]) > cutoff:
            raise ValueError("typed observation exceeds the frozen packet cutoff")
        evidence = tuple(AgentEvidence(**{**row, "supports": tuple(row.get("supports", ())),
                                          "contradicts": tuple(row.get("contradicts", ()))})
                         for row in public.get("evidence", []))
        observation = ToolObservation(
            tool="mainline_context", query=public.get("query", ""), evidence=evidence,
            observation=public.get("observation", ""),
            trace=ProviderTrace(provider="frozen:public", capability="mainline_context", status="success"),
            evidence_hashes=tuple(public.get("evidence_hashes", [])),
            dataset=public.get("dataset", "unknown"), query_basis=basis,
        )
        catalogue = compile_owned_results(observation, None)
        if not catalogue.blocks:
            unsupported.append({"observation_ref": ref, "reason": "no_validated_source_cards"})
            continue
        blocks = {block.key: block for block in catalogue.blocks if block.role == "strict_double_red"}
        cards = {tuple(json.loads(card.independent_key)): card for card in evidence}
        rows = []
        for row in basis["price_volume_signals"]:
            key = (row["trade_date"], row["theme_code"], row["sector_ts_code"])
            if key not in blocks:
                continue
            rows.append({
                "key": list(key), "theme_name": row["theme_name"],
                "title": cards[key].title, "evidence_hash": cards[key].content_hash,
                "price_change_pct": row["sector_pct"], "turnover_change_pct": row["diff_ratio"],
                "turnover_yi": row["sector_amount"],
                "price_direction": _direction(row["sector_pct"]),
                "turnover_direction": _direction(row["diff_ratio"]),
                "strict_double_red": blocks[key].value,
                "qualification_text": blocks[key].text,
                "source_ref": blocks[key].result_ref,
            })
        for group in basis["groups"]:
            counts = group.get("full_group_counts")
            if counts is None:
                continue
            preview = [row for row in rows if row["theme_name"] == group["theme_name"]]
            for prefix in ("price", "turnover"):
                for direction in ("up", "down", "flat", "unknown"):
                    if sum(row[f"{prefix}_direction"] == direction for row in preview) > counts[f"{prefix}_{direction}"]:
                        raise ValueError("full counts contradict delivered preview members")
            for value, field in ((True, "double_red"), (False, "not_double_red"), (None, "double_red_unknown")):
                if sum(row["strict_double_red"] is value for row in preview) > counts[field]:
                    raise ValueError("full qualification counts contradict delivered previews")
        groups = [_group_summary(group) for group in basis["groups"]]
        checks.append({
            "observation_ref": ref, "as_of": basis["snapshot_date"],
            "source_digest": catalogue.source_digest,
            "rule": dict(catalogue.witness["definition"]["descriptor"]["metric_semantics"]),
            "rule_digest": catalogue.blocks[0].definition_digest,
            "groups": groups, "preview_qualifications": rows,
            "limits": ["计数按本表每组登记行，不跨组去重或相加成唯一股票数。",
                       "明细资格只覆盖已送达并核对身份的预览行，不是全组名单。",
                       "成交增加是独立判断；未满足严格双红不能推出成交未增加。"],
        })
    return {
        "schema": "frozen_numeric_checks_v1", "packet_canonical_sha256": _digest(packet),
        "checks": checks, "unsupported_observations": unsupported,
        "authority": "calculation_only_no_prose_certification",
        "not_checked": ["未提供结构化列的展示文字及其平均数/比较计算。",
                        "资金方向、参与者身份、因果、趋势持续性与整篇正文。"],
    }
