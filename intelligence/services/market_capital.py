"""D12 资金面三件套：两融 / 大宗 / 未来 90 天解禁时间表。

库内无两融/大宗/解禁表，取数走东财 datacenter（与 a-stock-data 同源）。
意图词命中对应切片才取数；解析不到个股不输出块。只列事实，不构成买卖建议。
"""

from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from intelligence.paths import default_market_db_path
from intelligence.services import market_news, retrieval_cache
from intelligence.services.provider_observability import ProviderStatus
from intelligence.services.research_contract import ResearchDeadline

DEFAULT_MARKET_DB_PATH = default_market_db_path()
DEFAULT_MARGIN_DAYS = 5
DEFAULT_BLOCK_ROWS = 5
UNLOCK_FORWARD_DAYS = 90
_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

_SLICE_TERMS: dict[str, tuple[str, ...]] = {
    "margin": ("两融", "融资盘", "融资融券", "融资余额", "融资买入", "融券"),
    "block": ("大宗",),
    "unlock": ("解禁", "限售解禁"),
}


@dataclass(frozen=True)
class MarginRow:
    trade_date: str
    financing_yi: float | None
    financing_buy_yi: float | None
    short_yi: float | None


@dataclass(frozen=True)
class BlockTradeRow:
    trade_date: str
    price: float | None
    premium_pct: float | None
    amount_wan: float | None
    buyer: str
    seller: str


@dataclass(frozen=True)
class UnlockRow:
    free_date: str
    share_type: str
    shares_wan: float | None
    ratio_pct: float | None


class CapitalFetchError(RuntimeError):
    """取数失败不许变成空列表：空表和无法查询是不同业务状态。"""

    def __init__(self, status: ProviderStatus, detail: str):
        super().__init__(detail)
        self.status = status


@dataclass(frozen=True)
class CapitalSliceResult:
    kind: str
    rows: tuple[MarginRow | BlockTradeRow | UnlockRow, ...] = ()
    status: ProviderStatus = "empty"
    detail: str = ""


@dataclass(frozen=True)
class CapitalBundle:
    name: str
    ts_code: str
    as_of: str
    fetched_date: str
    slices: tuple[CapitalSliceResult, ...] = ()
    diagnostic: str = ""
    reason_code: str = ""

    @property
    def row_count(self) -> int:
        return sum(len(item.rows) for item in self.slices)

    @property
    def status(self) -> ProviderStatus:
        problems = [item for item in self.slices if item.status not in {"success", "empty"}]
        if self.row_count:
            return "partial" if problems else "success"
        if problems:
            return problems[0].status
        return "empty" if self.slices else "not_attempted"

    @property
    def block(self) -> str:
        if self.diagnostic:
            return f"## 资金面三件套 [D12]\n- ⚠{self.diagnostic}"
        lines = [build_capital_block(self.name, self.ts_code, self.as_of)]
        lines.append(f"- 使用边界：抓取日 {self.fetched_date}；历史交易记录不证明在交易当时已披露，不能用于当时已知的回测。")
        for item in self.slices:
            if item.status in {"success", "empty", "partial"}:
                if item.kind == "margin":
                    lines.extend(_render_margin(list(item.rows)))
                elif item.kind == "block":
                    lines.extend(_render_block(list(item.rows)))
                else:
                    lines.extend(_render_unlock(list(item.rows), self.as_of))
            if item.detail:
                lines.append(f"- ⚠{item.kind} [{item.status}]：{item.detail}")
        return "\n".join(lines)


def parse_capital_slices(query: str) -> frozenset[str]:
    text = re.sub(r"\s+", "", str(query or ""))
    if not text:
        return frozenset()
    return frozenset(
        name for name, terms in _SLICE_TERMS.items() if any(term in text for term in terms)
    )


def parse_capital_intent(query: str) -> bool:
    return bool(parse_capital_slices(query))


_UNRESOLVED_HISTORY = re.compile(
    r"昨天|昨日|前天|前日|上(?:个|一)?(?:周|星期|月|季度|年|交易日)|去年|前年|"
    r"当时|彼时|那时|历史|回测|回看|站在|"
    r"(?:截至|截止|截止到|截至到).{0,8}(?:以前|之前)|"
    r"\d+\s*(?:天|周|月|年|个交易日)前|yesterday|last\s+(?:week|month|year)", re.I,
)


