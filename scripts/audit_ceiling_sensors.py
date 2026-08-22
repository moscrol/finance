#!/usr/bin/env python3
"""封上限四形状 + 输入侧形状传感器聚合——把一次性 trace diff 变成常驻计量。

本脚本只读 ``continuous-episode.json``，不调模型、不改 run。

形状与字段（spec ``2026-08-21-ceiling-shape-closeout-design.md`` W5）：

    A  引了没绑     semantic_verifier.projection_cited_unbound_count > 0
                    缺字段 → 「不可判」，不报 0（#298 之前的历史 run 没有此键）
    B  契约不可满足 missing_mandatory_capability 非空
                    或 repair_goal.unreachable_without_tools 为真（落盘常是名单）
    C  破坏发生     marker_loss / repair_wiped_all_outputs
                    / (judge_status=repaired 且 rejected_claim_indexes 非空)
    D  预取名漏网   预取观察值 subject ≠ 问句里的最长「…概念」精确名（#288）

输入侧（spec ``2026-08-21-inputside-closeout-r2-design.md`` V7）：

    I  题形×KB 三层  authorized / planned / called
    III kb_search 送达  telemetry.delivered_chars / detail_chars / hit_count / source_pages
                        （delivered=observation 串；detail=evidence 通道，V3 粗管道；两通道分开计）
                        V9a 只读：pointer_dropped / reexcerpted；缺字段记 None，不报 0、不翻 unjudgeable
                        缺 delivered/hit/pages 或空 dict → 「不可判」，不报 0
                        零调用 → no_call（不是送达 0）

B/C 任一非零 → 退出码 1，可挂夜检。A 不可判、D 命中、输入侧只记账，不单独红。

用法::

    python3 scripts/audit_ceiling_sensors.py --since 2026-08-15 --until 2026-08-21
    python3 scripts/audit_ceiling_sensors.py --runs-dir /path/to/runs --json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

_RUN_DATE_RE = re.compile(r"^run_(\d{8})_")
_CONCEPT_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]+概念")
_PREFETCH_TITLE_RE = re.compile(r"^(.+?)\s+双红时间轴$")

_ISSUE_MANDATORY = "missing_mandatory_capability"
_ISSUE_MARKER_LOSS = "marker_loss"
_ISSUE_WIPED = "repair_wiped_all_outputs"

SHAPES = ("A", "B", "C", "D")
_KB_TOOLS = frozenset({"kb_search", "evidence_search"})
_AGENT_PREFIX = "agent:"
_TELEMETRY_KEYS = ("delivered_chars", "hit_count", "source_pages")


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _issue_texts(episode: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for block in (
        episode.get("semantic_verifier"),
        episode.get("structural_verifier"),
        _as_dict(episode.get("semantic_verifier")).get("verified"),
    ):
        issues = _as_dict(block).get("issues") or []
        if isinstance(issues, list):
            texts.extend(str(item) for item in issues)
    return texts


def _has_issue_code(texts: list[str], code: str) -> bool:
    token = f"code={code}"
    return any(token in text or f"issue_code={code}" in text for text in texts)


def _issue_subject(texts: list[str], code: str) -> str:
    prefix = f"code={code} subject="
    for text in texts:
        if prefix in text:
            rest = text.split(prefix, 1)[1]
            return rest.split(" ", 1)[0].strip()
    return ""


def _question(episode: dict[str, Any]) -> str:
    task = _as_dict(episode.get("task_frame"))
    contract = _as_dict(episode.get("contract"))
    return str(
        task.get("raw_question")
        or contract.get("question")
        or task.get("question")
        or ""
    )


def _question_exact_name(question: str) -> str | None:
    """问句里作为子串出现的最长「…概念」。没有就不判 D（不发明精确名）。"""

    compact = re.sub(r"\s+", "", question)
    names = _CONCEPT_RE.findall(compact)
    if not names:
        return None
    return max(names, key=len)


def _prefetch_subject(episode: dict[str, Any]) -> str | None:
    evidence = _as_dict(episode.get("outcome")).get("evidence") or []
    if not isinstance(evidence, list):
        return None
    for item in evidence:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "")
        if "问句日预取" not in source:
            continue
        observations = item.get("observations") or []
        if isinstance(observations, list) and observations:
            first = observations[0]
            if isinstance(first, dict):
                subject = str(first.get("subject") or "").strip()
                if subject:
                    return subject
        title = str(item.get("title") or "")
        matched = _PREFETCH_TITLE_RE.match(title)
        if matched:
            return matched.group(1).strip()
    return None


def _unreachable_without_tools(episode: dict[str, Any]) -> bool:
    for event in episode.get("events") or []:
        if not isinstance(event, dict) or event.get("kind") != "repair_goal":
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        value = payload.get("unreachable_without_tools")
        if value is True:
            return True
        if isinstance(value, (list, tuple)) and len(value) > 0:
            return True
        if isinstance(value, str) and value.strip() and value.strip().lower() not in {
            "false",
            "0",
        }:
            return True
    return False


def _unreachable_summary(episode: dict[str, Any]) -> str:
    for event in episode.get("events") or []:
        if not isinstance(event, dict) or event.get("kind") != "repair_goal":
            continue
        payload = event.get("payload") or {}
        if isinstance(payload, dict) and payload.get("unreachable_without_tools"):
            return f"unreachable_without_tools={payload.get('unreachable_without_tools')!r}"
    return "unreachable_without_tools"


def inspect_episode(episode: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """对一份 episode JSON 给出四形状裁决。"""

    semantic = _as_dict(episode.get("semantic_verifier"))
    structural = _as_dict(episode.get("structural_verifier"))
    issues = _issue_texts(episode)

    if "projection_cited_unbound_count" not in semantic:
        shape_a = {
            "status": "unjudgeable",
            "hit": False,
            "summary": "不可判：无 projection_cited_unbound_count 字段",
        }
    else:
        count = semantic.get("projection_cited_unbound_count")
        try:
            numeric = int(count)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            numeric = 0
        if numeric > 0:
            shape_a = {
                "status": "hit",
                "hit": True,
                "summary": f"projection_cited_unbound_count={numeric}",
            }
        else:
            shape_a = {
                "status": "clean",
                "hit": False,
                "summary": "projection_cited_unbound_count=0",
            }

    mandatory_list = structural.get("mandatory_missing_capabilities") or []
    b_reasons: list[str] = []
    if _has_issue_code(issues, _ISSUE_MANDATORY) or (
        isinstance(mandatory_list, list) and len(mandatory_list) > 0
    ):
        subject = _issue_subject(issues, _ISSUE_MANDATORY)
        if not subject and isinstance(mandatory_list, list):
            subject = ",".join(str(item) for item in mandatory_list)
        b_reasons.append(
            f"missing_mandatory_capability={subject or 'non-empty'}"
        )
    if _unreachable_without_tools(episode):
        b_reasons.append(_unreachable_summary(episode))
    shape_b = {
        "hit": bool(b_reasons),
        "summary": "; ".join(b_reasons) if b_reasons else "clean",
    }

    c_reasons: list[str] = []
    if _has_issue_code(issues, _ISSUE_MARKER_LOSS):
        subject = _issue_subject(issues, _ISSUE_MARKER_LOSS)
        c_reasons.append(f"marker_loss={subject or 'yes'}")
    if _has_issue_code(issues, _ISSUE_WIPED) or any(
        _ISSUE_WIPED in text for text in issues
    ):
        c_reasons.append("repair_wiped_all_outputs")
    indexes = semantic.get("rejected_claim_indexes") or []
    judge_status = semantic.get("judge_status")
    if judge_status == "repaired" and isinstance(indexes, list) and len(indexes) > 0:
        c_reasons.append(f"repaired+rejected_claim_indexes={indexes!r}")
    shape_c = {
        "hit": bool(c_reasons),
        "summary": "; ".join(c_reasons) if c_reasons else "clean",
    }

    prefetch = _prefetch_subject(episode)
    exact = _question_exact_name(_question(episode))
    if prefetch and exact and prefetch != exact:
        shape_d = {
            "hit": True,
            "summary": f"prefetch={prefetch!r} ≠ 问句精确名={exact!r}",
        }
    else:
        shape_d = {"hit": False, "summary": "clean"}

    return {
        "A": shape_a,
        "B": shape_b,
        "C": shape_c,
        "D": shape_d,
        "I": inspect_shape_i(episode),
        "III": inspect_shape_iii(episode),
    }


def _question_type(episode: dict[str, Any]) -> str:
    contract = _as_dict(episode.get("contract"))
    task = _as_dict(episode.get("task_frame"))
    return str(
        contract.get("question_type") or task.get("question_type") or "unknown"
    )


def _kb_authorized(episode: dict[str, Any]) -> bool:
    caps = _as_dict(episode.get("contract")).get("allowed_capabilities") or []
    if not isinstance(caps, list):
        return False
    return any(str(item) in _KB_TOOLS for item in caps)


def _kb_planned(episode: dict[str, Any]) -> bool:
    plan = _as_dict(_as_dict(episode.get("contract")).get("evidence_plan"))
    reqs = plan.get("requirements") or []
    if not isinstance(reqs, list):
        return False
    for req in reqs:
        if isinstance(req, dict) and str(req.get("capability") or "") in _KB_TOOLS:
            return True
        if isinstance(req, str) and req in _KB_TOOLS:
            return True
    return False


def _trace_tool_name(trace: dict[str, Any]) -> str:
    provider = str(trace.get("provider") or "")
    if provider.startswith(_AGENT_PREFIX):
        name = provider[len(_AGENT_PREFIX) :].strip()
        if name:
            return name
    return str(trace.get("capability") or "")


def _iter_traces(episode: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for block in (
        _as_dict(episode.get("outcome")).get("traces"),
        episode.get("traces"),
    ):
        if isinstance(block, list):
            found.extend(item for item in block if isinstance(item, dict))
    return found


def _kb_called(episode: dict[str, Any]) -> bool:
    for event in episode.get("events") or []:
        if not isinstance(event, dict):
            continue
        payload = _as_dict(event.get("payload"))
        kind = event.get("kind")
        if kind == "tool_result" and str(payload.get("tool") or "") in _KB_TOOLS:
            return True
        if kind == "tool_request":
            name = str(payload.get("name") or payload.get("tool") or "")
            if name in _KB_TOOLS:
                return True
    return any(_trace_tool_name(trace) in _KB_TOOLS for trace in _iter_traces(episode))


def _telemetry_complete(tel: object) -> bool:
    if not isinstance(tel, dict):
        return False
    return all(key in tel for key in _TELEMETRY_KEYS)


def inspect_shape_i(episode: dict[str, Any]) -> dict[str, Any]:
    authorized = _kb_authorized(episode)
    planned = _kb_planned(episode)
    called = _kb_called(episode)
    qtype = _question_type(episode)
    return {
        "question_type": qtype,
        "authorized": authorized,
        "planned": planned,
        "called": called,
        "status": "judgeable",
        "summary": (
            f"qtype={qtype} authorized={authorized} "
            f"planned={planned} called={called}"
        ),
    }


def inspect_shape_iii(episode: dict[str, Any]) -> dict[str, Any]:
    delivered: list[int] = []
    detail_chars: list[int | None] = []
    pointer_dropped: list[int | None] = []
    reexcerpted: list[object | None] = []
    hit_counts: list[int] = []
    source_pages: list[list[str]] = []
    unjudgeable = 0
    calls = 0
    for event in episode.get("events") or []:
        if not isinstance(event, dict) or event.get("kind") != "tool_result":
            continue
        payload = _as_dict(event.get("payload"))
        if str(payload.get("tool") or "") != "kb_search":
            continue
        calls += 1
        tel = payload.get("telemetry")
        if not _telemetry_complete(tel):
            unjudgeable += 1
            continue
        assert isinstance(tel, dict)
        try:
            chars = int(tel["delivered_chars"])
            hit_n = int(tel["hit_count"])
        except (TypeError, ValueError):
            unjudgeable += 1
            continue
        raw_pages = tel["source_pages"]
        if not isinstance(raw_pages, (list, tuple)):
            unjudgeable += 1
            continue
        delivered.append(chars)
        hit_counts.append(hit_n)
        source_pages.append([str(page) for page in raw_pages])
        # detail_chars 是后加的通道计数（evidence[].detail，V3 粗管道）。
        # 老 episode 没有这个字段：记 None（传感器早于字段），不得记 0、
        # 不得翻 unjudgeable——那会把存量全部打成不可判。
        raw_detail = tel.get("detail_chars")
        detail_chars.append(
            int(raw_detail) if isinstance(raw_detail, (int, float)) else None
        )
        raw_dropped = tel.get("pointer_dropped")
        pointer_dropped.append(
            int(raw_dropped) if isinstance(raw_dropped, (int, float)) else None
        )
        raw_reexcerpted = tel.get("reexcerpted")
        reexcerpted.append(
            raw_reexcerpted
            if isinstance(raw_reexcerpted, (list, tuple, bool))
            else None
        )
    if calls == 0:
        return {
            "status": "no_call",
            "hit": False,
            "calls": 0,
            "unjudgeable": 0,
            "delivered_chars": [],
            "detail_chars": [],
            "pointer_dropped": [],
            "reexcerpted": [],
            "hit_counts": [],
            "source_pages": [],
            "summary": "no kb_search call",
        }
    if unjudgeable:
        return {
            "status": "unjudgeable",
            "hit": False,
            "calls": calls,
            "unjudgeable": unjudgeable,
            "delivered_chars": delivered,
            "detail_chars": detail_chars,
            "pointer_dropped": pointer_dropped,
            "reexcerpted": reexcerpted,
            "hit_counts": hit_counts,
            "source_pages": source_pages,
            "summary": f"不可判：{unjudgeable}/{calls} 次 kb_search 缺 telemetry 字段",
        }
    return {
        "status": "judgeable",
        "hit": False,
        "calls": calls,
        "unjudgeable": 0,
        "delivered_chars": delivered,
        "detail_chars": detail_chars,
        "pointer_dropped": pointer_dropped,
        "reexcerpted": reexcerpted,
        "hit_counts": hit_counts,
        "source_pages": source_pages,
        "summary": f"kb_search calls={calls} chars={delivered} hits={hit_counts}",
    }


def _run_date(run_id: str) -> date | None:
    matched = _RUN_DATE_RE.match(run_id)
    if not matched:
        return None
    try:
        return datetime.strptime(matched.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _in_window(run_id: str, since: date, until: date) -> bool:
    run_day = _run_date(run_id)
    if run_day is None:
        return False
    return since <= run_day <= until


def _looks_like_run_dir(path: Path) -> bool:
    return path.is_dir() and path.name.startswith("run_") and (
        path / "continuous-episode.json"
    ).is_file()


def iter_run_dirs(roots: list[Path]) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        root = root.expanduser()
        if not root.exists():
            continue
        candidates: list[Path] = []
        if _looks_like_run_dir(root):
            candidates.append(root)
        else:
            candidates.extend(sorted(root.glob("run_*")))
            candidates.extend(sorted(root.glob("*/runs/run_*")))
            candidates.extend(sorted(root.glob("runs/run_*")))
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen or not _looks_like_run_dir(candidate):
                continue
            seen.add(resolved)
            found.append(candidate)
    return found


def _load_episode(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "continuous-episode.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def audit(
    runs_dirs: list[Path],
    *,
    since: str,
    until: str,
) -> dict[str, Any]:
    since_d = date.fromisoformat(since)
    until_d = date.fromisoformat(until)
    hits: dict[str, list[dict[str, str]]] = {shape: [] for shape in SHAPES}
    unjudgeable = {"A": 0}
    scanned = 0
    by_qtype: dict[str, dict[str, int]] = {}
    iii_unjudgeable = 0
    iii_judgeable = 0
    iii_no_call = 0
    iii_chars: list[int] = []
    iii_detail: list[int] = []
    iii_detail_missing = 0
    iii_hits: list[int] = []
    for run_dir in iter_run_dirs(runs_dirs):
        run_id = run_dir.name
        if not _in_window(run_id, since_d, until_d):
            continue
        episode = _load_episode(run_dir)
        if episode is None:
            continue
        scanned += 1
        verdict = inspect_episode(episode)
        if verdict["A"]["status"] == "unjudgeable":
            unjudgeable["A"] += 1
        for shape in SHAPES:
            if verdict[shape]["hit"]:
                hits[shape].append(
                    {"run_id": run_id, "summary": str(verdict[shape]["summary"])}
                )
        shape_i = verdict["I"]
        bucket = by_qtype.setdefault(
            str(shape_i["question_type"]),
            {"n": 0, "authorized": 0, "planned": 0, "called": 0},
        )
        bucket["n"] += 1
        if shape_i["authorized"]:
            bucket["authorized"] += 1
        if shape_i["planned"]:
            bucket["planned"] += 1
        if shape_i["called"]:
            bucket["called"] += 1
        shape_iii = verdict["III"]
        if shape_iii["status"] == "no_call":
            iii_no_call += 1
        else:
            iii_unjudgeable += int(shape_iii["unjudgeable"])
            complete = int(shape_iii["calls"]) - int(shape_iii["unjudgeable"])
            iii_judgeable += complete
            iii_chars.extend(int(item) for item in shape_iii["delivered_chars"])
            iii_hits.extend(int(item) for item in shape_iii["hit_counts"])
            for item in shape_iii.get("detail_chars", []):
                if item is None:
                    iii_detail_missing += 1
                else:
                    iii_detail.append(int(item))
    totals = {"n": 0, "authorized": 0, "planned": 0, "called": 0}
    for bucket in by_qtype.values():
        for key in totals:
            totals[key] += bucket[key]
    return {
        "since": since,
        "until": until,
        "scanned": scanned,
        "counts": {shape: len(hits[shape]) for shape in SHAPES},
        "unjudgeable": unjudgeable,
        "hits": hits,
        "inputside": {
            "shape_I": {
                "by_question_type": by_qtype,
                "totals": totals,
            },
            "shape_III": {
                "kb_calls": iii_judgeable + iii_unjudgeable,
                "judgeable": iii_judgeable,
                "unjudgeable": iii_unjudgeable,
                "no_call_runs": iii_no_call,
                "delivered_chars": iii_chars,
                # evidence[].detail 通道（V3 粗管道）；missing = 字段落地前的存量调用
                "detail_chars": iii_detail,
                "detail_chars_missing": iii_detail_missing,
                "hit_counts": iii_hits,
            },
        },
    }


def render_report(report: dict[str, Any]) -> str:
    lines = [
        f"窗 {report['since']}..{report['until']}  scanned={report['scanned']}",
        (
            f"A  引了没绑     hits={report['counts']['A']}"
            f"  不可判={report['unjudgeable']['A']}"
        ),
        f"B  契约不可满足 hits={report['counts']['B']}",
        f"C  破坏发生     hits={report['counts']['C']}",
        f"D  预取名漏网   hits={report['counts']['D']}",
    ]
    inputside = report.get("inputside") or {}
    shape_i = _as_dict(inputside.get("shape_I"))
    shape_iii = _as_dict(inputside.get("shape_III"))
    if shape_i or shape_iii:
        lines.append("")
        lines.append("输入侧")
        totals = _as_dict(shape_i.get("totals"))
        lines.append(
            "I  题形×KB     "
            f"n={totals.get('n', 0)} "
            f"authorized={totals.get('authorized', 0)} "
            f"planned={totals.get('planned', 0)} "
            f"called={totals.get('called', 0)}"
        )
        by_type = _as_dict(shape_i.get("by_question_type"))
        for qtype, bucket in sorted(by_type.items()):
            row = _as_dict(bucket)
            lines.append(
                f"   {qtype}  n={row.get('n', 0)} "
                f"authorized={row.get('authorized', 0)}/"
                f"{row.get('n', 0)} "
                f"planned={row.get('planned', 0)}/{row.get('n', 0)} "
                f"called={row.get('called', 0)}/{row.get('n', 0)}"
            )
        unjudgeable_iii = int(shape_iii.get("unjudgeable") or 0)
        lines.append(
            "III kb_search 送达  "
            f"judgeable={shape_iii.get('judgeable', 0)} "
            f"不可判={unjudgeable_iii} "
            f"no_call_runs={shape_iii.get('no_call_runs', 0)}"
        )
    listed = False
    for shape in SHAPES:
        rows = report["hits"][shape]
        if not rows:
            continue
        if not listed:
            lines.append("")
            lines.append("非零 run")
            listed = True
        for row in rows:
            lines.append(f"{shape}  {row['run_id']}  {row['summary']}")
    return "\n".join(lines) + "\n"


def _default_users_root() -> Path:
    raw = os.environ.get("FORESIGHT_USERS_DIR")
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    return Path.home() / ".local/share/finance-workbench/users"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-dir",
        action="append",
        type=Path,
        dest="runs_dirs",
        help="run 根、users 根、或单个 run_* 目录；可重复。默认 workbench users",
    )
    parser.add_argument(
        "--since",
        default=(today - timedelta(days=6)).isoformat(),
        help="窗起点（含），默认今天往前 6 天（7 日窗）",
    )
    parser.add_argument(
        "--until",
        default=today.isoformat(),
        help="窗终点（含），默认今天",
    )
    parser.add_argument("--json", action="store_true", help="机器可读")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    roots = args.runs_dirs or [_default_users_root()]
    report = audit(roots, since=args.since, until=args.until)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(render_report(report))
    if report["counts"]["B"] or report["counts"]["C"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
