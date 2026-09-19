from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import date, datetime
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


def run_hithink_sector_kline_step(trade_date: str | None = None) -> dict:
    """个股 dump 之后并跑板块 / 指数近 5 日。没 key 算 skip。日更不拉成分。"""

    from .sync_hithink_sector_kline import skip_reason_if_no_key, sync_hithink_sector_kline

    reason = skip_reason_if_no_key()
    if reason:
        return {"skipped": True, "reason": reason}
    return sync_hithink_sector_kline(
        mode="incremental", skip_constituents=True,
        end_date=date.fromisoformat(trade_date) if trade_date else None,
    )


def run_hithink_limit_pools_step(trade_date: str | None = None) -> dict:
    """板块日 K 之后并跑涨停 / 跌停 / 炸板近 3 个交易日。没 key 算 skip。"""

    from .sync_hithink_limit_pools import skip_reason_if_no_key, sync_hithink_limit_pools

    reason = skip_reason_if_no_key()
    if reason:
        return {"skipped": True, "reason": reason}
    return sync_hithink_limit_pools(
        mode="incremental", end_date=date.fromisoformat(trade_date) if trade_date else None,
    )


def run_hithink_dragon_auction_step(trade_date: str | None = None) -> dict:
    """涨停池之后并跑龙虎榜 / 热榜近 3 日 + 竞价终态。没 key 算 skip。"""

    from .sync_hithink_dragon_auction import (
        skip_reason_if_no_key,
        sync_hithink_dragon_auction,
    )

    reason = skip_reason_if_no_key()
    if reason:
        return {"skipped": True, "reason": reason}
    return sync_hithink_dragon_auction(
        mode="incremental", end_date=date.fromisoformat(trade_date) if trade_date else None,
    )


def run_hithink_stock_daily_step() -> dict:
    """东财 / mootdx 之后并跑十年 K 的日增量。没 key 算 skip，有 key 下载失败才失败。"""

    from .sync_hithink_stock_daily import skip_reason_if_no_key, sync_hithink_stock_daily

    reason = skip_reason_if_no_key()
    if reason:
        return {"skipped": True, "reason": reason}
    return sync_hithink_stock_daily(mode="incremental")


def _run_compute_features(trade_date: str) -> dict:
    """fact 写入后的派生层。漏跑就是「有行情、门禁红在 feature_*」。"""
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))
    from scripts.compute_features import compute_features

    return compute_features(trade_date)


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
    skip_long: bool = False,
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
    # 同花顺官方 dump 并跑，不改 fact_stock_daily。缺 key 跳过，不让整条 daily-full 红。
    steps.append(_run_step("sync-hithink-stock-daily", run_hithink_stock_daily_step))
    steps.append(_run_step("sync-hithink-sector-kline", run_hithink_sector_kline_step, td))
    steps.append(_run_step("sync-hithink-limit-pools", run_hithink_limit_pools_step, td))
    steps.append(_run_step("sync-hithink-dragon-auction", run_hithink_dragon_auction_step, td))
    steps.append(_run_step("sync-mainline-daily", sync_mainline_daily, td))
    steps.append(_run_step("sync-theme-flow-daily", sync_theme_flow_daily, td))
    steps.append(_run_step("sync-mainline-sector-daily", sync_mainline_sector_daily, td))
    steps.append(_run_step("sync-fupanhui-public-assets", sync_public_assets, td))
    # fact 写完必须派生；漏这一步就是 08-20「有行情无 feature」半成品。
    steps.append(_run_step("compute-features", _run_compute_features, td))
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
    skip_long: bool = False,
    stock_source: str = "snapshot",
    child_argv: list[str] | None = None,
    kind: str = "daily-full",
    pre_swap_backup: bool = False,
) -> dict:
    """staging 编排的公共入口：先取运行互斥锁，再进编排本体。

    QC 复审三轮 P1：两轮父进程共用同一 staging 路径时，B 会把 A 尚未发布
    的 staging 当旧残留清掉重建，A 恢复后发布的是 B 的失败半成品（连 A 写
    进 staging 的收据一起没了）。因此互斥锁在任何清理之前取得、覆盖本轮
    全生命周期（db.hold_run_mutex，锁在独立文件上，读写双方无感）。
    拿不到锁立即 rc=2，不做任何清理、不动 staging、不动生产库。
    """
    target = _db.DB_PATH
    try:
        with _db.hold_run_mutex(target):
            return _run_daily_full_staged_locked(
                trade_date,
                skip_long=skip_long,
                stock_source=stock_source,
                child_argv=child_argv,
                kind=kind,
                pre_swap_backup=pre_swap_backup,
            )
    except _db.DatabaseLockedError as exc:
        reason = f"{exc}；本轮不做任何清理与换名"
        print(f"[staging] {reason}", flush=True)
        return {
            "target": str(target),
            "staging": str(_db.staging_path(target)),
            "swapped": False,
            "rc": 2,
            "reason": reason,
            "copy": None,
            "child_returncode": None,
            "run_id": None,
            "backup": None,
        }