def capital_query_cutoff(query: str, *, upper_bound: str | date) -> date:
    """沿用显式日期解析器；没有可靠站立日的历史问法拒绝，不猜今天。

    「昨天」在上层可能指自然日或最近交易日，当前不另造一套日历语义；请补明确日期。
    日期只收紧：原任务和工具改写分别调用，不能用新 query 洗掉原问题的历史限定。
    """
    text = str(query or "")
    bound = upper_bound if isinstance(upper_bound, date) else date.fromisoformat(upper_bound)
    explicit = market_news.latest_explicit_query_date(text, reference_date=bound)
    relative = re.search(r"昨天|昨日|前天|前日|上(?:个|一)?(?:周|星期|月|季度|年|交易日)|去年|前年|当时|彼时|那时|yesterday|last\s+(?:week|month|year)", text, re.I)
    unresolved = _UNRESOLVED_HISTORY.search(text) or re.search(r"(?<!\d)20\d{2}(?!\d)", text)
    if relative or (explicit is None and unresolved):
        raise ValueError("历史日期边界未明确，请给出 YYYY-MM-DD 截止日；未请求当前滚动数据")
    return market_news.query_date_cutoff(text, upper_bound=bound)


def _num(value: Any, scale: float = 1.0) -> float | None:
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("%", "").strip()
        if not cleaned or cleaned in {"--", "-", "None"}:
            return None
        try:
            value = float(cleaned)
        except ValueError:
            return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return round(float(value) / scale, 2)


def _date_text(value: Any) -> str:
    text = value.isoformat()[:10] if isinstance(value, date) else str(value or "")[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise CapitalFetchError("parse_error", "源记录缺有效日期，不能当成无记录") from exc


def _fmt(value: float | None) -> str:
    if value is None:
        return "缺"
    return f"{value}"


def resolve_capital_stock(con: Any, query: str) -> tuple[str, str] | None:
    codes = re.findall(r"(?<![A-Za-z0-9])(\d{6})(?:\.(SH|SZ|BJ))?(?![A-Za-z0-9])", str(query or ""), re.I)
    if len({code for code, _suffix in codes}) > 1 or len({s.upper() for _, s in codes if s}) > 1:
        raise ValueError("每次只支持单只股票，代码或交易所冲突，请拆成分别查询")
    named_rows = con.execute(
        """
        select stock_ts_code, stock_name from fact_stock_daily
        where stock_name is not null and stock_name <> ''
        group by stock_ts_code, stock_name
        """
    ).fetchall()
    compact = re.sub(r"\s+", "", str(query or ""))
    matches = [(str(c), str(n)) for c, n in named_rows if re.sub(r"\s+", "", str(n)) in compact]
    if len({c for c, _n in matches}) > 1:
        raise ValueError("每次只支持单只股票，请把多家公司拆成分别查询")
    if codes:
        raw = codes[0][0]
        suffix = next((s for _, s in codes if s), "")
        if any(c.split('.')[0] != raw for c, _n in matches):
            raise ValueError("股票代码与名称冲突；每次只支持单只股票，请核对后分别查询")
        if suffix:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily where stock_ts_code=? limit 1",
                [f"{raw}.{suffix.upper()}"],
            ).fetchall()
        else:
            rows = con.execute(
                "select stock_ts_code, stock_name from fact_stock_daily where stock_ts_code like ? limit 1",
                [f"{raw}.%"],
            ).fetchall()
        if rows:
            return str(rows[0][0]), str(rows[0][1] or rows[0][0])
        return None
    if matches:
        matches.sort(key=lambda item: len(item[1]), reverse=True)
        return matches[0]
    return None


