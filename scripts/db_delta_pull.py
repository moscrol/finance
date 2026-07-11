#!/usr/bin/env python3
"""拉取端：先按需恢复全量基线，再把未导入的单日增量按日期顺序合并进本地 DuckDB。

配合云盘/对象存储用：Mac 复盘后把 `mfs-delta-<date>.zip` 写进一个会自动同步的文件夹
（iCloud Drive / 坚果云 / Dropbox 的本地目录，或 rclone 挂载的对象存储），另一台电脑上的
这个文件夹会自动出现新包；本脚本（手动或用 cron/launchd 定时跑）扫描该目录。目标库缺失时，
先恢复最新 ``mfs-baseline-YYYY-MM-DD.zip``，再按日期从旧到新导入没应用过的增量。

为什么这样设计（教学 / 技术选型）：
- 「同步文件夹」抽象：iCloud/坚果云/Dropbox 在本地都表现为一个普通目录，操作系统后台自动收发，
  所以推送=往目录里 cp 文件、拉取=扫目录，两端都**零凭证、零运维**。对象存储（S3/R2/OSS）可用
  rclone 挂载成同样的本地目录，脚本无需改动——这就是「面向文件夹」抽象的好处（可移植）。
- 幂等 + fail-closed 状态文件：import 本身按 trade_date 先删后插，天然幂等；state 记录已应用
  baseline/delta。state 损坏时拒绝按空状态继续，避免悄悄重放大量历史包。
- 全量基线 + 单日增量：基线解决新机器建库/灾难恢复，增量解决日常低成本同步；这是数据库备份中
  常见的「full + incremental」组合，比每天传整库省带宽，也比只有增量更可恢复。
- 复用而非重写：直接子进程调用同目录的 `db_delta_import.py`，合并逻辑只有一份来源，便于维护。

可复用知识点：「落地目录 + 状态游标 + 幂等应用」是增量管道/CDC 消费端的通用骨架，
日志摄取、对账文件处理、离线特征同步都能套。
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import duckdb

try:
    from scripts import db_delta_import as delta_import
except ImportError:  # pragma: no cover
    import db_delta_import as delta_import

HERE = os.path.dirname(os.path.abspath(__file__))
IMPORT_SCRIPT = os.path.join(HERE, "db_delta_import.py")
PAT = re.compile(r"mfs-delta-(\d{4}-\d{2}-\d{2})\.zip$")
BASELINE_PAT = re.compile(r"mfs-baseline-(\d{4}-\d{2}-\d{2})\.zip$")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_extract(zip_path: str, dest: str) -> None:
    dest_real = os.path.realpath(dest)
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            if os.path.isabs(name) or name.startswith(("/", "\\")) or (len(name) >= 2 and name[1] == ":"):
                raise RuntimeError(f"baseline zip 含绝对路径成员，拒绝: {name!r}")
            target = os.path.realpath(os.path.join(dest, name))
            if target != dest_real and not target.startswith(dest_real + os.sep):
                raise RuntimeError(f"baseline zip 成员越出解压目录，拒绝: {name!r}")
        archive.extractall(dest)


def restore_baseline(zip_path: str, db_path: str) -> dict:
    tmp = tempfile.mkdtemp(prefix="mfs-baseline-")
    backup = None
    replaced = False
    try:
        _safe_extract(zip_path, tmp)
        manifest_path = os.path.join(tmp, "manifest.json")
        if not os.path.exists(manifest_path):
            raise RuntimeError("baseline 缺少 manifest.json")
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        if manifest.get("schema_version") != 1 or manifest.get("kind") != "full_baseline":
            raise RuntimeError("baseline manifest 必须是 schema_version=1 / kind=full_baseline")
        db_file = manifest.get("db_file")
        if not isinstance(db_file, str) or not db_file.endswith(".duckdb"):
            raise RuntimeError(f"baseline db_file 非法: {db_file!r}")
        src = os.path.realpath(os.path.join(tmp, db_file))
        if not src.startswith(os.path.realpath(tmp) + os.sep) or not os.path.isfile(src):
            raise RuntimeError(f"baseline db_file 不在包内: {db_file!r}")
        if _sha256(src) != manifest.get("sha256"):
            raise RuntimeError("baseline duckdb sha256 不匹配")
        try:
            con = duckdb.connect(src, read_only=True)
            con.execute(
                "select count(*) from information_schema.tables where table_schema='main'"
            ).fetchone()
            schema = delta_import._schema_snapshot(con)
            con.close()
        except Exception as exc:
            raise RuntimeError(f"baseline 不是可读取的 DuckDB: {exc}") from exc
        if schema["hash"] != manifest.get("schema_hash"):
            raise RuntimeError("baseline schema_hash 与 manifest 不匹配")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)) or ".", exist_ok=True)
        if os.path.exists(db_path):
            backup = db_path + ".baseline-rollback"
            shutil.copy2(db_path, backup)
        os.replace(src, db_path)
        replaced = True
        ledger_path = delta_import._append_schema_ledger(db_path, {
            "event": "baseline_restore",
            "trade_date": manifest.get("trade_date"),
            "zip": os.path.basename(zip_path),
            "baseline_schema_version": manifest["schema_version"],
            "schema_hash_after": schema["hash"],
        })
        if backup and os.path.exists(backup):
            os.remove(backup)
        return {
            "baseline": os.path.basename(zip_path),
            "db": db_path,
            "trade_date": manifest.get("trade_date"),
            "schema_hash": schema["hash"],
            "schema_ledger": ledger_path,
        }
    except Exception:
        if backup and os.path.exists(backup):
            os.replace(backup, db_path)
        elif replaced and os.path.exists(db_path):
            os.remove(db_path)
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _load_state(path: str, reapply: bool) -> dict:
    if reapply or not os.path.exists(path):
        return {"applied_deltas": [], "applied_baselines": []}
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        raise RuntimeError(f"state 文件损坏，拒绝按空状态重放: {path}: {exc}") from exc
    if isinstance(payload, list):
        if not all(isinstance(item, str) for item in payload):
            raise RuntimeError(f"旧版 state 必须是文件名字符串列表: {path}")
        return {"applied_deltas": payload, "applied_baselines": []}
    if not isinstance(payload, dict):
        raise RuntimeError(f"state 顶层必须是 object 或旧版 list: {path}")
    payload.setdefault("applied_deltas", [])
    payload.setdefault("applied_baselines", [])
    if not all(isinstance(item, str) for item in payload["applied_deltas"]):
        raise RuntimeError(f"state.applied_deltas 必须是字符串列表: {path}")
    if not all(isinstance(item, str) for item in payload["applied_baselines"]):
        raise RuntimeError(f"state.applied_baselines 必须是字符串列表: {path}")
    return payload


def _write_state(path: str, state: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description="扫描同步目录、自动导入未应用的单日增量包")
    ap.add_argument(
        "--sync-dir",
        required=True,
        help="存放 mfs-baseline-*.zip / mfs-delta-*.zip 的同步文件夹",
    )
    ap.add_argument("--db", default="db/market_feature_store.duckdb")
    ap.add_argument("--state", default=None, help="已应用记录（默认 <db>.delta_applied.json）")
    ap.add_argument("--dry-run", action="store_true", help="只列出将导入的包，不写库")
    ap.add_argument("--reapply", action="store_true", help="忽略 state，重新应用所有包（幂等）")
    a = ap.parse_args()

    if not os.path.isdir(a.sync_dir):
        print(f"[err] 同步目录不存在: {a.sync_dir}", file=sys.stderr)
        return 2
    state_path = a.state or (a.db + ".delta_applied.json")
    try:
        state = _load_state(state_path, a.reapply)
    except RuntimeError as exc:
        print(f"[err] {exc}", file=sys.stderr)
        return 2
    applied: set[str] = set(state.get("applied_deltas") or [])
    applied_baselines: set[str] = set(state.get("applied_baselines") or [])

    found = []
    baselines = []
    for fn in os.listdir(a.sync_dir):
        m = PAT.search(fn)
        if m:
            found.append((m.group(1), fn))
        b = BASELINE_PAT.search(fn)
        if b:
            baselines.append((b.group(1), fn))
    found.sort()  # 按日期升序（从旧到新）
    baselines.sort()

    if not os.path.exists(a.db):
        if not baselines:
            print(f"[err] 目标 DB 不存在: {a.db}（请先放入 mfs-baseline-YYYY-MM-DD.zip）", file=sys.stderr)
            return 2
        bdate, bfn = baselines[-1]
        if a.dry_run:
            print(f"[*] 目标 DB 缺失，将先恢复 baseline {bdate} ({bfn})")
            todo_dates = [date for date, fn in found if fn not in applied]
            if todo_dates:
                print("[*] baseline 后将按序校验增量: " + ", ".join(todo_dates))
            return 0
        else:
            try:
                restored = restore_baseline(os.path.join(a.sync_dir, bfn), a.db)
            except Exception as exc:
                print(f"[err] baseline 恢复失败: {exc}", file=sys.stderr)
                return 2
            applied_baselines.add(bfn)
            state["applied_baselines"] = sorted(applied_baselines)
            _write_state(state_path, state)
            print(f"[*] 已恢复 baseline {restored['trade_date']} ({bfn}) → {a.db}")

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
            state["applied_deltas"] = sorted(applied)
            state["applied_baselines"] = sorted(applied_baselines)
            _write_state(state_path, state)

    print(f"\n[ok] {'(dry-run) ' if a.dry_run else ''}处理完成，状态记于 {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
