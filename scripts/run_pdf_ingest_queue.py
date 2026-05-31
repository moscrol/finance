#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PDF_ROOT_DEFAULT = Path("/Users/lbq/Desktop/hbs")
KB_ROOT_DEFAULT = Path("/Users/lbq/Desktop/c c/知识库")
FINANCE_ROOT_DEFAULT = Path("/Users/lbq/Desktop/c c/金融")
SKIP_NAME_TOKENS = ("狙击龙虎榜",)
REQUIRED_FRONTMATTER_FIELDS = ("created", "updated", "revision", "source_quality", "log")
RELATION_FILES = ("entity_exposures.json", "evidence_index.json", "concept_graph.json", "report_contexts.json")
STATE_DEFAULT = KB_ROOT_DEFAULT / "wiki" / "raw" / "pdf-ingest-state.json"
EXTRACTOR_DEFAULT = FINANCE_ROOT_DEFAULT / "scripts" / "extract_hbs_pdf_text.py"
AUTO_WORKER_DEFAULT = FINANCE_ROOT_DEFAULT / "scripts" / "auto_pdf_ingest_worker.py"


@dataclass(frozen=True)
class Candidate:
    pdf: Path
    source: str
    source_date: str


def canon_source(value: str) -> str:
    s = value.strip()
    s = re.sub(r"\(\d+\)$", "", s).strip()
    match = re.search(r"(\d{6})", s)
    if match:
        date = match.group(1)[-4:]
        typ = s[: match.start()] + s[match.end():]
    else:
        match = re.search(r"(\d{4})", s)
        if match:
            date = match.group(1)
            typ = s[: match.start()] + s[match.end():]
        else:
            date = ""
            typ = s
    typ = typ.replace(" ", "").replace("　", "")
    return f"{date}|{typ}"


def source_from_canon(value: str) -> str:
    if "|" not in value:
        return value.replace(" ", "").replace("　", "")
    date, typ = value.split("|", 1)
    return f"{date}{typ}"


def infer_report_type(source: str) -> str:
    if "早知道" in source:
        return "market_news"
    if "脱水" in source and "强势" not in source:
        return "beneficiary_list"
    if "评级日报" in source or "风口研报" in source or "强势" in source:
        return "core_company_or_theme_review"
    if "调研" in source:
        return "ir_research"
    return "unknown"


def suggest_strategy(report_type: str) -> str:
    return {
        "market_news": "observation_only_zero_exposure",
        "beneficiary_list": "existing_entities_graph_only_no_create_missing",
        "core_company_or_theme_review": "create_missing_only_for_core_company_with_concrete_evidence",
        "ir_research": "company_level_facts_can_use_curated_research_or_create_missing",
    }.get(report_type, "manual_judgement_required")


def normalize_source_name(pdf: Path) -> str:
    return pdf.stem.replace(" ", "").replace("　", "")


def infer_source_date(pdf: Path) -> str:
    parent = pdf.parent.name
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", parent):
        return parent
    match = re.search(r"(20\d{2})(\d{2})(\d{2})", pdf.stem)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return ""


def sort_key(pdf: Path) -> tuple[str, str]:
    return (infer_source_date(pdf), str(pdf))


def discover_candidates(root: Path, kb_root: Path, include_existing: bool) -> list[Candidate]:
    source_dir = kb_root / "wiki" / "sources"
    candidates = []
    for pdf in sorted(root.rglob("*.pdf"), key=sort_key):
        if any(token in pdf.name for token in SKIP_NAME_TOKENS):
            continue
        source = normalize_source_name(pdf)
        if not include_existing and (source_dir / f"{source}.md").exists():
            continue
        candidates.append(Candidate(pdf=pdf, source=source, source_date=infer_source_date(pdf)))
    return candidates


def discover_yanbao_candidates(root: Path, kb_root: Path, include_existing: bool) -> list[Candidate]:
    raw_dir = kb_root / "raw"
    source_dir = kb_root / "wiki" / "sources"
    raw_canon = {canon_source(path.stem) for path in raw_dir.glob("*.md")}
    source_canon = {canon_source(path.stem) for path in source_dir.glob("*.md")}
    seen = set()
    candidates = []
    for pdf in sorted(root.rglob("*.pdf")):
        if any(token in pdf.name for token in SKIP_NAME_TOKENS):
            continue
        canon = canon_source(pdf.stem)
        if canon in seen:
            continue
        seen.add(canon)
        if not include_existing and (canon in raw_canon or canon in source_canon):
            continue
        candidates.append(Candidate(pdf=pdf, source=source_from_canon(canon), source_date=infer_source_date(pdf)))
    return candidates


