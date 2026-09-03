#!/usr/bin/env python3
"""判官拒句账离线普查：P2「先量后改」的第二步，不调任何 LLM。

读 run 目录里 ``continuous-episode.json`` → ``semantic_verifier.sentence_verdicts``
（写侧 ``episode_semantic_verifier``，P2 第一步），按 stage / decision / reason /
有无出处 / 来源档 汇总，回答 spec 2026-09-02 §3.3 要量的那个数：

    被删的句子里，有多少是「有出处」的（引到了本轮证据表里的 E 号）？
    这些有出处被删的句子，来源档分布如何（public_web 占几条）？

阈值（spec 建议 10%，实测后定）够了才动判据；不够就把「不够」写进收据，停在这里。

它防的失败形状：没有这把尺，P2 会按印象改判据（「判官删太多 / 删太少」都有人说），
而 2026-08-21 那次判官删了 65% 真话正是没人量出来才拖到那一步。

历史 run 没有该字段（字段 2026-09-03 才有），按仓里纪律**报「不可判」不报 0**：
``runs_without_field`` 单列，不进任何分母。

用法：
    python3 scripts/offline_judge_verdict_census.py --runs-root ~/.local/share/finance-workbench/users
    python3 scripts/offline_judge_verdict_census.py --runs-root <dir> --since 2026-09-03 --out-dir docs/verification
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.services.episode_semantic_verifier import (  # noqa: E402
    VERDICT_DELETED,
    VERDICT_DEMOTED,
)

OUT_DIR = Path(os.environ.get("OFFLINE_CENSUS_OUT_DIR", str(REPO / "docs" / "verification")))
EPISODE_FILE = "continuous-episode.json"
SAMPLE_CAP = 6


def _iter_episode_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(root.rglob(EPISODE_FILE))


def _run_id(path: Path) -> str:
    for part in reversed(path.parts):
        if part.startswith("run_"):
            return part
    return path.parent.name


def _run_date(run_id: str) -> str:
    # run_20260903_142417_573363 → 2026-09-03
    tail = run_id[4:12] if run_id.startswith("run_") else ""
    if len(tail) == 8 and tail.isdigit():
        return f"{tail[:4]}-{tail[4:6]}-{tail[6:]}"
    return ""


def census(paths: list[Path], *, since: str | None) -> dict[str, Any]:
    runs_with_field = 0
    runs_without_field = 0
    runs_unreadable = 0
    runs_skipped_by_date = 0
    verdicts: list[dict[str, Any]] = []
    for path in paths:
        run_id = _run_id(path)
        day = _run_date(run_id)
        if since and day and day < since:
            runs_skipped_by_date += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            runs_unreadable += 1
            continue
        verifier = payload.get("semantic_verifier") if isinstance(payload, dict) else None
        if not isinstance(verifier, dict) or "sentence_verdicts" not in verifier:
            runs_without_field += 1
            continue
        runs_with_field += 1
        for item in verifier.get("sentence_verdicts") or []:
            if isinstance(item, dict):
                verdicts.append({**item, "run_id": run_id})

    by_stage = Counter(str(v.get("stage")) for v in verdicts)
    by_decision = Counter(str(v.get("decision")) for v in verdicts)
    by_reason = Counter(code for v in verdicts for code in (v.get("reasons") or []))
    deleted = [v for v in verdicts if v.get("decision") == VERDICT_DELETED]
    demoted = [v for v in verdicts if v.get("decision") == VERDICT_DEMOTED]
    deleted_with_source = [v for v in deleted if v.get("bound_evidence_hashes")]
    deleted_unresolved_only = [
        v
        for v in deleted
        if not v.get("bound_evidence_hashes") and v.get("unresolved_evidence_ordinals")
    ]
    deleted_no_citation = [
        v
        for v in deleted
        if not v.get("bound_evidence_hashes") and not v.get("unresolved_evidence_ordinals")
    ]
    tiers_deleted_with_source = Counter(
        tier for v in deleted_with_source for tier in (v.get("source_tiers") or [])
    )
    tiers_demoted = Counter(tier for v in demoted for tier in (v.get("source_tiers") or []))

    def _share(part: int, whole: int) -> float | None:
        return round(part / whole, 4) if whole else None

    def _samples(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "run_id": v.get("run_id"),
                "sentence": str(v.get("sentence") or "")[:120],
                "reasons": v.get("reasons"),
                "source_tiers": v.get("source_tiers"),
                "judge_issues": [str(i)[:120] for i in (v.get("judge_issues") or [])][:2],
            }
            for v in items[:SAMPLE_CAP]
        ]

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "since": since,
        "runs_scanned": len(paths),
        "runs_with_field": runs_with_field,
        "runs_without_field": runs_without_field,
        "runs_unreadable": runs_unreadable,
        "runs_skipped_by_date": runs_skipped_by_date,
        "verdict_count": len(verdicts),
        "by_stage": dict(by_stage),
        "by_decision": dict(by_decision),
        "by_reason": dict(by_reason),
        "deleted": {
            "count": len(deleted),
            "with_source_count": len(deleted_with_source),
            "with_source_share": _share(len(deleted_with_source), len(deleted)),
            "unresolved_ordinal_only_count": len(deleted_unresolved_only),
            "no_citation_count": len(deleted_no_citation),
            "with_source_tiers": dict(tiers_deleted_with_source),
            "with_source_samples": _samples(deleted_with_source),
        },
        "demoted": {
            "count": len(demoted),
            "source_tiers": dict(tiers_demoted),
            "samples": _samples(demoted),
        },
        "verdict": (
            "不可判：没有任何 run 带 sentence_verdicts 字段（写侧尚未上线或未切流）"
            if runs_with_field == 0
            else (
                "不可判：有字段的 run 里没有一条拒句"
                if not verdicts
                else "可判：见 deleted.with_source_share 与 with_source_tiers"
            )
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    d = report["deleted"]
    m = report["demoted"]
    share_text = (
        "不可判" if d["with_source_share"] is None else f"{d['with_source_share']:.1%}"
    )
    lines = [
        "# 判官拒句账普查",
        "",
        f"生成 {report['generated_at']}；since={report['since'] or 'all'}。",
        "",
        f"- 扫 run {report['runs_scanned']}：带字段 **{report['runs_with_field']}**、无字段（历史）{report['runs_without_field']}、"
        f"不可读 {report['runs_unreadable']}、按日期跳过 {report['runs_skipped_by_date']}",
        f"- 拒句 {report['verdict_count']} 条：stage {report['by_stage']}；decision {report['by_decision']}；reason {report['by_reason']}",
        "",
        "## 被删的句子",
        "",
        f"- 共 {d['count']}；**有出处**（引到本轮 E 号）{d['with_source_count']}，占比 {share_text}",
        f"- 只引了表外 E 号 {d['unresolved_ordinal_only_count']}；没引任何 E 号 {d['no_citation_count']}",
        f"- 有出处被删的来源档分布：{d['with_source_tiers'] or '—'}",
        "",
        "## 降成 issue（没删）的句子",
        "",
        f"- 共 {m['count']}；来源档分布：{m['source_tiers'] or '—'}",
        "",
        f"**结论**：{report['verdict']}",
        "",
        "阈值判定（spec §3.3 第 3 条）：`deleted.with_source_share` 中 `public_web` 等低档来源占比 ≥ 阈值才动判据；否则停在这里并把停下写进收据。",
    ]
    if d["with_source_samples"]:
        lines += ["", "### 有出处被删样本", ""]
        for s in d["with_source_samples"]:
            lines.append(f"- `{s['run_id']}` [{','.join(s['source_tiers'] or [])}] {s['sentence']} — {s['reasons']}")
    if m["samples"]:
        lines += ["", "### 降级样本", ""]
        for s in m["samples"]:
            lines.append(f"- `{s['run_id']}` [{','.join(s['source_tiers'] or [])}] {s['sentence']} — {s['judge_issues']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-root", required=True, help="users 根、runs 目录或单个 continuous-episode.json")
    parser.add_argument("--since", default=None, help="只算 run_id 日期 ≥ 该日（YYYY-MM-DD）的 run")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    parser.add_argument("--stem", default=None, help="输出文件名干，默认 YYYY-MM-DD-judge-verdict-census")
    args = parser.parse_args(argv)

    root = Path(args.runs_root).expanduser()
    if not root.exists():
        print(f"runs-root 不存在: {root}", file=sys.stderr)
        return 2
    report = census(_iter_episode_files(root), since=args.since)
    report["runs_root"] = str(root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.stem or f"{datetime.now().date().isoformat()}-judge-verdict-census"
    (out_dir / f"{stem}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / f"{stem}.md").write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    print(f"→ {out_dir / stem}.{{json,md}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
