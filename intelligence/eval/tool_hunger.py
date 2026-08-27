"""Aggregate tool-hunger JSONL files from run directories into a demand report.

Usage::

    python -m intelligence.eval.tool_hunger --runs-dir PATH --since 7d \\
        --out-dir intelligence/eval/measurements
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from intelligence.services.tool_hunger import HUNGER_FILENAME

SAMPLE_CAP = 8


def parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    now = datetime.now().astimezone()
    if text.endswith("d") and text[:-1].isdigit():
        return now - timedelta(days=int(text[:-1]))
    if text.endswith("h") and text[:-1].isdigit():
        return now - timedelta(hours=int(text[:-1]))
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=now.tzinfo or timezone.utc)
    return parsed


def discover_run_dirs(runs_root: Path) -> list[Path]:
    root = Path(runs_root)
    if not root.exists() or not root.is_dir():
        return []
    direct = sorted(
        path for path in root.iterdir() if path.is_dir() and path.name.startswith("run_")
    )
    if direct:
        return direct
    return sorted(
        path for path in root.glob("*/runs/run_*") if path.is_dir()
    )


def _event_time(event: dict[str, Any]) -> datetime | None:
    raw = event.get("ts")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return events
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def aggregate_hunger_runs(
    runs_root: Path,
    *,
    since: datetime | str | None = None,
) -> dict[str, Any]:
    cutoff = parse_since(since) if isinstance(since, str) else since
    run_dirs = discover_run_dirs(Path(runs_root))
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "sample_run_ids": []}
    )
    event_count = 0
    for run_dir in run_dirs:
        hunger_path = run_dir / HUNGER_FILENAME
        if not hunger_path.is_file():
            continue
        for event in _load_events(hunger_path):
            stamped = _event_time(event)
            if cutoff is not None and stamped is not None and stamped < cutoff:
                continue
            event_type = str(event.get("event_type") or "").strip()
            requested = str(event.get("requested_name") or event.get("dataset") or "").strip()
            if not event_type or not requested:
                continue
            event_count += 1
            bucket = grouped[(event_type, requested)]
            bucket["count"] += 1
            run_id = str(event.get("run_id") or run_dir.name)
            samples: list[str] = bucket["sample_run_ids"]
            if run_id and run_id not in samples and len(samples) < SAMPLE_CAP:
                samples.append(run_id)
    groups = [
        {
            "event_type": event_type,
            "requested_name": requested,
            "count": payload["count"],
            "sample_run_ids": list(payload["sample_run_ids"]),
        }
        for (event_type, requested), payload in grouped.items()
    ]
    groups.sort(key=lambda item: (-int(item["count"]), item["event_type"], item["requested_name"]))
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "runs_root": str(Path(runs_root)),
        "since": cutoff.isoformat() if cutoff is not None else None,
        "runs_scanned": len(run_dirs),
        "event_count": event_count,
        "groups": groups,
        "cadence_note": "建议每周扫一次 runs 目录，把 count 最高的 dataset/工具名推进决策队列；节奏最终由用户定。",
    }


def render_hunger_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 工具饥饿汇总",
        "",
        (
            f"扫描 {report.get('runs_scanned', 0)} 个 run，"
            f"事件 {report.get('event_count', 0)} 条。"
        ),
    ]
    since = report.get("since")
    if since:
        lines.append(f"since: `{since}`")
    lines.extend(
        [
            "",
            "| 类型 | 请求名 | 次数 | 样本 run_id |",
            "| --- | --- | ---: | --- |",
        ]
    )
    groups = report.get("groups") or []
    if not groups:
        lines.append("| — | — | 0 | — |")
    else:
        for item in groups:
            samples = ", ".join(str(run_id) for run_id in item.get("sample_run_ids") or ())
            lines.append(
                f"| {item.get('event_type')} | {item.get('requested_name')} | "
                f"{item.get('count')} | {samples or '—'} |"
            )
    note = str(report.get("cadence_note") or "").strip()
    if note:
        lines.extend(["", note, ""])
    else:
        lines.append("")
    return "\n".join(lines)


def write_hunger_report(
    report: dict[str, Any],
    out_dir: Path,
    *,
    stem: str | None = None,
) -> dict[str, Path]:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    name = stem or "tool-hunger"
    json_path = directory / f"{name}.json"
    md_path = directory / f"{name}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_hunger_markdown(report), encoding="utf-8")
    return {"json": json_path, "md": md_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate tool-hunger events from workbench run directories"
    )
    parser.add_argument(
        "--runs-dir",
        required=True,
        help="Directory of run_* folders, or a users root containing */runs/run_*",
    )
    parser.add_argument(
        "--since",
        default="7d",
        help="Only count events at/after this time (7d, 24h, or ISO datetime)",
    )
    parser.add_argument(
        "--out-dir",
        default="intelligence/eval/measurements",
        help="Directory for tool-hunger-YYYY-MM-DD.{json,md}",
    )
    parser.add_argument(
        "--stem",
        default=None,
        help="Output filename stem (default tool-hunger-YYYY-MM-DD)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    since = None if str(args.since).strip() in {"", "all"} else args.since
    report = aggregate_hunger_runs(Path(args.runs_dir), since=since)
    today = datetime.now().date().isoformat()
    stem = args.stem or f"tool-hunger-{today}"
    paths = write_hunger_report(report, Path(args.out_dir), stem=stem)
    print(paths["json"])
    print(paths["md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
