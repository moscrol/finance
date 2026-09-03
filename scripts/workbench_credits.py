#!/usr/bin/env python3
"""Workbench 积分账本运营 CLI：赠送、记充值、查余额、总览、撤销、流水、价目、估价。

账本本体在 ``intelligence/api/credits.py``（服务进程扣账用的同一份代码、同一把文件锁），
本脚本只是它的运营入口。服务进程每次扣账都重读文件，这里写完**立即生效，不用重启**。

单位：积分，100 积分 = 1 元。``--points`` 与 ``--yuan`` 二选一（20 元 == 2000 积分）。

用法（用 8792 同一个 users 根跑：FORESIGHT_USERS_DIR 与启动器一致）::

    # 赠送 2000 积分（20 元），不过期
    python3 scripts/workbench_credits.py grant --user alpha-friend-a --kind gift --points 2000 --note "内测赠送"
    # 记一笔月度充值：20 元，30 天后到期（--days 改天数，或 --expires 2026-10-01 到那天 0 点）
    python3 scripts/workbench_credits.py grant --user alpha-friend-a --kind monthly --yuan 20 --note "9 月充值 微信"
    python3 scripts/workbench_credits.py balance --user alpha-friend-a
    python3 scripts/workbench_credits.py list                      # 所有有账本的用户
    python3 scripts/workbench_credits.py revoke --user alpha-friend-a --grant-id g-2026... --note "退款"
    python3 scripts/workbench_credits.py history --user alpha-friend-a --limit 50
    python3 scripts/workbench_credits.py pricing                   # 当前生效的价目表（含来源）
    python3 scripts/workbench_credits.py estimate --input-tokens 37256 --output-tokens 792 --model glm-5.3

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
    POINTS_PER_YUAN,
    CorruptLedger,
    CreditPricing,
    CreditStore,
    RunUsage,
    points_to_yuan_text,
)

DEFAULT_MONTHLY_DAYS = 30


def _store() -> CreditStore:
    # enabled=True：运营操作不看服务端开关；exempt 与服务端同一个 env，免得给 owner 记账；
    # 价目表同样读 WORKBENCH_CREDITS_PRICING，estimate 出来的数与服务端结算一致。
    exempt = frozenset(
        item.strip()
        for item in (os.environ.get("WORKBENCH_QUOTA_EXEMPT_USERS") or "").split(",")
        if item.strip()
    )
    return CreditStore(
        enabled=True, exempt_users=exempt, pricing=CreditPricing.from_env()
    )


def _points_arg(args: argparse.Namespace) -> int:
    if (args.points is None) == (args.yuan is None):
        raise SystemExit("--points 与 --yuan 必须且只能给一个（100 积分 = 1 元）")
    if args.points is not None:
        if args.points <= 0:
            raise SystemExit("--points 必须是正整数")
        return int(args.points)
    if args.yuan <= 0:
        raise SystemExit("--yuan 必须是正数")
    points = round(args.yuan * POINTS_PER_YUAN)
    if abs(points - args.yuan * POINTS_PER_YUAN) > 1e-6:
        raise SystemExit("--yuan 最小到分（0.01 元 = 1 积分）")
    return int(points)


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
        return dt.datetime.combine(day, dt.time.min).astimezone()
    days = args.days
    if days is None:
        days = DEFAULT_MONTHLY_DAYS if args.kind == KIND_MONTHLY else None
    if days is None:
        return None
    if days <= 0:
        raise SystemExit("--days 必须是正整数")
    return dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)


def _fmt_points(points: int) -> str:
    return f"{points} 积分（{points_to_yuan_text(points)}）"


def _fmt_grant(g: dict[str, object]) -> str:
    exp = g["expires_at"] or "不过期"
    note = f"  # {g['note']}" if g.get("note") else ""
    return f"  {g['id']}  {g['kind']:<8}{g['remaining']:>6}/{g['amount']:<6} 到期 {exp}{note}"


def cmd_grant(args: argparse.Namespace) -> int:
    points = _points_arg(args)
    store = _store()
    if args.user in store.exempt_users:
        print(
            f"⚠ {args.user} 在 WORKBENCH_QUOTA_EXEMPT_USERS 里，不扣积分；这笔授予不会被用到。",
            file=sys.stderr,
        )
    try:
        grant = store.grant(
            args.user,
            args.kind,
            points,
            expires_at=_parse_expires(args),
            note=args.note,
        )
    except CorruptLedger as exc:
        raise SystemExit(f"账本损坏，拒绝叠新账：{exc}（先人工修文件）") from exc
    if args.json:
        print(json.dumps(grant.to_dict(), ensure_ascii=False))
        return 0
    print(f"✓ {args.user} +{_fmt_points(grant.amount)} ({grant.kind})")
    if grant.remaining < grant.amount:
        print(f"  其中 {grant.amount - grant.remaining} 积分先抵了欠账")
    print(_fmt_grant(grant.to_dict()))
    balance = store.balance(args.user)
    print(f"  可用 {_fmt_points(balance.remaining or 0)}")
    return 0


def cmd_balance(args: argparse.Namespace) -> int:
    balance = _store().balance(args.user)
    if args.json:
        print(json.dumps(balance.public_dict(), ensure_ascii=False))
        return 0
    if balance.exempt:
        print(f"{args.user}: 豁免（不计积分）")
        return 0
    if balance.corrupt:
        print(
            f"{args.user}: ⚠ 账本损坏（credits.json 解析失败），服务端已拒绝扣账",
            file=sys.stderr,
        )
        return 2
    line = f"{args.user}: 可用 {_fmt_points(balance.remaining or 0)}"
    if balance.holds:
        line += f"，在途预占 {balance.holds}"
    if balance.debt:
        line += f"，欠账 {balance.debt}"
    if balance.next_expiry:
        line += f"，最近到期 {balance.next_expiry}"
    print(line)
    for g in balance.grants:
        print(_fmt_grant(g.to_dict()))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = [
        {
            "user": b.user_id,
            "remaining": b.remaining,
            "holds": b.holds,
            "debt": b.debt,
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
        print("（没有任何用户有积分账本）")
        return 0
    for r in rows:
        flag = "  ⚠ 账本损坏" if r["corrupt"] else ""
        debt = f"  欠账 {r['debt']}" if r["debt"] else ""
        exp = f"  最近到期 {r['next_expiry']}" if r["next_expiry"] else ""
        print(
            f"{r['user']:<24} 可用 {str(r['remaining']):>6} 积分  授予 {r['grants']} 笔{debt}{exp}{flag}"
        )
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    store = _store()
    try:
        revoked = store.revoke(args.user, args.grant_id, note=args.note)
    except KeyError:
        raise SystemExit(f"{args.user} 没有 grant {args.grant_id}") from None
    except FileNotFoundError:
        raise SystemExit(f"{args.user} 没有积分账本") from None
    if args.json:
        print(json.dumps(revoked.to_dict(), ensure_ascii=False))
        return 0
    print(
        f"✓ 已撤销 {revoked.id}（{revoked.kind}），可用 {_fmt_points(store.balance(args.user).remaining or 0)}"
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
        detail = ""
        if row.get("note"):
            detail += f"  # {row['note']}"
        usage = row.get("usage")
        if isinstance(usage, dict):
            detail += f"  [{usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out]"
        if row.get("debt_added"):
            detail += f"  欠账 +{row['debt_added']}"
        ref = row.get("run_id") or row.get("grant_id") or ""
        print(
            f"{row['at']}  {row['delta']:>+6}  {row['reason']:<11} {ref}  by {row['actor']}{detail}"
        )
    return 0


def cmd_pricing(args: argparse.Namespace) -> int:
    pricing = CreditPricing.from_env()
    if args.json:
        print(json.dumps(pricing.to_dict(), ensure_ascii=False))
        return 0
    table = pricing.to_dict()
    print(
        f"价目表来源：{table['source']}（不设 WORKBENCH_CREDITS_PRICING 时用内置占位，上线前要改）"
    )
    print(
        f"  100 积分 = 1 元；markup ×{table['markup']}；每次基础费 {table['base_fee_yuan']} 元；"
    )
    print(
        f"  最低消费 {table['min_charge_yuan']} 元；预占 {table['hold_yuan']} 元；"
        f"工具调用 {table['tool_call_fee_yuan']} 元/次"
    )
    for name, rate in table["models"].items():  # type: ignore[union-attr]
        print(
            f"  {name:<16} 输入 {rate['input_yuan_per_1m']:>6} 元/M   输出 {rate['output_yuan_per_1m']:>6} 元/M"
        )
    print("  算式：ceil((基础费 + markup × Σ token 费 + 工具费) × 100)，再取最低消费")
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    pricing = CreditPricing.from_env()
    usage = RunUsage(
        {args.model: (args.input_tokens, args.output_tokens)},
        llm_calls=1,
        tool_calls=args.tool_calls,
    )
    breakdown = pricing.cost(usage, completed=True)
    if args.json:
        print(json.dumps(breakdown.to_dict(), ensure_ascii=False))
        return 0
    print(
        f"{args.input_tokens} in / {args.output_tokens} out @ {args.model}，{args.tool_calls} 次工具 → "
        f"{_fmt_points(breakdown.points)}"
    )
    print(
        f"  基础费 {breakdown.base_fee_yuan} + token 费 {breakdown.token_yuan}（含 markup ×{breakdown.markup}）"
        f" + 工具费 {breakdown.tool_yuan} = {breakdown.cost_yuan} 元"
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
    grant.add_argument("--points", type=int, help="授予的积分数（与 --yuan 二选一）")
    grant.add_argument(
        "--yuan", type=float, help="按元授予，100 积分 = 1 元（与 --points 二选一）"
    )
    grant.add_argument(
        "--days", type=int, help="几天后到期；monthly 默认 30，gift 默认不过期"
    )
    grant.add_argument("--expires", help="到期日 YYYY-MM-DD（当天本地 0 点失效）")
    grant.add_argument("--note", default="")
    grant.add_argument("--json", action="store_true")
    grant.set_defaults(func=cmd_grant)

    balance = sub.add_parser("balance", help="某用户余额、预占、欠账与各笔授予")
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

    history = sub.add_parser("history", help="逐笔流水（run 行带用量与算式）")
    history.add_argument("--user", required=True)
    history.add_argument("--limit", type=int, default=50, help="最近 N 条；0 = 全部")
    history.add_argument("--json", action="store_true")
    history.set_defaults(func=cmd_history)

    pricing = sub.add_parser("pricing", help="当前生效的价目表")
    pricing.add_argument("--json", action="store_true")
    pricing.set_defaults(func=cmd_pricing)

    estimate = sub.add_parser("estimate", help="按用量算一次 run 的积分")
    estimate.add_argument("--input-tokens", type=int, required=True)
    estimate.add_argument("--output-tokens", type=int, required=True)
    estimate.add_argument("--model", default="default")
    estimate.add_argument("--tool-calls", type=int, default=0)
    estimate.add_argument("--json", action="store_true")
    estimate.set_defaults(func=cmd_estimate)
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
    except ValueError as exc:  # 价目表/参数校验
        print(f"✗ {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
