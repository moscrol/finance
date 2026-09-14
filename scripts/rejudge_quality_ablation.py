#!/usr/bin/env python3
"""对冻结答案补评或完整重评，逐次保存独立收据，不重跑 ask。

pending 仅补未评分行，旧校准只保留历史，决定始终 no_call。
new-batch 用当前判官完整重评全部臂并重新校准；源写作者不可核实的探索仍无资格。
两种模式都保留源文件、答案和源评分，输出路径必须事前独占。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.run_quality_ablation import (  # noqa: E402
    _JUDGE_OVERRIDE,
    _score_is_numeric,
    COMPONENTS,
    resolve_judge,
    RUBRIC_DIMENSIONS,
    Question,
    aggregate_components,
    judge_answer,
    provider_label,
    require_llm_ready,
    build_judge_spec,
    finish_judging,
    write_artifact,
    writer_preflight,
)
from intelligence.eval import judge_validity as validity  # noqa: E402


def _fail(msg: str) -> "SystemExit":
    return SystemExit(f"❌ {msg}")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_run(path: Path, *, raw: bytes | None = None) -> dict[str, object]:
    payload = json.loads(raw if raw is not None else path.read_bytes())
    if not isinstance(payload, dict) or payload.get("kind") not in {
        "quality_ablation", "quality_ablation_rejudge",
    }:
        raise _fail(f"不是 quality_ablation 收据：{path}")
    for key in ("questions", "answers", "aggregates"):
        if key not in payload:
            raise _fail(f"收据缺 {key}：{path}")
    return payload


def source_preflight(artifact):
    """Validate frozen coordinates and contents without trusting old judge scores."""
    try:
        questions, answers, aggregates = artifact["questions"], artifact["answers"], artifact["aggregates"]
        if not isinstance(questions, list) or not questions or not isinstance(answers, list):
            raise ValueError("questions and answers must be arrays")
        if not isinstance(aggregates, dict) or not aggregates:
            raise ValueError("aggregates must identify the registered components")
        ids = []
        for question in questions:
            if (not isinstance(question, dict) or set(question) != {"case_id", "text", "as_of"}
                    or any(not isinstance(question[key], str) or not question[key]
                           for key in ("case_id", "text", "as_of"))):
                raise ValueError("invalid question")
            ids.append(question["case_id"])
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate case_id")
        components = list(aggregates)
        if any(component not in COMPONENTS for component in components):
            raise ValueError("unknown component")
        arms = ["baseline", *components]
        actual = []
        for answer in answers:
            if (not isinstance(answer, dict) or not isinstance(answer.get("answer"), str)
                    or type(answer.get("ok")) is not bool):
                raise ValueError("invalid answer")
            actual.append((answer["case_id"], answer["arm"]))
        expected = {(case_id, arm) for case_id in ids for arm in arms}
        if len(actual) != len(expected) or set(actual) != expected:
            raise ValueError("manifest_denominator_mismatch")
        manifest = artifact.get("manifest")
        if manifest is not None and not isinstance(manifest, dict):
            raise ValueError("invalid source manifest")
        if manifest is None or manifest.get("schema_version") != 2:
            return deepcopy(questions), components, ["unsupported_schema"]
        run, bound = manifest["run_manifest"], manifest["answer_manifest"]
        if (questions != run["questions"] or arms != run["arms"]
                or validity.canonical_hash(run) != manifest["run_manifest_sha256"]
                or validity.canonical_hash(bound) != manifest["answer_manifest_sha256"]
                or bound["run_manifest_sha256"] != manifest["run_manifest_sha256"]
                or run["batch_id"] != manifest["batch_id"]):
            raise ValueError("manifest_hash_mismatch")
        bindings = [validity._answer_binding(manifest, answer) for answer in answers]
        if bindings != bound["answers"]:
            raise ValueError("answer_binding_mismatch")
        for answer, binding in zip(answers, bindings):
            if any(answer.get(key) != binding[key]
                   for key in ("answer_id", "answer_sha256", "judge_input_sha256")):
                raise ValueError("answer_binding_mismatch")
        return deepcopy(questions), components, []
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise _fail(f"源收据冻结内容校验失败：{exc}") from exc


def _prepare_batch(artifact, *, mode, source_path, source_sha256, seed, spec,
                   calibration_repeats, batch_max_seconds, independence, now, output_path):
    questions, component_ids, source_reasons = source_preflight(artifact)
    source_manifest = artifact.get("manifest") or {}
    manifest = validity.new_manifest(
        questions, component_ids, spec, source_run_sha256=source_sha256,
        parent_batch_id=source_manifest.get("batch_id"), calibration_repeats=calibration_repeats,
        batch_max_seconds=batch_max_seconds, independence=independence, now=now,
    )
    result = {
        "schema_version": 2, "kind": "quality_ablation_rejudge", "mode": mode,
        "status": "incomplete", "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "source_run": str(source_path), "source_sha256": source_sha256,
        "source_generated_at": artifact.get("generated_at"),
        "parent_batch_id": source_manifest.get("batch_id"),
        "seed": artifact.get("seed"), "rejudge_seed": seed,
        "source_reason_codes": source_reasons,
        "manifest": manifest, "questions": questions, "answers": [],
        "calibration": [], "noise_floor": None,
        "source_calibration": deepcopy(artifact.get("calibration")),
        "source_noise_floor": deepcopy(artifact.get("noise_floor")),
        "aggregates_before": deepcopy(artifact["aggregates"]), "aggregates": {},
    }
    if output_path is not None:
        write_artifact(Path(output_path), result, create=True)
    for original in artifact["answers"]:
        record = deepcopy(original)
        if mode == "new-batch":
            for key in ("judge", "judge_history", "rejudge_attempts"):
                record.pop(key, None)
        result["answers"].append(validity.stamp_answer(manifest, record))
    result["manifest"] = validity.bind_answers(manifest, result["answers"])
    if output_path is not None:
        write_artifact(Path(output_path), result)
    return result


def _force_diagnostic(result, reasons):
    gate = deepcopy(result.get("judging_validity") or {})
    gate.update(valid=False, reason_codes=sorted(set(gate.get("reason_codes", [])) | set(reasons)))
    result["judging_validity"] = gate
    for aggregate in result["aggregates"].values():
        aggregate.update(decision="no_call", judging_validity=gate)
        aggregate["decision_reason"] = "; ".join(gate["reason_codes"])


def pending_indices(answers: list[dict[str, object]]) -> list[int]:
    """待补评的行：答出来了、但没打上分。

    ``ok=False`` 的行没有答案正文（judge 记的是「答案臂失败，未送评」），补评它
    等于凭空造一份读数——那类缺口只能靠重跑 ask 补，不归本脚本。
    """

    pending = []
    for i, rec in enumerate(answers):
        judge = rec.get("judge") or {}
        if judge.get("scored"):
            continue
        if not rec.get("ok"):
            continue
        if not str(rec.get("answer") or "").strip():
            continue
        pending.append(i)
    return pending


def baseline_absolute(answers: list[dict[str, object]]) -> dict[str, object]:
    """基线臂绝对分均值——门控前后对比用的那个头条数字。

    ⚠️ 跨轮比较的成立条件：绝对分只在同一 judge 下可比（见收据 ``judge_note``）。
    跨 run 比 7.6 → 9.2 时，两轮的 judge 必须是同一条链、同一套 rubric，否则读的
    是 judge 差异不是产品差异。这里只负责算出这一轮的值并附上样本量。
    """

    scored = [
        rec["judge"]
        for rec in answers
        if rec.get("arm") == "baseline" and _score_is_numeric(rec.get("judge") or {})
    ]
    total_n = sum(1 for rec in answers if rec.get("arm") == "baseline")
    if not scored:
        return {"mean_total": None, "questions_scored": 0, "questions_total": total_n}
    return {
        "mean_total": round(sum(j["total"] for j in scored) / len(scored), 3),
        "questions_scored": len(scored),
        "questions_total": total_n,
        "by_dim": {
            d: round(sum(j["scores"][d] for j in scored) / len(scored), 3)
            for d in RUBRIC_DIMENSIONS
        },
        "max_total": 20,
    }


def assert_only_judge_changed(
    answers: list[dict[str, object]],
    answers_before: dict[int, str],
    judged_before: dict[int, str],
) -> None:
    """补评后除 judge 外一切未变——答案正文与既有分数逐条对账。

    调用方（``rejudge_artifact``）目前没有改写答案的路径，这层是**防以后长出
    路径**：哪天有人给 judge_fn 传了整条记录、或加了「补评顺手修一下答案」的
    捷径，这里会当场炸而不是静静地把读数换掉。
    """

    for i, rec in enumerate(answers):
        if _sha256_text(str(rec.get("answer") or "")) != answers_before.get(i):
            raise _fail(f"答案 #{i} 被改写了——补评只补 judge，绝不动答案")
    for i, snapshot in judged_before.items():
        current = json.dumps(answers[i].get("judge"), ensure_ascii=False, sort_keys=True)
        if current != snapshot:
            raise _fail(f"答案 #{i} 原有分数被改动了——补评只碰未打分的行")


def rejudge_artifact(
    artifact: dict[str, object],
    *,
    judge_fn=None,
    seed: int,
    source_path: Path,
    source_sha256: str,
    now: datetime | None = None,
    spec=None,
    independence="require",
    batch_max_seconds=3600,
    output_path=None,
    clock=None,
) -> dict[str, object]:
    """Create a diagnostic batch, preserving every prior scored verdict."""
    from intelligence.services import llm_refine

    clock = clock or ((lambda: now) if now is not None else (lambda: datetime.now(timezone.utc)))
    result = _prepare_batch(
        artifact, mode="pending", source_path=source_path, source_sha256=source_sha256,
        seed=seed, spec=spec or build_judge_spec(), calibration_repeats=0,
        batch_max_seconds=batch_max_seconds, independence=independence, now=now,
        output_path=output_path,
    )
    answers = result["answers"]
    manifest = result["manifest"]
    run = manifest["run_manifest"]
    questions = {q["case_id"]: Question(**q) for q in result["questions"]}
    answers_before = {
        i: _sha256_text(str(rec.get("answer") or "")) for i, rec in enumerate(answers)
    }
    judged_before = {
        i: json.dumps(rec.get("judge"), ensure_ascii=False, sort_keys=True)
        for i, rec in enumerate(answers)
        if (rec.get("judge") or {}).get("scored")
    }

    order = pending_indices(answers)
    random.Random(seed).shuffle(order)
    rejudged: list[dict[str, object]] = []
    still_unscored: list[dict[str, object]] = []
    result.update(rejudged=rejudged, still_unscored=still_unscored)

    def persist():
        if output_path is not None:
            write_artifact(Path(output_path), result)

    with llm_refine.call_ledger_scope(max_calls=len(order) * run["judge_spec"]["max_attempts"]) as ledger:
        try:
            for idx in order:
                remaining = (datetime.fromisoformat(run["expires_at"]) - clock()).total_seconds()
                if remaining <= 0:
                    result["stop_reason_codes"] = ["batch_expired"]
                    raise TimeoutError("batch_expired")
                rec = answers[idx]
                previous = deepcopy(rec.get("judge") or {})
                rec.setdefault("judge_history", []).append(previous)
                attempts = rec.setdefault("rejudge_attempts", [])
                attempts.append({"scored": False, "reason": "not_called", "batch_id": manifest["batch_id"]})
                attempt_index = len(attempts) - 1

                def settled(verdict):
                    snapshot = deepcopy(dict(verdict))
                    if "provider" in snapshot:
                        snapshot["provider"] = provider_label(snapshot["provider"])
                    attempts[attempt_index] = snapshot
                    result["call_ledger"] = ledger.summary()
                    persist()

                if judge_fn is None:
                    verdict = judge_answer(
                        questions[rec["case_id"]], rec["answer"],
                        spec=run["judge_spec"], batch_id=manifest["batch_id"], phase="judge",
                        on_attempt=settled, timeout=min(90.0, remaining),
                    )
                else:
                    verdict = judge_fn(questions[rec["case_id"]], rec["answer"])
                settled(verdict)
                verdict = attempts[attempt_index]
                row = {"arm": rec["arm"], "case_id": rec["case_id"],
                       "previous_reason": previous.get("reason"),
                       "scored": bool(verdict.get("scored")), "total": verdict.get("total"),
                       "provider": verdict.get("provider")}
                if verdict.get("scored"):
                    rec["judge"] = {**verdict, "rejudged": True, "previous_reason": previous.get("reason")}
                    rejudged.append(row)
                else:
                    rec["judge"] = {**previous, "rejudge_attempted": True,
                                    "rejudge_reason": verdict.get("reason")}
                    row["rejudge_reason"] = verdict.get("reason")
                    still_unscored.append(row)
                persist()
                if judge_fn is None:
                    gate = validity._Validation()
                    question = questions[rec["case_id"]].__dict__
                    families = validity._writer_families(rec, question, gate)
                    validity._validate_verdict(verdict, rec, question, manifest, families, gate, phase="judge")
                    fatal = {reason for reason in gate.reasons if reason.startswith("judge_")}
                    if independence == "allow-correlated":
                        fatal.discard("judge_not_independent")
                    if fatal:
                        result["stop_reason_codes"] = sorted(fatal)
                        raise ValueError("judge identity or binding invalid")
            result["manifest"] = validity.seal_manifest(manifest, now=clock())
            result["status"] = "diagnostic"
        except (ValueError, TimeoutError) as exc:
            manifest["state"] = "invalid"
            result.update(status="invalid", error_type=type(exc).__name__)
        except BaseException as exc:
            manifest["state"] = "invalid"
            result.update(status="incomplete", error_type=type(exc).__name__)
            raise
        finally:
            assert_only_judge_changed(answers, answers_before, judged_before)
            result["call_ledger"] = ledger.summary()
            result["noise_floor"] = deepcopy(artifact.get("noise_floor"))
            result["noise_floor_source"] = (
                "源轮实测仅作历史证据；calibration_stale，不授予本批资格"
                if result["noise_floor"] else "源轮未实测；calibration_stale，全部 no_call"
            )
            result["judging_validity"] = validity.validate_judging_batch(
                answers, [], result["manifest"], noise_floor=result["noise_floor"], now=clock())
            result["aggregates"] = aggregate_components(
                answers, run["arms"][1:], noise_floor=result["noise_floor"],
                calibration=[], manifest=result["manifest"], now=clock())
            _force_diagnostic(result, ["calibration_stale", *result["source_reason_codes"]])
            result["baseline_absolute"] = baseline_absolute(answers)
            result["baseline_absolute"].update(
                decision_eligible=False, reason_codes=result["judging_validity"]["reason_codes"])
            providers = sorted({str(row["provider"]) for row in rejudged if row.get("provider")})
            result["judge_continuity"] = (
                f"新诊断批次补评 provider={providers}；旧分与新分仅作描述，"
                "calibration_stale，全部实验决定 no_call。"
            )
            persist()
    return result


def new_batch_artifact(artifact, *, source_path, source_sha256, seed, judge_fn=None,
                       calibration_repeats=2, batch_max_seconds=3600,
                       spec=None, independence="require", output_path=None, now=None, clock=None):
    """Re-score every frozen answer using a newly frozen current specification."""
    result = _prepare_batch(
        artifact, mode="new-batch", source_path=source_path, source_sha256=source_sha256,
        seed=seed, spec=spec or build_judge_spec(), calibration_repeats=calibration_repeats,
        batch_max_seconds=batch_max_seconds, independence=independence, now=now,
        output_path=output_path,
    )

    def persist():
        if output_path is not None:
            write_artifact(Path(output_path), result)

    try:
        finish_judging(result, seed=seed, judge_fn=judge_fn, persist=persist, clock=clock)
    finally:
        if result["source_reason_codes"]:
            _force_diagnostic(result, result["source_reason_codes"])
        result["baseline_absolute"] = baseline_absolute(result["answers"])
        result["baseline_absolute"]["decision_eligible"] = bool(result["judging_validity"]["valid"])
        result["baseline_absolute"]["reason_codes"] = result["judging_validity"]["reason_codes"]
        persist()
    return result


def _print_diff(artifact: dict[str, object]) -> None:
    before = artifact.get("aggregates_before") or {}
    after = artifact["aggregates"]
    mode = artifact.get("mode", "pending")
    print(f"\n== {mode} 描述性读数（源批次 → 新批次）==")
    for cid, agg in after.items():  # type: ignore[union-attr]
        old = before.get(cid, {})  # type: ignore[union-attr]
        print(
            f"  {cid:<18} Δ={old.get('marginal_contribution_total')} → "
            f"{agg['marginal_contribution_total']}"
            f"（可用 {old.get('questions_usable')}/{old.get('questions_total')} → "
            f"{agg['questions_usable']}/{agg['questions_total']} 题）"
        )
        print(f"                     分维度={agg['marginal_by_dim']}")
        print(f"                     决定={agg['decision']} 原因={agg.get('decision_reason') or '-'}")
    base = artifact.get("baseline_absolute") or baseline_absolute(artifact["answers"])
    print(
        f"\n  基线绝对分 均值={base['mean_total']}/20"  # type: ignore[index]
        f"（{base['questions_scored']}/{base['questions_total']} 题已评）"  # type: ignore[index]
        "；仅作描述性统计，配置同名不能证明跨批次可比"
    )
    answers = artifact["answers"]
    delivered = sum(record.get("ok") is True and bool(str(record.get("answer") or "").strip())
                    for record in answers)
    scored = sum((record.get("judge") or {}).get("scored") is True for record in answers)
    failures = (artifact.get("call_ledger") or {}).get("failure_count", 0)
    print(f"  分母：总样本={len(answers)} 已交付={delivered} 已评分={scored} 本批失败尝试={failures}")
    print(f"  资格原因={'; '.join((artifact.get('judging_validity') or {}).get('reason_codes', [])) or '-'}")
    still = artifact.get("still_unscored") or []
    if still:
        print(f"\n  仍未打分 {len(still)} 份（留在总分母，质量决定 no_call）：")
        for row in still:  # type: ignore[union-attr]
            print(f"     {row['arm']:<18} {row['case_id']:<22} {row.get('rejudge_reason')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="待补评的 quality_ablation 收据")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="修正收据路径（默认 <原名>-rejudge.json）；指向原文件会被拒绝",
    )
    parser.add_argument("--seed", type=int, default=20260827, help="补评洗牌种子")
    parser.add_argument("--mode", choices=("pending", "new-batch"), default="pending",
                        help="pending 只补未评分；new-batch 对全部冻结答案重评分")
    parser.add_argument("--batch-max-seconds", type=int, default=3600)
    parser.add_argument("--calibration-repeats", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="只列出待补评行，不调 LLM")
    parser.add_argument(
        "--judge-independence",
        choices=("require", "allow-correlated"),
        default="require",
        help="默认依据源答案收据要求写作者与当前判官异构；allow-correlated 仅作诊断",
    )
    parser.add_argument("--allowed-reported-models", default=None,
                        help="调用前冻结允许的响应型号，逗号分隔；默认仅请求型号")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = args.run.resolve()
    raw = source.read_bytes()
    artifact = load_run(source, raw=raw)
    if args.calibration_repeats < 0 or args.batch_max_seconds <= 0:
        raise _fail("calibration-repeats 必须非负，batch-max-seconds 必须大于零")
    suffix = "rejudge" if args.mode == "pending" else "new-batch"
    output = args.output or source.with_name(f"{source.stem}-{suffix}.json")
    if output.resolve() == source:
        raise _fail("--output 指向原文件；新收据必须另存，原始读数不可覆盖")
    if output.exists():
        raise _fail(f"输出已存在，拒绝覆盖：{output}")
    questions, _components, source_reasons = source_preflight(artifact)
    answers = artifact["answers"]  # type: ignore[assignment]
    pending = pending_indices(answers)  # type: ignore[arg-type]

    print(f"[run] {source}")
    print(f"[plan] 共 {len(answers)} 份答案，待补评 {len(pending)} 份；模式={args.mode}（不重跑 ask）")
    for idx in pending:
        rec = answers[idx]  # type: ignore[index]
        reason = str((rec.get("judge") or {}).get("reason") or "")[:60]
        print(f"  #{idx:<3} {rec['arm']:<18} {rec['case_id']:<22} 原因={reason}")
    if args.dry_run:
        if args.mode == "new-batch":
            print(f"[plan] 全臂重评 {len(answers)} 份，另加每份基线 {args.calibration_repeats} 次校准")
        return 0
    will_dispatch = bool(pending) or args.mode == "new-batch"
    if will_dispatch:
        require_llm_ready()
    # Current composer settings do not identify a historical writer.
    judge_info = resolve_judge(require_independent=False)
    _JUDGE_OVERRIDE["provider"] = judge_info.pop("override")
    allowed = None
    if args.allowed_reported_models is not None:
        allowed = [model.strip() for model in args.allowed_reported_models.split(",") if model.strip()]
        if not allowed:
            raise _fail("allowed-reported-models 不能为空")
    spec = build_judge_spec(allowed_models=allowed)
    preflight_reasons = sorted(set(source_reasons + writer_preflight(answers, spec, questions)))
    if will_dispatch and preflight_reasons and args.judge_independence == "require":
        raise _fail("源写作者/收据预检失败，零调用：" + "; ".join(preflight_reasons))
    print(
        f"[judge] 当前判官={judge_info['judge']} 源写作者预检={preflight_reasons or '通过'}"
    )
    common = {
        "source_path": source, "source_sha256": hashlib.sha256(raw).hexdigest(),
        "seed": args.seed, "spec": spec, "independence": args.judge_independence,
        "batch_max_seconds": args.batch_max_seconds, "output_path": output,
    }
    if args.mode == "new-batch":
        result = new_batch_artifact(
            artifact, **common, calibration_repeats=args.calibration_repeats,
        )
    else:
        result = rejudge_artifact(artifact, **common)
    result["judge_independence"] = judge_info
    result["source_preflight_reason_codes"] = preflight_reasons
    write_artifact(output, result)
    _print_diff(result)
    print(f"\n原始收据（未改动）→ {source}")
    print(f"修正收据 → {output}")
    return 0 if result["status"] in {"complete", "diagnostic"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
