"""一题历史练习（规格 §6）：从冻结题包按 issue 稳定选一题；学习者只拿到投影，答完才解锁解释。

三轴独立记录，互不推断：

- ``data_pit_grade``：题包声明 strict，但任一材料没日期或晚于题的 knowledge_cutoff → 降为 unverifiable。
  声明不能升级事实。
- ``model_exposure_grade``：首版无模型调用，默认 deterministic_only；有 ``model_exposure`` 收据命中同一
  ``outcome_identity`` → known_exposed。改名去日期不洗掉泄漏——判定按结局身份，不按题名。
- ``learner_exposure_grade``：``exercise_seen`` 命中 case_id 或 outcome_identity → seen_or_repeated；
  只有 ``learner_declaration`` 自报未见 → declared_unseen（不是盲测证明）；否则 not_declared。

选题是**确定性**的：同 owner、同 findings、同题包永远选同一题。选题依据是 issue 类别，不是随机；
06 记录选题与重复次数。
"""

from __future__ import annotations

from intelligence.services.research_diagnostics.clock import day_le
from intelligence.services.research_diagnostics.contracts import (
    AnswerKey,
    DiagnosticFinding,
    DiagnosticsInputError,
    ExerciseCase,
    ExerciseCheck,
    ExerciseFeedback,
    ExerciseResponse,
    Gap,
    HistoricalExercise,
    ProcessReceipt,
    content_hash,
)

LIMITATION = "只练一件事，按过程评分不猜涨跌；按 issue 类别选题不是随机；练习结果不进任何方法有效性统计"


def _pit_of(case: ExerciseCase) -> tuple[str, str | None]:
    declared = case.declared_data_pit_grade
    for m in case.materials:
        if m.dated is None:
            return "unverifiable", f"材料 {m.ref} 时间不明，不能进严格题包"
        if day_le(m.dated, case.knowledge_cutoff) is False:
            return "unverifiable", f"材料 {m.ref} 日期 {m.dated} 晚于题的知识截止 {case.knowledge_cutoff}"
    if declared == "strict" and not case.materials:
        return "trade_date_only", "声明 strict 但没有可核的材料清单，降为 trade_date_only"
    return declared, None


def _model_grade(case: ExerciseCase, receipts: list[ProcessReceipt]) -> str:
    for r in receipts:
        if r.kind == "model_exposure" and str(r.payload.get("outcome_identity")) == case.outcome_identity:
            return "known_exposed"
    return case.model_exposure_grade


def _learner_grade(case: ExerciseCase, receipts: list[ProcessReceipt]) -> str:
    seen = False
    declared = False
    for r in receipts:
        hit = str(r.payload.get("case_id") or "") == case.case_id or str(r.payload.get("outcome_identity") or "") == case.outcome_identity
        if not hit:
            continue
        if r.kind == "exercise_seen":
            seen = True
        elif r.kind == "learner_declaration" and str(r.payload.get("declared")) == "unseen":
            declared = True
    if seen:
        return "seen_or_repeated"
    if declared:
        return "declared_unseen"
    return "not_declared"


def select_exercise(
    *,
    owner_user_id: str,
    findings: list[DiagnosticFinding],
    cases: list[ExerciseCase],
    receipts: list[ProcessReceipt],
) -> tuple[HistoricalExercise | None, list[Gap]]:
    issues = sorted((f for f in findings if f.classification == "issue"), key=lambda f: (f.kind, f.id))
    if not issues:
        return None, [Gap("no_issue_findings", None, detail="没有带证据的 issue，不出题；unknown 不配题")]
    if not cases:
        return None, [Gap("exercise_pack_empty", None, detail="题包为空")]
    for finding in issues:
        pool = [c for c in cases if c.kind == finding.kind]
        if not pool:
            continue
        unseen = [c for c in pool if _learner_grade(c, receipts) != "seen_or_repeated"]
        ranked = sorted(
            unseen or pool,
            key=lambda c: content_hash({"owner": owner_user_id, "finding": finding.id, "case": c.case_id}),
        )
        case = ranked[0]
        pit, pit_note = _pit_of(case)
        limitation = LIMITATION if pit_note is None else f"{LIMITATION}；{pit_note}"
        projection = {
            "prompt": case.prompt,
            "visible_evidence_refs": list(case.visible_evidence_refs),
            "as_of": case.as_of,
            "knowledge_cutoff": case.knowledge_cutoff,
        }
        exercise = HistoricalExercise(
            id="hx-" + content_hash({"owner": owner_user_id, "finding": finding.id, "case": case.case_id, "pack": case.pack_version})[:16],
            target_finding_id=finding.id,
            case_ref=case.case_ref,
            as_of=case.as_of,
            knowledge_cutoff=case.knowledge_cutoff,
            prompt=case.prompt,
            visible_evidence_refs=case.visible_evidence_refs,
            projection_hash=content_hash(projection),
            data_pit_grade=pit,
            model_exposure_grade=_model_grade(case, receipts),
            learner_exposure_grade=_learner_grade(case, receipts),
            exercise_status="ready",
            answer_key_ref=case.answer_key.ref,
            limitation=limitation,
        )
        return exercise, []
    kinds = sorted({f.kind for f in issues})
    return None, [Gap("no_exercise_case_for_kind", ",".join(kinds), detail="题包里没有对应 issue 类别的题")]


def evaluate_exercise_response(*, exercise: HistoricalExercise, response: ExerciseResponse, answer_key: AnswerKey) -> ExerciseFeedback:
    """只比较结构化选择与引用；散文理由待人工（``manual_review``），不用模型评分。

    ``answer_key.ref`` 必须等于 ``exercise.answer_key_ref``，否则拒绝——防止拿别题的答案对本题。
    """
    if response.exercise_id != exercise.id:
        raise DiagnosticsInputError("response.exercise_id 与 exercise.id 不一致")
    if answer_key.ref != exercise.answer_key_ref:
        raise DiagnosticsInputError("answer_key.ref 与 exercise.answer_key_ref 不一致，拒绝评分")
    expected_choices = tuple(sorted(answer_key.expected_choices))
    got_choices = tuple(sorted(response.selected_choices))
    expected_refs = tuple(sorted(answer_key.expected_refs))
    got_refs = tuple(sorted(response.cited_refs))
    missing = tuple(r for r in expected_refs if r not in got_refs)
    checks = (
        ExerciseCheck("choices_match", expected_choices == got_choices, expected_choices, got_choices),
        ExerciseCheck("expected_refs_cited", not missing, expected_refs, got_refs),
    )
    status = "manual_review" if str(response.rationale or "").strip() else "checked"
    return ExerciseFeedback(
        exercise_id=exercise.id,
        status=status,
        checks=checks,
        missing_evidence_refs=missing,
        explanation_ref=answer_key.explanation_ref,
    )
