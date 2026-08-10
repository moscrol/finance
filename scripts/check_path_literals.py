#!/usr/bin/env python3
"""门禁：不得**新增**写死的家目录路径。

## 判据为什么不能是「测试目录一律放过」

全仓 64 处家目录字面量里，测试目录占 30 处，但它们不是同一种东西：

    # 故意的脱敏夹具——喂一个像家目录的串进去，断言输出里不含它
    assert "/Users/a77" not in encoded                      # test_runtime_backend_benchmark:241
    "reason_code": "provider said: /Users/a77/secret"        # test_synthesis_phase_observability

    # 真实路径依赖——断言夹具构造器真的用了这个解释器
    "/Users/a77/finance-workspace-private/.venv-workbench/bin/python"   # test_ceiling_pit_fixture

前者**必须保留**：换成 ``Path.home()`` 会让测试变成「检查一个不存在的东西有没有
泄漏」——永远通过，什么都没测，看起来更干净实际把安全网剪断了。
后者是真依赖，换机器就失效。

两者同在测试目录里，所以按目录判必错。按「像不像脱敏」判也不行——那是语义判断，
写成正则一定既漏又误伤。

## 所以判据是「有没有新增」，不是「是不是合理」

沿用本仓 ``layer_audit.py`` 已验证的棘轮模式（``ERROR_BASELINE`` 只减不增）：
已存在的一律免检，**新增的一律拦**。门禁不需要理解语义，只需要认出「这是新的」。

存量清单由本脚本从源码生成到 ``path-literals-baseline.json``，不手抄——手抄的
清单会与源码分叉，且分叉时门禁照旧发绿（本仓当天在依赖清单上刚栽过一次）。

## 存量比对「文件 + 具体字面量」，不比个数

若只记每文件的**个数**，在同一文件里删掉一处真依赖、又加一处新的，总数不变即通过。
这与 ``baseline_diff.py`` 的失败归属、以及读数收据存 ``failed_ids`` 而非 counts
是同一条教训：**按名字比，不按个数比**。

比字面量而不比行号：行号会随无关编辑漂移，那会让门禁天天发红。

## 确实需要新增时：在站点写明理由

    KB = Path("/Users/a77/kb")  # path-literal-ok: 单机固定挂载点，无同级仓可推导

标记必须带冒号和理由。理由写在**站点**而不是某个远处的白名单里——白名单会漂，
而且读代码的人看不到。这与「结论必须携带它成立的条件」是同一个原则。

## 覆盖面限于 .py

shell / markdown 里的家目录多是示例与文档，且不参与运行时解析。这是刻意的范围
限制，不是遗漏——扩到 .sh 需要另一套「哪些是示例」的判据。

退出码：
  0  无新增（或 --update-baseline 已写入）
  1  有新增未登记的家目录字面量
  2  用不了：仓库结构不对
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO / "path-literals-baseline.json"

# 不扫的目录：虚拟环境、git 内部、历史 clone、各类缓存。
# ``tmp/`` 下有 4 个历史工作 clone（pytest.ini 也为此设了 norecursedirs）。
SKIP_PARTS = frozenset(
    {
        ".venv-workbench",
        ".git",
        "tmp",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "work",
    }
)

# 家目录字面量：/Users/<名> 或 /home/<名>。不写死具体用户名——门禁本身若写死
# a77，换个开发者就静默失效。
#
# 用户名段必须以字母数字开头（`[A-Za-z0-9_]`），且**至少一个字符**。初版用了 `*`
# 允许空段，于是抓出两类假阳性，都在首次生成基线时暴露：
#
#   1. 别人的**正则源码**被当成路径：
#      normalize_harness_trace.py:74  r"(?:/Users/|/home/|/tmp/|[A-Za-z]:[\\/])"
#      从中抓出 `/Users/|/home/|[A-Za-z` —— 那是字符类，不是路径。
#   2. **裸前缀**被当成路径：
#      test_acceptance_trace_capture.py:106  assert "/Users/" not in serialized
#      那是脱敏断言本身，正是我们要保护的东西。
#
# 两类假阳性混进基线的后果比漏报更糟：基线是「存量免检」的依据，掺了假条目就等于
# 给真实硬编码留了后门（同文件里新增一处真路径，可能因前缀匹配被误判为已知）。
_LITERAL = re.compile(r"/(?:Users|home)/[A-Za-z0-9_][^\s\"'`)\]},;:|]*")

# 站点豁免标记。必须带冒号+理由：只写 ok 等于没解释，日后无人知道为何豁免。
_ALLOW = re.compile(r"#\s*path-literal-ok\s*:\s*\S")


def _iter_py() -> list[Path]:
    out: list[Path] = []
    for path in REPO.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.relative_to(REPO).parts):
            continue
        out.append(path)
    return sorted(out)


def _scan() -> dict[str, list[str]]:
    """返回 相对路径 → 该文件里出现的**去重后**家目录字面量（排序）。"""

    found: dict[str, set[str]] = {}
    for path in _iter_py():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(REPO))
        for line in text.splitlines():
            if _ALLOW.search(line):
                continue
            for hit in _LITERAL.findall(line):
                found.setdefault(rel, set()).add(hit)
    return {k: sorted(v) for k, v in sorted(found.items())}


def _load_baseline() -> dict[str, list[str]]:
    try:
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = data.get("entries")
    return entries if isinstance(entries, dict) else {}


def _write_baseline(current: dict[str, list[str]]) -> None:
    total = sum(len(v) for v in current.values())
    payload = {
        "_why": "存量家目录字面量清单。由 scripts/check_path_literals.py 生成，勿手改。",
        "_rule": "只减不增。新增需在站点写 `# path-literal-ok: 理由`，或删掉硬编码。",
        "_regen": ".venv-workbench/bin/python scripts/check_path_literals.py --update-baseline",
        "_note": "比对「文件+具体字面量」而非个数：同文件删一处加一处，个数不变但应被拦。",
        "files": len(current),
        "literals": total,
        "entries": current,
    }
    BASELINE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument(
        "--update-baseline",
        action="store_true",
        help="把当前状态写成新基线（棘轮下调时用；新增硬编码时不该用）",
    )
    args = ap.parse_args()

    if not (REPO / ".git").exists():
        print(f"用不了：{REPO} 不是 git 仓库", file=sys.stderr)
        return 2

    current = _scan()
    baseline = _load_baseline()

    added: list[tuple[str, str]] = []
    for rel, literals in current.items():
        known = set(baseline.get(rel, ()))
        added.extend((rel, lit) for lit in literals if lit not in known)

    removed: list[tuple[str, str]] = []
    for rel, literals in baseline.items():
        now = set(current.get(rel, ()))
        removed.extend((rel, lit) for lit in literals if lit not in now)

    print("=" * 72)
    print("路径字面量门禁 — 不得新增写死的家目录（存量免检）")
    print("=" * 72)
    print(f"  树        {REPO}")
    print(f"  扫描      {len(_iter_py())} 个 .py（不含 .venv/tmp/缓存）")
    print(
        f"  存量基线  {len(baseline)} 文件 / "
        f"{sum(len(v) for v in baseline.values())} 处"
    )
    print(
        f"  当前      {len(current)} 文件 / "
        f"{sum(len(v) for v in current.values())} 处\n"
    )

    if args.update_baseline:
        _write_baseline(current)
        print(f"✅ 基线已写入 {BASELINE_PATH.name}")
        if added:
            print(f"   其中新纳入 {len(added)} 处——确认它们都是有意保留的：")
            for rel, lit in added:
                print(f"     + {rel}  {lit}")
        return 0

    if removed:
        print(f"  ↓ 已清理 {len(removed)} 处（棘轮下调，跑 --update-baseline 固化）：")
        for rel, lit in removed[:10]:
            print(f"      - {rel}  {lit}")
        if len(removed) > 10:
            print(f"      …另 {len(removed) - 10} 处")
        print()

    if not added:
        print("✅ 无新增家目录字面量")
        return 0

    print(f"❌ 新增 {len(added)} 处写死的家目录：")
    for rel, lit in added:
        print(f"      + {rel}")
        print(f"        {lit}")
    print(
        "\n三条出路，按优先级：\n"
        "  1. 从位置推导——仓根 Path(__file__).resolve().parents[N]；\n"
        "     主检出树问 git（rev-parse --git-common-dir 的父目录）；\n"
        "     仓外运行时目录用 Path.home()。\n"
        "  2. 走 intelligence/paths.py（env 变量优先，已是路径真本源）。\n"
        "  3. 确实必须写死（例如脱敏测试要一个像家目录的输入）：\n"
        "     在该行加  # path-literal-ok: <理由>\n"
        "     理由写在站点，不要写进远处的白名单——白名单会漂，读代码的人也看不到。"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
