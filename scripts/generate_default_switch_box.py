#!/usr/bin/env python3
"""从源码生成冻结默认盒 ``default-v1``。

**冻的是函数，不是名单。** 本仓的授权面逐 frame 解算——`episode_factory` 的
`_authorized_capabilities` → `runtime_capabilities_for_frame`，`evidence_plan` 的
mandatory 还会往里追加，`_is_evidence_free_task` 会把它整个清空——所以根本不存在
一排可冻结的「生产开哪些」。default-v1 只冻两样：

    1. 授权面**派生函数的符号名**（收据写 capability_source）
    2. 非工具行的 on/off 取值

于是「再生一致」这条门禁覆盖的是 (1)+(2)，**不是授权面**。不要在收据、文档或 PR 里
把它说成「冻结了生产授权面」——那句话在本仓是假的。

生成，不手抄：符号名靠 import 校验得来，改名会让生成失败而不是产出一个过期的字符串。

用法：
    python3 scripts/generate_default_switch_box.py            # 写文件
    python3 scripts/generate_default_switch_box.py --check    # 只比对，不写
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.services.capability_switchboard import load_switchboard  # noqa: E402

OUTPUT = REPO / "intelligence" / "eval" / "fixtures" / "switch_box_default_v1.json"

# 授权面的派生链。每一环都要在源码里真的存在——存在性由 import 校验，不由本文件断言。
_SOURCE_CHAIN = (
    ("intelligence.services.episode_factory", "build_episode_context"),
    ("intelligence.services.episode_factory", "_authorized_capabilities"),
    ("intelligence.services.evidence_capabilities", "runtime_capabilities_for_frame"),
)


def resolve_capability_source() -> str:
    """校验派生链存在，返回入口符号的点分名。

    符号被改名 → 这里抛 AttributeError，生成失败。比起产出一个指向不存在符号的
    capability_source，失败是更好的结果：那个字符串会被下一个 agent 当成真的去查。
    """

    import importlib

    for module_name, symbol in _SOURCE_CHAIN:
        module = importlib.import_module(module_name)
        if not hasattr(module, symbol):
            raise AttributeError(f"授权面派生链断了：{module_name}.{symbol} 不存在")
    head_module, head_symbol = _SOURCE_CHAIN[0]
    return f"{head_module}.{head_symbol}"


def _in_default_box(row) -> tuple[bool, str]:
    """这一行该不该进默认盒，以及不进的理由。

    两条边界都踩过坑，写清楚：

    - **welded 要进。** `structural-verifier` 关不掉，但它在生产里确实是**开着的**，
      默认盒描述的是「今天怎么拨的」，不是「哪些拧得动」。按 status=="active" 过滤
      会把它漏掉，盒子就不再等于生产。能不能拧是 `status` 那一列的事。
    - **canonical 不是 exists 的不进。** `predicate.single-red` 之流正典还不存在，
      把它记成 `on` 会让盒子里出现一个没有对应物的状态位，差量也无从作用。
      它们是工单，不是开关（本表里剩下 `predicate.evidence-layers`；
      `predicate.reading-baseline` 已随 r3 落地转 active/exists，默认 on 进盒）。
    """

    if row.status == "retired":
        return False, "retired"
    if row.status == "pending-other-branch":
        return False, "代码不在本底"
    if row.id.startswith("program."):
        return False, "消融开关，生产不读本表"
    if row.kind == "parameter":
        # CLI 参数的默认值不是「开关位」。放进盒子会让人以为拨它就能改行为，
        # 实际它只是某条命令的 argparse default（`param.boards-min` 就是这样）。
        return False, "CLI 参数默认值，不是开关位"
    if row.kind == "predicate" and row.canonical != "exists":
        return False, f"canonical={row.canonical}，是待建正典的工单不是开关"
    return True, ""


def _l3_env_enabled() -> bool:
    from intelligence.services.l3_evidence import _env_bool

    return _env_bool("FINANCE_L3_LOOKUP_ENABLED")


def _reject_l3_on_when_env_off(included: dict[str, str]) -> None:
    """开关板 §5.2：env 关着时不许把 l3_lookup 记成 on。"""

    if included.get("l3_lookup") == "on" and not _l3_env_enabled():
        raise ValueError("FINANCE_L3_LOOKUP_ENABLED 关着时不许把 l3_lookup 记成 on")


def build_box() -> dict:
    board = load_switchboard()
    included: dict[str, str] = {}
    excluded: dict[str, str] = {}
    ambient: list[str] = []
    for row in board.rows:
        keep, reason = _in_default_box(row)
        if not keep:
            excluded[row.id] = reason
            continue
        if row.default == "ambient":
            ambient.append(row.id)
            continue
        included[row.id] = row.default
    _reject_l3_on_when_env_off(included)
    return {
        "switch_set": "default-v1",
        "capability_source": resolve_capability_source(),
        "generated_from": "intelligence/eval/fixtures/capability_switchboard.json",
        "non_tool_defaults": dict(sorted(included.items())),
        # 故意只记名字不记取值：这些跟该题的生产合同走，逐 frame 解算。
        # 每次 run 的实际面记在收据的 resolved_capabilities 里。
        "ambient_ids": sorted(ambient),
        # 盒子自述哪些行被排除、为什么——否则「短了几行」和「本来就这么多」
        # 在下游长得一样。
        "excluded": dict(sorted(excluded.items())),
    }


def render(box: dict) -> str:
    """规范 JSON：key 排序、缩进固定、末尾换行。字节比对靠它稳定。"""

    return json.dumps(box, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只比对，不写")
    args = parser.parse_args()

    rendered = render(build_box())
    if args.check:
        if not OUTPUT.exists():
            print(f"❌ {OUTPUT.relative_to(REPO)} 不存在，先跑一次生成")
            return 1
        current = OUTPUT.read_text(encoding="utf-8")
        if current != rendered:
            print("❌ default-v1 与源码再生结果不一致（比字面量，不比个数）")
            return 1
        print("✅ default-v1 再生一致")
        return 0

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"已写 {OUTPUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
