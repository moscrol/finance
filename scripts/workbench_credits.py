#!/usr/bin/env python3
"""Workbench 额度账本运营 CLI：赠送、记充值、查余额、总览、撤销、流水。

账本本体在 ``intelligence/api/credits.py``（服务进程扣账用的同一份代码、同一把文件锁），
本脚本只是它的运营入口。服务进程每次扣额度都重读文件，这里写完**立即生效，不用重启**。

用法（用 8792 同一个 users 根跑：FORESIGHT_USERS_DIR 与启动器一致）::

    # 赠送 30 次，不过期
    python3 scripts/workbench_credits.py grant --user alpha-friend-a --kind gift --runs 30 --note "内测赠送"
    # 记一笔月度充值：200 次，30 天后到期（--days 改天数，或 --expires 2026-10-01 到那天 0 点）
    python3 scripts/workbench_credits.py grant --user alpha-friend-a --kind monthly --runs 200 --note "9 月充值 ¥xx"
    python3 scripts/workbench_credits.py balance --user alpha-friend-a
    python3 scripts/workbench_credits.py list                      # 所有有账本的用户
    python3 scripts/workbench_credits.py revoke --user alpha-friend-a --grant-id g-2026... --note "退款"
    python3 scripts/workbench_credits.py history --user alpha-friend-a --limit 50

退出码：0 成功；2 参数/账本错误（信息在 stderr）。加 ``--json`` 输出机器可读。
将来接支付回调时，直接调 ``CreditStore.grant(kind="monthly", ...)``，不要再造一套写账本的代码。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from intelligence.api.credits import (  # noqa: E402
    KIND_MONTHLY,
    KINDS,
    CorruptLedger,
    CreditStore,
)

DEFAULT_MONTHLY_DAYS = 30


def _store() -> CreditStore:
    # enabled=True：运营操作不看服务端开关；exempt 与服务端同一个 env，免得给 owner 记账
    exempt = frozenset(
        item.strip()
        for item in (os.environ.get("WORKBENCH_QUOTA_EXEMPT_USERS") or "").split(",")
        if item.strip()
    )
    return CreditStore(enabled=True, exempt_users=exempt)


def _parse_expires(args: argparse.Namespace) -> dt.datetime | None:
    if args.expires and args.days is not None:
        raise SystemExit("--expires 与 --days 只能给一个")
    if args.expires:
        try:
            day = dt.date.fromisoformat(args.expires)
        except ValueError as exc:
            raise SystemExit(
                f"--expires 需要 YYYY-MM-DD，得到 {args.expires!r}"
            ) from exc
        # 那一天的本地 0 点：「有效期到 9 月底」= --expires 2026-10-01
        local = dt.datetime.combine(day, dt.time.min).astimezone()
        return local
    days = args.days
    if days is None:
        days = DEFAULT_MONTHLY_DAYS if args.kind == KIND_MONTHLY else None
    if days is None:
        return None
    if days <= 0:
        raise SystemExit("--days 必须是正整数")
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)


def _fmt_grant(g: dict[str, object]) -> str:
    exp = g["expires_at"] or "不过期"
    note = f"  # {g['note']}" if g.get("note") else ""
    return f"  {g['id']}  {g['kind']:<8}{g['remaining']:>5}/{g['amount']:<5} 到期 {exp}{note}"


def cmd_grant(args: argparse.Namespace) -> int:
    if args.runs <= 0:
        raise SystemExit("--runs 必须是正整数")
    store = _store()
    if args.user in store.exempt_users:
        print(
            f"⚠ {args.user} 在 WORKBENCH_QUOTA_EXEMPT_USERS 里，不扣额度；这笔授予不会被用到。",
            file=sys.stderr,
        )
    try:
        grant = store.grant(
            args.user,
            args.kind,
            args.runs,
            expires_at=_parse_expires(args),
            note=args.note,
        )
    except CorruptLedger as exc:
        raise SystemExit(f"账本损坏，拒绝叠新账：{exc}（先人工修文件）") from exc
    if args.json:
        print(json.dumps(grant.to_dict(), ensure_ascii=False))
    else:
        print(f"✓ {args.user} +{grant.amount} ({grant.kind})")
        print(_fmt_grant(grant.to_dict()))
        balance = store.balance(args.user)
        print(f"  余额 {balance.remaining}")
    return 0


def cmd_balance(args: argparse.Namespace) -> int:
    balance = _store().balance(args.user)
    if args.json:
        print(json.dumps(balance.public_dict(), ensure_ascii=False))
        return 0
    if balance.exempt:
        print(f"{args.user}: 豁免（不计额度）")
        return 0
    if balance.corrupt:
        print(
            f"{args.user}: ⚠ 账本损坏（credits.json 解析失败），服务端已拒绝扣额",
            file=sys.stderr,
        )
        return 2
    print(
        f"{args.user}: 余额 {balance.remaining}"
        + (f"，最近到期 {balance.next_expiry}" if balance.next_expiry else "")
    )
    for g in balance.grants:
        print(_fmt_grant(g.to_dict()))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = [
        {
            "user": b.user_id,
            "remaining": b.remaining,
            "next_expiry": b.next_expiry,
            "grants": len(b.grants),
            "corrupt": b.corrupt,
        }
        for b in _store().list_users()
    ]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    if not rows:
        print("（没有任何用户有额度账本）")
        return 0
    for r in rows:
        flag = "  ⚠ 账本损坏" if r["corrupt"] else ""
        exp = f"  最近到期 {r['next_expiry']}" if r["next_expiry"] else ""
        print(
            f"{r['user']:<24} 余额 {str(r['remaining']):>5}  授予 {r['grants']} 笔{exp}{flag}"
        )
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    store = _store()
    try:
        revoked = store.revoke(args.user, args.grant_id, note=args.note)
    except KeyError:
        raise SystemExit(f"{args.user} 没有 grant {args.grant_id}") from None
    except FileNotFoundError:
        raise SystemExit(f"{args.user} 没有额度账本") from None
    if args.json:
        print(json.dumps(revoked.to_dict(), ensure_ascii=False))
    else:
        print(
            f"✓ 已撤销 {revoked.id}（{revoked.kind}），余额 {store.balance(args.user).remaining}"
        )
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    rows = _store().history(args.user, limit=args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False))
        return 0
    if not rows:
        print(f"{args.user}: 无流水")
        return 0
    for row in rows:
        note = f"  # {row['note']}" if row.get("note") else ""
        refunded = "  (已退回)" if row.get("refunded") else ""
        print(
            f"{row['at']}  {row['delta']:>+5}  {row['reason']:<7} {row['grant_id']}  by {row['actor']}{note}{refunded}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    grant = sub.add_parser("grant", help="赠送 / 记充值")
    grant.add_argument("--user", required=True)
    grant.add_argument("--kind", required=True, choices=KINDS)
    grant.add_argument("--runs", required=True, type=int, help="授予的 run 次数")
    grant.add_argument(
        "--days", type=int, help="几天后到期；monthly 默认 30，gift 默认不过期"
    )
    grant.add_argument("--expires", help="到期日 YYYY-MM-DD（当天本地 0 点失效）")
    grant.add_argument("--note", default="")
    grant.add_argument("--json", action="store_true")
    grant.set_defaults(func=cmd_grant)

    balance = sub.add_parser("balance", help="某用户余额与各笔授予")
    balance.add_argument("--user", required=True)
    balance.add_argument("--json", action="store_true")
    balance.set_defaults(func=cmd_balance)

    listing = sub.add_parser("list", help="所有有账本的用户")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=cmd_list)

    revoke = sub.add_parser("revoke", help="把某笔授予的余量清零")
    revoke.add_argument("--user", required=True)
    revoke.add_argument("--grant-id", required=True)
    revoke.add_argument("--note", default="")
    revoke.add_argument("--json", action="store_true")
    revoke.set_defaults(func=cmd_revoke)

    history = sub.add_parser("history", help="逐笔流水")
    history.add_argument("--user", required=True)
    history.add_argument("--limit", type=int, default=50, help="最近 N 条；0 = 全部")
    history.add_argument("--json", action="store_true")
    history.set_defaults(func=cmd_history)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(f"✗ {exc.code}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
