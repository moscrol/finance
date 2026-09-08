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

本脚本用**声明（元数据表）**对**真实装配函数 ``build_episode_registry`` 的产物**，
两边不一致就报警。它不跑真实 Episode，也不外呼。

> 初版拿声明本身去合成装配输入，unreachable 恒空、永不报警，还报了一次「12/12
> 一致」的假绿。判据必须取自**独立于声明**的那一侧，否则审计只是在照镜子。

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
from datetime import date
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.services.episode_factory import build_episode_context  # noqa: E402
from intelligence.services.episode_tools import (  # noqa: E402
    build_episode_registry,
)
from intelligence.services.research_tool_registry import (  # noqa: E402
    _DEFAULT_TOOL_METADATA,
    DEFAULT_RESEARCH_CAPABILITIES,
)
from intelligence.services.historical_research.episode import HistorySession  # noqa: E402
from intelligence.services.query_understanding import understand_query  # noqa: E402
from intelligence.services.research_contract import InformationCutoff  # noqa: E402
from intelligence.services.run_store import RunStore  # noqa: E402
from intelligence.services.task_frame import TaskFrame  # noqa: E402


# Explanations only: these strings never synthesize a runner or decide reachability.
_CONDITIONAL_INPUTS = {
    "memory_lookup": "已授权 memory_lookup，且传入 memory_user 或 memory_users_root 身份",
    "sub_research": "已授权 sub_research，且运行时传入绑定协调器和父证据账本的 sub_research_runner",
    "history_query": "已授权 finance_query，且真实 TaskFrame.history_intent 存在；无需 HistorySession 也可仅计算",
    "read_history_result": "已授权 finance_query、history_intent，且传入通过同用户/同会话校验的 HistorySession（临时 RunStore 探针）",
    "save_history_research": "已授权 finance_query、history_intent，且传入通过同用户/同会话校验的 HistorySession（临时 RunStore 探针）",
}


def _all_capability_frame() -> TaskFrame:
    """一个只为走通装配而存在的题面。

    ``question_type`` 取 ``valuation_estimate`` 是有讲究的：``build_episode_registry``
    只在**不是**该题型时才去读 market DB 取 as-of（episode_tools.py:412）。
    通用探针不需读行情；历史专用探针使用临时目录里的两日 fixture，不触生产库。
    """

    return TaskFrame(
        raw_question="工具可达性审计探针",
        user_goal="装配探针",
        question_type="valuation_estimate",
        subject="探针",
        subject_kind="company",
        market_scope="A股",
        timeframe="当前",
        required_outputs=("valuation_range",),
        assumptions=(),
        ambiguities=(),
        clarification_question=None,
        evidence_policy="valuation_with_current_anchor",
        confidence=0.95,
    )


def _probe_sub_research_runner(_goals: str, _context: object) -> object:
    raise AssertionError("audit probe runner must never be invoked")


def _assemble(*, extra_inputs: bool, root: Path) -> set[str]:
    """跑一次真实装配，返回产出的工具名。

    ``extra_inputs=True`` 时补上「能力授权之外还要的输入」：memory 身份（``memory_lookup``）
    与运行时按 episode 绑好的子研究 runner（``sub_research``：要协调器 + 父证据账本，
    装配层拿不到，spec 2026-09-03 §5）。这两个都是「条件装配」，报告但不算够不着。
    """

    frame = _all_capability_frame()
    # 全能力授权：审计问的是「结构性够不着」，不是「这一轮授没授权」。
    context = build_episode_context(
        frame,
        task_id=f"tool-reachability-audit-{uuid4().hex}",
        # Tool names are not capabilities: the three history tools all share
        # finance_query. Use the registry's canonical deduplicated mapping.
        capabilities=DEFAULT_RESEARCH_CAPABILITIES,
        timeout=30.0,
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=root / "finance",
        knowledge_wiki=root / "wiki-unavailable",
        memory_user="__audit_probe__" if extra_inputs else None,
        memory_users_root=root / "memory" if extra_inputs else None,
        sub_research_runner=_probe_sub_research_runner if extra_inputs else None,
    )
    return set(registry.names())


