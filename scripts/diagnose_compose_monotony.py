#!/usr/bin/env python3
"""Compose 单调专项诊断（方案 0）：扫近 N 个 run 统计降级原因 + D 块重合度。

用途：回答「为什么 compose 输出看起来总是模板/同质」——三个嫌疑逐一量化：
1. 门禁拒绝率：answer_synthesis 的 fallback_reason 里 quality_gate_rejected 占比
   （高 → 静默降级为模板是主因，优先做逐段质检）；
2. LLM 不可用率：未配置 key / 超时占比（高 → 先修基础设施）；
3. 证据同质化：各 run 命中的 D 块集合两两 Jaccard 重合度（高 → 规则门控
   让不同问题取到同一批块，优先做 LLM 检索 planner）。

只读诊断，不写任何数据。用法：

    python3 scripts/diagnose_compose_monotony.py \
        --runs-root intelligence/users/default/runs \
        --runs-root /path/to/other/runs \
        --limit 50 [--json-out report.json]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from itertools import combinations
from pathlib import Path

# answer.md 里渲染的引用标记，例如 [D6] [W7] [M] [V]；S/G/R/W/E/L 是检索源，
# D0-D9/W7/M/V 是数据块（与 evidence_registry 注册表对应）。
_BLOCK_TAG_RE = re.compile(r"\[(D\d|W7|M|V)\d*\]")


def _iter_run_dirs(roots: list[Path], limit: int) -> list[Path]:
    run_dirs = [
        path
        for root in roots
        for path in root.glob("run_*")
        if path.is_dir()
    ]
    # run 目录名带时间戳，倒序即最近优先。
    return sorted(run_dirs, key=lambda p: p.name, reverse=True)[:limit]


def _synthesis_record(run_dir: Path) -> dict | None:
    trace = run_dir / "trace.jsonl"
    if not trace.is_file():
        return None
    record: dict | None = None
    for line in trace.read_text(encoding="utf-8").splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("name") == "answer_synthesis":
            record = data  # 取最后一条（重试后以最终结果为准）
    return record


def _classify_fallback(reason: str) -> str:
    lowered = reason.lower()
    if "quality_gate" in lowered:
        return "quality_gate_rejected"
    if "未配置" in reason or "no key" in lowered or "api_key" in lowered:
        return "llm_not_configured"
    if "超时" in reason or "timeout" in lowered or "deadline" in lowered:
        return "llm_timeout"
    return reason


def _quality_issue_codes(run_dir: Path) -> list[str]:
    spec_path = run_dir / "answer_spec.json"
    if not spec_path.is_file():
        return []
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    quality = spec.get("quality")
    if not isinstance(quality, dict):
        return []
    codes: list[str] = []
    for issue in quality.get("issues") or []:
        if isinstance(issue, dict):
            code = str(issue.get("code") or issue.get("rule") or "").strip()
            if code:
                codes.append(code)
        elif isinstance(issue, str) and issue.strip():
            codes.append(issue.strip())
    return codes


def _block_tags(run_dir: Path) -> frozenset[str]:
    answer = run_dir / "answer.md"
    if not answer.is_file():
        return frozenset()
    return frozenset(_BLOCK_TAG_RE.findall(answer.read_text(encoding="utf-8")))


def diagnose(roots: list[Path], limit: int) -> dict:
    run_dirs = _iter_run_dirs(roots, limit)
    fallback_counter: Counter[str] = Counter()
    issue_counter: Counter[str] = Counter()
    block_counter: Counter[str] = Counter()
    block_sets: list[frozenset[str]] = []
    synthesized = 0
    no_trace = 0

    for run_dir in run_dirs:
        record = _synthesis_record(run_dir)
        if record is None:
            no_trace += 1
        else:
            synthesized += 1
            summary = record.get("output_summary")
            if isinstance(summary, str):
                try:
                    summary = json.loads(summary)
                except json.JSONDecodeError:
                    summary = {}
            summary = summary if isinstance(summary, dict) else {}
            stream = summary.get("stream") or {}
            reason = (
                summary.get("fallback_reason")
                or (stream.get("fallback_reason") if isinstance(stream, dict) else None)
            )
            if summary.get("status") == "validated" and not reason:
                fallback_counter["validated（无降级）"] += 1
            else:
                fallback_counter[_classify_fallback(str(reason or "未知原因"))] += 1
        for code in _quality_issue_codes(run_dir):
            issue_counter[code] += 1
        tags = _block_tags(run_dir)
        if tags:
            block_sets.append(tags)
            block_counter.update(tags)

    overlaps = [
        len(a & b) / len(a | b)
        for a, b in combinations(block_sets, 2)
        if a | b
    ]
    total = synthesized or 1
    return {
        "scanned_runs": len(run_dirs),
        "synthesis_runs": synthesized,
        "runs_without_trace": no_trace,
        "fallback_distribution": {
            key: {"count": count, "pct": round(100 * count / total, 1)}
            for key, count in fallback_counter.most_common()
        },
        "quality_issue_distribution": dict(issue_counter.most_common()),
        "d_block": {
            "runs_with_blocks": len(block_sets),
            "block_frequency": dict(block_counter.most_common()),
            "mean_pairwise_jaccard": (
                round(sum(overlaps) / len(overlaps), 3) if overlaps else None
            ),
        },
    }


def render_report(stats: dict) -> str:
    lines = [
        "# Compose 单调专项诊断",
        "",
        f"- 扫描 run 数：{stats['scanned_runs']}（有 synthesis trace：{stats['synthesis_runs']}，无 trace：{stats['runs_without_trace']}）",
        "",
        "## 降级原因分布（占有 synthesis 的 run）",
    ]
    for key, item in stats["fallback_distribution"].items():
        lines.append(f"- {key}：{item['count']}（{item['pct']}%）")
    lines += ["", "## 质检 issue 类型分布"]
    issues = stats["quality_issue_distribution"]
    if issues:
        lines += [f"- {code}：{count}" for code, count in issues.items()]
    else:
        lines.append("-（无质检 issue 记录）")
    d_block = stats["d_block"]
    lines += [
        "",
        "## D 块证据同质化",
        f"- 含数据块引用的 run：{d_block['runs_with_blocks']}",
        f"- 两两 Jaccard 重合度均值：{d_block['mean_pairwise_jaccard']}"
        "（>0.7 视为高度同质，建议启用 LLM 检索 planner）",
        "- 各块命中频次：" + (
            "、".join(f"{tag}×{count}" for tag, count in d_block["block_frequency"].items())
            or "（无）"
        ),
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root", action="append", required=True,
        help="run 目录的父目录（可重复传多个）",
    )
    parser.add_argument("--limit", type=int, default=50, help="最近 N 个 run（默认 50）")
    parser.add_argument("--json-out", help="同时把统计写成 JSON 文件")
    args = parser.parse_args()

    roots = [Path(root).expanduser() for root in args.runs_root]
    missing = [str(root) for root in roots if not root.is_dir()]
    if missing:
        raise SystemExit(f"runs-root 不存在：{'、'.join(missing)}")
    stats = diagnose(roots, args.limit)
    print(render_report(stats))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8",
        )


if __name__ == "__main__":
    main()
