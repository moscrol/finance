#!/usr/bin/env python3
"""两个授课框架版本的逐日配对比较（McNemar）——回答「一致率涨的那几个点是真的还是挑出来的」。

输入是两个 `build-labels` 产出的旁路库（各自一个 framework_version），必须在同一份主库快照上建、
且至少一个载有参照标注（`load-reference`）。输出一行 JSON；`--markdown` 时多打一段可贴进收据的表。

    python3 scripts/teaching_framework_paired_compare.py \
        --a /tmp/mcnemar-A.duckdb --b /tmp/mcnemar-B.duckdb --train-until 2025-12-31 --markdown
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.services.methodology_backtest.store import open_labels_db  # noqa: E402
from intelligence.services.teaching_framework.paired import PERIODS, paired_stage_agreement  # noqa: E402

PERIOD_NAMES = {"all": "全期", "train": "训练期", "validate": "验证期"}


def read_sidecar(path: str | Path) -> tuple[str | None, dict[str, str | None], dict[str, str | None]]:
    """返回 (framework_version, 日 → stage_coarse, 日 → 参照 cycle_stage)。参照表可以为空。"""
    con = open_labels_db(path, read_only=True)
    try:
        rows = con.execute(
            "SELECT CAST(trade_date AS VARCHAR), value_text, framework_version FROM history_teaching_labels "
            "WHERE entity_type = 'market' AND label = 'tf.stage_coarse'"
        ).fetchall()
        reference = {
            str(day): stage
            for day, stage in con.execute(
                "SELECT CAST(trade_date AS VARCHAR), cycle_stage FROM history_reference_stages"
            ).fetchall()
        }
    finally:
        con.close()
    versions = {r[2] for r in rows}
    if len(versions) > 1:
        raise ValueError(f"{path} 里 tf.stage_coarse 混了多个 framework_version: {sorted(versions)}")
    return (next(iter(versions)) if versions else None), {str(r[0]): r[1] for r in rows}, reference


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def to_markdown(result: dict[str, Any], version_a: str | None, version_b: str | None) -> str:
    lines = [
        f"A = `{version_a}` · B = `{version_b}` · 切点 {result['train_until']} · 重叠参照日 {result['overlap_days']}",
        "",
        "| 时期 | 口径 | n | A 对 | B 对 | A错B对 | A对B错 | 净 | McNemar p |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in PERIODS:
        p = result["periods"][name]
        for caliber, label in (("all_reference_days", "全部参照日（未判定算错）"), ("both_resolved", "两版都判定")):
            blk = p[caliber]
            m = blk["mcnemar"]
            lines.append(
                f"| {PERIOD_NAMES[name]} | {label} | {blk['days']} | {blk['a_correct']} ({_pct(blk['a_rate'])}) | "
                f"{blk['b_correct']} ({_pct(blk['b_rate'])}) | {m['a_wrong_b_right']} | {m['a_right_b_wrong']} | "
                f"{m['net_gain']:+d} | {m['p_value']:.4f} |"
            )
        rc = p["receipt_caliber"]
        lines.append(
            f"| {PERIOD_NAMES[name]} | 收据口径（各自已判定日） | — | {rc['a']['agree_days']}/{rc['a']['resolved_days']} ({_pct(rc['a']['rate'])}) | "
            f"{rc['b']['agree_days']}/{rc['b']['resolved_days']} ({_pct(rc['b']['rate'])}) | — | — | — | — |"
        )
    flips = result["periods"]["validate"]["flips_by_reference_stage"]
    if flips:
        lines += ["", "验证期翻转按参照阶段：" + "；".join(f"{k} {v}" for k, v in flips.items())]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--a", required=True, help="旧版旁路库（build-labels 产出）")
    ap.add_argument("--b", required=True, help="新版旁路库")
    ap.add_argument("--train-until", required=True, help="校准切点 YYYY-MM-DD，之后的日子是验证期")
    ap.add_argument("--markdown", action="store_true", help="JSON 之后追加可贴进收据的 markdown 表")
    args = ap.parse_args(argv)

    version_a, stages_a, ref_a = read_sidecar(args.a)
    version_b, stages_b, ref_b = read_sidecar(args.b)
    if ref_a and ref_b and ref_a != ref_b:
        raise SystemExit("两个旁路库的参照标注不一致，不能配对比较（重新 load-reference 同一份 JSON）")
    reference = ref_a or ref_b
    if not reference:
        raise SystemExit("两个旁路库都没有参照标注（先 load-reference）")
    if version_a == version_b:
        print(f"警告：两个旁路库是同一个 framework_version {version_a}", file=sys.stderr)

    result = paired_stage_agreement(stages_a, stages_b, reference, train_until=args.train_until)
    result["version_a"] = version_a
    result["version_b"] = version_b
    print(json.dumps(result, ensure_ascii=False))
    if args.markdown:
        print()
        print(to_markdown(result, version_a, version_b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
