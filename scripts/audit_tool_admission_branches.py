#!/usr/bin/env python3
"""工具目录收口的 P0 闸门 — 装配区不许按工具名写死，搬家不许唤醒中央表文案。

为什么判据一不锁函数名
----------------------
上一版把判据钉在 ``build_episode_registry`` 这个函数名上。而 P0 的第一步明文
就是「抽出 ``assemble_episode_specs``」——**把那 7 条 if 原样搬进新函数，闸门
立刻报 0、退出码 0，活还在**。锁函数名 = 给稿子规定的第一步开了后门。

所以判据一改成**按模块 + 白名单**：装配相关模块里，任何形如
``<字符串常量> in|not in <授权表>`` 的比较都算一条，除非它所在的函数在
``PREFETCH_WHITELIST`` 里（今天只有开口预取那一个，它管的不是工具登记）。
搬到哪个函数、哪个新模块都躲不掉；白名单每次运行都打印，想加得显式加。

为什么判据一不是 ``rg``
-----------------------
初版验收写的是 ``rg 'if "[a-z_]+" in context.contract.allowed_capabilities'``。
它在真实代码上只看得见 **7 条准入里的 5 条**，两个盲区互相独立：

1. ``[a-z_]+`` 不含数字，``l3_lookup`` 带个 ``3``，**即使写成闸门瞄准的那个
   单行 if 形式也匹配不上**；
2. 同行 ``if "`` 锚点，看不见多行 ``if (\\n    "memory_lookup" in ...`` 形式。

正则匹配的是文本形状，而重构改的恰恰是文本形状。

为什么判据二看装配产物
----------------------
上一版判据二只扫本文件里字面量 ``ToolSpec(name="finance_query")`` 带没带
``contract``/``produces``。但 P0 最顺手的收法是**把这三个 runner 塞进 ``tools``
再走 ``default_registry``**——中央表文案会醒，而构造发生在
``research_tool_registry.py``，扫构造器的判据在那边什么也看不见。

所以判据二真跑一次 ``build_episode_registry``（沿用
``scripts/audit_tool_reachability.py`` 那套不碰 DB 的探针题面），拿**装配出来的
spec** 看字段。AST 扫构造器降级为辅助信号，只提示不判决。

判据
----
1. 装配模块里按工具名写死的分支 = 0（预取白名单除外）。
2. 装配产物里 ``finance_query`` / ``evidence_search`` / ``memory_lookup``
   的 ``contract`` 与 ``produces`` 仍为空——它们今天就是空的，而中央表里有真
   内容。``contract`` 直接拼进模型看见的工具描述，``produces`` 会把这三个拉进
   ``check_satisfiability`` 的 declared_specs。**唤醒它们是行为变更，不是搬家。**

用法
----
    .venv-workbench/bin/python scripts/audit_tool_admission_branches.py
    .venv-workbench/bin/python scripts/audit_tool_admission_branches.py --self-test
    python3 scripts/audit_tool_admission_branches.py --static-only --rev gitea/main

退出码：0 = 两条判据都过；1 = 有判据不过；2 = 判据没能执行（fail closed）。
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

#: 装配相关模块。P1 把工具拆成一模块一文件后，``research_tools/`` 下的
#: ``catalog.py`` 与各 builder 自动进入射程——它们正是最可能把 if 搬过去的地方。
#: 两条 research_tools 通配是有意的：``Path.glob`` 的 ``**/*.py`` 能匹配直属文件，
#: 但 ``--rev`` 那条路走 ``fnmatch``，``**/`` 会被译成 ``.*/`` 从而**漏掉**
#: ``research_tools/catalog.py``。两条并列让两个代码路径的射程一致。
ASSEMBLY_GLOBS: tuple[str, ...] = (
    "intelligence/services/episode_tools.py",
    "intelligence/services/research_tools/*.py",
    "intelligence/services/research_tools/**/*.py",
)

#: **不在射程内**（按本稿落点不会有装配 if，但「顺手」会）：
#: ``episode_factory.py`` / ``research_tool_registry.py``。
#: 真要把装配挪过去，得先来这里加 glob——写在这里是让这个缺口可见，不是让它隐身。
OUT_OF_SCOPE_NOTE = (
    "episode_factory.py / research_tool_registry.py 不在射程内；"
    "装配若挪过去需先扩 ASSEMBLY_GLOBS"
)

#: 允许按能力名判断的函数——它们管的不是工具登记。
#: 每次运行都打印；要加得显式加，并在这里写清为什么不是装配。
PREFETCH_WHITELIST: dict[str, str] = {
    "_should_attach_overnight_news": "开口预取要不要附隔夜新闻，不是工具登记",
}

#: 装配产物里这三个 spec 的字段必须仍为空值（见文件头「为什么判据二看装配产物」）。
APPENDED_SPECS: tuple[str, ...] = ("finance_query", "evidence_search", "memory_lookup")

CAPABILITY_ATTR = "allowed_capabilities"
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Hit:
    module: str
    line: int
    capability: str
    negated: bool
    function: str
    source: str

    @property
    def whitelisted(self) -> bool:
        return self.function in PREFETCH_WHITELIST


# ---------------------------------------------------------------------------
# 判据一：静态——装配模块里按工具名写死的分支
# ---------------------------------------------------------------------------


def _function_spans(tree: ast.Module) -> list[tuple[str, int, int]]:
    spans = [
        (node.name, node.lineno, node.end_lineno or node.lineno)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    return sorted(spans, key=lambda item: (item[1], -(item[2] - item[1])))


def _owner(spans: list[tuple[str, int, int]], line: int) -> str:
    owner = "<module>"
    for name, start, end in spans:
        if start <= line <= end:
            owner = name
    return owner


def _mentions_capabilities(node: ast.AST, aliases: frozenset[str]) -> bool:
    """右操作数是不是那张授权表——认属性名，也认它的本地别名。

    少了别名那条，把授权表先存进一个中间变量就能绕过闸门。
    """

    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == CAPABILITY_ATTR:
            return True
        if isinstance(sub, ast.Name) and (
            sub.id == CAPABILITY_ATTR or sub.id in aliases
        ):
            return True
    return False


def _capability_aliases(tree: ast.Module) -> frozenset[str]:
    """收集「值里提到授权表」的赋值目标名；不动点迭代，别名可链式传递。"""

    aliases: set[str] = set()
    while True:
        grew = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets: list[ast.expr] = list(node.targets)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets = [node.target]
            else:
                continue
            if node.value is None or not _mentions_capabilities(
                node.value, frozenset(aliases)
            ):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    grew = True
        if not grew:
            return frozenset(aliases)


def scan(source: str, module: str = "<mem>") -> list[Hit]:
    tree = ast.parse(source)
    lines = source.splitlines()
    spans = _function_spans(tree)
    aliases = _capability_aliases(tree)
    hits: list[Hit] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare) or len(node.ops) != 1:
            continue
        op = node.ops[0]
        if not isinstance(op, (ast.In, ast.NotIn)):
            continue
        left = node.left
        if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
            continue
        if not _mentions_capabilities(node.comparators[0], aliases):
            continue
        hits.append(
            Hit(
                module=module,
                line=node.lineno,
                capability=left.value,
                negated=isinstance(op, ast.NotIn),
                function=_owner(spans, node.lineno),
                source=(
                    lines[node.lineno - 1].strip()
                    if node.lineno <= len(lines)
                    else ""
                ),
            )
        )
    return sorted(hits, key=lambda hit: (hit.module, hit.line))


def scan_spec_constructors(source: str) -> list[tuple[str, int, frozenset[str]]]:
    """辅助信号：字面量 ToolSpec(...) 有没有新设 contract/produces。

    **只提示不判决**——判决权在判据二的装配产物那一侧。走 ``default_registry``
    的收法里根本没有这样的字面量，扫构造器会全程沉默。
    """

    tree = ast.parse(source)
    found: list[tuple[str, int, frozenset[str]]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call) and getattr(node.func, "id", None) == "ToolSpec"
        ):
            continue
        supplied = {kw.arg for kw in node.keywords if kw.arg}
        name = next(
            (
                kw.value.value
                for kw in node.keywords
                if kw.arg == "name" and isinstance(kw.value, ast.Constant)
            ),
            None,
        )
        if name in APPENDED_SPECS:
            found.append((name, node.lineno, frozenset({"contract", "produces"}) & supplied))
    return sorted(found, key=lambda item: item[1])


# ---------------------------------------------------------------------------
# 判据二：动态——装配产物里的字段
# ---------------------------------------------------------------------------


def assembled_spec_fields() -> dict[str, dict[str, object]]:
    """真跑一次 ``build_episode_registry``，返回受钉 spec 的字段现值。

    题面沿用 ``scripts/audit_tool_reachability.py`` 的探针：``valuation_estimate``
    是唯一不去读 market DB 取 as-of 的题型，审计要回答装配问题不是数据问题。
    传 ``memory_user`` 是因为 ``memory_lookup`` 缺身份就不注册。
    """

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from intelligence.services.episode_factory import build_episode_context
    from intelligence.services.episode_tools import build_episode_registry
    from intelligence.services.research_tool_registry import _DEFAULT_TOOL_METADATA
    from intelligence.services.task_frame import TaskFrame

    frame = TaskFrame(
        raw_question="工具目录收口闸门探针",
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
    context = build_episode_context(
        frame,
        task_id="tool-admission-gate",
        capabilities=tuple(sorted(_DEFAULT_TOOL_METADATA)),
        timeout=30.0,
    )
    registry = build_episode_registry(frame, context, memory_user="__audit_probe__")
    return {
        spec.name: {
            "contract": spec.contract,
            "produces": frozenset(spec.produces),
        }
        for spec in registry.authorized_specs()
        if spec.name in APPENDED_SPECS
    }


# ---------------------------------------------------------------------------
# 变异测试
# ---------------------------------------------------------------------------

_STATIC_CASES: tuple[tuple[str, str, int], ...] = (
    (
        "A 收口完成",
        "def build_episode_registry(frame, context):\n"
        "    specs = assemble_episode_specs(deps, context.contract.allowed_capabilities)\n",
        0,
    ),
    (
        "B l3_lookup 单行 if（正则因数字漏掉）",
        "def build_episode_registry(frame, context):\n"
        '    if "l3_lookup" in context.contract.allowed_capabilities:\n'
        "        pass\n",
        1,
    ),
    (
        "C memory_lookup 多行 if（正则因换行漏掉）",
        "def build_episode_registry(frame, context):\n"
        "    if (\n"
        '        "memory_lookup" in context.contract.allowed_capabilities\n'
        "        and identity\n"
        "    ):\n"
        "        pass\n",
        1,
    ),
    (
        "D ⭐ 原样搬进 assemble_episode_specs（上一版在此发假绿）",
        "def assemble_episode_specs(deps, allowed):\n"
        '    if "market_data" in deps.contract.allowed_capabilities:\n'
        "        pass\n"
        '    if "l3_lookup" in deps.contract.allowed_capabilities:\n'
        "        pass\n"
        "def build_episode_registry(frame, context):\n"
        "    return ResearchToolRegistry(assemble_episode_specs(deps, allowed))\n",
        2,
    ),
    (
        "E ⭐ 搬进 catalog.py 的模块级代码",
        '"""catalog"""\n'
        "CATALOG = []\n"
        'if "kb_search" in context.contract.allowed_capabilities:\n'
        "    CATALOG.append(kb_search_builder)\n",
        1,
    ),
    (
        "F 授权表存进中间变量后再比较",
        "def assemble_episode_specs(deps):\n"
        "    allowed = deps.contract.allowed_capabilities\n"
        '    if "kb_search" in allowed:\n'
        "        pass\n",
        1,
    ),
    (
        "G 别名链式传递两跳",
        "def assemble_episode_specs(deps):\n"
        "    allowed = deps.contract.allowed_capabilities\n"
        "    caps = allowed\n"
        '    if "kb_search" in caps:\n'
        "        pass\n",
        1,
    ),
    (
        "H not in 形式也算一条",
        "def assemble_episode_specs(deps):\n"
        '    if "news_search" not in deps.contract.allowed_capabilities:\n'
        "        return None\n",
        1,
    ),
    (
        "I 预取白名单函数放行",
        "def _should_attach_overnight_news(allowed_capabilities):\n"
        '    if "news_search" not in allowed_capabilities:\n'
        "        return False\n",
        0,
    ),
    (
        "J 白名单只赦免那个函数，同模块别处照拦",
        "def _should_attach_overnight_news(allowed_capabilities):\n"
        '    if "news_search" not in allowed_capabilities:\n'
        "        return False\n"
        "def assemble_episode_specs(deps):\n"
        '    if "news_search" in deps.contract.allowed_capabilities:\n'
        "        pass\n",
        1,
    ),
    (
        "K 非能力表的 in 比较不算",
        "def assemble_episode_specs(deps):\n"
        '    if "market_data" in {"market_data", "financial_data"}:\n'
        "        pass\n",
        0,
    ),
    (
        "L 对目录循环、能力名是变量——正是收口想要的形状",
        "def assemble_episode_specs(deps, allowed):\n"
        "    for builder in CATALOG:\n"
        "        if builder.capability in allowed:\n"
        "            yield builder.build(deps)\n",
        0,
    ),
)

#: 判据二的变异用例——直接喂装配产物的形状，不经代码文本。
_PRODUCT_CASES: tuple[tuple[str, dict[str, dict[str, object]], int], ...] = (
    (
        "现状：三个 spec 的 contract/produces 都空",
        {
            name: {"contract": "", "produces": frozenset()}
            for name in APPENDED_SPECS
        },
        0,
    ),
    (
        "⭐ 改走 default_registry，中央表 contract 醒了（扫构造器看不见）",
        {
            "finance_query": {"contract": "结果会按…截断", "produces": frozenset()},
            "evidence_search": {"contract": "", "produces": frozenset()},
            "memory_lookup": {"contract": "", "produces": frozenset()},
        },
        1,
    ),
    (
        "⭐ produces 醒了，会改 satisfiability 判读",
        {
            "finance_query": {"contract": "", "produces": frozenset({"data_date"})},
            "evidence_search": {"contract": "", "produces": frozenset()},
            "memory_lookup": {"contract": "", "produces": frozenset()},
        },
        1,
    ),
    (
        "两样一起醒，算两条",
        {
            "finance_query": {"contract": "x", "produces": frozenset()},
            "evidence_search": {"contract": "", "produces": frozenset()},
            "memory_lookup": {"contract": "", "produces": frozenset({"prime_memory"})},
        },
        2,
    ),
    (
        "spec 整个消失也要报（装配没接上，不是「没醒就好」）",
        {"finance_query": {"contract": "", "produces": frozenset()}},
        2,
    ),
)


def _product_violations(fields: dict[str, dict[str, object]]) -> list[str]:
    problems: list[str] = []
    for name in APPENDED_SPECS:
        got = fields.get(name)
        if got is None:
            problems.append(f"{name}: 装配产物里根本没有这个 spec")
            continue
        if got["contract"]:
            problems.append(f"{name}: contract 非空（{str(got['contract'])[:40]}…）")
        if got["produces"]:
            problems.append(f"{name}: produces 非空（{sorted(got['produces'])}）")
    return problems


def self_test() -> int:
    """没被证伪过的门禁就是假门禁。⭐ 标的是上一版会发假绿的用例。"""

    failures = 0
    print("变异测试 — 把闸门放到「重构没做完」的代码/产物上，看它拦不拦\n")
    print("判据一（静态）：装配模块里不许按工具名写死")
    for label, src, expected in _STATIC_CASES:
        got = len([h for h in scan(src) if not h.whitelisted])
        ok = got == expected
        failures += not ok
        print(
            f"  {'✓' if ok else '✗'} {label:46s} -> "
            f"{'放行' if got == 0 else f'拦下 {got} 条'}（期望 {expected}）"
        )

    print("\n判据二（装配产物）：搬家不许唤醒中央表文案")
    for label, fields, expected in _PRODUCT_CASES:
        got = len(_product_violations(fields))
        ok = got == expected
        failures += not ok
        print(
            f"  {'✓' if ok else '✗'} {label:46s} -> "
            f"{'放行' if got == 0 else f'拦下 {got} 条'}（期望 {expected}）"
        )

    total = len(_STATIC_CASES) + len(_PRODUCT_CASES)
    print(f"\n共 {total} 条变异用例，{total - failures} 条符合预期。")
    print(
        "已知盲区：能力名不是字面量时（``if builder.capability in allowed``）本闸门\n"
        "不拦——那已经是「对目录循环」而不是「按工具名写死」，正是收口想要的形状（用例 L）。"
    )
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def _resolve_sources(rev: str | None, repo: Path) -> tuple[dict[str, str], str]:
    if rev is None:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        sources: dict[str, str] = {}
        for pattern in ASSEMBLY_GLOBS:
            for path in sorted(repo.glob(pattern)):
                sources[str(path.relative_to(repo))] = path.read_text(encoding="utf-8")
        dirty = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", *sources],
            capture_output=True,
            text=True,
        ).stdout.strip()
        return sources, f"工作树 (HEAD {head}{'，装配文件有未提交改动' if dirty else ''})"

    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", rev],
        capture_output=True,
        text=True,
    )
    if listing.returncode != 0:
        raise SystemExit(f"读不到 revision {rev} — {listing.stderr.strip()}")
    import fnmatch

    sources = {}
    for name in listing.stdout.splitlines():
        if any(fnmatch.fnmatch(name, pattern) for pattern in ASSEMBLY_GLOBS):
            sources[name] = subprocess.run(
                ["git", "-C", str(repo), "show", f"{rev}:{name}"],
                capture_output=True,
                text=True,
            ).stdout
    resolved = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", rev],
        capture_output=True,
        text=True,
    ).stdout.strip()
    return sources, f"{rev} ({resolved})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rev", default=None, help="对某个 git revision 断言（静态判据）")
    parser.add_argument("--repo", default=REPO_ROOT, type=Path)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--static-only",
        action="store_true",
        help="只跑判据一。判据二会被记为「未执行」，不得当成通过",
    )
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    # 判据二靠 import 跑真实装配，读到的永远是工作树——对历史 revision 断言时
    # 它测的不是那个 revision。让退出码自称「对 gitea/main 成立」而实际混了工作树
    # 的读数，就是自己造一份跨层口径不一致。所以 --rev 强制降为静态。
    static_only = args.static_only or args.rev is not None
    if args.rev is not None and not args.static_only:
        print(f"ⓘ --rev {args.rev}：判据二靠 import 读工作树，对历史 revision 不成立，已自动降为 --static-only\n")

    sources, label = _resolve_sources(args.rev, args.repo)
    if not sources:
        print(f"❌ {label}：装配模块一个都没匹配到 {ASSEMBLY_GLOBS} — fail closed")
        return 2

    print(f"目标 revision：{label}")
    print(f"装配模块（{len(sources)} 个）：{', '.join(sources)}")
    print(f"射程外：{OUT_OF_SCOPE_NOTE}")
    print("预取白名单（按函数名赦免，加白必须写理由）：")
    for func, why in PREFETCH_WHITELIST.items():
        seen = any(
            hit.function == func for src in sources.values() for hit in scan(src)
        )
        print(f"  - {func}() — {why}{'' if seen else '  ⚠ 本 revision 未命中，可能已失效'}")
    print()

    # ---- 判据一 ----
    hits = [
        hit
        for name, src in sources.items()
        for hit in scan(src, module=name)
    ]
    blocking = [hit for hit in hits if not hit.whitelisted]
    exempt = [hit for hit in hits if hit.whitelisted]

    print("判据一：装配模块里按工具名写死的分支 = 0")
    if blocking:
        print(f"🔴 仍有 {len(blocking)} 条：")
        for hit in blocking:
            op = "not in" if hit.negated else "in"
            print(
                f"   {hit.module}:{hit.line:<6} {hit.capability:<18} ({op})"
                f"  in {hit.function}()"
            )
    else:
        print("🟢 已收口：0 条")
    if exempt:
        print(f"   （白名单赦免 {len(exempt)} 条：" + ", ".join(
            f"{h.module}:{h.line} {h.capability}" for h in exempt) + "）")

    # ---- 判据二 ----
    print("\n判据二：装配产物里三个 spec 的 contract / produces 仍为空")
    aux = [item for item in (
        scan_spec_constructors(src) for src in sources.values()
    ) for item in item if item[2]]

    if static_only:
        print("⚠️ --static-only：判据二未执行。**未执行 ≠ 通过**，合并闸不得用这个模式。")
        product_failed = None
    else:
        try:
            fields = assembled_spec_fields()
        except Exception as exc:  # noqa: BLE001 — 判据跑不动就 fail closed
            print(f"❌ 装配探针跑不起来，判据二无法执行 — fail closed\n   {type(exc).__name__}: {exc}")
            print("   多半是解释器不对：用 .venv-workbench/bin/python 跑。")
            return 2
        problems = _product_violations(fields)
        product_failed = bool(problems)
        if problems:
            print(f"🔴 {len(problems)} 处偏离——这是行为变更，不是搬家：")
            for problem in problems:
                print(f"   {problem}")
            print(
                "   contract 直接进模型提示词，produces 会改 check_satisfiability 判读。\n"
                "   要接上就单独立一单带 A/B，别夹在收口里。"
            )
        else:
            print("🟢 三个 spec 装配出来仍是空 contract / 空 produces，与收口前一致")

    if aux:
        print("   辅助信号（字面量 ToolSpec 构造器新设了字段）：" + ", ".join(
            f"{n}@L{ln} {sorted(f)}" for n, ln, f in aux))

    # 退码优先级：判据一红先于「判据二没跑」。页脚必须打印**真实** verdict——
    # 上一版无条件写「按 fail closed 退 2」，而判据一红时实际退 1，
    # 是一份自己说谎的收据。收据说谎比没有收据更贵。
    if blocking:
        verdict, why = 1, f"判据一未收口（{len(blocking)} 条）"
        if product_failed is None:
            why += "；判据二未执行"
    elif product_failed:
        verdict, why = 1, "判据二偏离（中央表文案被唤醒）"
    elif product_failed is None:
        verdict, why = 2, "判据一已绿，但判据二未执行——未执行 ≠ 通过"
    else:
        verdict, why = 0, "两条判据都过"

    print(f"\n退出码 {verdict}：{why}。本次读数对 {label} 成立。")
    return verdict


if __name__ == "__main__":
    sys.exit(main())
