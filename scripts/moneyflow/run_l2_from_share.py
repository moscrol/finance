"""夜跑入口：分享转存 → 分片下载 → 解算入库 → 删本地 7z。不打 ClickHouse。"""
from __future__ import annotations

import os
import shutil
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

STEPS = ("limitup", "top100", "quant")


def already_complete(date: str) -> bool:
    import duckdb
    from config import DUCKDB_PATH

    if os.environ.get("L2_FORCE_RESCAN", "").strip() in {"1", "true", "yes"}:
        return False
    con = duckdb.connect(DUCKDB_PATH, read_only=True)
    try:
        rows = con.execute(
            "SELECT step, status FROM ops_pipeline_run_daily "
            "WHERE trade_date=? AND pipeline='l2-moneyflow'",
            [date],
        ).fetchall()
    finally:
        con.close()
    got = {row[0]: row[1] for row in rows}
    return all(got.get(step) == "complete" for step in STEPS)


def cleanup_local(day: str) -> None:
    cache = cache_dir()
    for path in (
        cache / f"{day}.7z",
        cache / f"{day}.7z.part",
        cache / f"{day}.7z.part.ok",
        cache / f"extract-{day}",
    ):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
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
    if already_complete(date):
        print(f"{date} l2-moneyflow 已 complete，跳过", flush=True)
        cleanup_local(day)
        return
    wait_share_file(date)
    transferred = ensure_transferred(name, month_dir(date))
    size = int(transferred["file"]["size"])
    inbox = transferred["inbox"].rstrip("/")
    archive = cache_dir() / name
    try:
        download(name, size, dest=archive, pan_file=f"{inbox}/{name}")
        process_date(date, archive)
    except Exception:
        print(f"FAIL {date}，本地 7z 留下便于重试", flush=True)
        raise
    cleanup_local(day)
    meta = transferred["meta"]
    meta["last_processed"] = date
    meta["last_file"] = name
    meta["updated_at"] = date
    write_meta(meta)
    print(f"done {date}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: run_l2_from_share.py YYYY-MM-DD")
    run_date(sys.argv[1])
