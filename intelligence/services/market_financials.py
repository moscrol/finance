"""D7 逐季财报数据块：东财免费 F10 主要财务指标（营收/归母净利/毛利率/净利率 + 同比）。

- 取数走东财免费接口 `RPT_F10_FINANCE_MAINFINADATA`，不依赖 iFinD / 问财 key；
  与 D5 估值块（valuation_estimate）同一条东财免费路线。
- Provider 链：东财 F10 → 新浪利润表（a-stock-data 自包含 HTTP，不依赖 akshare）
  → AKShare `stock_financial_abstract`。任一成功即返回，引用行标实际 provider + 取数日。
- 全败输出结构化状态（ok / degraded / missing_config / NO_DATA），不落「查询失败」。
  备源未安装仍单独披露「未尝试」，不得谎称两源都试过。
- 含金量科目：经营现金流 / 合同负债 / 存货 / 股东户数。毛利率同比改善但经营现金流反向
  时块内自动出「利润质量待核」（只报数字与方向，不下结论）。
- 口径为**累计值**（中报=H1、三季报=前三季累计），同比字段 `*TZ` 为东财原始累计同比，
  是卖方读「业绩兑现节奏」的主流口径；本块不做单季还原，避免引入推算误差。
- 补的缺口：brief/D4/D5 只有当日盘面与当前估值快照，无逐季营收/净利/毛利率序列，
  遇「业绩兑现节奏/中报/财报」类问题只能定性；瑞华泰、厦钨两题因此判负。
- 意图路由 `parse_financials_intent` 为确定性正则（财报/业绩/营收/净利/毛利率类词面），
  命中且能解析到目标股才追加本块；否则行为不变。
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Callable, Literal

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


ProviderStatus = Literal["ok", "degraded", "missing_config", "NO_DATA"]
PRIMARY_PROVIDER = "东财 F10"
SINA_PROVIDER = "新浪利润表"
AKSHARE_PROVIDER = "AKShare·新浪财务摘要"


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
    ocf_yi: float | None = None  # 经营活动现金流量净额（亿元，累计）
    contract_liability_yi: float | None = None  # 合同负债（亿元）
    inventory_yi: float | None = None  # 存货（亿元）
    holder_num: int | None = None  # 股东户数
    holder_change_pct: float | None = None  # 股东户数环比（%）


@dataclass(frozen=True)
class FinancialsFetchResult:
    rows: tuple[QuarterFinancials, ...]
    provider: str
    status: ProviderStatus
    as_of: str
    attempted: tuple[str, ...]
    notes: tuple[str, ...] = ()


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
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("%", "").strip()
        if not cleaned or cleaned in {"--", "-", "None"}:
            return None
        try:
            value = float(cleaned)
        except ValueError:
            return None
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
    except urllib.error.HTTPError:
        raise
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
                ocf_yi=_num(r.get("NETCASH_OPERATE_PK"), 1e8),
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


def akshare_available() -> bool:
    """备源库在不在。**不 import，只查 spec**——import 会拖进 akshare 的全部依赖。

    存在的理由：``fetch_quarterly_financials_akshare`` 里 ``except Exception``
    把三件不同的事压成同一个 ``[]``：

        1. akshare 没装（ImportError）        —— 备源**从未尝试**
        2. akshare 装了但取数失败（网络等）    —— 备源尝试过、失败
        3. 取到了但没有目标字段              —— 备源尝试过、无数据

    这三件对用户的含义完全不同，而缺口文案写死了「东财与 AKShare 均未取到」。
    2026-08-10 实测：akshare 在 .venv-workbench 里从未安装，于是那句话对**每一次**
    财报缺口都成立地撒谎——声称试过两个源，实际只试了一个。

    这不是文案瑕疵。它让「备源不可用」这个基础设施事实，伪装成「这家公司查不到
    财报」这个数据事实，于是没人会去修备源——因为仪表显示它已经试过了。
    """

    return importlib.util.find_spec("akshare") is not None


def fetch_quarterly_financials_akshare(
    ts_code: str, name: str = "", periods: int = DEFAULT_PERIODS
) -> list[QuarterFinancials]:
    """AKShare fallback：新浪财务摘要 `stock_financial_abstract`（累计口径，与东财 F10 一致）。
    任何异常返回空列表，由上层写缺口；备源未安装时同样返回空列表，
    由 ``akshare_available()`` 供上层区分「未尝试」与「尝试过但失败」。"""
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


def _sina_paper_code(ts_code: str) -> str | None:
    secucode = _secucode(ts_code)
    if secucode is None:
        return None
    code, suffix = secucode.split(".")
    if suffix == "SH":
        return f"sh{code}"
    if suffix == "BJ":
        return f"bj{code}"
    return f"sz{code}"


def _first_num(row: dict[str, Any], keys: tuple[str, ...], scale: float = 1.0) -> float | None:
    for key in keys:
        value = _num(row.get(key), scale)
        if value is not None:
            return value
    return None


def _parse_sina_lrb_rows(report_list: dict[str, Any], periods: int) -> list[QuarterFinancials]:
    rows: list[QuarterFinancials] = []
    for period_key in sorted(report_list.keys(), reverse=True)[: max(1, int(periods))]:
        obj = report_list[period_key] or {}
        rec: dict[str, Any] = {}
        for item in obj.get("data", []) or []:
            title = str(item.get("item_title") or "").strip()
            if not title or item.get("item_value") is None:
                continue
            rec[title] = item.get("item_value")
            tongbi = item.get("item_tongbi")
            if tongbi not in (None, ""):
                rec[title + "_同比"] = tongbi
        report_date = f"{period_key[:4]}-{period_key[4:6]}-{period_key[6:8]}"
        q = QuarterFinancials(
            report_name=_report_name(report_date),
            report_date=report_date,
            revenue_yi=_first_num(rec, ("营业总收入", "营业收入"), 1e8),
            revenue_yoy=_first_num(rec, ("营业总收入_同比", "营业收入_同比")),
            netprofit_yi=_first_num(
                rec,
                ("归属于母公司股东的净利润", "归属于母公司所有者的净利润", "净利润"),
                1e8,
            ),
            netprofit_yoy=_first_num(
                rec,
                (
                    "归属于母公司股东的净利润_同比",
                    "归属于母公司所有者的净利润_同比",
                    "净利润_同比",
                ),
            ),
            gross_margin=_first_num(rec, ("销售毛利率", "毛利率")),
            net_margin=_first_num(rec, ("销售净利率", "净利率")),
        )
        if any(
            x is not None
            for x in (q.revenue_yi, q.netprofit_yi, q.gross_margin, q.net_margin)
        ):
            rows.append(q)
    return rows


def fetch_quarterly_financials_sina(
    ts_code: str,
    name: str = "",
    periods: int = DEFAULT_PERIODS,
    timeout: float = 8.0,
) -> list[QuarterFinancials]:
    """a-stock-data 中间源：新浪利润表 HTTP，不依赖 akshare / mootdx。"""
    del name
    paper_code = _sina_paper_code(ts_code)
    if paper_code is None:
        return []
    params = urllib.parse.urlencode(
        {
            "paperCode": paper_code,
            "source": "lrb",
            "type": "0",
            "page": "1",
            "num": str(max(1, int(periods))),
        }
    )
    url = (
        "https://quotes.sina.cn/cn/api/openapi.php/"
        f"CompanyFinanceService.getFinanceReport2022?{params}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    report_list = ((payload.get("result") or {}).get("data") or {}).get("report_list") or {}
    if not isinstance(report_list, dict):
        return []
    return _parse_sina_lrb_rows(report_list, periods)


def _invoke_provider(
    fetcher: Callable[..., list[QuarterFinancials]],
    ts_code: str,
    name: str,
    periods: int,
    timeout: float,
) -> tuple[list[QuarterFinancials], str | None]:
    try:
        try:
            rows = fetcher(ts_code, name, periods, timeout)
        except TypeError:
            rows = fetcher(ts_code, name, periods)
        return list(rows or []), None
    except urllib.error.HTTPError as exc:
        return [], f"HTTP {exc.code}"
    except Exception as exc:
        return [], type(exc).__name__


def fetch_quarterly_financials_chain(
    ts_code: str,
    name: str = "",
    periods: int = DEFAULT_PERIODS,
    timeout: float = 8.0,
    *,
    today: str | None = None,
    primary: Callable[..., list[QuarterFinancials]] | None = None,
    secondary: Callable[..., list[QuarterFinancials]] | None = None,
    tertiary: Callable[..., list[QuarterFinancials]] | None = None,
    tertiary_available: bool | None = None,
) -> FinancialsFetchResult:
    """东财 F10 → 新浪利润表 → AKShare。状态分列，不混成 failed。"""
    as_of = today or date.today().isoformat()
    attempted: list[str] = []
    notes: list[str] = []
    steps: list[tuple[str, Callable[..., list[QuarterFinancials]]]] = [
        (PRIMARY_PROVIDER, primary or fetch_quarterly_financials),
        (SINA_PROVIDER, secondary or fetch_quarterly_financials_sina),
    ]
    for index, (label, fetcher) in enumerate(steps):
        attempted.append(label)
        rows, error = _invoke_provider(fetcher, ts_code, name, periods, timeout)
        if error:
            notes.append(f"{label} {error}")
        if rows:
            status: ProviderStatus = "ok" if index == 0 else "degraded"
            return FinancialsFetchResult(
                rows=tuple(rows),
                provider=label,
                status=status,
                as_of=as_of,
                attempted=tuple(attempted),
                notes=tuple(notes),
            )

    akshare_on = akshare_available() if tertiary_available is None else tertiary_available
    if not akshare_on:
        notes.append(f"{AKSHARE_PROVIDER} 未安装，本次未尝试")
        return FinancialsFetchResult(
            rows=(),
            provider="",
            status="missing_config",
            as_of=as_of,
            attempted=tuple(attempted),
            notes=tuple(notes),
        )

    attempted.append(AKSHARE_PROVIDER)
    rows, error = _invoke_provider(
        tertiary or fetch_quarterly_financials_akshare,
        ts_code,
        name,
        periods,
        timeout,
    )
    if error:
        notes.append(f"{AKSHARE_PROVIDER} {error}")
    if rows:
        return FinancialsFetchResult(
            rows=tuple(rows),
            provider=AKSHARE_PROVIDER,
            status="degraded",
            as_of=as_of,
            attempted=tuple(attempted),
            notes=tuple(notes),
        )
    return FinancialsFetchResult(
        rows=(),
        provider="",
        status="NO_DATA",
        as_of=as_of,
        attempted=tuple(attempted),
        notes=tuple(notes),
    )


def _sina_period_items(report_list: dict[str, Any], periods: int) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for period_key in sorted(report_list.keys(), reverse=True)[: max(1, int(periods))]:
        rec: dict[str, Any] = {}
        obj = report_list[period_key] or {}
        for item in obj.get("data", []) or []:
            title = str(item.get("item_title") or "").strip()
            if not title or item.get("item_value") is None:
                continue
            rec[title] = item.get("item_value")
            tongbi = item.get("item_tongbi")
            if tongbi not in (None, ""):
                rec[title + "_同比"] = tongbi
        out[f"{period_key[:4]}-{period_key[4:6]}-{period_key[6:8]}"] = rec
    return out


def _fetch_sina_report_list(
    ts_code: str,
    source: str,
    periods: int,
    timeout: float,
) -> dict[str, Any]:
    paper_code = _sina_paper_code(ts_code)
    if paper_code is None:
        return {}
    params = urllib.parse.urlencode(
        {
            "paperCode": paper_code,
            "source": source,
            "type": "0",
            "page": "1",
            "num": str(max(1, int(periods))),
        }
    )
    url = (
        "https://quotes.sina.cn/cn/api/openapi.php/"
        f"CompanyFinanceService.getFinanceReport2022?{params}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}
    report_list = ((payload.get("result") or {}).get("data") or {}).get("report_list") or {}
    return report_list if isinstance(report_list, dict) else {}


def fetch_sina_llb_map(
    ts_code: str, periods: int = DEFAULT_PERIODS, timeout: float = 8.0
) -> dict[str, dict[str, float]]:
    items = _sina_period_items(_fetch_sina_report_list(ts_code, "llb", periods, timeout), periods)
    out: dict[str, dict[str, float]] = {}
    for report_date, rec in items.items():
        ocf = _first_num(rec, ("经营活动产生的现金流量净额",), 1e8)
        if ocf is not None:
            out[report_date] = {"ocf_yi": ocf}
    return out


def fetch_sina_fzb_map(
    ts_code: str, periods: int = DEFAULT_PERIODS, timeout: float = 8.0
) -> dict[str, dict[str, float]]:
    items = _sina_period_items(_fetch_sina_report_list(ts_code, "fzb", periods, timeout), periods)
    out: dict[str, dict[str, float]] = {}
    for report_date, rec in items.items():
        mapped: dict[str, float] = {}
        contract = _first_num(rec, ("合同负债",), 1e8)
        inventory = _first_num(rec, ("存货", "存货合计"), 1e8)
        if contract is not None:
            mapped["contract_liability_yi"] = contract
        if inventory is not None:
            mapped["inventory_yi"] = inventory
        if mapped:
            out[report_date] = mapped
    return out


def fetch_holder_map(ts_code: str, timeout: float = 8.0) -> dict[str, tuple[int, float | None]]:
    secucode = _secucode(ts_code)
    if secucode is None:
        return {}
    code = secucode.split(".")[0]
    params = urllib.parse.urlencode(
        {
            "reportName": "RPT_HOLDERNUMLATEST",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageNumber": "1",
            "pageSize": "12",
            "sortColumns": "END_DATE",
            "sortTypes": "-1",
            "source": "WEB",
            "client": "WEB",
        }
    )
    url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}
    rows = ((payload.get("result") or {}).get("data")) or []
    out: dict[str, tuple[int, float | None]] = {}
    for row in rows:
        report_date = str(row.get("END_DATE") or "")[:10]
        raw_num = row.get("HOLDER_NUM")
        if not report_date or not isinstance(raw_num, (int, float)):
            continue
        out[report_date] = (int(raw_num), _num(row.get("HOLDER_NUM_RATIO")))
    return out


def enrich_quality_fields(
    ts_code: str,
    rows: list[QuarterFinancials],
    *,
    llb: dict[str, dict[str, float]] | None = None,
    fzb: dict[str, dict[str, float]] | None = None,
    holders: dict[str, tuple[int, float | None]] | None = None,
    timeout: float = 8.0,
    fetch_missing: bool = False,
    periods: int = DEFAULT_PERIODS,
) -> list[QuarterFinancials]:
    """把经营现金流/合同负债/存货/股东户数补进已有逐季行；缺源保持缺口，不编造。"""
    if not rows:
        return rows
    if fetch_missing:
        if llb is None and any(row.ocf_yi is None for row in rows):
            llb = fetch_sina_llb_map(ts_code, periods=periods, timeout=timeout)
        if fzb is None and any(
            row.contract_liability_yi is None or row.inventory_yi is None for row in rows
        ):
            fzb = fetch_sina_fzb_map(ts_code, periods=periods, timeout=timeout)
        if holders is None and any(row.holder_num is None for row in rows):
            holders = fetch_holder_map(ts_code, timeout=timeout)
    llb = llb or {}
    fzb = fzb or {}
    holders = holders or {}
    enriched: list[QuarterFinancials] = []
    for row in rows:
        cash = llb.get(row.report_date) or {}
        balance = fzb.get(row.report_date) or {}
        holder = holders.get(row.report_date)
        enriched.append(
            replace(
                row,
                ocf_yi=row.ocf_yi if row.ocf_yi is not None else cash.get("ocf_yi"),
                contract_liability_yi=(
                    row.contract_liability_yi
                    if row.contract_liability_yi is not None
                    else balance.get("contract_liability_yi")
                ),
                inventory_yi=(
                    row.inventory_yi if row.inventory_yi is not None else balance.get("inventory_yi")
                ),
                holder_num=row.holder_num if row.holder_num is not None else (holder[0] if holder else None),
                holder_change_pct=(
                    row.holder_change_pct
                    if row.holder_change_pct is not None
                    else (holder[1] if holder else None)
                ),
            )
        )
    return enriched


def _yoy_peer(
    rows: list[QuarterFinancials], current: QuarterFinancials
) -> QuarterFinancials | None:
    if len(current.report_date) < 10:
        return None
    peer_date = f"{int(current.report_date[:4]) - 1}-{current.report_date[5:10]}"
    for row in rows:
        if row.report_date[:10] == peer_date:
            return row
    return None


def profit_quality_watch(rows: list[QuarterFinancials]) -> str | None:
    """毛利率同比改善但经营现金流反向 → 待核行。只报数字与方向，不下结论。"""
    if not rows:
        return None
    latest = rows[0]
    peer = _yoy_peer(rows, latest)
    if peer is None:
        return None
    if latest.gross_margin is None or peer.gross_margin is None:
        return None
    if latest.ocf_yi is None or peer.ocf_yi is None:
        return None
    if latest.gross_margin <= peer.gross_margin or latest.ocf_yi >= peer.ocf_yi:
        return None
    return (
        f"- 利润质量待核：销售毛利率 {peer.gross_margin}%→{latest.gross_margin}%（改善）"
        f"但经营现金流 {peer.ocf_yi}亿→{latest.ocf_yi}亿（反向）；不下结论。"
    )


def _fmt(value: float | None, unit: str = "") -> str:
    if value is None:
        return "缺"
    return f"{value}{unit}"


def _gap_from_result(result: FinancialsFetchResult) -> str:
    attempted = " / ".join(result.attempted) or "无"
    notes = "；".join(result.notes)
    if result.status == "missing_config":
        extra = notes or f"{AKSHARE_PROVIDER} 未安装，本次未尝试"
        return (
            f"- ⚠缺逐季财报：已尝试 {attempted}，状态=missing_config；{extra}。"
            "业绩兑现节奏按缺口处理，不得编造。"
        )
    return (
        f"- ⚠缺逐季财报：已尝试 {attempted}，状态={result.status}，"
        "业绩兑现节奏按缺口处理，不得编造。"
    )


def build_financials_block(
    target_name: str,
    ts_code: str,
    rows: list[QuarterFinancials],
    fetch_disabled: bool = False,
    data_source: str = "东财 F10",
    fallback_attempted: bool | None = None,
    fetch_result: FinancialsFetchResult | None = None,
) -> str:
    """生成 D7 逐季财报数据块（注入 compose）；缺数时仍返回带显式缺口的块或空串。

    ``fallback_attempted``：备源（AKShare）这次到底跑没跑过。``None`` = 调用方
    没说，则按 ``akshare_available()`` 现场判定。它只改缺口文案的措辞——
    把「这家公司查不到数据」与「备源不可用」分开，理由见 ``akshare_available``。
    """

    source = fetch_result.provider or data_source if fetch_result is not None else data_source
    lines = [f"## 逐季财报数据块 [D7]（{source} 主要财务指标，硬数据；口径=累计值）"]
    if fetch_disabled:
        lines.append(f"- ⚠财报取数已被 {FETCH_ENV_FLAG}=0 关闭：逐季营收/净利/毛利率全部为缺口，需说明数据不可得。")
        return "\n".join(lines)
    if not rows:
        if fetch_result is not None:
            lines.append(_gap_from_result(fetch_result))
            return "\n".join(lines)
        attempted = (
            akshare_available() if fallback_attempted is None else fallback_attempted
        )
        if attempted:
            lines.append(
                "- ⚠缺逐季财报：东财 F10 与 AKShare(新浪财务摘要) 均未取到目标公司主要财务指标，"
                "业绩兑现节奏按缺口处理，不得编造。"
            )
        else:
            # 说清「只试了一个源」，并指明这是环境缺依赖而非该公司无数据——否则
            # 备源不可用会被永久伪装成数据缺失，于是没人会去修备源。
            lines.append(
                "- ⚠缺逐季财报：东财 F10 未取到目标公司主要财务指标；"
                "**备源 AKShare 未安装，本次未尝试**（环境缺依赖，非该公司无数据）。"
                "业绩兑现节奏按缺口处理，不得编造。"
            )
        return "\n".join(lines)
    lines.append(f"- 目标：{target_name}（{ts_code}），近 {len(rows)} 期累计口径（新→旧）：")
    if fetch_result is not None:
        lines.append(f"- 引用：provider={fetch_result.provider} 取数日={fetch_result.as_of}")
    lines.append("- | 报告期 | 营收(亿) | 营收同比% | 归母净利(亿) | 净利同比% | 销售毛利率% | 销售净利率% |")
    lines.append("- |---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"- | {r.report_name} | {_fmt(r.revenue_yi)} | {_fmt(r.revenue_yoy)} | "
            f"{_fmt(r.netprofit_yi)} | {_fmt(r.netprofit_yoy)} | "
            f"{_fmt(r.gross_margin)} | {_fmt(r.net_margin)} |"
        )
    lines.append("- | 报告期 | 经营现金流(亿) | 合同负债(亿) | 存货(亿) | 股东户数 | 户数环比% |")
    lines.append("- |---|---|---|---|---|---|")
    for r in rows:
        holder = "缺" if r.holder_num is None else str(r.holder_num)
        lines.append(
            f"- | {r.report_name} | {_fmt(r.ocf_yi)} | {_fmt(r.contract_liability_yi)} | "
            f"{_fmt(r.inventory_yi)} | {holder} | {_fmt(r.holder_change_pct)} |"
        )
    watch = profit_quality_watch(rows)
    if watch:
        lines.append(watch)
    lines.append(
        "- 口径说明：均为**累计值**（中报=上半年累计、三季报=前三季累计），同比为东财原始累计同比；"
        "含金量对照只比上年同期（同报告期），不把一季报和年报横比。"
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
    timeout: float = 8.0,
    chain: Callable[..., FinancialsFetchResult] | None = None,
) -> str:
    """给定目标股，取数并渲染 D7 块。

    默认走三级链（东财 F10 → 新浪利润表 → AKShare）。显式注入
    ``fetcher`` / ``fallback_fetcher`` 时保留两级路径，以免改写既有测试语义。
    """
    if not fetch_enabled():
        return build_financials_block(name or ts_code, ts_code, [], fetch_disabled=True)
    use_default_chain = chain is None and fetcher is None and fallback_fetcher is None
    if chain is not None or use_default_chain:
        result = (chain or fetch_quarterly_financials_chain)(
            ts_code, name, periods, timeout
        )
        rows = list(result.rows)
        if use_default_chain:
            rows = enrich_quality_fields(
                ts_code, rows, timeout=timeout, fetch_missing=True, periods=periods
            )
        source = result.provider or PRIMARY_PROVIDER
        if result.status == "degraded" and result.provider:
            source = f"{result.provider}（{PRIMARY_PROVIDER} 不可用，已降级）"
        return build_financials_block(
            name or ts_code,
            ts_code,
            rows,
            data_source=source,
            fetch_result=result,
        )
    fetch = fetcher or fetch_quarterly_financials
    rows = (
        fetch(ts_code, name, periods, timeout)
        if fetcher is None
        else fetch(ts_code, name, periods)
    )
    source = "东财 F10"
    # 备源到底跑没跑过，必须如实往下传：显式注入 fallback_fetcher 时它真的跑了；
    # 未注入且 akshare 没装时，那次调用只是撞上 ImportError 被吞掉——两种情况
    # 对用户的含义不同（数据缺失 vs 环境缺依赖），不能共用一句缺口文案。
    fallback_attempted = False
    if not rows:
        fallback = fallback_fetcher or fetch_quarterly_financials_akshare
        fallback_attempted = fallback_fetcher is not None or akshare_available()
        rows = fallback(ts_code, name, periods)
        if rows:
            source = "AKShare·新浪财务摘要（东财 F10 不可用，已降级备源）"
    return build_financials_block(
        name or ts_code,
        ts_code,
        rows,
        data_source=source,
        fallback_attempted=fallback_attempted,
    )
