#!/usr/bin/env python3
"""拉取端：扫描一个「同步目录」，把里面还没导入过的单日增量包按日期顺序自动合并进本地 DuckDB。

配合云盘/对象存储用：Mac 复盘后把 `mfs-delta-<date>.zip` 写进一个会自动同步的文件夹
（iCloud Drive / 坚果云 / Dropbox 的本地目录，或 rclone 挂载的对象存储），另一台电脑上的
这个文件夹会自动出现新包；本脚本（手动或用 cron/launchd 定时跑）扫描该目录，按日期从旧到新
把没应用过的包 import 进本地库。

为什么这样设计（教学 / 技术选型）：
- 「同步文件夹」抽象：iCloud/坚果云/Dropbox 在本地都表现为一个普通目录，操作系统后台自动收发，
  所以推送=往目录里 cp 文件、拉取=扫目录，两端都**零凭证、零运维**。对象存储（S3/R2/OSS）可用
  rclone 挂载成同样的本地目录，脚本无需改动——这就是「面向文件夹」抽象的好处（可移植）。
- 幂等 + 状态文件：import 本身按 trade_date 先删后插，天然幂等；这里再记一个 state（已应用文件名），
  只是为了避免重复劳动、加速扫描。即使 state 丢了，重导也不会出错。
- 复用而非重写：直接子进程调用同目录的 `db_delta_import.py`，合并逻辑只有一份来源，便于维护。

可复用知识点：「落地目录 + 状态游标 + 幂等应用」是增量管道/CDC 消费端的通用骨架，
日志摄取、对账文件处理、离线特征同步都能套。
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPORT_SCRIPT = os.path.join(HERE, "db_delta_import.py")
PAT = re.compile(r"mfs-delta-(\d{4}-\d{2}-\d{2})\.zip$")


def main() -> int:
    ap = argparse.ArgumentParser(description="扫描同步目录、自动导入未应用的单日增量包")
    ap.add_argument("--sync-dir", required=True, help="存放 mfs-delta-*.zip 的同步文件夹")
    ap.add_argument("--db", default="db/market_feature_store.duckdb")
    ap.add_argument("--state", default=None, help="已应用记录（默认 <db>.delta_applied.json）")
    ap.add_argument("--dry-run", action="store_true", help="只列出将导入的包，不写库")
    ap.add_argument("--reapply", action="store_true", help="忽略 state，重新应用所有包（幂等）")
    a = ap.parse_args()

    if not os.path.isdir(a.sync_dir):
        print(f"[err] 同步目录不存在: {a.sync_dir}", file=sys.stderr); return 2
    if not os.path.exists(a.db):
        print(f"[err] 目标 DB 不存在: {a.db}（请先用整库快照建底库）", file=sys.stderr); return 2

    state_path = a.state or (a.db + ".delta_applied.json")
    applied: set[str] = set()
    if os.path.exists(state_path) and not a.reapply:
        try:
            applied = set(json.load(open(state_path)))
        except Exception:
            applied = set()

    found = []
    for fn in os.listdir(a.sync_dir):
        m = PAT.search(fn)
        if m:
            found.append((m.group(1), fn))
    found.sort()  # 按日期升序（从旧到新）

    todo = [(d, fn) for d, fn in found if fn not in applied]
    if not todo:
        print(f"[*] 同步目录共 {len(found)} 个增量包，无新包需导入。")
        return 0

    print(f"[*] 待导入 {len(todo)} 个（共 {len(found)} 个）：" + ", ".join(d for d, _ in todo))
    for d, fn in todo:
        zp = os.path.join(a.sync_dir, fn)
        cmd = [sys.executable, IMPORT_SCRIPT, "--zip", zp, "--db", a.db]
        if a.dry_run:
            cmd.append("--dry-run")
        print(f"\n=== {d} ({fn}) ===")
        rc = subprocess.run(cmd).returncode
        if rc != 0:
            print(f"[err] 导入 {fn} 失败 (rc={rc})，停止以保持顺序。", file=sys.stderr)
            return rc
        if not a.dry_run:
            applied.add(fn)
            json.dump(sorted(applied), open(state_path, "w"), ensure_ascii=False, indent=2)

    print(f"\n[ok] {'(dry-run) ' if a.dry_run else ''}处理完成，状态记于 {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
