#!/usr/bin/env python3
"""审计：同一板块中文名不得**新增**挂到多个 `sector_ts_code` 上。

## 这是什么故障

`fact_sector_daily`（公开 VIEW，预取读口）按 `sector_name` 查。当一个中文名同时
挂在两个供应商代码上、且两者日期区间重叠时，同一天会返回**两行不同的数**。
2026-08-21 生产实测（`docs/verification/2026-08-21-judge-quantity-blindspot.md`）
的完整代价：

    E1 预取行给了模型 2026-07-08 两条：成交额亿=922.49 与 914.5
      → 模型诚实写成区间「约914-922亿」
      → 判官按「不等于任何注册数字」判它编造
      → marker_loss 摘掉两个必填输出，残稿发布

**模型全程没错。** 脏在数据层，代价在答案层，中间隔着四层，靠读答案永远追不回来。

## 为什么不放 pre-commit

撞名由 `daily-full` 写入数据时引入，不由改代码引入——commit 时跑它，拦的是
错的东西。而且 worktree 不带 `db/`（gitignore），放 pre-commit 会天天误红。
本脚本属 `audit_*` 家族：**同步之后跑**，或排查数据可疑时手跑。

## 判据：只拦「新增」，不清算存量

沿用 `layer_audit.py` / `check_path_literals.py` 已验证的棘轮模式。全库现有 128 个
撞名板块、3192 组 (名字,日期) 多行，一次清完既不现实也会把审计变成永久红灯。
存量写进 `sector-name-collisions-baseline.json`（本脚本生成，不手抄），
**新增一个就拦**。

## 为什么读公开 VIEW，不读 `*_generation`

预取走 `fact_sector_daily`。物理表按 `sector_universe_snapshot_id` 分代，同日可
以有 candidate / superseded / published 多行——那是快照机制，不是撞名。2026-08-21
库里有 804 组 (名字,日期) 跨多个 snapshot_id；拿物理表当判据会把分代算进重叠。
`check_sector_fact_access.py` 也禁止名单外文件读物理表。本脚本只读公开 VIEW。

## 为什么按「重叠」而不是「代码个数」

一个名字换过代码（旧代码停、新代码起）是**正常换代**，两段区间不重叠，查任何
一天都只有一行，不产生歧义。真正致命的是**并存**——同一天两个代码都有数据。
所以判据是「同日多行」，不是「代码数 > 1」。这也让正常换代不会误报。

`overlapping_days` 存的是多余行（`count(*) - count(distinct trade_date)`）：
为 0 当且仅当没有同日多行。三代码同一天时该值会大于「有重叠的交易日数」，
棘轮仍正确——多余行增加就是恶化。

退出码：
  0  无新增撞名（或 --update-baseline 已写入，或库不可达而跳过）
  1  发现新增撞名
  2  用法错误
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASELINE_PATH = REPO / "sector-name-collisions-baseline.json"


def _db_path() -> Path | None:
    """库位置。缺库时返回 None——worktree 不带 db/，跳过比误红有用。"""

    env = os.environ.get("MARKET_FEATURE_STORE_DB")
    if env:
        candidate = Path(env).expanduser()
        return candidate if candidate.exists() else None
    for base in (REPO, REPO.parent / "finance-workspace-private"):
        candidate = base / "db" / "market_feature_store.duckdb"
        if candidate.exists():
            return candidate
    return None


def _collisions(db: Path) -> dict[str, dict[str, object]]:
    """名字 → {代码列表, 重叠交易日数}。只收重叠 > 0 的。"""

    import duckdb

    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute(
            """
            select sector_name,
                   count(distinct sector_ts_code) as codes,
                   count(*) as rows_total,
                   count(distinct trade_date) as days
            from fact_sector_daily
            group by 1
            having codes > 1 and rows_total > days
            order by 1
            """
        ).fetchall()
        out: dict[str, dict[str, object]] = {}
        for name, codes, rows_total, days in rows:
            codes_list = [
                str(r[0])
                for r in con.execute(
                    "select distinct sector_ts_code from "
                    "fact_sector_daily where sector_name = ? "
                    "order by 1",
                    [name],
                ).fetchall()
            ]
            out[str(name)] = {
                "codes": codes_list,
                "overlapping_days": int(rows_total) - int(days),
            }
        return out
    finally:
        try:
            con.close()
        except Exception:
            pass


def _load_baseline() -> dict[str, dict[str, object]]:
    if not BASELINE_PATH.exists():
        return {}
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="把当前撞名清单写成新存量（只在确认清理过之后用）",
    )
    args = parser.parse_args()

    db = _db_path()
    print("=" * 68)
    print("板块撞名审计 — 一个中文名不得新增挂到多个 sector_ts_code")
    print("=" * 68)
    if db is None:
        print("  ⓘ 库不可达（worktree 不带 db/，或 MARKET_FEATURE_STORE_DB 未指）")
        print("  跳过。这不是通过——同步数据的那棵树上要真跑一次。")
        return 0
    print(f"  库        {db}")

    try:
        current = _collisions(db)
    except Exception as exc:  # noqa: BLE001
        print(f"  ✗ 读库失败：{type(exc).__name__}: {exc}")
        return 1

    baseline = _load_baseline()
    print(f"  存量基线  {len(baseline)} 个撞名板块")
    print(f"  当前      {len(current)} 个")

    if args.update_baseline:
        BASELINE_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"  已写入 {BASELINE_PATH.name}（{len(current)} 个）")
        return 0

    added = sorted(set(current) - set(baseline))
    cleared = sorted(set(baseline) - set(current))
    worsened = sorted(
        name
        for name in set(current) & set(baseline)
        if int(current[name]["overlapping_days"])  # type: ignore[arg-type]
        > int(baseline[name].get("overlapping_days", 0))  # type: ignore[union-attr]
    )

    if cleared:
        print(f"\n  ↓ 已清理 {len(cleared)} 个（棘轮下调，跑 --update-baseline 固化）：")
        for name in cleared[:10]:
            print(f"      - {name}")

    if not added and not worsened:
        print("\n✅ 无新增撞名")
        return 0

    if added:
        print(f"\n❌ 新增 {len(added)} 个撞名板块：")
        for name in added:
            item = current[name]
            print(
                f"      {name}  代码={item['codes']}  "
                f"重叠交易日={item['overlapping_days']}"
            )
    if worsened:
        print(f"\n❌ {len(worsened)} 个存量撞名恶化（重叠天数增加）：")
        for name in worsened:
            print(
                f"      {name}  {baseline[name].get('overlapping_days')}"  # type: ignore[union-attr]
                f" → {current[name]['overlapping_days']}"
            )
    print(
        "\n  同名多代码并存 → 按 sector_name 查会返回同日多行 → 预取把矛盾当事实"
        "投递 → 模型只能写区间 → 判官判编造。修数据，别在下游打补丁。"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
