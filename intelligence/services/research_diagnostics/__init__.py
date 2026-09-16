"""个人研究流程诊断与一题历史练习（研究进化 04）。

规格 ``docs/superpowers/specs/2026-09-13-research-evolution/04-personal-diagnostics.md``。

五类流程检查（迟登 / 条件修改 / 过期证据沿用 / 阶段不适用 / 到期未回检）→ 带证据的 finding、
分母、不能归因项，再从冻结题包稳定选一题。确定性、无模型、无 IO：

    diagnose(*, owner_user_id, start, end, knowledge_cutoff,
             records, verdicts, maintenance_reports, process_receipts, exercise_cases, policy) -> DiagnosticReport
    evaluate_exercise_response(*, exercise, response, answer_key) -> ExerciseFeedback

旧台账接入走 ``adapters``（只读适配器）；授权、路径解析与展示归 06。
"""

from intelligence.services.research_diagnostics.contracts import (
    ACTOR_GROUPS,
    CLASSIFICATIONS,
    KINDS,
    MAINTENANCE_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    SCHEMA_VERSION,
    ActorInfo,
    AnswerKey,
    ApplicabilityTable,
    DiagnosticFinding,
    DiagnosticPolicy,
    DiagnosticReport,
    DiagnosticsInputError,
    ExerciseCase,
    ExerciseFeedback,
    ExerciseResponse,
    HistoricalExercise,
    InvalidRef,
    ObjectRef,
    OwnerMismatch,
    ProcessReceipt,
    ProcessRecord,
    Rule,
    TimePoint,
    UnsupportedSchema,
    VerdictRecord,
    VersionEntry,
    parse_exercise_pack,
)
from intelligence.services.research_diagnostics.exercise import evaluate_exercise_response
from intelligence.services.research_diagnostics.report import diagnose

__all__ = [
    "ACTOR_GROUPS",
    "CLASSIFICATIONS",
    "KINDS",
    "MAINTENANCE_SCHEMA_VERSION",
    "POLICY_SCHEMA_VERSION",
    "SCHEMA_VERSION",
    "ActorInfo",
    "AnswerKey",
    "ApplicabilityTable",
    "DiagnosticFinding",
    "DiagnosticPolicy",
    "DiagnosticReport",
    "DiagnosticsInputError",
    "ExerciseCase",
    "ExerciseFeedback",
    "ExerciseResponse",
    "HistoricalExercise",
    "InvalidRef",
    "ObjectRef",
    "OwnerMismatch",
    "ProcessReceipt",
    "ProcessRecord",
    "Rule",
    "TimePoint",
    "UnsupportedSchema",
    "VerdictRecord",
    "VersionEntry",
    "diagnose",
    "evaluate_exercise_response",
    "parse_exercise_pack",
]