def _history_probe(root: Path, *, with_session: bool):
    """Build the real history context/registry on disposable canonical facts.

    The script only inspects registry membership; regression tests execute its
    actual history runners. No runner dict is generated from tool declarations.
    """
    finance = root / "finance"
    db_path = finance / "db" / "market_feature_store.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        with duckdb.connect(str(db_path)) as con:
            con.execute(
                "CREATE TABLE fact_sector_daily (trade_date DATE, sector_ts_code TEXT, sector_name TEXT, pct_chg DOUBLE, amount DOUBLE, diff_ratio DOUBLE)"
            )
            con.execute(
                "INSERT INTO fact_sector_daily VALUES ('2026-08-03','AUDIT.FP','审计农业',1,600,11),('2026-08-04','AUDIT.FP','审计农业',2,610,12)"
            )
            con.execute(
                "CREATE TABLE fact_market_daily (trade_date DATE,sh_index_pct_chg DOUBLE)"
            )
            con.execute(
                "INSERT INTO fact_market_daily VALUES ('2026-08-03',0),('2026-08-04',0)"
            )
            con.execute(
                "CREATE TABLE fact_stock_daily (trade_date DATE,stock_ts_code TEXT)"
            )
    question = "复盘2026-08-03到2026-08-04这波农业行情怎么走出来的，找历史失败案例"
    frame = understand_query(question).task_frame
    if frame.history_intent is None:
        raise AssertionError("real history query did not produce history_intent")
    session = None
    task_id = f"history-tool-reachability-audit-{uuid4().hex}"
    if with_session:
        store = RunStore("reachability-audit", root=root / "runs")
        run = store.create_run(question, "ask", session_id="audit-history-session")
        task_id = run.run_id
        session = HistorySession(store, run.run_id, "audit-history-session")
    context = build_episode_context(
        frame,
        task_id=task_id,
        capabilities=DEFAULT_RESEARCH_CAPABILITIES,
        timeout=30.0,
        information_cutoff=InformationCutoff(date(2026, 8, 4), "requested"),
    )
    registry = build_episode_registry(
        frame,
        context,
        finance_root=finance,
        knowledge_wiki=root / "wiki-unavailable",
        history_session=session,
    )
    return registry, context, session


def audit() -> tuple[list[str], list[str], list[str], list[str]]:
    """返回（声明的、无条件装配的、够不着的）三份名单，外加条件装配的一份。

    **装配名单必须来自真实装配函数** ``build_episode_registry``——它按
    ``allowed_capabilities`` 逐个 ``if`` 手拼 runner dict，而「声明了、runner 没接线」
    这个历史故障形状只有拿它的产物来比才抓得住。

    初版这里是用声明本身合成 runner dict 再喂 ``default_registry``，装配输入来自声明，
    于是 unreachable 恒空、永不报警——一个把假绿制度化的恒真式，而且它还真的报了一次
    「12/12 一致」的假绿。这条注释留着，因为下一个想「简化」这个函数的人会正好又走回那条路。

    **三分而不是二分**：有些工具除了能力授权还要额外输入才装配得出来
    （``memory_lookup`` 要 ``memory_user`` 或 ``memory_users_root``）。把它们算进
    「够不着」会天天误报然后被人关掉；算进「装配出来了」又会掩盖「生产忘了传身份 →
    该工具静默永不装配」这个真故障。所以单列一档，报告但不失败。
    """

    report = audit_report()
    return (
        report["declared"],
        report["assembled"],
        report["unreachable"],
        report["conditional"],
    )


def audit_report() -> dict:
    """Compare independent production assemblies and explain conditional inputs."""
    declared = sorted(_DEFAULT_TOOL_METADATA)
    with TemporaryDirectory(prefix="finance-tool-reachability-") as directory:
        root = Path(directory)
        bare = _assemble(extra_inputs=False, root=root / "bare")
        enriched = _assemble(extra_inputs=True, root=root / "enriched")
        history_bare, _, _ = _history_probe(root / "history-bare", with_session=False)
        history_full, _, _ = _history_probe(root / "history-session", with_session=True)
        contexts = {
            "general": sorted(bare),
            "general_with_identity_and_subresearch": sorted(enriched),
            "history_without_session": sorted(history_bare.names()),
            "history_with_session": sorted(history_full.names()),
        }
        reachable = enriched | set(history_bare.names()) | set(history_full.names())
    conditional = sorted(reachable - bare)
    unreachable = sorted(set(declared) - reachable)
    return {
        "declared": declared,
        "assembled": sorted(bare),
        "conditional": conditional,
        "unreachable": unreachable,
        "ok": not unreachable,
        "capability_by_tool": {
            name: _DEFAULT_TOOL_METADATA[name][0] for name in declared
        },
        "conditional_requirements": {
            name: _CONDITIONAL_INPUTS.get(
                name, "仅在附加真实装配上下文中出现；需检查对应入口"
            )
            for name in conditional
        },
        "assembly_contexts": contexts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出机器可读结果（供 CI 消费）",
    )
    args = parser.parse_args()

    report = audit_report()
    declared, assembled, unreachable, conditional = (
        report["declared"],
        report["assembled"],
        report["unreachable"],
        report["conditional"],
    )

    if args.json:
        print(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if unreachable else 0

    print("=" * 72)
    print("工具可达性审计 — 声明 vs 生产装配")
    print("=" * 72)
    print(f"  声明（_DEFAULT_TOOL_METADATA）      {len(declared)} 个")
    print(f"  无条件装配（build_episode_registry） {len(assembled)} 个")
    print(f"  条件装配（需额外输入）               {len(conditional)} 个")
    print()
    if conditional:
        print("  ⓘ 以下工具在能力授权之外还需额外输入才装配得出来：")
        for name in conditional:
            print(f"      - {name}: {report['conditional_requirements'][name]}")
        print("    这不是缺陷，但生产入口若忘了传那个输入，它会静默永不装配。")
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
