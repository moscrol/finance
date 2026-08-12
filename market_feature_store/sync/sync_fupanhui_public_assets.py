"""同步复盘会公开 API 增量资产到 DuckDB（及可选知识库 raw 笔记）。

全部走 api_get_public，不依赖 CDP / 登录。失败按子任务隔离：
单个接口挂了不影响其它；全部失败才让调用方视为步骤失败。

子任务与落点：
  historical_mapping → fact_historical_mapping
  leader_height      → fact_leader_height_daily（一次回填 height_trend 全序列）
  global_market      → fact_global_index_daily / fact_global_stock_daily
  dragon             → fact_dragon_tiger_daily
  regulation         → fact_regulation_event_daily / fact_regulation_pool_daily
  core_stocks        → fact_core_stock_daily
  auction            → fact_auction_stock_daily
  events             → fact_event_daily
  research_catalog   → fact_research_report_catalog
  fundamentals       → fact_theme_fundamental_doc + 可选 KB markdown
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from ..db import connect, init_db
from ..sources import fupanhui_source as fs

SOURCE_PREFIX = "fupanhui:public-api"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _num(val):
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _int(val):
    n = _num(val)
    return int(n) if n is not None else None


def _date_text(val) -> str | None:
    if not val:
        return None
    s = str(val).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s[:10] if len(s) >= 10 else s


def _executemany(sql: str, rows: list[tuple]) -> int:
    if not rows:
        return 0
    init_db()
    con = connect()
    try:
        con.executemany(sql, rows)
    finally:
        con.close()
    return len(rows)


def sync_historical_mapping(trade_date: str) -> dict:
    data = fs.get_historical_mapping(trade_date)
    source_date = _date_text(data.get("source_date") or trade_date)
    now = _now()
    source = f"{SOURCE_PREFIX}/reviews/historical-mapping"
    rows = []
    for item in data.get("similar_days") or []:
        if not isinstance(item, dict):
            continue
        similar = _date_text(item.get("date") or item.get("trade_date"))
        if not source_date or not similar:
            continue
        rows.append((
            source_date,
            similar,
            _num(item.get("similarity")),
            item.get("external_cycle"),
            _int(item.get("external_cycle_day") or item.get("cycle_day")),
            item.get("summary"),
            source,
            now,
        ))
    written = _executemany(
        """
        INSERT INTO fact_historical_mapping
            (source_date, similar_date, similarity, external_cycle, cycle_day,
             summary, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT (source_date, similar_date) DO UPDATE SET
            similarity = excluded.similarity,
            external_cycle = excluded.external_cycle,
            cycle_day = excluded.cycle_day,
            summary = excluded.summary,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return {"rows": written, "source_date": source_date}


def sync_leader_height(trade_date: str) -> dict:
    data = fs.get_leader_ladder(trade_date)
    now = _now()
    source = f"{SOURCE_PREFIX}/reviews/leader-ladder"
    rows = []
    for point in data.get("height_trend") or []:
        if not isinstance(point, dict):
            continue
        td = _date_text(point.get("trade_date"))
        if not td:
            continue
        leader = point.get("leader_stock") if isinstance(point.get("leader_stock"), dict) else {}
        rows.append((
            td,
            _int(point.get("height")),
            leader.get("ts_code"),
            leader.get("name"),
            _int(leader.get("limit_times")),
            _num(leader.get("fd_amount")),
            str(leader.get("first_limit_time") or "") or None,
            source,
            now,
        ))
    written = _executemany(
        """
        INSERT INTO fact_leader_height_daily
            (trade_date, height, leader_ts_code, leader_name, limit_times,
             fd_amount, first_limit_time, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        ON CONFLICT (trade_date) DO UPDATE SET
            height = excluded.height,
            leader_ts_code = excluded.leader_ts_code,
            leader_name = excluded.leader_name,
            limit_times = excluded.limit_times,
            fd_amount = excluded.fd_amount,
            first_limit_time = excluded.first_limit_time,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return {"rows": written, "requested_date": trade_date}


def sync_global_market(trade_date: str) -> dict:
    data = fs.get_global_market(trade_date)
    now = _now()
    source = f"{SOURCE_PREFIX}/reviews/global-market"
    req_date = _date_text(data.get("trade_date") or trade_date)
    src_date = _date_text(data.get("source_trade_date") or req_date)
    data_stage = data.get("data_stage")
    index_rows = []
    for item in data.get("markets") or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        if not code or not req_date:
            continue
        index_rows.append((
            req_date,
            src_date,
            code,
            item.get("name"),
            item.get("market_group"),
            _num(item.get("close")),
            _num(item.get("pct_chg")),
            data_stage,
            source,
            now,
        ))
    stock_rows = []
    for item in data.get("core_stocks") or []:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts_code") or "").strip()
        if not ts or not req_date:
            continue
        business = item.get("business")
        if isinstance(business, str) and len(business) > 500:
            business = business[:500]
        stock_rows.append((
            req_date,
            src_date,
            ts,
            item.get("name_cn"),
            item.get("name_en"),
            item.get("exchange"),
            _num(item.get("close")),
            _num(item.get("pct_chg")),
            _num(item.get("pct_chg_5d")),
            _num(item.get("market_cap_usd")),
            business,
            item.get("industry_position"),
            source,
            now,
        ))
    n_idx = _executemany(
        """
        INSERT INTO fact_global_index_daily
            (trade_date, source_trade_date, code, name, market_group,
             close, pct_chg, data_stage, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (trade_date, code) DO UPDATE SET
            source_trade_date = excluded.source_trade_date,
            name = excluded.name,
            market_group = excluded.market_group,
            close = excluded.close,
            pct_chg = excluded.pct_chg,
            data_stage = excluded.data_stage,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        index_rows,
    )
    n_stk = _executemany(
        """
        INSERT INTO fact_global_stock_daily
            (trade_date, source_trade_date, ts_code, name_cn, name_en, exchange,
             close, pct_chg, pct_chg_5d, market_cap_usd, business,
             industry_position, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (trade_date, ts_code) DO UPDATE SET
            source_trade_date = excluded.source_trade_date,
            name_cn = excluded.name_cn,
            name_en = excluded.name_en,
            exchange = excluded.exchange,
            close = excluded.close,
            pct_chg = excluded.pct_chg,
            pct_chg_5d = excluded.pct_chg_5d,
            market_cap_usd = excluded.market_cap_usd,
            business = excluded.business,
            industry_position = excluded.industry_position,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        stock_rows,
    )
    return {
        "index_rows": n_idx,
        "stock_rows": n_stk,
        "source_trade_date": src_date,
    }


def sync_dragon(trade_date: str) -> dict:
    data = fs.get_dragon_list(trade_date)
    td = _date_text(data.get("trade_date") or trade_date)
    now = _now()
    source = f"{SOURCE_PREFIX}/data/dragon/list"
    rows = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts_code") or "").strip()
        if not ts or not td:
            continue
        rows.append((
            td,
            ts,
            item.get("name"),
            _num(item.get("close")),
            _num(item.get("pct_change")),
            _num(item.get("turnover_rate")),
            _num(item.get("amount")),
            _num(item.get("l_buy")),
            _num(item.get("l_sell")),
            _num(item.get("l_amount")),
            _num(item.get("net_amount")),
            _num(item.get("net_rate")),
            _num(item.get("amount_rate")),
            item.get("reason"),
            source,
            now,
        ))
    written = _executemany(
        """
        INSERT INTO fact_dragon_tiger_daily
            (trade_date, stock_ts_code, stock_name, close, pct_change, turnover_rate,
             amount, l_buy, l_sell, l_amount, net_amount, net_rate, amount_rate,
             reason, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
            stock_name = excluded.stock_name,
            close = excluded.close,
            pct_change = excluded.pct_change,
            turnover_rate = excluded.turnover_rate,
            amount = excluded.amount,
            l_buy = excluded.l_buy,
            l_sell = excluded.l_sell,
            l_amount = excluded.l_amount,
            net_amount = excluded.net_amount,
            net_rate = excluded.net_rate,
            amount_rate = excluded.amount_rate,
            reason = excluded.reason,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return {"rows": written}


def sync_regulation(trade_date: str) -> dict:
    logs = fs.get_regulation_logs(trade_date)
    pool = fs.get_regulation_pool(trade_date)
    now = _now()
    log_date = _date_text(logs.get("effective_date") or trade_date)
    event_rows = []
    for item in logs.get("items") or []:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts_code") or "").strip()
        if not ts or not log_date:
            continue
        event_rows.append((
            log_date,
            ts,
            item.get("ts_name") or item.get("name"),
            _date_text(item.get("start_date")),
            _date_text(item.get("end_date")),
            _int(item.get("days_remaining_trading")),
            item.get("status_type"),
            item.get("event_type"),
            item.get("event_types"),
            item.get("leader_plate"),
            f"{SOURCE_PREFIX}/regulation/logs",
            now,
        ))
    n_evt = _executemany(
        """
        INSERT INTO fact_regulation_event_daily
            (effective_date, stock_ts_code, stock_name, start_date, end_date,
             days_remaining_trading, status_type, event_type, event_types,
             leader_plate, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (effective_date, stock_ts_code) DO UPDATE SET
            stock_name = excluded.stock_name,
            start_date = excluded.start_date,
            end_date = excluded.end_date,
            days_remaining_trading = excluded.days_remaining_trading,
            status_type = excluded.status_type,
            event_type = excluded.event_type,
            event_types = excluded.event_types,
            leader_plate = excluded.leader_plate,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        event_rows,
    )
    pool_date = _date_text(pool.get("effective_date") or trade_date)
    pool_rows = []
    waiting_codes = set()
    # pool 接口把安全池放 items；waiting 若另有字段也收
    waiting = pool.get("waiting_items") or pool.get("waiting") or []
    if isinstance(waiting, list):
        for item in waiting:
            if isinstance(item, dict) and item.get("ts_code"):
                waiting_codes.add(str(item["ts_code"]))
                pool_rows.append(_pool_row(item, pool_date, "waiting", now))
    for item in pool.get("items") or []:
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts_code") or "").strip()
        if not ts or ts in waiting_codes:
            continue
        pool_rows.append(_pool_row(item, pool_date, "safe", now))
    pool_rows = [r for r in pool_rows if r]
    n_pool = _executemany(
        """
        INSERT INTO fact_regulation_pool_daily
            (effective_date, stock_ts_code, stock_name, pool_status, close,
             pct_chg_10d, safe_space_10d, safe_days_10d, pct_chg_30d,
             safe_space_30d, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (effective_date, stock_ts_code) DO UPDATE SET
            stock_name = excluded.stock_name,
            pool_status = excluded.pool_status,
            close = excluded.close,
            pct_chg_10d = excluded.pct_chg_10d,
            safe_space_10d = excluded.safe_space_10d,
            safe_days_10d = excluded.safe_days_10d,
            pct_chg_30d = excluded.pct_chg_30d,
            safe_space_30d = excluded.safe_space_30d,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        pool_rows,
    )
    return {"event_rows": n_evt, "pool_rows": n_pool}


def _pool_row(item: dict, effective_date: str | None, status: str, now: str):
    ts = str(item.get("ts_code") or "").strip()
    if not ts or not effective_date:
        return None
    return (
        effective_date,
        ts,
        item.get("name") or item.get("ts_name"),
        status,
        _num(item.get("close")),
        _num(item.get("pct_chg_10d")),
        _num(item.get("safe_space_10d")),
        _int(item.get("safe_days_10d")),
        _num(item.get("pct_chg_30d")),
        _num(item.get("safe_space_30d")),
        f"{SOURCE_PREFIX}/regulation/pool",
        now,
    )


def sync_core_stocks(trade_date: str) -> dict:
    data = fs.get_core_stocks(trade_date)
    td = _date_text(data.get("trade_date") or trade_date)
    now = _now()
    source = f"{SOURCE_PREFIX}/core-stocks/list"
    rows = []
    for idx, item in enumerate(data.get("stocks") or [], start=1):
        if not isinstance(item, dict):
            continue
        ts = str(item.get("ts_code") or "").strip()
        if not ts or not td:
            continue
        rows.append((
            td,
            idx,
            ts,
            item.get("name"),
            _num(item.get("close")),
            _num(item.get("pct_chg") if item.get("pct_chg") is not None else item.get("pct_change")),
            _num(item.get("amount")),
            _num(item.get("circ_mv")),
            item.get("sw_l1_name"),
            item.get("leader_plate"),
            _num(item.get("fund_flow_today")),
            _num(item.get("gain_5d")),
            _num(item.get("gain_10d")),
            source,
            now,
        ))
    written = _executemany(
        """
        INSERT INTO fact_core_stock_daily
            (trade_date, rank, stock_ts_code, stock_name, close, pct_chg, amount,
             circ_mv, sw_l1_name, leader_plate, fund_flow_today, gain_5d, gain_10d,
             source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (trade_date, stock_ts_code) DO UPDATE SET
            rank = excluded.rank,
            stock_name = excluded.stock_name,
            close = excluded.close,
            pct_chg = excluded.pct_chg,
            amount = excluded.amount,
            circ_mv = excluded.circ_mv,
            sw_l1_name = excluded.sw_l1_name,
            leader_plate = excluded.leader_plate,
            fund_flow_today = excluded.fund_flow_today,
            gain_5d = excluded.gain_5d,
            gain_10d = excluded.gain_10d,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return {"rows": written}


def sync_auction(trade_date: str) -> dict:
    data = fs.get_auction_dashboard(trade_date)
    td = _date_text(data.get("trade_date") or trade_date)
    now = _now()
    source = f"{SOURCE_PREFIX}/data/auction/dashboard"
    rows = []
    for panel in data.get("panels") or []:
        if not isinstance(panel, dict):
            continue
        key = str(panel.get("key") or "").strip()
        label = panel.get("label")
        for item in panel.get("stocks") or []:
            if not isinstance(item, dict):
                continue
            ts = str(item.get("ts_code") or "").strip()
            if not ts or not td or not key:
                continue
            rows.append((
                td,
                key,
                label,
                ts,
                item.get("name"),
                _num(item.get("auction_pct")),
                _num(item.get("pct_chg")),
                _num(item.get("auction_amount")),
                _num(item.get("day_amount")),
                _int(item.get("limit_seq")),
                item.get("leader_plate"),
                source,
                now,
            ))
    written = _executemany(
        """
        INSERT INTO fact_auction_stock_daily
            (trade_date, panel_key, panel_label, stock_ts_code, stock_name,
             auction_pct, pct_chg, auction_amount, day_amount, limit_seq,
             leader_plate, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (trade_date, panel_key, stock_ts_code) DO UPDATE SET
            panel_label = excluded.panel_label,
            stock_name = excluded.stock_name,
            auction_pct = excluded.auction_pct,
            pct_chg = excluded.pct_chg,
            auction_amount = excluded.auction_amount,
            day_amount = excluded.day_amount,
            limit_seq = excluded.limit_seq,
            leader_plate = excluded.leader_plate,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return {"rows": written}


def sync_events(trade_date: str) -> dict:
    now = _now()
    rows = []
    timeline = fs.get_news_events_timeline(trade_date)
    td = _date_text(timeline.get("date") or trade_date)
    for item in timeline.get("items") or []:
        row = _event_row(item, td, is_future=False, now=now)
        if row:
            rows.append(row)
    future = fs.get_news_events_future()
    for item in future.get("items") or []:
        event_date = _date_text(item.get("date") or item.get("event_date"))
        row = _event_row(item, event_date, is_future=True, now=now)
        if row:
            rows.append(row)
    written = _executemany(
        """
        INSERT INTO fact_event_daily
            (event_date, event_id, title, content, importance, event_type,
             source_types, sectors, is_future, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (event_date, event_id) DO UPDATE SET
            title = excluded.title,
            content = excluded.content,
            importance = excluded.importance,
            event_type = excluded.event_type,
            source_types = excluded.source_types,
            sectors = excluded.sectors,
            is_future = excluded.is_future,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return {"rows": written}


def _event_row(item: dict, event_date: str | None, *, is_future: bool, now: str):
    if not isinstance(item, dict) or not event_date:
        return None
    event_id = str(
        item.get("id") or item.get("article_id") or item.get("title") or ""
    ).strip()
    if not event_id:
        return None
    sectors = item.get("sectors") or item.get("themes") or []
    return (
        event_date,
        event_id[:180],
        item.get("title"),
        item.get("content"),
        _int(item.get("importance_level") if item.get("importance_level") is not None else item.get("grade")),
        item.get("event_type"),
        _json_text(item.get("source_types")),
        _json_text(sectors),
        is_future,
        f"{SOURCE_PREFIX}/news/events",
        now,
    )


def sync_research_catalog(page_size: int = 50, max_pages: int = 20) -> dict:
    now = _now()
    source = f"{SOURCE_PREFIX}/reports/list"
    rows = []
    total = None
    for page in range(1, max_pages + 1):
        data = fs.get_reports_page(page=page, page_size=page_size)
        if total is None:
            total = _int(data.get("total"))
        items = data.get("items") or []
        if not items:
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            rid = item.get("id")
            if rid is None:
                continue
            stocks = item.get("stocks") or []
            names = []
            for s in stocks:
                if isinstance(s, dict):
                    names.append(str(s.get("name") or s.get("stock_name") or "").strip())
                else:
                    names.append(str(s).strip())
            rows.append((
                int(rid),
                item.get("title"),
                _date_text(item.get("report_date")),
                item.get("report_type"),
                bool(item.get("is_hot")),
                _json_text(item.get("sector_tags") or []),
                _json_text(item.get("concept_tags") or []),
                _int(item.get("stock_count") if item.get("stock_count") is not None else len(names)),
                _json_text([n for n in names if n]),
                str(item.get("created_at") or "") or None,
                source,
                now,
            ))
        if total is not None and len(rows) >= total:
            break
        if len(items) < page_size:
            break
    written = _executemany(
        """
        INSERT INTO fact_research_report_catalog
            (report_id, title, report_date, report_type, is_hot, sector_tags,
             concept_tags, stock_count, stocks, created_at, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (report_id) DO UPDATE SET
            title = excluded.title,
            report_date = excluded.report_date,
            report_type = excluded.report_type,
            is_hot = excluded.is_hot,
            sector_tags = excluded.sector_tags,
            concept_tags = excluded.concept_tags,
            stock_count = excluded.stock_count,
            stocks = excluded.stocks,
            created_at = excluded.created_at,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return {"rows": written, "listed_total": total}


def _kb_root() -> Path | None:
    raw = os.environ.get("KNOWLEDGE_BASE_ROOT") or os.environ.get("FINANCE_KB_ROOT")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() else None


def _slug(title: str, pk: int) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "-", title).strip("-")
    cleaned = cleaned[:60] or "untitled"
    return f"{pk}-{cleaned}"


def _write_fundamental_note(kb_root: Path, detail: dict) -> str | None:
    pk = detail.get("document_pk")
    if pk is None:
        return None
    title = str(detail.get("title") or f"fundamental-{pk}")
    judgement = detail.get("core_judgement") if isinstance(detail.get("core_judgement"), dict) else {}
    themes = detail.get("linked_themes") or []
    sectors = detail.get("linked_sectors") or []
    theme_names = [
        t.get("theme_name") for t in themes if isinstance(t, dict) and t.get("theme_name")
    ]
    sector_names = [
        s.get("sector_name") for s in sectors if isinstance(s, dict) and s.get("sector_name")
    ]
    out_dir = kb_root / "wiki" / "raw" / "fupanhui-fundamentals"
    out_dir.mkdir(parents=True, exist_ok=True)
    rel = f"wiki/raw/fupanhui-fundamentals/{_slug(title, int(pk))}.md"
    path = kb_root / rel
    overview = detail.get("industry_overview") if isinstance(detail.get("industry_overview"), dict) else {}
    companies = overview.get("companies") or []
    chain = overview.get("chain_segments") or []
    catalysts = detail.get("catalyst_timeline") or []
    lines = [
        "---",
        f'title: "{title.replace(chr(34), "")}"',
        'source_type: "fupanhui_fundamentals"',
        'evidence_layer: "L1"',
        'update_type: "report_context"',
        "graph_only: true",
        f"document_pk: {int(pk)}",
        f'produced_at: "{detail.get("produced_at") or ""}"',
        f'workflow_name: "{detail.get("workflow_name") or ""}"',
        f"linked_themes: {json.dumps(theme_names, ensure_ascii=False)}",
        f"linked_sectors: {json.dumps(sector_names, ensure_ascii=False)}",
        "---",
        "",
        f"# {title}",
        "",
        "> 复盘会题材挖掘公开接口。默认 `graph_only` / `report_context`，",
        "> 不写实体正文；公司名单只作 theme-radar 暴露线索。",
        "",
        "## 核心判断",
        "",
        judgement.get("judgement_text") or judgement.get("core_theme") or "",
        "",
        "### 验证点",
        "",
        judgement.get("verification_points") or "",
        "",
        "## 产业链分段",
        "",
    ]
    for seg in chain:
        if not isinstance(seg, dict):
            continue
        lines.append(
            f"- **{seg.get('chain_stage') or ''} / {seg.get('sub_segment_product') or ''}** "
            f"价值占比 {seg.get('value_share') or '-'}，毛利 {seg.get('gross_margin_level') or '-'}。"
            f"{seg.get('core_features') or ''}"
        )
    lines.extend(["", "## 公司暴露（graph_only）", ""])
    for co in companies:
        if not isinstance(co, dict):
            continue
        lines.append(
            f"- {co.get('company_name') or ''} `{co.get('stock_code') or ''}` "
            f"[{co.get('chain_segment') or ''}/{co.get('industry_relation') or ''}] "
            f"{co.get('core_feature_values') or ''}"
        )
    lines.extend(["", "## 催化时间线", ""])
    for ev in catalysts:
        if not isinstance(ev, dict):
            continue
        lines.append(
            f"- {ev.get('expected_date_text') or ''} {ev.get('event_name') or ''}："
            f"{ev.get('possible_impact') or ''}"
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return rel


def sync_fundamentals(*, sleep: float = 0.15, kb_root: Path | None = None) -> dict:
    listing = fs.get_fundamentals_list(limit=100, offset=0)
    items = listing.get("items") or []
    now = _now()
    source = f"{SOURCE_PREFIX}/topics/fundamentals"
    kb = kb_root if kb_root is not None else _kb_root()
    rows = []
    written_notes = 0
    for item in items:
        if not isinstance(item, dict) or item.get("document_pk") is None:
            continue
        pk = int(item["document_pk"])
        try:
            detail = fs.get_fundamentals_detail(pk)
        except Exception:
            detail = item
        if not isinstance(detail, dict):
            detail = item
        judgement = detail.get("core_judgement")
        if isinstance(judgement, dict):
            core_theme = judgement.get("core_theme") or judgement.get("judgement_text")
            verification = judgement.get("verification_points")
        else:
            core_theme = judgement if isinstance(judgement, str) else item.get("core_judgement")
            verification = item.get("verification_points")
        kb_path = None
        if kb is not None:
            kb_path = _write_fundamental_note(kb, detail)
            if kb_path:
                written_notes += 1
        rows.append((
            pk,
            detail.get("title") or item.get("title"),
            str(detail.get("produced_at") or item.get("produced_at") or "") or None,
            detail.get("workflow_name") or item.get("workflow_name"),
            detail.get("analysis_type") or item.get("analysis_type"),
            core_theme,
            verification,
            _json_text(detail.get("linked_themes") or item.get("linked_themes") or []),
            _json_text(detail.get("linked_sectors") or item.get("linked_sectors") or []),
            kb_path,
            source,
            now,
        ))
        if sleep:
            time.sleep(sleep)
    n = _executemany(
        """
        INSERT INTO fact_theme_fundamental_doc
            (document_pk, title, produced_at, workflow_name, analysis_type,
             core_theme, verification_points, linked_themes, linked_sectors,
             kb_path, source, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT (document_pk) DO UPDATE SET
            title = excluded.title,
            produced_at = excluded.produced_at,
            workflow_name = excluded.workflow_name,
            analysis_type = excluded.analysis_type,
            core_theme = excluded.core_theme,
            verification_points = excluded.verification_points,
            linked_themes = excluded.linked_themes,
            linked_sectors = excluded.linked_sectors,
            kb_path = COALESCE(excluded.kb_path, fact_theme_fundamental_doc.kb_path),
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        rows,
    )
    return {
        "rows": n,
        "listed_total": listing.get("total"),
        "kb_notes": written_notes,
        "kb_root": str(kb) if kb else None,
    }


def sync_summary_keywords(trade_date: str) -> dict:
    """只补 fact_market_daily.summary_keywords，不改其它市场字段。"""
    from .sync_fupanhui_market_daily import _keywords_json

    data = fs.get_review_summary(trade_date)
    keywords = _keywords_json(data if isinstance(data, dict) else {})
    init_db()
    con = connect()
    try:
        con.execute(
            "ALTER TABLE fact_market_daily ADD COLUMN IF NOT EXISTS summary_keywords TEXT"
        )
        exists = con.execute(
            "SELECT 1 FROM fact_market_daily WHERE trade_date = ?",
            [trade_date],
        ).fetchone()
        if not exists:
            return {"keywords": keywords, "updated": False, "rows": 0}
        con.execute(
            """
            UPDATE fact_market_daily
            SET summary_keywords = ?,
                updated_at = ?
            WHERE trade_date = ?
            """,
            [keywords, _now(), trade_date],
        )
    finally:
        con.close()
    return {"keywords": keywords, "updated": True, "rows": 1 if keywords else 0}


DAILY_SYNCS = (
    ("keywords", sync_summary_keywords),
    ("historical_mapping", sync_historical_mapping),
    ("leader_height", sync_leader_height),
    ("global_market", sync_global_market),
    ("dragon", sync_dragon),
    ("regulation", sync_regulation),
    ("core_stocks", sync_core_stocks),
    ("auction", sync_auction),
    ("events", sync_events),
)

ONCE_SYNCS = (
    ("research_catalog", lambda _td: sync_research_catalog()),
    ("fundamentals", lambda _td: sync_fundamentals()),
)

ASSET_SYNCS = DAILY_SYNCS + ONCE_SYNCS

_COVERAGE_SQL = {
    "keywords": (
        "SELECT COUNT(*) FROM fact_market_daily "
        "WHERE trade_date = ? AND summary_keywords IS NOT NULL AND summary_keywords <> ''"
    ),
    "historical_mapping": (
        "SELECT COUNT(*) FROM fact_historical_mapping WHERE source_date = ?"
    ),
    "leader_height": (
        "SELECT COUNT(*) FROM fact_leader_height_daily WHERE trade_date = ?"
    ),
    "global_market": (
        "SELECT COUNT(*) FROM fact_global_index_daily WHERE trade_date = ?"
    ),
    "dragon": (
        "SELECT COUNT(*) FROM fact_dragon_tiger_daily WHERE trade_date = ?"
    ),
    "regulation": (
        "SELECT COUNT(*) FROM fact_regulation_pool_daily WHERE effective_date = ?"
    ),
    "core_stocks": (
        "SELECT COUNT(*) FROM fact_core_stock_daily WHERE trade_date = ?"
    ),
    "auction": (
        "SELECT COUNT(*) FROM fact_auction_stock_daily WHERE trade_date = ?"
    ),
    "events": (
        "SELECT COUNT(*) FROM fact_event_daily WHERE event_date = ? AND is_future IS NOT TRUE"
    ),
}

_PIPELINE = "fupanhui-public-assets"


def _has_rows(con, name: str, trade_date: str) -> bool:
    sql = _COVERAGE_SQL.get(name)
    if not sql:
        return False
    try:
        row = con.execute(sql, [trade_date]).fetchone()
    except Exception:  # noqa: BLE001
        return False
    return bool(row and row[0])


def _ops_done(con, trade_date: str, step: str) -> bool:
    try:
        row = con.execute(
            """
            SELECT status FROM ops_pipeline_run_daily
            WHERE trade_date = ? AND pipeline = ? AND step = ?
            """,
            [trade_date, _PIPELINE, step],
        ).fetchone()
    except Exception:  # noqa: BLE001
        return False
    return bool(row and row[0] in {"complete", "empty"})


def _mark_ops(trade_date: str, step: str, status: str, row_count: int, message: str | None = None) -> None:
    init_db()
    con = connect()
    try:
        con.execute(
            """
            INSERT INTO ops_pipeline_run_daily
                (trade_date, pipeline, step, status, row_count, message, source, finished_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT (trade_date, pipeline, step) DO UPDATE SET
                status = excluded.status,
                row_count = excluded.row_count,
                message = excluded.message,
                source = excluded.source,
                finished_at = excluded.finished_at
            """,
            [
                trade_date,
                _PIPELINE,
                step,
                status,
                int(row_count),
                message,
                f"{SOURCE_PREFIX}/{step}",
                _now(),
            ],
        )
    finally:
        con.close()


def _result_row_count(result) -> int:
    if not isinstance(result, dict):
        return 0
    for key in ("rows", "index_rows", "event_rows", "pool_rows", "stock_rows"):
        val = result.get(key)
        if isinstance(val, int) and val > 0:
            return val
    if result.get("updated"):
        return 1
    return 0


def align_bounds() -> tuple[str, str]:
    """其它复盘会日表的共同窗口：新高/涨停热度起点 → market_daily 终点。"""
    init_db()
    con = connect()
    try:
        row = con.execute(
            """
            SELECT
              COALESCE(
                (SELECT MIN(trade_date) FROM fact_stock_high_daily),
                (SELECT MIN(trade_date) FROM fact_market_daily)
              ),
              (SELECT MAX(trade_date) FROM fact_market_daily)
            """
        ).fetchone()
    finally:
        con.close()
    if not row or not row[0] or not row[1]:
        raise RuntimeError("无法从 fact_market_daily / fact_stock_high_daily 推断对齐窗口")
    return str(row[0]), str(row[1])


def calendar_dates(start_date: str, end_date: str) -> list[str]:
    init_db()
    con = connect()
    try:
        rows = con.execute(
            """
            SELECT CAST(trade_date AS VARCHAR) FROM fact_market_daily
            WHERE trade_date BETWEEN ? AND ?
            ORDER BY trade_date DESC
            """,
            [start_date, end_date],
        ).fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


def sync(trade_date: str) -> dict:
    """跑完全部公开资产子任务。至少一个成功则步骤可继续；全失败才 raise。"""
    init_db()
    results: dict[str, object] = {}
    errors: dict[str, str] = {}
    for name, fn in ASSET_SYNCS:
        try:
            results[name] = fn(trade_date)
        except Exception as exc:  # noqa: BLE001
            errors[name] = f"{type(exc).__name__}: {exc}"
    payload = {
        "trade_date": trade_date,
        "results": results,
        "errors": errors,
        "ok": bool(results),
    }
    if not results:
        raise RuntimeError(f"复盘会公开资产全部失败: {errors}")
    return payload


def sync_range(
    start_date: str,
    end_date: str,
    *,
    refresh: bool = False,
    sleep: float = 0.2,
    include_catalog: bool = False,
) -> dict:
    """按 fact_market_daily 交易日历回补日频资产，跳过已有行。

    研报目录 / 题材挖掘默认不重拉（不是按日切片的库）。
    """
    dates = calendar_dates(start_date, end_date)
    if not dates:
        raise RuntimeError(f"fact_market_daily 在 {start_date}~{end_date} 无交易日")
    tasks = list(DAILY_SYNCS)
    if include_catalog:
        tasks.extend(ONCE_SYNCS)

    synced = 0
    skipped = 0
    failed = 0
    per_task = {name: {"synced": 0, "skipped": 0, "failed": 0, "empty": 0} for name, _fn in tasks}

    for i, td in enumerate(dates, start=1):
        init_db()
        con = connect()
        try:
            pending = []
            for name, fn in tasks:
                if not refresh and (_has_rows(con, name, td) or _ops_done(con, td, name)):
                    per_task[name]["skipped"] += 1
                    skipped += 1
                    continue
                pending.append((name, fn))
        finally:
            con.close()

        if not pending:
            print(f"[{i}/{len(dates)}] {td} skip-all", flush=True)
            continue

        print(f"[{i}/{len(dates)}] {td} run={','.join(n for n, _ in pending)}", flush=True)
        for name, fn in pending:
            try:
                result = fn(td)
                rows = _result_row_count(result)
                if rows > 0 or (name == "keywords" and isinstance(result, dict) and result.get("updated")):
                    _mark_ops(td, name, "complete", max(rows, 1))
                    per_task[name]["synced"] += 1
                    synced += 1
                else:
                    _mark_ops(td, name, "empty", 0)
                    per_task[name]["empty"] += 1
                    synced += 1
            except Exception as exc:  # noqa: BLE001
                _mark_ops(td, name, "failed", 0, f"{type(exc).__name__}: {exc}")
                per_task[name]["failed"] += 1
                failed += 1
                print(f"  FAIL {name}: {type(exc).__name__}: {exc}", flush=True)
            if sleep:
                time.sleep(float(sleep))

    return {
        "start_date": start_date,
        "end_date": end_date,
        "calendar_days": len(dates),
        "synced": synced,
        "skipped": skipped,
        "failed": failed,
        "per_task": per_task,
        "ok": failed == 0 or synced > 0,
    }
