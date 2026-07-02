"""闭环健康度报告：把散在两仓的评估/沉淀/入库信号聚合成一页周报。

闭环系统的前提是可测量——没有度量就没有优化。本脚本只读不写业务数据，
聚合四路信号并输出 markdown：

1. 回答评估：``users/<id>/answer_scores.jsonl``（次数/均分/等级分布/高频缺口）
2. 经验沉淀：``users/<id>/experience_cards.jsonl``（窗口内新增卡，按来源/状态）
3. 知识库入库：知识库仓 ``wiki/log.md`` 的条目头（窗口内条数、按类型分布）
4. 跨仓回补：知识库仓 ``wiki/raw/cross-repo-ingest-queue/<date>/`` 归档任务包数

用法::

    python3 scripts/loop_health_report.py --days 7
    python3 scripts/loop_health_report.py --days 7 --out runs/loop-health.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from intelligence import userspace

# wiki/log.md 条目头：### #2177 | 2026-07-01 | sellside-coverage-cross + concept-ingest | 标题
LOG_HEADER_RE = re.compile(
    r"^### #(?P<num>\d+) \| (?P<date>\d{4}-\d{2}-\d{2})[^|]*\| (?P<type>[^|]+) \|"
)


def _kb_root(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.exists() else None
    env = os.environ.get("KB_VAULT")
    if env and Path(env).expanduser().exists():
        return Path(env).expanduser()
    sibling = ROOT.parent / "knowledge-base-private"
    return sibling if sibling.exists() else None


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _in_window(ts: str, since: date) -> bool:
    return str(ts or "")[:10] >= since.isoformat()


def _answer_scores_section(user: str | None, since: date) -> list[str]:
    us = userspace.user_space(user)
    ledger = us.root / "answer_scores.jsonl"
    rows = [r for r in _load_jsonl(ledger) if _in_window(str(r.get("ts") or ""), since)]
    lines = ["## 1. 回答评估（answer_scores.jsonl）", ""]
    if not rows:
        lines.append(f"- 窗口内无评分记录（{ledger}）。评估节点未在跑 → 闭环处于开环状态。")
        return lines
    scores = [int(r.get("total_score") or 0) for r in rows]
    grades = Counter(str(r.get("grade") or "?") for r in rows)
    failures = Counter()
    for r in rows:
        for f in r.get("failures") or []:
            failures[str(f).split("：")[0]] += 1
    lines.append(f"- 评分次数：{len(rows)}；平均分：{sum(scores) / len(scores):.1f}；最低分：{min(scores)}")
    lines.append("- 等级分布：" + "、".join(f"{g}×{n}" for g, n in sorted(grades.items())))
    if failures:
        top = "、".join(f"{k}（{v}次）" for k, v in failures.most_common(3))
        lines.append(f"- 高频缺口：{top}")
    return lines


def _experience_cards_section(user: str | None, since: date) -> list[str]:
    us = userspace.user_space(user)
    rows = [
        r
        for r in _load_jsonl(us.experience_cards_path)
        if _in_window(str(r.get("ts") or ""), since)
    ]
    lines = ["## 2. 经验沉淀（experience_cards.jsonl）", ""]
    if not rows:
        lines.append("- 窗口内无新增经验卡。")
        return lines
    by_source = Counter(str(r.get("source") or "manual") for r in rows)
    by_promotion = Counter(str(r.get("promotion") or "candidate") for r in rows)
    lines.append(f"- 新增经验卡：{len(rows)}")
    lines.append("- 按来源：" + "、".join(f"{k}×{v}" for k, v in by_source.most_common()))
    lines.append("- 按状态：" + "、".join(f"{k}×{v}" for k, v in by_promotion.most_common()))
    pending = by_promotion.get("candidate", 0)
    if pending:
        lines.append(f"- ⚠ {pending} 张 candidate 待人工复核升级（promoted/methodology 才有长期权重）。")
    return lines


def _kb_ingest_section(kb: Path | None, since: date) -> list[str]:
    lines = ["## 3. 知识库入库（wiki/log.md）", ""]
    if kb is None:
        lines.append("- 未找到知识库仓（设 KB_VAULT 或 --kb-root）。")
        return lines
    log_path = kb / "wiki" / "log.md"
    if not log_path.exists():
        lines.append(f"- 未找到 {log_path}。")
        return lines
    by_type: Counter[str] = Counter()
    total = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        m = LOG_HEADER_RE.match(line)
        if not m or m.group("date") < since.isoformat():
            continue
        total += 1
        by_type[m.group("type").strip()] += 1
    if not total:
        lines.append("- 窗口内无入库条目。")
        return lines
    lines.append(f"- 入库条目：{total}")
    lines.append("- 按类型：" + "、".join(f"{k}×{v}" for k, v in by_type.most_common(8)))
    return lines


def _cross_repo_queue_section(kb: Path | None, since: date) -> list[str]:
    lines = ["## 4. 跨仓回补队列（cross-repo-ingest-queue）", ""]
    if kb is None:
        lines.append("- 未找到知识库仓，跳过。")
        return lines
    queue_dir = kb / "wiki" / "raw" / "cross-repo-ingest-queue"
    if not queue_dir.exists():
        lines.append("- 尚无归档任务包目录。")
        return lines
    days = sorted(
        d.name for d in queue_dir.iterdir() if d.is_dir() and d.name >= since.isoformat()
    )
    if not days:
        lines.append("- 窗口内无归档任务包。")
        return lines
    n_files = sum(
        1 for d in days for f in (queue_dir / d).iterdir() if f.suffix == ".json"
    )
    lines.append(f"- 窗口内归档 {len(days)} 天、{n_files} 个任务包：{('、'.join(days))}")
    return lines


def build_report(*, days: int, user: str | None, kb_root: str | None, today: date | None = None) -> str:
    anchor = today or date.today()
    since = anchor - timedelta(days=days)
    kb = _kb_root(kb_root)
    sections = [
        f"# 闭环健康度报告（{since.isoformat()} ～ {anchor.isoformat()}）",
        "",
        f"> 数据窗口 {days} 天；用户 `{userspace.resolve_user_id(user)}`；"
        f"知识库仓：{kb if kb else '未找到'}",
        "",
    ]
    for part in (
        _answer_scores_section(user, since),
        _experience_cards_section(user, since),
        _kb_ingest_section(kb, since),
        _cross_repo_queue_section(kb, since),
    ):
        sections.extend(part)
        sections.append("")
    return "\n".join(sections).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="闭环健康度报告（评估/沉淀/入库/跨仓回补聚合）")
    parser.add_argument("--days", type=int, default=7, help="统计窗口天数（默认 7）")
    parser.add_argument("--user", default=None, help="用户 id（默认 default 或 FORESIGHT_USER）")
    parser.add_argument("--kb-root", default=None, help="知识库仓路径（默认 KB_VAULT 或同级目录自动探测）")
    parser.add_argument("--out", default=None, help="写出 markdown 文件；不指定则打印到 stdout")
    args = parser.parse_args()

    report = build_report(days=args.days, user=args.user, kb_root=args.kb_root)
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"已写出 → {out}")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
