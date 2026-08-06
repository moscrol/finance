#!/usr/bin/env python3
"""离线扫描 grounded_composer_shadow.json，报告删除率 / 假绿 / 必需输出存活。

用法:
    python3 scripts/scan_grounded_composer_runs.py [runs_dir]

默认 runs_dir = ~/.local/share/finance-workbench/users/<当前用户>/runs

输出三段：
  1. 汇总：status 分布、judge 通过率、假绿率、平均删除率
  2. 按 claim_type 的删除率
  3. 逐 run 明细（keep < 0.5 或 judge=False 且放行态的 run 标 <<<）

判据来源：agent-run-triage skill 对 run_20260806_015516_705609 的分诊。
该 run 暴露的三类问题（无差别删句、假绿、门禁缺席）均可从已有 artifact
离线计算，不需要 runtime 埋点。
"""
from __future__ import annotations

import collections
import glob
import json
import os
import re
import sys

CLAIM_MARKER = re.compile(
    r"<!--\s*claim_ids=(?P<ids>[^;]*);"
    r"\s*evidence_atom_ids=(?P<atoms>[^;]*);"
    r"\s*claim_type=(?P<ct>[a-zA-Z_]+)\s*-->"
)

# judge=False 但仍放行给用户的状态
RELEASED_STATUSES = frozenset({"accepted", "repaired", "judge_outage_released"})


def claim_type_counts(text: str | None) -> collections.Counter:
    return collections.Counter(m.group("ct") for m in CLAIM_MARKER.finditer(text or ""))


def scan(runs_dir: str) -> None:
    shadows = sorted(glob.glob(os.path.join(runs_dir, "*/grounded_composer_shadow.json")))
    if not shadows:
        print(f"没有找到 grounded_composer_shadow.json 于 {runs_dir}")
        return

    rows: list[dict] = []
    for f in shadows:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        jr = d.get("judge_report") or {}
        raw = d.get("raw_answer") or ""
        rep = d.get("repaired_answer")
        rows.append(
            {
                "run": os.path.basename(os.path.dirname(f)),
                "status": d.get("status"),
                "judged": jr.get("passed"),
                "nrej": len(jr.get("rejected_sentence_indexes") or []),
                "raw_len": len(raw),
                "rep_len": len(rep) if rep else None,
                "raw_types": claim_type_counts(raw),
                "rep_types": claim_type_counts(rep) if rep else collections.Counter(),
            }
        )

    total = len(rows)
    judgeable = [r for r in rows if r["judged"] is not None]
    comparable = [r for r in rows if r["rep_len"] is not None and r["raw_len"] > 0]

    # --- 汇总 ---
    print("=" * 70)
    print(f"扫描 {total} 个 run（{runs_dir}）")
    print("=" * 70)

    print("\n## status 分布")
    for k, v in collections.Counter(r["status"] for r in rows).most_common():
        print(f"  {k:<35} {v:>4}")

    print(f"\n## judge 通过率: {sum(1 for r in judgeable if r['judged'])}/{len(judgeable)}"
          f" = {sum(1 for r in judgeable if r['judged']) / max(1, len(judgeable)):.0%}")

    false_green = [r for r in rows if r["judged"] is False and r["status"] in RELEASED_STATUSES]
    print(f"## 假绿（judge=False 且放行态）: {len(false_green)}/{total} = {len(false_green) / max(1, total):.0%}")

    # --- 按 claim_type 删除率 ---
    kept_total = collections.Counter()
    dropped_total = collections.Counter()
    for r in comparable:
        a, b = r["raw_types"], r["rep_types"]
        for k in set(a) | set(b):
            kept_total[k] += min(a[k], b[k])
            dropped_total[k] += max(0, a[k] - b[k])

    print("\n## 按 claim_type 的删除率")
    print(f"  {'claim_type':<14}{'总句':>6}{'留存':>7}{'删除':>7}{'删除率':>9}")
    all_types = sorted(set(kept_total) | set(dropped_total),
                       key=lambda x: -(kept_total[x] + dropped_total[x]))
    for k in all_types:
        tot = kept_total[k] + dropped_total[k]
        rate = dropped_total[k] / tot if tot else 0
        print(f"  {k:<14}{tot:>6}{kept_total[k]:>7}{dropped_total[k]:>7}{rate:>8.0%}")

    grand_tot = sum(kept_total.values()) + sum(dropped_total.values())
    grand_drop = sum(dropped_total.values())
    print(f"  {'总计':<14}{grand_tot:>6}{sum(kept_total.values()):>7}{grand_drop:>7}"
          f"{grand_drop / max(1, grand_tot):>8.0%}")

    # --- 逐 run 明细 ---
    print("\n## 逐 run 明细（按 keep 升序，<<< 标记需关注项）")
    print(f"  {'run':<34}{'status':<26}{'judge':<7}{'rej':<5}{'raw':>6}{'rep':>7}{'keep':>7}")
    for r in sorted(comparable, key=lambda x: x["rep_len"] / x["raw_len"]):
        keep = r["rep_len"] / r["raw_len"]
        mark = " <<<" if (keep < 0.5 or (r["judged"] is False and r["status"] in RELEASED_STATUSES)) else ""
        print(f"  {r['run']:<34}{str(r['status']):<26}{str(r['judged']):<7}{r['nrej']:<5}"
              f"{r['raw_len']:>6}{r['rep_len']:>7}{keep:>7.2f}{mark}")


if __name__ == "__main__":
    users_dir = os.path.expanduser("~/.local/share/finance-workbench/users")
    if len(sys.argv) > 1:
        runs_dir = sys.argv[1]
    else:
        # 自动发现：选 shadow 文件最多的 profile
        profiles = [
            (len(glob.glob(os.path.join(d, "*/grounded_composer_shadow.json"))), d)
            for d in glob.glob(os.path.join(users_dir, "*/runs"))
        ]
        profiles = [(n, d) for n, d in profiles if n > 0]
        runs_dir = max(profiles, default=(0, os.path.join(users_dir, "linxiaoqi5111", "runs")))[1]
    scan(runs_dir)
