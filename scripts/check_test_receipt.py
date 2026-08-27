#!/usr/bin/env python3
"""判定一份读数收据能不能采信——**不重跑测试**就给出结论。

## 要解决的浪费

多 agent 协作里反复出现：上一个 agent 报「3943 passed」，下一个不采信、重跑一遍。
这不是不礼貌，是**理性反应**——那个数字没说明它在哪个解释器、哪棵树、哪个 revision
上得出，因此不可复核。而 2026-08-10 的实测证明这种怀疑必要：同一棵树同一时刻，
宿主 python3 得 71 failed，.venv-workbench 得 14 failed，差 57 条全是环境噪声。

所以方向不是「让 agent 互相信任」（做不到，也不该做），而是**把验证成本降到几秒**：
结论携带它成立的条件，下一个 agent 比对条件即可决定采信还是重跑。业界叫
provenance（来源溯源）。

## 判定规则：任何一条不符就该重跑，并说明**为什么**

    revision 不同        → 代码不同，读数无关
    dirty=true           → 未提交改动无法被 revision 描述，别人无从复现同一份代码。
                           这类收据只对「本机此刻」有效，跨 agent 一律不可采信。
    解释器不同           → 就是那个 71 vs 14 的病因
    依赖指纹不同         → 装的包变了，读数不可比
    绕过依赖门禁         → 收据自述 FWP_ALLOW_ANY_PYTHON=1，读数不可跨环境比较

**「重跑」不是失败**，是"这份收据不适用于你的处境"。所以退出码 1 的含义是
"需要重跑"，不是"测试坏了"——两者混淆会让调用方在 CI 里把它当成红灯。

## 为什么比 revision 而不是比时间

新不代表适用。半小时前在**同一 revision 同一环境**下的收据，比五分钟前在另一个
分支上的收据有用得多。时间只作为展示信息，不参与判定。

退出码：
  0  可采信 —— 收据成立的条件与当前环境一致
  1  需重跑 —— 至少一条条件不符（逐条说明）
  2  用不了 —— 没有收据 / 收据损坏
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import json
import platform
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECEIPT_DIR = Path.home() / ".finance-runtime" / "test-receipts"
_SPEC_PATH = REPO / "test-environment.json"
_LOCK = REPO / "requirements-consumer.lock"


def _spec() -> dict:
    try:
        return json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_SPEC = _spec()


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _git_status_lines() -> list[str]:
    """porcelain 行，**整体不 strip**——与 ``conftest.py`` 同一个理由。

    ``_git`` 的 ``.strip()`` 会吃掉首行 ``" M path"`` 的前导空格，随后
    ``line[3:]`` 多切一个字符，该路径被静默丢弃。写方（conftest）和检方（本文件）
    是同一份逻辑的两个拷贝，所以这个洞两边都有：写方会把收据记成干净树，
    检方也不会在「你当前的树有未提交的代码改动」里列出那个文件。
    """

    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    return [line for line in out.stdout.splitlines() if line.strip()]


# 与 conftest.py 共读 test-environment.json 的同两个字段，不各写一份。
_CODE_PREFIXES = tuple(_SPEC.get("code_path_prefixes") or ())
_DATA_EXCEPTIONS = tuple(_SPEC.get("data_path_exceptions") or ())


def _code_dirt() -> list[str]:
    """未提交改动里**能影响被测行为**的那些路径。

    与 ``conftest.py`` 的 ``_code_dirt`` 同判据。为什么不按全树 ``git status``：
    本仓工作区长期有 45 个脏文件（复盘台账、exports、复盘/ 下 HTML 产物等），
    都是每日 ingest 的正常产物。按全树判则每份收据都 dirty、本校验器永远建议
    重跑——永远发红的门禁比没有门禁更糟，它训练人忽略它。
    """

    out: list[str] = []
    for line in _git_status_lines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not path.startswith(_CODE_PREFIXES):
            continue
        if path.startswith(_DATA_EXCEPTIONS):
            continue
        out.append(path)
    return sorted(out)


def _fingerprint() -> str:
    """必须与 conftest.py 的 ``_dependency_fingerprint`` **逐字节同算法**。

    两处各写一份算法就会漂——本仓当天已经在依赖清单上栽过一次（conftest 与
    check_agent_workspace_facts 各存一份，uvicorn/ruff 只在其中一处）。这里两边
    都从同一份锁文件 + test-environment.json 推导，输入相同故输出相同；任何一边
    改算法都会让所有收据判为「需重跑」——**朝安全方向失败**，不会误判为可采信。
    """

    try:
        spec = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        spec = {}
    names = tuple(spec.get("required_modules") or ())
    if _LOCK.is_file():
        pinned = [
            line.split("==")[0].strip()
            for line in _LOCK.read_text(encoding="utf-8").splitlines()
            if "==" in line and not line.startswith("#")
        ]
        names = tuple(sorted({*names, *pinned}))
    parts = []
    for name in names:
        try:
            parts.append(f"{name}=={md.version(name)}")
        except md.PackageNotFoundError:
            parts.append(f"{name}==<缺失>")
    return hashlib.sha256(";".join(parts).encode("utf-8")).hexdigest()[:16]


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"用不了：收据读不了 {path}（{exc}）", file=sys.stderr)
        raise SystemExit(2) from exc


def _rev_parse(ref: str) -> str:
    """展开成全 SHA；解析不了返回原串（供字符串全等 fallback）。"""
    resolved = _git("rev-parse", "--verify", f"{ref}^{{commit}}")
    return resolved or ref


def check_expected_revision(receipt_rev: str, expect: str) -> tuple[bool, str]:
    """收据 revision 必须与期望 SHA **全等**（rev-parse 展开后比较）。

    为什么不许 startswith：前缀比较是口径的削弱面——比到前 4 位时任何
    同前缀提交都能冒充；工单 §P1-a 的变异测试就打这条。差额（收据落后
    期望几张合并）打进错误正文，让读者知道这份收据旧了多少。
    """

    theirs = _rev_parse(receipt_rev)
    want = _rev_parse(expect)
    if theirs == want:
        return True, f"收据 revision == {want[:12]}"
    lag = _git("rev-list", "--count", "--merges", f"{theirs}..{want}")
    lag_note = f"，落后期望 {lag} 张合并" if lag and lag != "0" else ""
    return False, (
        f"收据 revision {theirs[:12]} ≠ 期望 {want[:12]}{lag_note}——"
        "这份收据证明的是另一棵树"
    )


def check_base_drift(
    receipt_rev: str, main_ref: str, *, max_merges: int
) -> tuple[bool, str]:
    """收据 revision 的合并基座落后主干超过 N 张合并 → 拒绝。

    治的形状（#444 实测）：分支尖收据是真的，但基座落后 main 27 张 PR，
    「分支绿」不能代表「合流绿」。认不出引用就 fail-closed，不降级放行。
    """

    main_sha = _git("rev-parse", "--verify", f"{main_ref}^{{commit}}")
    if not main_sha:
        return False, f"主干引用 {main_ref} 解析不了——fail closed，先 fetch 再验"
    receipt_sha = _rev_parse(receipt_rev)
    base = _git("merge-base", receipt_sha, main_sha)
    if not base:
        return False, (
            f"算不出 {receipt_sha[:12]} 与 {main_ref} 的合并基座——fail closed"
        )
    drift = _git("rev-list", "--count", "--merges", f"{base}..{main_sha}")
    if not drift:
        return False, "基座漂移数取不到——fail closed"
    if int(drift) > max_merges:
        return False, (
            f"收据基座落后 {main_ref} 共 {drift} 张合并（上限 {max_merges}）——"
            "分支尖收据不得冒充批次门禁，rebase 后重跑"
        )
    return True, f"基座漂移 {drift} ≤ {max_merges}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument(
        "receipt",
        nargs="?",
        default=str(RECEIPT_DIR / "latest.json"),
        help=f"收据路径，默认 {RECEIPT_DIR / 'latest.json'}",
    )
    ap.add_argument(
        "--require-target",
        default=None,
        help="要求收据覆盖了这个 pytest 目标（子串匹配）；不给则不检查覆盖面",
    )
    ap.add_argument(
        "--expect-revision",
        default=None,
        metavar="SHA",
        help="收据 revision 必须与此 SHA 全等（rev-parse 展开后比较）；"
        "合并前置用它把「收据树 == 要合的树」从规程文字变成 exit code",
    )
    ap.add_argument(
        "--base-drift-max",
        type=int,
        default=None,
        metavar="N",
        help="收据 revision 的合并基座落后 --main-ref 超过 N 张合并即拒绝"
        "（治「分支尖收据冒充批次门禁」，工单建议 N=5）",
    )
    ap.add_argument(
        "--main-ref",
        default="gitea/main",
        help="--base-drift-max 的主干引用（默认 gitea/main）",
    )
    args = ap.parse_args()

    path = Path(args.receipt).expanduser()
    if not path.is_file():
        print(f"用不了：没有收据 {path}", file=sys.stderr)
        print("        先跑一次测试即会自动生成（conftest.py 的 sessionfinish 钩子）。")
        return 2
    receipt = _load(path)

    here = {
        "revision": _git("rev-parse", "HEAD") or "(unknown)",
        "interpreter": sys.executable,
        "python_version": platform.python_version(),
        "dependency_fingerprint": _fingerprint(),
        # 与收据同判据：只看能影响被测行为的路径，不看全树。
        "dirty": bool(_code_dirt()),
    }

    print("=" * 72)
    print("读数收据校验 — 判「能不能采信」，不重跑测试")
    print("=" * 72)
    print(f"  收据     {path}")
    print(f"  产生于   {receipt.get('finished_at', '?')}")
    print(f"  目标     {receipt.get('target') or '(全量)'}")
    counts = receipt.get("counts") or {}
    print(
        f"  读数     passed={counts.get('passed', '?')} "
        f"failed={counts.get('failed', '?')} error={counts.get('error', '?')} "
        f"skipped={counts.get('skipped', '?')}\n"
    )

    blockers: list[str] = []

    def compare(field: str, label: str) -> None:
        theirs, mine = receipt.get(field), here[field]
        same = theirs == mine
        mark = "✓" if same else "✗"
        print(f"  {mark} {label}")
        if not same:
            print(f"      收据 : {theirs}")
            print(f"      当前 : {mine}")
            blockers.append(label)

    compare("revision", "revision 一致")
    compare("interpreter", "解释器一致")
    compare("python_version", "python 版本一致")
    compare("dependency_fingerprint", "依赖指纹一致")

    if receipt.get("dirty"):
        print("  ✗ 收据来自干净树（按代码路径判，非全树）")
        print("      收据自述 dirty=true —— 未提交改动无法被 revision 描述，")
        print("      别人无从复现同一份代码。这类收据只对「本机此刻」有效。")
        for item in (receipt.get("dirty_paths") or [])[:8]:
            print(f"        脏: {item}")
        blockers.append("收据来自脏树")
    else:
        total = receipt.get("worktree_dirty_total")
        note = ""
        if isinstance(total, int) and total:
            # 说清「全树脏但代码干净」，否则读者会以为判据漏了东西。
            note = f"（全树另有 {total} 个脏文件，均为 ingest 数据产物，不影响被测行为）"
        print(f"  ✓ 收据来自干净树{note}")

    if receipt.get("dependency_gate_bypassed"):
        print("  ✗ 依赖门禁未被绕过")
        print("      收据自述 FWP_ALLOW_ANY_PYTHON=1 —— 读数不可跨环境比较。")
        blockers.append("依赖门禁曾被绕过")
    else:
        print("  ✓ 依赖门禁未被绕过")

    if here["dirty"]:
        # 当前树脏不影响「这份收据是否成立」，但影响「你能不能拿它代表你手上的代码��。
        print("\n  ⚠ 你当前的树有未提交的**代码**改动：即使上面全部一致，")
        print("    收据描述的是已提交的那份代码，不含你手上的改动。")
        for item in _code_dirt()[:8]:
            print(f"      脏: {item}")

    if args.require_target:
        target = receipt.get("target") or ""
        if args.require_target not in target:
            print(f"\n  ✗ 覆盖面不含 {args.require_target}（收据目标：{target or '(全量)'}）")
            blockers.append("覆盖面不足")

    receipt_rev = str(receipt.get("revision") or "")
    if args.expect_revision:
        ok, message = check_expected_revision(receipt_rev, args.expect_revision)
        print(f"  {'✓' if ok else '✗'} {message}")
        if not ok:
            blockers.append("revision 与期望不符")
    if args.base_drift_max is not None:
        ok, message = check_base_drift(
            receipt_rev, args.main_ref, max_merges=args.base_drift_max
        )
        print(f"  {'✓' if ok else '✗'} {message}")
        if not ok:
            blockers.append("基座漂移超限")

    if not blockers:
        print("\n✅ 可采信 —— 收据成立的条件与当前环境一致，无需重跑。")
        failed = receipt.get("failed_ids") or []
        if failed:
            print(f"   注意收据里有 {len(failed)} 条失败，按名字逐条对待：")
            for item in failed[:10]:
                print(f"     - {item}")
            if len(failed) > 10:
                print(f"     …另 {len(failed) - 10} 条")
        return 0

    print(f"\n🔁 需重跑 —— {len(blockers)} 项条件不符：{'、'.join(blockers)}")
    print("   （「需重跑」不等于「测试坏了」，只是这份收据不适用于你的处境。）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
