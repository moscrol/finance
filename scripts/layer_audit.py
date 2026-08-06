#!/usr/bin/env python3
"""门禁：领域层不得依赖 loop 底座。

规则一条，目录级：

    intelligence/services/**   不得 import   intelligence.runtime.*

反向允许——`runtime/` 编排领域层是正常方向。入口层（`api/`、`cli.py`、`eval/`、
`workbench_skills/`、`workflows/`）也不受约束，它们本就要组装 runtime。

## 为什么圈 runtime 而不是圈领域层

被圈起来的应该是**底座**，不是积木。底座 15 个模块、稳定、不该增长；积木 200 个、
会长。门禁圈住小而稳的那一侧，才不需要持续维护——新增模块默认落 `services/`，
自动受保护，没人需要"记得登记"。

反过来（圈领域层、维护一张白名单）实测更贵：改 40 条 import 而非 30 条，接缝要走
8 步拓扑序且中途涨到 3 条，而那张名单会漂。详见
`docs/handoffs/2026-08-06d-layer-split-and-8792-revival.md` B.1。

## TYPE_CHECKING 分两级

    runtime import 违规      → ERROR，退出码 1
    TYPE_CHECKING 块内违规   → WARN，退出码 0，但逐条列出

算违规，因为门禁保护的是"底座可替换"：领域模块的公开签名里出现 runtime 类型，
换掉底座就得回来改领域模块。运行时不耦合不代表契约不耦合。

只 WARN 不拦截，因为一刀切会逼人改用 `Any` 或裸字符串注解规避——那是丢掉类型检查
而耦合仍在，比违规本身更糟。修法是依赖倒置（让 runtime 实现 services 定义的
Protocol），不是删注解。

## 输出必须自述 revision

`exit 0` 单独看会被读成"main 上就是这样"。本仓有 5 个 worktree 各在不同分支
（含一个生产快照），不写清审的是哪棵树哪个 revision，结论无法复核。

退出码：
  0  ERROR 数未超基线
  1  ERROR 数超过基线，或有新增违规模块
  2  用不了：仓库结构不对
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG_ROOT = REPO / "intelligence"
PKG = "intelligence"

# 受保护的领域层目录。只有这里的模块受本门禁约束。
GUARDED_PREFIX = "services."

# loop 底座的物理落点。
RUNTIME_DIR = PKG_ROOT / "runtime"
RUNTIME_PREFIX = "runtime."

# 迁移前的过渡清单：`intelligence/runtime/` 尚不存在时，按模块名模拟搬迁后的分层，
# 这样门禁在搬之前就能给出基线。目录一旦建立，本清单自动失效（见 _resolve_layers）。
#
# 判别口径（后续遇到同类模块照此判，别看名字前缀）：
#   做 IO / 调模型 / 起子进程 / 管预算            → runtime/
#   只声明"长什么样"、纯变换、只有 Protocol 与数据类 → services/
PLANNED_RUNTIME_MODULES = frozenset(
    {
        "agent",
        "agent_episode",
        "agent_runtime_factory",
        "codex_headless_runtime",
        "continuous_sub_research",
        "continuous_turn_adapter",
        "conversation_orchestrator",
        "episode_finalizer",
        "episode_progress",
        "episode_tool_batch",
        "glm_agent_runtime",
        "headless_tool_gateway",
        "openai_agents_runtime",
        "sub_research",
        "turn_control_core",
    }
)

# 基线：只减不增。每断一条接缝就把这个数字减一，并在 commit 里说明断的是哪条。
ERROR_BASELINE = 1


@dataclass(frozen=True)
class Violation:
    src: str
    tgt: str
    lineno: int
    type_checking: bool
    in_function: bool

    @property
    def level(self) -> str:
        return "WARN" if self.type_checking else "ERROR"


def _revision() -> tuple[str, str, bool]:
    """返回 (branch, revision, dirty)。审的是哪棵树必须自述。"""

    def _git(*args: str) -> str:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return out.stdout.strip() if out.returncode == 0 else ""

    branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "(unknown)"
    revision = _git("rev-parse", "--short", "HEAD") or "(unknown)"
    dirty = bool(_git("status", "--porcelain"))
    return branch, revision, dirty


def _module_name(path: Path) -> str:
    rel = path.relative_to(PKG_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _source_files() -> list[Path]:
    return sorted(
        p
        for p in PKG_ROOT.rglob("*.py")
        if "tests" not in p.parts and "__pycache__" not in p.parts
    )


def _resolve_layers(modules: set[str]) -> tuple[frozenset[str], str]:
    """判定哪些模块属 runtime 层，并说明用的是哪种口径。

    目录存在就以目录为准（唯一真源，无名单可漂）；不存在则回落到迁移清单，
    让门禁在搬迁前也能给出基线。
    """
    if RUNTIME_DIR.is_dir():
        by_dir = frozenset(m for m in modules if m.startswith(RUNTIME_PREFIX))
        return by_dir, f"目录 intelligence/runtime/（{len(by_dir)} 个模块）"

    planned = frozenset(
        m
        for m in modules
        if m.startswith(GUARDED_PREFIX)
        and m[len(GUARDED_PREFIX) :] in PLANNED_RUNTIME_MODULES
    )
    return planned, (
        f"迁移清单 PLANNED_RUNTIME_MODULES（{len(planned)} 个模块，"
        "intelligence/runtime/ 尚未建立)"
    )


def _type_checking_import_ids(tree: ast.Module) -> set[int]:
    """收集 `if TYPE_CHECKING:` 块内所有 import 节点的 id。"""

    def _is_type_checking(test: ast.expr) -> bool:
        if isinstance(test, ast.Name):
            return test.id == "TYPE_CHECKING"
        if isinstance(test, ast.Attribute):
            return test.attr == "TYPE_CHECKING"
        return False

    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    ids.add(id(child))
    return ids


def _function_import_ids(tree: ast.Module) -> set[int]:
    """收集函数体内的 import 节点 id。延迟 import 仍是运行时耦合，只是位置更隐蔽。"""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    ids.add(id(child))
    return ids


def _imported_modules(node: ast.Import | ast.ImportFrom) -> list[str]:
    """一个 import 语句触及的 intelligence.* 模块名（去掉包前缀）。"""
    out: list[str] = []
    if isinstance(node, ast.ImportFrom):
        if node.level or not node.module:
            return out
        if node.module == PKG:
            # from intelligence import services  —— 触及子模块
            out.extend(alias.name for alias in node.names)
        elif node.module.startswith(PKG + "."):
            base = node.module[len(PKG) + 1 :]
            out.append(base)
            # from intelligence.services import agent_episode
            out.extend(f"{base}.{alias.name}" for alias in node.names)
        return out
    for alias in node.names:
        if alias.name.startswith(PKG + "."):
            out.append(alias.name[len(PKG) + 1 :])
    return out


def collect_violations() -> tuple[list[Violation], str, int]:
    files = _source_files()
    if not files:
        print(f"layer audit 无法运行：{PKG_ROOT} 下没有 .py 文件", file=sys.stderr)
        raise SystemExit(2)

    modules = {_module_name(p): p for p in files}
    runtime_layer, criterion = _resolve_layers(set(modules))
    if not runtime_layer:
        print(
            "layer audit 无法运行：判不出 runtime 层。"
            f"既没有 {RUNTIME_DIR}，迁移清单也没命中任何模块。",
            file=sys.stderr,
        )
        raise SystemExit(2)

    violations: list[Violation] = []
    for mod, path in sorted(modules.items()):
        if not mod.startswith(GUARDED_PREFIX) or mod in runtime_layer:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            print(f"⚠️  跳过 {mod}（语法错误 line {exc.lineno}）", file=sys.stderr)
            continue

        tc_ids = _type_checking_import_ids(tree)
        fn_ids = _function_import_ids(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            hits = {t for t in _imported_modules(node) if t in runtime_layer}
            for tgt in sorted(hits):
                violations.append(
                    Violation(
                        src=mod,
                        tgt=tgt,
                        lineno=node.lineno,
                        type_checking=id(node) in tc_ids,
                        in_function=id(node) in fn_ids,
                    )
                )
    return violations, criterion, len(modules)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="门禁：intelligence/services/** 不得 import intelligence.runtime.*"
    )
    parser.add_argument(
        "--baseline",
        type=int,
        default=ERROR_BASELINE,
        help=f"允许的 ERROR 条数上限（默认 {ERROR_BASELINE}，只减不增）",
    )
    args = parser.parse_args(argv)

    violations, criterion, module_count = collect_violations()
    branch, revision, dirty = _revision()

    errors = [v for v in violations if not v.type_checking]
    warns = [v for v in violations if v.type_checking]

    print("=" * 72)
    print("层级门禁 — intelligence/services/** 不得 import intelligence.runtime.*")
    print("=" * 72)
    print(f"  树        {REPO}")
    print(f"  分支      {branch}")
    print(f"  revision  {revision}{'  ⚠️ 工作区有未提交改动' if dirty else ''}")
    print(f"  扫描      {module_count} 个模块（不含 tests）")
    print(f"  分层依据  {criterion}")
    print()

    if errors:
        print(f"❌ ERROR {len(errors)} 条（运行时耦合，基线 {args.baseline}）")
        for v in errors:
            where = "，函数内延迟 import" if v.in_function else ""
            print(f"     {v.src}:{v.lineno}  →  {v.tgt}{where}")
        print()
    else:
        print("✅ ERROR 0 条")
        print()

    if warns:
        print(f"⚠️  WARN {len(warns)} 条（TYPE_CHECKING 块内，契约耦合，不拦截）")
        for v in warns:
            print(f"     {v.src}:{v.lineno}  →  {v.tgt}")
        print("     修法是依赖倒置：让 runtime 实现 services 定义的 Protocol，")
        print("     不要改成 Any 或裸字符串注解——那是丢掉类型检查而耦合仍在。")
        print()

    if len(errors) > args.baseline:
        print(
            f"结论：不通过。ERROR {len(errors)} 条 > 基线 {args.baseline} 条"
            f"（对 {branch}@{revision} 成立）"
        )
        return 1

    if len(errors) < args.baseline:
        print(
            f"结论：通过，且优于基线（{len(errors)} < {args.baseline}）。"
            f"请把 ERROR_BASELINE 下调到 {len(errors)}——只减不增。"
        )
    else:
        print(f"结论：通过，ERROR {len(errors)} 条 == 基线（对 {branch}@{revision} 成立）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
