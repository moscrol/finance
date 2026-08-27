"""复盘前置闸门: 检测 DuckDB 是否被占锁/残留进程, 快速失败给出清晰提示。

背景: market_feature_store DuckDB 单写锁。若有残留的 daily-full/daily-update 进程
(常见 CPU 0 卡死) 持有写锁, 后续所有同步会长时间无反馈地卡住。本脚本在复盘开始前
尝试拿一次写连接, 锁冲突时解析占锁 PID 并打印进程信息, 返回非零让工作流提前阻断。

用法:
    python3 scripts/check_db_lock.py
退出码: 0=空闲可写; 2=被占锁(打印占锁进程); 1=其他错误。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_feature_store.db import DB_PATH, connect  # noqa: E402

PID_RE = re.compile(r"\(PID\s+(\d+)\)")


def _proc_info(pid: str) -> str:
    try:
        out = subprocess.run(
            ["ps", "-p", pid, "-o", "pid,etime,stat,%cpu,%mem,command", "-ww"],
            capture_output=True, text=True, check=False,
        )
        return out.stdout.strip() or f"(PID {pid} 已不存在)"
    except Exception as exc:  # noqa: BLE001
        return f"(无法读取 PID {pid} 信息: {exc})"


def _default_feishu_alert(text: str) -> bool:
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from notify_feishu import send_alert

    return send_alert(text)


def _alert_production_blocked(holder: str, *, alerter=None) -> None:
    """生产库被占锁时飞书告一声；staging 自检不告（夜跑自己持 staging 锁是常态）。

    告警失败不得改变退出码——锁检测本身才是这道门的产品。
    """
    from market_feature_store.write_path import is_canonical_production

    if not is_canonical_production(DB_PATH):
        return
    send = alerter or _default_feishu_alert
    send(f"⚠️ 生产库被占用：{holder} held exclusive DuckDB lock ({DB_PATH})")


def main() -> int:
    if not DB_PATH.exists():
        print(f"DB-LOCK OK: 数据库尚不存在, 可写 ({DB_PATH})")
        return 0
    try:
        con = connect()
        con.close()
        print(f"DB-LOCK OK: {DB_PATH} 当前可写, 无锁冲突")
        return 0
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        m = PID_RE.search(msg)
        print("DB-LOCK BLOCKED: DuckDB 写锁被占用, 复盘同步会卡住")
        print(f"  db: {DB_PATH}")
        holder = msg
        if m:
            pid = m.group(1)
            info = _proc_info(pid)
            holder = info or f"PID {pid}"
            print(f"  占锁进程 PID={pid}:")
            print("    " + info.replace("\n", "\n    "))
            print(f"  若确认是残留卡死进程, 先终止再重跑: kill -TERM {pid}")
        else:
            print(f"  原始错误: {msg}")
        try:
            _alert_production_blocked(holder)
        except Exception:  # noqa: BLE001
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