def apply_start_after(candidates: list[Candidate], start_after: str) -> list[Candidate]:
    if not start_after:
        return candidates
    for idx, candidate in enumerate(candidates):
        if start_after in {candidate.source, str(candidate.pdf), candidate.pdf.name}:
            return candidates[idx + 1:]
    return [candidate for candidate in candidates if candidate.source > start_after]


def render_command(template: str, candidate: Candidate, text_path: Path | None = None) -> str:
    return template.format(
        pdf=str(candidate.pdf),
        pdf_q=shlex.quote(str(candidate.pdf)),
        source=candidate.source,
        source_q=shlex.quote(candidate.source),
        date=candidate.source_date,
        date_q=shlex.quote(candidate.source_date),
        text=str(text_path or ""),
        text_q=shlex.quote(str(text_path or "")),
    )


def run_command(command: str, cwd: Path | None) -> tuple[int, str, str]:
    result = subprocess.run(
        command,
        shell=True,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    return result.returncode, result.stdout, result.stderr


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def relation_source_hits(kb_root: Path, source: str) -> dict[str, int]:
    hits = {}
    for name in RELATION_FILES:
        path = kb_root / "wiki" / "relations" / name
        if not path.exists():
            continue
        data = load_json(path)
        text = json.dumps(data, ensure_ascii=False)
        hits[name] = text.count(source) + text.count(f"[[{source}]]")
    return hits


def section_exists(text: str, section: str) -> bool:
    return bool(re.search(rf"^## {re.escape(section)}\s*$", text, re.M))


def frontmatter(text: str) -> str:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    return match.group(1) if match else ""


def parse_source_quality(text: str) -> str:
    fm = frontmatter(text)
    match = re.search(r"^source_quality:\s*['\"]?([^'\"\n]+)['\"]?\s*$", fm, re.M)
    return match.group(1).strip() if match else ""


def source_has_delta_section(kb_root: Path, source: str) -> bool:
    entities_dir = kb_root / "wiki" / "entities"
    for path in entities_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        delta = re.search(r"^## 边际变化\s*\n(.+?)(?=^## |\Z)", text, re.M | re.S)
        if delta and source in delta.group(1):
            return True
    return False


def check_relations_semantics(kb_root: Path, source: str) -> list[str]:
    errors = []
    exposure_path = kb_root / "wiki" / "relations" / "entity_exposures.json"
    evidence_path = kb_root / "wiki" / "relations" / "evidence_index.json"
    exposures = load_json(exposure_path) if exposure_path.exists() else {}
    evidence = load_json(evidence_path) if evidence_path.exists() else {}
    for entity, ent in (exposures.get("entities") or {}).items():
        for concept, exp in (ent.get("concepts") or {}).items():
            sources = [str(x) for x in exp.get("sources") or []]
            if source not in sources and f"[[{source}]]" not in sources:
                continue
            loc = f"entity_exposures.json:{entity}/{concept}"
            if exp.get("source_quality") == "broker_research_high" and exp.get("fact_hardness") == "hard_fact":
                errors.append(f"{loc}: broker_research_high must not be hard_fact")
            if exp.get("update_type") == "graph_only" and exp.get("strength") in {"core", "related"}:
                errors.append(f"{loc}: graph_only must not be strength={exp.get('strength')}")
            if exp.get("fact_hardness") == "hard_fact" and exp.get("source_quality") not in {"official_disclosure", "company_primary"}:
                errors.append(f"{loc}: hard_fact requires official_disclosure/company_primary")
    for item in evidence.get("items") or []:
        value = str(item.get("source") or "")
        if source not in value:
            continue
        loc = f"evidence_index.json:{item.get('target')}/{item.get('concept')}"
        if item.get("source_quality") == "broker_research_high" and item.get("fact_hardness") == "hard_fact":
            errors.append(f"{loc}: broker_research_high must not be hard_fact")
    return errors


def run_quality_gate(candidate: Candidate, kb_root: Path, finance_root: Path, strict_index_log: bool, allow_warnings: bool) -> tuple[bool, list[str], dict]:
    errors = []
    details = {}
    raw_path = kb_root / "raw" / f"{candidate.source}.md"
    source_path = kb_root / "wiki" / "sources" / f"{candidate.source}.md"
    log_path = kb_root / "wiki" / "log.md"
    index_path = kb_root / "wiki" / "index.md"
    lint_path = finance_root / "skills" / "lib" / "pdf_ingest_lint.py"

    if not raw_path.exists() or raw_path.stat().st_size == 0:
        errors.append(f"raw missing or empty: {raw_path}")
    if not source_path.exists():
        errors.append(f"source note missing: {source_path}")
        return False, errors, details

    source_text = source_path.read_text(encoding="utf-8")
    source_quality = parse_source_quality(source_text)
    details["source_quality"] = source_quality
    fm = frontmatter(source_text)
    for field in REQUIRED_FRONTMATTER_FIELDS:
        if not re.search(rf"^{field}:", fm, re.M):
            errors.append(f"source frontmatter missing field: {field}")
    if candidate.source not in source_text and f"raw/{candidate.source}.md" not in source_text:
        errors.append("source note does not reference raw/source name")

    if not log_path.exists() or candidate.source not in log_path.read_text(encoding="utf-8"):
        errors.append("wiki/log.md missing source entry")
    index_text = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    if not index_text:
        errors.append("wiki/index.md missing")
    elif strict_index_log and candidate.source not in index_text:
        errors.append("wiki/index.md missing source/log reference")

    for name in RELATION_FILES:
        path = kb_root / "wiki" / "relations" / name
        if path.exists():
            load_json(path)
    details["json_parse"] = "OK"

    code, stdout, stderr = run_command(f"python3 {shlex.quote(str(lint_path))} {shlex.quote(candidate.source)}", finance_root)
    details["lint_stdout"] = stdout
    details["lint_stderr"] = stderr
    if code != 0:
        errors.append("pdf_ingest_lint.py failed")
    if "ALL CHECKS PASSED" not in stdout:
        if not allow_warnings or "PASSED WITH WARNINGS" not in stdout:
            errors.append("lint did not report ALL CHECKS PASSED")

    has_updated = section_exists(source_text, "已更新实体")
    has_graph = section_exists(source_text, "仅更新图谱")
    has_watchlist = section_exists(source_text, "观察列表")
    hits = relation_source_hits(kb_root, candidate.source)
    details["relation_hits"] = hits
    total_hits = sum(hits.values())
    if has_watchlist and not has_updated and not has_graph and total_hits != 0:
        errors.append(f"observation-only source has relation hits: {hits}")
    if (has_updated or has_graph) and hits.get("entity_exposures.json", 0) == 0:
        errors.append("source note claims entity/graph updates but entity_exposures has no source hit")
    if total_hits and not (has_updated or has_graph or has_watchlist):
        errors.append("relations contain source but source note has no classification section")

    if source_quality in {"market_narrative", "broker_research_high", "broker_research_normal"} and source_has_delta_section(kb_root, candidate.source):
        errors.append("market/broker source appears in entity ## 边际变化")
    errors.extend(check_relations_semantics(kb_root, candidate.source))
    return not errors, errors, details


def append_run_log(path: Path, event: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def candidate_payload(candidate: Candidate) -> dict:
    report_type = infer_report_type(candidate.source)
    return {
        "pdf": str(candidate.pdf),
        "source": candidate.source,
        "source_date": candidate.source_date,
        "report_type": report_type,
        "suggested_strategy": suggest_strategy(report_type),
    }


def write_state(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    json.loads(path.read_text(encoding="utf-8"))


def default_worker_command() -> str:
    return f"python3 {shlex.quote(str(AUTO_WORKER_DEFAULT))} --source {{source_q}} --date {{date_q}} --pdf {{pdf_q}} --text {{text_q}}"


def discover_queue_candidates(args: argparse.Namespace) -> list[Candidate]:
    if args.root.name == "研报":
        return discover_yanbao_candidates(args.root, args.kb_root, args.include_existing)
    return discover_candidates(args.root, args.kb_root, args.include_existing)


def run_worker_and_gate(args: argparse.Namespace, candidate: Candidate, text_path: Path | None = None, extract_payload: dict | None = None) -> tuple[int, dict]:
    started_at = datetime.now().isoformat(timespec="seconds")
    command = render_command(args.worker_command, candidate, text_path)
    print(f"\n=== PROCESS {candidate.source} ===")
    print(f"PDF: {candidate.pdf}")
    if text_path:
        print(f"TEXT: {text_path}")
    code, stdout, stderr = run_command(command, args.worker_cwd)
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    event = {
        "source": candidate.source,
        "pdf": str(candidate.pdf),
        "source_date": candidate.source_date,
        "started_at": started_at,
        "worker_command": command,
        "worker_returncode": code,
    }
    if text_path:
        event["text_path"] = str(text_path)
    if extract_payload:
        event["extract"] = extract_payload
    if code != 0:
        event.update({"status": "worker_failed", "finished_at": datetime.now().isoformat(timespec="seconds")})
        append_run_log(args.run_log, event)
        print(f"STOP: worker failed for {candidate.source}", file=sys.stderr)
        return code, event
    ok, errors, details = run_quality_gate(candidate, args.kb_root, args.finance_root, args.strict_index_log, args.allow_warnings)
    event.update({
        "status": "passed" if ok else "quality_failed",
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "errors": errors,
        "details": {k: v for k, v in details.items() if not k.startswith("lint_")},
    })
    append_run_log(args.run_log, event)
    if not ok:
        print(json.dumps({"source": candidate.source, "errors": errors, "details": event["details"]}, ensure_ascii=False, indent=2), file=sys.stderr)
        print(f"STOP: quality gate failed for {candidate.source}", file=sys.stderr)
        return 1, event
    print(f"PASS: {candidate.source}; moving to next only because all gates passed")
    return 0, event


def handle_next(args: argparse.Namespace) -> int:
    candidates = discover_queue_candidates(args)
    selected = candidates[: max(args.limit, 0)]
    payload = {
        "root": str(args.root),
        "remaining": len(candidates),
        "selected": [candidate_payload(candidate) for candidate in selected],
        "state_path": str(args.state),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if args.write_state:
        write_state(args.state, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def handle_run_next(args: argparse.Namespace) -> int:
    candidates = discover_queue_candidates(args)
    candidates = apply_start_after(candidates, args.start_after)
    if not candidates:
        payload = {
            "root": str(args.root),
            "remaining": 0,
            "selected": [],
            "status": "empty",
            "state_path": str(args.state),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        if args.write_state:
            write_state(args.state, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    candidate = candidates[0]
    text_out = args.text_out_dir / f"{candidate.source}.txt"
    text_out.parent.mkdir(parents=True, exist_ok=True)
    command = ["python3", str(args.extractor), "--pdf", str(candidate.pdf), "--out", str(text_out)]
    result = subprocess.run(command, text=True, capture_output=True)
    extract_payload = {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    payload = {
        "root": str(args.root),
        "remaining": len(candidates),
        "selected": [candidate_payload(candidate)],
        "status": "extracted" if result.returncode == 0 else "extract_failed",
        "text_path": str(text_out),
        "extract_returncode": result.returncode,
        "extract_stdout": result.stdout,
        "extract_stderr": result.stderr,
        "state_path": str(args.state),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if args.extract_only:
        args.worker_command = ""
    if result.returncode == 0 and args.worker_command:
        code, event = run_worker_and_gate(args, candidate, text_out, extract_payload)
        payload.update({
            "status": event.get("status"),
            "worker_returncode": event.get("worker_returncode"),
            "errors": event.get("errors", []),
            "details": event.get("details", {}),
            "updated_at": event.get("finished_at", payload["updated_at"]),
        })
        if args.write_state:
            write_state(args.state, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return code
    if args.write_state:
        write_state(args.state, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return result.returncode


def handle_gate(args: argparse.Namespace) -> int:
    source = args.source
    pdf = args.pdf or Path("")
    candidate = Candidate(pdf=pdf, source=source, source_date=args.source_date)
    ok, errors, details = run_quality_gate(candidate, args.kb_root, args.finance_root, args.strict_index_log, args.allow_warnings)
    payload = {
        "source": source,
        "ok": ok,
        "errors": errors,
        "details": {k: v for k, v in details.items() if not k.startswith("lint_")},
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if args.write_state:
        write_state(args.state, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def handle_state(args: argparse.Namespace) -> int:
    if args.state.exists():
        print(args.state.read_text(encoding="utf-8"), end="")
        return 0
    print(json.dumps({"state_path": str(args.state), "exists": False}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Serial PDF ingest queue orchestrator with per-file quality gates.")
    sub = parser.add_subparsers(dest="cmd")
    next_parser = sub.add_parser("next")
    next_parser.add_argument("--root", type=Path, default=Path("/Users/lbq/Desktop/研报"))
    next_parser.add_argument("--kb-root", type=Path, default=KB_ROOT_DEFAULT)
    next_parser.add_argument("--limit", type=int, default=1)
    next_parser.add_argument("--include-existing", action="store_true")
    next_parser.add_argument("--state", type=Path, default=STATE_DEFAULT)
    next_parser.add_argument("--write-state", action="store_true")
    run_next_parser = sub.add_parser("run-next")
    run_next_parser.add_argument("--root", type=Path, default=Path("/Users/lbq/Desktop/研报"))
    run_next_parser.add_argument("--kb-root", type=Path, default=KB_ROOT_DEFAULT)
    run_next_parser.add_argument("--include-existing", action="store_true")
    run_next_parser.add_argument("--start-after", default="")
    run_next_parser.add_argument("--state", type=Path, default=STATE_DEFAULT)
    run_next_parser.add_argument("--write-state", action="store_true")
    run_next_parser.add_argument("--extractor", type=Path, default=EXTRACTOR_DEFAULT)
    run_next_parser.add_argument("--text-out-dir", type=Path, default=Path("/tmp"))
    run_next_parser.add_argument("--finance-root", type=Path, default=FINANCE_ROOT_DEFAULT)
    run_next_parser.add_argument("--worker-command", default=default_worker_command())
    run_next_parser.add_argument("--extract-only", action="store_true")
    run_next_parser.add_argument("--worker-cwd", type=Path, default=None)
    run_next_parser.add_argument("--strict-index-log", action="store_true")
    run_next_parser.add_argument("--allow-warnings", action="store_true")
    run_next_parser.add_argument("--run-log", type=Path, default=KB_ROOT_DEFAULT / "wiki" / "raw" / "pdf-ingest-queue-runs.jsonl")
    gate_parser = sub.add_parser("gate")
    gate_parser.add_argument("source")
    gate_parser.add_argument("--pdf", type=Path, default=None)
    gate_parser.add_argument("--source-date", default="")
    gate_parser.add_argument("--kb-root", type=Path, default=KB_ROOT_DEFAULT)
    gate_parser.add_argument("--finance-root", type=Path, default=FINANCE_ROOT_DEFAULT)
    gate_parser.add_argument("--strict-index-log", action="store_true")
    gate_parser.add_argument("--allow-warnings", action="store_true")
    gate_parser.add_argument("--state", type=Path, default=STATE_DEFAULT)
    gate_parser.add_argument("--write-state", action="store_true")
    state_parser = sub.add_parser("state")
    state_parser.add_argument("--state", type=Path, default=STATE_DEFAULT)
    parser.add_argument("--root", type=Path, default=PDF_ROOT_DEFAULT)
    parser.add_argument("--kb-root", type=Path, default=KB_ROOT_DEFAULT)
    parser.add_argument("--finance-root", type=Path, default=FINANCE_ROOT_DEFAULT)
    parser.add_argument("--worker-command", default="")
    parser.add_argument("--worker-cwd", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=1, help="Number of PDFs to process. Use 0 for all discovered candidates.")
    parser.add_argument("--start-after", default="")
    parser.add_argument("--include-existing", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--strict-index-log", action="store_true")
    parser.add_argument("--allow-warnings", action="store_true")
    parser.add_argument("--run-log", type=Path, default=KB_ROOT_DEFAULT / "wiki" / "raw" / "pdf-ingest-queue-runs.jsonl")
    args = parser.parse_args()
    if args.cmd == "next":
        return handle_next(args)
    if args.cmd == "run-next":
        return handle_run_next(args)
    if args.cmd == "gate":
        return handle_gate(args)
    if args.cmd == "state":
        return handle_state(args)

    candidates = discover_queue_candidates(args)
    candidates = apply_start_after(candidates, args.start_after)
    selected = candidates if args.limit == 0 else candidates[: max(args.limit, 0)]

    if args.plan_only or not args.worker_command:
        print(json.dumps({
            "root": str(args.root),
            "remaining": len(candidates),
            "selected": [{"pdf": str(c.pdf), "source": c.source, "source_date": c.source_date} for c in selected],
            "worker_required": not bool(args.worker_command),
        }, ensure_ascii=False, indent=2))
        return 0

    for candidate in selected:
        code, _event = run_worker_and_gate(args, candidate)
        if code != 0:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
