#!/usr/bin/env python3
"""Read-only audit of declared-but-unrequested tools in continuous episodes.

Implements R-20260827-14 P0. This measures a *signal*, not an answer-quality
failure: a declared tool may be unnecessary, and an output may be filled by an
undeclared tool or prefetch. No code or user run data is modified.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import re
import sys

RUN_DATE = re.compile(r"^run_(\d{4})(\d{2})(\d{2})(?:_|$)")
REAL_USER_DIRS = {"linxiaoqi5111", "a77", "default"}
BLIND_SPOT = (
    "The instrument's range depends on the produces declaration table: "
    "an empty declaration hides missed calls. Conversely, a declared-but-uncalled "
    "tool does not prove the output was left empty; another tool or prefetch may fill it. "
    "Neither the run-level gap nor the output-instance count measures model quality."
)


def run_date(path: Path) -> str | None:
    """Prefer the durable run id, falling back to run.json; never use file mtime."""
    match = RUN_DATE.match(path.parent.name)
    if match:
        try:
            return date(*map(int, match.groups())).isoformat()
        except ValueError:
            pass
    try:
        stamp = json.loads((path.parent / "run.json").read_text()).get("created_at")
        if isinstance(stamp, str):
            return date.fromisoformat(stamp[:10]).isoformat()
    except (OSError, ValueError, TypeError):
        pass
    return None


def code_revision(doc: dict, path: Path) -> str | None:
    """Only accept actual code-revision fields, never mistake kb_commit for code."""
    value = doc.get("code_revision")
    if isinstance(value, str) and value.strip():
        return value.strip()
    try:
        run = json.loads((path.parent / "run.json").read_text())
        value = run.get("code_revision")
        if isinstance(value, str) and value.strip():
            return value.strip()
    except (OSError, ValueError, TypeError):
        pass
    return None


def analyze(paths: list[Path], *, since: str | None = None,
            until: str | None = None, user: str | None = None) -> dict:
    """Aggregate the exact workorder §3.0 definition; no output-id normalization."""
    declared_per_tool: Counter[str] = Counter()
    uncalled_per_tool: Counter[str] = Counter()
    output_instances: Counter[str] = Counter()
    users: Counter[str] = Counter()
    dates: list[str] = []
    revisions: Counter[str] = Counter()
    scanned = included = with_checks = computable = gap_runs = suspicious = gap_instances = 0
    missing_sp = bad_json = unknown_dates = unknown_revisions = 0

    for path in paths:
        scanned += 1
        directory_user = path.parent.parent.parent.name
        if user and directory_user != user:
            continue
        day = run_date(path)
        if (since or until) and day is None:
            unknown_dates += 1
            continue
        if (since and day < since) or (until and day > until):
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            bad_json += 1
            continue
        if not isinstance(doc, dict):
            bad_json += 1
            continue
        included += 1
        users[directory_user] += 1
        if day:
            dates.append(day)
        else:
            unknown_dates += 1
        revision = code_revision(doc, path)
        if revision:
            revisions[revision] += 1
        else:
            unknown_revisions += 1

        # The historical §3.0 sample skips this artifact in ALL gap metrics.
        precheck = doc.get("satisfiability_precheck")
        if not isinstance(precheck, dict):
            missing_sp += 1
            continue
        checks = precheck.get("checks") or []
        if not isinstance(checks, list):
            checks = []
        if checks:
            with_checks += 1
        called = {
            e.get("payload", {}).get("name")
            for e in (doc.get("events") or [])
            if isinstance(e, dict) and e.get("kind") == "tool_request"
            and isinstance(e.get("payload"), dict)
            and isinstance(e["payload"].get("name"), str)
        }
        declared: set[str] = set()
        for item in checks:
            if not isinstance(item, dict):
                continue
            tools = {t for t in (item.get("contributing_tools") or []) if isinstance(t, str) and t}
            declared.update(tools)
            if item.get("status") == "suspicious":
                suspicious += 1
            if tools and not (tools & called):
                gap_instances += 1
                output_instances[str(item.get("output_id") or "<missing>")] += 1
        if not declared:
            continue
        computable += 1
        uncalled = declared - called
        if uncalled:
            gap_runs += 1
        declared_per_tool.update(declared)
        uncalled_per_tool.update(uncalled)

    tools = {
        tool: {"declared_runs": total, "uncalled_runs": uncalled_per_tool[tool],
               "uncalled_rate": uncalled_per_tool[tool] / total}
        for tool, total in sorted(declared_per_tool.items())
    }
    probe = sum(n for name, n in users.items() if name not in REAL_USER_DIRS)
    return {
        "scope": {"scanned_files": scanned, "sample_files": included, "since": since,
                  "until": until, "user": user or "all", "date_min": min(dates, default=None),
                  "date_max": max(dates, default=None), "unknown_dates": unknown_dates,
                  "invalid_json": bad_json, "missing_precheck": missing_sp,
                  "named_user_dirs": included - probe, "probe_or_other_dirs": probe,
                  "probe_or_other_fraction": probe / included if included else None,
                  "code_revision_distinct": sorted(revisions),
                  "code_revision_known_runs": sum(revisions.values()),
                  "code_revision_unknown_runs": unknown_revisions,
                  "revision_span": (
                      "multiple: " + ", ".join(sorted(revisions)) if len(revisions) > 1
                      else next(iter(revisions), "UNAVAILABLE: no code revision in artifacts")
                  )},
        "run_counts": {"with_checks": with_checks, "computable": computable,
                       "with_uncalled": gap_runs,
                       "uncalled_rate": gap_runs / computable if computable else None},
        "tool_counts": tools,
        "output_instances": {"declared_without_request": gap_instances,
                             "suspicious_without_declaration": suspicious,
                             "by_output_id": dict(sorted(output_instances.items()))},
        "caveat": BLIND_SPOT,
    }


def render_markdown(report: dict) -> str:
    s, runs, inst = (report[k] for k in ("scope", "run_counts", "output_instances"))
    def ratio(a: int, b: int) -> str:
        return f"{a}/{b} ({a / b:.1%})" if b else f"{a}/{b} (N/A)"
    out = ["# 工具授权与调用差值 · 离线审计", "",
           f"- 范围：{s['sample_files']} 份有效 JSON / 扫描 {s['scanned_files']} 份；"
           f"日期 {s['date_min']} → {s['date_max']}；过滤 since={s['since']} until={s['until']} user={s['user']}。",
           f"- 样本成分：具名目录 {s['named_user_dirs']}；探针／其他目录 "
           f"{ratio(s['probe_or_other_dirs'], s['sample_files'])}。具名目录亦可能混有评测。",
           f"- 代码 revision 跨度：{s['revision_span']}（有记录 {s['code_revision_known_runs']} / "
           f"{s['sample_files']}，缺 {s['code_revision_unknown_runs']}；KB commit 不算代码版本）。",
           f"- 容缺：缺预检 {s['missing_precheck']}，无效 JSON {s['invalid_json']}，"
           f"日期未知 {s['unknown_dates']}。", "",
           f"- 有 checks 的 run：{runs['with_checks']}。可算差值：{runs['computable']}。",
           f"- 至少一个声明工具未被调用：{ratio(runs['with_uncalled'], runs['computable'])}。",
           f"- **output 实例差值 {inst['declared_without_request']}；声明盲区 "
           f"suspicious {inst['suspicious_without_declaration']}。两数必须并读。**", "",
           "| 工具 | 声明为 contributor 的 run | 未调用 | 未调用率 |",
           "| --- | ---: | ---: | ---: |"]
    for name, c in report["tool_counts"].items():
        out.append(f"| `{name}` | {c['declared_runs']} | {c['uncalled_runs']} | "
                   f"{ratio(c['uncalled_runs'], c['declared_runs'])} |")
    out += ["", "| output_id | 实例级差值 |", "| --- | ---: |"]
    for output, n in sorted(inst["by_output_id"].items(), key=lambda x: (-x[1], x[0])):
        out.append(f"| `{output}` | {n} |")
    out += ["", "## 边界", BLIND_SPOT, "", "只读聚合；不是线上用户质量或路由缺陷的结论。"]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--users-dir", type=Path, default=Path(os.environ.get(
        "FORESIGHT_USERS_DIR", Path.home() / ".local/share/finance-workbench/users")))
    ap.add_argument("--since", type=date.fromisoformat, default=None)
    ap.add_argument("--until", type=date.fromisoformat, default=None)
    ap.add_argument("--user", default=None, help="exact directory name, not a substring")
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] /
                    "intelligence/eval/measurements")
    args = ap.parse_args()
    if args.since and args.until and args.since > args.until:
        ap.error("--since must be <= --until")
    files = sorted(args.users_dir.glob("*/runs/*/continuous-episode.json"))
    report = analyze(files, since=args.since.isoformat() if args.since else None,
                     until=args.until.isoformat() if args.until else None, user=args.user)
    if not report["scope"]["sample_files"]:
        print("No runs matched; no report written", file=sys.stderr)
        return 2
    args.output_dir.mkdir(parents=True, exist_ok=True)
    suffix = report["scope"]["date_max"] or "unknown"
    scope = args.user or "all"
    if args.since:
        scope += "-since-" + args.since.isoformat()
    if args.until:
        scope += "-until-" + args.until.isoformat()
    prefix = args.output_dir / f"tool-usage-differential-{suffix}-{scope}"
    for path in (prefix.with_suffix(".json"), prefix.with_suffix(".md")):
        if path.exists():
            print(f"Refusing to overwrite existing report: {path}", file=sys.stderr)
            return 2
    prefix.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    prefix.with_suffix(".md").write_text(render_markdown(report))
    print(f"Wrote {prefix}.json and {prefix}.md; sample={report['scope']['sample_files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
