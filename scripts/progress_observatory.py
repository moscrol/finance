#!/usr/bin/env python3
"""进度观测台生成器。stdlib-only，只读、幂等。"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any

L0_HEADER = ["层", "闭合", "当前刻度取数口径", "本层 L1"]
L1_HEADER = ["ID", "战役", "状态", "完成判据", "handoff/spec 指针", "谁在做"]
DECISION_HEADER = ["提出日", "事项", "卡在谁", "关联"]
L0_CLOSED = {"是", "否", "未评"}
L1_STATES = {"planned", "in_flight", "blocked_on_user", "done", "dropped"}
ROADMAP_MAX_LINES = 120
DEFAULT_HEALTH_URL = "http://127.0.0.1:8792/api/health"
DEFAULT_GITEA_PULLS = (
    "http://127.0.0.1:3300/api/v1/repos/a77/finance-workspace-private/pulls"
    "?state=closed&sort=recentupdate&limit=50"
)

REQUIRED_FILES = {
    "ROADMAP": "docs/roadmap.md",
    "PREDICTION_LEDGER": "docs/prediction-ledger.md",
    "BOOKGAP_INDEX": "docs/superpowers/specs/2026-08-15-bookgap-index.md",
    "INFLIGHT": "docs/handoffs/inflight/main.md",
    "TRIAGE_LOOP": "docs/handoffs/2026-08-15-runtime-trace-triage-loop.md",
}


class CheckError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


def emit_err(code: str, detail: str = "") -> None:
    sys.stderr.write(f"{code}:{detail}\n" if detail else f"{code}\n")


def split_row(line: str) -> list[str]:
    return [part.strip() for part in line.strip().strip("|").split("|")]


def iter_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    tables: list[tuple[list[str], list[list[str]]]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("|") and i + 1 < len(lines) and re.match(
            r"^\|[\s:|-]+\|", lines[i + 1]
        ):
            header = split_row(lines[i])
            rows: list[list[str]] = []
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            tables.append((header, rows))
        else:
            i += 1
    return tables


def section_after(text: str, heading_substr: str) -> str:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("##") and heading_substr in line:
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    prefix = "##" if heading_substr.startswith("当前") else "###"
    for j in range(start, len(lines)):
        if lines[j].startswith(prefix + " ") and heading_substr not in lines[j]:
            end = j
            break
    return "\n".join(lines[start:end])


def strip_ticks(cell: str) -> str:
    return cell.strip().strip("`").strip()


def parse_roadmap(text: str) -> dict[str, Any]:
    errors: list[CheckError] = []
    line_count = len(text.splitlines())
    if line_count > ROADMAP_MAX_LINES:
        errors.append(CheckError("ROADMAP_BUDGET", str(line_count)))
    tables = iter_tables(text)
    l0 = next((rows for header, rows in tables if header == L0_HEADER), None)
    l1 = next((rows for header, rows in tables if header == L1_HEADER), None)
    decisions = next((rows for header, rows in tables if header == DECISION_HEADER), None)
    if l0 is None or l1 is None or decisions is None:
        errors.append(CheckError("ROADMAP_SCHEMA", "missing frozen table"))
        return {"errors": errors, "l0": [], "l1": [], "decisions": [], "line_count": line_count}
    for row in l0:
        if len(row) != 4 or row[1] not in L0_CLOSED:
            errors.append(CheckError("ROADMAP_SCHEMA", f"L0:{row}"))
    for row in l1:
        if len(row) != 6 or row[2] not in L1_STATES:
            errors.append(CheckError("ROADMAP_SCHEMA", f"L1:{row}"))
    return {
        "errors": errors,
        "l0": l0,
        "l1": l1,
        "decisions": decisions,
        "line_count": line_count,
    }


def bookgap_done_ids(text: str) -> set[str]:
    return {f"L1-S{m.group(1)}" for m in re.finditer(r"^### S(\d+)\b", text, re.M)}


def check_l1_vs_bookgap(l1_rows: list[list[str]], bookgap_text: str) -> list[CheckError]:
    done = bookgap_done_ids(bookgap_text)
    errors: list[CheckError] = []
    for row in l1_rows:
        ident, status = row[0], row[2]
        if not re.fullmatch(r"L1-S\d+", ident):
            continue
        if ident in done and status != "done":
            errors.append(CheckError("L1_STALE", f"{ident} expected done (bookgap §4)"))
        if ident not in done and status == "done":
            errors.append(CheckError("L1_OVERCLAIM", ident))
    return errors


def same_rev(left: str, right: str) -> bool:
    a, b = left.lower(), right.lower()
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= 7 and long.startswith(short)


def inflight_claimed_revision(text: str) -> str | None:
    section = section_after(text, "当前状态")
    match = re.search(r"8792\s*=\s*`([0-9a-fA-F]{7,40})`", section)
    return match.group(1) if match else None


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_health(health_file: Path | None, health_url: str) -> dict[str, Any]:
    if health_file is not None:
        if not health_file.is_file():
            raise CheckError("HEALTH_MISSING", str(health_file))
        return load_json_file(health_file)
    try:
        with urllib.request.urlopen(health_url, timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise CheckError("HEALTH_UNREACHABLE", str(exc)) from exc


def health_revision(payload: dict[str, Any]) -> str:
    revision = payload.get("runtime", {}).get("source_revision")
    if not revision:
        raise CheckError("HEALTH_MISSING", "runtime.source_revision")
    return str(revision)


def required_path(root: Path, key: str) -> Path:
    return root / REQUIRED_FILES[key]


def missing_sources(root: Path, keys: tuple[str, ...]) -> list[CheckError]:
    errors: list[CheckError] = []
    for key in keys:
        path = required_path(root, key)
        if not path.exists():
            errors.append(CheckError(f"{key}_MISSING", str(path)))
    runs = root / "intelligence" / "eval" / "runs"
    if not runs.is_dir() or not any(runs.glob("*.json")):
        errors.append(CheckError("EVAL_RUNS_MISSING", str(runs)))
    return errors


def parse_ledger(text: str) -> dict[str, int]:
    counts = {"pending": 0, "confirmed": 0, "refuted": 0}
    open_sec = section_after(text, "Open")
    closed_sec = section_after(text, "Closed")
    for header, rows in iter_tables(open_sec):
        if "outcome" not in header:
            continue
        idx = header.index("outcome")
        for row in rows:
            if idx < len(row) and strip_ticks(row[idx]) == "pending":
                counts["pending"] += 1
    for header, rows in iter_tables(closed_sec):
        if "outcome" not in header:
            continue
        idx = header.index("outcome")
        for row in rows:
            if idx >= len(row):
                continue
            outcome = strip_ticks(row[idx])
            if outcome in counts:
                counts[outcome] += 1
    return counts


def delivery_rate(batch: dict[str, Any]) -> tuple[int, int]:
    hits = 0
    total = 0
    for case in batch.get("cases") or []:
        for turn in case.get("turns") or []:
            if "evidence_bound" not in turn:
                continue
            total += 1
            if int(turn["evidence_bound"] or 0) > 0:
                hits += 1
    return hits, total


def latest_batch(root: Path) -> dict[str, Any]:
    runs = sorted((root / "intelligence" / "eval" / "runs").glob("*.json"))
    if not runs:
        raise CheckError("EVAL_RUNS_MISSING", "no json")
    chosen = max(runs, key=lambda p: p.name)
    return load_json_file(chosen)


def unclosed_lowest(l0_rows: list[list[str]]) -> str:
    for row in l0_rows:
        if row[1] == "否":
            return row[0].split()[0]
    return "无"


def git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise CheckError("GIT_FAILED", proc.stderr.strip() or " ".join(args))
    return proc.stdout


def production_lag(git_root: Path, revision: str) -> int:
    resolved = git("rev-parse", "--verify", f"{revision}^{{commit}}", cwd=git_root).strip()
    head = git("rev-parse", "HEAD", cwd=git_root).strip()
    count = git("rev-list", "--count", f"{resolved}..{head}", cwd=git_root).strip()
    return int(count)


def worktree_rows(git_root: Path) -> list[str]:
    text = git("worktree", "list", cwd=git_root)
    rows = []
    for line in text.splitlines():
        if not line.strip() or ".finance-runtime" in line:
            continue
        rows.append(line)
    return rows


def week_pulls(pulls: list[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
    end = datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = end - timedelta(days=7)
    chosen: list[dict[str, Any]] = []
    for item in pulls:
        merged = item.get("merged_at")
        if not merged:
            continue
        when = datetime.fromisoformat(merged.replace("Z", "+00:00"))
        if start <= when <= end + timedelta(days=1):
            chosen.append(item)
    chosen.sort(key=lambda item: item.get("merged_at") or "", reverse=True)
    return chosen


def _gitea_auth_header() -> str | None:
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=http\nhost=127.0.0.1:3300\n\n",
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    password = ""
    username = "a77"
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            password = line.split("=", 1)[1]
        elif line.startswith("username="):
            username = line.split("=", 1)[1]
    if not password:
        return None
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def _fetch_gitea_pulls() -> list[dict[str, Any]] | None:
    headers = {}
    auth = _gitea_auth_header()
    if auth:
        headers["Authorization"] = auth
    req = urllib.request.Request(DEFAULT_GITEA_PULLS, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, list) else None


def _pr_number_from_subject(subject: str) -> str:
    match = re.search(r"#(\d+)", subject)
    return match.group(1) if match else "?"


def load_pulls(pulls_file: Path | None, git_root: Path, as_of: str) -> tuple[list[dict[str, Any]], str]:
    if pulls_file is not None:
        if not pulls_file.is_file():
            raise CheckError("PULLS_MISSING", str(pulls_file))
        return load_json_file(pulls_file), "pulls-file"
    remote = _fetch_gitea_pulls()
    if remote is not None:
        return remote, "gitea"
    since = (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    log = git(
        "log",
        "--first-parent",
        "--merges",
        f"--since={since}",
        "--format=%s",
        cwd=git_root,
    )
    rows = []
    for line in log.splitlines():
        rows.append(
            {
                "number": _pr_number_from_subject(line),
                "title": line,
                "merged_at": f"{as_of}T00:00:00Z",
            }
        )
    return rows, "git-log-merges"


def run_check(root: Path, health_file: Path | None, health_url: str) -> int:
    errors: list[CheckError] = []
    roadmap_path = required_path(root, "ROADMAP")
    if not roadmap_path.is_file():
        emit_err("ROADMAP_MISSING", str(roadmap_path))
        return 1
    parsed = parse_roadmap(roadmap_path.read_text(encoding="utf-8"))
    errors.extend(parsed["errors"])
    schema_failed = any(err.code == "ROADMAP_SCHEMA" for err in errors)
    if not schema_failed:
        errors.extend(missing_sources(root, ("BOOKGAP_INDEX", "INFLIGHT")))
        bookgap_path = required_path(root, "BOOKGAP_INDEX")
        inflight_path = required_path(root, "INFLIGHT")
        if bookgap_path.is_file():
            errors.extend(
                check_l1_vs_bookgap(
                    parsed["l1"], bookgap_path.read_text(encoding="utf-8")
                )
            )
        if inflight_path.is_file():
            try:
                claimed = inflight_claimed_revision(
                    inflight_path.read_text(encoding="utf-8")
                )
                if not claimed:
                    errors.append(CheckError("INFLIGHT_REVISION_MISSING"))
                else:
                    live = health_revision(load_health(health_file, health_url))
                    if not same_rev(claimed, live):
                        errors.append(
                            CheckError("INFLIGHT_REVISION_STALE", f"{claimed}!={live}")
                        )
            except CheckError as exc:
                errors.append(exc)
    if errors:
        for err in errors:
            emit_err(err.code, err.detail)
        return 1
    sys.stdout.write("OK\n")
    return 0


def render_html(model: dict[str, Any]) -> str:
    l0_rows = "".join(
        f"<tr><td>{escape(r[0])}</td><td>{escape(r[1])}</td>"
        f"<td>{escape(r[2])}</td><td>{escape(r[3])}</td></tr>"
        for r in model["l0"]
    )
    l1_rows = "".join(
        f"<tr><td>{escape(r[0])}</td><td>{escape(r[1])}</td>"
        f"<td>{escape(r[2])}</td><td>{escape(r[3])}</td>"
        f"<td>{escape(r[4])}</td><td>{escape(r[5])}</td></tr>"
        for r in model["l1"]
    )
    local = "".join(f"<li>{escape(line)}</li>" for line in model["l2_local"])
    repo = "".join(
        f"<li>#{escape(str(item.get('number')))} {escape(str(item.get('title')))}</li>"
        for item in model["week_pulls"]
    )
    if model.get("week_extra"):
        repo += f"<li>外 {model['week_extra']} 条</li>"
    hits, total = model["delivery"]
    confirmed = model["ledger"]["confirmed"]
    refuted = model["ledger"]["refuted"]
    denom = confirmed + refuted
    hit_rate = f"{confirmed}/{denom}" if denom else "n/a"
    return (
        "<!doctype html>\n<meta charset=\"utf-8\">\n"
        "<title>进度观测台</title>\n"
        "<h1>进度观测台</h1>\n"
        "<section id=\"five\"><h2>五问</h2><ol>\n"
        f"<li>未闭合的最低层：{escape(model['unclosed'])}</li>\n"
        f"<li>本周合并：{escape(model['week_summary'])}</li>\n"
        f"<li>账本 open：{model['ledger']['pending']}</li>\n"
        f"<li>生产落后：{model['lag']}</li>\n"
        f"<li>下一个裁决：{escape(model['next_decision'])}</li>\n"
        "</ol></section>\n"
        "<section id=\"frame\"><h2>参照系</h2>\n"
        "<table><thead><tr><th>层</th><th>闭合</th><th>口径</th><th>L1</th></tr></thead>"
        f"<tbody>{l0_rows}</tbody></table></section>\n"
        "<section id=\"progress\"><h2>推进</h2>\n"
        "<table><thead><tr><th>ID</th><th>战役</th><th>状态</th>"
        "<th>完成判据</th><th>指针</th><th>谁在做</th></tr></thead>"
        f"<tbody>{l1_rows}</tbody></table>\n"
        f"<h3 id=\"l2-local\">L2 本机</h3><ul>{local}</ul>\n"
        f"<h3 id=\"l2-repo\">L2 仓</h3><ul>{repo}</ul></section>\n"
        "<section id=\"ops\"><h2>运行</h2>\n"
        f"<p>最新批交付率 {hits}/{total}（evidence_bound&gt;0）</p>\n"
        f"<p>账本命中率 {escape(hit_rate)}（confirmed/(confirmed+refuted)）</p>\n"
        f"<p>health {escape(model['health_rev'])} dirty={model['dirty']}</p>\n"
        "</section>\n"
    )


def run_render(
    root: Path,
    out: Path,
    health_file: Path | None,
    health_url: str,
    pulls_file: Path | None,
    as_of: str,
    git_root: Path,
) -> int:
    errors = missing_sources(
        root,
        ("ROADMAP", "PREDICTION_LEDGER", "BOOKGAP_INDEX", "INFLIGHT", "TRIAGE_LOOP"),
    )
    if errors:
        for err in errors:
            emit_err(err.code, err.detail)
        return 1
    try:
        if not (git_root / ".git").exists() and not (git_root / ".git").is_file():
            # worktree uses .git file; plain repo uses .git dir
            git("rev-parse", "--git-dir", cwd=git_root)
        parsed = parse_roadmap(required_path(root, "ROADMAP").read_text(encoding="utf-8"))
        if any(err.code == "ROADMAP_SCHEMA" for err in parsed["errors"]):
            for err in parsed["errors"]:
                emit_err(err.code, err.detail)
            return 1
        health = load_health(health_file, health_url)
        revision = health_revision(health)
        ledger = parse_ledger(required_path(root, "PREDICTION_LEDGER").read_text(encoding="utf-8"))
        batch = latest_batch(root)
        pulls, _source = load_pulls(pulls_file, git_root, as_of)
        week = week_pulls(pulls, as_of)
        shown = week[:8]
        extra = len(week) - len(shown)
        week_summary = ", ".join(
            f"#{item.get('number')} {item.get('title')}" for item in shown
        ) or "无"
        if extra > 0:
            week_summary += f" 外 {extra} 条"
        next_decision = parsed["decisions"][0][1] if parsed["decisions"] else "无"
        model = {
            "l0": parsed["l0"],
            "l1": parsed["l1"],
            "unclosed": unclosed_lowest(parsed["l0"]),
            "week_pulls": shown,
            "week_extra": extra,
            "week_summary": week_summary,
            "ledger": ledger,
            "lag": production_lag(git_root, revision),
            "next_decision": next_decision,
            "l2_local": worktree_rows(git_root),
            "delivery": delivery_rate(batch),
            "health_rev": revision,
            "dirty": bool(health.get("runtime", {}).get("source_dirty")),
        }
    except CheckError as exc:
        emit_err(exc.code, exc.detail)
        return 1
    html = render_html(model)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    sys.stdout.write(
        f"未闭合的最低层: {model['unclosed']}\n"
        f"本周合并: {model['week_summary']}\n"
        f"账本 open: {model['ledger']['pending']}\n"
        f"生产落后: {model['lag']}\n"
        f"下一个裁决: {model['next_decision']}\n"
    )
    return 0


def default_as_of() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="进度观测台（只读、幂等）")
    parser.add_argument("command", nargs="?", default="render", choices=["render"])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--git-root", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--health-file", type=Path, default=None)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--pulls-file", type=Path, default=None)
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args(argv)
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    git_root = (args.git_root or root).resolve()
    if args.check:
        return run_check(root, args.health_file, args.health_url)
    out = args.out or (root / "var" / "observatory" / "index.html")
    return run_render(
        root,
        out,
        args.health_file,
        args.health_url,
        args.pulls_file,
        args.as_of or default_as_of(),
        git_root,
    )


if __name__ == "__main__":
    sys.exit(main())
