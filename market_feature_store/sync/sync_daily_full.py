from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
import urllib.request

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


def preflight_daily_update(
    *,
    module_exists=None,
    cdp_probe=None,
) -> dict:
    """开跑前把「这个解释器/环境跑不完整条链」的事实一次说清。

    2026-08-12 实测两次白跑：宿主 python3(3.9) 在 import 期就崩
    （`dataclass(slots=True)`），换 `.venv-workbench` 后 akshare 缺失——
    但那次直到第 4 步才暴露，前面 3 步的网络抓取已经花掉，且 index/sw-l1/
    deviation 三步连环 FAIL、同日门必挂、报告必不生成，整轮 7 分钟注定白跑。

    按「事实投递 > 提醒」：缺什么、哪些步骤会因此失败、该用哪个解释器，
    开跑前打出与错误信念直接矛盾的那条事实，而不是让人事后从 step 错误里拼。
    返回 {ok, problems: [...]}；调用方 fail closed。
    """

    exists = module_exists or (
        lambda name: importlib.util.find_spec(name) is not None
    )
    problems: list[str] = []
    if not exists("akshare"):
        problems.append(
            f"当前解释器 {sys.executable} 缺 akshare："
            "sync-index-daily / sync-sw-l1-daily 必挂，"
            "sync-market-deviation 的 MA 兜底缺当日上证收盘价也会挂，"
            "同日门必不通过、报告必不生成。"
            "请换装有 akshare 的解释器（日常为 homebrew python3）再跑。"
        )
    if not exists("duckdb"):
        problems.append(
            f"当前解释器 {sys.executable} 缺 duckdb：所有写库步骤必挂。"
        )

    def _default_cdp_probe() -> bool:
        try:
            urllib.request.urlopen("http://localhost:3456/targets", timeout=3)
            return True
        except Exception:
            return False

    if not (cdp_probe or _default_cdp_probe)():
        problems.append(
            "CDP proxy(localhost:3456) 不可达：fupanhui 侧全部 sync 步骤必挂。"
            "先启动 node ~/.claude/skills/web-access/scripts/cdp-proxy.mjs"
            "（需 Chrome 已开 remote debugging）。"
        )
    return {"ok": not problems, "problems": problems}


def _run_step(name, func, *args, **kwargs):
    # 即时输出 + 逐步计时：这条链单步可到分钟级，重定向到文件时 Python 还会
    # 块缓冲——2026-08-12 实测跑了 6 分钟日志 0 字节，中途卡在哪完全不可判。
    # flush 让「文件里最后一行」重新成为可信的进度指针；elapsed_s 让「哪步最贵」
    # 不用靠掐表（先量后改的量就从这来）。
    started = time.monotonic()
    print(f"[step] {name} ...", flush=True)
    try:
        result = func(*args, **kwargs)
        elapsed = round(time.monotonic() - started, 1)
        print(f"[step] {name} ok ({elapsed}s)", flush=True)
        return {
            "name": name,
            "ok": True,
            "result": result,
            "error": None,
            "elapsed_s": elapsed,
        }
    except Exception as exc:
        elapsed = round(time.monotonic() - started, 1)
        print(f"[step] {name} FAIL ({elapsed}s): {exc}", flush=True)
        return {
            "name": name,
            "ok": False,
            "result": None,
            "error": str(exc),
            "elapsed_s": elapsed,
        }


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
    from .sync_fupanhui_mainline_daily import sync as sync_mainline_daily
    from .sync_fupanhui_theme_flow_daily import sync as sync_theme_flow_daily
    from .sync_fupanhui_mainline_sector_daily import sync as sync_mainline_sector_daily
    from .sync_fupanhui_public_assets import sync as sync_public_assets

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
    steps.append(_run_step("sync-mainline-daily", sync_mainline_daily, td))
    steps.append(_run_step("sync-theme-flow-daily", sync_theme_flow_daily, td))
    steps.append(_run_step("sync-mainline-sector-daily", sync_mainline_sector_daily, td))
    steps.append(_run_step("sync-fupanhui-public-assets", sync_public_assets, td))
    if with_chart:
        steps.append(_run_step("advancers-chart", _run_advancers_chart, td, chart_table))
    validation = validate_daily_data(td)
    return {"trade_date": str(td), "steps": steps, "validation": validation, "ok": all(s["ok"] for s in steps) and validation["ok"]}


DECLARED_SECTOR_TABLES = frozenset({"fact_sector_daily", "fact_sector_stock_daily"})


def sector_completion_gate(trade_date: str) -> dict:
    """把板块宇宙完成度审计投影成一道门。

    fail-closed: 没有已发布宇宙、成分未抓全、或任一声明表在本代际下缺行,
    都判不通过。审计本身来自 SectorUniverseStore, 这里不重新计算完成条件。
    """
    from ..db import connect
    from ..sector_universe import SectorUniverseStore

    con = connect(read_only=True)
    try:
        audit = SectorUniverseStore(con).completion_audit(
            trade_date, declared_tables=DECLARED_SECTOR_TABLES
        )
    finally:
        con.close()
    return {
        "trade_date": trade_date,
        "ok": audit.complete,
        "brief": audit.brief(),
        "snapshot_id": audit.snapshot_id,
        "missing_tables": list(audit.missing_tables),
        "status_counts": dict(audit.status_counts),
    }


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
    # 第三道门: 板块宇宙的精确完成度。与夜间循环共用同一个 completion_audit,
    # 不另造公式——两处公式一旦分叉, 报告就可能在成分有缺口时照常生成。
    sector_gate = (
        sector_completion_gate(update["trade_date"])
        if update["ok"] and cross_day_gate["ok"]
        else {
            "trade_date": update["trade_date"],
            "ok": False,
            "brief": "earlier gate failed; sector completion gate skipped",
            "skipped": True,
        }
    )
    gates_ok = update["ok"] and cross_day_gate["ok"] and sector_gate["ok"]
    review = build_daily_review(trade_date=update["trade_date"]) if gates_ok else None
    return {
        "trade_date": update["trade_date"],
        "update": update,
        "cross_day_gate": cross_day_gate,
        "sector_gate": sector_gate,
        "review": review,
        "ok": gates_ok,
    }
