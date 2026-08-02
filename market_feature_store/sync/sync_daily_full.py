from __future__ import annotations

import os
import subprocess
import sys

from ..db import PROJECT_DIR, connect


def _latest_trade_date() -> str:
    con = connect(read_only=True)
    try:
        row = con.execute("SELECT MAX(trade_date) FROM fact_market_daily").fetchone()
        if not row or not row[0]:
            raise RuntimeError("fact_market_daily 无交易日")
        return str(row[0])
    finally:
        con.close()


def _run_step(name, func, *args, **kwargs):
    try:
        result = func(*args, **kwargs)
        return {"name": name, "ok": True, "result": result, "error": None}
    except Exception as exc:
        return {"name": name, "ok": False, "result": None, "error": str(exc)}


def _run_advancers_chart(trade_date: str, chart_table: str | None = None) -> dict:
    output = PROJECT_DIR / "market_feature_store" / "exports" / f"{trade_date}-advancers-ma5.png"
    script = PROJECT_DIR / "skills" / "advancers-chart" / "scripts" / "feishu_chart.py"
    env = os.environ.copy()
    if chart_table:
        env["FEISHU_CHART_TABLE"] = chart_table
    proc = subprocess.run(
        [sys.executable, str(script), str(output)],
        cwd=str(PROJECT_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return {"output": str(output), "stdout": proc.stdout.strip()}


def validate_daily_data(trade_date: str | None = None) -> dict:
    con = connect(read_only=True)
    try:
        td = trade_date or _latest_trade_date()
        field_row = con.execute(
            """
            SELECT
              market_stage, stage_day, total_amount, amount_vs_yesterday_pct, amount_ma20, volume_ratio,
              advancers, limit_up, limit_down, sh_week_ma, sh_deviation_pct, sh_index_close,
              sh_index_pct_chg, top3_industry_ratio, industry_1, industry_2, industry_3,
              strength_avg_pct, strength_amount_pct, strength_amount, strength_marginal_pct,
              strength_ma5_avg_pct, strength_ma20_avg_pct, strength_status, stock_high_count_120d
            FROM fact_market_daily
            WHERE trade_date = ?
            """,
            [td],
        ).fetchone()
        field_names = [
            "market_stage", "stage_day", "total_amount", "amount_vs_yesterday_pct", "amount_ma20", "volume_ratio",
            "advancers", "limit_up", "limit_down", "sh_week_ma", "sh_deviation_pct", "sh_index_close",
            "sh_index_pct_chg", "top3_industry_ratio", "industry_1", "industry_2", "industry_3",
            "strength_avg_pct", "strength_amount_pct", "strength_amount", "strength_marginal_pct",
            "strength_ma5_avg_pct", "strength_ma20_avg_pct", "strength_status", "stock_high_count_120d",
        ]
        missing_fields = []
        if not field_row:
            missing_fields = field_names
        else:
            missing_fields = [name for name, value in zip(field_names, field_row) if value is None]
        tables = [
            "fact_market_daily", "fact_sector_daily", "fact_sw_l1_daily", "fact_sector_stock_daily", "fact_stock_high_daily",
            "fact_theme_limit_heat_daily", "fact_theme_limit_stock_daily", "fact_limit_advance_daily", "fact_stock_daily",
        ]
        table_status = []
        for table in tables:
            max_date, rows, target_rows = con.execute(
                f"""
                SELECT MAX(trade_date), COUNT(*), COUNT(*) FILTER (WHERE trade_date = ?)
                FROM {table}
                """,
                [td],
            ).fetchone()
            table_status.append({
                "table": table,
                "max_date": str(max_date) if max_date else None,
                "rows": rows,
                "target_rows": target_rows,
                "ok": target_rows > 0,
            })
        return {"trade_date": str(td), "missing_fields": missing_fields, "tables": table_status, "ok": not missing_fields and all(t["ok"] for t in table_status)}
    finally:
        con.close()


def run_daily_update(
    trade_date: str | None = None,
    chart_table: str | None = None,
    skip_long: bool = False,
    with_chart: bool = True,
    stock_source: str = "snapshot",
) -> dict:
    """stock_source: 全A日线取数方式。
    'snapshot' (默认) 走东财全市场快照, 单日盘后增量, 几秒完成;
    'mootdx' 走通达信逐只 TCP, 慢但可拉历史多日 (skip_long 时跳过)。
    """
    steps = []
    td = trade_date

    from .sync_fupanhui_sectors import sync_dim_sector
    from .sync_fupanhui_market_daily import sync_fupanhui_market_overview
    from .sync_feishu_market_daily import sync_fact_market_daily
    from .sync_akshare_index_daily import sync_akshare_index_daily
    from .sync_akshare_sw_l1_daily import sync_akshare_sw_l1_daily
    from .sync_fupanhui_market_deviation import sync_market_deviation
    from .sync_fupanhui_sector_daily import sync_fact_sector_daily
    from .sync_fupanhui_sector_stock_daily import sync_fact_sector_stock_daily
    from .sync_fupanhui_limit_heat_daily import sync_fupanhui_limit_heat
    from .sync_fupanhui_stock_high_daily import sync_fupanhui_stock_high
    from .sync_fupanhui_limit_advance_daily import sync_fupanhui_limit_advance
    from .sync_mootdx_stock_daily import sync_fact_stock_daily
    from .sync_eastmoney_stock_snapshot import sync_fact_stock_daily_snapshot
    from .sync_feishu_sector_resonance import sync_sector_multi_period_resonance
    from .sync_fupanhui_mainline_daily import sync as sync_mainline_daily
    from .sync_fupanhui_theme_flow_daily import sync as sync_theme_flow_daily
    from .sync_fupanhui_mainline_sector_daily import sync as sync_mainline_sector_daily

    steps.append(_run_step("sync-sectors", sync_dim_sector, trade_date=td))
    steps.append(_run_step("sync-market-overview", sync_fupanhui_market_overview, trade_date=td, days=60))
    if not td:
        td = str(steps[-1]["result"].get("trade_date")) if steps[-1]["ok"] and steps[-1]["result"] else _latest_trade_date()
    steps.append(_run_step("sync-market-daily", sync_fact_market_daily))
    steps.append(_run_step("sync-index-daily", sync_akshare_index_daily, trade_date=td))
    steps.append(_run_step("sync-sw-l1-daily", sync_akshare_sw_l1_daily, trade_date=td, days=20))
    steps.append(_run_step("sync-market-deviation", sync_market_deviation, trade_date=td))
    steps.append(_run_step("sync-sector-daily", sync_fact_sector_daily, trade_date=td, days=25))
    if not skip_long:
        steps.append(_run_step("sync-sector-stocks", sync_fact_sector_stock_daily, trade_date=td, only_missing=True, sleep=0.2))
    steps.append(_run_step("sync-limit-heat", sync_fupanhui_limit_heat, trade_date=td))
    steps.append(_run_step("sync-stock-high", sync_fupanhui_stock_high, trade_date=td, page_size=200))
    steps.append(_run_step("sync-limit-advance", sync_fupanhui_limit_advance, trade_date=td, min_boards=2))
    if stock_source == "mootdx":
        if not skip_long:
            steps.append(_run_step("sync-stock-daily", sync_fact_stock_daily, start_date=td, offset=3, only_missing=True, sleep=0.0, qfq=False))
    else:
        steps.append(_run_step("sync-stock-daily", sync_fact_stock_daily_snapshot, trade_date=td))
    steps.append(_run_step("sync-sector-resonance", sync_sector_multi_period_resonance))
    steps.append(_run_step("sync-mainline-daily", sync_mainline_daily, td))
    steps.append(_run_step("sync-theme-flow-daily", sync_theme_flow_daily, td))
    steps.append(_run_step("sync-mainline-sector-daily", sync_mainline_sector_daily, td))
    if with_chart:
        steps.append(_run_step("advancers-chart", _run_advancers_chart, td, chart_table))
    validation = validate_daily_data(td)
    return {"trade_date": str(td), "steps": steps, "validation": validation, "ok": all(s["ok"] for s in steps) and validation["ok"]}


def run_daily_full(
    trade_date: str | None = None,
    chart_table: str | None = None,
    skip_long: bool = False,
    stock_source: str = "snapshot",
) -> dict:
    from ..reports.daily_review import build_daily_review
    from ..quality import check_daily

    update = run_daily_update(
        trade_date=trade_date,
        chart_table=chart_table,
        skip_long=skip_long,
        with_chart=False,
        stock_source=stock_source,
    )
    cross_day_gate = check_daily(trade_date=update["trade_date"]) if update["ok"] else {
        "trade_date": update["trade_date"],
        "ok": False,
        "brief": "same-day gate failed; cross-day gate skipped",
        "skipped": True,
    }
    gates_ok = update["ok"] and cross_day_gate["ok"]
    review = build_daily_review(trade_date=update["trade_date"]) if gates_ok else None
    return {
        "trade_date": update["trade_date"],
        "update": update,
        "cross_day_gate": cross_day_gate,
        "review": review,
        "ok": gates_ok,
    }
