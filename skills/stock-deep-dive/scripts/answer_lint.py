#!/usr/bin/env python3
"""个股深挖 / 复盘先验 最终稿质检门（exit-code 门）。

定位：stock-deep-dive skill 的硬关卡。把 agent-memory 里「95 分生成路径 +
自审框架」的覆盖率检查从散文约定硬化成 exit-code 门，体例同
`task-planner/check_task_plan.py`。

设计取舍：答案是自然叙事（不机械分块），所以不检查固定标题，而是按
「维度 → 关键词组」做覆盖率匹配：每个维度给一组同义关键词，命中任一即算覆盖。
关键词组宁松勿紧——本门的目标是拦「整个视角漏掉」，不是拦措辞。

用法::

    python3 skills/stock-deep-dive/scripts/answer_lint.py <answer.md> --type deep-dive
    python3 skills/stock-deep-dive/scripts/answer_lint.py <answer.md> --type forecast
    python3 skills/stock-deep-dive/scripts/answer_lint.py --list-dims

退出码 0 = 全部维度覆盖可交付，1 = 有缺失维度（打印 MISSING 列表），2 = 用法错误。
只读脚本：不抓数据、不写任何库。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 每个维度：(维度名, 说明, [关键词组——命中任一即覆盖])
_DEEP_DIVE_DIMS: list[tuple[str, str, list[str]]] = [
    (
        "market_context",
        "市场状态/盘面融合：大盘阶段、量能、涨家数/双红/涨停热度",
        ["大盘", "市场阶段", "涨家数", "双红", "涨停热度", "量能", "成交额", "市场情绪"],
    ),
    (
        "company_reality",
        "公司本体：真实主营/业务是什么",
        ["主营", "真实业务", "业务本体", "收入结构", "主业", "基本盘"],
    ),
    (
        "market_value_scorecard",
        "市场价值成绩单（D1）：区间/峰值涨幅、回撤、收益保留、相对强度",
        ["峰值涨幅", "区间涨幅", "回撤", "收益保留", "相对强度", "半衰期"],
    ),
    (
        "evidence_layering",
        "证据分层（D2）：硬证据 vs 弱证据/研报推断，显式区分",
        ["硬证据", "证据硬度", "L3", "研报推断", "弱证据", "候选证据", "证据分层"],
    ),
    (
        "counter_evidence",
        "反证/证据缺口",
        ["反证", "证据缺口", "缺口", "反面", "风险点", "证伪信号"],
    ),
    (
        "lifecycle",
        "逻辑生命周期：阶段判断 + 升级/降级/证伪条件",
        ["生命周期", "升级条件", "降级", "证伪", "阶段判断", "高位分歧", "逻辑唤醒"],
    ),
    (
        "second_derivative",
        "二阶导/替代表达（D3）：更优表达是谁、研究应发散到哪",
        ["二阶导", "替代表达", "更优表达", "替代队列", "产业瓶颈", "发散"],
    ),
    (
        "conditional_conclusion",
        "条件化结论：如果…则…/触发条件，不许单一定论",
        ["如果", "若", "触发条件", "一旦", "则需", "满足以下"],
    ),
]

_FORECAST_DIMS: list[tuple[str, str, list[str]]] = [
    (
        "market_stage_volume",
        "市场阶段与量能承接",
        ["市场阶段", "量能", "成交额", "承接", "大盘", "涨家数"],
    ),
    (
        "double_red_marginal",
        "双红/边际量约束：区分放量新启动 vs 缩量修复",
        ["双红", "边际量", "diff_ratio", "缩量", "放量", "存量抱团"],
    ),
    (
        "overnight_info",
        "外盘/隔夜信息（含 source_trade_date 或未取到声明）",
        ["外盘", "隔夜", "美股", "纳指", "费半", "source_trade_date", "未取到外盘"],
    ),
    (
        "sellside_weight",
        "卖方/机构信息权重（或显式未读取）",
        ["卖方", "机构", "胜率", "覆盖密度", "未读取卖方", "研报"],
    ),
    (
        "strategy_selection",
        "策略选择结果：策略一二三四选谁、对应题材/个股、为什么",
        ["策略一", "策略二", "策略三", "策略四", "策略组合", "未读取候选池"],
    ),
    (
        "verification_plan",
        "次日验证条件：怎么算命中/证伪",
        ["验证", "命中", "证伪", "观察点", "确认信号"],
    ),
    (
        "counter_scenario",
        "反证/风险情形",
        ["反证", "风险情形", "失败情形", "反面", "如果走弱", "风险点"],
    ),
]

_TYPES = {"deep-dive": _DEEP_DIVE_DIMS, "forecast": _FORECAST_DIMS}


def lint(text: str, answer_type: str) -> list[tuple[str, str]]:
    """返回缺失维度 [(维度名, 说明)]；空列表 = 全覆盖。"""
    missing: list[tuple[str, str]] = []
    for name, desc, keywords in _TYPES[answer_type]:
        if not any(kw in text for kw in keywords):
            missing.append((name, desc))
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description="个股深挖/复盘先验最终稿质检门")
    parser.add_argument("answer", nargs="?", help="最终稿 markdown 文件路径")
    parser.add_argument("--type", choices=sorted(_TYPES), default="deep-dive")
    parser.add_argument("--list-dims", action="store_true", help="列出全部维度后退出")
    args = parser.parse_args()

    if args.list_dims:
        for t, dims in _TYPES.items():
            print(f"[{t}]")
            for name, desc, _ in dims:
                print(f"  - {name}: {desc}")
        return 0

    if not args.answer:
        print("用法错误：缺少最终稿文件路径（或用 --list-dims）", file=sys.stderr)
        return 2
    path = Path(args.answer)
    if not path.is_file():
        print(f"用法错误：文件不存在 {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8", errors="replace")
    missing = lint(text, args.type)
    total = len(_TYPES[args.type])
    covered = total - len(missing)

    if missing:
        print(f"MISSING ({covered}/{total} 维度覆盖，type={args.type}):")
        for name, desc in missing:
            print(f"  - {name}: {desc}")
        print("\n按缺失维度补写后重跑本脚本；两轮仍不过 → 答案开头标注低置信再交付。")
        return 1

    print(f"OK: {covered}/{total} 维度全覆盖（type={args.type}），可交付。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
