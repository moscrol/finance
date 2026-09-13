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

import hashlib
import json
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, NamedTuple

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


class SwapTargetReplacedError(DatabaseLockedError):
    """换库目标的**路径身份**（st_dev + st_ino）与协调时锁定的那个不一致，
    或目标已整个消失。

    QC 复审四轮（2026-09-13）：flock 锁的是 inode，而检查与 os.replace 走的
    是路径。有人把另一个文件换到该路径上时，我们锁住的是旧 inode，要覆盖的
    却是新路径对象。四处（拿锁/开锁失败、拿锁瞬间、克隆后基线、换名前最后
    一刻）各查一次身份，查到就 fail closed。

    **能做到什么、做不到什么见本文件顶部「换库威胁模型」**：对非协同方
    （不拿锁的 mv/cp）这是检测不是保证，检查与换名之间的窗口关不掉。

    继承 DatabaseLockedError 是刻意的：既有调用方的 `except
    DatabaseLockedError` 会把它变成明确的 rc=2 拒绝，而不是让异常逃逸出编排
    （QC 复审三轮 P2 已定的口径：拒绝要有出口码，不能靠 traceback）。
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
#
# 换库威胁模型（单一口径；别在别处再写第二份，下面各 docstring 只引不抄）：
#
# 【协同方】= 走 hold_run_mutex / hold_swap_lock / duckdb 文件锁的写者。
#   对他们「最终复查→[备份]→原子换名」全程在 SH 锁内，排他是**保证**。
#   本仓所有写者都是协同方。
#
# 【非协同方】= 不拿任何锁、直接动生产路径的 mv / cp / dd（人手操作或外部
#   工具）。对他们我们只能**检测，不能保证**，原因是 POSIX 没有「比对 inode
#   再换名」的原子原语：
#     - os.replace 不带条件；macOS renamex_np(RENAME_SWAP) 只保证交换本身
#       原子，照样会跟冒名者交换；RENAME_EXCL 只判「存在与否」，判不了
#       「是不是我锁的那个 inode」；Linux renameat2 同理。
#     - 所以 assert_same_target 与 os.replace 之间必然留一道窗口（两条相邻
#       语句 + 一次 syscall）。整文件替换发生在检查**之前** → 拒绝；发生在
#       检查之后、换名之前 → 仍会覆盖冒名者。
#     - 裸字节直写（cp/dd 写进同一个 inode）连身份都不变，身份校验更看不见。
#   后一种由 test_identity_check_and_replace_are_not_atomic 钉住：它是**已声明
#   的边界**，不是未知漏洞。要真闭合只能把所有发布方收编进同一把协调锁，
#   再加一次 stat 是没用的。
#
# 因此措辞纪律：身份校验可以说「把非协同方的整文件替换从静默覆盖变成可检测
# 的拒绝」，**不能**说「已覆盖 / 已闭合 / 不再靠假设排除」。
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


def file_identity(db_path: Path) -> tuple[int, int]:
    """文件的路径身份 (st_dev, st_ino)——跨换名唯一标识一个 inode。

    size/mtime 只是「版本」，识别不了身份：cp -c / shutil.copy2 会把 mtime
    一并带过去，换个 inode 而版本完全一致的文件是可以造出来的。
    """
    st = os.stat(db_path)
    return (st.st_dev, st.st_ino)


class SwapLock(NamedTuple):
    """hold_swap_lock 的把手: 被锁 inode 的身份 + 它的 fd。

    给出 fd 是为了让调用方能 stat **被锁的那个 inode 本身**而不是再走一次
    路径——路径 stat 拿到的可能已经是别人换上来的文件 (QC 复审五轮)。
    fd 的生命周期归 hold_swap_lock, 调用方不要 close。
    """

    dev: int
    ino: int
    fd: int

    @property
    def identity(self) -> tuple[int, int]:
        return (self.dev, self.ino)

    def stat(self) -> os.stat_result:
        """被锁 inode 自身的 stat (fstat), 不经路径, 没有「stat 完被换路径」的窗口。"""
        return os.fstat(self.fd)


def assert_same_target(db_path: Path, expected: tuple[int, int], *, stage: str) -> None:
    """确认 db_path 此刻仍解析到 expected 那个 inode, 否则 SwapTargetReplacedError。

    stage 只进异常消息, 用来指认是哪一处守卫发现的身份漂移 (开锁 / 拿锁瞬间 /
    克隆后基线 / 换名前最后一刻), 便于事后定位替换发生的窗口。

    注意这是**检测**: 返回之后到调用方真正动手之间仍有窗口, 见文件顶部威胁模型。
    """
    try:
        actual = file_identity(db_path)
    except FileNotFoundError as exc:
        raise SwapTargetReplacedError(
            f"{stage}: 换库目标 {db_path} 已不存在 (协调时身份 {expected})"
        ) from exc
    if actual != expected:
        raise SwapTargetReplacedError(
            f"{stage}: 换库目标 {db_path} 的路径身份已变 "
            f"(dev,ino {expected} -> {actual}), 疑似被第三方整文件替换; 拒绝继续"
        )


def atomic_swap_into_place(
    staging: Path, target: Path, *, expect_identity: tuple[int, int] | None = None
) -> None:
    """os.replace 把 staging 原子换名为 target。

    前置断言 (fail closed):
    - staging 存在且无残留 WAL——写者收笔后 duckdb close 会 checkpoint,
      仍有 WAL 说明 staging 没有干净关闭, 换过去会让生产端做恢复重放;
    - target 无 WAL——生产路径出现 WAL 说明有第三方写者在写/刚崩溃,
      此时换名会覆盖它的工作, 必须人工裁决;
    - expect_identity 给定时, os.replace 前最后一刻复查 target 的
      (st_dev, st_ino)——调用方锁的 inode 与此刻被覆盖的必须是同一个
      (QC 复审四轮: 锁 inode 而按路径换名, 中间被换路径就覆盖了别人)。
      **这一查与 os.replace 不是一个原子操作**: 检查之后、换名之前被换上
      来的冒名者仍会被覆盖, 见文件顶部威胁模型与
      test_identity_check_and_replace_are_not_atomic。它把「替换发生在检查
      之前」这一类从静默覆盖变成明确拒绝, 仅此而已。

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
    if expect_identity is not None:
        assert_same_target(target, expect_identity, stage="换名前最后一刻")
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


