#!/usr/bin/env python3
"""opinion-cross 复核门控（把「由 agent 复核盘面维度与硬度后定稿」散文门硬化成 exit-code 门）。

定位：opinion-cross 管线 C5（Tier 卡片报告）之后、**定稿/落地最终卡片报告之前**的检查点门。
`opinion_cross.py` 吐出的 `opportunities[]`（含机器 resonance_tier + 硬度分层）只是**机器底稿**；
SKILL.md「已知局限（交给 agent 复核）」要求 agent 逐标的复核——尤其堵三个已知坑：
  1. 主体指代（anaphora）：硬事实句以「公司…」指代时会归错主体（矽电的 3.35 亿被归到兆驰）；
  2. 市场热点维度：静态文本常无当日盘面，多为「待补」，复核须显式表态；
  3. Tier 改判：硬度/多空/预期差复核后可能改判机器 Tier。
本脚本校验这份人工复核产物：**机器命中的每个🟢硬证据标的**都有复核结论、Tier 合法、
硬证据标的已核对主体指代归属、市场热点维度已表态。**只读**，不写任何库文件、不改 opinion_cross.py。

诚实的天花板：本门只能保证「每个硬证据标的被有意识地复核过（结论非空、归属已核、热点已表态）」，
**无法**验证 agent 真的纠对了主体指代、或真的补全了盘面——这与 sellside 的观点不可枚举天花板同源，
区别在 opinion-cross 的命中标的可枚举（来自 opportunities[]），故能强制逐标的覆盖。

- 全部通过 → 打印 OK，exit 0 → 才放行定稿/落地最终卡片报告。
- 任一缺失/非法 → 打印 GATE VIOLATIONS，exit 1 → 回复核补全。
- 用法错误（缺参/JSON 解析失败）→ exit 2。

体例同知识库仓 cross-analysis/check_cross_review.py、sellside/check_opinion_review.py
（exit-0 信号门）、disclosure-archive 的 --apply 菱形门。

用法::

    python3 skills/opinion-cross/scripts/opinion_cross.py --term CPO --input stream.txt --out /tmp/oc.json
    # 人工逐标的复核，填一份 /tmp/opinion_review.json（--template 出空白模板）
    python3 skills/opinion-cross/scripts/check_opinion_review.py /tmp/oc.json /tmp/opinion_review.json

退出码 0 = 复核充分可放行，1 = 门控未过，2 = 用法/解析错误。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_TIERS = {"Tier 1", "Tier 2", "Tier 3", "排除"}

_TEMPLATE = {
    "reviewed": [
        {
            "target": "命中标的名（与 opinion_cross.json 的 opportunities[].target 对应）",
            "final_tier": "Tier 1|Tier 2|Tier 3|排除",
            "anaphora_checked": False,
            "market_heat": "市场热点维度复核：待补 / 或填当日盘面信号（涨停/异动/估值切换）",
            "note": "复核结论：硬度归属 / 多空 / 预期差 / 操作判断",
        }
    ]
}


def _is_nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_hard_evidence(opp: dict) -> bool:
    """机器底稿里该标的是否落🟢硬证据：dominant==硬证据 或 hardness.hard 非空。"""
    hardness = opp.get("hardness")
    if not isinstance(hardness, dict):
        return False
    if hardness.get("dominant") == "硬证据":
        return True
    hard = hardness.get("hard")
    return isinstance(hard, list) and len(hard) > 0


def validate(machine: dict, review: dict) -> list[str]:
    """返回门控违规说明列表；空列表表示全部通过。"""
    issues: list[str] = []

    if not isinstance(machine, dict):
        return ["机器底稿（opinion_cross.json）顶层必须是 JSON 对象"]
    if not isinstance(review, dict):
        return ["复核产物（opinion_review.json）顶层必须是 JSON 对象"]

    opportunities = machine.get("opportunities")
    if not isinstance(opportunities, list):
        return ["机器底稿缺 opportunities[]：请确认传入的是 opinion_cross.py 的 --out 产物"]

    reviewed = review.get("reviewed")
    if not isinstance(reviewed, list):
        return ["复核产物缺 reviewed[]：每个需复核的命中标的一条结论"]

    by_target: dict[str, dict] = {}
    for idx, item in enumerate(reviewed):
        if not isinstance(item, dict):
            issues.append(f"reviewed[{idx}] 不是对象")
            continue
        target = item.get("target")
        if not _is_nonempty_str(target):
            issues.append(f"reviewed[{idx}] 缺 target")
            continue
        by_target[target.strip()] = item
        if item.get("final_tier") not in _TIERS:
            issues.append(f"[{target}] final_tier 非法（得到 {item.get('final_tier')!r}）：须为 Tier 1/2/3/排除")
        if not isinstance(item.get("anaphora_checked"), bool):
            issues.append(f"[{target}] anaphora_checked 缺失：须显式 bool（是否已核对硬事实归属正确主体）")
        if not _is_nonempty_str(item.get("market_heat")):
            issues.append(f"[{target}] market_heat 缺：市场热点维度必须表态（待补也要显式写「待补」）")
        if not _is_nonempty_str(item.get("note")):
            issues.append(f"[{target}] note 缺：复核结论必填")

    # 覆盖性 + 归属核对：机器命中的每个🟢硬证据标的都必须有复核结论，且必须核过主体指代归属。
    for opp in opportunities:
        if not isinstance(opp, dict):
            continue
        target = (opp.get("target") or "").strip()
        if not target or not _is_hard_evidence(opp):
            continue
        rv = by_target.get(target)
        if rv is None:
            issues.append(f"[{target}] 机器命中为🟢硬证据，但 reviewed 里缺对应复核结论（已知局限①必做）")
            continue
        if rv.get("anaphora_checked") is not True:
            issues.append(f"[{target}] 硬证据标的：anaphora_checked 必须为 true（已核对硬事实归属正确主体，堵主体指代误归）")

    return issues


def _load(path_str: str, label: str) -> dict:
    path = Path(path_str)
    if not path.is_file():
        print(f"error: 找不到{label} {path}")
        sys.exit(2)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: {label} 不是合法 JSON：{exc}")
        sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="校验 opinion-cross 复核是否覆盖机器硬证据命中 + 核过主体指代归属（exit-0 门）。"
    )
    parser.add_argument("report", nargs="?", help="opinion_cross.py 的 --out 机器底稿 JSON")
    parser.add_argument("review", nargs="?", help="人工逐标的复核 JSON")
    parser.add_argument(
        "--template", action="store_true", help="打印一份空白复核模板后退出"
    )
    args = parser.parse_args()

    if args.template:
        print(json.dumps(_TEMPLATE, ensure_ascii=False, indent=2))
        sys.exit(0)

    if not args.report or not args.review:
        parser.print_usage()
        print("error: 需要依次传入 opinion_cross.json 与 opinion_review.json（或用 --template）")
        sys.exit(2)

    machine = _load(args.report, "机器底稿")
    review = _load(args.review, "复核产物")

    issues = validate(machine, review)

    if not issues:
        print("OPINION REVIEW GATE: OK — 复核已覆盖机器硬证据命中且核过主体指代归属，放行定稿。")
        sys.exit(0)

    print(f"OPINION REVIEW GATE VIOLATIONS — {len(issues)} 项未过，禁止定稿最终卡片报告：")
    for issue in issues:
        print(f"  [GATE] {issue}")
    sys.exit(1)


if __name__ == "__main__":
    main()
