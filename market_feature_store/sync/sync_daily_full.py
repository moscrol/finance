from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

import duckdb

from .. import db as _db
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


OPS_SYNC_RUN_DDL = """
CREATE TABLE IF NOT EXISTS ops_sync_run (
    run_id        TEXT,
    kind          TEXT,
    plan          TEXT,
    trade_date    TEXT,
    started_at    TIMESTAMP,
    finished_at   TIMESTAMP,
    duration_s    DOUBLE,
    ok            BOOLEAN,
    pid           BIGINT,
    child_pid     BIGINT,
    copy_method   TEXT,
    copy_seconds  DOUBLE,
    source_bytes  BIGINT,
    rows_summary  TEXT,
    steps_summary TEXT
)
"""

# 校验/收据行数口径: 与 validate_daily_data 同一张表清单, 不另造分母。
_RECEIPT_TABLES = (
    "fact_market_daily", "fact_sector_daily", "fact_sw_l1_daily",
    "fact_sector_stock_daily", "fact_stock_high_daily",
    "fact_theme_limit_heat_daily", "fact_theme_limit_stock_daily",
    "fact_limit_advance_daily", "fact_stock_daily",
)


def _db_shape(path: Path) -> dict | None:
    """read_only 读一个库的形状: 表数 / 核心表行数 / fact_market_daily 覆盖上界。

    打不开 (损坏/半成品) 返回 None——调用方 fail closed。
    """
    try:
        con = duckdb.connect(str(path), read_only=True)
    except Exception:
        return None
    try:
        from ..db import list_tables

        tables = list_tables(con)
        rows: dict[str, int] = {}
        for table in _RECEIPT_TABLES:
            if table in tables:
                rows[table] = con.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
        max_trade_date = None
        if "fact_market_daily" in tables:
            row = con.execute(
                "SELECT MAX(trade_date) FROM fact_market_daily"
            ).fetchone()
            max_trade_date = str(row[0]) if row and row[0] is not None else None
        return {
            "table_count": len(tables),
            "rows": rows,
            "max_trade_date": max_trade_date,
        }
    finally:
        con.close()


