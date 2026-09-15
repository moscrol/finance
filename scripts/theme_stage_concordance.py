#!/usr/bin/env python3
"""题材阶段人工对照集（G-04 验收 b / 工单 #21 P1 剩余项）：模板生成 + 一致率报告。

两个子命令：

* ``build``  —— 从主库抽活跃题材，重放时间线（``theme_lifecycle_timeline``），在段边界日
  （阶段切换日，最易错）与长段中点取样，生成待人工标注的对照集 CSV。诊断列
  （``theme_lifecycle`` 八阶段）**如实留 gap**：诊断的输入是问答会话里检索到的证据文本，
  历史上没有按日落账，批量重放会发明输入——历史样本标 ``gap:no_recorded_diagnosis``，
  只随后续复盘按日积累，不回填、不猜。
* ``report`` —— 读已标注的 CSV，按 canonical 词（``theme_stage_vocab``）算三组一致率：
  timeline vs 人工、诊断 vs 人工、timeline vs 诊断；任一组 N < 10 只报「样本不足」不出
  比率（口径同 ``checkpoints.DEFAULT_CALIBRATION_MIN_N``）；不一致样本逐条列出，
  附 timeline 触发条件作归因线索。

只读：主库以 read_only 连接；本脚本不写库。库路径 ``--db`` >
``MARKET_FEATURE_STORE_DB`` > 仓内默认；不存在则 fail closed（退出码 2）。

人工标注规则（也写在输出目录 README）：``human_stage_canonical`` 只填钦定七段词
（酝酿/首发/发酵/主升/分歧/退潮/回流）或留空；判读依据写 ``notes``。标注是创始人的活，
本脚本不代填。
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from intelligence.services import theme_lifecycle_timeline as timeline  # noqa: E402
from intelligence.services import theme_stage_vocab  # noqa: E402
from intelligence.services.checkpoints import DEFAULT_CALIBRATION_MIN_N  # noqa: E402
from market_feature_store import signals as _signals  # noqa: E402

DIAGNOSIS_GAP = "gap:no_recorded_diagnosis"
CSV_FIELDS = (
    "theme",
    "date",
    "sample_kind",           # boundary | midpoint
    "timeline_stage",        # canonical 词（timeline 细词即 canonical）
    "timeline_trigger",
    "diagnosis_stage",       # 八阶段细词；历史样本为 gap:no_recorded_diagnosis
    "diagnosis_canonical",   # 由 vocab 映射；诊断缺席时留空
    "human_stage_canonical", # 人工填：钦定七段词，留空 = 未标注
    "notes",
)
LONG_SEGMENT_DAYS = 7  # 段长 ≥ 此值时加取中点样本


def _resolve_db(arg: str | None) -> Path:
    candidate = arg or os.environ.get("MARKET_FEATURE_STORE_DB")
    if candidate:
        path = Path(candidate).expanduser()
    else:
        path = REPO_ROOT / "db" / "market_feature_store.duckdb"
    if not path.exists():
        raise SystemExit(f"主库不存在：{path}（--db 或 MARKET_FEATURE_STORE_DB 指定）")
    return path


def _active_themes(db_path: Path, days: int, limit: int) -> list[str]:
    """近 ``days`` 个交易日内双红天数最多的板块名——段切换多，对照价值高。"""
    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        trade_days = [
            r[0]
            for r in con.execute(
                "select distinct trade_date from fact_market_daily order by trade_date desc limit ?",
                [days],
            ).fetchall()
        ]
        if not trade_days:
            raise SystemExit("fact_market_daily 无交易日，无法抽样")
        since = str(min(trade_days))[:10]
        rows = con.execute(
            """
            select sector_name, count(*) as dr_days
            from fact_sector_daily
            where trade_date >= ? and pct_chg > ? and diff_ratio > ? and amount > ?
            group by sector_name
            order by dr_days desc, sector_name
            limit ?
            """,
            [
                since,
                _signals.DOUBLE_RED_PCT,
                _signals.DOUBLE_RED_DIFF,
                _signals.DOUBLE_RED_AMOUNT,
                limit,
            ],
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


@dataclass
class SamplePoint:
    theme: str
    day: str
    kind: str
    stage: str
    trigger: str


def sample_points(
    artifact: "timeline.ThemeTimelineArtifact", window_start: str
) -> list[SamplePoint]:
    """段边界（切换日）必取；段长 ≥ LONG_SEGMENT_DAYS 再取日历中点。只留窗口内样本。"""
    points: list[SamplePoint] = []
    for seg in artifact.segments:
        start = str(seg.start_date)[:10]
        end = str(seg.end_date)[:10]
        if end < window_start:
            continue
        if start >= window_start:
            points.append(SamplePoint(artifact.theme, start, "boundary", seg.stage, seg.trigger))
        span = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        if span >= LONG_SEGMENT_DAYS:
            mid = (date.fromisoformat(start) + timedelta(days=span // 2)).isoformat()
            if mid >= window_start:
                points.append(SamplePoint(artifact.theme, mid, "midpoint", seg.stage, seg.trigger))
    seen: set[tuple[str, str]] = set()
    unique: list[SamplePoint] = []
    for p in points:
        key = (p.theme, p.day)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def cmd_build(args: argparse.Namespace) -> int:
    db_path = _resolve_db(args.db)
    themes = (
        [t.strip() for t in args.themes.split(",") if t.strip()]
        if args.themes
        else _active_themes(db_path, args.days, args.max_themes)
    )
    if not themes:
        raise SystemExit("抽不到活跃题材（窗口内无双红板块）")
    import duckdb

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        window_rows = con.execute(
            "select distinct trade_date from fact_market_daily order by trade_date desc limit ?",
            [args.days],
        ).fetchall()
    finally:
        con.close()
    window_start = str(min(r[0] for r in window_rows))[:10]

    out_dir = Path(args.out) if args.out else REPO_ROOT / "docs" / "learning" / "theme-stage-concordance"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_csv = out_dir / f"concordance-set-{today}.csv"
    if out_csv.exists() and not args.force:
        raise SystemExit(f"{out_csv} 已存在；标注中的对照集不覆盖（--force 显式覆盖）")

    n_rows = 0
    skipped: list[str] = []
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for theme in themes:
            artifact = timeline.load_theme_timeline_artifact(theme, market_db_path=db_path)
            if not artifact.available:
                skipped.append(f"{theme}: {artifact.degrade_reason or '无段'}")
                continue
            for p in sample_points(artifact, window_start):
                writer.writerow(
                    {
                        "theme": p.theme,
                        "date": p.day,
                        "sample_kind": p.kind,
                        "timeline_stage": p.stage,
                        "timeline_trigger": p.trigger,
                        "diagnosis_stage": DIAGNOSIS_GAP,
                        "diagnosis_canonical": "",
                        "human_stage_canonical": "",
                        "notes": "",
                    }
                )
                n_rows += 1
    print(f"对照集模板：{out_csv}（{n_rows} 样本 / {len(themes) - len(skipped)} 题材，窗口起 {window_start}，vocab={theme_stage_vocab.VOCAB_VERSION}）")
    for line in skipped:
        print(f"  跳过 {line}")
    return 0


def _pair_stats(pairs: list[tuple[str, str]]) -> tuple[int, int]:
    agree = sum(1 for a, b in pairs if a == b)
    return agree, len(pairs)


def _rate_line(name: str, agree: int, total: int) -> str:
    if total < DEFAULT_CALIBRATION_MIN_N:
        return f"- {name}：样本不足（N={total} < {DEFAULT_CALIBRATION_MIN_N}），不出比率"
    return f"- {name}：{agree}/{total} = {agree / total:.0%}"


def cmd_report(args: argparse.Namespace) -> int:
    src = Path(args.set).expanduser()
    if not src.exists():
        raise SystemExit(f"对照集不存在：{src}")
    rows = list(csv.DictReader(src.open(encoding="utf-8")))
    if not rows:
        raise SystemExit(f"对照集为空：{src}")

    valid_words = set(theme_stage_vocab.CANONICAL_STAGES)
    bad = [
        r for r in rows
        if r["human_stage_canonical"].strip() and r["human_stage_canonical"].strip() not in valid_words
    ]
    tl_vs_human: list[tuple[str, str]] = []
    dg_vs_human: list[tuple[str, str]] = []
    tl_vs_dg: list[tuple[str, str]] = []
    mismatches: list[dict[str, str]] = []
    for r in rows:
        tl = r["timeline_stage"].strip()
        human = r["human_stage_canonical"].strip()
        dg_raw = r["diagnosis_stage"].strip()
        dg_canonical = (
            theme_stage_vocab.to_canonical(dg_raw, theme_stage_vocab.MODULE_DIAGNOSIS)
            if dg_raw and not dg_raw.startswith("gap:")
            else None
        )
        if human and human in valid_words:
            tl_vs_human.append((tl, human))
            if tl != human:
                mismatches.append({**r, "pair": "timeline vs human"})
            if dg_canonical:
                dg_vs_human.append((dg_canonical, human))
                if dg_canonical != human:
                    mismatches.append({**r, "pair": "diagnosis vs human"})
        if dg_canonical:
            tl_vs_dg.append((tl, dg_canonical))
            if tl != dg_canonical:
                mismatches.append({**r, "pair": "timeline vs diagnosis"})

    labelled = len({(r["theme"], r["date"]) for r in rows if r["human_stage_canonical"].strip()})
    lines = [
        f"# 题材阶段一致率报告（{src.name}，vocab={theme_stage_vocab.VOCAB_VERSION}）",
        "",
        f"样本 {len(rows)} 行；已人工标注 {labelled}；诊断列有值 {len(tl_vs_dg)}（历史样本无按日落账，"
        f"标 {DIAGNOSIS_GAP}，随后续复盘积累）。",
        "",
        _rate_line("timeline vs 人工", *_pair_stats(tl_vs_human)),
        _rate_line("诊断 vs 人工", *_pair_stats(dg_vs_human)),
        _rate_line("timeline vs 诊断", *_pair_stats(tl_vs_dg)),
    ]
    if bad:
        lines += ["", f"⚠️ {len(bad)} 行 human_stage_canonical 不是钦定七段词，未计入："]
        lines += [f"  - {r['theme']} {r['date']}: {r['human_stage_canonical']!r}" for r in bad[:20]]
    if mismatches:
        lines += ["", "## 不一致样本（逐条归因）", "", "| 对比 | 题材 | 日期 | timeline | 诊断/人工 | timeline 触发 |", "|---|---|---|---|---|---|"]
        for m in mismatches:
            other = m["human_stage_canonical"] or m["diagnosis_stage"]
            lines.append(
                f"| {m['pair']} | {m['theme']} | {m['date']} | {m['timeline_stage']} | {other} | {m['timeline_trigger'][:60]} |"
            )
    stage_mix = Counter(r["timeline_stage"] for r in rows)
    lines += ["", "## 样本阶段分布（timeline）", ""]
    lines += [f"- {stage}: {n}" for stage, n in stage_mix.most_common()]
    report = "\n".join(lines)
    if args.out:
        Path(args.out).expanduser().write_text(report + "\n", encoding="utf-8")
        print(f"报告：{args.out}")
    else:
        print(report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="生成待标注对照集 CSV")
    b.add_argument("--db", default=None)
    b.add_argument("--days", type=int, default=120, help="抽样窗口（近 N 个交易日）")
    b.add_argument("--themes", default=None, help="逗号分隔手选题材；缺省自动抽活跃题材")
    b.add_argument("--max-themes", type=int, default=12)
    b.add_argument("--out", default=None, help="输出目录（默认 docs/learning/theme-stage-concordance/）")
    b.add_argument("--force", action="store_true", help="覆盖已存在的当日模板")
    b.set_defaults(func=cmd_build)
    r = sub.add_parser("report", help="读已标注对照集出一致率报告")
    r.add_argument("--set", required=True, help="对照集 CSV 路径")
    r.add_argument("--out", default=None, help="报告输出文件（缺省打印 stdout）")
    r.set_defaults(func=cmd_report)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
