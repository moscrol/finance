"""DuckDB 连接与初始化助手。

数据库文件默认位于 PROJECT_DIR/db/ 下, 已被 .gitignore 忽略, 不入库。
schema.sql 与本模块同目录, 可重复执行 (全部 CREATE ... IF NOT EXISTS)。

可移植性: 数据库路径可用环境变量 MARKET_FEATURE_STORE_DB 覆盖, 便于在
不同机器 / 自定义目录 / 样本库自测时切换, 不必把库放在仓内 db/ 下。
未设置时回退到 PROJECT_DIR/db/market_feature_store.duckdb (与原行为一致)。

staging 换库 (2026-08-15, bookgap S7): 长事务同步全程持生产库写锁会把
生产端 read_only 短连接饿死 (实测锁窗 ≥14min, 批 #2 A 组全灭)。处方是
同步写 staging 副本、收笔后 os.replace 原子换名——本模块提供路径推导、
克隆与换名三个工具, 编排在 sync.sync_daily_full.run_daily_full_staged。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import duckdb

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
_ENV_DB = os.environ.get("MARKET_FEATURE_STORE_DB")
DB_PATH = Path(_ENV_DB).expanduser() if _ENV_DB else PROJECT_DIR / "db" / "market_feature_store.duckdb"
DB_DIR = DB_PATH.parent
SCHEMA_PATH = PACKAGE_DIR / "schema.sql"

# duckdb 对文件锁冲突只给 IOException + 消息文本，没有专用异常类型；
# 两个片段分别覆盖「拿不到锁」与「谁在持锁」两种措辞，缩窄误判面。
_LOCK_CONFLICT_MARKERS = ("Could not set lock", "Conflicting lock")


class DatabaseLockedError(RuntimeError):
    """只读诊断连接在重试窗口内始终拿不到 duckdb 文件锁。

    语义：库文件被写进程（通常是 sync/backfill）独占，检查**没有执行**——
    调用方必须把它与「检查执行了但数据不完整」区分开，不得混报。
    """


def is_lock_conflict(exc: BaseException) -> bool:
    """该异常是否为 duckdb 文件锁冲突（可等待重试），而非其他 IO 故障。"""
    return isinstance(exc, duckdb.IOException) and any(
        marker in str(exc) for marker in _LOCK_CONFLICT_MARKERS
    )


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """打开 DuckDB 连接。非只读模式会确保 db 目录存在。"""
    if not read_only:
        DB_DIR.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def connect_read_only_with_retry(
    *,
    attempts: int = 6,
    delay_seconds: float = 10.0,
    opener: Callable[[], duckdb.DuckDBPyConnection] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> duckdb.DuckDBPyConnection:
    """只读连接 + 文件锁有界重试；等不到锁时抛 DatabaseLockedError。

    供只读诊断类调用方（质检闸门等）使用：夜间 sync/backfill 持写锁是常态，
    直接 connect 会当场炸 IOException，被外层误报成「数据不完整」。这里
    在有界窗口内等写进程收工；非锁类 IOException 原样抛出，不掩盖真故障。

    opener 可注入是为了让调用方保留自己模块级的 connect 绑定
    （既有测试靠 monkeypatch 那个符号换假库），默认走本模块 connect。
    """
    if attempts < 1:
        raise ValueError(f"attempts 必须 >= 1，得到 {attempts}")
    open_connection = opener or (lambda: connect(read_only=True))
    last_error: duckdb.IOException | None = None
    for attempt in range(attempts):
        try:
            return open_connection()
        except duckdb.IOException as exc:
            if not is_lock_conflict(exc):
                raise
            last_error = exc
            if attempt + 1 < attempts:
                sleep(delay_seconds)
    waited = delay_seconds * (attempts - 1)
    raise DatabaseLockedError(
        f"duckdb 文件锁持续被占用：重试 {attempts} 次（约 {waited:.0f}s）仍未拿到"
        f"只读锁；最后错误：{last_error}"
    ) from last_error


def init_db(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """由 SectorUniverseStore.ensure_schema() 统一装载 schema 并完成代际迁移。

    2026-08-02 合 main 后，两张 sector 事实表的 VIEW 定义也进了 schema.sql
    （main a5321eec，与生产库 37 个对象逐一校验）。于是**顺序变成硬约束**：
    必须先把遗留的 BASE TABLE 改名，才能建同名 VIEW，否则 DuckDB 报
    「Existing object fact_sector_daily is of type Table, trying to replace
    with type View」。

    ensure_schema() 内部就是这个顺序（改名 → 重放 schema.sql 全文 → 拷贝遗留行），
    且无条件重放，所以这里不能再先跑一遍 schema.sql——那正好会踩在改名之前。
    """
    from .sector_universe import SectorUniverseStore

    own = con is None
    if own:
        con = connect()
    try:
        SectorUniverseStore.ensure_schema(con)
    finally:
        if own:
            con.close()


def get_published_snapshot_id(con: duckdb.DuckDBPyConnection, trade_date: str) -> str:
    """获取某交易日已发布的 sector_universe_snapshot_id。

    fact_sector_daily / fact_sector_stock_daily 已重构为视图，
    底层 *_generation 表需要 snapshot_id 作为主键的一部分。
    如果当天没有 published 快照，回退到 'legacy'。
    """
    row = con.execute(
        """
        SELECT snapshot_id FROM ops_sector_universe_snapshot_daily
        WHERE trade_date = ? AND status = 'published'
        ORDER BY captured_at DESC LIMIT 1
        """,
        [trade_date],
    ).fetchone()
    return row[0] if row else "legacy"


def list_tables(con: duckdb.DuckDBPyConnection) -> list[str]:
    """返回 main schema 下全部表名 (按名称排序)。"""
    rows = con.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
        """
    ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# staging 写 + 原子换名 (bookgap S7)
