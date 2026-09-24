"""离线 CLI：freeze / validate / measure / summarize。显式输入、显式输出目录，不碰生产用户态。

    python -m intelligence.eval.product_value freeze    --protocol template.yaml --out frozen.yaml
    python -m intelligence.eval.product_value validate  --events E.jsonl [--protocol P.yaml]
    python -m intelligence.eval.product_value measure   --events E.jsonl --protocol P.yaml --out-dir OUT [--evidence-json R.json]
    python -m intelligence.eval.product_value summarize --events E.jsonl --protocol P.yaml --out-dir OUT \\
        [--evidence-json R.json] [--due-rechecks D.json] [--as-of 2026-10-11]

证据来源二选一：``--evidence-json`` 喂夹具（``{"runs": [{owner_user_id, run_id, status,
error, degrades, artifacts}]}``），或 ``--users-root`` 打开该目录下 ``<owner>/runs`` 的真实
``RunStore``（注意 RunStore 初始化会在该 runs 目录建 sqlite 索引，请对副本运行）。
两者都不给时用空的内存解析器，所有 run 引用记为 missing。

生产保存不在这里：06 的 writer 调用同样的纯函数把收据与总结落到用户态。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from intelligence.eval.product_value.render import render_receipt_markdown, render_summary_markdown
from intelligence.services.product_value.evidence import (
    EvidenceReader,
    InMemoryEvidenceReader,
    RunStoreEvidenceReader,
)
from intelligence.services.product_value.events import load_events_jsonl, prepare_events
from intelligence.services.product_value.measure import measure_pair
from intelligence.services.product_value.protocol import (
    ProtocolError,
    freeze_protocol,
    load_protocol,
    validate_protocol,
)
from intelligence.services.product_value.summarize import summarize


def _dump(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_reader(args: argparse.Namespace) -> EvidenceReader:
    if getattr(args, "evidence_json", None):
        payload = json.loads(Path(args.evidence_json).read_text(encoding="utf-8"))
        return InMemoryEvidenceReader.from_json(payload)
    if getattr(args, "users_root", None):
        users_root = Path(args.users_root)
        from intelligence.services.run_store import RunStore

        def store_for_owner(owner: str) -> RunStore | None:
            runs_dir = users_root / owner / "runs"
            if not runs_dir.is_dir():
                return None
            return RunStore(owner, root=runs_dir)

        return RunStoreEvidenceReader(store_for_owner)
    return InMemoryEvidenceReader()


def _split_pairs(events: Sequence[Mapping[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """按 case_pair_id 分组；没有配对号的事件是参与者 / 试点级事件，附给每一对并单独返回。"""
    by_pair: dict[str, list[dict[str, Any]]] = {}
    cohort: list[dict[str, Any]] = []
    for event in events:
        pair = event.get("case_pair_id") if isinstance(event, Mapping) else None
        if pair:
            by_pair.setdefault(str(pair), []).append(dict(event))
        else:
            cohort.append(dict(event))
    return by_pair, cohort


def cmd_freeze(args: argparse.Namespace) -> int:
    """校验协议模板并写入 protocol_hash；已冻结且哈希不符的协议会被拒绝。"""
    frozen = freeze_protocol(load_protocol(args.protocol))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        out.write_text(yaml.safe_dump(frozen, allow_unicode=True, sort_keys=False), encoding="utf-8")
    else:
        _dump(out, frozen)
    print(json.dumps({"protocol_version": frozen["protocol_version"], "protocol_hash": frozen["protocol_hash"], "out": str(out)}, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    protocol = validate_protocol(load_protocol(args.protocol)) if args.protocol else None
    prepared = prepare_events(load_events_jsonl(args.events), protocol=protocol)
    report = {"events_file": str(args.events), **prepared.accounting()}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not prepared.rejected and not prepared.conflicts else 1


def _measure_all(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    protocol = validate_protocol(load_protocol(args.protocol))
    reader = _build_reader(args)
    raw_events = load_events_jsonl(args.events)
    by_pair, cohort = _split_pairs(raw_events)
    receipts: list[dict[str, Any]] = []
    for pair_id, pair_events in sorted(by_pair.items()):
        if getattr(args, "pair", None) and pair_id != args.pair:
            continue
        receipts.append(measure_pair(pair_events + cohort, protocol, reader, case_pair_id=pair_id))
    return protocol, receipts, raw_events


def _write_receipts(receipts: Sequence[Mapping[str, Any]], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for receipt in receipts:
        stem = f"receipt-{receipt['case_pair_id']}"
        json_path = out_dir / f"{stem}.json"
        _dump(json_path, receipt)
        (out_dir / f"{stem}.md").write_text(render_receipt_markdown(receipt), encoding="utf-8")
        written.append(json_path)
    return written


def cmd_measure(args: argparse.Namespace) -> int:
    _, receipts, _ = _measure_all(args)
    written = _write_receipts(receipts, Path(args.out_dir))
    for receipt, path in zip(receipts, written):
        print(f"{receipt['case_pair_id']}\t{receipt['status']}\t{path}")
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    protocol, receipts, raw_events = _measure_all(args)
    out_dir = Path(args.out_dir)
    _write_receipts(receipts, out_dir)
    assignments = [e for e in raw_events if isinstance(e, Mapping) and e.get("event_type") == "assignment_created"]
    cohort = [e for e in raw_events if isinstance(e, Mapping) and e.get("event_type") != "assignment_created"]
    due = None
    if args.due_rechecks:
        loaded = json.loads(Path(args.due_rechecks).read_text(encoding="utf-8"))
        due = loaded.get("due_rechecks") if isinstance(loaded, Mapping) else loaded
    summary = summarize(receipts, assignments, protocol, cohort_events=cohort, due_rechecks=due, as_of=args.as_of)
    _dump(out_dir / "pilot-summary.json", summary)
    (out_dir / "pilot-summary.md").write_text(render_summary_markdown(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "summary_id": summary["summary_id"],
                "engineering_status": summary["engineering_status"],
                "field_status": summary["field_status"],
                "commercial_status": summary["commercial_status"],
                "synthetic": summary["provenance"]["synthetic"],
                "receipts": {r["case_pair_id"]: r["status"] for r in receipts},
                "out_dir": str(out_dir),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m intelligence.eval.product_value", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze", help="校验协议模板并写入 protocol_hash（采集前冻结）")
    freeze.add_argument("--protocol", required=True, help="协议模板 YAML/JSON")
    freeze.add_argument("--out", required=True, help="冻结后的协议文件（按后缀写 YAML 或 JSON）")
    freeze.set_defaults(func=cmd_freeze)

    validate = sub.add_parser("validate", help="校验事件文件（合同 + 可选协议核对）")
    validate.add_argument("--events", required=True)
    validate.add_argument("--protocol", default=None)
    validate.set_defaults(func=cmd_validate)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--events", required=True, help="ProductValueEvent JSONL")
        p.add_argument("--protocol", required=True, help="冻结协议 YAML/JSON")
        p.add_argument("--out-dir", required=True, help="输出目录（显式，不默认写进仓库）")
        p.add_argument("--evidence-json", default=None, help="夹具 run 证据 JSON")
        p.add_argument("--users-root", default=None, help="真实用户态根（打开 <owner>/runs 的 RunStore）")

    measure = sub.add_parser("measure", help="逐配对生成 MeasurementReceipt")
    add_common(measure)
    measure.add_argument("--pair", default=None, help="只算这一对")
    measure.set_defaults(func=cmd_measure)

    summ = sub.add_parser("summarize", help="生成全部收据并汇总 PilotSummary")
    add_common(summ)
    summ.add_argument("--due-rechecks", default=None, help="到期回检清单 JSON（06 从 01 取得）")
    summ.add_argument("--as-of", default=None, help="截止时点 ISO 日期/时间，缺省用协议 cohort_window.end")
    summ.set_defaults(func=cmd_summarize)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ProtocolError as exc:
        print(f"protocol error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"missing input: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
