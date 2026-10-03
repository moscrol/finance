"""记忆长河 + 连板日历的只读 API。

两条纪律与 `intelligence/services/river.py` 一致，写在这里是因为路由层最容易偷偷破戒：

1. **路径上无 LLM、无新存储。** 每个端点都是现算，同参数两次调用逐字段相同。
2. **缺就说缺。** 六轨时间轴里读不到的格子返回 ``None``，不用 0 冒充；切片里的
   ``Gap`` 原样透传给前端，由前端画成「缺口」而不是空白。

端点：

- ``GET /api/river/meta``        交易日历、默认实体、各轨数据覆盖区间
- ``GET /api/river/entities``    板块 / 题材实体检索（精确 + 前缀 + 包含，按成交额排序）
- ``GET /api/river/timeline``    一个实体 × 一段交易日 × 六轨的逐日摘要（长河主视图）
- ``GET /api/river/slice``       单点切片（透传 ``slice_river``）
- ``GET /api/river/scan``        横扫（透传 ``scan_cross_section`` / ``find_dislocation``）
- ``POST /api/river/cohort``     纵扫：条件选日 → ``cohort_compare``
- ``GET /api/river/range``       区间聚合（透传 ``range_aggregate``，附每日累计曲线）
- ``GET /api/river/kline``       上证 K 线底座：OHLCV + 周均线 + MA5/10/20/60
- ``GET /api/limitup/calendar``  连板日历：梯队 / 晋级率 / 龙头高度 / 市场环境
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from intelligence.services import river as river_svc
from intelligence.services import river_query as rq

DEFAULT_ENTITY_FALLBACK = "人工智能"
TRACK_LABELS: dict[str, str] = {
    "market": "盘面",
    "theme": "题材",
    "opinion": "舆论",
    "capital": "资金",
    "stock": "个股",
    "judgment": "判断",
}

CohortSelectorKind = Literal[
    "market_stage",
    "volume_state",
    "concentration_state",
    "limit_up_gte",
    "limit_down_gte",
    "amount_change_lte",
    "amount_change_gte",
    "sh_pct_lte",
    "sh_pct_gte",
    "explicit",
]


class CohortRequest(BaseModel):
    selector: CohortSelectorKind = "market_stage"
    value: str | float | None = None
    dates: list[str] = Field(default_factory=list)
    feature: Literal["market_stage", "volume_state", "concentration_state"] = "market_stage"
    start: str | None = None
    end: str | None = None


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    return str(v)[:10]


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        result = float(v)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _connect(db_path: Path):
    import duckdb

    if not db_path.exists():
        raise HTTPException(status_code=503, detail=f"盘面数据库不存在：{db_path}")
    return duckdb.connect(str(db_path), read_only=True)


def _rows(con: Any, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]


def _has_table(con: Any, table: str) -> bool:
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = ? LIMIT 1", [table]
        ).fetchone()
    )


def _trading_days(con: Any, start: str | None, end: str | None, limit: int | None = None) -> list[str]:
    sql = "SELECT CAST(trade_date AS DATE) AS d FROM fact_market_daily"
    where: list[str] = []
    params: list[Any] = []
    if start:
        where.append("CAST(trade_date AS DATE) >= CAST(? AS DATE)")
        params.append(start)
    if end:
        where.append("CAST(trade_date AS DATE) <= CAST(? AS DATE)")
        params.append(end)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY d DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return sorted(_iso(r["d"]) or "" for r in _rows(con, sql, params))


def _resolve(con: Any, as_of: str, entity: str) -> river_svc.EntityRef:
    ref = river_svc.resolve_entity(con, as_of, entity)
    if ref is None:
        raise HTTPException(
            status_code=404,
            detail=f"{as_of} 这天解析不到实体「{entity}」（只做精确匹配，不猜）",
        )
    return ref


# --------------------------------------------------------------------------- #
# 长河：元信息 / 实体
# --------------------------------------------------------------------------- #
def _track_coverage(con: Any) -> dict[str, dict[str, Any]]:
    """每条轨的主数据在库里覆盖到哪一天。前端用它画「这条轨从哪天起才有」。"""
    spec = {
        "market": ("fact_sector_daily", "trade_date"),
        "theme": ("fact_theme_limit_heat_daily", "trade_date"),
        "opinion": ("fact_research_report_catalog", "report_date"),
        "capital": ("fact_sector_stock_daily", "trade_date"),
        "stock": ("fact_sector_stock_daily", "trade_date"),
    }
    out: dict[str, dict[str, Any]] = {}
    for track, (table, col) in spec.items():
        if not _has_table(con, table):
            out[track] = {"table": table, "min": None, "max": None, "rows": 0}
            continue
        r = _rows(con, f"SELECT MIN({col}) AS lo, MAX({col}) AS hi, COUNT(*) AS n FROM {table}")[0]  # noqa: S608
        out[track] = {"table": table, "min": _iso(r["lo"]), "max": _iso(r["hi"]), "rows": int(r["n"] or 0)}
    ck = river_svc_checkpoints_path()
    out["judgment"] = {
        "table": str(ck),
        "min": None,
        "max": None,
        "rows": _count_lines(ck),
        "exists": ck.exists(),
    }
    return out


def river_svc_checkpoints_path() -> Path:
    try:
        from intelligence.userspace import user_space

        return Path(user_space().checkpoints_path)
    except Exception:  # noqa: BLE001 —— 用户空间不可用时判断轨整体报缺，不阻断其余五轨
        return Path("checkpoints.jsonl")


def _count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    with p.open(encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _entities(con: Any, as_of: str, q: str, limit: int) -> list[dict[str, Any]]:
    q = (q or "").strip()
    rows = _rows(
        con,
        """
        SELECT sector_ts_code AS id, sector_name AS name, amount, pct_chg
        FROM fact_sector_daily
        WHERE CAST(trade_date AS DATE) = CAST(? AS DATE)
          AND (? = '' OR sector_name = ? OR sector_ts_code = ? OR sector_name LIKE ? OR sector_name LIKE ?)
        ORDER BY
          CASE WHEN sector_name = ? OR sector_ts_code = ? THEN 0
               WHEN sector_name LIKE ? THEN 1 ELSE 2 END,
          amount DESC NULLS LAST
        LIMIT ?
        """,
        [as_of, q, q, q, f"{q}%", f"%{q}%", q, q, f"{q}%", int(limit)],
    )
    return [
        {"id": r["id"], "name": r["name"], "amount": _num(r["amount"]), "pct_chg": _num(r["pct_chg"])}
        for r in rows
    ]


# --------------------------------------------------------------------------- #
# 长河：六轨时间轴
# --------------------------------------------------------------------------- #
def _timeline(con: Any, entity: str, start: str, end: str) -> dict[str, Any]:
    days = _trading_days(con, start, end)
    if not days:
        raise HTTPException(status_code=404, detail=f"{start}~{end} 没有交易日")
    ref = _resolve(con, days[-1], entity)
    # 实体在这段日子里可能跨过换源（.TI → .FP）。按名字取全部代码，标记 codes_seen。
    codes = [
        r["c"]
        for r in _rows(
            con,
            """
            SELECT DISTINCT sector_ts_code AS c FROM fact_sector_daily
            WHERE sector_name = ? AND CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            """,
            [ref.name, start, end],
        )
    ]
    if not codes:
        codes = [ref.code_on_date]
    ph = ",".join("?" for _ in codes)

    market_rows = {
        _iso(r["d"]): r
        for r in _rows(
            con,
            """
            SELECT CAST(trade_date AS DATE) AS d, market_stage, stage_day, total_amount,
                   amount_vs_yesterday_pct, advancers, limit_up, limit_down, sh_index_pct_chg, volume_state
            FROM fact_market_daily
            WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            """,
            [start, end],
        )
    }
    sector_rows: dict[str, dict[str, Any]] = {}
    for r in _rows(
        con,
        f"""
        SELECT CAST(trade_date AS DATE) AS d, sector_ts_code, pct_chg, amount, diff_ratio, strength
        FROM fact_sector_daily
        WHERE sector_ts_code IN ({ph})
          AND CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        ORDER BY d, sector_ts_code
        """,  # noqa: S608
        [*codes, start, end],
    ):
        sector_rows.setdefault(_iso(r["d"]) or "", r)

    heat_rows: dict[str, dict[str, Any]] = {}
    if _has_table(con, "fact_theme_limit_heat_daily"):
        for r in _rows(
            con,
            f"""
            SELECT CAST(trade_date AS DATE) AS d, MAX(limit_up_count) AS limit_up_count,
                   MAX(total_count) AS total_count, MAX(limit_up_ratio) AS limit_up_ratio,
                   MIN(rank) AS rank, ANY_VALUE(top_stocks_json) AS top_stocks_json
            FROM fact_theme_limit_heat_daily
            WHERE sector_ts_code IN ({ph})
              AND CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            GROUP BY 1
            """,  # noqa: S608
            [*codes, start, end],
        ):
            heat_rows[_iso(r["d"]) or ""] = r

    # 舆论：研报目录按 report_date 计数，实体名精确落在 sector_tags / concept_tags / 标题里。
    opinion_rows: dict[str, dict[str, Any]] = {}
    if _has_table(con, "fact_research_report_catalog"):
        for r in _rows(
            con,
            """
            SELECT CAST(report_date AS DATE) AS d, COUNT(*) AS n,
                   LIST(title ORDER BY report_id DESC)[1:3] AS titles
            FROM fact_research_report_catalog
            WHERE CAST(report_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
              AND (COALESCE(sector_tags, '') LIKE ? OR COALESCE(concept_tags, '') LIKE ? OR title LIKE ?)
            GROUP BY 1
            """,
            [start, end, f'%"{ref.name}"%', f'%"{ref.name}"%', f"%{ref.name}%"],
        ):
            opinion_rows[_iso(r["d"]) or ""] = r

    # 资金 + 个股：成分股表按日聚合一次（这张表 470 万行，只扫一次）。
    cap_rows: dict[str, dict[str, Any]] = {}
    stock_rows: dict[str, dict[str, Any]] = {}
    if _has_table(con, "fact_sector_stock_daily"):
        for r in _rows(
            con,
            f"""
            SELECT CAST(trade_date AS DATE) AS d,
                   COUNT(*) AS n_stocks,
                   COUNT(fund_flow_1d) AS n_with_fund,
                   SUM(fund_flow_1d) AS fund_flow_1d,
                   SUM(CASE WHEN pct_chg >= 9.5 THEN 1 ELSE 0 END) AS n_limit_like,
                   SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) AS n_up,
                   SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) AS n_down,
                   ARG_MAX(stock_name, pct_chg) AS top_name,
                   MAX(pct_chg) AS top_pct,
                   ARG_MAX(stock_name, amount) AS amount_leader,
                   MAX(amount) AS amount_leader_amount
            FROM fact_sector_stock_daily
            WHERE sector_ts_code IN ({ph})
              AND CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            GROUP BY 1
            """,  # noqa: S608
            [*codes, start, end],
        ):
            d = _iso(r["d"]) or ""
            cap_rows[d] = r
            stock_rows[d] = r

    # 判断：checkpoints.jsonl 精确同名 themes，按 ts 日期计数。
    judgment_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    ck = river_svc_checkpoints_path()
    judgment_available = ck.exists()
    if judgment_available:
        with ck.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ref.name not in (rec.get("themes") or []):
                    continue
                d = str(rec.get("ts", ""))[:10]
                if start <= d <= end:
                    judgment_rows[d].append(
                        {"id": rec.get("id"), "claim": rec.get("claim"), "category": rec.get("category"), "due": rec.get("due")}
                    )

    out_days: list[dict[str, Any]] = []
    for d in days:
        m = market_rows.get(d)
        s = sector_rows.get(d)
        h = heat_rows.get(d)
        o = opinion_rows.get(d)
        c = cap_rows.get(d)
        st = stock_rows.get(d)
        j = judgment_rows.get(d)
        out_days.append(
            {
                "date": d,
                "market": None
                if m is None and s is None
                else {
                    "stage": m.get("market_stage") if m else None,
                    "stage_day": m.get("stage_day") if m else None,
                    "sh_pct": _num(m.get("sh_index_pct_chg")) if m else None,
                    "total_amount": _num(m.get("total_amount")) if m else None,
                    "amount_chg_pct": _num(m.get("amount_vs_yesterday_pct")) if m else None,
                    "limit_up": m.get("limit_up") if m else None,
                    "limit_down": m.get("limit_down") if m else None,
                    "sector_pct": _num(s.get("pct_chg")) if s else None,
                    "sector_amount": _num(s.get("amount")) if s else None,
                    "sector_diff_ratio": _num(s.get("diff_ratio")) if s else None,
                    "sector_code": s.get("sector_ts_code") if s else None,
                },
                "theme": None
                if h is None
                else {
                    "limit_up_count": h.get("limit_up_count"),
                    "total_count": h.get("total_count"),
                    "limit_up_ratio": _num(h.get("limit_up_ratio")),
                    "rank": h.get("rank"),
                    "top_stocks": _safe_json(h.get("top_stocks_json"))[:5],
                },
                "opinion": None if o is None else {"reports": int(o["n"]), "titles": list(o.get("titles") or [])},
                "capital": None
                if c is None or not c.get("n_with_fund")
                else {
                    "fund_flow_1d": _num(c.get("fund_flow_1d")),
                    "n_with_fund": int(c.get("n_with_fund") or 0),
                    "n_stocks": int(c.get("n_stocks") or 0),
                },
                "stock": None
                if st is None
                else {
                    "n_stocks": int(st.get("n_stocks") or 0),
                    "n_up": int(st.get("n_up") or 0),
                    "n_down": int(st.get("n_down") or 0),
                    "n_limit_like": int(st.get("n_limit_like") or 0),
                    "top_name": st.get("top_name"),
                    "top_pct": _num(st.get("top_pct")),
                    "amount_leader": st.get("amount_leader"),
                },
                "judgment": None if not j else {"count": len(j), "items": j[:3]},
            }
        )

    return {
        "entity": {"id": ref.canonical_id, "name": ref.name, "codes_seen": codes, "alias_applied": ref.alias_applied or len(codes) > 1},
        "start": days[0],
        "end": days[-1],
        "trading_days": len(days),
        "judgment_source": {"path": str(ck), "exists": judgment_available},
        "days": out_days,
    }


def _safe_json(raw: Any) -> list[Any]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


# --------------------------------------------------------------------------- #
# 纵扫：条件选日
# --------------------------------------------------------------------------- #
def _select_dates(con: Any, req: CohortRequest) -> tuple[list[str], str]:
    if req.selector == "explicit":
        return sorted({d[:10] for d in req.dates if d}), "显式日期列表"
    where: list[str] = []
    params: list[Any] = []
    if req.start:
        where.append("CAST(trade_date AS DATE) >= CAST(? AS DATE)")
        params.append(req.start)
    if req.end:
        where.append("CAST(trade_date AS DATE) <= CAST(? AS DATE)")
        params.append(req.end)
    v = req.value
    label = ""
    if req.selector in {"market_stage", "volume_state", "concentration_state"}:
        if not isinstance(v, str) or not v:
            raise HTTPException(status_code=422, detail=f"{req.selector} 需要一个类别值")
        col = req.selector
        if req.selector == "market_stage":
            # 与 river_query.normalize_stage 同口径：库里「下跌阶段」与「下跌」并存。
            where.append("REPLACE(COALESCE(market_stage, ''), '阶段', '') = ?")
            params.append(v.replace("阶段", ""))
        else:
            where.append(f"{col} = ?")
            params.append(v)
        label = f"{col} = {v}"
    else:
        try:
            num = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"{req.selector} 需要一个数值") from exc
        col, op = {
            "limit_up_gte": ("limit_up", ">="),
            "limit_down_gte": ("limit_down", ">="),
            "amount_change_lte": ("amount_vs_yesterday_pct", "<="),
            "amount_change_gte": ("amount_vs_yesterday_pct", ">="),
            "sh_pct_lte": ("sh_index_pct_chg", "<="),
            "sh_pct_gte": ("sh_index_pct_chg", ">="),
        }[req.selector]
        where.append(f"{col} {op} ?")
        params.append(num)
        label = f"{col} {op} {num:g}"
    sql = "SELECT CAST(trade_date AS DATE) AS d FROM fact_market_daily"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY d"
    return [_iso(r["d"]) or "" for r in _rows(con, sql, params)], label


def _cohort_options(con: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for col in ("market_stage", "volume_state", "concentration_state"):
        vals = _rows(
            con,
            f"SELECT DISTINCT {col} AS v FROM fact_market_daily WHERE {col} IS NOT NULL AND {col} <> '' ORDER BY 1",  # noqa: S608
        )
        seen: list[str] = []
        for r in vals:
            v = str(r["v"])
            v = rq.normalize_stage(v) if col == "market_stage" else v
            if v not in seen:
                seen.append(v)
        out[col] = seen
    return out


# --------------------------------------------------------------------------- #
# 区间：每日累计曲线
# --------------------------------------------------------------------------- #
def _range_curve(con: Any, agg: rq.RangeAggregate) -> list[dict[str, Any]]:
    if agg.kind == "stock":
        rows = _rows(
            con,
            """
            SELECT CAST(trade_date AS DATE) AS d, close, pct_chg, amount FROM fact_stock_daily
            WHERE (stock_ts_code = ? OR stock_name = ?)
              AND CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            ORDER BY d
            """,
            [agg.entity_id, agg.entity_name, agg.start, agg.end],
        )
        base = None
        out = []
        for r in rows:
            close = _num(r["close"])
            if base is None and close:
                base = close
            out.append(
                {
                    "date": _iso(r["d"]),
                    "pct_chg": _num(r["pct_chg"]),
                    "cum_pct": None if not (base and close) else round((close / base - 1) * 100, 4),
                    "amount": _num(r["amount"]),
                }
            )
        return out
    codes = list(agg.codes_seen) or [agg.entity_id]
    ph = ",".join("?" for _ in codes)
    rows = _rows(
        con,
        f"""
        SELECT CAST(trade_date AS DATE) AS d, ANY_VALUE(pct_chg) AS pct_chg, ANY_VALUE(amount) AS amount
        FROM fact_sector_daily
        WHERE (sector_ts_code IN ({ph}) OR sector_name = ?)
          AND CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        GROUP BY 1 ORDER BY d
        """,  # noqa: S608
        [*codes, agg.entity_name, agg.start, agg.end],
    )
    cum = 1.0
    out = []
    for r in rows:
        p = _num(r["pct_chg"])
        if p is not None:
            cum *= 1 + p / 100
        out.append({"date": _iso(r["d"]), "pct_chg": p, "cum_pct": round((cum - 1) * 100, 4), "amount": _num(r["amount"])})
    return out



# --------------------------------------------------------------------------- #
# 上证 K 线底座
# --------------------------------------------------------------------------- #
MA_WINDOWS = (5, 10, 20, 60)


def _sh_kline(con: Any, start: str, end: str, entity: str | None = None) -> dict[str, Any]:
    """上证 OHLCV + 周均线 + MA5/10/20/60（收盘价现算，向前预热 60 根）+ 广度/强度副图字段。

    副图字段直接透传：涨家数 advancers（库里没有跌家数，不伪造）、强势股强度 strength_avg_pct 及其
    MA5/MA20（复盘汇口径，非本地现算）、强度成交环比、强度档位、创新高家数。

    只用 ``fact_market_daily``：它同时是交易日历，所以与六轨时间轴逐列对齐。
    MA 在窗口前 N-1 根不足时返回 ``None``，不用短窗均值冒充。
    """
    rows = _rows(
        con,
        """
        SELECT CAST(trade_date AS DATE) AS d, sh_index_open, sh_index_high, sh_index_low, sh_index_close,
               sh_index_volume, sh_index_amount, sh_index_pct_chg, sh_week_ma, sh_deviation_pct,
               total_amount, amount_ma20, market_stage, stage_day, limit_up, limit_down, sh_index_source,
               advancers, strength_avg_pct, strength_ma5_avg_pct, strength_ma20_avg_pct, strength_marginal_pct,
               strength_status, strength_source,
               stock_high_count_20d, stock_high_count_60d, stock_high_count_120d, stock_high_count_1y
        FROM fact_market_daily
        WHERE CAST(trade_date AS DATE) <= CAST(? AS DATE)
        ORDER BY d DESC
        LIMIT (SELECT COUNT(*) FROM fact_market_daily
               WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)) + ?
        """,
        [end, start, end, max(MA_WINDOWS) - 1],
    )
    rows.reverse()
    closes = [_num(r["sh_index_close"]) for r in rows]
    out: list[dict[str, Any]] = []
    for i, r in enumerate(rows):
        d = _iso(r["d"]) or ""
        if d < start:
            continue
        mas: dict[str, float | None] = {}
        for w in MA_WINDOWS:
            window = closes[i - w + 1 : i + 1] if i - w + 1 >= 0 else []
            mas[f"ma{w}"] = round(sum(window) / w, 2) if len(window) == w and all(c is not None for c in window) else None  # type: ignore[arg-type]
        out.append(
            {
                "date": d,
                "open": _num(r["sh_index_open"]),
                "high": _num(r["sh_index_high"]),
                "low": _num(r["sh_index_low"]),
                "close": _num(r["sh_index_close"]),
                "volume": _num(r["sh_index_volume"]),
                "amount": _num(r["sh_index_amount"]),
                "pct_chg": _num(r["sh_index_pct_chg"]),
                "week_ma": _num(r["sh_week_ma"]),
                "deviation_pct": _num(r["sh_deviation_pct"]),
                "total_amount": _num(r["total_amount"]),
                "amount_ma20": _num(r["amount_ma20"]),
                "stage": r.get("market_stage"),
                "stage_day": r.get("stage_day"),
                "limit_up": r.get("limit_up"),
                "limit_down": r.get("limit_down"),
                "advancers": r.get("advancers"),
                "strength_avg_pct": _num(r["strength_avg_pct"]),
                "strength_ma5_pct": _num(r["strength_ma5_avg_pct"]),
                "strength_ma20_pct": _num(r["strength_ma20_avg_pct"]),
                "strength_marginal_pct": _num(r["strength_marginal_pct"]),
                "strength_status": r.get("strength_status"),
                "high_20d": r.get("stock_high_count_20d"),
                "high_60d": r.get("stock_high_count_60d"),
                "high_120d": r.get("stock_high_count_120d"),
                "high_1y": r.get("stock_high_count_1y"),
                **mas,
            }
        )
    overlay = _entity_nav(con, entity, [d["date"] for d in out]) if entity else None
    if overlay:
        for d in out:
            d["entity_pct"] = overlay["pct"].get(d["date"])
            d["entity_nav"] = overlay["nav"].get(d["date"])
    source = next((r.get("sh_index_source") for r in reversed(rows) if r.get("sh_index_source")), None)
    strength_source = next((r.get("strength_source") for r in reversed(rows) if r.get("strength_source")), None)
    return {"index": "上证指数", "code": "sh000001", "source": source, "strength_source": strength_source,
            "entity": ({"id": entity, "name": overlay["name"], "coverage": overlay["coverage"], "note": overlay["note"]} if overlay else None), "start": start, "end": end, "ma_windows": list(MA_WINDOWS), "days": out}

def _entity_nav(con: Any, entity: str, dates: list[str]) -> dict[str, Any] | None:
    """板块区间净值线：用 fact_sector_daily.pct_chg 逐日累乘，起点 1.0。

    板块表没有 OHLC，只能画一条线；缺日不补零，净值在缺口处断开并记入 coverage。
    entity 可以是 sector_ts_code 或 sector_name。
    """
    if not dates:
        return None
    rows = _rows(
        con,
        """
        SELECT CAST(trade_date AS DATE) AS d, sector_name, pct_chg
        FROM fact_sector_daily
        WHERE (sector_ts_code = ? OR sector_name = ?)
          AND CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        ORDER BY d
        """,
        [entity, entity, dates[0], dates[-1]],
    )
    if not rows:
        return None
    pct = {(_iso(r["d"]) or ""): _num(r["pct_chg"]) for r in rows}
    nav: dict[str, float | None] = {}
    cur = 1.0
    for d in dates:
        p = pct.get(d)
        if p is None:
            nav[d] = None
            continue
        cur *= 1 + p / 100
        nav[d] = round(cur, 4)
    covered = sum(1 for d in dates if pct.get(d) is not None)
    return {
        "name": rows[-1]["sector_name"],
        "pct": pct,
        "nav": nav,
        "coverage": round(covered / len(dates), 3),
        "note": "净值 = 区间内 pct_chg 逐日累乘，起点 1.0；缺日断开不补零" + ("" if covered == len(dates) else f"，缺 {len(dates) - covered} 天"),
    }


# --------------------------------------------------------------------------- #
# 连板日历
# --------------------------------------------------------------------------- #
def _limitup_calendar(con: Any, days: int, end: str | None = None) -> dict[str, Any]:
    if not _has_table(con, "fact_limit_advance_daily"):
        raise HTTPException(status_code=503, detail="fact_limit_advance_daily 不存在")
    trading = _trading_days(con, None, end, limit=days + 1)  # 多取一天算首日晋级率
    if not trading:
        raise HTTPException(status_code=404, detail="fact_market_daily 没有交易日")
    start, end = trading[0], trading[-1]

    details_by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in _rows(
        con,
        """
        SELECT CAST(trade_date AS DATE) AS d, stock_ts_code, stock_name, boards, theme, pct_chg,
               CAST(first_limit_date AS DATE) AS first_limit_date
        FROM fact_limit_advance_daily
        WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
        ORDER BY d, boards DESC, stock_name
        """,
        [start, end],
    ):
        details_by_day[_iso(r["d"]) or ""].append(
            {
                "name": r["stock_name"],
                "ts_code": r["stock_ts_code"],
                "boards": int(r["boards"] or 0),
                "theme": r["theme"],
                "pct": _num(r["pct_chg"]),
                "first_limit_date": _iso(r["first_limit_date"]),
            }
        )
    market = {
        _iso(r["d"]): r
        for r in _rows(
            con,
            """
            SELECT CAST(trade_date AS DATE) AS d, limit_up, limit_down, advancers, total_amount,
                   amount_vs_yesterday_pct, market_stage, stage_day, sh_index_pct_chg, volume_state
            FROM fact_market_daily
            WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
            """,
            [start, end],
        )
    }
    leader: dict[str, dict[str, Any]] = {}
    if _has_table(con, "fact_leader_height_daily"):
        leader = {
            _iso(r["d"]): r
            for r in _rows(
                con,
                """
                SELECT CAST(trade_date AS DATE) AS d, height, leader_name, leader_ts_code, limit_times
                FROM fact_leader_height_daily
                WHERE CAST(trade_date AS DATE) BETWEEN CAST(? AS DATE) AND CAST(? AS DATE)
                """,
                [start, end],
            )
        }

    out_days: list[dict[str, Any]] = []
    prev_ladder: dict[int, int] | None = None
    prev_market: dict[str, Any] | None = None
    for d in trading:
        det = details_by_day.get(d, [])
        ladder: dict[int, int] = defaultdict(int)
        theme_counter: dict[str, int] = defaultdict(int)
        for x in det:
            ladder[x["boards"]] += 1
            if x["theme"]:
                theme_counter[x["theme"]] += 1
        ladder_d = dict(sorted(ladder.items()))
        # 晋级率：今日 k 板数 / 昨日 (k-1) 板数。昨日 1 板数库里没有（表只收 2 板起），
        # 所以 2 板晋级率算不出来，如实给 None 而不是用涨停家数冒充分母。
        promotion: dict[int, float | None] = {}
        promotion_estimated: list[int] = []
        m = market.get(d)
        if prev_ladder is not None:
            for k, n in ladder_d.items():
                denom = prev_ladder.get(k - 1)
                if k == 2 and prev_market is not None and prev_market.get("limit_up") is not None:
                    # 昨日首板数 ≈ 昨日涨停家数 − 昨日连板家数。是估算，前端必须标出来。
                    denom = int(prev_market["limit_up"]) - sum(prev_ladder.values())
                    promotion_estimated.append(2)
                promotion[k] = None if not denom or denom <= 0 else round(n / denom * 100, 1)
        ld = leader.get(d)
        top_themes = sorted(theme_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        out_days.append(
            {
                "trade_date": d,
                "ladder": ladder_d,
                "promotion_rate": promotion,
                "promotion_estimated": promotion_estimated,
                # The ledger has no completeness marker: no rows cannot prove zero.
                "data_status": "available" if det else "missing",
                "total": len(det) if det else None,
                "high_boards": sum(n for k, n in ladder_d.items() if k >= 3) if det else None,
                "max_boards": max(ladder_d) if ladder_d else None,
                "details": det,
                "top_themes": [{"theme": t, "count": n} for t, n in top_themes],
                "market": None
                if m is None
                else {
                    "limit_up": m.get("limit_up"),
                    "limit_down": m.get("limit_down"),
                    "advancers": m.get("advancers"),
                    "amount": _num(m.get("total_amount")),
                    "amount_chg_pct": _num(m.get("amount_vs_yesterday_pct")),
                    "stage": m.get("market_stage"),
                    "stage_day": m.get("stage_day"),
                    "sh_pct": _num(m.get("sh_index_pct_chg")),
                    "volume_state": m.get("volume_state"),
                },
                "leader": None
                if ld is None
                else {"height": int(ld.get("height") or 0), "name": ld.get("leader_name"), "ts_code": ld.get("leader_ts_code")},
            }
        )
        prev_ladder = ladder_d if det else None
        prev_market = m
    out_days = out_days[-days:]
    covered = [day for day in out_days if day["total"] is not None]
    complete = bool(out_days) and len(covered) == len(out_days)
    max_boards_day = max(covered, key=lambda x: x["max_boards"]) if covered else None
    return {
        "start": out_days[0]["trade_date"] if out_days else None,
        "end": out_days[-1]["trade_date"] if out_days else None,
        "days": out_days,
        "stats": {
            "trading_days": len(out_days),
            "covered_days": len(covered),
            "avg_total": round(sum(x["total"] for x in out_days) / len(out_days), 1) if complete else None,
            "avg_max_boards": round(sum(x["max_boards"] for x in out_days) / len(out_days), 2) if complete else None,
            "max_boards": max_boards_day["max_boards"] if max_boards_day else None,
            "max_boards_date": max_boards_day["trade_date"] if max_boards_day else None,
        },
    }


# --------------------------------------------------------------------------- #
# 注册
# --------------------------------------------------------------------------- #
def register_river_routes(app: FastAPI, *, market_db_path: Path | None = None) -> None:
    """把长河 / 连板端点挂到 FastAPI 实例上。``market_db_path`` 缺省走 paths.default_market_db_path()。"""

    def db() -> Path:
        if market_db_path is not None:
            return Path(market_db_path)
        from intelligence.paths import default_market_db_path

        return Path(default_market_db_path())

    from intelligence.api.river_daily_routes import register_daily_river_routes

    register_daily_river_routes(app, market_db_path=market_db_path)

    @app.get("/api/river/meta")
    def river_meta(days: int = Query(default=90, ge=5, le=400)) -> dict[str, Any]:
        con = _connect(db())
        try:
            trading = _trading_days(con, None, None, limit=days)
            latest = trading[-1] if trading else None
            defaults = _entities(con, latest, "", 12) if latest else []
            default_entity = next((e for e in defaults if e["name"] == DEFAULT_ENTITY_FALLBACK), defaults[0] if defaults else None)
            return {
                "latest": latest,
                "trading_days": trading,
                "default_entity": default_entity,
                "hot_entities": defaults,
                "tracks": [{"key": k, "label": v} for k, v in TRACK_LABELS.items()],
                "coverage": _track_coverage(con),
                "cohort_options": _cohort_options(con),
            }
        finally:
            con.close()

    @app.get("/api/river/entities")
    def river_entities(q: str = "", as_of: str | None = None, limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        con = _connect(db())
        try:
            day = as_of or (_trading_days(con, None, None, limit=1) or [None])[0]
            if not day:
                return {"as_of": None, "items": []}
            return {"as_of": day, "items": _entities(con, day, q, limit)}
        finally:
            con.close()

    @app.get("/api/river/timeline")
    def river_timeline(entity: str, start: str, end: str) -> dict[str, Any]:
        if start > end:
            raise HTTPException(status_code=422, detail="start 晚于 end")
        con = _connect(db())
        try:
            return _timeline(con, entity, start, end)
        finally:
            con.close()

    @app.get("/api/river/slice")
    def river_slice(
        as_of: str,
        entity: str,
        cutoff: str | None = None,
        require_strict: bool = False,
        allow_hindsight: bool = False,
    ) -> dict[str, Any]:
        try:
            sl = river_svc.slice_river(
                as_of,
                entity,
                knowledge_cutoff=cutoff,
                require_strict=require_strict,
                allow_hindsight=allow_hindsight,
                db_path=db(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        payload = sl.to_dict()
        payload["track_labels"] = TRACK_LABELS
        return payload

    @app.get("/api/river/scan")
    def river_scan(
        as_of: str,
        mode: Literal["all", "dislocation"] = "all",
        min_coverage_90d: int = Query(default=3, ge=0),
        max_market_pctile: float = Query(default=0.4, ge=0, le=1),
    ) -> dict[str, Any]:
        try:
            if mode == "dislocation":
                rows = rq.find_dislocation(
                    as_of, min_coverage_90d=min_coverage_90d, max_market_pctile=max_market_pctile, db_path=db()
                )
            else:
                rows = rq.scan_cross_section(as_of, db_path=db())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"as_of": as_of, "mode": mode, "count": len(rows), "rows": [r.to_dict() for r in rows]}

    @app.post("/api/river/cohort")
    def river_cohort(req: CohortRequest) -> dict[str, Any]:
        con = _connect(db())
        try:
            dates, label = _select_dates(con, req)
        finally:
            con.close()
        if not dates:
            return {"selector_label": label, "dates": [], "report": None, "note": "条件没有筛出任何交易日"}
        try:
            rep = rq.cohort_compare(dates, feature=req.feature, db_path=db())
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"selector_label": label, "dates": dates, "report": rep.to_dict()}

    @app.get("/api/river/range")
    def river_range(
        entity: str,
        start: str,
        end: str,
        kind: Literal["stock", "sector"] | None = None,
        require_complete: bool = False,
    ) -> dict[str, Any]:
        if start > end:
            raise HTTPException(status_code=422, detail="start 晚于 end")
        try:
            agg = rq.range_aggregate(start, end, entity, kind=kind, require_complete=require_complete, db_path=db())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        con = _connect(db())
        try:
            curve = _range_curve(con, agg)
        finally:
            con.close()
        payload = agg.to_dict()
        payload["curve"] = curve
        return payload

    @app.get("/api/river/kline")
    def river_kline(start: str, end: str, entity: str | None = None) -> dict[str, Any]:
        if start > end:
            raise HTTPException(status_code=422, detail="start 晚于 end")
        con = _connect(db())
        try:
            return _sh_kline(con, start, end, entity)
        finally:
            con.close()

    @app.get("/api/limitup/calendar")
    def limitup_calendar(days: int = Query(default=60, ge=5, le=250), end: date | None = None) -> dict[str, Any]:
        con = _connect(db())
        try:
            return _limitup_calendar(con, days, end.isoformat() if end else None)
        finally:
            con.close()