def _write_receipt(staging: Path, receipt: dict) -> None:
    """收据写进 staging、随换名一起可见——生产库自始至终不开 rw 连接。

    (spec §2 的「换名后写收据」若按字面在换名后写生产库, 那一瞬的 rw 打开
    会让恰好撞上的 read_only 连接秒败, 违背判据 1 的零失败; 故收笔前写入
    staging, 换名后收据自然在场, 文件 mtime 即换名时刻。)
    """
    con = duckdb.connect(str(staging))
    try:
        con.execute(OPS_SYNC_RUN_DDL)
        con.execute(
            """
            INSERT INTO ops_sync_run
                (run_id, kind, plan, trade_date, started_at, finished_at,
                 duration_s, ok, pid, child_pid, copy_method, copy_seconds,
                 source_bytes, rows_summary, steps_summary)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                receipt["run_id"], receipt["kind"], receipt["plan"],
                receipt["trade_date"], receipt["started_at"],
                receipt["finished_at"], receipt["duration_s"], receipt["ok"],
                receipt["pid"], receipt["child_pid"], receipt["copy_method"],
                receipt["copy_seconds"], receipt["source_bytes"],
                json.dumps(receipt["rows_summary"], ensure_ascii=False),
                json.dumps(receipt["steps_summary"], ensure_ascii=False),
            ],
        )
    finally:
        con.close()


def run_daily_full_staged(
    trade_date: str | None = None,
    chart_table: str | None = None,
    skip_long: bool = False,
    stock_source: str = "snapshot",
    child_argv: list[str] | None = None,
) -> dict:
    """daily-full 的 staging 编排: 同步全程不持有生产库写锁 (bookgap S7)。

    克隆生产库 → 子进程对 staging 副本跑原管道 (env 重定向, 见下) → 校验 →
    第三方写者守卫 → 收据 → os.replace 原子换名。生产库文件只在换名一瞬变化,
    正持旧句柄的读者继续读旧 inode, 新连接读新库。

    为什么是子进程而不是进程内改 DB_PATH: 包内存在 import 期捕获路径的读点
    (cli 顶层常量、analysis.sector_data 的默认参), 进程内改全局会漏掉它们,
    以后新增的捕获点也会静默漏掉; 子进程在 import 前就带上
    MARKET_FEATURE_STORE_DB, 天然覆盖全部现有与未来读点 (含孙子进程)。

    child_argv 是测试缝: 注入假子进程 (自身读 env 写库/自杀) 来测换名、
    守卫与 crash 语义, 不必跑真管道。

    返回 {rc, swapped, reason, ...}; rc: 0=全绿, 1=管道有失败步但按现状
    口径落库 (换名照做——今天的行为就是失败步不回滚已提交写入),
    2=fail closed (未换名, 生产库未动)。
    """
    started_at = datetime.now()
    started_mono = time.monotonic()
    target = _db.DB_PATH
    staging = _db.staging_path(target)
    result: dict = {
        "target": str(target),
        "staging": str(staging),
        "swapped": False,
        "rc": 2,
        "reason": None,
        "copy": None,
        "child_returncode": None,
        "run_id": None,
        "stale_staging_removed": False,
    }

    result["stale_staging_removed"] = _db.remove_stale_staging(staging)
    if result["stale_staging_removed"]:
        print(f"[staging] 清理上一轮残留 staging: {staging}", flush=True)

    # 开工闸: 有活跃写者时开跑, 克隆是撕裂快照、换名会覆盖对方工作。
    try:
        _db.probe_no_active_writer(target)
    except _db.DatabaseLockedError as exc:
        result["reason"] = f"生产库有活跃写者, 拒绝开工: {exc}"
        print(f"[staging] {result['reason']}", flush=True)
        return result

    source_exists = target.exists()
    source_stat = target.stat() if source_exists else None
    source_shape = _db_shape(target) if source_exists else None
    if source_exists and source_shape is None:
        result["reason"] = f"生产库打不开, 拒绝开工: {target}"
        return result

    if source_exists:
        result["copy"] = _db.clone_to_staging(target, staging)
        # 克隆完成后的基线 stat: 此后生产文件再有任何变化 = 第三方写者。
        source_stat = target.stat()
        copy = result["copy"]
        print(
            f"[staging] 克隆生产库 -> {staging.name} "
            f"({copy['method']}, {copy['seconds']}s, {copy['bytes']} bytes)",
            flush=True,
        )

    status_json = Path(str(staging) + ".status.json")
    if child_argv is None:
        child_argv = [
            sys.executable, "-m", "market_feature_store.cli",
            "daily-full-exec", "--status-json", str(status_json),
        ]
        if trade_date:
            child_argv += ["--trade-date", trade_date]
        if chart_table:
            child_argv += ["--chart-table", chart_table]
        if skip_long:
            child_argv.append("--skip-long")
        child_argv += ["--stock-source", stock_source]

    child_env = os.environ.copy()
    child_env["MARKET_FEATURE_STORE_DB"] = str(staging)
    proc = subprocess.Popen(child_argv, env=child_env, cwd=str(PROJECT_DIR))
    print(
        f"[staging] 子进程同步 pid={proc.pid} (写锁只落在 staging, 生产库无锁)",
        flush=True,
    )
    child_rc = proc.wait()
    result["child_returncode"] = child_rc
    result["child_pid"] = proc.pid

    status: dict = {}
    if status_json.exists():
        try:
            status = json.loads(status_json.read_text(encoding="utf-8"))
        finally:
            status_json.unlink()
    result["status"] = status

    def _abort(reason: str) -> dict:
        result["reason"] = reason
        print(f"[staging] {reason}", flush=True)
        return result

    if child_rc < 0:
        return _abort(
            f"子进程被信号终止 (rc={child_rc}), staging 视为半成品, 不换名"
        )
    if not status:
        return _abort(
            f"子进程未写出 status.json (rc={child_rc}), 视为未跑完管道, 不换名"
        )
    if child_rc not in (0, 1):
        return _abort(f"子进程异常退出 (rc={child_rc}), 不换名")

    staging_shape = _db_shape(staging)
    if staging_shape is None:
        return _abort(f"staging 打不开, 不换名: {staging}")
    if source_shape is not None:
        if staging_shape["table_count"] < source_shape["table_count"]:
            return _abort(
                f"校验失败: staging 表数 {staging_shape['table_count']} < "
                f"生产 {source_shape['table_count']}, 不换名"
            )
        if (
            source_shape["max_trade_date"]
            and (staging_shape["max_trade_date"] or "")
            < source_shape["max_trade_date"]
        ):
            return _abort(
                f"校验失败: staging 交易日覆盖 {staging_shape['max_trade_date']}"
                f" 倒退于生产 {source_shape['max_trade_date']}, 不换名"
            )
    result["validation"] = {
        "source": source_shape,
        "staging": staging_shape,
    }
    print(
        "[staging] 校验通过: 表 "
        f"{staging_shape['table_count']}"
        + (f">={source_shape['table_count']}" if source_shape else "")
        + f", fact_market_daily 覆盖到 {staging_shape['max_trade_date']}",
        flush=True,
    )

    run_id = uuid.uuid4().hex[:12]
    result["run_id"] = run_id
    finished_at = datetime.now()
    _write_receipt(staging, {
        "run_id": run_id,
        "kind": "daily-full",
        "plan": "staging-swap",
        "trade_date": status.get("trade_date") or trade_date,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": round(time.monotonic() - started_mono, 1),
        "ok": child_rc == 0,
        "pid": os.getpid(),
        "child_pid": proc.pid,
        "copy_method": (result["copy"] or {}).get("method"),
        "copy_seconds": (result["copy"] or {}).get("seconds"),
        "source_bytes": (result["copy"] or {}).get("bytes"),
        "rows_summary": staging_shape["rows"],
        "steps_summary": status.get("steps") or [],
    })

    # 第三方写者守卫: 克隆基线之后生产文件动过、或此刻有写者持锁,
    # 换名都会覆盖对方工作——fail closed, staging 留作取证。
    if source_exists:
        if not target.exists():
            return _abort("生产库文件在同步期间被移除, 不换名")
        now_stat = target.stat()
        if (
            now_stat.st_mtime_ns != source_stat.st_mtime_ns
            or now_stat.st_size != source_stat.st_size
        ):
            return _abort(
                "第三方写者守卫: 生产库在同步期间被修改 "
                f"(mtime {source_stat.st_mtime_ns}->{now_stat.st_mtime_ns}), "
                "拒绝换名以免覆盖其写入; staging 保留待人工裁决"
            )
    elif target.exists():
        return _abort("生产库文件在同步期间被第三方创建, 不换名")
    try:
        _db.probe_no_active_writer(target)
    except _db.DatabaseLockedError as exc:
        return _abort(f"第三方写者守卫: {exc}; 拒绝换名")

    swap_started = time.monotonic()
    try:
        _db.atomic_swap_into_place(staging, target)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        return _abort(f"换名失败: {exc}")
    result["swap_seconds"] = round(time.monotonic() - swap_started, 3)
    result["swapped"] = True
    result["rc"] = child_rc
    result["reason"] = "ok"
    print(
        f"[staging] 原子换名完成 ({result['swap_seconds']}s), "
        f"收据 run_id={run_id}",
        flush=True,
    )
    return result


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
