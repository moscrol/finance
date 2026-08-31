#!/usr/bin/env python3
"""预热后对 #19 同一 6 题打一次 hybrid，报 load / freshness / encode / search / 合计。

工单 ``docs/superpowers/specs/2026-08-31-wiki-hybrid-25s-workorder.md``。
分段来自 worker 挂钩（``RAG_PROFILE_PATH``）；合计是 ``kb_rag.retrieve`` 墙钟。
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from intelligence.paths import default_paths  # noqa: E402
from intelligence.services import kb_rag  # noqa: E402

from run_wiki_aperture_ablation import default_questions, latest_as_of  # noqa: E402

LEDGER_ID = "R-20260831-02"


def _env() -> None:
    os.environ.setdefault("RAG_WORKER_ENABLED", "1")
    os.environ.setdefault("RAG_WORKER_PREWARM_TIMEOUT", "360")
    os.environ["ASK_EVIDENCE_JUDGE"] = "off"
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.pop("RAG_INCLUDE_RAW", None)
    os.environ.pop("ASK_WIKI_APERTURES", None)
    os.environ.pop("ASK_WIKI_TOTAL_SECONDS", None)


def _read_phases(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {"load": 0.0, "freshness": 0.0, "encode": 0.0, "search": 0.0}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: float(raw.get(key) or 0.0)
        for key in ("load", "freshness", "encode", "search")
    }


def _summarize(rows: list[dict]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key in ("load", "freshness", "encode", "search", "total"):
        values = [float(row[key]) for row in rows]
        out[key] = {
            "p50": round(statistics.median(values), 3),
            "p95": round(sorted(values)[max(0, int(round(0.95 * (len(values) - 1))))], 3),
            "mean": round(statistics.mean(values), 3),
            "max": round(max(values), 3),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="baseline", help="baseline / after")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    _env()
    paths = default_paths()
    as_of = latest_as_of(paths.market_exports)
    questions = default_questions(as_of)
    wiki = str(paths.knowledge_wiki)
    profile_path = Path("/tmp/wiki-hybrid-25s-phases.json")
    os.environ["RAG_PROFILE_PATH"] = str(profile_path)
    if profile_path.exists():
        profile_path.unlink()

    print(f"[profile] label={args.label} as_of={as_of} prewarm…", flush=True)
    t0 = time.perf_counter()
    status = kb_rag.prewarm(wiki, timeout=360)
    prewarm_s = time.perf_counter() - t0
    print(f"[profile] prewarm {prewarm_s:.1f}s status={status}", flush=True)

    rows: list[dict] = []
    for q in questions:
        if profile_path.exists():
            profile_path.unlink()
        started = time.perf_counter()
        result = kb_rag.retrieve(
            q.text,
            wiki,
            mode="hybrid",
            require_fresh=True,
            timeout=90,
        )
        total = time.perf_counter() - started
        phases = _read_phases(profile_path)
        freshness = ""
        if result.hits:
            freshness = str(getattr(result.hits[0], "index_freshness", "") or "")
        row = {
            "id": q.case_id,
            "query": q.text,
            "ok": bool(result.ok),
            "n_hits": len(result.hits),
            "warning": result.warning or "",
            "index_freshness": freshness,
            "load": round(phases["load"], 3),
            "freshness": round(phases["freshness"], 3),
            "encode": round(phases["encode"], 3),
            "search": round(phases["search"], 3),
            "total": round(total, 3),
            "retrieve_latency_ms": int(getattr(result.telemetry, "latency_ms", 0) or 0),
        }
        rows.append(row)
        print(
            f"[profile] {q.case_id} ok={row['ok']} hits={row['n_hits']} "
            f"load={row['load']:.2f} freshness={row['freshness']:.2f} "
            f"encode={row['encode']:.2f} search={row['search']:.2f} "
            f"total={row['total']:.2f}",
            flush=True,
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "ledger_id": LEDGER_ID,
        "label": args.label,
        "as_of": as_of,
        "prewarm_s": round(prewarm_s, 3),
        "mode": "hybrid",
        "require_fresh": True,
        "index_dir": str(paths.vector_index_dir),
        "questions": rows,
        "summary": _summarize(rows),
    }
    out = Path(args.out) if args.out else (
        REPO / "intelligence" / "eval" / "runs" / f"{stamp}-wiki-hybrid-25s-{args.label}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[profile] wrote {out}", flush=True)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
