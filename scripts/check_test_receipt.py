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


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


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
        "dirty": bool(_git("status", "--porcelain")),
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
        print("  ✗ 收据来自干净树")
        print("      收据自述 dirty=true —— 未提交改动无法被 revision 描述，")
        print("      别人无从复现同一份代码。这类收据只对「本机此刻」有效。")
        blockers.append("收据来自脏树")
    else:
        print("  ✓ 收据来自干净树")

    if receipt.get("dependency_gate_bypassed"):
        print("  ✗ 依赖门禁未被绕过")
        print("      收据自述 FWP_ALLOW_ANY_PYTHON=1 —— 读数不可跨环境比较。")
        blockers.append("依赖门禁曾被绕过")
    else:
        print("  ✓ 依赖门禁未被绕过")

    if here["dirty"]:
        # 当前树脏不影响「这份收据是否成立」，但影响「你能不能拿它代表你手上的代码��。
        print("\n  ⚠ 你当前的树有未提交改动：即使上面全部一致，收据描述的是")
        print("    已提交的那份代码，不含你手上的改动。")

    if args.require_target:
        target = receipt.get("target") or ""
        if args.require_target not in target:
            print(f"\n  ✗ 覆盖面不含 {args.require_target}（收据目标：{target or '(全量)'}）")
            blockers.append("覆盖面不足")

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
