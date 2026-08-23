"""问句日确定性预取：双红个数、发酵精确名时间轴。

不给模型 Shell / 任意 SQL。harness 在进场前跑分析师第一刀查询，
观察值与 AgentEvidence 交给 episode。阈值只引用
``theme_lifecycle_timeline`` 的双红常量。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from intelligence.paths import default_market_db_path
from intelligence.services.agent_research import (
    AgentEvidence,
    StructuredObservation,
    evidence_content_hash,
)
from intelligence.services.theme_lifecycle_timeline import (
    DOUBLE_RED_AMOUNT,
    DOUBLE_RED_DIFF,
    DOUBLE_RED_PCT,
    is_double_red,
    load_theme_daily_rows,
    resolve_theme_alias,
)
from intelligence.services.market_analogs import parse_analog_intent
from intelligence.services.market_regime_analogs import (
    parse_regime_intent,
    regime_block_for_llm,
)
from intelligence.services.stock_analogs import parse_stock_analog_intent

FERMENTATION_MARKERS = (
    "发酵",
    "回溯",
    "链路",
    "怎么走到",
    "怎么走过来",
    "起涨",
    "补涨",
)

_FERMENT_END_ISO_RE = re.compile(
    r"(?:发酵到|回溯到|截止到|截至|走到)\s*(?P<iso>\d{4}-\d{2}-\d{2})"
)
_LEADING_ISO_RE = re.compile(r"^(?P<iso>\d{4}-\d{2}-\d{2})(?!\s*至)")
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIMELINE_LOOKBACK_DAYS = 30

_CALIBER = (
    f"pct_chg>{DOUBLE_RED_PCT:g} 且 diff_ratio>{DOUBLE_RED_DIFF:g} "
    f"且 amount>{DOUBLE_RED_AMOUNT:g}"
)


def is_fermentation_query(query: str) -> bool:
    text = str(query or "")
    return any(marker in text for marker in FERMENTATION_MARKERS)


def standing_iso_from_query(query: str) -> str | None:
    """问句站立日（ISO）。区间题（1日至5日）返回 None，避免把起点当截止日。

    顺序：收盘站立日由调用方 ``requested_information_cutoff`` 先匹配；
    这里补发酵终点日、以及问句开头的单个 ISO 日期。
    """

    text = str(query or "").strip()
    if not text:
        return None
    if is_fermentation_query(text):
        match = _FERMENT_END_ISO_RE.search(text)
        if match is not None:
            return match.group("iso")
        isos = _ISO_RE.findall(text)
        if len(isos) == 1:
            return isos[0]
        if len(isos) >= 2:
            return max(isos)
        return None
    if re.search(r"\d{4}-\d{2}-\d{2}\s*至", text) or re.search(
        r"\d{4}年\d{1,2}月\d{1,2}日至", text
    ):
        return None
    leading = _LEADING_ISO_RE.match(text)
    if leading is not None:
        return leading.group("iso")
    return None


def dual_red_counts(
    con: Any,
    days: tuple[date, ...],
) -> dict[str, str]:
    """每个交易日：双红个数，或 ``缺数``（当日板块表零行）。"""

    out: dict[str, str] = {}
    for day in days:
        iso = day.isoformat()
        total = con.execute(
            "select count(*) from fact_sector_daily where trade_date = ?",
            [iso],
        ).fetchone()
        if total is None or int(total[0]) == 0:
            out[iso] = "缺数"
            continue
        n = con.execute(
            """
            select count(*) from fact_sector_daily
            where trade_date = ?
              and pct_chg > ?
              and diff_ratio > ?
              and amount > ?
            """,
            [iso, DOUBLE_RED_PCT, DOUBLE_RED_DIFF, DOUBLE_RED_AMOUNT],
        ).fetchone()
        out[iso] = str(int(n[0]) if n else 0)
    return out


def format_dual_red_counts(counts: dict[str, str]) -> str:
    parts = [f"{day}={value}" for day, value in counts.items()]
    return "双红个数（口径 " + _CALIBER + "）：" + "；".join(parts)


_TIMELINE_METRICS = ("pct_chg", "amount", "diff_ratio")


def sector_timeline_observations(
    rows: list[dict[str, Any]],
    *,
    sector_name: str,
    start: str,
    end: str,
) -> tuple[StructuredObservation, ...]:
    """与 ``format_sector_timeline`` 同源同窗，只是不拼成文本。

    取数与格式化分开：格式化改措辞不该动到槽里的数，槽换口径也不该动文案。
    """

    seen: dict[tuple[str, str], set[float]] = {}
    for row in rows:
        day = str(row.get("trade_date") or "")[:10]
        if day < start or day > end:
            continue
        for metric in _TIMELINE_METRICS:
            raw = row.get(metric)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            seen.setdefault((day, metric), set()).add(value)
    # 同一 (日期,指标) 出现互相矛盾的值 → **不产出观察值**。
    #
    # 生产实锤 run_20260821_114642_385979：`钙钛矿电池` 撞 2 个 sector_ts_code，
    # E1 里 13 个交易日同日两行（922.49 与 914.5）。两行并排当事实端上桌，
    # 模型只能诚实写成区间「约914-922亿」，判官再按「不等于任何注册数字」
    # 判它编造。**把矛盾当事实投递，是那条质量下降链的第一次分叉。**
    #
    # 这里宁可少给（该格降为结构缺口）也不给一个随便挑的值：静默挑第一行
    # 会让「有分歧」和「就是这个数」在下游长得一样，正是本模块一贯禁的近似。
    # 值相同的重复行无害，照常产出。
    return tuple(
        StructuredObservation(
            subject=sector_name, as_of=day, metric=metric, value=next(iter(values))
        )
        for (day, metric), values in seen.items()
        if len(values) == 1
    )


def observation_value(
    items: tuple[PrefetchItem, ...],
    *,
    trade_date: str,
    metric: str,
    sector_name: str | None = None,
) -> float | None:
    """从预取行取一个格子的真值。**精确匹配，缺数返 None。**

    禁止回退到邻近交易日、另一板块或近似指标：静默近似会让「没有数据」
    和「数据是这个」在下游长得一样，覆盖率审计永远抓不到。
    None 的正确处置是标结构缺口，不是拿别的数顶上。
    """

    for item in items:
        for obs in item.observations:
            if obs.as_of != trade_date or obs.metric != metric:
                continue
            if sector_name is not None and obs.subject != sector_name:
                continue
            return obs.value
    return None


def format_sector_timeline(
    rows: list[dict[str, Any]],
    *,
    sector_name: str,
    start: str,
    end: str,
) -> str:
    lines = [
        f"板块={sector_name}；窗口 {start}..{end}；口径 {_CALIBER}",
    ]
    # 同日多行 = 供应商口径分歧（板块名撞多个 sector_ts_code）。并排列成两条
    # 事实会逼模型写区间，再被判官按「不等于任何注册数字」判编造——生产实锤
    # run_20260821_114642_385979。这里把分歧显式说出来，不当事实端上桌。
    per_day: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        day = str(row.get("trade_date") or "")[:10]
        if start <= day <= end:
            per_day.setdefault(day, []).append(row)
    for day in sorted(per_day):
        same_day = per_day[day]
        if len(same_day) > 1:
            variants = "；".join(
                f"涨跌幅={r.get('pct_chg')}／成交额亿={r.get('amount')}"
                f"／边际量={r.get('diff_ratio')}"
                for r in same_day
            )
            lines.append(
                f"交易日={day}；**口径分歧**：库中有 {len(same_day)} 条互不一致的行"
                f"（{variants}）。该日数值不作为证据，"
                "回答时请说明存在口径分歧，不要合成区间或任选其一。"
            )
            continue
        row = same_day[0]
        stamp = "是" if is_double_red(row) else "否"
        pct = row.get("pct_chg")
        amount = row.get("amount")
        diff = row.get("diff_ratio")
        lines.append(
            f"交易日={day}；涨跌幅={pct}；成交额亿={amount}；"
            f"边际量={diff}；双红={stamp}"
        )
    if len(lines) == 1:
        return f"未锚定板块逐日行：{sector_name} 在 {start}..{end} 无 fact_sector_daily 行"
    return "；".join(lines) if len(lines) <= 2 else "\n".join(lines)


def _prior_trade_dates(con: Any, as_of: date, n: int) -> tuple[date, ...]:
    rows = con.execute(
        """
        select distinct trade_date
        from fact_sector_daily
        where trade_date <= ?
        order by trade_date desc
        limit ?
        """,
        [as_of.isoformat(), n],
    ).fetchall()
    days: list[date] = []
    for row in rows:
        raw = row[0]
        if hasattr(raw, "isoformat"):
            days.append(raw)
        else:
            days.append(date.fromisoformat(str(raw)[:10]))
    return tuple(reversed(days))


def _timeline_window(con: Any, question: str, as_of: date) -> tuple[str, str]:
    isos = _ISO_RE.findall(str(question or ""))
    if len(isos) >= 2:
        return min(isos), max(isos)
    window_days = _prior_trade_dates(con, as_of, _TIMELINE_LOOKBACK_DAYS)
    start = window_days[0].isoformat() if window_days else as_of.isoformat()
    return start, as_of.isoformat()


def _connect(db_path: Path) -> Any | None:
    from intelligence.services import retrieval_cache

    if not db_path.exists():
        return None
    result = retrieval_cache.try_connect_readonly(db_path)
    if not result.available:
        return None
    return result.connection


def _exact_sector_names_in_query(con: Any, query: str) -> tuple[str, ...]:
    """问句里作为子串出现的 ``sector_name``，长名优先。

    不含 ``resolve_query_themes`` 的宽松轮：口语别名仍走 subject → alias。
    宽松命中若抢在精确长名之前，会把「PCB概念」收成短名「PCB」。
    """

    compact = re.sub(r"\s+", "", str(query or ""))
    if not compact:
        return ()
    try:
        names = [
            str(row[0])
            for row in con.execute(
                "select distinct sector_name from fact_sector_daily "
                "where sector_name is not null"
            ).fetchall()
        ]
    except Exception:
        return ()
    hit: list[str] = []
    remaining = compact
    for name in sorted({item for item in names if item}, key=len, reverse=True):
        if name in remaining:
            hit.append(name)
            remaining = remaining.replace(name, "□")
    return tuple(hit)


def resolve_prefetch_sector(con: Any, query: str, subject: str) -> str | None:
    """问句里已出现且表中存在的精确板块名优先；禁止 SQL ``contains`` 近义名。

    ``decide_turn`` 常把「PCB概念」收成 subject=「PCB」。短名在表里也有行，
    若先查 subject 会把问句点名的长口径挤掉。
    """

    candidates: list[str] = []
    for name in _exact_sector_names_in_query(con, query):
        if name not in candidates:
            candidates.append(name)
    subject_text = str(subject or "").strip()
    if subject_text and subject_text not in candidates:
        candidates.append(subject_text)
    for candidate in candidates:
        rows = load_theme_daily_rows(con, candidate)
        if rows:
            return candidate
        alias = resolve_theme_alias(con, candidate)
        if alias:
            rows = load_theme_daily_rows(con, alias)
            if rows:
                return alias
    from intelligence.services.market_midterm import resolve_query_themes

    hits = resolve_query_themes(con, query, limit=1)
    if hits:
        rows = load_theme_daily_rows(con, hits[0])
        if rows:
            return hits[0]
    return None


@dataclass(frozen=True)
class PrefetchItem:
    tool: str
    title: str
    detail: str
    source: str = "本地 DuckDB · 问句日预取"
    source_date: str | None = None
    observations: tuple[StructuredObservation, ...] = ()

    def to_evidence(self) -> AgentEvidence:
        item = AgentEvidence(
            tool=self.tool,
            title=self.title,
            detail=self.detail,
            source=self.source,
            source_date=self.source_date,
            evidence_tier="L4_structured",
            observations=self.observations,
        )
        return replace(item, content_hash=evidence_content_hash(item))


def _history_analog_items(
    question: str,
    as_of: date,
    as_of_iso: str,
    db_path: Path,
) -> list[PrefetchItem]:
    """算子命中即供数：D10 出块或 gap；D8 / D11 在 P0 只留 gap。

    不变量：D10 取数按 as_of 截断（见 market_regime_analogs.load_market_regime_vectors），
    禁止把问句截止日之后的行情写进历史窗口。
    """
    items: list[PrefetchItem] = []
    wants_regime = parse_regime_intent(question)
    wants_theme_analog = parse_analog_intent(question) and not wants_regime
    if wants_regime:
        block = regime_block_for_llm(db_path, as_of=as_of)
        if str(block or "").strip():
            items.append(
                PrefetchItem(
                    tool="market_data",
                    title="市场情绪环境类比 [D10]",
                    detail=block,
                    source="本地 DuckDB · D10",
                    source_date=as_of_iso,
                )
            )
        else:
            items.append(
                PrefetchItem(
                    tool="market_data",
                    title="historical_analogs gap（D10 不可用）",
                    detail=(
                        "D10 市场情绪类比不可用（库缺失、历史不足或无可比窗口）。"
                        "historical_analogs 必须标 gap，禁止用画像或框架原文冒充历史窗口。"
                    ),
                    source="本地 DuckDB · D10",
                    source_date=as_of_iso,
                )
            )
    elif wants_theme_analog:
        items.append(
            PrefetchItem(
                tool="market_data",
                title="historical_analogs gap（D8 未预取）",
                detail=(
                    "本题命中题材级历史类比算子，D10 市场环境块不适用；"
                    "D8 未在 Engine A 开场预取接线。historical_analogs 标 gap，"
                    "禁止编造未注册的历史阶段。"
                ),
                source="本地 DuckDB · D8 未预取",
                source_date=as_of_iso,
            )
        )
    if parse_stock_analog_intent(question):
        items.append(
            PrefetchItem(
                tool="market_data",
                title="个股对标 gap（D11 未预取）",
                detail=(
                    "本题含个股对标词面。D11 个股走势类比只在 Engine B 接线，"
                    "且当前实现不按 as_of 截断，P0 不接入 Engine A 预取。"
                    "个股对标必须标 gap，禁止用画像或题材原文冒充个股历史窗口。"
                ),
                source="D11 未预取",
                source_date=as_of_iso,
            )
        )
    return items


def collect_prefetch_items(
    *,
    question: str,
    question_type: str,
    subject: str,
    as_of: date,
    market_db_path: str | Path | None = None,
) -> tuple[PrefetchItem, ...]:
    db_path = (
        Path(market_db_path).expanduser()
        if market_db_path is not None
        else default_market_db_path()
    )
    items: list[PrefetchItem] = []
    as_of_iso = as_of.isoformat()
    items.extend(_history_analog_items(question, as_of, as_of_iso, db_path))
    con = _connect(db_path)
    if con is None:
        return tuple(items)
    try:
        if question_type == "market_forecast":
            try:
                days = _prior_trade_dates(con, as_of, 3)
                if days:
                    counts = dual_red_counts(con, days)
                    items.append(
                        PrefetchItem(
                            tool="market_data",
                            title="双红个数序列",
                            detail=format_dual_red_counts(counts),
                            source_date=as_of_iso,
                        )
                    )
            except Exception:
                pass
        if is_fermentation_query(question):
            try:
                sector = resolve_prefetch_sector(con, question, subject)
                if sector is None:
                    items.append(
                        PrefetchItem(
                            tool="finance_query",
                            title="发酵板块未锚定",
                            detail=(
                                "未锚定板块，双红序列未预取；"
                                "请用 finance_query 精确板块名，不要 contains 近义名"
                            ),
                            source_date=as_of_iso,
                        )
                    )
                else:
                    start, end = _timeline_window(con, question, as_of)
                    rows = load_theme_daily_rows(con, sector)
                    items.append(
                        PrefetchItem(
                            tool="market_data",
                            title=f"{sector} 双红时间轴",
                            detail=format_sector_timeline(
                                rows, sector_name=sector, start=start, end=end
                            ),
                            source_date=as_of_iso,
                            observations=sector_timeline_observations(
                                rows, sector_name=sector, start=start, end=end
                            ),
                        )
                    )
                    items.append(
                        PrefetchItem(
                            tool="mainline_context",
                            title="发酵题主线预取已替换",
                            detail=(
                                f"问句日 {as_of_iso} 未预取 runtime 当日主线总览；"
                                f"已用 {sector} 双红时间轴替代。"
                                "不要把更新的交易日主线当作本题证据。"
                            ),
                            source_date=as_of_iso,
                        )
                    )
            except Exception:
                pass
    finally:
        try:
            con.close()
        except Exception:
            pass
    return tuple(items)


def evidence_from_prefetch(items: tuple[PrefetchItem, ...]) -> tuple[AgentEvidence, ...]:
    return tuple(item.to_evidence() for item in items)


def format_opening_prefetch_message(items: tuple[PrefetchItem, ...] | tuple[AgentEvidence, ...]) -> str:
    """开场预取消息。带 E 号，否则模型引用不到、判官按无出处删真话。

    号不是这里新编的：``evidence_ordinal_table`` 与终局注册表同一张表，
    而 ``_seed_opening_prefetch`` 把预取**先**放进证据账本，故此处算出的
    ``E1..En`` 就是终局解析得到的那几个。认不出 hash 的条目不发号
    （fail closed），绝不自己编——编出来的号会解析到别人头上。
    """

    if not items:
        return ""
    from intelligence.services.episode_protocol import evidence_ordinal_table

    hashed = tuple(
        item for item in items if str(getattr(item, "content_hash", "") or "").strip()
    )
    table = evidence_ordinal_table(hashed)
    blocks: list[str] = []
    for item in items:
        digest = str(getattr(item, "content_hash", "") or "").strip()
        eid = table.get(digest)
        head = f"[{eid}] {item.title}" if eid else item.title
        blocks.append(f"{head}\n{item.detail}")
    return (
        "问句日预取（harness 进场事实，不是工具调用；"
        "下列 [E 号] 与证据注册表同号，写结论时可直接引用）：\n"
        + "\n\n".join(blocks)
    )