def _eastmoney_rows(
    report_name: str,
    filter_str: str,
    sort_columns: str,
    sort_types: str,
    page_size: int,
    timeout: float,
) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "reportName": report_name,
            "columns": "ALL",
            "filter": filter_str,
            "pageNumber": "1",
            "pageSize": str(page_size),
            "sortColumns": sort_columns,
            "sortTypes": sort_types,
            "source": "WEB",
            "client": "WEB",
        }
    )
    url = f"{_DATACENTER_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise CapitalFetchError("parse_error", "东财响应无法解析；不能判断是否有记录") from exc
    except Exception as exc:
        raise CapitalFetchError("request_error", f"东财请求失败（{type(exc).__name__}）；不能判断是否有记录") from exc
    if not isinstance(payload, dict):
        raise CapitalFetchError("parse_error", "东财响应不是对象")
    # 2026-09-18 实测：合法空窗口返回 success=false/code=9201/result=null。
    # 只认这个明确空码，其他 success=false 是故障，不凭 message 模糊猜。
    if payload.get("code") == 9201 and payload.get("result") is None:
        return []
    if payload.get("success") is not True:
        raise CapitalFetchError("request_error", "东财未确认查询成功；不能判断是否有记录")
    result = payload.get("result")
    rows = result.get("data") if isinstance(result, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise CapitalFetchError("parse_error", "东财缺 data 列表；不能判断是否有记录")
    if not rows and result.get("count") not in (None, 0):
        raise CapitalFetchError("parse_error", "东财记录数与空列表冲突")
    return rows


def fetch_margin_rows(
    code: str, limit: int = DEFAULT_MARGIN_DAYS, timeout: float = 8.0,
    *, as_of: str | None = None,
) -> list[MarginRow]:
    rows = _eastmoney_rows(
        "RPTA_WEB_RZRQ_GGMX",
        f'(SCODE="{code}")' + (f"(DATE<='{as_of}')" if as_of else ""),
        "DATE",
        "-1",
        limit,
        timeout,
    )
    out: list[MarginRow] = []
    for row in rows:
        out.append(
            MarginRow(
                trade_date=_date_text(row.get("DATE")),
                financing_yi=_num(row.get("RZYE"), 1e8),
                financing_buy_yi=_num(row.get("RZMRE"), 1e8),
                short_yi=_num(row.get("RQYE"), 1e8),
            )
        )
    return out


def fetch_block_rows(
    code: str, limit: int = DEFAULT_BLOCK_ROWS, timeout: float = 8.0,
    *, as_of: str | None = None,
) -> list[BlockTradeRow]:
    rows = _eastmoney_rows(
        "RPT_DATA_BLOCKTRADE",
        f'(SECURITY_CODE="{code}")' + (f"(TRADE_DATE<='{as_of}')" if as_of else ""),
        "TRADE_DATE",
        "-1",
        limit,
        timeout,
    )
    out: list[BlockTradeRow] = []
    for row in rows:
        close = _num(row.get("CLOSE_PRICE"))
        price = _num(row.get("DEAL_PRICE"))
        premium = None
        if close is not None and close > 0 and price is not None:
            premium = _num((price / close - 1) * 100)
        out.append(
            BlockTradeRow(
                trade_date=_date_text(row.get("TRADE_DATE")),
                price=_num(price),
                premium_pct=premium,
                amount_wan=_num(row.get("DEAL_AMT"), 1e4),
                buyer=str(row.get("BUYER_NAME") or "缺"),
                seller=str(row.get("SELLER_NAME") or "缺"),
            )
        )
    return out


def fetch_unlock_rows(
    code: str,
    as_of: str,
    forward_days: int = UNLOCK_FORWARD_DAYS,
    timeout: float = 8.0,
) -> list[UnlockRow]:
    start = date.fromisoformat(as_of)
    end = start + timedelta(days=int(forward_days))
    rows = _eastmoney_rows(
        "RPT_LIFT_STAGE",
        f"(SECURITY_CODE=\"{code}\")(FREE_DATE>='{start.isoformat()}')(FREE_DATE<='{end.isoformat()}')",
        "FREE_DATE",
        "1",
        21,  # 多取一条哨兵，不能把前 20 条说成完整日程。
        timeout,
    )
    out: list[UnlockRow] = []
    for row in rows:
        # FREE_RATIO 是比例，不是百分数；先乘 100 再四舍五入，不能 0.2123→0.21→21。
        ratio = _num(row.get("FREE_RATIO"), 0.01)
        out.append(
            UnlockRow(
                free_date=_date_text(row.get("FREE_DATE")),
                share_type=str(row.get("FREE_SHARES_TYPE") or "缺类型"),
                shares_wan=_num(row.get("CURRENT_FREE_SHARES")),
                ratio_pct=ratio,
            )
        )
    return out


def _render_margin(rows: list[MarginRow]) -> list[str]:
    lines = ["- ### 两融（东财 RPTA_WEB_RZRQ_GGMX，金额=亿元）"]
    if not rows:
        lines.append("- ⚠缺两融：东财未取到该股融资融券明细，按缺口处理，不得编造。")
        return lines
    lines.append("- | 日期 | 融资余额(亿) | 融资买入(亿) | 融券余额(亿) |")
    lines.append("- |---|---|---|---|")
    for row in rows:
        lines.append(
            f"- | {row.trade_date} | {_fmt(row.financing_yi)} | "
            f"{_fmt(row.financing_buy_yi)} | {_fmt(row.short_yi)} |"
        )
    return lines


def _render_block(rows: list[BlockTradeRow]) -> list[str]:
    lines = ["- ### 大宗交易（东财 RPT_DATA_BLOCKTRADE，成交额=万元）"]
    if not rows:
        lines.append("- ⚠缺大宗：东财未取到该股大宗记录，按缺口处理，不得编造。")
        return lines
    lines.append("- | 日期 | 成交价 | 溢价% | 成交额(万) | 买方 | 卖方 |")
    lines.append("- |---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            f"- | {row.trade_date} | {_fmt(row.price)} | {_fmt(row.premium_pct)} | "
            f"{_fmt(row.amount_wan)} | {row.buyer} | {row.seller} |"
        )
    return lines


def _render_unlock(rows: list[UnlockRow], as_of: str) -> list[str]:
    lines = [
        f"- ### 解禁时间表（东财 RPT_LIFT_STAGE，自 {as_of} 起未来 {UNLOCK_FORWARD_DAYS} 天）"
    ]
    if not rows:
        lines.append(f"- 本次查询未返回解禁记录（自 {as_of} 起 {UNLOCK_FORWARD_DAYS} 天）；仅代表该来源本次返回，不能据此断言公司没有解禁。")
        return lines
    lines.append("- | 解禁日 | 类型 | 解禁量(万股) | 占比% |")
    lines.append("- |---|---|---|---|")
    for row in rows:
        lines.append(
            f"- | {row.free_date} | {row.share_type} | {_fmt(row.shares_wan)} | {_fmt(row.ratio_pct)} |"
        )
    return lines


def build_capital_block(
    target_name: str,
    ts_code: str,
    as_of: str,
    *,
    margin_rows: list[MarginRow] | None = None,
    block_rows: list[BlockTradeRow] | None = None,
    unlock_rows: list[UnlockRow] | None = None,
) -> str:
    lines = [f"## 资金面三件套 [D12]（{target_name} {ts_code}）"]
    lines.append(
        "- 口径：东财 datacenter 免费接口（两融 RPTA_WEB_RZRQ_GGMX / 大宗 RPT_DATA_BLOCKTRADE / "
        f"解禁 RPT_LIFT_STAGE）；解禁只列 {as_of} 起未来 {UNLOCK_FORWARD_DAYS} 天时间表，"
        "是待验证变量+时点，不是涨跌预测。只列事实，不构成买卖建议。"
    )
    if margin_rows is not None:
        lines.extend(_render_margin(margin_rows))
    if block_rows is not None:
        lines.extend(_render_block(block_rows))
    if unlock_rows is not None:
        lines.extend(_render_unlock(unlock_rows, as_of))
    return "\n".join(lines)


def capital_bundle_for_llm(
    query: str,
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
    timeout: float = 8.0,
    deadline: ResearchDeadline | None = None,
    task_query: str = "",
    check_cancelled: Callable[[], None] = lambda: None,
    margin_fetcher: Callable[..., list[MarginRow]] | None = None,
    block_fetcher: Callable[..., list[BlockTradeRow]] | None = None,
    unlock_fetcher: Callable[..., list[UnlockRow]] | None = None,
) -> CapitalBundle:
    """旧 ask 与 Episode 共用取数。每切片保留状态，共享一个绝对截止时刻。

    两融/大宗可按交易日回看（非当时已知证明）；解禁滚动表无披露时点，拒绝历史快照。
    socket timeout 不是操作系统硬墙；不以本函数保证单次阻塞读取绝不超时。
    """
    today = date.today().isoformat()
    end = min(date.fromisoformat(as_of or today).isoformat(), today)
    window = deadline.bounded_stage(timeout) if deadline else ResearchDeadline.from_timeout(timeout)
    slices = parse_capital_slices(query)
    def gap(text: str, reason_code: str = "") -> CapitalBundle:
        return CapitalBundle("", "", end, today, diagnostic=text, reason_code=reason_code)
    if not slices:
        return gap("请指定两融、大宗或解禁；本工具不提供大单流、龙虎榜或股东名单")
    try:
        end = capital_query_cutoff(task_query, upper_bound=end).isoformat()
        end = capital_query_cutoff(query, upper_bound=end).isoformat()
    except ValueError as exc:
        return gap(str(exc), "historical_date_unresolved")
    check_cancelled()
    db_path = Path(market_db_path).expanduser() if market_db_path else DEFAULT_MARKET_DB_PATH
    if not db_path.exists():
        return gap("本地证券身份库不可用，未请求外部数据")
    db_result = retrieval_cache.try_connect_readonly(db_path)
    if not db_result.available:
        return gap("本地证券身份库不可读，未请求外部数据")
    con = db_result.connection
    try:
        stock = resolve_capital_stock(con, query)
    except ValueError as exc:
        return gap(str(exc))
    except Exception:
        return gap("证券身份查询失败，未请求外部数据")
    finally:
        con.close()
    if stock is None:
        return gap("未解析到单只 A 股，请提供股票全名或六位代码；未请求外部数据")
    ts_code, name = stock
    code = ts_code.split(".")[0]
    results = []
    for kind in ("margin", "block", "unlock"):
        if kind not in slices:
            continue
        check_cancelled()
        if kind == "unlock" and end < today:
            results.append(CapitalSliceResult(kind, status="not_attempted", detail="历史解禁快照未取得；滚动源无披露日期，不能证明当时已知，未请求"))
            continue
        budget = window.stage_timeout(timeout)
        if budget <= 0.001:
            results.append(CapitalSliceResult(kind, status="not_attempted", detail="剩余预算不足，未请求；不能判断是否有记录"))
            continue
        try:
            if kind == "margin":
                rows = (margin_fetcher(code, DEFAULT_MARGIN_DAYS, budget) if margin_fetcher
                        else fetch_margin_rows(code, DEFAULT_MARGIN_DAYS, budget, as_of=end))
                limit = DEFAULT_MARGIN_DAYS
            elif kind == "block":
                rows = (block_fetcher(code, DEFAULT_BLOCK_ROWS, budget) if block_fetcher
                        else fetch_block_rows(code, DEFAULT_BLOCK_ROWS, budget, as_of=end))
                limit = DEFAULT_BLOCK_ROWS
            else:
                rows = (unlock_fetcher or fetch_unlock_rows)(code, end, UNLOCK_FORWARD_DAYS, budget)
                limit = 20
            check_cancelled()
            if window.expired:
                raise CapitalFetchError("request_error", "取数超过本次预算，晚结果未用于判断")
            kept = []
            for row in rows:
                row_date = _date_text(row.free_date if kind == "unlock" else row.trade_date)
                if kind == "unlock":
                    if not end <= row_date <= (date.fromisoformat(end) + timedelta(days=UNLOCK_FORWARD_DAYS)).isoformat():
                        continue
                    values = (row.shares_wan, row.ratio_pct)
                elif kind == "margin":
                    if row_date > end:
                        continue
                    values = (row.financing_yi, row.financing_buy_yi, row.short_yi)
                else:
                    if row_date > end:
                        continue
                    values = (row.price, row.amount_wan)
                if not any(_num(value) is not None for value in values):
                    raise CapitalFetchError("parse_error", "源记录关键数值全缺，不能当成成功或无记录")
                kept.append(row)
            truncated = len(kept) > limit
            results.append(CapitalSliceResult(
                kind, tuple(kept[:limit]),
                "partial" if truncated else "success" if kept else "empty",
                f"结果截断至 {limit} 条，不代表完整日程" if truncated else "",
            ))
        except CapitalFetchError as exc:
            results.append(CapitalSliceResult(kind, status=exc.status, detail=str(exc)))
        except Exception as exc:
            check_cancelled()
            results.append(CapitalSliceResult(kind, status="request_error", detail=f"请求失败（{type(exc).__name__}）；不能判断是否有记录"))
    return CapitalBundle(
        name, ts_code, end, today, tuple(results),
        reason_code="historical_snapshot_unavailable" if "unlock" in slices and end < today else "",
    )


def capital_block_for_llm(
    query: str,
    market_db_path: str | Path | None,
    *,
    as_of: str | None = None,
    timeout: float = 8.0,
    margin_fetcher: Callable[..., list[MarginRow]] | None = None,
    block_fetcher: Callable[..., list[BlockTradeRow]] | None = None,
    unlock_fetcher: Callable[..., list[UnlockRow]] | None = None,
) -> str:
    if not parse_capital_intent(query):
        return ""
    bundle = capital_bundle_for_llm(
        query, market_db_path, as_of=as_of, timeout=timeout,
        margin_fetcher=margin_fetcher, block_fetcher=block_fetcher, unlock_fetcher=unlock_fetcher,
    )
    # 保留旧无标的时不注入块的行为，但不能吞掉日期/身份冲突等拒绝原因。
    if bundle.diagnostic.startswith("未解析到单只 A 股"):
        return ""
    return bundle.block
