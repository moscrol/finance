"""冻结 30 题 live 基线驱动：#152 sidecar + 生产 grounded 车道，不碰 8792。

判分只读 ``finance_answer_rubric``（确定性，无 LLM）。题面一字不改；
``as_of`` 只进机读元数据——``POST /api/runs`` 没有日期字段。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError

from intelligence.eval import live_probe as probe
from intelligence.eval.finance_answer_rubric import score_answer
from intelligence.eval.frozen_question_set import load_frozen_question_set
from intelligence.services.ask_llm_context import LLM_CONTEXT_FILENAME

REQUIRED_ARTIFACTS = ("answer.md", LLM_CONTEXT_FILENAME, "trace.jsonl")
NO_MARKET = "本轮没有连接本地市场数据"
VARIANCE_DOC = "10_knowledge/eval-harness-variance-governance.md"
DEFAULT_OUT = Path.home() / ".finance-runtime" / "frozen-thirty-live-20260818"
DEFAULT_REPO = Path.home() / "finance-workspace-runtime"
DEFAULT_USER = "frozen-thirty-live"

# 盘面/行情/板块通道依赖。知识/方法/估值题不进这个子集。
MARKET_DEPENDENT_IDS = frozenset(
    {
        "rebound-duration",
        "index-rebound-space",
        "weekly-market-cause",
        "current-mainline",
        "A1-market-overview",
        "A4-dual-red",
        "A5-limit-heat",
        "A6-limit-advance-ladder",
        "A8-market-stage",
        "C2-non-trading-day",
        "C1-future-date-no-data",
        "sci-tech-support",
        "A2-next-day-call",
        "C6-strict-definition",
        "A7-mainline",
        "B4-fermentation-trace",
        "B7-volume-sentiment-evolution",
        "B5-cross-table-intersection",
        "C7-temporal-leakage",
        "A10-new-high-structure",
        "A9-sentiment-contradiction",
    }
)

_GROUNDED_OFF = "export WORKBENCH_GROUNDED_PRESENTER=0"
_GROUNDED_ON = "export WORKBENCH_GROUNDED_PRESENTER=1"


def grounded_sidecar_script(spec: probe.SidecarSpec) -> str:
    script = probe.sidecar_zsh(spec)
    if _GROUNDED_OFF not in script:
        raise probe.ProbeBlocked("live_probe sidecar_zsh no longer pins grounded=0")
    rewritten = script.replace(_GROUNDED_OFF, _GROUNDED_ON, 1)
    head, _, _tail = rewritten.partition("grep")
    if "--port 8792" in rewritten and "--port 8792" in head:
        raise probe.ProbeBlocked("refusing sidecar script that execs production 8792")
    return rewritten


def start_grounded_sidecar(
    spec: probe.SidecarSpec, *, log_path: Path, timeout: float = 90
) -> int:
    probe.assert_safe_to_start(
        lock_path=probe.LIVE_LOCK_PATH,
        port=spec.port,
        is_busy=probe.port_is_listening,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    script = grounded_sidecar_script(spec)
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            ["zsh", "-c", script],
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    try:
        probe.wait_for_health(f"http://127.0.0.1:{spec.port}", timeout=timeout)
    except Exception:
        probe.stop_sidecar(process.pid, spec.port)
        raise
    return process.pid


def classify_attempt(
    *,
    error: str | None,
    status: str | None,
    artifacts: dict[str, str],
) -> str:
    if error:
        return "infra_fail"
    if status != "completed":
        return "infra_fail"
    if any(name not in artifacts for name in REQUIRED_ARTIFACTS):
        return "infra_fail"
    return "scored"


def score_case(
    question: str,
    answer: str,
    *,
    question_type: str | None = None,
) -> dict[str, Any]:
    scored = score_answer(question, answer, question_type=question_type)
    payload = scored.to_dict() if hasattr(scored, "to_dict") else {
        "question": scored.question,
        "total_score": scored.total_score,
        "max_score": scored.max_score,
        "grade": scored.grade,
        "failures": list(scored.failures),
        "question_type": scored.question_type,
    }
    payload["judge"] = "finance_answer_rubric"
    payload["judge_kind"] = "deterministic"
    payload["quality"] = (
        "quality_fail" if payload.get("failures") else "quality_pass"
    )
    return payload


def build_measurement(
    *,
    cases: list[dict[str, Any]],
    sidecar_revision: str,
    answer_model: str | None,
) -> dict[str, Any]:
    scored = [row for row in cases if row.get("classification") == "scored"]
    infra = [row for row in cases if row.get("classification") == "infra_fail"]
    return {
        "schema_version": "frozen-thirty-live-baseline-1.0",
        "purpose": "answer-quality-regression-anchor",
        "question_set": "intelligence/eval/fixtures/frozen-thirty-2026-08-16.questions.json",
        "sidecar_revision": sidecar_revision,
        "grounded_presenter": "1",
        "as_of_injection": "none",
        "answer_model": answer_model,
        "judge": {
            "name": "finance_answer_rubric",
            "kind": "deterministic",
            "acceptance_axes": "not_applied_sidecar_run_shape",
        },
        "heterogeneous_scoring": True,
        "heterogeneous_note": (
            "答案走 sidecar 生产合成模型；判分是仓内确定性 rubric，无 LLM 判分，"
            "故无同源 confound。"
        ),
        "variance_governance": VARIANCE_DOC,
        "single_run_limit": True,
        "market_dependent_ids": sorted(MARKET_DEPENDENT_IDS),
        "counts": {
            "total": len(cases),
            "scored": len(scored),
            "infra_fail": len(infra),
            "quality_pass": sum(1 for row in scored if row.get("quality") == "quality_pass"),
            "quality_fail": sum(1 for row in scored if row.get("quality") == "quality_fail"),
        },
        "cases": cases,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def extract_run_meta(dest: Path) -> dict[str, Any]:
    run = _read_json(dest / "run.json")
    summary = _read_json(dest / "summary.json")
    report = _read_json(dest / "report.json")
    context = _read_json(dest / LLM_CONTEXT_FILENAME)
    answer = (dest / "answer.md").read_text(encoding="utf-8") if (dest / "answer.md").is_file() else ""
    telemetry = context.get("llm_stream_telemetry") or {}
    tokens = telemetry.get("completion_tokens") or telemetry.get("output_tokens")
    usage = context.get("usage") or report.get("usage") or {}
    model = (
        report.get("model")
        or (report.get("runtime") or {}).get("model")
        or context.get("llm_model")
        or context.get("llm_provider")
    )
    degrades = [str(item) for item in (run.get("degrades") or [])]
    blob = "\n".join([answer, json.dumps(degrades, ensure_ascii=False)])
    return {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "source_date": run.get("source_date"),
        "question_type": summary.get("question_type"),
        "answer_model": model,
        "tokens": tokens if tokens is not None else usage.get("completion_tokens"),
        "input_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
        "output_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
        "no_local_market": NO_MARKET in blob,
        "frozen_0715": "2026-07-15" in blob and NO_MARKET in blob,
        "degrades": degrades[:12],
        "answer_chars": len(answer),
        "answer": answer,
    }


def case_timeout(case: dict[str, Any]) -> float:
    raw = float(case.get("timeout") or 180.0)
    return max(300.0, min(420.0, raw * 2.0))


def run_one_case(
    *,
    base_url: str,
    users_dir: Path,
    user: str,
    case: dict[str, Any],
    dest: Path,
    timeout: float,
) -> dict[str, Any]:
    question = str(case["question"])
    started = time.monotonic()
    error: str | None = None
    status: str | None = None
    run_id = ""
    artifacts: dict[str, str] = {}
    try:
        run_id = probe.post_ask(base_url, question=question, user=user)
        status_payload = probe.wait_for_run(
            base_url, run_id, user=user, timeout=timeout
        )
        status = str(status_payload.get("status") or "")
        run_dir = probe.run_dir_for(users_dir, user, run_id)
        artifacts = probe.copy_run_artifacts(run_dir, dest)
    except (probe.ProbeBlocked, URLError, TimeoutError, OSError) as exc:
        error = str(exc)
    elapsed = round(time.monotonic() - started, 1)
    classification = classify_attempt(error=error, status=status, artifacts=artifacts)
    meta = extract_run_meta(dest) if dest.exists() else {}
    rubric: dict[str, Any] | None = None
    quality = None
    if classification == "scored":
        rubric = score_case(
            question,
            str(meta.get("answer") or ""),
            question_type=meta.get("question_type")
            if isinstance(meta.get("question_type"), str)
            else None,
        )
        quality = rubric["quality"]
    row = {
        "id": case["id"],
        "question": question,
        "as_of": case.get("as_of"),
        "profile": case.get("profile"),
        "market_dependent": case["id"] in MARKET_DEPENDENT_IDS,
        "run_id": run_id or meta.get("run_id"),
        "classification": classification,
        "quality": quality,
        "error": error,
        "elapsed_seconds": elapsed,
        "timeout_seconds": timeout,
        "artifacts": artifacts,
        "source_date": meta.get("source_date"),
        "answer_model": meta.get("answer_model"),
        "tokens": meta.get("tokens"),
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "no_local_market": meta.get("no_local_market"),
        "frozen_0715": meta.get("frozen_0715"),
        "answer_chars": meta.get("answer_chars"),
        "rubric": rubric,
        "degrades": meta.get("degrades") or [],
    }
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "case.json").write_text(
        json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return row


def _sidecar_revision(repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    sha = completed.stdout.strip()
    return sha if completed.returncode == 0 and sha else "unknown"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_suite(
    *,
    cases: list[dict[str, Any]],
    out_dir: Path,
    repo_root: Path,
    launcher: Path,
    python: Path,
    user: str,
    keep_sidecar: bool,
    attach: str = "",
) -> dict[str, Any]:
    users_dir = out_dir / "users"
    pid: int | None = None
    port: int | None = None
    if attach:
        base_url = attach.rstrip("/")
        probe.wait_for_health(base_url, timeout=15)
        meta = _read_json(out_dir / "sidecar.json")
        port = int(meta["port"]) if meta.get("port") is not None else None
    else:
        spec = probe.SidecarSpec(
            port=probe.choose_port(preferred=8796, is_busy=probe.port_is_listening),
            repo_root=repo_root,
            python=python,
            launcher=launcher,
            users_dir=users_dir,
            user=user,
        )
        pid = start_grounded_sidecar(spec, log_path=out_dir / "sidecar.err.log")
        port = spec.port
        _write_json(
            out_dir / "sidecar.json",
            {"pid": pid, "port": spec.port, "repo_root": str(repo_root), "grounded": "1"},
        )
        base_url = f"http://127.0.0.1:{spec.port}"
    rows: list[dict[str, Any]] = []
    try:
        for case in cases:
            dest = out_dir / "cases" / str(case["id"])
            existing = dest / "case.json"
            if existing.is_file():
                previous = _read_json(existing)
                if previous.get("classification") == "scored":
                    rows.append(previous)
                    continue
            timeout = case_timeout(case)
            row = run_one_case(
                base_url=base_url,
                users_dir=users_dir,
                user=user,
                case=case,
                dest=dest,
                timeout=timeout,
            )
            if row["classification"] == "infra_fail":
                retry_dest = out_dir / "cases" / f"{case['id']}__retry"
                retried = run_one_case(
                    base_url=base_url,
                    users_dir=users_dir,
                    user=user,
                    case=case,
                    dest=retry_dest,
                    timeout=timeout,
                )
                retried["retried_from"] = row
                retried["infra_retry"] = True
                row = retried
            rows.append(row)
            _write_json(out_dir / "progress.json", {"done": len(rows), "total": len(cases), "last": row["id"]})
    finally:
        if pid is not None and port is not None and not keep_sidecar:
            probe.stop_sidecar(pid, port)
    models = [str(row.get("answer_model")) for row in rows if row.get("answer_model")]
    answer_model = models[0] if models else None
    measurement = build_measurement(
        cases=rows,
        sidecar_revision=_sidecar_revision(repo_root),
        answer_model=answer_model,
    )
    measurement["generated_at"] = datetime.now(timezone.utc).isoformat()
    measurement["out_dir"] = str(out_dir)
    measurement["base_url"] = base_url
    _write_json(out_dir / "measurement.json", measurement)
    return measurement


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="冻结 30 题 live 基线（sidecar，不碰 8792）")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--launcher", type=Path, default=probe.DEFAULT_LAUNCHER)
    parser.add_argument("--python", type=Path, default=None)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--keep-sidecar", action="store_true")
    parser.add_argument("--attach", default="", help="existing sidecar URL, e.g. http://127.0.0.1:8796")
    args = parser.parse_args(argv)

    loaded = load_frozen_question_set()
    cases = list(loaded["cases"])
    if args.only:
        wanted = {item.strip() for item in args.only.split(",") if item.strip()}
        cases = [case for case in cases if case["id"] in wanted]
        missing = wanted - {case["id"] for case in cases}
        if missing:
            raise SystemExit(f"unknown case ids: {sorted(missing)}")
    repo_root = args.repo_root.expanduser().resolve()
    python = args.python or probe._resolve_python(repo_root)
    measurement = run_suite(
        cases=cases,
        out_dir=args.out_dir.expanduser().resolve(),
        repo_root=repo_root,
        launcher=args.launcher.expanduser().resolve(),
        python=python,
        user=args.user,
        keep_sidecar=args.keep_sidecar,
        attach=args.attach,
    )
    print(json.dumps(measurement["counts"], ensure_ascii=False, indent=2))
    print("measurement", args.out_dir / "measurement.json")
    return 0 if measurement["counts"]["infra_fail"] < measurement["counts"]["total"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