# ---------------------------------------------------------------------------

STAGING_SUFFIX = ".staging"


def staging_path(db_path: Path | None = None) -> Path:
    """同步用 staging 副本路径: 与目标库同目录 (同卷才保证 os.replace 原子)。"""
    target = Path(db_path) if db_path is not None else DB_PATH
    return target.with_name(target.name + STAGING_SUFFIX)


def wal_path(db_path: Path) -> Path:
    """duckdb 的 WAL 伴生文件路径 (<db>.wal)。"""
    return Path(str(db_path) + ".wal")


def clone_to_staging(source: Path, staging: Path) -> dict:
    """把 source 库克隆成 staging 副本, 返回 {method, seconds, bytes}。

    优先 APFS clonefile (`cp -c`): 同卷 COW 克隆是单个 syscall, 秒级完成、
    初始零额外磁盘占用, 且相对文件系统是原子快照。非 APFS/非 macOS 退回
    shutil.copy2 (3.4G 实测约几十秒, 磁盘峰值 2×库大小)。

    source 若带 WAL (上一个写者崩溃留下), 一并按 staging 命名克隆——
    duckdb 打开 staging 时自动重放, 不丢已提交事务。
    """
    started = time.monotonic()
    method = "clonefile"
    try:
        subprocess.run(
            ["cp", "-c", str(source), str(staging)],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        method = "copy"
        shutil.copy2(source, staging)
    source_wal = wal_path(source)
    if source_wal.exists():
        shutil.copy2(source_wal, wal_path(staging))
    return {
        "method": method,
        "seconds": round(time.monotonic() - started, 3),
        "bytes": source.stat().st_size,
    }


def probe_no_active_writer(db_path: Path) -> None:
    """确认 db_path 当前没有 rw 写者; 有则抛 DatabaseLockedError。

    机制: duckdb 单写者独占——存在 rw 连接时 read_only 打开立即
    IOException(锁冲突)。探针本身只做 read_only 开/关, 不取写锁,
    不会反过来饿死生产读者。文件不存在视为无写者。
    """
    if not db_path.exists():
        return
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except duckdb.IOException as exc:
        if is_lock_conflict(exc):
            raise DatabaseLockedError(
                f"{db_path} 存在活跃写者 (read_only 探针拿不到锁): {exc}"
            ) from exc
        raise
    con.close()


def atomic_swap_into_place(staging: Path, target: Path) -> None:
    """os.replace 把 staging 原子换名为 target。

    前置断言 (fail closed):
    - staging 存在且无残留 WAL——写者收笔后 duckdb close 会 checkpoint,
      仍有 WAL 说明 staging 没有干净关闭, 换过去会让生产端做恢复重放;
    - target 无 WAL——生产路径出现 WAL 说明有第三方写者在写/刚崩溃,
      此时换名会覆盖它的工作, 必须人工裁决。

    POSIX rename 语义: 已打开旧文件的读者继续读旧 inode (安全),
    新连接读新文件; 旧文件空间在最后一个句柄释放后归还。
    """
    if not staging.exists():
        raise FileNotFoundError(f"staging 副本不存在: {staging}")
    staging_wal = wal_path(staging)
    if staging_wal.exists():
        raise RuntimeError(
            f"staging 带未 checkpoint 的 WAL ({staging_wal}), 拒绝换名——"
            "写者未干净关闭"
        )
    if wal_path(target).exists():
        raise RuntimeError(
            f"生产路径存在 WAL ({wal_path(target)}), 疑似第三方写者, 拒绝换名"
        )
    os.replace(staging, target)


def remove_stale_staging(staging: Path) -> bool:
    """清掉上一轮崩溃残留的 staging (含 WAL); 有清理动作返回 True。

    staging 语义上是一次性中间产物: 收据从未写入、生产库未动,
    残留文件只占磁盘, 开新一轮前直接丢弃。
    """
    removed = False
    for leftover in (staging, wal_path(staging)):
        if leftover.exists():
            leftover.unlink()
            removed = True
    return removed
