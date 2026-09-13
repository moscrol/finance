"""原流程与配对试点的受控登记入口（spec 06 §5.1）：
``python -m intelligence.services.research_evolution.pilot_io``。

四个子命令 ``register / import-events / rebuild / show``，全部经 06 的**同一个 writer**
（``EvolutionStore``）落盘，计算调 05 的纯函数（``prepare_events`` / ``measure_pair`` / ``summarize``）。

为什么需要它：光靠研究会话里点几下，测不到「用户不用工具是怎么做的」。原流程计时、外部查阅、
人工帮助、盲审、费用这些事实根本不经过 Workbench，只能由执行人按权限导入。

边界（每一条都是刻意的）：

- 默认 dry-run，``--apply`` 才写；
- 只接受**命令行显式指定**的本地输入文件，不从任意路径 / URL 自动读取；
- ``manual_import`` 渠道的事件必须带 ``importer_id`` / ``evidence_ref`` / ``evidence_hash``（05 校验）；
- 整批校验失败就整批不写：不留半批有效测量；
- 它不发邀请、不联系参与者、不创建付款。付款只能在**实际发生后**按凭据导入。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence

from intelligence.services.research_evolution.access import OwnerContext
from intelligence.services.research_evolution.contracts import ApiError, digest, scrub_paths, utc_iso
from intelligence.services.research_evolution.store import (
    PROTOCOLS_DIR,
    RECEIPTS_DIR,
    REGISTRATIONS_DIR,
    SUMMARIES_DIR,
    EvolutionStore,
)

REGISTER_KINDS = ("protocol", "assignment", "diagnostics_policy", "exercise_pack")


def _shanghai_now() -> datetime:
    from intelligence.services.research_validation.contracts import SHANGHAI

    return datetime.now(SHANGHAI)


def _store(ctx: OwnerContext) -> EvolutionStore:
    return EvolutionStore(ctx.evolution_root, ctx.owner_user_id)


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(Path(path).expanduser().read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{Path(path).name} 第 {lineno} 行不是合法 JSON：{exc}") from None
        rows.append(row)
    return rows


def _emit(payload: Any) -> None:
    print(json.dumps(scrub_paths(payload), ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------- #
# register：协议 / 分配 / 诊断策略 / 题包
# --------------------------------------------------------------------------- #
def cmd_register(args: argparse.Namespace, ctx: OwnerContext, now: datetime) -> int:
    from intelligence.services.product_value import freeze_protocol, protocol_hash, validate_protocol
    from intelligence.services.product_value.protocol import ProtocolError

    body = _read_json(args.input)
    store = _store(ctx)

    if args.kind == "protocol":
        try:
            validate_protocol(body)
            frozen = freeze_protocol(body)
        except ProtocolError as exc:
            _emit({"ok": False, "error": str(exc)})
            return 2
        phash = protocol_hash(frozen)
        if not args.apply:
            _emit({"dry_run": True, "would": "publish_protocol", "protocol_hash": phash, "protocol_version": frozen.get("protocol_version")})
            return 0
        with store.transaction() as txn:
            stored, created = txn.publish_immutable(PROTOCOLS_DIR, phash, dict(frozen))
        _emit({"ok": True, "created": created, "protocol_hash": phash, "protocol_version": stored.get("protocol_version")})
        return 0

    if args.kind == "assignment":
        # 分配是「事前配对」的证据：迟登照实标记，不能补成事前。
        assignment_id = str(body.get("assignment_id") or "").strip()
        if not assignment_id:
            _emit({"ok": False, "error": "assignment 必须带 assignment_id"})
            return 2
        record = {
            **body,
            "owner_user_id": ctx.owner_user_id,
            "registered_at": utc_iso(now),
            "late_registration": bool(body.get("assigned_at") and str(body["assigned_at"]) < utc_iso(now)),
        }
        if not args.apply:
            _emit({"dry_run": True, "would": "publish_assignment", "assignment_id": assignment_id, "late_registration": record["late_registration"]})
            return 0
        with store.transaction() as txn:
            stored, created = txn.publish_immutable(REGISTRATIONS_DIR, f"assignment-{assignment_id}", record)
        _emit({"ok": True, "created": created, "assignment_id": assignment_id, "late_registration": stored["late_registration"]})
        return 0

    # diagnostics_policy / exercise_pack：04 需要的领域配置
    payload = {"policy": body, "provenance": body.get("provenance", "observed")} if args.kind == "diagnostics_policy" else {"pack": body, "provenance": body.get("provenance", "observed")}
    if not args.apply:
        _emit({"dry_run": True, "would": "publish_registration", "kind": args.kind, "digest": digest(payload)[:16]})
        return 0
    with store.transaction() as txn:
        _, created = txn.publish_immutable(REGISTRATIONS_DIR, args.kind, payload)
    _emit({"ok": True, "created": created, "kind": args.kind})
    return 0


# --------------------------------------------------------------------------- #
# import-events：M 渠道导入
# --------------------------------------------------------------------------- #
def cmd_import_events(args: argparse.Namespace, ctx: OwnerContext, now: datetime) -> int:
    from intelligence.services.product_value import prepare_events
    from intelligence.services.product_value.contracts import SOURCE_MANUAL

    rows = _read_jsonl(args.events)
    protocol = _read_json(args.protocol) if args.protocol else None
    stamped: list[dict[str, Any]] = []
    for row in rows:
        stamped.append(
            {
                **row,
                "owner_user_id": ctx.owner_user_id,
                # 来源渠道由**接收入口**决定，不采信文件里写的。
                "source_channel": SOURCE_MANUAL,
                "recorded_at": utc_iso(now),
            }
        )
    prepared = prepare_events(stamped, protocol=protocol)
    if prepared.rejected or prepared.conflicts:
        _emit(
            {
                "ok": False,
                "reason": "整批校验未通过，未写入任何事件",
                "rejected": prepared.rejected[:20],
                "conflicts": prepared.conflicts[:20],
                "accepted_would_be": len(prepared.accepted),
            }
        )
        return 2
    if not args.apply:
        _emit({"dry_run": True, "would": "append_events", "accepted": len(prepared.accepted), "duplicates": len(prepared.duplicates)})
        return 0
    store = _store(ctx)
    created = 0
    with store.transaction() as txn:
        # S2：先在锁内把**整批**与现有台账对账——同 event_id 异内容的任何一条都让整批失败、
        # 零写入（「锁不是回滚机制」：逐条追加到一半才发现冲突，前半批已经生效了）。
        existing_by_id: dict[str, str] = {}
        for row in txn.list_product_value_events():
            existing_by_id[str(row.get("event_id") or "")] = str(row.get("content_digest") or "")
        ledger_conflicts: list[dict[str, Any]] = []
        for event in prepared.accepted:
            event_id = str(event["event_id"])
            content_hash = prepared.content_hashes.get(event_id) or digest(event)
            stored_digest = existing_by_id.get(event_id)
            if stored_digest is not None and stored_digest != content_hash:
                ledger_conflicts.append({"event_id": event_id, "code": "idempotency_payload_mismatch", "message": "与台账中同 id 事件内容不同"})
        if ledger_conflicts:
            _emit({"ok": False, "reason": "整批与现有台账冲突，未写入任何事件", "conflicts": ledger_conflicts[:20], "accepted_would_be": len(prepared.accepted)})
            return 2
        for event in prepared.accepted:
            _, is_new = txn.append_product_value_event(event, content_hash=prepared.content_hashes.get(str(event["event_id"])) or digest(event))
            created += 1 if is_new else 0
    _emit({"ok": True, "written": created, "already_present": len(prepared.accepted) - created, "duplicates_in_input": len(prepared.duplicates)})
    return 0


# --------------------------------------------------------------------------- #
# rebuild：由协议 + 原事件重算不可变收据与总结
# --------------------------------------------------------------------------- #
def cmd_rebuild(args: argparse.Namespace, ctx: OwnerContext, now: datetime) -> int:
    from intelligence.services.product_value import RunStoreEvidenceReader, measure_pair, summarize
    from intelligence.services.run_store import RunStore

    store = _store(ctx)
    protocol = store.read_immutable(PROTOCOLS_DIR, args.protocol_hash)
    if protocol is None:
        _emit({"ok": False, "error": "找不到该协议哈希对应的冻结协议；先 register --kind protocol"})
        return 2
    events = store.list_product_value_events()
    if not events:
        _emit({"ok": False, "error": "本 owner 名下没有任何测量事件"})
        return 2

    reader = RunStoreEvidenceReader(store_for_owner=lambda owner: RunStore(user_id=owner) if owner == ctx.owner_user_id else None)
    pair_ids = sorted({str(e.get("case_pair_id")) for e in events if e.get("case_pair_id")})
    receipts: list[dict[str, Any]] = []
    for pair_id in pair_ids:
        receipts.append(measure_pair(events, protocol, reader, case_pair_id=pair_id, now=now))
    assignments = [e for e in events if e.get("event_type") == "assignment_created"]
    cohort = [e for e in events if e.get("event_type") in {"consent_changed", "reuse_observed", "recheck_completed", "payment_recorded"}]
    summary = summarize(receipts, assignments, protocol, cohort_events=cohort, now=now)

    if not args.apply:
        _emit(
            {
                "dry_run": True,
                "pairs": pair_ids,
                "receipt_ids": [r.get("receipt_id") for r in receipts],
                "summary_id": summary.get("summary_id"),
                "engineering_status": summary.get("engineering_status"),
                "field_status": summary.get("field_status"),
                "commercial_status": summary.get("commercial_status"),
            }
        )
        return 0

    written = 0
    with store.transaction() as txn:
        for receipt in receipts:
            _, created = txn.publish_immutable(RECEIPTS_DIR, str(receipt["receipt_id"]), receipt)
            written += 1 if created else 0
        _, summary_created = txn.publish_immutable(SUMMARIES_DIR, str(summary["summary_id"]), summary)
    _emit(
        {
            "ok": True,
            "receipts_written": written,
            "receipts_total": len(receipts),
            "summary_id": summary["summary_id"],
            "summary_created": summary_created,
            "field_status": summary.get("field_status"),
            "commercial_status": summary.get("commercial_status"),
        }
    )
    return 0


# --------------------------------------------------------------------------- #
# show
# --------------------------------------------------------------------------- #
def cmd_show(args: argparse.Namespace, ctx: OwnerContext, now: datetime) -> int:
    store = _store(ctx)
    _emit(
        {
            "owner": ctx.owner_user_id,
            "events": len(store.list_product_value_events()),
            "process_receipts": len(store.list_process_receipts()),
            "protocols": [p.get("protocol_version") for p in store.list_immutable(PROTOCOLS_DIR)],
            "receipts": [{"id": r.get("receipt_id"), "status": r.get("status")} for r in store.list_immutable(RECEIPTS_DIR)],
            "summaries": [
                {
                    "id": s.get("summary_id"),
                    "engineering_status": s.get("engineering_status"),
                    "field_status": s.get("field_status"),
                    "commercial_status": s.get("commercial_status"),
                }
                for s in store.list_immutable(SUMMARIES_DIR)
            ],
            "registrations": sorted(str(r.get("kind") or "") for r in store.list_immutable(REGISTRATIONS_DIR)),
        }
    )
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pilot_io", description="原流程与配对试点的受控本地登记入口（06 单 writer，计算调 05）")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--apply", action="store_true", help="真正落盘；缺省是 dry-run")
    sub = parser.add_subparsers(dest="command", required=True)

    register = sub.add_parser("register", help="登记协议 / 分配 / 诊断策略 / 题包")
    register.add_argument("--kind", required=True, choices=REGISTER_KINDS)
    register.add_argument("--input", required=True, help="本地 JSON 路径（只读命令行显式给出的文件）")

    imp = sub.add_parser("import-events", help="导入 manual_import 渠道的原流程事件")
    imp.add_argument("--events", required=True, help="JSONL 路径")
    imp.add_argument("--protocol", default=None, help="冻结协议 JSON 路径（给了就核版本与哈希）")

    rebuild = sub.add_parser("rebuild", help="按协议 + 原事件重算不可变收据与总结")
    rebuild.add_argument("--protocol-hash", required=True)

    sub.add_parser("show", help="列出本 owner 的事件、收据与总结状态")
    return parser


_HANDLERS: dict[str, Callable[..., int]] = {
    "register": cmd_register,
    "import-events": cmd_import_events,
    "rebuild": cmd_rebuild,
    "show": cmd_show,
}


def main(argv: Sequence[str] | None = None, *, now: datetime | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    ctx = OwnerContext.for_owner(args.owner)
    moment = now or _shanghai_now()
    try:
        return _HANDLERS[args.command](args, ctx, moment)
    except ApiError as exc:
        _emit({"ok": False, "code": exc.code, "message": exc.message, "detail": exc.detail})
        return 2


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    sys.exit(main())
