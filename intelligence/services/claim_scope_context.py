"""Shared, IO-free evidence mapping for frozen CLI and runtime claim review."""

from __future__ import annotations

import json
import re
from typing import Any

from intelligence.services.answer_claim_scope import FUND_FLOW_METRICS, ClaimEvidenceContext

_SECTOR_FIELDS = {"sector_code", "sector_ts_code", "sector_name"}


def _tool_requests(episode: dict[str, Any]) -> list[dict[str, Any]]:
    events = episode.get("outcome", {}).get("events", [])
    return [
        event.get("payload", {})
        for event in events
        if isinstance(event, dict) and event.get("kind") == "tool_request"
    ]


def _sector_codes(requests: list[dict[str, Any]]) -> set[str]:
    codes: set[str] = set()
    for request in requests:
        arguments = request.get("arguments") or {}
        for condition in arguments.get("filters") or []:
            if not isinstance(condition, dict):
                continue
            if condition.get("field") not in _SECTOR_FIELDS:
                continue
            value = condition.get("value")
            if isinstance(value, list):
                codes.update(str(item) for item in value)
            elif value is not None:
                codes.add(str(value))
    return codes


# 取回来的证据台账里带资金流数字（常见于新闻：「逆 38 亿主力资金净流入」），
# 也是资金方向证据。只认 finance_query 指标会把这类声明当成无证据（1347 个
# 历史 run 里 13 条如此）。注意这里只扫**取回来的证据**，不扫工具参数：
# 后者是模型自己敲的检索词，敲什么都行，不构成证据。
_LEDGER_FLOW = re.compile(r"净流入|净流出|主力净|资金净|净申购|net_inflow|moneyflow")
# 2026-09-23 第二方审查（#65）压出的 fail-open：对整份台账做子串匹配，工具回包里
# 一句「本次未取得主力资金净流入数据」也会把 fund_flow_evidence 判成 True，答案里
# 的「资金集中流入」随即被放行。改为按子句判：资金流名词出现在否定 / 缺失语境的
# 子句里不算证据；同一批证据里另有肯定子句（带数字的新闻句）仍算。两组子句都进
# diagnostics 供人核——L5 再验条件卡要求 ledger 为真时人读原文。
_LEDGER_CLAUSE_SPLIT = re.compile(r"[。！？!?；;，,\n]")
_LEDGER_NEGATION = re.compile(
    r"未(?:取得|取到|提供|返回|获取|获得|见|含|包含|能|有|披露|公布|覆盖)|"
    r"无(?:法|从|相关|该|此|资金流|净流入|净流出|主力)|没有|缺(?:失|少|乏)|不含|"
    r"不可得|不可用|暂无|拿不到|查不到|未能|不提供|不支持"
)


def _ledger_flow_clauses(episode: dict[str, Any]) -> tuple[list[str], list[str]]:
    """把证据台账里提到资金流的子句分成「肯定」与「否定 / 缺失」两组（各截 80 字）。"""

    evidence = episode.get("outcome", {}).get("evidence", []) or []
    positive: list[str] = []
    negated: list[str] = []
    for item in evidence:
        text = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        for clause in _LEDGER_CLAUSE_SPLIT.split(text):
            if not _LEDGER_FLOW.search(clause):
                continue
            bucket = negated if _LEDGER_NEGATION.search(clause) else positive
            bucket.append(clause.strip()[:80])
    return positive, negated


def _ledger_has_fund_flow(episode: dict[str, Any]) -> bool:
    return bool(_ledger_flow_clauses(episode)[0])


def _fund_flow_metrics(requests: list[dict[str, Any]]) -> set[str]:
    """资金方向证据 = 请求里真的要了资金流**指标**。

    不再对整份 payload 做子串匹配：kb_search 的检索词、工具描述里随便出现
    「资金流」三个字，都会把证据判成取过（同日审查探针实测）。
    """

    seen: set[str] = set()
    for request in requests:
        arguments = request.get("arguments") or {}
        for metric in arguments.get("metrics") or []:
            if str(metric) in FUND_FLOW_METRICS:
                seen.add(str(metric))
    return seen


def build_context(
    run: dict[str, Any],
    episode: dict[str, Any],
    scope_total: int | None,
    calendar_source: str | None = None,
) -> tuple[ClaimEvidenceContext, dict[str, Any]]:
    """解出证据上下文，并把「怎么解出来的」一并返回供人核。"""

    requests = _tool_requests(episode)
    evidence = episode.get("outcome", {}).get("evidence", []) or []
    dates = sorted(
        {
            str(item.get("source_date"))
            for item in evidence
            if isinstance(item, dict) and item.get("source_date")
        }
    )
    codes = _sector_codes(requests)
    flow_metrics = _fund_flow_metrics(requests)
    ledger_positive, ledger_negated = _ledger_flow_clauses(episode)
    ledger_flow = bool(ledger_positive)
    context = ClaimEvidenceContext(
        question=str(run.get("question") or ""),
        evidence_dates=tuple(dates),
        calendar_evidence=bool(calendar_source),
        compared_scope_count=len(codes) or None,
        known_scope_total=scope_total,
        fund_flow_evidence=bool(flow_metrics) or ledger_flow,
    )
    degraded: list[str] = []
    if scope_total is not None and context.compared_scope_count is None:
        degraded.append(
            "给了 --scope-total 却没从 episode 解出比较范围数（本轮只认"
            f"filters 里的 {sorted(_SECTOR_FIELDS)}）：范围规则本次没有真在跑"
        )
    diagnostics = {
        "tool_request_count": len(requests),
        "tool_names": sorted({str(r.get("name")) for r in requests if r.get("name")}),
        "sector_codes_seen": sorted(codes),
        "fund_flow_metrics_seen": sorted(flow_metrics),
        "fund_flow_in_evidence_ledger": ledger_flow,
        "fund_flow_ledger_clauses": ledger_positive[:5],
        "fund_flow_ledger_negated_clauses": ledger_negated[:5],
        "calendar_evidence_source": calendar_source
        or "未声明（finance_query 无交易日历 dataset，episode 推不出）",
        "degraded": degraded,
    }
    return context, diagnostics
