#!/usr/bin/env python3
"""工具可达性审计 — 定义了的工具，生产 Scope 里够不够得着。

spec §7.2 验收第 2 条：「新增工具若只存在于测试注册表而不在生产 Scope，
审计命令必须报警」。

--------------------------------------------------------------------------
它抓的是什么
--------------------------------------------------------------------------

一个工具从「写出来」到「模型真能用上」要过四道：

    _DEFAULT_TOOL_METADATA 有声明 → runner 真的接上 → capability 被 contract
    授权 → 进入发给模型的 schema

**只有第一道是纯代码，后三道都依赖装配**。历史上出过的形状是：工具在测试注册表
里跑得好好的，生产装配少接一根线，于是它在生产里从来没被调起过——而单元测试全绿、
`/api/health` 一切正常，因为没有任何断言在问「生产装配里有它吗」。

本脚本用**声明（元数据表）**对**装配（default_registry 的产物）**，两边不一致就
报警。它不需要跑起真实 Episode，也不外呼。

--------------------------------------------------------------------------
为什么判据是「声明 vs 装配」而不是「授权与否」
--------------------------------------------------------------------------

「这一轮没授权某个能力」是**正常的**：contract 按题型给能力，quick_fact 用不上
l3_lookup 很合理。所以未授权不报警。报警的是**结构性够不着**：声明了却装配不出来，
那不管哪一轮都用不上。

退出码：0 = 一致；1 = 有工具够不着（CI 可直接用）。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.services import agent_research  # noqa: E402
from intelligence.services.research_tool_registry import (  # noqa: E402
    _DEFAULT_TOOL_METADATA,
    default_registry,
)


def _noop_runner(
    value: object,
    context: agent_research.AgentToolContext,
) -> tuple[list[object], str, object]:
    """装配探针用的空 runner。

    审计只问「装配得出来吗」，不问「跑起来对不对」——后者是单元测试的事。
    用真 runner 会把审计变成一次真实外呼。
    """

    raise AssertionError("audit runner must never be invoked")


def audit() -> tuple[list[str], list[str], list[str]]:
    """返回（声明的、装配出来的、够不着的）三份名单。"""

    declared = sorted(_DEFAULT_TOOL_METADATA)
    registry = default_registry({name: _noop_runner for name in declared})
    assembled = sorted(registry.names())
    unreachable = sorted(set(declared) - set(assembled))
    return declared, assembled, unreachable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出机器可读结果（供 CI 消费）",
    )
    args = parser.parse_args()

    declared, assembled, unreachable = audit()

    if args.json:
        print(
            json.dumps(
                {
                    "declared": declared,
                    "assembled": assembled,
                    "unreachable": unreachable,
                    "ok": not unreachable,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if unreachable else 0

    print("=" * 72)
    print("工具可达性审计 — 声明 vs 生产装配")
    print("=" * 72)
    print(f"  声明（_DEFAULT_TOOL_METADATA）  {len(declared)} 个")
    print(f"  装配（default_registry）        {len(assembled)} 个")
    print()

    if unreachable:
        print(f"❌ {len(unreachable)} 个工具声明了但生产装配里够不着：")
        for name in unreachable:
            print(f"      - {name}")
        print()
        print("  这类工具在生产里永远不会被调起，而单元测试可能全绿——")
        print("  测试注册表是自己拼的，不走 default_registry。")
        return 1

    print("✅ 声明与装配一致，无够不着的工具")
    print()
    print(f"结论：通过（对 {len(declared)} 个声明工具成立）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
