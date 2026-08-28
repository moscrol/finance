"""问句日确定性预取：双红个数、发酵精确名时间轴。

不给模型 Shell / 任意 SQL。harness 在进场前跑分析师第一刀查询，
观察值与 AgentEvidence 交给 episode。阈值只引用
``theme_lifecycle_timeline`` 的双红常量。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date, timedelta
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
from intelligence.services.task_frame import is_weekly_calendar_question

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
# 区间分隔符只有一份词表。原先 `_MD_RANGE_RE` 认全套 `[-~—–～至到]`，而站立日守卫
# 与 `_LEADING_ISO_RE` 只认「至」——同一个概念在一个文件里存了两份，于是
# 「2026-07-16 到 07-22 …」绕过守卫，cutoff 落成区间**起点**，终点那端整段取不到
# （2026-08-27 四臂对照实测）。
_RANGE_SEP = r"[-~—–～至到]"
# 分隔符后面必须跟数字：区间总有第二个日期。只判分隔符会把
# 「2026-07-22 - 今天怎么样」这种误判成区间，把单日题也一起挡掉。
_RANGE_TAIL = rf"\s*{_RANGE_SEP}+\s*\d"
_LEADING_ISO_RE = re.compile(rf"^(?P<iso>\d{{4}}-\d{{2}}-\d{{2}})(?!{_RANGE_TAIL})")
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_MD_RANGE_RE = re.compile(
    rf"(?P<m1>\d{{1,2}})月(?P<d1>\d{{1,2}})日\s*{_RANGE_SEP}+\s*"
    r"(?:(?P<m2>\d{1,2})月)?(?P<d2>\d{1,2})日"
)
_TIMELINE_LOOKBACK_DAYS = 30

_CALIBER = (
    f"pct_chg>{DOUBLE_RED_PCT:g} 且 diff_ratio>{DOUBLE_RED_DIFF:g} "
    f"且 amount>{DOUBLE_RED_AMOUNT:g}"
)


def is_fermentation_query(query: str) -> bool:
    text = str(query or "")
    if is_weekly_calendar_question(text):
        # 「周末发酵了什么新闻 + 下周大事」是跨市场周历，不是题材发酵链路。
        return False
    return any(marker in text for marker in FERMENTATION_MARKERS)


def calendar_event_window(question: str, as_of: date) -> tuple[str, str]:
    """问句里的显式窗；没有就用 as_of 次日到 +7 日。"""

    text = str(question or "")
    isos = _ISO_RE.findall(text)
    if len(isos) >= 2:
        return min(isos), max(isos)
    match = _MD_RANGE_RE.search(text)
    if match is not None:
        year = as_of.year
        month2 = match.group("m2") or match.group("m1")
        start = date(year, int(match.group("m1")), int(match.group("d1")))
        end = date(year, int(month2), int(match.group("d2")))
        if end < start:
            end = date(year + 1, int(month2), int(match.group("d2")))
        return start.isoformat(), end.isoformat()
    start = as_of + timedelta(days=1)
    end = as_of + timedelta(days=7)
    return start.isoformat(), end.isoformat()


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
    if re.search(rf"\d{{4}}-\d{{2}}-\d{{2}}{_RANGE_TAIL}", text) or re.search(
        rf"\d{{4}}年\d{{1,2}}月\d{{1,2}}日{_RANGE_TAIL}", text
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
    """每个交易日：双红个数，或 ``缺数``（当日板块表零行）。

    算数面关掉时返回空 dict——调用方不得再拼「双红个数」观察值。空集合（生产默认）
    不走这支，行为与本函数不读开关时一致。
    """

    from intelligence.services.predicate_faces import faces

    if not faces().counts_double_red():
        return {}
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


def _calendar_prefetch_items(
    question: str,
    as_of: date,
    db_path: Path,
) -> tuple[PrefetchItem, ...]:
    """周历题进场先查 event_daily。空窗也落「查了、库无行」，不装没查。"""

    if not is_weekly_calendar_question(question):
        return ()
    start, end = calendar_event_window(question, as_of)
    title = f"事件日历 {start}..{end}"
    as_of_iso = as_of.isoformat()
    try:
        from intelligence.services.finance_query import FinanceQuery, FinanceQuerySpec
        from intelligence.services.research_contract import (
            InformationCutoff,
            ResearchDeadline,
        )

        result = FinanceQuery(db_path).run(
            FinanceQuerySpec.from_arguments(
                {
                    "dataset": "event_daily",
                    "metrics": ["importance"],
                    "dimensions": [
                        "event_date",
                        "title",
                        "content",
                        "sectors",
                        "is_future",
                    ],
                    "time_range": {"start": start, "end": end},
                    "order_by": [{"field": "event_date", "direction": "asc"}],
                    "limit": 25,
                }
            ),
            information_cutoff=InformationCutoff(as_of, "requested"),
            deadline=ResearchDeadline.from_timeout(2.0),
        )
    except Exception as exc:
        return (
            PrefetchItem(
                tool="finance_query",
                title=title,
                detail=f"已查 event_daily，窗口 {start}..{end}，查询失败：{exc}",
                source_date=as_of_iso,
            ),
        )
    if result.rows:
        detail = result.observation or "；".join(
            f"{row.get('event_date')} {row.get('title')}" for row in result.rows
        )
    else:
        detail = (
            f"已查 event_daily，窗口 {start}..{end}，库无行"
            "（复盘会编辑日历，不是官方全集）"
        )
    return (
        PrefetchItem(
            tool="finance_query",
            title=title,
            detail=detail,
            source_date=result.served_date or as_of_iso,
        ),
    )


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


def _market_forecast_weekly_items(
    as_of: date, as_of_iso: str, db_path: Path
) -> list[PrefetchItem]:
    """展望开口菜。自己连库、自己分类；锁和爆炸必须发卡，不得依赖外层 con。"""

    try:
        from intelligence.services.weekly_watch_pack import (
            day_bag_details,
            run_weekly_watch_pack,
        )

        weekly = run_weekly_watch_pack(
            as_of_iso,
            market_db_path=db_path,
            window=5,
        )
        if weekly.access != "ok":
            return [
                PrefetchItem(
                    tool="market_data",
                    title=title,
                    detail=detail,
                    source_date=as_of_iso,
                )
                for title, detail in day_bag_details(weekly)
            ]
        if weekly.days:
            return [
                PrefetchItem(
                    tool="market_data",
                    title=title,
                    detail=detail,
                    source_date=as_of_iso if title == "先验周量能序列" else title[:10],
                )
                for title, detail in day_bag_details(weekly)
            ]
        con = _connect(db_path)
        if con is None:
            return [
                PrefetchItem(
                    tool="market_data",
                    title="先验周盘面",
                    detail="status=unavailable 盘面库打不开，不是该日无数据。",
                    source_date=as_of_iso,
                )
            ]
        try:
            days = _prior_trade_dates(con, as_of, 3)
            if not days:
                return []
            counts = dual_red_counts(con, days)
            return [
                PrefetchItem(
                    tool="market_data",
                    title="双红个数序列",
                    detail=format_dual_red_counts(counts),
                    source_date=as_of_iso,
                )
            ]
        finally:
            con.close()
    except Exception as exc:
        return [
            PrefetchItem(
                tool="market_data",
                title="先验周盘面",
                detail=f"status=unavailable {type(exc).__name__}: {exc}",
                source_date=as_of_iso,
            )
        ]


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
    if question_type == "market_forecast":
        from intelligence.services.forecast_residual_followup import (
            WEEKLY_PACK_REUSE_DETAIL,
            WEEKLY_PACK_REUSE_TITLE,
            should_skip_weekly_pack,
        )

        if should_skip_weekly_pack(
            question=question, question_type=question_type
        ):
            items.append(
                PrefetchItem(
                    tool="market_data",
                    title=WEEKLY_PACK_REUSE_TITLE,
                    detail=WEEKLY_PACK_REUSE_DETAIL,
                    source_date=as_of_iso,
                )
            )
        else:
            items.extend(_market_forecast_weekly_items(as_of, as_of_iso, db_path))
    con = _connect(db_path)
    if con is None:
        return tuple(items)
    from intelligence.services.query_understanding import (
        SIGNAL_FERMENTATION,
        surface_research_signals,
    )
    from intelligence.services.research_contract import (
        OPERATOR_STRICT_DOUBLE_RED,
        compile_research_program,
    )

    from intelligence.services.research_contract import (
        OPERATOR_STEP_TRAJECTORY,
        OPERATOR_SUBSTITUTE_OBSERVATION,
        OPERATOR_VOLUME_QUALIFICATION,
        OPERATOR_WIDTH_RESONANCE,
    )

    program = compile_research_program(question, question_class=question_type)
    has_double_red = OPERATOR_STRICT_DOUBLE_RED in program.operators
    ferment_sector: str | None = None
    try:
        items.extend(_calendar_prefetch_items(question, as_of, db_path))
        if OPERATOR_SUBSTITUTE_OBSERVATION in program.operators:
            items.extend(_substitute_observation_items(con, as_of))
        if OPERATOR_VOLUME_QUALIFICATION in program.operators:
            items.extend(_volume_qualification_items(con, as_of))
        ferment = SIGNAL_FERMENTATION in surface_research_signals(
            question, question_class=question_type
        )
        if has_double_red and ferment:
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
                    ferment_sector = sector
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
        if question_type == "theme_analysis":
            # R-20260828-02：题材题确定性供数（精确板块行 + 成员映射），
            # 内层自捕获——本分支失败不得连坐后续 operator 的预取。
            try:
                items.extend(
                    _theme_sector_snapshot_items(
                        con,
                        question,
                        subject,
                        as_of,
                        exclude_sector=ferment_sector,
                    )
                )
            except Exception:
                pass
        if OPERATOR_STEP_TRAJECTORY in program.operators:
            items.extend(
                _step_trajectory_items(
                    con,
                    subject,
                    as_of,
                    exclude_sector=ferment_sector,
                )
            )
        if OPERATOR_WIDTH_RESONANCE in program.operators:
            items.extend(_width_resonance_items(con, as_of))
    finally:
        try:
            con.close()
        except Exception:
            pass
    return tuple(items)


def _substitute_observation_items(
    con: Any,
    as_of: date,
) -> tuple[PrefetchItem, ...]:
    """题材+个股观察题：主线题材当日无严格双红匹配时，预取带标签替补池。

    站立日 = 库内 ``max(trade_date) <= as_of``（隐式语义，不越过问句截止日）；
    探针查询本身仍是该站立日精确命中（复用 market_watch_pack 探针，
    无第二套口径）。任何异常回空——预取不得杀掉整个 episode 开口。
    """

    from intelligence.services.market_watch_pack import (
        SUBSTITUTE_BLOCK_TITLE,
        render_probe_lines,
        substitute_observation_receipts,
    )

    try:
        standing = _standing_on_or_before(con, as_of)
        probes = substitute_observation_receipts(con, standing)
        if not probes:
            return ()
        return (
            PrefetchItem(
                tool="market_data",
                title=SUBSTITUTE_BLOCK_TITLE.lstrip("# "),
                detail="\n".join(render_probe_lines(probes)),
                source_date=standing,
            ),
        )
    except Exception:
        return ()


def _width_resonance_items(con: Any, as_of: date) -> tuple[PrefetchItem, ...]:
    """概念×申万一级宽度对照袋：站立日与其余袋同源，异常回空，空集也上桌。

    空集也交付（「查过了、当日无放量上涨概念」），否则模型分不清
    「没查」和「查了没有」——与替补探针的 no-hit 表达同一纪律。
    """

    from intelligence.services.market_watch_pack import (
        WIDTH_RESONANCE_DISCLAIMER,
        WIDTH_RESONANCE_MIN_AMOUNT,
        WIDTH_RESONANCE_TITLE,
        render_width_resonance_lines,
        width_resonance_rows,
    )

    try:
        standing = _standing_on_or_before(con, as_of)
        if standing is None:
            return ()
        rows = width_resonance_rows(con, standing)
        if rows:
            body = "\n".join(render_width_resonance_lines(rows))
        else:
            body = (
                f"站立日 {standing} 无符合条件的放量上涨概念"
                f"（pct_chg>0 且成交额≥{WIDTH_RESONANCE_MIN_AMOUNT:.0f} 亿），"
                "对照为空集。"
            )
        return (
            PrefetchItem(
                tool="market_data",
                title=WIDTH_RESONANCE_TITLE,
                detail=f"{WIDTH_RESONANCE_DISCLAIMER}\n{body}",
                source_date=standing,
            ),
        )
    except Exception:
        return ()


THEME_SNAPSHOT_UNANCHORED_TITLE = "题材板块未锚定"
_THEME_MEMBER_LIMIT = 12


def _theme_sector_snapshot_items(
    con: Any,
    question: str,
    subject: str,
    as_of: date,
    *,
    exclude_sector: str | None = None,
) -> tuple[PrefetchItem, ...]:
    """theme_analysis 确定性预取：精确板块名 → 当日板块行 + 成员表。

    `R-20260828-02`（四臂 D5、`R-20260827-09` refuted 升格）：模型自选查询
    从不使用精确板块名（``contains "核"`` 撒网 / 按成交额 top8），判据要的
    板块数值与成员映射永远缺供数。解析复用 ``resolve_prefetch_sector``
    （问句内精确长名 > subject > 既有别名梯，与发酵分支同一把尺）；解析不到
    → 单条 fail-closed 提示项，不臆配。``exclude_sector``：发酵分支已交付
    同板块逐日时间轴时，板块行让位、成员表仍交付（时间轴不含成员映射）。
    """

    as_of_iso = as_of.isoformat()
    sector = resolve_prefetch_sector(con, question, subject)
    if sector is None:
        return (
            PrefetchItem(
                tool="finance_query",
                title=THEME_SNAPSHOT_UNANCHORED_TITLE,
                detail=(
                    "未在板块表中锚定精确板块名，当日板块行与成员表未预取；"
                    "请用 finance_query 精确板块名查 sector_daily / "
                    "sector_stock_daily，不要 contains 近义名"
                ),
                source_date=as_of_iso,
            ),
        )
    items: list[PrefetchItem] = []
    trade_iso = as_of_iso
    row = con.execute(
        "select trade_date, pct_chg, diff_ratio, amount from fact_sector_daily "
        "where sector_name = ? and trade_date <= cast(? as date) "
        "order by trade_date desc limit 1",
        [sector, as_of_iso],
    ).fetchone()
    if row is None:
        # 板块锚定成功、却没有当日及之前的板块行（`R-20260828-04`）。这条路真实
        # 可达：`resolve_prefetch_sector` 经 `load_theme_daily_rows` 判存在性，
        # 而后者**不带日期过滤**——「板块在表里有行」与「as_of 当天有行」是两件
        # 事，问一个板块诞生前的日期即命中（本仓明确支持回溯问句）。
        # 缺口必须出声：静默返回 = 让模型以为没有异常。
        items.append(
            PrefetchItem(
                tool="finance_query",
                title=f"{sector} 板块行缺失（{as_of_iso}）",
                detail=(
                    f"fact_sector_daily 在 {as_of_iso} 及之前无 {sector} 行，"
                    "当日板块数值未预取；不要用其他日期的板块行冒充"
                ),
                source_date=as_of_iso,
            )
        )
    else:
        trade_iso = str(row[0])[:10]
        pct, diff, amount = row[1], row[2], row[3]
        if sector != exclude_sector:
            parts = [f"{sector} {trade_iso}："]
            observations: list[StructuredObservation] = []
            for metric, value, label, fmt in (
                ("pct_chg", pct, "涨跌幅", "{:+.2f}%"),
                ("diff_ratio", diff, "边际量", "{:+.1f}%"),
                ("amount", amount, "成交额", "{:.1f} 亿"),
            ):
                if value is None:
                    continue
                parts.append(f"{label} {fmt.format(float(value))}")
                observations.append(
                    StructuredObservation(
                        subject=sector,
                        as_of=trade_iso,
                        metric=metric,
                        value=float(value),
                    )
                )
            items.append(
                PrefetchItem(
                    tool="market_data",
                    title=f"{sector} 板块日行情（{trade_iso}）",
                    detail=parts[0] + "，".join(parts[1:]),
                    source_date=trade_iso,
                    observations=tuple(observations),
                )
            )
    member_rows = con.execute(
        "select stock_name, pct_chg, amount, pct_chg_5d "
        "from fact_sector_stock_daily "
        "where sector_name = ? and trade_date = cast(? as date) "
        "order by amount desc nulls last limit ?",
        [sector, trade_iso, _THEME_MEMBER_LIMIT],
    ).fetchall()
    if member_rows:
        lines = []
        member_obs: list[StructuredObservation] = []
        for name, pct, amount, pct_5d in member_rows:
            piece = [str(name)]
            if pct is not None:
                piece.append(f"涨跌幅 {float(pct):+.2f}%")
                member_obs.append(
                    StructuredObservation(
                        subject=str(name),
                        as_of=trade_iso,
                        metric="pct_chg",
                        value=float(pct),
                    )
                )
            if amount is not None:
                piece.append(f"成交额 {float(amount):.1f}亿")
            if pct_5d is not None:
                piece.append(f"5日 {float(pct_5d):+.1f}%")
            lines.append(" ".join(piece))
        items.append(
            PrefetchItem(
                tool="finance_query",
                title=f"{sector} 成员当日表现 top{len(member_rows)}（{trade_iso}，按成交额）",
                detail="；".join(lines),
                source_date=trade_iso,
                observations=tuple(member_obs),
            )
        )
    else:
        # 缺口声明**不再挂在「板块行已产出」上**（`R-20260828-04`）。原先写作
        # `elif items:`，于是它恰好在两种最该出声的场合被抑制：板块行本身缺失
        # 时，以及 exclude_sector 命中（发酵分支已交付时间轴）时——而成员映射
        # 正是发酵分支不提供、本函数存在的理由。
        items.append(
            PrefetchItem(
                tool="finance_query",
                title=f"{sector} 成员行缺失（{trade_iso}）",
                detail=(
                    f"fact_sector_stock_daily 在 {trade_iso} 无 {sector} 成员行，"
                    "个股映射存在覆盖缺口；不要用其他日期的成员表冒充"
                ),
                source_date=trade_iso,
            )
        )
    return tuple(items)


QUALIFICATION_TITLE = "大盘量能资格盘"
TRAJECTORY_TITLE_SUFFIX = " 近5日量能台阶"
UNANCHORED_TRAJECTORY_TITLE = "量能台阶：subject 未锚定声明"
_TRAJECTORY_WINDOW_DAYS = 5
_TRAJECTORY_MAX_SECTORS = 6
_MAINLINE_LOOKBACK_TRADE_DAYS = 20
_MAINLINE_MAX_THEMES = 6


def _standing_on_or_before(con: Any, as_of: date) -> str | None:
    """库内不越过问句截止日的最新行情站立日（替补/资格/台阶三件同源）。"""

    row = con.execute(
        "select max(trade_date) from fact_market_daily"
        " where trade_date <= cast(? as date)",
        [as_of.isoformat()],
    ).fetchone()
    return str(row[0]) if row and row[0] else None


def _volume_qualification_items(con: Any, as_of: date) -> tuple[PrefetchItem, ...]:
    """大盘量能资格盘：站立日总量 vs 20 日均额（含当日窗口，spec §6.1）。

    只交付事实，资格判语（共建/主升）留给回答方按画像规则解读。窗口实有
    N<20 时如实标注真实口径，且不注册均额/比值观察值（口径不纯不注册），
    N=20 才注册三个观察值。任何异常回空——预取不得杀 episode 开口。
    """

    from intelligence.services.market_watch_pack import (
        AMOUNT_MA20_WINDOW,
        volume_qualification_receipt,
    )

    try:
        standing = _standing_on_or_before(con, as_of)
        receipt = volume_qualification_receipt(con, standing)
        if receipt is None:
            return ()
        served = str(receipt["standing_date"])
        window_n = int(receipt["window_n"])
        full_window = window_n == AMOUNT_MA20_WINDOW
        caliber = (
            "20日均额（窗口=截至站立日最近20个交易日、含当日）"
            if full_window
            else f"近{window_n}日均额（窗口不足20个交易日，N={window_n}，含当日）"
        )
        stage_day = receipt.get("stage_day")
        detail = (
            f"站立日={served}；全市场成交额={receipt['total_amount']} 亿；"
            f"{caliber}={receipt['amount_avg_20d']} 亿；"
            f"总量/均额比={receipt['amount_vs_avg20_pct']}%；"
            f"市场阶段={receipt.get('market_stage') or '未标注'}"
            + (f"（第{stage_day}天）" if stage_day is not None else "")
            + f"；量能状态={receipt.get('volume_state') or '未标注'}。"
            "本件只交付事实，资格判语（如共建/主升）由回答方按画像规则解读。"
        )
        observations = (
            StructuredObservation(
                subject="全市场",
                as_of=served,
                metric="total_amount",
                value=float(receipt["total_amount"]),
            ),
        )
        if full_window:
            observations += (
                StructuredObservation(
                    subject="全市场",
                    as_of=served,
                    metric="amount_avg_20d",
                    value=float(receipt["amount_avg_20d"]),
                ),
                StructuredObservation(
                    subject="全市场",
                    as_of=served,
                    metric="amount_vs_avg20_pct",
                    value=float(receipt["amount_vs_avg20_pct"]),
                ),
            )
        return (
            PrefetchItem(
                tool="market_data",
                title=QUALIFICATION_TITLE,
                detail=detail,
                source_date=served,
                observations=observations,
            ),
        )
    except Exception:
        return ()


def _subject_tokens(subject: str) -> tuple[str, ...]:
    return tuple(
        token.strip()
        for token in re.split(r"[、，,]", str(subject or ""))
        if token.strip()
    )


def _table_exists(con: Any, name: str) -> bool:
    row = con.execute(
        "select 1 from information_schema.tables"
        " where table_schema = 'main' and table_name = ?",
        [name],
    ).fetchone()
    return row is not None


def _recent_mainline_themes(
    con: Any,
    standing: str,
    lookback_start: str,
) -> tuple[str, ...]:
    if not _table_exists(con, "fact_mainline_theme_daily"):
        return ()
    rows = con.execute(
        """
        select theme_name, count(*) as registered_days
        from fact_mainline_theme_daily
        where trade_date <= cast(? as date)
          and trade_date >= cast(? as date)
          and theme_name is not null
        group by theme_name
        order by registered_days desc, theme_name
        limit ?
        """,
        [standing, lookback_start, _MAINLINE_MAX_THEMES],
    ).fetchall()
    return tuple(str(row[0]) for row in rows if row[0])


def _mainline_theme_registered(
    con: Any,
    standing: str,
    lookback_start: str,
    token: str,
) -> bool:
    if not _table_exists(con, "fact_mainline_theme_daily"):
        return False
    row = con.execute(
        """
        select 1 from fact_mainline_theme_daily
        where theme_name = ?
          and trade_date <= cast(? as date)
          and trade_date >= cast(? as date)
        limit 1
        """,
        [token, standing, lookback_start],
    ).fetchone()
    return row is not None


def _resolve_subject_token(
    con: Any,
    standing: str,
    lookback_start: str,
    token: str,
    start: str,
    end: str,
) -> str | None:
    """subject token → 板块口径，fail closed（spec §6.2 解析梯）。

    梯 1：token 精确等于板块名且窗口内有行；梯 2：token 恰为近 20 交易日
    主线登记题材名 → 复用替补探针的包含+额度 top1。**禁止宽松轮**——
    resolve_query_themes 的锚定宽松匹配会把「科技」臆配成「量子科技」，
    词面近邻 ≠ 语义家族（R-20260825-11）。解析不到由调用方如实声明。
    """

    from intelligence.services.market_watch_pack import resolve_theme_sector

    row = con.execute(
        """
        select 1 from fact_sector_daily
        where sector_name = ?
          and trade_date between cast(? as date) and cast(? as date)
        limit 1
        """,
        [token, start, end],
    ).fetchone()
    if row is not None:
        return token
    if _mainline_theme_registered(con, standing, lookback_start, token):
        hit = resolve_theme_sector(con, standing, token)
        if hit is not None:
            return hit[0]
    return None


def _step_trajectory_items(
    con: Any,
    subject: str,
    as_of: date,
    *,
    exclude_sector: str | None = None,
) -> tuple[PrefetchItem, ...]:
    """题目相关板块近 5 日量能台阶（spec §6.2：subject 解析 ∪ 主线池）。

    「AI算力/半导体属于科技系」这类语义归类刻意留给模型——组件只保证近
    20 交易日主线登记板块的台阶在桌上（cap 6，subject 命中优先占位）。
    发酵题已锚定的板块让位（exclude_sector），不双份。任何异常回空。
    """

    from intelligence.services.market_watch_pack import resolve_theme_sector

    try:
        standing = _standing_on_or_before(con, as_of)
        if standing is None:
            return ()
        standing_day = date.fromisoformat(standing[:10])
        window = _prior_trade_dates(con, standing_day, _TRAJECTORY_WINDOW_DAYS)
        if not window:
            return ()
        start, end = window[0].isoformat(), window[-1].isoformat()
        lookback = _prior_trade_dates(
            con, standing_day, _MAINLINE_LOOKBACK_TRADE_DAYS
        )
        lookback_start = lookback[0].isoformat() if lookback else start
        resolved: list[str] = []
        unresolved: list[str] = []
        for token in _subject_tokens(subject):
            sector = _resolve_subject_token(
                con, standing, lookback_start, token, start, end
            )
            if sector is None:
                unresolved.append(token)
            elif sector not in resolved:
                resolved.append(sector)
        for theme in _recent_mainline_themes(con, standing, lookback_start):
            if len(resolved) >= _TRAJECTORY_MAX_SECTORS:
                break
            hit = resolve_theme_sector(con, standing, theme)
            if hit is not None and hit[0] not in resolved:
                resolved.append(hit[0])
        pool = [
            sector for sector in resolved if sector != exclude_sector
        ][:_TRAJECTORY_MAX_SECTORS]
        items: list[PrefetchItem] = []
        for sector in pool:
            rows = load_theme_daily_rows(con, sector)
            items.append(
                PrefetchItem(
                    tool="market_data",
                    title=f"{sector}{TRAJECTORY_TITLE_SUFFIX}",
                    detail=format_sector_timeline(
                        rows, sector_name=sector, start=start, end=end
                    ),
                    source_date=standing,
                    observations=sector_timeline_observations(
                        rows, sector_name=sector, start=start, end=end
                    ),
                )
            )
        if unresolved:
            declared = "；".join(
                f"「{token}」未锚定到板块口径（不做宽松匹配，避免臆配词面近邻板块）"
                for token in unresolved
            )
            items.append(
                PrefetchItem(
                    tool="market_data",
                    title=UNANCHORED_TRAJECTORY_TITLE,
                    detail=(
                        f"{declared}。近 20 个交易日主线登记板块的台阶已另行上桌"
                        f"（站立日={standing}）。"
                    ),
                    source_date=standing,
                )
            )
        return tuple(items)
    except Exception:
        return ()


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
