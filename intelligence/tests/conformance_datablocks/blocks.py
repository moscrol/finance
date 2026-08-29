"""参数表（逐块，解析器数）+ 能力声明表 + 探针 provider 工厂 + 装配面 AST 扫描。

缝：``ask_planner.DataBlockProvider``（name/label/applies/collect）×
``evidence_registry.REGISTRY`` 的 N 个命名块 × ``run_providers`` 运行器。
与工具缝（``conformance_tools``）同为「一名一实现共用壳」形状：门控语义与
运行器契约由 ``evidence_registry`` / ``ask_planner`` **单点强制**，N 个块在
这两层是同一实现的 N 份配置——默认声明全 SUPPORTED 是如实读数。

漂移入口在**装配面**（``ask.py`` 内联闭包，各块 applies/collect 独立演化）。
本套件不重跑生产闭包（那是各块自己单测的事），但用 AST 对账钉住
「注册了 ⇔ 装配了」与「装配 label == 注册 label」——工具缝那边同类对账由
pre-commit ``tool-reachability`` 门禁承担，数据块缝此前没有任何对账面。

零 import ``ask.py``：该模块导入有重依赖（装配对账只读源码文本，不执行）。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from intelligence.services import ask_planner
from intelligence.services.evidence_registry import (
    PROVIDER_NAMES,
    REGISTRY,
)

# 块个数用解析器数（AGENTS.md「数数别用固定行号」）：直接枚举唯一事实源。
BLOCK_NAMES: tuple[str, ...] = PROVIDER_NAMES

DB_INVARIANT_IDS: tuple[str, ...] = ("DB-1", "DB-2", "DB-3", "DB-4", "DB-5", "DB-6")

# 能力声明表：注册表/运行器层契约单点强制，逐块全 SUPPORTED；
# notes 承载装配面的已知形状差异（断言不靠这张表写死分支）。
BLOCK_DECLARATIONS: dict[str, dict[str, str]] = {
    name: {inv: "supported" for inv in DB_INVARIANT_IDS} for name in BLOCK_NAMES
}
BLOCK_NOTES: dict[str, str] = {
    "D3": (
        "旁路块：不经 DataBlockProvider 构造，依赖此前累积的 evidence_text，"
        "在 ask.py 各块汇总后串行收尾，但同受 provider_enabled 门控（装配对账"
        "对它豁免构造面、改验门控调用存在）。"
    ),
    "MAINLINE_KB": (
        "旁路块：不经构造面，在 market-review 路径直接生成知识锚定块"
        "（ask.py ~L907/L976），同受 provider_enabled 门控——与 D3 同一豁免档。"
    ),
    "D5": (
        "构造为 provider 并行取数，但汇总顺序特殊：outcome 被暂存、排在 D3 之后"
        "拼接（ask.py 注释「D5 按原有顺序在 D3 之后汇总」）。运行器层顺序契约"
        "不受影响——特殊排序发生在消费侧。"
    ),
    "MARKET_DAILY": (
        "旁路块：与 M（用户记忆）严格区分的同日结构化市场总览，走 owner 侧"
        "预取（agent market_data 工具的 mainline_current 档）。曾是本套件首跑"
        "抓到的绕门控缺陷（原 baseline DB-6 条目），R-20260829-02 接上"
        " provider_enabled 门控后转为合法旁路：被裁剪时零下游取数、trace 留"
        " skipped 痕、缺口经完成层如实声明。"
    ),
}

# 旁路块：不走 DataBlockProvider 构造面，但必须仍受 provider_enabled 门控。
BYPASS_BLOCKS: tuple[str, ...] = ("D3", "MAINLINE_KB", "MARKET_DAILY")

# 装配面已知缺口（登记为 finding，不改生产代码、不入 baseline——baseline 收
# 「运行器/注册表层红」，本条是装配面观测性缺口）：被 enabled_providers 裁剪
# 的块与意图门控未命中的块，在 provider_traces 里同样无痕，只有 progress
# stage 的计数（provider_count/outcome_count）。逐块级「为什么没取数」不可
# 事后区分——与工具缝 README「装配面差异登记」同一处置。
ASSEMBLY_FINDINGS: tuple[str, ...] = (
    "enabled_providers 裁剪与意图门控未命中在装配面同样无逐块痕迹"
    "（仅 stage 计数），事后无法区分「被裁剪」与「词面未命中」。",
)


@dataclass
class BlockProbe:
    """collect 调用观测：记录哪些块真的被取了数。"""

    collected: list[str] = field(default_factory=list)


def probe_provider(
    name: str,
    probe: BlockProbe,
    *,
    applies: bool | Callable[[], bool] = True,
    block_text: str | None = None,
    citation: object | None = None,
    collect_error: Exception | None = None,
    on_collect: Callable[[], None] | None = None,
) -> ask_planner.DataBlockProvider:
    """探针 provider：真实注册名 × 零 IO 的 applies/collect 替身。"""

    spec = next(item for item in REGISTRY if item.name == name)

    def _applies() -> bool:
        return applies() if callable(applies) else bool(applies)

    def _collect() -> tuple[str, object]:
        probe.collected.append(name)
        if on_collect is not None:
            on_collect()
        if collect_error is not None:
            raise collect_error
        text = f"{name} 探针块" if block_text is None else block_text
        return text, (citation if citation is not None else f"{name} 探针引用")

    return ask_planner.DataBlockProvider(name, spec.label, _applies, _collect)


@dataclass(frozen=True)
class DuckOptions:
    """provider_enabled 的最小鸭子型 options。

    真身 ``AskOptions`` 在 ``ask.py``——该模块导入重（本套件零 import 纪律，
    见模块 docstring），而 ``provider_enabled`` 的契约只读
    ``options.enabled_providers`` 一个属性（``evidence_registry`` 对
    ``AskOptions`` 的引用也只在 TYPE_CHECKING 下）。若它将来读第二个属性，
    这里 AttributeError 立刻红，不会静默漂移。
    """

    enabled_providers: tuple[str, ...] | None = None


# ---------------------------------------------------------------------------
# 装配面 AST 扫描（只读源码，不执行 ask.py）
# ---------------------------------------------------------------------------

_ASK_SOURCE = Path(__file__).resolve().parents[2] / "services" / "ask.py"


def _constant_str(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def assembled_provider_names_and_labels() -> dict[str, str]:
    """扫 ask.py 里全部 ``DataBlockProvider(<name>, <label>, ...)`` 构造。

    fail closed：出现认不出的构造形状（name/label 不是字符串字面量）直接抛错
    ——认不出来就当作故障，否则漏计的块会静默从对账里消失（与
    ``EpisodeScope.model_visible_names`` 同一条纪律）。
    """

    tree = ast.parse(_ASK_SOURCE.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        callee = (
            func.attr
            if isinstance(func, ast.Attribute)
            else func.id if isinstance(func, ast.Name) else ""
        )
        if callee != "DataBlockProvider":
            continue
        args: dict[str, ast.AST] = {}
        if len(node.args) >= 2:
            args["name"], args["label"] = node.args[0], node.args[1]
        for keyword in node.keywords:
            if keyword.arg in {"name", "label"}:
                args[keyword.arg] = keyword.value
        name = _constant_str(args.get("name")) if "name" in args else None
        label = _constant_str(args.get("label")) if "label" in args else None
        if name is None or label is None:
            raise AssertionError(
                f"ask.py:{node.lineno} 的 DataBlockProvider 构造 name/label "
                "不是字符串字面量——装配对账认不出来，先修扫描器再合入"
            )
        if name in found:
            raise AssertionError(f"ask.py 对块 {name} 有重复构造")
        found[name] = label
    return found


def gate_call_present(name: str) -> bool:
    """块的 ``provider_enabled`` 门控调用是否存在于 ask.py（源码文本证据）。

    旁路块（不走构造面）靠它证明仍受注册表门控；构造面块的门控在各自
    applies 闭包里，同样是这条调用。
    """

    return f'provider_enabled(options, "{name}")' in _ASK_SOURCE.read_text(
        encoding="utf-8"
    )
