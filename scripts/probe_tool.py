#!/usr/bin/env python3
"""单个 Agent 工具的试验场：把一个工具从 episode 里摘出来单独跑。

**为什么需要它**：2026-08-10 定位 `evidence_search` 超时，花了三次完整 live
（每次约 5 分钟 + 真实 provider 配额 + 人工比对三份收据），才把病因缩到一个工具
身上。而那个结论——「首次调用约 28s、之后 4-6s」——用这个脚本跑一次 `--repeat 2`
就能直接看出来。**整条 episode 是诊断单个工具最贵的方式。**

它与既有两个探针的分界：

| 脚本 | 测什么 |
|---|---|
| `probe_provider_latency.py` | 只测 LLM provider 快慢，不碰工具 |
| `run_episode_seam_ladder.py` | 测**一组能力**装配起来跑不跑得通（粒度=阶梯层） |
| **本脚本** | 测**单个工具**本身：多久、返回什么、空结果长什么样 |

三条刻意的设计选择：

1. **给独立且充裕的 deadline**（默认 120s），不复用 episode 那条紧张预算。
   目的是测「这个工具要多久」，不是测「预算压力下它会不会被砍」。后者是
   seam ladder 的活。混在一起就分不清「工具慢」和「预算不够」——这正是上一轮
   把 judge 误判成元凶的那个形状。
2. **默认连跑 2 次**（`--repeat`）。本仓的检索链有一次性预热成本：
   `closed_loop_retrieval.py:170` 记着 RAG worker 冷启动 60.1s / 热查询 4-6s，
   `research_owner.py:65` 记着「即使 BGE-m3 已预热，首次真实查询仍要约 28s」。
   **只跑一次必然把冷启动读成"这个工具很慢"。**

   ⚠️ 但 `--repeat` 单独用会骗你：同一个 query 第二次走查询缓存，读数是
   **0.00s**，那不是「热查询有多快」，是「缓存命中有多快」。要测真实热查询用
   `--queries A,B`——**同一个进程内换一个词再查**，那个读数才是稳态成本。
   2026-08-10 实测就是这么分开的：同 query 复跑 0.00s，换词仍要 56s。
3. **路由用 stub，不调模型**。试验场只测工具，不该烧 provider 配额，
   也不该让模型的随机性混进读数。

用法::

    scripts/probe_tool.py --list
    scripts/probe_tool.py evidence_search --query "光伏 装机"
    scripts/probe_tool.py evidence_search --query "光伏 装机" --repeat 3
    scripts/probe_tool.py --all --query "光伏"      # 12 个工具全过一遍

只读：不写 DuckDB、不写飞书、不落盘任何文件。
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.runtime.turn_control_core import TurnControlCore
from intelligence.services.episode_factory import build_episode_context
from intelligence.services.episode_tools import build_episode_registry
from intelligence.services.research_contract import (
    ResearchDeadline,
    release_root_budget,
)
from intelligence.services.research_tool_registry import (
    _DEFAULT_TOOL_METADATA,
    _TOOL_CONTRACTS,
)

ALL_TOOLS: tuple[str, ...] = tuple(_DEFAULT_TOOL_METADATA)

# 不吃 query 的三个工具（``EMPTY_TOOL_PARAMETERS``，取值由 task frame 决定）。
_EPISODE_SCOPED = frozenset({"market_data", "financial_data", "mainline_context"})

# finance_query 要的是结构化 spec 而不是一句话。给一个最小合法示例，够跑通即可；
# 真要试别的切片用 --finance-spec 传自己的 JSON。
# 注意字段必须属于所选 dataset：``market_daily`` 的成交额叫 ``total_amount``，
# ``amount`` 是 sector_*/stock_daily 那几张的字段——第一版就写错了这个，
# 而 ``validation_retry_hint`` 会跨 dataset 指出归属，照它改即可。
_DEFAULT_FINANCE_SPEC: dict[str, object] = {
    "dataset": "market_daily",
    "metrics": ["total_amount"],
    "dimensions": ["trade_date"],
    "limit": 5,
}


def _stub_llm_complete(*_args: object, **_kwargs: object):
    """路由不得调用模型——返回「没有 LLM 意见」那个形状。"""

    return (None, None, "probe-tool-offline")


def _arguments_for(tool: str, query: str, finance_spec: str | None):
    if tool == "finance_query":
        return json.loads(finance_spec) if finance_spec else _DEFAULT_FINANCE_SPEC
    if tool in _EPISODE_SCOPED:
        # 这类工具的取值范围由 task frame 定，``parse_snapshot_arguments`` 要求
        # 参数为空。必须传空 dict 而**不能**传空字符串——``prepare`` 会把任何
        # str 包成 ``{"query": ...}``，空串也一样，于是校验判定为「传了参数」。
        return {}
    return query


def _probe_once(registry, context, tool: str, arguments, index: int) -> dict:
    """跑一次，把「花了多久 + 拿到什么」压成一行读数。"""

    started = time.monotonic()
    try:
        observation = registry.execute(
            tool,
            arguments,
            context=context,
            step_id=f"probe:{tool}:{index}",
        )
    except Exception as exc:  # noqa: BLE001 - 试验场要如实报告任何失败
        return {
            "seconds": round(time.monotonic() - started, 2),
            "outcome": type(exc).__name__,
            "detail": str(exc)[:200],
        }
    elapsed = round(time.monotonic() - started, 2)
    trace = observation.trace
    return {
        "seconds": elapsed,
        "outcome": "ok",
        "status": getattr(trace, "status", None),
        "evidence": len(observation.evidence),
        "observation": (observation.observation or "")[:160],
        "gaps": list(observation.gaps or ())[:3],
    }


def _print_reading(tool: str, reading: dict, index: int, total: int) -> None:
    tag = f"[{index}/{total}]"
    if reading["outcome"] != "ok":
        print(
            f"  {tag} {reading['seconds']:>6.2f}s  ✗ {reading['outcome']}"
            f"  {reading['detail']}"
        )
        return
    print(
        f"  {tag} {reading['seconds']:>6.2f}s  status={reading['status']:<12}"
        f" evidence={reading['evidence']}"
    )
    if reading["observation"]:
        print(f"        → {reading['observation']}")
    for gap in reading["gaps"]:
        print(f"        ⚠ {gap}")


def probe(
    tool: str,
    *,
    question: str,
    queries: tuple[str, ...],
    timeout: float,
    as_of: str | None,
    finance_spec: str | None,
    memory_user: str | None = None,
) -> dict:
    """构造生产同款的 frame/context/registry，然后只调这一个工具。"""

    control = TurnControlCore().control(
        question,
        context="",
        previous_frame=None,
        previous_intent=None,
        previous_turn_id=None,
        llm_complete=_stub_llm_complete,
    )
    task_id = f"probe-tool:{tool}:{int(time.time())}"
    try:
        context = build_episode_context(
            control.task_frame,
            task_id=task_id,
            # 放宽授权面到全部工具。放宽 allowed 不会触碰
            # ``mandatory ⊆ allowed`` 这条不变量（收紧才会），所以是安全的。
            capabilities=ALL_TOOLS,
            tier="deep",
            timeout=timeout,
            today=as_of,
            latest_data_date=as_of,
        )
        allowed = context.contract.allowed_capabilities
        if tool not in allowed:
            return {
                "tool": tool,
                "skipped": (
                    f"该 task frame 未授权此能力（question_type="
                    f"{control.task_frame.question_type}）。换个 --question 再试。"
                ),
            }
        # memory_user 不传则 memory_lookup **根本不会被注册**（episode_tools 里
        # 「缺身份就不注册」是刻意的：多用户服务端上回落到 default 等于每个人
        # 都去读同一份私有台账）。试验场要能测到它，就得把身份显式传进来。
        registry = build_episode_registry(
            control.task_frame,
            context,
            memory_user=memory_user,
        )
        # 关键：给一条**独立且充裕**的 deadline。工具真实耗时才是这里要测的量，
        # 复用 episode 那条递减预算会把「工具慢」和「轮到它时没时间了」搅在一起。
        context = replace(
            context,
            deadline=ResearchDeadline.from_timeout(timeout),
        )
        readings = []
        for i, term in enumerate(queries):
            arguments = _arguments_for(tool, term, finance_spec)
            readings.append(
                _probe_once(registry, context, tool, arguments, i + 1)
            )
            readings[-1]["query"] = term
        return {"tool": tool, "readings": readings}
    finally:
        # 与 seam ladder 同一条纪律：registry 是 WeakValueDictionary，
        # 不配对释放会让下一次运行撞上一个已死的注册。
        release_root_budget(task_id)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="单个 Agent 工具的试验场（只读、不调模型）",
    )
    parser.add_argument("tool", nargs="?", help=f"工具名，可选：{', '.join(ALL_TOOLS)}")
    parser.add_argument("--list", action="store_true", help="列出 12 个工具与契约状态")
    parser.add_argument("--all", action="store_true", help="把全部工具跑一遍")
    parser.add_argument("--query", default="光伏 装机", help="传给工具的检索词")
    parser.add_argument(
        "--queries",
        default=None,
        help="逗号分隔的多个检索词，在同一进程内依次跑——测真实热查询用这个，"
        "别用 --repeat（同词第二次走缓存，读数是 0.00s）",
    )
    parser.add_argument(
        "--question",
        default="本周光伏板块为什么上涨",
        help="用来驱动路由的用户问题（决定 task frame 与授权面）",
    )
    parser.add_argument("--repeat", type=int, default=2, help="连跑几次（默认 2，看冷热差）")
    parser.add_argument("--timeout", type=float, default=120.0, help="给工具的独立预算")
    parser.add_argument("--as-of", default=None, help="数据截止日 YYYY-MM-DD")
    parser.add_argument("--finance-spec", default=None, help="finance_query 用的 JSON spec")
    parser.add_argument(
        "--memory-user",
        default=os.environ.get("FORESIGHT_USER"),
        help="memory_lookup 读谁的私有台账（默认取 FORESIGHT_USER）；不给则该工具不注册",
    )
    args = parser.parse_args()

    if args.list:
        print(f"共 {len(ALL_TOOLS)} 个工具：")
        for name in ALL_TOOLS:
            mark = "有契约" if _TOOL_CONTRACTS.get(name) else "无契约"
            print(f"  {name:<18} {mark}")
        return 0

    targets = ALL_TOOLS if args.all else ((args.tool,) if args.tool else ())
    if not targets:
        parser.error("给一个工具名，或用 --all / --list")

    if args.queries:
        queries = tuple(q.strip() for q in args.queries.split(",") if q.strip())
    else:
        queries = tuple([args.query] * max(1, args.repeat))
    print(
        f"question={args.question!r}  queries={list(queries)}  "
        f"budget={args.timeout}s"
    )
    failures = 0
    for tool in targets:
        if tool not in _DEFAULT_TOOL_METADATA:
            print(f"\n{tool}: 未知工具")
            failures += 1
            continue
        print(f"\n=== {tool} ===")
        try:
            result = probe(
                tool,
                question=args.question,
                queries=queries,
                timeout=args.timeout,
                as_of=args.as_of,
                finance_spec=args.finance_spec,
                memory_user=args.memory_user,
            )
        except Exception:  # noqa: BLE001 - 一个工具炸了不该中断整轮
            print("  构造失败：")
            traceback.print_exc(limit=3)
            failures += 1
            continue
        if "skipped" in result:
            print(f"  跳过：{result['skipped']}")
            continue
        readings = result["readings"]
        for i, reading in enumerate(readings, start=1):
            _print_reading(tool, reading, i, len(readings))
            if reading["outcome"] != "ok":
                failures += 1
        # 冷热差是这个脚本存在的主要理由，但要说准是哪一种——
        # 「同词复跑变快」是缓存命中，「换词仍慢」才是稳态成本。
        oks = [r for r in readings if r["outcome"] == "ok"]
        if len(oks) >= 2 and oks[0]["seconds"] > 2 * max(
            r["seconds"] for r in oks[1:]
        ):
            later = max(r["seconds"] for r in oks[1:])
            distinct = len({r["query"] for r in oks}) > 1
            if distinct:
                print(
                    f"        ⓘ 首次 {oks[0]['seconds']:.1f}s vs 换词后 "
                    f"{later:.1f}s——一次性预热成本，不是这个工具慢"
                )
            else:
                print(
                    f"        ⓘ 首次 {oks[0]['seconds']:.1f}s vs 同词复跑 "
                    f"{later:.1f}s——这是**查询缓存命中**，不是热查询速度。"
                    "要测稳态成本请用 --queries 换个词"
                )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
