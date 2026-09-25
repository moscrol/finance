#!/usr/bin/env python3
"""属性被**写**但全仓从没被**读**过 —— 「契约与交付不符」的可执行版。

## 它防的失败形状

2026-08-12 一天里在七个互不相干的模块各命中一次同一个形状：某处向模型（或向
下游审计）**承诺**了一件事，实际交付另一件，**且模型无法自行诊断**。其中三例
是本脚本能机械抓到的那一种 —— **字段填了，没人读**：

    tel.degraded = True            # kb_rag 如实记了检索降级
    tel.fallback_reason = "..."    # 也记了原因
    tel.recall_desc = "..."        # 还记了实际用了哪几路
    # …而 _kb_search 只读 status，上面三个从没往模型那边传

后果不是「少一条日志」：模型拿到一份看起来正常的关键词命中，不知道语义那一路
根本没跑，于是把「查不到」写成「不存在」。这类缺陷**静默、自洽、且量具同盲**，
可以活很久 —— 那次实际活了 ≤6 天，而 health 与就绪门禁全程发绿。

## 为什么现有门禁抓不到

`layer_audit` 查 import、`check_path_literals` 查字面量、`graph_audit` 查能力
清单 —— 粒度都在模块/文件级。外部工具 `code-review-graph` 实测也只到
Function/Class（且在本仓精度 1/3，误报集中在「函数作为值传递」，而本仓的工具
注册架构恰好整个建立在传函数上）。**字段这一层没有任何工具。**

## 判据与保守取舍

写：`X.attr = ...`（Store 上下文的属性赋值）、dataclass 字段声明。
读：`X.attr`（Load 上下文）、`getattr(_, "attr")`。

**属性名只要作为字符串字面量在任何地方出现过，就当作可能被动态读取，不报。**
本仓大量走 `payload["detail"]` / `to_dict()` / JSON 序列化，字符串就是它们的读法；
不这么保守会淹没在误报里。代价是漏抓 —— 这是刻意的取舍：**一个吵闹的门禁会
被训练成忽略，而漏抓至少不会让人不信任它**（同 `tool_result_budget` 那条纪律）。

## 棘轮

存量从源码生成到 `unread-fields-baseline.json`，**只拦新增**（BUILD 模式 1）。
本仓 dataclass 很多，不少字段本就只写给审计/收据看，全拦没法提交。
基线**从源码生成不手抄** —— 手抄的清单会与源码分叉，而分叉时门禁照旧发绿。

退出码：0 无新增（或已 --update-baseline）／1 有新增／2 用不了。
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO / "unread-fields-baseline.json"

# 只扫产品代码。测试里「写了没读」是常态（构造夹具），扫了全是噪声。
SCAN_DIRS = ("intelligence", "market_feature_store")
SKIP_PARTS = {"tests", "__pycache__", ".venv", "tmp", "node_modules"}

# 这些名字属于协议/框架回调，写了不读是正常的。
ALLOWED = frozenset(
    {
        "__post_init__",
        "__dict__",
        "__class__",
        "maxDiff",
    }
)


def _iter_files() -> list[Path]:
    out: list[Path] = []
    for top in SCAN_DIRS:
        root = REPO / top
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            # 按**仓内相对路径**判，不能拿绝对路径的每一段去比：SKIP_PARTS 说的是
            # 「仓里的这些目录不扫」。用绝对路径时，仓一旦被检出到含 tmp/ 的路径下
            # （worktree 放 /tmp 是常事），整棵树都会被跳过，于是拿 0 个文件去比
            # 非空基线，门禁报「✅ 无新增」并 exit 0——静默假绿，而它是 pre-commit
            # 钩子，等于那次提交完全没被这道门禁看过。
            if SKIP_PARTS & set(path.relative_to(REPO).parts):
                continue
            out.append(path)
    return sorted(out)


def _collect(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    """返回 (写入的属性名, 读取的属性名, 出现过的字符串字面量)。"""

    written: set[str] = set()
    read: set[str] = set()
    literals: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.ctx, ast.Store):
                written.add(node.attr)
            else:
                read.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # 动态读取的载体：payload["detail"]、getattr(x, "degraded")、
            # to_dict() 里的键名。只要名字以字符串出现过就不报。
            literals.add(node.value)
    # dataclass / 类属性声明也算一次「写」：它**承诺**了这个字段存在。
    #
    # ⚠ 只认**类体内**的注解，不认函数里的。初版一律收，于是 `idx: dict = {}`
    # 这类带标注的局部变量全被当成字段，存量从 ~100 涨到 606 条、绝大多数是噪声。
    # **局部变量不是契约**——契约是「对外声明了什么」。
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                written.add(stmt.target.id)
    return written, read, literals


def scan() -> dict[str, list[str]]:
    """全仓扫描：写了但没读的属性，按文件归集。

    读与字符串字面量取**全仓并集**——字段常常在 A 模块写、B 模块读，
    按文件判会把所有跨模块字段都误报成死字段。
    """

    per_file_written: dict[str, set[str]] = {}
    all_read: set[str] = set()
    all_literals: set[str] = set()

    for path in _iter_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        written, read, literals = _collect(tree)
        rel = str(path.relative_to(REPO))
        if written:
            per_file_written[rel] = written
        all_read |= read
        all_literals |= literals

    findings: dict[str, list[str]] = {}
    for rel, written in per_file_written.items():
        unread = sorted(
            name
            for name in written
            if name not in all_read
            and name not in all_literals
            and name not in ALLOWED
            and not name.startswith("__")
        )
        if unread:
            findings[rel] = unread
    return findings


def _load_baseline() -> dict[str, list[str]]:
    if not BASELINE_PATH.is_file():
        return {}
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help="把当前状态写成新基线（清理后棘轮下调时用；新增时不该用）",
    )
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args(argv)

    current = scan()
    baseline = _load_baseline()

    # 扫到 0 个文件却有非空基线 = 这次运行根本没看过代码。必须响亮失败：门禁最坏的
    # 失效不是漏抓，是**空转却发绿**——那会让人以为查过了。放在 --update-baseline
    # 之前，因为空转时写基线会把存量清单直接清空，比误报更难发现。
    if not _iter_files() and baseline:
        print(
            f"用不了：{', '.join(SCAN_DIRS)} 下扫到 0 个 .py，"
            f"而基线有 {sum(len(v) for v in baseline.values())} 个字段。"
            f"\n  这次运行没有看过任何代码，报绿就是假绿。"
            f"\n  REPO={REPO}"
        )
        return 2

    if args.update_baseline:
        BASELINE_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        total = sum(len(v) for v in current.values())
        print(f"基线已写入：{len(current)} 文件 / {total} 个字段")
        return 0

    # 比对「文件 + 具体字段名」，**不比个数**——清理 1 个 + 新增 1 个总数不变。
    added: dict[str, list[str]] = {}
    for rel, names in current.items():
        known = set(baseline.get(rel) or ())
        new = sorted(set(names) - known)
        if new:
            added[rel] = new

    if args.json:
        print(json.dumps({"added": added, "current": current}, ensure_ascii=False))
        return 1 if added else 0

    total_cur = sum(len(v) for v in current.values())
    total_base = sum(len(v) for v in baseline.values())
    print("=" * 64)
    print("字段契约门禁 — 属性写了但全仓没人读（存量免检）")
    print("=" * 64)
    print(f"  扫描      {len(_iter_files())} 个 .py（{', '.join(SCAN_DIRS)}，不含 tests）")
    print(f"  存量基线  {len(baseline)} 文件 / {total_base} 字段")
    print(f"  当前      {len(current)} 文件 / {total_cur} 字段")
    if not added:
        print("\n✅ 无新增「写了没人读」的字段")
        return 0
    print(f"\n❌ 新增 {sum(len(v) for v in added.values())} 个：")
    for rel in sorted(added):
        print(f"  {rel}")
        for name in added[rel]:
            print(f"    · {name}")
    print(
        "\n  这类字段的典型病是「填了但没往下传」——先问：谁该读它？"
        "\n  确属误报（动态读取/对外协议）就加进 ALLOWED 或补一处真实读取点。"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
