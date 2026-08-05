#!/usr/bin/env python3
"""用真实历史提问回放 operator 路由判别，产出可人工判读的命中清单。

为什么要有这个脚本（而不是每次临时探测一遍）：
    2026-08-05 排查 `_COMPARISON_RE` 误命中时，手造的样本句给出了「正则没问题」
    的结论；换成用户真实提过的 108 条 query 回放，立刻暴露出 4 条误判
    （「多少估值比较合理」「什么板块比较有机会」这类把「比较」当程度副词的
    问法）。真实语料推翻了手造样本的结论。以后凡改路由层的判别条件，都应该
    先跑这个脚本拿到证据，而不是重新造一遍样本。

刻意不做自动 TP/FP 判定：
    「这条 query 到底该不该走 comparison」是语义判断，需要人看。硬编一套
    期望标签只会产出一个看起来很高、实则由标签作者的偏见决定的准确率。
    所以本脚本只做两件事：把命中集合完整打出来给人读；以及把两次运行的命中
    集合做差集，让「这次改动动了哪些 query」变成机械可查的事实。

典型用法：
    # 看当前树的命中清单
    scripts/replay_operator_routing.py

    # 改动前后对照：先用另一棵树（旧代码）存基线，再跟当前树比
    scripts/replay_operator_routing.py --repo /path/to/old/tree --out /tmp/before.json
    scripts/replay_operator_routing.py --baseline /tmp/before.json

语料来源是 run.json 里的 `question` 字段，只读，不改代码也不写库。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Callable

SELF_ROOT = Path(__file__).resolve().parents[1]

# 语料默认落点：两个已知台账的并集，都是 <root>/<user>/runs/<run>/run.json。
# 刻意「并集」而不是「FORESIGHT_USERS_DIR 优先」：该变量在实际会话里常被指向
# 其中之一（例：指向 agent-memory/.foresight），若拿它覆盖默认值，另一个台账的
# 260+ 条真实提问会被静默漏掉，回放规模从 108 条塌到 10 条却不报错——这种
# 无声缩水会让回归证据失效，比直接报错危险得多。
CANONICAL_LEDGERS = (
    "~/.local/share/finance-workbench/users",
    "~/agent-memory/.foresight",
)


def default_ledgers() -> list[Path]:
    """规范台账 + FORESIGHT_USERS_DIR 指向，按真实路径去重后保序返回。"""
    candidates = [*CANONICAL_LEDGERS]
    override = (os.environ.get("FORESIGHT_USERS_DIR") or "").strip()
    if override:
        candidates.append(override)

    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw in candidates:
        path = Path(raw).expanduser()
        key = path.resolve() if path.exists() else path
        if key in seen:
            continue
        seen.add(key)
        resolved.append(path)
    return resolved


def build_operators(repo_root: Path) -> "OrderedDict[str, Callable[[str], bool]]":
    """从指定工作树导入判别函数。

    这里读的是 `query_understanding` 的模块级正则（带下划线的私有名）。路由层
    没有把它们包成公开 API，而回放的意义恰恰在于打到与线上完全同一个判别条件
    上，所以此处刻意直连私有名：一旦上游改名，这个脚本应该立刻 ImportError
    炸掉，而不是悄悄退化成测另一套东西。
    """
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from intelligence.services.market_analogs import parse_analog_intent
    from intelligence.services.query_understanding import (
        _COMPANY_MAPPING_RE,
        _COMPARISON_RE,
        _COUNTEREVIDENCE_RE,
        _MARKET_CHANGE_RE,
        _MONEY_FLOW_RE,
        _RELATION_RE,
        is_market_cause_query,
    )
    from intelligence.services.scenario_tree import parse_scenario_intent

    return OrderedDict(
        [
            ("history_analog", lambda q: bool(parse_analog_intent(q))),
            ("scenario_tree", lambda q: bool(parse_scenario_intent(q))),
            ("counterevidence", lambda q: _COUNTEREVIDENCE_RE.search(q) is not None),
            ("money_flow", lambda q: _MONEY_FLOW_RE.search(q) is not None),
            ("comparison", lambda q: _COMPARISON_RE.search(q) is not None),
            ("relation", lambda q: _RELATION_RE.search(q) is not None),
            ("company_mapping", lambda q: _COMPANY_MAPPING_RE.search(q) is not None),
            ("market_change", lambda q: _MARKET_CHANGE_RE.search(q) is not None),
            ("cause_attribution", lambda q: bool(is_market_cause_query(q))),
        ]
    )


def _git_head(repo_root: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def collect_questions(ledgers: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """按 run.json 收集提问，按「去掉空白后的字面」去重，保留首次出现的顺序。"""
    seen: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    per_ledger: dict[str, int] = {}
    unreadable = 0

    for root in ledgers:
        if not root.exists():
            per_ledger[str(root)] = -1  # -1 = 目录不存在，与「存在但空」区分开
            continue
        count = 0
        for path in sorted(root.glob("*/runs/*/run.json")):
            count += 1
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                unreadable += 1
                continue
            if not isinstance(payload, dict):
                continue
            question = payload.get("question")
            if not isinstance(question, str):
                continue
            key = re.sub(r"\s+", "", question.strip())
            if not key:
                continue
            record = seen.get(key)
            if record is None:
                seen[key] = {
                    "question": question.strip(),
                    "count": 1,
                    "first_run": payload.get("run_id"),
                    "task_type": payload.get("task_type"),
                }
            else:
                record["count"] += 1
        per_ledger[str(root)] = count

    stats = {
        "run_json_files": sum(n for n in per_ledger.values() if n > 0),
        "per_ledger": per_ledger,
        "unreadable_files": unreadable,
    }
    return list(seen.values()), stats


def replay(
    records: list[dict[str, Any]], operators: "OrderedDict[str, Callable[[str], bool]]"
) -> dict[str, list[dict[str, Any]]]:
    hits: dict[str, list[dict[str, Any]]] = {name: [] for name in operators}
    for record in records:
        question = record["question"]
        fired: list[str] = []
        for name, detect in operators.items():
            try:
                matched = bool(detect(question))
            except Exception as exc:  # noqa: BLE001 - 判别函数抛错要记录而非中断整轮回放
                record.setdefault("errors", []).append(f"{name}: {exc!r}")
                matched = False
            if matched:
                fired.append(name)
                hits[name].append(record)
        record["operators"] = fired
    return hits


def render_report(
    records: list[dict[str, Any]],
    hits: dict[str, list[dict[str, Any]]],
    stats: dict[str, Any],
    meta: dict[str, Any],
    show_queries: bool,
) -> str:
    lines: list[str] = []
    total = len(records)

    lines.append("=" * 78)
    lines.append("operator 路由回放（真实历史提问）")
    lines.append("=" * 78)
    lines.append(f"判别代码来自: {meta['repo']}" + (f" @ {meta['head']}" if meta.get("head") else ""))
    lines.append(f"run.json 文件数: {stats['run_json_files']}")
    for ledger, n in stats["per_ledger"].items():
        lines.append(f"  {ledger}: {'目录不存在' if n < 0 else n}")
    if stats["unreadable_files"]:
        lines.append(f"  解析失败文件: {stats['unreadable_files']}")
    lines.append(f"去重后 unique question: {total}")
    lines.append("")

    lines.append("命中规模")
    lines.append("-" * 78)
    for name in hits:
        n = len(hits[name])
        pct = (100.0 * n / total) if total else 0.0
        lines.append(f"{name:<20} {n:>3}/{total}  ({pct:4.1f}%)")
    lines.append("")

    fired_any = sum(1 for r in records if r["operators"])
    dist = Counter(len(r["operators"]) for r in records)
    lines.append(f"至少命中 1 个 operator: {fired_any}/{total}")
    lines.append(f"每题命中 operator 数分布: {dict(sorted(dist.items()))}")
    errored = [r for r in records if r.get("errors")]
    if errored:
        lines.append(f"判别过程抛错的 query: {len(errored)}")
        for record in errored:
            lines.append(f"  ! {record['question']}  {record['errors']}")
    lines.append("")

    if show_queries:
        lines.append("命中明细（需人工判读该不该命中，脚本不做判定）")
        lines.append("=" * 78)
        for name, items in hits.items():
            lines.append(f"[{name}]  n={len(items)}")
            if not items:
                lines.append("   (无命中)")
            for record in items:
                seen_n = record["count"]
                suffix = f"  (提过 {seen_n} 次)" if seen_n > 1 else ""
                lines.append(f"   - {record['question']}{suffix}")
            lines.append("")

    return "\n".join(lines)


def render_diff(
    baseline: dict[str, Any], hits: dict[str, list[dict[str, Any]]]
) -> tuple[str, bool]:
    """对照基线做集合差。只报事实，不判断哪边对。"""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("与基线对照")
    lines.append("=" * 78)
    base_meta = baseline.get("meta", {})
    lines.append(
        f"基线判别代码: {base_meta.get('repo', '?')}"
        + (f" @ {base_meta['head']}" if base_meta.get("head") else "")
    )
    lines.append(f"基线 unique question: {baseline.get('unique_questions', '?')}")
    lines.append("")

    base_hits: dict[str, list[str]] = baseline.get("hits", {})
    changed = False
    for name, items in hits.items():
        current = {r["question"] for r in items}
        before = set(base_hits.get(name, []))
        added = sorted(current - before)
        removed = sorted(before - current)
        if not added and not removed:
            lines.append(f"{name:<20} 不变  n={len(current)}")
            continue
        changed = True
        lines.append(f"{name:<20} 变化  {len(before)} -> {len(current)}")
        for question in removed:
            lines.append(f"   - 不再命中: {question}")
        for question in added:
            lines.append(f"   + 新增命中: {question}")

    only_in_base = sorted(set(base_hits) - set(hits))
    only_in_current = sorted(set(hits) - set(base_hits))
    if only_in_base or only_in_current:
        changed = True
        lines.append("")
        lines.append(f"基线独有 operator: {only_in_base or '无'}")
        lines.append(f"本次独有 operator: {only_in_current or '无'}")

    return "\n".join(lines), changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="用真实历史提问回放 operator 路由判别，输出命中清单供人工判读。"
    )
    parser.add_argument(
        "--repo",
        default=str(SELF_ROOT),
        help="从哪棵工作树导入判别代码（默认脚本自身所在仓库；改动前后对照时指向另一棵树）",
    )
    parser.add_argument(
        "--ledger",
        action="append",
        default=None,
        help=f"语料目录，可重复。默认: {', '.join(str(p) for p in default_ledgers())}",
    )
    parser.add_argument("--out", default=None, help="把完整结果写成 JSON（供下次当基线）")
    parser.add_argument("--baseline", default=None, help="与该 JSON 做命中集合差集对照")
    parser.add_argument(
        "--fail-on-change",
        action="store_true",
        help="与基线有任何命中差异时以退出码 1 结束（给 CI 当回归闸门用）",
    )
    parser.add_argument("--no-queries", action="store_true", help="只看命中规模，不打明细")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo).expanduser().resolve()
    if not (repo_root / "intelligence").is_dir():
        print(f"--repo 不像一个工作树（缺 intelligence/）: {repo_root}", file=sys.stderr)
        return 2

    ledgers = [Path(p).expanduser() for p in args.ledger] if args.ledger else default_ledgers()
    records, stats = collect_questions(ledgers)
    if not records:
        print("没收集到任何 question，检查 --ledger 指向。", file=sys.stderr)
        return 2

    operators = build_operators(repo_root)
    hits = replay(records, operators)
    meta = {"repo": str(repo_root), "head": _git_head(repo_root)}

    print(render_report(records, hits, stats, meta, show_queries=not args.no_queries))

    payload = {
        "meta": meta,
        "stats": stats,
        "unique_questions": len(records),
        "records": records,
        "hits": {name: [r["question"] for r in items] for name, items in hits.items()},
    }
    if args.out:
        out_path = Path(args.out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"完整结果 -> {out_path}")

    if args.baseline:
        baseline = json.loads(Path(args.baseline).expanduser().read_text(encoding="utf-8"))
        diff_text, changed = render_diff(baseline, hits)
        print()
        print(diff_text)
        if changed and args.fail_on_change:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
