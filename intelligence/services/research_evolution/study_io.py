"""真实前向实验的受控入口（spec 06 §5.2）：``python -m intelligence.services.research_evolution.study_io``。

五个子命令 ``freeze / register / settle / evaluate / show``，**全部调 03 的公开函数**，
冻结与评分逻辑一行都不复制；唯一 writer 仍是 03 的 ``Repository``。

四条硬规矩：

1. **时钟归服务端**。``now`` 一律在这里取（``datetime.now(SHANGHAI)``），输入包里出现
   ``now`` / ``registered_at`` / ``eligible`` 之类的键会被 03 直接拒收——登记时刻不能被回填。
2. **默认只读**。不加 ``--apply`` 就是 dry-run：校验、打印将要发生什么，不落任何盘。
3. **owner 显式传**，用户态根由 ``userspace.user_space(owner).root / "research_validation"`` 解析，
   不从 cwd 推断。
4. **未到期就是未到期**。``settle`` 读已授权结果源；未来没到 03 会返回 pending，这里照实打印，
   不催熟、不倒填。

它不发邀请、不联系任何人、不创建付款，也不新增任何调度：要回检就人来敲这条命令。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from intelligence.services.research_evolution.access import OwnerContext
from intelligence.services.research_evolution.contracts import scrub_paths

COMMANDS = ("freeze", "register", "settle", "evaluate", "show")
# 登记时钟必须由服务端取；输入包里出现这些键一律视为试图回填。
FORBIDDEN_INPUT_KEYS = frozenset({"now", "registered_at", "accessed_at", "eligible", "frozen_at"})


def _shanghai_now() -> datetime:
    from intelligence.services.research_validation.contracts import SHANGHAI

    return datetime.now(SHANGHAI)


def _repository(ctx: OwnerContext) -> Any:
    from intelligence.services.research_validation import Repository

    return Repository(ctx.validation_root, owner_user_id=ctx.owner_user_id)


def _load(path: str | Path) -> Any:
    body = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    _reject_clock_keys(body, where=str(Path(path).name))
    return body


def _reject_clock_keys(body: Any, *, where: str) -> None:
    if isinstance(body, Mapping):
        bad = sorted(FORBIDDEN_INPUT_KEYS & set(body))
        if bad:
            raise SystemExit(f"{where}: 输入包不得包含 {bad}——登记时刻由服务端取，不接受回填")
        for value in body.values():
            _reject_clock_keys(value, where=where)
    elif isinstance(body, (list, tuple)):
        for item in body:
            _reject_clock_keys(item, where=where)


def _emit(payload: Any) -> None:
    print(json.dumps(scrub_paths(payload), ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------- #
# 子命令
# --------------------------------------------------------------------------- #
def cmd_freeze(args: argparse.Namespace, ctx: OwnerContext, now: datetime) -> int:
    from intelligence.services.research_validation import ContractError, freeze_study

    body = _load(args.protocol)
    if not args.apply:
        _emit({"dry_run": True, "would": "freeze_study", "owner": ctx.owner_user_id, "mode": body.get("mode"), "lineage_id": body.get("lineage_id"), "now": now.isoformat()})
        return 0
    try:
        protocol = freeze_study(owner=ctx.owner_user_id, repository=_repository(ctx), now=now, protocol_input=body)
    except ContractError as exc:
        _emit({"ok": False, "error": str(exc)})
        return 2
    _emit({"ok": True, "study_id": protocol["study_id"], "frozen_at": protocol["frozen_at"], "synthetic": protocol.get("synthetic")})
    return 0


def cmd_register(args: argparse.Namespace, ctx: OwnerContext, now: datetime) -> int:
    from intelligence.services.research_validation import register_forecasts

    forecasts = _load(args.forecasts)
    if not isinstance(forecasts, list):
        raise SystemExit("forecasts 必须是列表")
    if not args.apply:
        _emit({"dry_run": True, "would": "register_forecasts", "study_id": args.study_id, "count": len(forecasts), "now": now.isoformat()})
        return 0
    result = register_forecasts(owner=ctx.owner_user_id, repository=_repository(ctx), now=now, study_id=args.study_id, forecasts=forecasts)
    _emit(
        {
            "ok": not result.rejected,
            "accepted": len(result.accepted),
            "idempotent": len(result.idempotent),
            "rejected": [dict(r.to_dict()) if hasattr(r, "to_dict") else r for r in result.rejected],
            "gaps": [g.__dict__ if hasattr(g, "__dict__") else g for g in result.gaps],
        }
    )
    return 0 if not result.rejected else 2


def cmd_settle(args: argparse.Namespace, ctx: OwnerContext, now: datetime, outcome_source_factory: Callable[[argparse.Namespace], Any] | None = None) -> int:
    from intelligence.services.research_validation import settle_outcomes

    if outcome_source_factory is None:
        _emit(
            {
                "ok": False,
                "error": "没有配置结果源：settle 需要一个已授权的 OutcomeSource",
                "hint": "由执行人按 03 BLOCKED 的「结果源」一条决定生产用哪个源，再以 --outcome-source 接入",
            }
        )
        return 2
    source = outcome_source_factory(args)
    if not args.apply:
        _emit({"dry_run": True, "would": "settle_outcomes", "study_id": args.study_id, "now": now.isoformat()})
        return 0
    result = settle_outcomes(owner=ctx.owner_user_id, repository=_repository(ctx), now=now, study_id=args.study_id, outcome_source=source)
    _emit(
        {
            "ok": not result.refused,
            "refused": result.refused,
            "settled": len(result.settled),
            "pending": len(result.pending),
            "missing": len(result.missing),
            "invalid": len(result.invalid),
            "revised": len(result.revised),
        }
    )
    return 0 if not result.refused else 2


def cmd_evaluate(args: argparse.Namespace, ctx: OwnerContext, now: datetime) -> int:
    from intelligence.services.research_validation import evaluate_study

    receipt = evaluate_study(owner=ctx.owner_user_id, repository=_repository(ctx), now=now, study_id=args.study_id)
    _emit(
        {
            "study_id": args.study_id,
            "empirical_status": receipt.get("empirical_status"),
            "counts": receipt.get("counts"),
            "decision_eligible": receipt.get("decision_eligible"),
            "synthetic": receipt.get("synthetic"),
            "pending_gaps": receipt.get("pending_gaps"),
        }
    )
    return 0


def cmd_show(args: argparse.Namespace, ctx: OwnerContext, now: datetime) -> int:
    """只读：列出本 owner 的实验与收据状态。读收据正文仍要走 03 的曝光登记。"""
    repo = _repository(ctx)
    studies = []
    for study_id in repo.list_studies():
        receipts = repo.list_receipts(study_id)
        studies.append(
            {
                "study_id": study_id,
                "forecasts": len(repo.list_forecasts(study_id)),
                "receipts": [{"id": r.get("id"), "empirical_status": r.get("empirical_status")} for r in receipts],
            }
        )
    _emit({"owner": ctx.owner_user_id, "studies": studies, "exposures": len(repo.list_exposures())})
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="study_io", description="真实前向实验的受控本地入口（调用 03，不复制其逻辑）")
    parser.add_argument("--owner", required=True, help="经验证的用户 id；用户态根由 userspace 解析")
    parser.add_argument("--apply", action="store_true", help="真正落盘；缺省是 dry-run")
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze", help="冻结一份前向协议")
    freeze.add_argument("--protocol", required=True, help="协议输入 JSON 路径")

    register = sub.add_parser("register", help="登记预测")
    register.add_argument("--study-id", required=True)
    register.add_argument("--forecasts", required=True, help="预测列表 JSON 路径")

    settle = sub.add_parser("settle", help="到期结算")
    settle.add_argument("--study-id", required=True)

    evaluate = sub.add_parser("evaluate", help="出收据（未到期就是 pending）")
    evaluate.add_argument("--study-id", required=True)

    sub.add_parser("show", help="列出实验与收据状态")
    return parser


_HANDLERS: dict[str, Callable[..., int]] = {
    "freeze": cmd_freeze,
    "register": cmd_register,
    "settle": cmd_settle,
    "evaluate": cmd_evaluate,
    "show": cmd_show,
}


def main(argv: Sequence[str] | None = None, *, now: datetime | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    ctx = OwnerContext.for_owner(args.owner)
    moment = now or _shanghai_now()
    handler = _HANDLERS[args.command]
    return handler(args, ctx, moment)


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    sys.exit(main())
