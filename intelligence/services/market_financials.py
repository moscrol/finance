"""D7 逐季财报数据块：东财免费 F10 主要财务指标（营收/归母净利/毛利率/净利率 + 同比）。

- 取数走东财免费接口 `RPT_F10_FINANCE_MAINFINADATA`，不依赖 iFinD / 问财 key；
  与 D5 估值块（valuation_estimate）同一条东财免费路线。
- 东财失败时 fallback 到 AKShare `stock_financial_abstract`（新浪财务摘要，同为累计口径），
  块内标注实际数据源；两源都失败才写缺口。
- 口径为**累计值**（中报=H1、三季报=前三季累计），同比字段 `*TZ` 为东财原始累计同比，
  是卖方读「业绩兑现节奏」的主流口径；本块不做单季还原，避免引入推算误差。
- 补的缺口：brief/D4/D5 只有当日盘面与当前估值快照，无逐季营收/净利/毛利率序列，
  遇「业绩兑现节奏/中报/财报」类问题只能定性；瑞华泰、厦钨两题因此判负。
- 意图路由 `parse_financials_intent` 为确定性正则（财报/业绩/营收/净利/毛利率类词面），
  命中且能解析到目标股才追加本块；否则行为不变。
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

FETCH_ENV_FLAG = "FINANCE_FINANCIALS_FETCH"
_F10_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
_REPORT_NAME = "RPT_F10_FINANCE_MAINFINADATA"

DEFAULT_PERIODS = 6

# 命中即触发（确定性词面）：财报 / 业绩兑现节奏 / 逐季营收利润 / 毛利率净利率类问题。
_FINANCIALS_TERMS = (
    "财报",
    "财务",
    "业绩",
    "营收",
    "营业收入",
    "净利润",
    "归母",
    "毛利率",
    "净利率",
    "兑现节奏",
    "业绩兑现",
    "逐季",
    "季度业绩",
    "基本面",
    "扭亏",
    "增收",
)


@dataclass
class QuarterFinancials:
    report_name: str  # e.g. "2026一季报"
    report_date: str  # e.g. "2026-03-31"
    revenue_yi: float | None = None  # 营业总收入（亿元，累计）
    revenue_yoy: float | None = None  # 营收同比（%，累计）
    netprofit_yi: float | None = None  # 归母净利润（亿元，累计）
    netprofit_yoy: float | None = None  # 归母净利同比（%，累计）
    gross_margin: float | None = None  # 销售毛利率（%）
    net_margin: float | None = None  # 销售净利率（%）


def fetch_enabled() -> bool:
    return os.environ.get(FETCH_ENV_FLAG, "1").strip().lower() not in {"0", "false", "off"}


def parse_financials_intent(query: str) -> bool:
    """确定性意图路由：命中财报/业绩/营收/净利/毛利率类词面即触发。"""
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return False
    return any(term in text for term in _FINANCIALS_TERMS)


def _secucode(ts_code: str) -> str | None:
    """归一到东财 F10 的 SECUCODE，如 300454.SZ / 688111.SH / 830879.BJ。"""
    raw = str(ts_code or "").strip().upper()
    m = re.match(r"^(\d{6})(?:\.(SH|SZ|BJ))?$", raw)
    if not m:
        return None
    code, suffix = m.group(1), m.group(2)
    if not suffix:
        if code.startswith(("6", "9")):
            suffix = "SH"
        elif code.startswith(("4", "8")):
            suffix = "BJ"
        else:
            suffix = "SZ"
    return f"{code}.{suffix}"


def _num(value: Any, scale: float = 1.0) -> float | None:
    if not isinstance(value, (int, float)) or value != value:  # 非数值或 NaN
        return None
    return round(float(value) / scale, 2)


def fetch_quarterly_financials(
    ts_code: str, name: str = "", periods: int = DEFAULT_PERIODS, timeout: float = 8.0
) -> list[QuarterFinancials]:
    """Best-effort 东财 F10 逐季主要财务指标；网络/字段异常时返回空列表，由上层写缺口。"""
    secucode = _secucode(ts_code)
    if secucode is None:
        return []
    params = {
        "reportName": _REPORT_NAME,
        "columns": "ALL",
        "filter": f'(SECUCODE="{secucode}")',
        "pageSize": str(max(1, int(periods))),
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "HSF10",
        "client": "PC",
    }
    url = f"{_F10_URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://emweb.securities.eastmoney.com/",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    if payload.get("code") != 0:
        return []
    rows = ((payload.get("result") or {}).get("data")) or []
    out: list[QuarterFinancials] = []
    for r in rows:
        report_date = str(r.get("REPORT_DATE") or "")[:10]
        out.append(
            QuarterFinancials(
                report_name=str(r.get("REPORT_DATE_NAME") or report_date),
                report_date=report_date,
                revenue_yi=_num(r.get("TOTALOPERATEREVE"), 1e8),
                revenue_yoy=_num(r.get("TOTALOPERATEREVETZ")),
                netprofit_yi=_num(r.get("PARENTNETPROFIT"), 1e8),
                netprofit_yoy=_num(r.get("PARENTNETPROFITTZ")),
                gross_margin=_num(r.get("XSMLL")),
                net_margin=_num(r.get("XSJLL")),
            )
        )
    return out


_ABSTRACT_INDICATORS = {
    "营业总收入": "revenue",
    "归母净利润": "netprofit",
    "毛利率": "gross_margin",
    "销售净利率": "net_margin",
    "营业总收入增长率": "revenue_yoy",
    "归属母公司净利润增长率": "netprofit_yoy",
}


def _report_name(report_date: str) -> str:
    year, md = report_date[:4], report_date[5:]
    suffix = {"03-31": "一季报", "06-30": "中报", "09-30": "三季报", "12-31": "年报"}.get(md)
    return f"{year}{suffix}" if suffix else report_date


def fetch_quarterly_financials_akshare(
    ts_code: str, name: str = "", periods: int = DEFAULT_PERIODS
) -> list[QuarterFinancials]:
    """AKShare fallback：新浪财务摘要 `stock_financial_abstract`（累计口径，与东财 F10 一致）。
    任何异常返回空列表，由上层写缺口。"""
    secucode = _secucode(ts_code)
    if secucode is None:
        return []
    try:
        import akshare as ak

        df = ak.stock_financial_abstract(symbol=secucode[:6])
    except Exception:
        return []
    if df is None or df.empty or "指标" not in df.columns:
        return []
    date_cols = sorted((c for c in df.columns if re.fullmatch(r"\d{8}", str(c))), reverse=True)
    values: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        key = _ABSTRACT_INDICATORS.get(str(row["指标"]))
        if key is None:
            continue
        for col in date_cols[: max(1, int(periods))]:
            values.setdefault(col, {}).setdefault(key, row[col])
    out: list[QuarterFinancials] = []
    for col in date_cols[: max(1, int(periods))]:
        v = values.get(col) or {}
        report_date = f"{col[:4]}-{col[4:6]}-{col[6:]}"
        q = QuarterFinancials(
            report_name=_report_name(report_date),
            report_date=report_date,
            revenue_yi=_num(v.get("revenue"), 1e8),
            revenue_yoy=_num(v.get("revenue_yoy")),
            netprofit_yi=_num(v.get("netprofit"), 1e8),
            netprofit_yoy=_num(v.get("netprofit_yoy")),
            gross_margin=_num(v.get("gross_margin")),
            net_margin=_num(v.get("net_margin")),
        )
        if any(
            x is not None
            for x in (q.revenue_yi, q.netprofit_yi, q.gross_margin, q.net_margin)
        ):
            out.append(q)
    return out


def _fmt(value: float | None, unit: str = "") -> str:
    if value is None:
        return "缺"
    return f"{value}{unit}"


def build_financials_block(
    target_name: str,
    ts_code: str,
    rows: list[QuarterFinancials],
    fetch_disabled: bool = False,
    data_source: str = "东财 F10",
) -> str:
    """生成 D7 逐季财报数据块（注入 compose）；缺数时仍返回带显式缺口的块或空串。"""
    lines = [f"## 逐季财报数据块 [D7]（{data_source} 主要财务指标，硬数据；口径=累计值）"]
    if fetch_disabled:
        lines.append(f"- ⚠财报取数已被 {FETCH_ENV_FLAG}=0 关闭：逐季营收/净利/毛利率全部为缺口，需说明数据不可得。")
        return "\n".join(lines)
    if not rows:
        lines.append("- ⚠缺逐季财报：东财 F10 与 AKShare(新浪财务摘要) 均未取到目标公司主要财务指标，业绩兑现节奏按缺口处理，不得编造。")
        return "\n".join(lines)
    lines.append(f"- 目标：{target_name}（{ts_code}），近 {len(rows)} 期累计口径（新→旧）：")
    lines.append("- | 报告期 | 营收(亿) | 营收同比% | 归母净利(亿) | 净利同比% | 销售毛利率% | 销售净利率% |")
    lines.append("- |---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"- | {r.report_name} | {_fmt(r.revenue_yi)} | {_fmt(r.revenue_yoy)} | "
            f"{_fmt(r.netprofit_yi)} | {_fmt(r.netprofit_yoy)} | "
            f"{_fmt(r.gross_margin)} | {_fmt(r.net_margin)} |"
        )
    lines.append(
        "- 口径说明：均为**累计值**（中报=上半年累计、三季报=前三季累计），同比为东财原始累计同比；"
        "本块不做单季还原，如需单季请显式声明推算。"
    )
    lines.append(
        "- 使用要求：业绩兑现节奏/拐点只引用本块逐季硬数据（营收/净利趋势、毛利率变化、同比方向）；"
        "缺失季度按缺口处理，禁止外推补齐或编造未披露数字。"
    )
    return "\n".join(lines)


def financials_block_for_target(
    ts_code: str,
    name: str = "",
    periods: int = DEFAULT_PERIODS,
    fetcher: Callable[..., list[QuarterFinancials]] | None = None,
    fallback_fetcher: Callable[..., list[QuarterFinancials]] | None = None,
) -> str:
    """给定目标股，取数并渲染 D7 块；主源（东财 F10）失败时 fallback 到 AKShare，
    块头标注实际数据源；两源都失败才写缺口。"""
    if not fetch_enabled():
        return build_financials_block(name or ts_code, ts_code, [], fetch_disabled=True)
    fetch = fetcher or fetch_quarterly_financials
    rows = fetch(ts_code, name, periods)
    source = "东财 F10"
    if not rows:
        fallback = fallback_fetcher or fetch_quarterly_financials_akshare
        rows = fallback(ts_code, name, periods)
        if rows:
            source = "AKShare·新浪财务摘要（东财 F10 不可用，已降级备源）"
    return build_financials_block(name or ts_code, ts_code, rows, data_source=source)
