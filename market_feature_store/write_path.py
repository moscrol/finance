"""写入路径策略：生产库不是默认可写目标。

2026-08-20：脏树上的旧 `cli daily-full` 直写生产 fact、不算 features。
gitea/main 上 `daily-full` 已走 staging 换名；剩下的逃生舱是
`daily-update` 和手跑 `daily-full-exec` 且 MARKET_FEATURE_STORE_DB 指向生产。

本模块只回答两件事：这是不是 canonical 生产库？有没有 --direct？
提醒写在 skill 里拦不住人，必须在副作用前 fail closed。

2026-09-13 加固（QC G1）：生产库身份不得随代码检出位置改变。旧实现
用包所在目录推导 canonical 路径——从独立 worktree 跑代码时，主检出树
里的真生产库被误判成普通副本，--child --db <真库> 能直达写入函数
（替换写入函数探针实证，未写生产）。现在 canonical 身份取候选集：
包相对路径 ∪ 主检出树路径（git common dir 解析，worktree 共享同一
.git）∕ env 显式钉（MARKET_FEATURE_STORE_PRODUCTION_DB）。
"""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from .db import DB_PATH, PROJECT_DIR, connect

CANONICAL_DB_NAME = "market_feature_store.duckdb"
DIRECT_RECEIPT_DIR = PROJECT_DIR / "skills" / "daily-full-review" / "state"

_OPS_SYNC_RUN_DDL = """
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


def canonical_production_path() -> Path:
    return (PROJECT_DIR / "db" / CANONICAL_DB_NAME).resolve()


def _main_checkout_dir() -> Path | None:
    """本 clone 家族的主检出树：worktree 共享同一个 git common dir。

    生产库住在主检出树的 db/ 下（AGENTS.md 数据契约），而代码可以在任何
    附属 worktree 里跑。`git rev-parse --git-common-dir` 从任何 worktree
    都解析回主树的 .git，dirname 即主树根——生产库身份由此与检出位置
    脱钩。解析失败（非 git 环境 / 无 git）返回 None，候选集退化为
    包相对路径 ∪ env 钉，不会让非生产路径被误判成生产。
    """
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    if not out:
        return None
    return Path(out).resolve().parent


def canonical_production_candidates() -> frozenset[Path]:
    """canonical 生产库的全部候选绝对路径（检出位置无关）。

    - 包相对路径：代码就在主检出树里跑时的常态。
    - 主检出树路径：代码在附属 worktree 里跑时，真生产库仍被认出（G1）。
    - MARKET_FEATURE_STORE_PRODUCTION_DB：跨 clone（独立克隆跑代码写主仓
      库）时的显式钉；调用期读 env，不做 import 期捕获。
    """
    candidates = {canonical_production_path()}
    main = _main_checkout_dir()
    if main is not None:
        candidates.add((main / "db" / CANONICAL_DB_NAME).resolve())
    pinned = os.environ.get("MARKET_FEATURE_STORE_PRODUCTION_DB")
    if pinned:
        candidates.add(Path(pinned).expanduser().resolve())
    return frozenset(candidates)


def is_canonical_production(path: Path | str | None = None) -> bool:
    """目标是否为 canonical 生产库（不是 .staging、不是测试库、不是克隆）。"""
    target = Path(path) if path is not None else DB_PATH
    try:
        return target.expanduser().resolve() in canonical_production_candidates()
    except OSError:
        return False


def production_write_blocked(direct: bool, path: Path | str | None = None) -> str | None:
    """允许写则返回 None；拦下则返回给人看的拒绝理由。"""
    if not is_canonical_production(path):
        return None
    if direct:
        return None
    return (
        "拒绝直写生产库 db/market_feature_store.duckdb。"
        "正门：python3 skills/daily-full-review/scripts/run_review_sync.py --date YYYY-MM-DD"
        "（或 python3 -m market_feature_store.cli daily-full，走 staging 换名）。"
        "急救直写必须显式加 --direct，并会写 ops_sync_run / state/direct-write-*.json 收据。"
    )


def write_direct_receipt(
    *,
    trade_date: str | None,
    command: str,
    ok: bool,
    started_at: datetime | None = None,
    extra: dict | None = None,
) -> Path:
    """--direct 写入的最低审计：先落 JSON，再尽力写 ops_sync_run。"""
    run_id = uuid.uuid4().hex[:12]
    finished = datetime.now()
    started = started_at or finished
    payload = {
        "run_id": run_id,
        "kind": "cli-direct",
        "plan": "direct-prod",
        "trade_date": trade_date,
        "command": command,
        "ok": ok,
        "pid": os.getpid(),
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "db": str(DB_PATH),
        "extra": extra or {},
    }
    DIRECT_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = DIRECT_RECEIPT_DIR / f"direct-write-{trade_date or 'unknown'}-{run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        con = connect()
        try:
            con.execute(_OPS_SYNC_RUN_DDL)
            con.execute(
                """
                INSERT INTO ops_sync_run
                    (run_id, kind, plan, trade_date, started_at, finished_at,
                     duration_s, ok, pid, child_pid, copy_method, copy_seconds,
                     source_bytes, rows_summary, steps_summary)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                [
                    run_id,
                    "cli-direct",
                    "direct-prod",
                    trade_date,
                    started,
                    finished,
                    round((finished - started).total_seconds(), 1),
                    ok,
                    os.getpid(),
                    None,
                    None,
                    None,
                    None,
                    json.dumps({"receipt": str(path)}, ensure_ascii=False),
                    json.dumps({"command": command}, ensure_ascii=False),
                ],
            )
        finally:
            con.close()
    except Exception:
        # JSON 收据已在；库表是加分项，写失败不得把急救路径再砸一遍。
        pass
    return path
