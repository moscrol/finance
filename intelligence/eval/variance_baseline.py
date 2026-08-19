"""同 revision、同题复跑的翻转率基线（loop 鲁棒性 W7）。

失败形状：单次探针 ``degrade_count=1`` 被当成产品回归。判官 transient 与
provider 延迟都能翻 N=1 结果。A/B 没有方差底就没有显著性。

翻转率只许在「输入相同且被测代码相同」的重复上算（见
``eval-harness-variance-governance``）。跨一次修复的两次运行测到的是
「修复效果 + 噪声」，两个都读不出来。

判据分层：``primary_outcome``（内容/协议终局）与 ``judge_unavailable`` 分列，
不把所有断言压成一个 pass/fail。确定性字段，不上 LLM 判官。
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO = Path(__file__).resolve().parents[2]
RUNS_DIR = REPO / "intelligence" / "eval" / "runs"
CASES_PATH = REPO / "intelligence" / "eval" / "cases" / "acceptance_cases.json"
SCHEMA = "eval_variance_baseline.v1"

# qc28 默认子集：三档各一题，live 成本可控。全量用 --questions 或 --all-qc28。
QC28_DEFAULT_SUBSET: tuple[str, ...] = (
    "A1-market-overview",
    "B1-theme-photoresist",
    "C1-future-date-no-data",
)

# W2 落地前：用现有字段把判官不可用单列。W2 会换成显式 degrade 分类。
JUDGE_UNAVAILABLE_STATUSES = frozenset(
    {
        "unavailable",
        "timeout",
        "none",
        "not_applicable",
    }
)

FLIP_RATE_FORMULA = (
    "per_question_flip_rate = count(primary_outcome != mode) / N; "
    "baseline_flip_rate = mean(per_question_flip_rate); "
    "mode = most frequent primary_outcome, ties broken by lexicographically smallest label; "
    "judge_unavailable_rate is mean(count(judge_unavailable)/N) and is NOT folded into "
    "content quality or into the A/B pass/fail call."
)

AB_RULE = (
    "观测差异小于基线翻转率，不得下回归/改善结论。"
    "judge_unavailable 类 degrade 单列，不计入内容质量。"
)


def _rate(value: float) -> float:
    return round(float(value), 6)


def utc_stamp(now: datetime | None = None) -> str:
    clock = now if now is not None else datetime.now(timezone.utc)
    return clock.strftime("%Y%m%dT%H%M%SZ")


def is_judge_unavailable(judge_status: Any) -> bool:
    """W2 前的桶：``judge_status in {unavailable, None}`` 或 timeout。"""
    if judge_status is None:
        return True
    text = str(judge_status).strip().lower()
    return text in JUDGE_UNAVAILABLE_STATUSES or text == ""


def mode_of(values: Sequence[str]) -> str:
    if not values:
        raise ValueError("cannot take mode of empty outcomes")
    counts = Counter(values)
    top = max(counts.values())
    return sorted(label for label, n in counts.items() if n == top)[0]


def per_question_flip_rate(outcomes: Sequence[str]) -> float:
    if not outcomes:
        raise ValueError("no repeats")
    mode = mode_of(outcomes)
    return sum(1 for item in outcomes if item != mode) / len(outcomes)


def ab_decision(observed_delta: float, baseline_flip_rate: float) -> str:
    """A/B 方差门：差异小于基线翻转率则不得下结论。

    Returns:
        ``no_call`` — 不得写回归/改善；``callable`` — 差异达到噪声底之上。
    """
    if abs(float(observed_delta)) < float(baseline_flip_rate):
        return "no_call"
    return "callable"


def primary_outcome_from_fields(
    *,
    verified_status: Any = None,
    terminal_outcome: Any = None,
    status: Any = None,
    degrades: Any = None,
) -> str:
    """优先 ``verified_status``，否则 smoke 口径的 ``terminal_outcome``。"""
    if verified_status not in (None, ""):
        return str(verified_status)
    if terminal_outcome not in (None, ""):
        return str(terminal_outcome)
    degrade_list = degrades if isinstance(degrades, list) else []
    run_status = str(status or "unknown")
    if run_status == "completed" and degrade_list:
        return "degraded"
    return run_status


def normalize_repeat(raw: Mapping[str, Any], *, default_qid: str = "") -> dict[str, Any]:
    question_id = str(
        raw.get("question_id") or raw.get("case_id") or default_qid or ""
    )
    if "judge_status" in raw:
        judge_status = raw.get("judge_status")
    elif "semantic_status" in raw:
        judge_status = raw.get("semantic_status")
    else:
        judge_status = None
    primary = primary_outcome_from_fields(
        verified_status=raw.get("verified_status"),
        terminal_outcome=raw.get("terminal_outcome") or raw.get("primary_outcome"),
        status=raw.get("status") or raw.get("run_status"),
        degrades=raw.get("degrades"),
    )
    unavailable = is_judge_unavailable(judge_status)
    return {
        "question_id": question_id,
        "primary_outcome": primary,
        "judge_status": judge_status,
        "judge_unavailable": unavailable,
        "verified_status": raw.get("verified_status"),
        "terminal_outcome": raw.get("terminal_outcome"),
        "run_id": raw.get("run_id"),
        "repeat_index": raw.get("repeat_index"),
    }


def extract_from_run_dir(run_dir: Path) -> dict[str, Any]:
    """从 live_probe / workbench run 目录抽一条 repeat（只读现有字段）。"""
    run = _read_json_object(run_dir / "run.json")
    episode = _read_json_object(run_dir / "continuous-episode.json")
    report = _read_json_object(run_dir / "report.json")
    smoke = _read_json_object(run_dir / "smoke.json")

    verified = None
    judge_status: Any = None
    if episode:
        structural = episode.get("structural_verifier") or episode.get("verifier")
        if isinstance(structural, dict):
            verified = structural.get("verified_status")
        semantic = episode.get("semantic_verifier")
        if isinstance(semantic, dict):
            judge_status = semantic.get("judge_status")
        metrics = episode.get("metrics")
        if judge_status is None and isinstance(metrics, dict):
            judge_status = metrics.get("semantic_status") or metrics.get("judge_status")

    if smoke:
        return normalize_repeat(
            {
                "question_id": smoke.get("question_id") or run_dir.name,
                "verified_status": verified,
                "terminal_outcome": smoke.get("terminal_outcome"),
                "status": smoke.get("run_status") or run.get("status"),
                "degrades": run.get("degrades") or [],
                "judge_status": judge_status,
                "run_id": smoke.get("run_id") or run.get("run_id") or run_dir.name,
            }
        )

    degrades = run.get("degrades") if isinstance(run.get("degrades"), list) else []
    question_id = str(
        run.get("case_id")
        or report.get("case_id")
        or run.get("slug")
        or run_dir.name
    )
    return normalize_repeat(
        {
            "question_id": question_id,
            "verified_status": verified,
            "status": run.get("status"),
            "degrades": degrades,
            "judge_status": judge_status,
            "run_id": run.get("run_id") or run_dir.name,
        }
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_replay(path: Path) -> dict[str, Any]:
    """从夹具 JSON 或目录加载 repeats。不碰网络。"""
    if path.is_file():
        payload = _read_json(path)
        if not isinstance(payload, dict):
            raise ValueError(f"replay fixture must be an object: {path}")
        return _normalize_fixture(payload, source=str(path))
    if not path.is_dir():
        raise FileNotFoundError(path)

    bundled = path / "repeats.json"
    if bundled.is_file():
        payload = _read_json(bundled)
        if not isinstance(payload, dict):
            raise ValueError(f"replay fixture must be an object: {bundled}")
        return _normalize_fixture(payload, source=str(bundled))

    files = sorted(
        item
        for item in path.glob("*.json")
        if item.is_file() and not item.name.startswith(".")
    )
    if not files:
        run_dirs = sorted(item for item in path.iterdir() if item.is_dir())
        if not run_dirs:
            raise ValueError(f"no JSON or run dirs under {path}")
        repeats = [extract_from_run_dir(item) for item in run_dirs]
        return _fixture_from_repeat_rows(repeats, source=str(path), live=False)

    first = _read_json(files[0])
    if isinstance(first, dict) and (
        "questions" in first or first.get("schema") == SCHEMA
    ):
        if len(files) != 1:
            raise ValueError(
                f"{path} has multiple fixture JSON files; pass one file to --replay"
            )
        return _normalize_fixture(first, source=str(files[0]))

    # 每个文件 = 一次同题全量复跑（acceptance run 形态：cases[].turns[]）。
    grouped: dict[str, list[dict[str, Any]]] = {}
    revs: list[str] = []
    for file_path in files:
        payload = _read_json(file_path)
        if not isinstance(payload, dict):
            continue
        rev = str(payload.get("rev") or payload.get("revision") or "")
        if rev:
            revs.append(rev)
        for row in _iter_acceptance_repeats(payload, source=file_path.name):
            grouped.setdefault(row["question_id"], []).append(row)
    if not grouped:
        raise ValueError(f"no usable repeats under {path}")
    unique_revs = sorted(set(revs))
    if len(unique_revs) > 1:
        raise ValueError(
            "replay directory mixes revisions "
            f"{unique_revs}; flip-rate is only defined on a clean same-rev set"
        )
    questions = [
        {"question_id": qid, "repeats": rows} for qid, rows in sorted(grouped.items())
    ]
    return {
        "schema": SCHEMA,
        "live": False,
        "rev": unique_revs[0] if unique_revs else "",
        "source": str(path),
        "questions": questions,
    }


def _iter_acceptance_repeats(
    payload: Mapping[str, Any], *, source: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in payload.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        qid = str(case.get("case_id") or case.get("id") or "")
        turns = case.get("turns") or []
        turn = turns[-1] if isinstance(turns, list) and turns else case
        if not isinstance(turn, Mapping):
            continue
        row = normalize_repeat(turn, default_qid=qid)
        row["question_id"] = qid or row["question_id"]
        row["source"] = source
        if row["question_id"]:
            rows.append(row)
    if rows:
        return rows
    for item in payload.get("repeats") or []:
        if isinstance(item, Mapping):
            rows.append(normalize_repeat(item))
    return rows


def _normalize_fixture(payload: Mapping[str, Any], *, source: str) -> dict[str, Any]:
    questions_raw = payload.get("questions")
    questions: list[dict[str, Any]] = []
    if isinstance(questions_raw, list):
        for item in questions_raw:
            if not isinstance(item, Mapping):
                continue
            qid = str(item.get("question_id") or item.get("id") or "")
            repeats_raw = item.get("repeats") or []
            repeats = [
                normalize_repeat(rep, default_qid=qid)
                for rep in repeats_raw
                if isinstance(rep, Mapping)
            ]
            for index, rep in enumerate(repeats, start=1):
                if not rep.get("repeat_index"):
                    rep["repeat_index"] = index
                if not rep.get("question_id"):
                    rep["question_id"] = qid
            if qid and repeats:
                questions.append({"question_id": qid, "repeats": repeats})
    if not questions:
        rows = _iter_acceptance_repeats(payload, source=source)
        if rows:
            return _fixture_from_repeat_rows(
                rows,
                source=source,
                live=bool(payload.get("live")),
                rev=str(payload.get("rev") or payload.get("revision") or ""),
            )
        raise ValueError(f"fixture has no questions/repeats: {source}")
    return {
        "schema": SCHEMA,
        "live": bool(payload.get("live")),
        "rev": str(payload.get("rev") or payload.get("revision") or "fixture"),
        "source": source,
        "questions": questions,
        "note": payload.get("note"),
    }


def _fixture_from_repeat_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    source: str,
    live: bool,
    rev: str = "",
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in rows:
        row = normalize_repeat(raw)
        qid = row["question_id"]
        if not qid:
            continue
        grouped.setdefault(qid, []).append(row)
    return {
        "schema": SCHEMA,
        "live": live,
        "rev": rev,
        "source": source,
        "questions": [
            {"question_id": qid, "repeats": items}
            for qid, items in sorted(grouped.items())
        ],
    }


def score_distribution(fixture: Mapping[str, Any]) -> dict[str, Any]:
    per_question: list[dict[str, Any]] = []
    flip_rates: list[float] = []
    content_flip_rates: list[float] = []
    judge_rates: list[float] = []

    for block in fixture.get("questions") or []:
        qid = str(block.get("question_id") or "")
        repeats = [normalize_repeat(item, default_qid=qid) for item in block.get("repeats") or []]
        if not repeats:
            continue
        outcomes = [str(item["primary_outcome"]) for item in repeats]
        mode = mode_of(outcomes)
        flip = per_question_flip_rate(outcomes)
        n = len(repeats)
        unavailable_n = sum(1 for item in repeats if item["judge_unavailable"])
        judge_rate = unavailable_n / n
        content = [item for item in repeats if not item["judge_unavailable"]]
        content_outcomes = [str(item["primary_outcome"]) for item in content]
        content_flip: float | None
        if len(content_outcomes) >= 2:
            content_flip = per_question_flip_rate(content_outcomes)
            content_flip_rates.append(content_flip)
        elif len(content_outcomes) == 1:
            content_flip = 0.0
            content_flip_rates.append(content_flip)
        else:
            content_flip = None
        flip_rates.append(flip)
        judge_rates.append(judge_rate)
        per_question.append(
            {
                "question_id": qid,
                "n": n,
                "primary_outcome_counts": dict(Counter(outcomes)),
                "mode": mode,
                "flip_rate": _rate(flip),
                "judge_unavailable_count": unavailable_n,
                "judge_unavailable_rate": _rate(judge_rate),
                "content_n": len(content_outcomes),
                "content_flip_rate": None if content_flip is None else _rate(content_flip),
                "repeats": repeats,
            }
        )

    if not per_question:
        raise ValueError("no scored questions")

    baseline = _rate(statistics.fmean(flip_rates))
    judge_mean = _rate(statistics.fmean(judge_rates))
    content_mean = (
        _rate(statistics.fmean(content_flip_rates)) if content_flip_rates else None
    )
    n_repeats = per_question[0]["n"]
    if any(item["n"] != n_repeats for item in per_question):
        n_repeats = max(item["n"] for item in per_question)

    return {
        "schema": SCHEMA,
        "formula": FLIP_RATE_FORMULA,
        "ab_rule": AB_RULE,
        "question_count": len(per_question),
        "n": n_repeats,
        "baseline_flip_rate": baseline,
        "judge_unavailable_rate": judge_mean,
        "content_flip_rate": content_mean,
        "questions": per_question,
        "rev": fixture.get("rev") or "",
        "live": bool(fixture.get("live")),
        "source": fixture.get("source"),
        "note": fixture.get("note"),
    }


def receipt_filename(
    *,
    n: int,
    live: bool,
    stamp: str | None = None,
    fixture: bool = False,
) -> str:
    token = stamp or utc_stamp()
    kind = ""
    if fixture or not live:
        kind = "-fixture"
    return f"{token}{kind}-var{n}.json"


def build_receipt(
    scored: Mapping[str, Any],
    *,
    stamp: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    n = int(scored.get("n") or 0)
    live = bool(scored.get("live"))
    name = receipt_filename(n=n, live=live, stamp=stamp, fixture=not live)
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": stamp or utc_stamp(),
        "filename": name,
        "live": live,
        "fixture": not live,
        "rev": scored.get("rev") or "",
        "n": n,
        "question_count": scored.get("question_count"),
        "baseline_flip_rate": scored["baseline_flip_rate"],
        "judge_unavailable_rate": scored["judge_unavailable_rate"],
        "content_flip_rate": scored.get("content_flip_rate"),
        "formula": scored.get("formula") or FLIP_RATE_FORMULA,
        "ab_rule": scored.get("ab_rule") or AB_RULE,
        "how_to_produce_441c60f2_live_baseline": (
            "Checkout or attach sidecar at 441c60f2. Then: "
            "python scripts/eval_variance_baseline.py --live --rev 441c60f2 "
            "--n 5 --port 8796 --questions A1-market-overview,B1-theme-photoresist,"
            "C1-future-date-no-data. Do not use reserved ports 8792/8793/8795/8799/8801. "
            "Same rev, same questions, N repeats; do not mix with a later fix."
        ),
        "questions": scored.get("questions"),
        "source": scored.get("source"),
        "note": scored.get("note"),
    }
    if extra:
        payload.update(dict(extra))
    return payload


def write_receipt(payload: Mapping[str, Any], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path = dest.with_suffix(".md")
    md_path.write_text(_render_summary_md(payload), encoding="utf-8")
    return dest


def _render_summary_md(payload: Mapping[str, Any]) -> str:
    lines = [
        f"# 评测方差基线 `{payload.get('filename')}`",
        "",
        f"- live: `{payload.get('live')}`",
        f"- rev: `{payload.get('rev') or '—'}`",
        f"- N: {payload.get('n')} · 题数 {payload.get('question_count')}",
        f"- baseline_flip_rate: **{payload.get('baseline_flip_rate')}**",
        f"- judge_unavailable_rate: {payload.get('judge_unavailable_rate')}",
        f"- content_flip_rate: {payload.get('content_flip_rate')}",
        "",
        AB_RULE,
        "",
        "## 每题",
        "",
    ]
    for item in payload.get("questions") or []:
        lines.append(
            f"- `{item.get('question_id')}` n={item.get('n')} "
            f"mode={item.get('mode')} flip={item.get('flip_rate')} "
            f"judge_unavailable={item.get('judge_unavailable_rate')} "
            f"counts={item.get('primary_outcome_counts')}"
        )
    lines.append("")
    lines.append(str(payload.get("formula") or FLIP_RATE_FORMULA))
    lines.append("")
    return "\n".join(lines)


def load_qc28_questions(ids: Sequence[str] | None = None) -> list[dict[str, str]]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    by_id = {str(case.get("id")): case for case in cases if isinstance(case, Mapping)}
    wanted = list(ids) if ids else list(QC28_DEFAULT_SUBSET)
    missing = [qid for qid in wanted if qid not in by_id]
    if missing:
        raise ValueError(f"unknown qc28 ids: {missing}")
    from intelligence.eval.acceptance import effective_query

    return [
        {"question_id": qid, "query": effective_query(by_id[qid])}
        for qid in wanted
    ]


def parse_question_ids(raw: str | None, *, all_qc28: bool) -> list[str] | None:
    if all_qc28:
        payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        return [str(case["id"]) for case in payload.get("cases") or [] if case.get("id")]
    if not raw:
        return None
    ids = [part.strip() for part in raw.split(",") if part.strip()]
    return ids or None


def _assert_live_port(port: int) -> None:
    from intelligence.eval.live_probe import RESERVED_PORTS

    if port in RESERVED_PORTS:
        raise ValueError(
            f"port {port} is reserved ({sorted(RESERVED_PORTS)}); "
            "live variance must use a sidecar (default 8796), never 8792"
        )


def run_live_repeats(
    questions: Sequence[Mapping[str, str]],
    *,
    n: int,
    port: int,
    repo_root: Path,
    user: str,
    timeout: float,
    attach: str,
    keep_sidecar: bool,
) -> dict[str, Any]:
    import os

    from intelligence.eval.live_probe import (
        DEFAULT_LAUNCHER,
        SidecarSpec,
        _resolve_python,
        choose_port,
        port_is_listening,
        post_ask,
        run_dir_for,
        start_sidecar,
        stop_sidecar,
        wait_for_health,
        wait_for_run,
    )

    _assert_live_port(port)
    started_pid: int | None = None
    spec_port = port
    if attach:
        base_url = attach.rstrip("/")
        wait_for_health(base_url, timeout=15)
        users_env = os.environ.get("FORESIGHT_USERS_DIR") or ""
        if not users_env:
            raise ValueError("--attach 需要环境变量 FORESIGHT_USERS_DIR 指向 sidecar 的 users 根")
        users_root = Path(users_env)
    else:
        spec_port = choose_port(preferred=port, is_busy=port_is_listening)
        _assert_live_port(spec_port)
        out_dir = Path.home() / ".finance-runtime" / "eval-variance-sidecar"
        users_root = out_dir / "users"
        spec = SidecarSpec(
            port=spec_port,
            repo_root=repo_root,
            python=_resolve_python(repo_root),
            launcher=DEFAULT_LAUNCHER,
            users_dir=users_root,
            user=user,
        )
        started_pid = start_sidecar(spec, log_path=out_dir / "sidecar.err.log")
        base_url = f"http://127.0.0.1:{spec_port}"
    grouped: dict[str, list[dict[str, Any]]] = {}
    try:
        for case in questions:
            qid = str(case["question_id"])
            query = str(case["query"])
            rows: list[dict[str, Any]] = []
            for index in range(1, n + 1):
                run_id = post_ask(base_url, question=query, user=user)
                status = wait_for_run(
                    base_url, run_id, user=user, timeout=timeout
                )
                run_dir = run_dir_for(users_root, user, run_id)
                row = extract_from_run_dir(run_dir)
                row["question_id"] = qid
                row["repeat_index"] = index
                row["run_status"] = status.get("status")
                rows.append(row)
            grouped[qid] = rows
    finally:
        if started_pid is not None and not keep_sidecar:
            stop_sidecar(started_pid, spec_port)
    return {
        "schema": SCHEMA,
        "live": True,
        "source": base_url,
        "questions": [
            {"question_id": qid, "repeats": grouped[qid]}
            for qid in grouped
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eval_variance_baseline.py",
        description=(
            "同 rev 同题跑 N 次（默认 5），产出每题 outcome 分布与翻转率收据。"
            "默认 --replay 离线，不打 8792。--live 才起 sidecar（默认端口 8796）。"
        ),
        epilog=(
            "对 441c60f2 出真基线（本任务默认不跑 live）：\n"
            "  python scripts/eval_variance_baseline.py --live --rev 441c60f2 "
            "--n 5 --port 8796\n"
            "保留口 8792/8793/8795/8799/8801 一律拒绝。\n"
            "A/B：python scripts/eval_variance_baseline.py --decide "
            "--observed-delta 0.05 --baseline-flip 0.2  → no_call"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--replay",
        type=Path,
        help="已保存的夹具 JSON 或 run 目录（单测走这条，无网络）",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="经 live_probe 起 sidecar 真跑；默认关闭，且绝不默认打 8792",
    )
    parser.add_argument("--n", type=int, default=5, help="每题重复次数（默认 5）")
    parser.add_argument(
        "--questions",
        default="",
        help="逗号分隔的 qc28 case id；缺省用 A1/B1/C1 子集",
    )
    parser.add_argument(
        "--all-qc28",
        action="store_true",
        help="28 题全跑（只对 --live 有意义；很贵）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8796,
        help="sidecar 端口（默认 8796；保留口会 fail）",
    )
    parser.add_argument("--attach", default="", help="已有 sidecar URL，不再起进程")
    parser.add_argument("--user", default="eval-variance")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--keep-sidecar", action="store_true")
    parser.add_argument("--rev", default="", help="被测 revision（live 必填建议）")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="收据 JSON 路径；缺省写 intelligence/eval/runs/<UTC>-[fixture-]varN.json",
    )
    parser.add_argument("--stamp", default="", help="覆盖收据时间戳（测试用）")
    parser.add_argument("--repo-root", type=Path, default=REPO)
    parser.add_argument(
        "--decide",
        action="store_true",
        help="只跑 A/B 判定，不复跑",
    )
    parser.add_argument("--observed-delta", type=float, default=None)
    parser.add_argument("--baseline-flip", type=float, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.decide:
        if args.observed_delta is None or args.baseline_flip is None:
            parser.error("--decide 需要 --observed-delta 与 --baseline-flip")
        decision = ab_decision(args.observed_delta, args.baseline_flip)
        print(
            json.dumps(
                {
                    "decision": decision,
                    "observed_delta": args.observed_delta,
                    "baseline_flip_rate": args.baseline_flip,
                    "ab_rule": AB_RULE,
                },
                ensure_ascii=False,
            )
        )
        return 0

    if args.live and args.replay:
        parser.error("不要同时传 --live 与 --replay")
    if not args.live and args.replay is None:
        parser.error("需要 --replay PATH 或 --live（默认不打网）")

    if args.replay is not None:
        fixture = load_replay(args.replay)
        if args.rev:
            fixture["rev"] = args.rev
        fixture["live"] = False
    else:
        try:
            _assert_live_port(args.port)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        ids = parse_question_ids(args.questions or None, all_qc28=args.all_qc28)
        questions = load_qc28_questions(ids)
        fixture = run_live_repeats(
            questions,
            n=args.n,
            port=args.port,
            repo_root=args.repo_root.resolve(),
            user=args.user,
            timeout=args.timeout,
            attach=args.attach,
            keep_sidecar=args.keep_sidecar,
        )
        fixture["rev"] = args.rev or fixture.get("rev") or ""

    scored = score_distribution(fixture)
    stamp = args.stamp or None
    receipt = build_receipt(scored, stamp=stamp)
    dest = args.out
    if dest is None:
        dest = RUNS_DIR / str(receipt["filename"])
    write_receipt(receipt, dest)
    print(json.dumps({"receipt": str(dest), **{k: receipt[k] for k in (
        "live",
        "rev",
        "n",
        "baseline_flip_rate",
        "judge_unavailable_rate",
        "content_flip_rate",
        "filename",
    )}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
