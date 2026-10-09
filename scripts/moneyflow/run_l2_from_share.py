"""夜跑入口：分享转存 → 分片下载 → 解算入库，成功或失败都清理本地下载。不打 ClickHouse。"""
from __future__ import annotations

import os
import shutil
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from baidu_share import (  # noqa: E402
    ensure_transferred,
    load_meta,
    pan_session,
    share_file_map,
    verify_share,
    write_meta,
)
from cdn_chunks import download  # noqa: E402
from l2_paths import archive_name, cache_dir, month_dir, yyyymmdd  # noqa: E402
from process_l2_archive import process_date  # noqa: E402
from write_to_duckdb import mark_failed  # noqa: E402

STEPS = ("limitup", "top100", "quant")


def already_complete(date: str) -> bool:
    import duckdb
    from config import DUCKDB_PATH

    if os.environ.get("L2_FORCE_RESCAN", "").strip() in {"1", "true", "yes"}:
        return False
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        from scripts.check_daily_review_data import L2_RESULT_SQL

        for step in STEPS:
            row = con.execute(
                "SELECT status, row_count, input_count, processed_count, failed_count "
                "FROM ops_pipeline_run_daily "
                "WHERE trade_date=? AND pipeline='l2-moneyflow' AND step=?",
                [date, step],
            ).fetchone()
            if row is None:
                return False
            status, count, inputs, processed, failed = row
            if (
                status != "complete" or inputs is None or inputs <= 0
                or processed != inputs or failed != 0
                or (step == "top100" and inputs < 100)
            ):
                return False
            actual, = con.execute(L2_RESULT_SQL[step], [date]).fetchone()
            # File scans require a valid tick file for every capital candidate.
            if count != actual or (step != "quant" and actual != inputs):
                return False
        return True
    finally:
        con.close()


def cleanup_local(day: str) -> None:
    if len(day) != 8 or not day.isascii() or not day.isdigit():
        raise ValueError("L2 cleanup requires a YYYYMMDD date, not a path")
    cache = cache_dir()
    for path in (
        cache / f"{day}.7z",
        cache / f"{day}.7z.part",
        cache / f"{day}.7z.part.ok",
        cache / f"extract-{day}",
    ):
        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def wait_share_file(date: str) -> None:
    """分享还没上当日包时等（闲鱼日更常晚于 20:40）。"""
    attempts = int(os.environ.get("L2_SHARE_WAIT_ATTEMPTS", "8"))
    delay = float(os.environ.get("L2_SHARE_WAIT_SECONDS", "180"))
    name = archive_name(date)
    month = month_dir(date)
    meta = load_meta()
    for i in range(attempts):
        try:
            session = pan_session()
            verify_share(session, meta)
            files = share_file_map(session, meta, month)
        except Exception as exc:  # noqa: BLE001 — 分享未上线/目录还没有都算可等
            files = {}
            print(f"share list {month} 失败: {type(exc).__name__}: {exc}", flush=True)
        if name in files:
            print(f"share has {name} size={files[name].get('size')}", flush=True)
            return
        if i + 1 >= attempts:
            break
        print(
            f"分享 {month} 还没有 {name}，{delay:.0f}s 后再看 ({i + 1}/{attempts})",
            flush=True,
        )
        time.sleep(delay)
    raise FileNotFoundError(f"分享 {month} 目录连续 {attempts} 次没有 {name}")


def run_date(date: str) -> None:
    os.environ.setdefault("L2_SOURCE", "baidu-share:xianyu-l2-7z")
    day = yyyymmdd(date)
    name = archive_name(date)
    try:
        if already_complete(date):
            print(f"{date} l2-moneyflow 已 complete，跳过", flush=True)
            return
        archive = cache_dir() / name
        try:
            wait_share_file(date)
            transferred = ensure_transferred(name, month_dir(date))
            size = int(transferred["file"]["size"])
            inbox = transferred["inbox"].rstrip("/")
            download(name, size, dest=archive, pan_file=f"{inbox}/{name}")
            process_date(date, archive)
        except Exception as exc:
            mark_failed(date, f"file pipeline failed: {exc}")
            print(f"FAIL {date}，退出时清理本地下载包，重试需重新下载", flush=True)
            raise
        meta = transferred["meta"]
        meta["last_processed"] = date
        meta["last_file"] = name
        meta["updated_at"] = date
        write_meta(meta)
    finally:
        cleanup_local(day)
    print(f"done {date}", flush=True)


def _exit_on_sigterm(signum, frame) -> None:
    # Unwind through run_date's finally block on normal process termination.
    raise SystemExit(128 + signum)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("用法: run_l2_from_share.py YYYY-MM-DD")
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    run_date(sys.argv[1])


if __name__ == "__main__":
    main()
