"""从源码生成运行底座的三张目录：事件 / 工具 / harness 接缝。

来源：``docs/superpowers/specs/2026-09-07-runtime-base-endstate-design.md`` §6.1 P0 第 5 条
（G8）。形状学 dsh：目录由脚本从源码生成，CI（本仓先是 pytest）比对生成物与仓内文件，
不一致即红——文档不再靠人记得改。

三张表各自的单一事实源：

- 事件：``episode_event_lanes.DURABLE_EVENT_KINDS / LIVE_EVENT_KINDS``（车道）、
  ``episode_phase._KIND_PHASE``（阶段）、``normalize_harness_trace._BENCHMARK_STEPS``
  （L1 步）、``episode_messages.MODEL_VISIBLE_TEXT_FIELDS``（投影剔正文的字段）、
  以及 AST 扫出的发射文件（与 ``test_episode_event_lanes`` 同一套扫法，只记文件不记行号——
  行号随无关改动漂移会让保鲜测试变成噪声源）。
- 工具：``research_tool_registry.default_registry`` 用哑 runner 装配出的 ``ToolSpec``
  （名字 / 能力 / 成本 / 新鲜度 / 查询范围 / 最小窗 / 参数键 / produces / 说明书）。
- harness 接缝：``ResearchHarness`` Protocol 的方法签名与 docstring 首段，按源码顺序。

用法::

    python3 scripts/gen_runtime_catalog.py            # 写 docs/runtime/*.md
    python3 scripts/gen_runtime_catalog.py --check    # 只比对，不一致 exit 1

不写时间戳、不写 revision：生成物必须是源码的纯函数，否则每次提交都会「不新鲜」。
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Mapping
import inspect
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.eval.normalize_harness_trace import _BENCHMARK_STEPS  # noqa: E402
from intelligence.services.episode_event_lanes import (  # noqa: E402
    DURABLE_EVENT_KINDS,
    LIVE_EVENT_KINDS,
)
from intelligence.services.episode_messages import (  # noqa: E402
    MODEL_VISIBLE_TEXT_FIELDS,
)
from intelligence.services.episode_phase import _KIND_PHASE  # noqa: E402
from intelligence.services.research_harness import ResearchHarness  # noqa: E402
from intelligence.services.research_tool_registry import (  # noqa: E402
    _DEFAULT_TOOL_METADATA,
    default_registry,
)

DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "runtime"
HEADER = (
    "<!-- 由 scripts/gen_runtime_catalog.py 从源码生成，不要手改。\n"
    "     再生成：python3 scripts/gen_runtime_catalog.py ；校验：--check（pytest "
    "test_runtime_catalog 也会比对）。 -->\n\n"
)

_EMITTER_MARKERS = ("EpisodeEvent(", "_add_event(", "class _EpisodeLedger", "ledger.add(")


# ── 事件发射点（与 test_episode_event_lanes 同一套扫法） ──────────────────────


def _string_constants(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _string_constants(node.body) + _string_constants(node.orelse)
    return []


def _call_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _receiver_root(func: ast.AST) -> str | None:
    if not isinstance(func, ast.Attribute):
        return None
    value = func.value
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return None


def _kinds_from_call(node: ast.Call, *, positional_index: int) -> list[str]:
    kinds: list[str] = []
    if len(node.args) > positional_index:
        kinds.extend(_string_constants(node.args[positional_index]))
    for keyword in node.keywords:
        if keyword.arg == "kind":
            kinds.extend(_string_constants(keyword.value))
    return kinds


def emitter_files_by_kind(root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """kind → 发射它的生产源文件（仓相对路径，排序去重）。"""

    result: dict[str, set[str]] = {}
    for path in sorted((root / "intelligence").rglob("*.py")):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if not any(marker in text for marker in _EMITTER_MARKERS):
            continue
        tree = ast.parse(text, filename=str(path))
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node.func)
            kinds: list[str] = []
            if name == "_add_event":
                kinds = _kinds_from_call(node, positional_index=0)
            elif name == "add" and _receiver_root(node.func) in {"ledger", "self"}:
                kinds = _kinds_from_call(node, positional_index=0)
            elif name == "EpisodeEvent":
                kinds = _kinds_from_call(node, positional_index=1)
            for kind in kinds:
                result.setdefault(kind, set()).add(relative)
    return {kind: sorted(files) for kind, files in result.items()}


# ── 渲染 ───────────────────────────────────────────────────────────────────


def _cell(value: object) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")


def render_events(root: Path = REPO_ROOT) -> str:
    emitters = emitter_files_by_kind(root)
    text_fields: dict[str, list[str]] = {}
    for kind, field in sorted(MODEL_VISIBLE_TEXT_FIELDS):
        text_fields.setdefault(kind, []).append(field)
    lines = [
        HEADER,
        "# 运行底座事件目录\n",
        "\n",
        "车道：durable 进重放日志与对账权威；live 只走实时出口。阶段来自 `episode_phase`，"
        "L1 步来自 `normalize_harness_trace`（评测口径），投影剔正文的字段来自 "
        "`episode_messages.MODEL_VISIBLE_TEXT_FIELDS`（对外 artifact 只留 sha256 与字符数）。\n",
        "\n",
        f"durable {len(DURABLE_EVENT_KINDS)} 种 · live {len(LIVE_EVENT_KINDS)} 种\n",
        "\n",
        "| kind | 车道 | 阶段 | L1 步 | 投影剔正文字段 | 发射文件 |\n",
        "|---|---|---|---|---|---|\n",
    ]
    rows = [(kind, "durable") for kind in sorted(DURABLE_EVENT_KINDS)] + [
        (kind, "live") for kind in sorted(LIVE_EVENT_KINDS)
    ]
    for kind, lane in rows:
        step = _BENCHMARK_STEPS.get(kind)
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{kind}`",
                    lane,
                    _cell(_KIND_PHASE.get(kind, "—")),
                    _cell(step[0] if step else "—"),
                    _cell(", ".join(text_fields.get(kind, [])) or "—"),
                    _cell(", ".join(f"`{f}`" for f in emitters.get(kind, [])) or "—"),
                ]
            )
            + " |\n"
        )
    return "".join(lines)


def _noop_runner(query, context):  # pragma: no cover - 装配哑 runner，不会被调
    del query, context
    return None


def render_tools() -> str:
    registry = default_registry({name: _noop_runner for name in _DEFAULT_TOOL_METADATA})
    lines = [
        HEADER,
        "# 研究工具目录\n",
        "\n",
        "来源：`research_tool_registry.default_registry`（用哑 runner 装配）+ "
        "`_TOOL_CONTRACTS`。`query_scope=episode` 的工具参数表为空，截止日在 context 上而不在参数里。"
        "说明书只写实测过的失败模式，空即合法。\n",
        "\n",
        f"{len(_DEFAULT_TOOL_METADATA)} 个工具\n",
        "\n",
        "| 工具 | 能力 | 成本 | 新鲜度 | 查询范围 | 最小窗(s) | 参数键 | produces | 描述 |\n",
        "|---|---|---|---|---|---|---|---|---|\n",
    ]
    specs = registry.authorized_specs()  # 已按 name 排序
    for spec in specs:
        # ToolSpec 里的参数表是冻结 Mapping（不是 dict），按协议判。
        properties = (
            spec.parameters.get("properties") if isinstance(spec.parameters, Mapping) else None
        )
        keys = sorted(properties) if isinstance(properties, Mapping) else []
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{spec.name}`",
                    _cell(spec.capability),
                    _cell(spec.cost),
                    _cell(spec.freshness),
                    _cell(spec.query_scope),
                    _cell(spec.min_window_seconds if spec.min_window_seconds is not None else "—"),
                    _cell(", ".join(f"`{k}`" for k in keys) or "—"),
                    _cell(", ".join(sorted(spec.produces)) or "—"),
                    _cell(spec.description),
                ]
            )
            + " |\n"
        )
    lines.append("\n## 说明书（`ToolSpec.contract`）\n\n")
    for spec in specs:
        contract = str(spec.contract or "").strip()
        lines.append(f"### `{spec.name}`\n\n")
        lines.append((contract if contract else "（空：尚无实测过的失败模式）") + "\n\n")
    return "".join(lines)


def _first_paragraph(doc: str | None) -> str:
    if not doc:
        return ""
    cleaned = inspect.cleandoc(doc)
    return cleaned.split("\n\n", 1)[0].replace("\n", " ").strip()


def render_harness_seams() -> str:
    lines = [
        HEADER,
        "# ResearchHarness 接缝目录\n",
        "\n",
        "loop 只在这些方法上调领域 harness（`research_harness.ResearchHarness`）。"
        "签名与首段 docstring 直接取自 Protocol 源码，顺序即源码顺序。"
        "改接缝先改 Protocol，本表随之再生成；接缝的取舍见 "
        "`docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md` §4。\n",
        "\n",
    ]
    members = [
        (name, value)
        for name, value in vars(ResearchHarness).items()
        if not name.startswith("_") and callable(value)
    ]
    lines.append(f"{len(members)} 个方法\n\n")
    for name, func in members:
        try:
            signature = str(inspect.signature(func))
        except (TypeError, ValueError):  # pragma: no cover - Protocol 成员皆可取签名
            signature = "(...)"
        lines.append(f"## `{name}`\n\n")
        lines.append(f"```python\ndef {name}{signature}\n```\n\n")
        summary = _first_paragraph(inspect.getdoc(func))
        lines.append((summary or "（无 docstring）") + "\n\n")
    return "".join(lines)


def render_all(root: Path = REPO_ROOT) -> dict[str, str]:
    return {
        "events.md": render_events(root),
        "tools.md": render_tools(),
        "harness-seams.md": render_harness_seams(),
    }


def check(out_dir: Path = DEFAULT_OUT_DIR, root: Path = REPO_ROOT) -> list[str]:
    """返回不新鲜的文件名（含缺失）。空列表 = 全部新鲜。"""

    stale: list[str] = []
    for name, rendered in render_all(root).items():
        path = out_dir / name
        if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
            stale.append(name)
    return stale


def write(out_dir: Path = DEFAULT_OUT_DIR, root: Path = REPO_ROOT) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, rendered in render_all(root).items():
        path = out_dir / name
        path.write_text(rendered, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="只比对，不一致 exit 1")
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT_DIR, help="输出目录（默认 docs/runtime）"
    )
    args = parser.parse_args(argv)
    if args.check:
        stale = check(args.out)
        if stale:
            print("不新鲜：" + ", ".join(stale) + "；运行 python3 scripts/gen_runtime_catalog.py")
            return 1
        print("三张目录与源码一致")
        return 0
    for path in write(args.out):
        print(f"写出 {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
