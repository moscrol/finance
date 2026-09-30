#!/usr/bin/env python3
"""正则路由棘轮：路由 / 题型判定模块里的正则规则只减不增。

## 为什么（2026-09-30 质检 P1「冻结新增正则路由」）

题型路由靠字面正则：``query_understanding`` 61 条、``user_task`` 55 条，路由相关模块
合计 243 处（2026-09-30 基线，含内联 ``re.search`` 等）。正则按字面匹配，换个说法就漏——四臂对照里 8792 恰恰输在「没见过的
改写题」（unseen react 0.857 vs 8792 0.567）；``route_table.py`` 头部也自记了一次
字面规则误判（821 字材料题被判成 disclosure_scan，静默返回 183 字节存根）。
每修一次漏判就再加一条正则，是这类代码膨胀的主要方式。

本脚本不评价已有规则，只拦**新增**：要加规则就得在同一个提交里显式
``--update-baseline``，让「又加了一条正则路由」在评审里看得见。
改成模型路由为主、正则兜底之前，先用同义改写题量一次路由准确率（质检报告 §2）。

## 口径

- 范围：``intelligence/`` 下非测试 ``.py``，路径命中路由关键词（``ROUTING_PATH``）。
  新建的路由模块从 0 起算，第一条正则就算新增。
- 计数：AST 里对 ``re`` 模块的调用点（compile / search / match / fullmatch / findall /
  finditer / sub / subn / split）。注释和字符串里的字样不算；已编译对象的
  ``_X_RE.search(...)`` 不算（规则在定义处已计过）。
- 沿用 ``check_path_literals.py`` 的棘轮模式：基线 ``regex-routes-baseline.json``
  由本脚本生成，不手抄；减少时提示 ``--update-baseline`` 把改进锁进基线。

退出码：0 无新增（或已写入基线）；1 有新增；2 基线损坏。只用标准库。
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO / "regex-routes-baseline.json"
SCAN_ROOT = "intelligence"
ROUTING_PATH = re.compile(
    r"route|routing|router|query_understanding|user_task|intent|turn_controller|"
    r"task_frame|question_type|classif|dispatch"
)
RE_FUNCS = frozenset(
    {"compile", "search", "match", "fullmatch", "findall", "finditer", "sub", "subn", "split"}
)


def _is_test(rel: str) -> bool:
    parts = rel.split("/")
    return "tests" in parts or parts[-1].startswith("test_")


def count_regex_calls(source: str) -> int:
    """``re.<fn>(...)`` 调用点个数；也认 ``import re as X`` 的别名。"""

    tree = ast.parse(source)
    aliases = {"re"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "re":
                    aliases.add(alias.asname or "re")
    total = 0
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in RE_FUNCS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in aliases
        ):
            total += 1
    return total


def scan(repo: Path = REPO) -> dict[str, int]:
    current: dict[str, int] = {}
    for path in sorted((repo / SCAN_ROOT).rglob("*.py")):
        rel = path.relative_to(repo).as_posix()
        if _is_test(rel) or not ROUTING_PATH.search(rel):
            continue
        count = count_regex_calls(path.read_text(encoding="utf-8"))
        if count:
            current[rel] = count
    return current


def load_baseline(path: Path = BASELINE_PATH) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    files = data.get("files")
    if not isinstance(files, dict) or not all(
        isinstance(k, str) and isinstance(v, int) and v >= 0 for k, v in files.items()
    ):
        raise ValueError("基线格式不对：需要 {\"files\": {路径: 非负整数}}")
    return files


def write_baseline(current: dict[str, int], path: Path = BASELINE_PATH) -> None:
    payload = {
        "_comment": "scripts/check_regex_routes.py 生成，勿手改；只减不增。",
        "total": sum(current.values()),
        "files": dict(sorted(current.items())),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compare(current: dict[str, int], baseline: dict[str, int]) -> tuple[dict, dict]:
    grown = {
        rel: (baseline.get(rel, 0), count)
        for rel, count in current.items()
        if count > baseline.get(rel, 0)
    }
    shrunk = {
        rel: (count, current.get(rel, 0))
        for rel, count in baseline.items()
        if current.get(rel, 0) < count
    }
    return grown, shrunk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="正则路由棘轮：只减不增")
    parser.add_argument("--update-baseline", action="store_true", help="把当前计数写成新基线")
    args = parser.parse_args(argv)

    current = scan(REPO)
    if args.update_baseline:
        write_baseline(current, BASELINE_PATH)
        print(f"✅ 已写入基线：{len(current)} 个文件 / {sum(current.values())} 处")
        return 0
    try:
        baseline = load_baseline(BASELINE_PATH)
    except (OSError, ValueError) as exc:
        print(f"❌ 基线读不了：{exc}", file=sys.stderr)
        return 2

    grown, shrunk = compare(current, baseline)
    print(f"  基线    {len(baseline)} 文件 / {sum(baseline.values())} 处")
    print(f"  当前    {len(current)} 文件 / {sum(current.values())} 处")
    if grown:
        print("\n❌ 路由模块新增了正则规则：")
        for rel, (before, after) in sorted(grown.items()):
            print(f"    {rel}: {before} → {after}")
        print(
            "\n改写题会绕过字面规则，每加一条都是在给弱路由打补丁。确实要加：\n"
            "  python3 scripts/check_regex_routes.py --update-baseline\n"
            "并在提交说明里写清为什么不能用已有规则或模型路由解决。"
        )
        return 1
    if shrunk:
        print(f"\n✅ 无新增；另有 {len(shrunk)} 个文件减少了，跑 --update-baseline 把改进锁进基线")
    else:
        print("\n✅ 无新增正则路由")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