def _run_daily_full_staged_locked(
    trade_date: str | None = None,
    skip_long: bool = False,
    stock_source: str = "snapshot",
    child_argv: list[str] | None = None,
    kind: str = "daily-full",
    pre_swap_backup: bool = False,
) -> dict:
    """daily-full 的 staging 编排: 同步全程不持有生产库写锁 (bookgap S7)。

    克隆生产库 → 子进程对 staging 副本跑原管道 (env 重定向, 见下) → 校验 →
    第三方写者守卫 → [可选换名前备份] → 收据 → 原子发布（既有库在换库锁内
    os.replace 换名；首次建库 os.link no-clobber，六轮 P1）。生产库文件只在
    发布一瞬变化, 正持旧句柄的读者继续读旧 inode, 新连接读新库。
    existing/absent 分类钉死在本轮首次观察（七轮 P2，见下文开工闸注释）。

    pre_swap_backup=True 时（修复类调用方，QC S4 执行前提）：守卫通过后、
    换名前给 target 落一份带 sha256 指纹与恢复步骤收据的备份
    （db.backup_before_swap），结果带 result["backup"]。日更默认不开——
    每晚 3.6G 级备份会把磁盘打爆，且日更已有 ops_sync_run 链。

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
    run_id = uuid.uuid4().hex[:12]
    target = _db.DB_PATH
    staging = _db.staging_path(target)
    status_json = Path(str(staging) + ".status.json")
    result: dict = {
        "target": str(target),
        "staging": str(staging),
        "swapped": False,
        "rc": 2,
        "reason": None,
        "copy": None,
        "child_returncode": None,
        "run_id": run_id,
        "stale_staging_removed": False,
        "stale_status_removed": False,
        "backup": None,
        "publish": None,
    }

    result["stale_staging_removed"] = _db.remove_stale_staging(staging)
    if result["stale_staging_removed"]:
        print(f"[staging] 清理上一轮残留 staging: {staging}", flush=True)
    if status_json.exists():
        # QC 复审二轮 P1（2026-09-13）：旧 status 不被清理，子进程失败且不写
        # status 时父进程会读到上一轮的成功 JSON 照样换库（复现证据
        # stale-status-min.json）。开工即删 + 后文 run_id 绑定双保险。
        status_json.unlink()
        result["stale_status_removed"] = True

    # 开工闸: 有活跃写者时开跑, 克隆是撕裂快照、换名会覆盖对方工作。
    # QC 七轮 P2：existing/absent 的分类钉死在**本轮首次观察**（就是这次
    # exists()），之后不再就分类重新观察。此前分类在探针成功之后再做一次
    # exists()：探针已经打开过旧库、随后目标被第三方删除，第二次 exists 得
    # False，本轮被静默重新归类为首次建库——子进程建出缺历史的新库并发布
    # 成功（七轮独立探针实测：旧库 2026-08-14/10000 被删后 rc=0，库里只剩
    # 2026-08-15/12345）。钉死之后，「已见旧库、随后消失」只剩拒绝：消失在
    # 探针窗口内由探针抛 SwapTargetReplacedError；消失在探针之后由
    # hold_swap_lock 开锁失败拒绝——都是 rc=2，不再降格为 bootstrap。反向
    # （钉为 absent 后第三方新建）由发布前守卫与 os.link EEXIST 原子拒绝
    # （六轮 P1），所以首次观察一次 exists 就够，不需要身份钉死。
    # 声明边界：钉死只对「本轮首次观察之后」的消失负责；观察之前就被删的，
    # 本轮无从知道它存在过。
    source_exists = target.exists()
    try:
        _db.probe_no_active_writer(target)
    except _db.SwapTargetReplacedError as exc:
        # 探针窗口内目标消失（探针的 exists→connect 之间被删）：与「有活跃
        # 写者」分开给措辞，reason 才能指认是哪一处拒绝。它是
        # DatabaseLockedError 子类，必须排在前面。
        result["reason"] = f"{exc}; 拒绝开工"
        print(f"[staging] {result['reason']}", flush=True)
        return result
    except _db.DatabaseLockedError as exc:
        result["reason"] = f"生产库有活跃写者, 拒绝开工: {exc}"
        print(f"[staging] {result['reason']}", flush=True)
        return result

    if source_exists:
        # QC 复审三轮 P1：基线与克隆必须落在同一受保护窗口——克隆之后才认领
        # 来源最新 stat，会把「副本不含的新写入」记成副本基线（QC 复现：克隆
        # 10000 → 窗口内第三方提交 17000 → 末端守卫拿错基线 → 换入 10000）。
        # hold_swap_lock 是 SH 锁：排写不排读，克隆内部的只读探针照常工作，
        # 窗口内任何写者的 rw 打开必失败；窗口外（子进程阶段）的写入仍由
        # 末端 stat 守卫兜底。形态基线改从克隆体自身读取——基线=副本版本。
        try:
            with _db.hold_swap_lock(target) as lock:
                result["copy"] = _db.clone_to_staging(target, staging)
                # QC 复审五轮：基线身份必须**来自这把锁**，并在克隆之后复查一次。
                # 否则「锁住 A → 克隆 A → 路径被换成 B → 从路径 stat 得到 B」会
                # 把 A 的副本配上 B 的基线，两边都不自知。
                _db.assert_same_target(target, lock.identity, stage="克隆后基线")
                # 版本基线读被锁 inode 自身 (fstat)，不再走路径——路径 stat 拿到的
                # 可能已经是别人换上来的文件。
                source_stat = lock.stat()
                source_identity = lock.identity
                source_shape = _db_shape(staging)
        except _db.DatabaseLockedError as exc:
            # SwapTargetReplacedError 是其子类：开锁时目标已没了、克隆期间目标被
            # 删、克隆后身份漂了，都走这条，统一成 rc=2 拒绝，不让异常逃逸。
            # （措辞从「拿锁失败」放宽到「失败」：六轮起这条出口不再只有拿锁一种
            #   来源，具体是哪一处由 exc 自带的 stage 指认。）
            result["reason"] = f"基线窗口失败: {exc}; 拒绝开工"
            print(f"[staging] {result['reason']}", flush=True)
            return result
        if source_shape is None:
            result["reason"] = f"克隆体打不开, 拒绝开工: {staging}"
            return result
        copy = result["copy"]
        print(
            f"[staging] 克隆生产库 -> {staging.name} "
            f"({copy['method']}, {copy['seconds']}s, {copy['bytes']} bytes)",
            flush=True,
        )
    else:
        source_stat = None
        source_shape = None
        source_identity = None

    if child_argv is None:
        child_argv = [
            sys.executable, "-m", "market_feature_store.cli",
            "daily-full-exec", "--status-json", str(status_json),
        ]
        if trade_date:
            child_argv += ["--trade-date", trade_date]
        if skip_long:
            child_argv.append("--skip-long")
        child_argv += ["--stock-source", stock_source]

    child_env = os.environ.copy()
    child_env["MARKET_FEATURE_STORE_DB"] = str(staging)
    # 本轮身份：子进程把 run_id 写进 status，父进程据此拒收上一轮遗留
    child_env["MARKET_FEATURE_STORE_RUN_ID"] = run_id
    proc = subprocess.Popen(child_argv, env=child_env, cwd=str(PROJECT_DIR))
    print(
        f"[staging] 子进程同步 pid={proc.pid} (写锁只落在 staging, 生产库无锁)",
        flush=True,
    )
    child_rc = proc.wait()
    result["child_returncode"] = child_rc
    result["child_pid"] = proc.pid

    def _abort(reason: str) -> dict:
        result["reason"] = reason
        print(f"[staging] {reason}", flush=True)
        return result

    status: dict = {}
    if status_json.exists():
        # QC 复审三轮 P2：损坏/非标量 status 不得抛异常逃逸，统一走明确拒绝。
        try:
            raw_status = json.loads(status_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            status_json.unlink(missing_ok=True)
            result["status"] = {}
            return _abort(f"status.json 解析失败 ({exc}), 不换名")
        status_json.unlink(missing_ok=True)
        if not isinstance(raw_status, dict):
            return _abort(
                f"status.json 不是 JSON 对象 ({type(raw_status).__name__}), 不换名"
            )
        status = raw_status
    result["status"] = status

    if child_rc < 0:
        return _abort(
            f"子进程被信号终止 (rc={child_rc}), staging 视为半成品, 不换名"
        )
    if not status:
        return _abort(
            f"子进程未写出 status.json (rc={child_rc}), 视为未跑完管道, 不换名"
        )
    if status.get("run_id") != run_id:
        return _abort(
            "status.json 缺本轮 run_id 或不匹配（疑似上一轮遗留/非本轮产物），不换名"
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

    finished_at = datetime.now()
    _write_receipt(staging, {
        "run_id": run_id,
        "kind": kind,
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

    # 第三方写者守卫（锁外预检）: 克隆基线之后生产文件动过、或此刻有写者持锁,
    # 换名都会覆盖对方工作——fail closed, staging 留作取证。
    # 这里只是早失败 + 给出具体措辞; 权威判定在下面的换库锁内重做一次。
    if source_exists:
        # QC 六轮 P2：一次 stat 兼做「还在不在」与「动没动过」。此前是
        # exists() + 裸 stat() 两段，两段之间目标被删就是裸 FileNotFoundError
        # 逃出编排（六轮独立探针在此行复现）；合成一次调用后窗口不存在，
        # 「已消失」也变成带出口码的拒绝。
        try:
            now_stat = target.stat()
        except FileNotFoundError:
            return _abort("锁外预检: 生产库文件在同步期间被移除, 不换名")
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
    if source_exists:
        # QC 复审四轮 P1：「最终复查→[备份]→原子换名」整段必须在同一把换库锁
        # 内，**与 pre_swap_backup 无关**。此前只有备份分支进锁，日更默认走的是
        # 「守卫 → 无锁 os.replace」，守卫与使用之间是裸窗口（TOCTOU）；四轮复现
        # 在此窗口内让第三方 rw 提交 17000，编排照样 rc=0/swapped=true，而新库不
        # 含 17000——写入已提交却被静默覆盖。
        # hold_swap_lock 是 SH：排写不排读，日更的锁窗口只有「stat + rename」量级
        # （毫秒），不会重新把只读读者挡在门外（S7 判据 1）；修复类多一次备份。
        try:
            with _db.hold_swap_lock(target) as lock:
                # 锁内权威复查。身份先于版本：版本一致但 inode 已换，说明被整文件
                # 替换过，此时 mtime/size 相等毫无意义（cp/mv 会带走 mtime）。
                _db.assert_same_target(
                    target, source_identity, stage="换库临界区（对克隆基线）"
                )
                if lock.identity != source_identity:
                    # 锁的 inode 与基线 inode 不同 = 我们锁住的不是要换的那个。
                    return _abort(
                        f"目标身份守卫: 换库锁锁定 {lock.identity} 与克隆基线 "
                        f"{source_identity} 不是同一个 inode; 拒绝换名"
                    )
                now_stat = lock.stat()  # 读被锁 inode 自身，不走路径
                if (
                    now_stat.st_mtime_ns != source_stat.st_mtime_ns
                    or now_stat.st_size != source_stat.st_size
                ):
                    return _abort(
                        "拿锁前窗口内生产库被修改，拒绝换名；staging 保留待人工裁决"
                    )
                if pre_swap_backup:
                    # QC S4 执行前提：修复类调用方换库前留一份可验明备份。
                    # 日更不带（每晚 3.6G 级备份会把磁盘打爆），但锁一样要进。
                    try:
                        result["backup"] = _db.backup_before_swap(
                            target, run_id=run_id, writer_lock_held=True
                        )
                    except Exception as exc:
                        return _abort(f"换名前备份失败, 不换名: {exc}")
                    print(
                        f"[staging] 换名前备份: {result['backup']['backup_path']} "
                        f"(sha256={result['backup']['backup_sha256'][:16]}…)",
                        flush=True,
                    )
                try:
                    _db.atomic_swap_into_place(
                        staging, target, expect_identity=source_identity
                    )
                except _db.SwapTargetReplacedError as exc:
                    return _abort(f"目标身份守卫: {exc}")
                except (RuntimeError, FileNotFoundError, OSError) as exc:
                    return _abort(f"换名失败: {exc}")
        except _db.SwapTargetReplacedError as exc:
            return _abort(f"目标身份守卫: {exc}; 拒绝换名")
        except _db.DatabaseLockedError as exc:
            return _abort(f"排他协调锁: {exc}; 拒绝换名")
    else:
        # 首次建库：目标不存在 = 没有 inode 可锁，但**不等于没有数据可丢**。
        # QC 六轮 P1 否掉了旧理由：守卫通过之后、发布之前，一个普通
        # duckdb.connect(target) 写者可以建库、提交、关闭（持 DuckDB 自己的 EX
        # 锁，没绕过任何机制），os.replace 会把它已提交的数据静默覆盖，编排还报
        # rc=0/swapped=True。run mutex 只排同协议的 staging 编排，排不掉普通
        # DuckDB 新建库。改用 os.link 发布：目标名已存在就在同一个 syscall 里
        # 原子拒绝，「守卫通过后才被创建」这段窗口不再是覆盖而是拒绝。
        try:
            result["publish"] = _db.publish_new_into_place(staging, target)
        except _db.SwapTargetCreatedError as exc:
            # 注意：它是 RuntimeError 的后代，必须排在下面那条之前。
            return _abort(f"首次建库守卫: {exc}")
        except (RuntimeError, FileNotFoundError, OSError) as exc:
            return _abort(f"首次建库发布失败: {exc}")
        if not result["publish"]["staging_name_removed"]:
            # link 已成功 = 已发布。清理失败不得回退成「未换库、生产未动」。
            print(
                "[staging] 已发布, 但 staging 名字未删掉: "
                f"{result['publish']['staging_cleanup_error']}; "
                "它与 target 同 inode, 删名不伤数据, 下一轮 remove_stale_staging 收掉",
                flush=True,
            )
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
    skip_long: bool = False,
    stock_source: str = "snapshot",
) -> dict:
    from ..reports.daily_review import build_daily_review
    from ..quality import check_daily

    update = run_daily_update(
        trade_date=trade_date,
        skip_long=skip_long,
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
