#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

WIKI_DIR = Path("/Users/lbq/Desktop/c c/知识库/wiki")
QUEUE_PATH = WIKI_DIR / "raw/baseline-queue/entity-baseline-queue.jsonl"
RAW_DIR = WIKI_DIR / "raw/a-stock-baseline"
SUMMARY_DIR = WIKI_DIR / "raw/baseline-queue"
SCRIPT_DIR = Path(__file__).resolve().parent
FETCH_SCRIPT = SCRIPT_DIR / "fetch_a_stock_baseline.py"
BUILD_SCRIPT = SCRIPT_DIR / "build_a_stock_baseline_update.py"
WRITER_SCRIPT = SCRIPT_DIR / "entity_baseline_writer.py"


def load_queue(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def save_queue(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def safe_filename(name):
    return str(name).replace("/", "_").replace("\\", "_").strip() or "未命名公司"


def run_json(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {"status": "error", "error": result.stderr.strip() or result.stdout.strip()}
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {"status": "error", "error": f"invalid json output: {exc}; output={result.stdout[-500:]}"}


def batch_number():
    numbers = []
    for path in SUMMARY_DIR.glob("batch*"):
        match = re.match(r"batch(\d+)", path.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def merge_payloads(paths, source_name):
    updates = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        updates.extend(data.get("updates", []))
    return {"source_name": source_name, "updates": updates}


def validate_payload(data):
    valid = []
    skipped = []
    for update in data.get("updates", []):
        reasons = []
        if not update.get("main_business"):
            reasons.append("missing main_business")
        if not update.get("products"):
            reasons.append("missing products")
        if not update.get("exposures"):
            reasons.append("missing exposures")
        if reasons:
            skipped.append({"company": update.get("company"), "reason": "; ".join(reasons)})
        else:
            valid.append(update)
    return {"source_name": data.get("source_name"), "updates": valid}, skipped


def write_summary(path, rows, payload, skipped, apply_result=None):
    lines = [f"# Entity Baseline Batch {path.stem}", "", f"- 日期：{date.today().isoformat()}", f"- 候选数：{len(rows)}", f"- 合格 updates：{len(payload.get('updates', []))}", f"- 跳过 updates：{len(skipped)}", "", "## 候选", ""]
    lines.append("| 公司 | 代码 | 状态 | 原因 |")
    lines.append("|---|---:|---|---|")
    for row in rows:
        lines.append(f"| {row.get('company')} | {row.get('code')} | {row.get('status')} | {row.get('reason', '')} |")
    lines.extend(["", "## 跳过", ""])
    if skipped:
        lines.append("| 公司 | 原因 |")
        lines.append("|---|---|")
        for item in skipped:
            lines.append(f"| {item.get('company')} | {item.get('reason')} |")
    else:
        lines.append("无。")
    if apply_result is not None:
        lines.extend(["", "## Apply 结果", "", "```json", json.dumps(apply_result, ensure_ascii=False, indent=2), "```"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default=str(QUEUE_PATH))
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-akshare", action="store_true")
    args = parser.parse_args()
    queue_path = Path(args.queue).expanduser()
    rows = load_queue(queue_path)
    pending = [row for row in rows if row.get("status") == "pending"][: args.batch_size]
    if not pending:
        print(json.dumps({"status": "ok", "message": "no pending rows"}, ensure_ascii=False))
        return
    batch = batch_number()
    payload_paths = []
    for row in pending:
        fetch_cmd = [sys.executable, str(FETCH_SCRIPT), "--company", row["company"], "--code", row["code"], "--out-dir", str(RAW_DIR)]
        if args.include_akshare:
            fetch_cmd.append("--include-akshare")
        fetch_out = run_json(fetch_cmd)
        if fetch_out.get("status") != "ok":
            row["status"] = "failed"
            row["reason"] = fetch_out.get("error", "fetch failed")[:240]
            continue
        raw_file = fetch_out["raw_file"]
        payload_file = RAW_DIR / f"{safe_filename(row['company'])}.update.json"
        build_cmd = [sys.executable, str(BUILD_SCRIPT), "--raw-file", raw_file, "--out", str(payload_file)]
        for concept in row.get("concepts", []) or []:
            build_cmd.extend(["--concept", concept])
        build_out = run_json(build_cmd)
        if build_out.get("status") != "ok":
            row["status"] = "failed"
            row["reason"] = build_out.get("error", "build failed")[:240]
            continue
        row["status"] = "dry_run_ready"
        row["reason"] = "payload_generated"
        payload_paths.append(payload_file)
    data = merge_payloads(payload_paths, f"a-stock baseline {date.today().isoformat()} batch{batch}") if payload_paths else {"source_name": f"a-stock baseline {date.today().isoformat()} batch{batch}", "updates": []}
    valid_payload, skipped = validate_payload(data)
    valid_companies = {item.get("company") for item in valid_payload.get("updates", [])}
    valid_codes = {str(item.get("code") or "").strip() for item in valid_payload.get("updates", []) if str(item.get("code") or "").strip()}
    skipped_companies = {item.get("company") for item in skipped}
    skipped_codes = {str(item.get("code") or "").strip() for item in skipped if str(item.get("code") or "").strip()}
    for row in pending:
        row_code = str(row.get("code") or "").strip()
        if row.get("company") in valid_companies or (row_code and row_code in valid_codes):
            row["status"] = "dry_run_ready"
            row["reason"] = "payload_validated"
        elif row.get("company") in skipped_companies or (row_code and row_code in skipped_codes):
            row["status"] = "skipped"
            match = next((item for item in skipped if item.get("company") == row.get("company") or (row_code and str(item.get("code") or "").strip() == row_code)), {})
            row["reason"] = match.get("reason", "payload_validation_failed")
    batch_payload = RAW_DIR / f"baseline-updates-{date.today().isoformat()}-batch{batch:03d}.json"
    batch_payload.parent.mkdir(parents=True, exist_ok=True)
    batch_payload.write_text(json.dumps(valid_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    apply_result = None
    if args.apply and valid_payload.get("updates"):
        result = subprocess.run([sys.executable, str(WRITER_SCRIPT)], input=json.dumps(valid_payload, ensure_ascii=False), capture_output=True, text=True, check=False)
        try:
            apply_result = json.loads(result.stdout)
        except Exception:
            apply_result = {"status": "error", "stdout": result.stdout[-1000:], "stderr": result.stderr[-1000:], "returncode": result.returncode}
        for row in pending:
            if row.get("status") == "dry_run_ready":
                row["status"] = "applied"
                row["reason"] = "writer_executed"
    summary = SUMMARY_DIR / f"batch{batch:03d}-summary.md"
    write_summary(summary, pending, valid_payload, skipped, apply_result=apply_result)
    save_queue(queue_path, rows)
    print(json.dumps({"status": "ok", "batch": batch, "payload": str(batch_payload), "summary": str(summary), "updates": len(valid_payload.get("updates", [])), "skipped": len(skipped), "applied": bool(args.apply)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
