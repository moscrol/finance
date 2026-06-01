#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FINANCE_ROOT = SCRIPT_DIR.parents[2]
WIKI_DIR = Path("/Users/lbq/Desktop/c c/知识库/wiki")
QUEUE_PATH = WIKI_DIR / "raw/baseline-queue/entity-baseline-queue.jsonl"
RUNNER_SCRIPT = SCRIPT_DIR / "run_entity_baseline_queue.py"
RUN_LOG = WIKI_DIR / "raw/baseline-queue/baseline-next-runs.jsonl"
STATE_PATH = WIKI_DIR / "raw/baseline-queue/baseline-next-state.json"
BAD_PRODUCT_TOKENS = {"研发", "开发", "生产", "销售", "制造", "服务", "经营", "业务", "产品", "设计"}
BAD_PRODUCT_SUFFIXES = ("的研发", "的开发", "的生产", "的销售", "的制造", "和销售", "及销售", "、销售")


def load_queue(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pending_rows(path, limit):
    return [row for row in load_queue(path) if row.get("status") == "pending"][:limit]


def load_payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_batch(args):
    cmd = [sys.executable, str(RUNNER_SCRIPT), "--batch-size", str(args.batch_size)]
    if args.include_akshare:
        cmd.append("--include-akshare")
    result = subprocess.run(cmd, cwd=str(FINANCE_ROOT), capture_output=True, text=True, check=False)
    event = {
        "cmd": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    if result.returncode != 0:
        event["status"] = "runner_failed"
        return event
    try:
        event.update(json.loads(result.stdout.strip().splitlines()[-1]))
    except Exception as exc:
        event["status"] = "runner_output_invalid"
        event["error"] = str(exc)
    return event


def validate_with_writer(payload_path):
    sys.path.insert(0, str(SCRIPT_DIR))
    import entity_baseline_writer as writer

    data = load_payload(payload_path)
    ok = []
    bad = []
    for update in data.get("updates", []):
        try:
            writer.validate_update(update, data.get("source_name", ""))
            ok.append(update.get("company", ""))
        except Exception as exc:
            bad.append({"company": update.get("company", ""), "error": str(exc)})
    return {"ok": ok, "bad": bad}


def quality_gate(payload_path):
    data = load_payload(payload_path)
    issues = []
    summaries = []
    for update in data.get("updates", []):
        company = update.get("company", "")
        products = [str(item).strip() for item in update.get("products", []) or [] if str(item).strip()]
        exposures = update.get("exposures", []) or []
        concepts = update.get("concepts", []) or []
        if not products:
            issues.append({"company": company, "issue": "missing_products"})
        for product in products:
            if product in BAD_PRODUCT_TOKENS or product.endswith(BAD_PRODUCT_SUFFIXES):
                issues.append({"company": company, "issue": "bad_product", "value": product})
        if not exposures:
            issues.append({"company": company, "issue": "missing_exposures"})
        for exposure in exposures:
            if exposure.get("strength") == "core":
                issues.append({"company": company, "issue": "unexpected_core_strength", "concept": exposure.get("concept")})
            if exposure.get("confidence") == "high":
                issues.append({"company": company, "issue": "unexpected_high_confidence", "concept": exposure.get("concept")})
        summaries.append({
            "company": company,
            "products": products[:6],
            "concepts": concepts,
            "exposures": [f"{e.get('concept')}({e.get('strength')}/{e.get('confidence')})" for e in exposures],
        })
    return {"issues": issues, "summaries": summaries}


def append_run_log(path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def write_state(path, event):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_next(args):
    before = pending_rows(args.queue, args.batch_size)
    event = run_batch(args)
    event["selected_before"] = before
    event["finished_at"] = datetime.now().isoformat(timespec="seconds")
    if event.get("status") != "ok" or not event.get("payload"):
        event.setdefault("status", "failed")
        append_run_log(args.run_log, event)
        write_state(args.state, event)
        print(json.dumps(event, ensure_ascii=False, indent=2))
        return 1
    writer_result = validate_with_writer(event["payload"])
    quality = quality_gate(event["payload"])
    event["writer_validation"] = writer_result
    event["quality_gate"] = quality
    event["status"] = "passed" if not writer_result["bad"] and not quality["issues"] else "gate_failed"
    event["next_pending"] = pending_rows(args.queue, args.batch_size)
    append_run_log(args.run_log, event)
    write_state(args.state, event)
    print(json.dumps({
        "status": event["status"],
        "batch": event.get("batch"),
        "updates": event.get("updates"),
        "skipped": event.get("skipped"),
        "selected": [(r.get("company"), r.get("code")) for r in before],
        "writer_bad": writer_result["bad"],
        "quality_issues": quality["issues"],
        "summary": quality["summaries"],
        "payload": event.get("payload"),
        "summary_file": event.get("summary"),
    }, ensure_ascii=False, indent=2))
    return 0 if event["status"] == "passed" else 1


def run_loop(args):
    results = []
    for _ in range(args.max_batches):
        if not pending_rows(args.queue, args.batch_size):
            break
        code = run_next(args)
        state = json.loads(args.state.read_text(encoding="utf-8")) if args.state.exists() else {"status": "missing_state"}
        results.append({"batch": state.get("batch"), "status": state.get("status"), "updates": state.get("updates"), "skipped": state.get("skipped")})
        if code != 0:
            break
    print(json.dumps({"status": "done", "results": results}, ensure_ascii=False, indent=2))
    return 0 if all(item.get("status") == "passed" for item in results) else 1


def main():
    parser = argparse.ArgumentParser(description="Serial baseline next runner with per-batch gates.")
    sub = parser.add_subparsers(dest="cmd")
    next_parser = sub.add_parser("next")
    next_parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    next_parser.add_argument("--batch-size", type=int, default=5)
    run_next_parser = sub.add_parser("run-next")
    loop_parser = sub.add_parser("loop")
    for p in (run_next_parser, loop_parser, parser):
        p.add_argument("--queue", type=Path, default=QUEUE_PATH)
        p.add_argument("--batch-size", type=int, default=5)
        p.add_argument("--include-akshare", action=argparse.BooleanOptionalAction, default=True)
        p.add_argument("--run-log", type=Path, default=RUN_LOG)
        p.add_argument("--state", type=Path, default=STATE_PATH)
    loop_parser.add_argument("--max-batches", type=int, default=3)
    parser.add_argument("--max-batches", type=int, default=3)
    args = parser.parse_args()
    if args.cmd == "next":
        rows = pending_rows(args.queue, args.batch_size)
        print(json.dumps({"pending": len(load_queue(args.queue)), "selected": rows}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "run-next":
        return run_next(args)
    return run_loop(args)


if __name__ == "__main__":
    raise SystemExit(main())
