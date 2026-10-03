#!/usr/bin/env python3
"""数值门禁掩码候选的存证 A/B：比较旧版与当前代码的数量抽取。

2026-10-03 收口仅纳入列表序号修复；日期候选因新增误报未纳入。
本脚本始终按实际导入的当前正则计数，不把尚未通过的候选当成已部署修复。

- ``date``：短日期掩码（见下）。
- ``list_label``：句首列表序号剥离把小数 / 区间拦腰截断——``10.37 元是关键支撑…`` 被剥成
  ``37 元``：证据里有 10.37 也挂「37」（误报），证据里没有时点名的也是错的数。

背景（2026-10-01）：数值门禁抽数前用 ``_DATE_TOKEN_RE`` 掩日期，「MM.DD / MM-DD」短写
连带掩掉了 ``10.25元``、``12.15%``、``11.30亿``、``10-15倍`` 这类数量——条件句里的
阈值因此不受审（「若跌破 9.25 元则止损」挂待核，「若跌破 10.25 元则止损」放行）。
修复后，后面紧跟数量单位的短写按数量审。

本脚本只读、不调模型、不重跑核验器：扫 ``<runs-dir>/*/answer.md``，逐句比较新旧两版
正则，输出「新放出来受审」的 token 及所在句子，供人工逐条判断它们是复述证据还是
自拟阈值（与 post986 的 950 run A/B 同一纪律：消失 / 新增逐条核对）。条件句标 ``cond``——
数值门禁只审条件句，非条件句里的这些 token 修前修后行为相同。

用法::

    python3 scripts/date_mask_ab.py --runs-dir runs            # 摘要 + 前 40 条
    python3 scripts/date_mask_ab.py --runs-dir runs --json     # 全量 JSON
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Direct execution needs the repository root on sys.path before project imports.

from intelligence.services.episode_semantic_verifier import _DATE_TOKEN_RE as NEW_RE  # noqa: E402
from intelligence.services.episode_semantic_verifier import (  # noqa: E402
    _LEADING_LIST_LABEL_RE as NEW_LABEL_RE,
)

# 修复前的原样正则（episode_semantic_verifier.py @ main 75693271）。
OLD_RE = re.compile(
    r"(?:20\d{2}年\d{1,2}月\d{1,2}日|"
    r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|"
    r"\d{1,2}月\d{1,2}日|"
    r"(?<!\d)(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])(?!\d)|"
    r"(?<!\d)(?:0[1-9]|1[0-2])[-/.](?:0[1-9]|[12]\d|3[01])(?!\d))"
)
OLD_LABEL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\d+|[一二三四五六七八九十]+)\s*"
    r"(?:[:：、.)）-]\s*)"
)
_LEADING_NUMBER_RE = re.compile(r"^\s*(?:[-*]\s*)?(\d+[.-]\d[\d.]*)")
_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+")
# 与核验器条件句判定同方向的粗筛（只用于给人看的标签，不参与计数口径）。
_CONDITION_HINT_RE = re.compile(r"若|如果|一旦|假如|跌破|站上|突破|回落到|升到|降到|达到|超过|低于|高于|止损|阈值|触发")


def released_tokens(sentence: str) -> list[str]:
    """旧正则掩掉、新正则不再掩的片段（即修复后新受审的数量）。"""

    new_spans = {m.span() for m in NEW_RE.finditer(sentence)}
    return [m.group(0) for m in OLD_RE.finditer(sentence) if m.span() not in new_spans]


def truncated_leading_number(sentence: str) -> str | None:
    """旧序号剥离会截断、新版保留的句首小数 / 区间（如 ``10.37``、``20-30``）。

    与核验器同序：先掩日期、再剥序号（``10-31日…`` 在剥序号前已作为日期掩掉，不算）。
    用修前的日期掩码，量的是修前流水线里真实发生过的截断。
    """

    sentence = OLD_RE.sub("", sentence)
    old, new = OLD_LABEL_RE.match(sentence), NEW_LABEL_RE.match(sentence)
    if old is None or (new is not None and new.end() == old.end()):
        return None
    number = _LEADING_NUMBER_RE.match(sentence)
    return number.group(1) if number else None


def scan(runs_dir: Path) -> dict:
    rows = []
    answers = sorted(runs_dir.glob("*/answer.md"))
    for path in answers:
        text = path.read_text(encoding="utf-8", errors="replace")
        for sentence in _SENTENCE_RE.findall(text):
            found = [("date", token) for token in released_tokens(sentence)]
            leading = truncated_leading_number(sentence)
            if leading:
                found.append(("list_label", leading))
            for kind, token in found:
                rows.append({
                    "run": path.parent.name,
                    "kind": kind,
                    "token": token,
                    "cond": bool(_CONDITION_HINT_RE.search(sentence)),
                    "sentence": sentence.strip()[:120],
                })
    return {
        "runs_scanned": len(answers),
        "runs_affected": len({r["run"] for r in rows}),
        "released_tokens": len(rows),
        "released_in_condition_sentences": sum(r["cond"] for r in rows),
        "by_kind": {k: sum(r["kind"] == k for r in rows) for k in ("date", "list_label")},
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args(argv)
    if not args.runs_dir.is_dir():
        print(f"找不到 runs 目录：{args.runs_dir}", file=sys.stderr)
        return 2
    report = scan(args.runs_dir)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(
        f"扫描 {report['runs_scanned']} 个 run；受影响 {report['runs_affected']} 个；"
        f"新受审 token {report['released_tokens']} 个（条件句 {report['released_in_condition_sentences']} 个）；"
        f"按类：{report['by_kind']}"
    )
    for row in report["rows"][: args.limit]:
        tag = "cond" if row["cond"] else "    "
        print(f"[{tag}] [{row['kind']}] {row['run']}  {row['token']!r}  {row['sentence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
