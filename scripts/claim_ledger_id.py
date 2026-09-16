#!/usr/bin/env python3
"""预注册号「先占后用」——原子取号，消灭台账撞号的落盘窗口。

## 治的形状（2026-08-27 单日四例撞号，工单
`docs/superpowers/specs/2026-08-28-ledger-id-claim-workorder.md`，`R-20260828-01`）

预注册号的旧取法是 check-then-act：分支上「读当日 max」与「落盘占号」不原子，
取号到合并的整个窗口内并发 session 会取到同一个号；**双向避撞不收敛**
（-12 例：两个 session 各自让路，让到同一条道上）。与 MOC 原则
「配额要在副作用前预占，不是事后计数」同族。

## 机制

- 登记簿 ``~/.finance-runtime/ledger-id-claims.jsonl``：**仓外 runtime 目录**
  （机器状态，不是仓状态），只追加、不删改、**号不回收**——回收会造成
  「同号先后指两件事」，与重号同病。放弃的单就让号烧掉。
- 取号 = ``max(主干台账全文所有当日号, 登记簿当日已发号) + 1``，
  「读-算-追加」全程持 ``fcntl.flock(LOCK_EX)``（内核仲裁，覆盖本机全部进程）。
- 台账读 ``git show <ledger-ref>:docs/prediction-ledger.md``——**读主干不读
  工作树**（工作树可能是旧基座）；claim 默认先 fetch。

## fail-closed（三处，全部报错退出、不发号）

锁在时限内拿不到 / 登记簿任一行损坏 / ``git`` 读台账失败。
**不回退到手工 max+1**——回退 = 把洞重新打开。

## 约定依赖（诚实声明）

本脚本消灭的是**脚本用户之间**的竞态；有人绕过脚本手工取号，残余窗口仍在。
治本靠流程全员切换（AGENTS.md 台账节已约定：预注册号一律走本脚本）。
成立边界：所有取号 session 在同一台机器（当前事实成立）；
跨机取号出现时升级为「先占号 PR」（工单 §2 方案 b），先论证再做。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CLAIMS_FILE = Path.home() / ".finance-runtime" / "ledger-id-claims.jsonl"
LEDGER_RELPATH = "docs/prediction-ledger.md"
_ID_RE = re.compile(r"R-(\d{8})-(\d{2})")
_LOCK_TIMEOUT_SEC = 10.0


class ClaimError(RuntimeError):
    """fail-closed 出口：报错退出，不发号。"""


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise ClaimError(
            f"git {' '.join(args)} 失败（exit {proc.returncode}）：{proc.stderr.strip()}"
            "——fail closed，不发号"
        )
    return proc.stdout


def _read_claims(handle) -> list[dict]:
    """读登记簿全部行；任一行损坏 → ClaimError（fail-closed，不跳行）。"""
    handle.seek(0)
    claims: list[dict] = []
    for lineno, raw in enumerate(handle.read().splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ClaimError(
                f"登记簿第 {lineno} 行损坏（{exc}）——fail closed，不发号；"
                "人工修复该行后重试，勿删登记簿重建（已发号会被遗忘）"
            ) from exc
        if not isinstance(row, dict) or "id" not in row:
            raise ClaimError(
                f"登记簿第 {lineno} 行缺 id 字段——fail closed，不发号"
            )
        claims.append(row)
    return claims


def _max_nn_for_date(ids: list[str], date: str) -> int:
    best = 0
    for rid in ids:
        m = _ID_RE.fullmatch(rid) or _ID_RE.match(rid)
        if m and m.group(1) == date:
            best = max(best, int(m.group(2)))
    return best


def _ledger_max(ledger_text: str, date: str) -> int:
    """台账全文（含历史回填段）该日最大 NN。

    超码后缀留档行（如 ``R-…-07a``）会被前缀匹配读成 ``-07``——对 max 无害：
    超码行是同号变体，不占新号。
    """
    return max(
        (int(m.group(2)) for m in _ID_RE.finditer(ledger_text) if m.group(1) == date),
        default=0,
    )


def _acquire_lock(handle) -> None:
    deadline = time.monotonic() + _LOCK_TIMEOUT_SEC
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise ClaimError(
                    f"{_LOCK_TIMEOUT_SEC}s 内拿不到登记簿锁——fail closed，不发号"
                ) from None
            time.sleep(0.05)


def claim(
    *,
    branch: str,
    date: str,
    claims_file: Path,
    repo: Path,
    ledger_ref: str,
    fetch: bool,
) -> str:
    if fetch:
        remote, _, _ = ledger_ref.partition("/")
        _git(repo, "fetch", remote, "main")

    claims_file.parent.mkdir(parents=True, exist_ok=True)
    with open(claims_file, "a+", encoding="utf-8") as handle:
        _acquire_lock(handle)
        # 锁内完成全部「读-算-追加」；坏行/git 失败在追加前抛出 → 不发号。
        claims = _read_claims(handle)
        ledger_text = _git(repo, "show", f"{ledger_ref}:{LEDGER_RELPATH}")
        base_rev = _git(repo, "rev-parse", ledger_ref).strip()

        ledger_max = _ledger_max(ledger_text, date)
        claims_max = _max_nn_for_date([c["id"] for c in claims], date)
        next_nn = max(ledger_max, claims_max) + 1
        if next_nn > 99:
            raise ClaimError(f"{date} 两位号用尽（{next_nn}）——升位需人工裁决")
        rid = f"R-{date}-{next_nn:02d}"

        handle.seek(0, os.SEEK_END)
        handle.write(
            json.dumps(
                {
                    "id": rid,
                    "branch": branch,
                    "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                    "base_rev": base_rev,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())

    # 自述四项：取号依据可复核。
    print(f"主干 revision   {base_rev[:12]}（{ledger_ref}）")
    print(f"台账 {date} max  {ledger_max:02d}")
    print(f"登记簿 {date} max {claims_max:02d}")
    print(f"取到           {rid}")
    return rid


def list_claims(*, date: str | None, claims_file: Path) -> int:
    if not claims_file.is_file():
        print("登记簿不存在（尚无预占）")
        return 0
    with open(claims_file, "r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        claims = _read_claims(handle)
    shown = 0
    for row in claims:
        if date and not row["id"].startswith(f"R-{date}-"):
            continue
        shown += 1
        print(f"{row['id']}  branch={row.get('branch', '?')}  ts={row.get('ts', '?')}")
    if not shown:
        print(f"无{'当日' if date else ''}预占记录")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--claims-file",
        type=Path,
        default=DEFAULT_CLAIMS_FILE,
        help=f"登记簿路径（默认 {DEFAULT_CLAIMS_FILE}）",
    )
    common.add_argument(
        "--date",
        default=_dt.date.today().strftime("%Y%m%d"),
        help="取号日期 YYYYMMDD（默认今天）",
    )

    p_claim = sub.add_parser("claim", parents=[common], help="原子取一个新号")
    p_claim.add_argument("--branch", required=True, help="占号分支（登记溯源）")
    p_claim.add_argument("--repo", type=Path, default=REPO, help="仓库根（默认本仓）")
    p_claim.add_argument(
        "--ledger-ref",
        default="gitea/main",
        help="台账读取引用（默认 gitea/main；读主干不读工作树）",
    )
    p_claim.add_argument(
        "--no-fetch",
        action="store_true",
        help="跳过取号前 fetch（仅测试/离线用；生产默认 fetch）",
    )

    p_list = sub.add_parser("list", parents=[common], help="查已预占的号")
    p_list.add_argument(
        "--all-dates", action="store_true", help="不按日期过滤，列出全部"
    )

    args = ap.parse_args()
    try:
        if args.cmd == "claim":
            claim(
                branch=args.branch,
                date=args.date,
                claims_file=args.claims_file,
                repo=args.repo,
                ledger_ref=args.ledger_ref,
                fetch=not args.no_fetch,
            )
            return 0
        return list_claims(
            date=None if args.all_dates else args.date,
            claims_file=args.claims_file,
        )
    except ClaimError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