def backup_before_swap(
    db_path: Path, *, run_id: str, writer_lock_held: bool = False
) -> dict:
    """换名前给 target 留一份可验明备份——换库成功后还能恢复旧状态。

    与 staging 克隆的分工：staging 防「副本失败污染生产」，本备份防
    「换库成功后回滚无门」（os.replace 不留旧库）。QC S4（2026-09-13）
    把此项列为正式换库的执行前提：备份路径、验证指纹、无活跃写者检查、
    恢复步骤，四样都要可验明。

    顺序：写者探针（此刻无 rw 写者才拷，否则快照是撕裂的）→ clonefile
    同卷快照 → sha256 指纹 → read_only 开库验证（备份必须真打得开）→
    落 <backup>.receipt.json（含恢复步骤）。任何一步失败都抛异常，
    由调用方 fail closed（不换名）。

    writer_lock_held=True：调用方已持 hold_swap_lock（覆盖「最终检查→
    备份→换名」全临界区，QC 复审二轮 P1），跳过函数内探针——此时探针
    连自己都会被锁拦下。
    """
    if not writer_lock_held:
        probe_no_active_writer(db_path)
    source_stat = db_path.stat()
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup = db_path.with_name(f"{db_path.name}.bak-{ts}-{run_id}")
    copy_info = clone_to_staging(db_path, backup)

    digest = hashlib.sha256()
    with backup.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    sha = digest.hexdigest()

    con = duckdb.connect(str(backup), read_only=True)
    try:
        table_count = len(list_tables(con))
    finally:
        con.close()
    if table_count == 0:
        raise RuntimeError(f"备份可读性校验失败（0 张表）: {backup}")

    receipt = {
        "kind": "pre-swap-backup",
        "run_id": run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_db": str(db_path),
        "source_size_bytes": source_stat.st_size,
        "source_mtime_ns": source_stat.st_mtime_ns,
        "backup_path": str(backup),
        "backup_sha256": sha,
        "backup_bytes": backup.stat().st_size,
        "copy_method": copy_info["method"],
        "readability_check": f"read_only 打开成功, {table_count} 张表",
        "restore_steps": [
            "1. 确认无活跃写者/读者（probe_no_active_writer 或 lsof）",
            f"2. 校验备份指纹: shasum -a 256 {backup.name} 应等于 receipt 的 backup_sha256",
            f"3. 若 target 处有残留 WAL 先删除: {db_path.name}.wal",
            f"4. cp -c {backup.name} {db_path.name}（同卷 clonefile；跨卷用 cp）",
            "5. 只读打开 target 抽查行数，确认恢复完成后再让读写方上线",
            "6. 验证通过后备份可人工删除（3.6G 量级，别长期留）",
        ],
    }
    receipt_path = Path(str(backup) + ".receipt.json")
    receipt_path.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


@contextmanager
def hold_swap_lock(db_path: Path):
    """换库锁：对 target inode 持 LOCK_SH|LOCK_NB——排写不排读。

    duckdb 的单写者独占用 flock 实现（本机 2026-09-13 三向实测：我方 SH
    下 duckdb rw 打开失败、read_only 照常；duckdb rw 持锁时我方 SH 得
    EWOULDBLOCK；read_only 读者不挡我方 SH）。SH 已足以排他全部 duckdb
    写者（他们要 EX），同时不挡只读探针与读者（S7 判据 1）。

    两个窗口都用它：
    - 基线窗口（QC 复审三轮 P1）：克隆与来源版本基线必须在同一受保护
      窗口内建立，否则克隆之后才认领来源最新 stat，会把「副本不含的新
      写入」记成副本基线（QC 复现：克隆 10000→窗口内提交 17000→换入
      10000）。SH 罩住克隆时，克隆内部的 read_only 探针照常工作。
    - 换库临界区（QC 复审二轮 P1 + 四轮 P1）：「最终复查→[备份]→原子
      换名」全程排写，第三方写者进不来；读者持旧 inode 不受影响。**与
      是否备份无关**——日更不备份也必须在锁内换名，否则「守卫通过」到
      「os.replace」之间仍是裸窗口（四轮复现：窗口内提交 17000 → rc=0
      swapped=true → 新库不含 17000，写入被静默覆盖）。

    yield 一个 SwapLock（被锁 inode 的 dev/ino + fd）：flock 锁 inode、检查
    与换名走路径，中间隔着一次「路径可能被换掉」的风险。调用方拿 .identity
    去复查路径、拿 .stat() 读被锁 inode 自身的版本（别再走路径 stat）。拿锁
    瞬间本函数先自查一次：open 与 flock 之间被换路径的，当场拒绝。

    拿不到锁立刻 DatabaseLockedError，不在临界区门口等长事务。开锁时目标已
    不存在 → SwapTargetReplacedError（不是裸 FileNotFoundError）：编排的
    fail-closed 合同要求拒绝带出口码，不能靠 traceback（QC 复审五轮 P2）。

    **身份校验能做到什么、做不到什么见本文件顶部「换库威胁模型」**：对协同方
    是保证，对不拿锁的 mv/cp 只是检测。
    """
    import fcntl

    try:
        fd = os.open(db_path, os.O_RDONLY)
    except FileNotFoundError as exc:
        raise SwapTargetReplacedError(
            f"换库锁开锁失败: 目标 {db_path} 已不存在（疑似被第三方移走或删除）"
        ) from exc
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except OSError as exc:
            raise DatabaseLockedError(
                f"{db_path} 换库锁被占用（疑似第三方写者）: {exc}"
            ) from exc
        locked = os.fstat(fd)
        lock = SwapLock(locked.st_dev, locked.st_ino, fd)
        assert_same_target(db_path, lock.identity, stage="换库锁拿锁瞬间")
        yield lock
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def hold_run_mutex(db_path: Path):
    """同一 target 的 staging 编排运行互斥锁，覆盖一轮的完整生命周期。

    QC 复审三轮 P1：两轮父进程共用同一 staging 路径时，B 会把 A 尚未发布
    的 staging 当旧残留删掉重建，A 恢复后发布的「同名 staging」已是 B 的
    失败半成品（连 A 写进 staging 的收据一起没了）。状态属于本轮 ≠ 最终
    发布的文件仍属于本轮——必须在任何清理之前取得互斥，覆盖到换名/放弃。

    锁在独立文件 <db>.run.lock 上：不碰 duckdb 的锁命名空间，读者与写者
    完全无感；进程死亡（含 SIGKILL）由 OS 释放，下一轮正常接管并清理
    残留。锁文件常驻不删（删锁文件本身有竞态）。
    """
    import fcntl

    lock_path = Path(str(db_path) + ".run.lock")
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DatabaseLockedError(
                f"另一轮 staging 编排持有 {lock_path.name} 运行互斥锁: {exc}"
            ) from exc
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
