"""Historical research policy and immutable drafts; no execution or persistence.

The Episode owns execution. The caller supplies authorized result references and
the exact previous artifact; RunStore remains the only artifact writer.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, fields
from datetime import date
import json
from typing import Literal

from intelligence.services.episode_protocol import RejectionKind, parse_finish_json
from intelligence.services.historical_research.intent import HistoryIntent
from intelligence.services.research_contract import ResearchRunContext

ResearchPurpose = Literal["retrospective_discovery", "historical_comparison"]
SelectionMode = Literal[
    "user_specified", "posthoc_winner", "condition_match", "system_candidate"
]
DraftStatus = Literal["candidate", "weakened", "unsupported", "needs_data"]
ClaimLevel = Literal["single_case", "historical_comparison", "insufficient_evidence"]

_PURPOSES = ("retrospective_discovery", "historical_comparison")
_SELECTION_MODES = (
    "user_specified",
    "posthoc_winner",
    "condition_match",
    "system_candidate",
)
_DRAFT_STATUSES = ("candidate", "weakened", "unsupported", "needs_data")
_QUALIFICATIONS = {
    "research_only": True,
    "promotion_eligible": False,
    "decision_eligible": False,
}


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a string list")
    return tuple(dict.fromkeys(_text(item, name) for item in value))


def _version(value: object, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _lineage(version: int, parent: int | None) -> None:
    _version(version, "version")
    if version == 1:
        if parent is not None:
            raise ValueError("initial version cannot have a parent")
    elif type(parent) is not int or parent != version - 1:
        raise ValueError("revision must name its immediate parent version")


def _object(value: object, cls: type) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) for k in value):
        raise ValueError(f"{cls.__name__} must be an object")
    unknown = set(value) - {item.name for item in fields(cls)} - set(_QUALIFICATIONS)
    if unknown:
        raise ValueError(f"unknown {cls.__name__} fields: {', '.join(sorted(unknown))}")
    for key, expected in _QUALIFICATIONS.items():
        if key in value and value[key] is not expected:
            raise ValueError(f"uncertified research requires {key}={expected}")
    return {key: item for key, item in value.items() if key not in _QUALIFICATIONS}


@dataclass(frozen=True)
class HypothesisDraft:
    hypothesis_id: str
    statement: str
    source_case_refs: tuple[str, ...]
    version: int = 1
    parent_version: int | None = None
    origin: str = "model_proposed"
    # Versioned supported definitions only. Unsupported proposals remain below.
    feature_definitions: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    support_refs: tuple[str, ...] = ()
    counterevidence_refs: tuple[str, ...] = ()
    failed_sample_refs: tuple[str, ...] = ()
    exposed_sample_refs: tuple[str, ...] = ()
    unresolved_definitions: tuple[str, ...] = ()
    status: DraftStatus = "candidate"

    def __post_init__(self) -> None:
        for name in ("hypothesis_id", "statement", "origin"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "source_case_refs",
            "feature_definitions",
            "alternatives",
            "support_refs",
            "counterevidence_refs",
            "failed_sample_refs",
            "exposed_sample_refs",
            "unresolved_definitions",
        ):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        _lineage(self.version, self.parent_version)
        if not self.source_case_refs:
            raise ValueError("hypothesis must retain its source case")
        if self.status not in _DRAFT_STATUSES:
            raise ValueError("unsupported draft status; a draft cannot be promoted")

    @classmethod
    def from_dict(cls, value: object) -> HypothesisDraft:
        try:
            return cls(**_object(value, cls))
        except TypeError as exc:
            raise ValueError(f"invalid HypothesisDraft: {exc}") from exc

    def to_dict(self) -> dict[str, object]:
        # JSON-native lists are required by the existing artifact writer; frozen
        # tuples stay an implementation detail of the in-memory value object.
        return {**json.loads(json.dumps(asdict(self))), **_QUALIFICATIONS}


@dataclass(frozen=True)
class ResearchCase:
    case_id: str
    question: str
    purpose: ResearchPurpose
    entity_ids: tuple[str, ...]
    source_refs: tuple[str, ...]
    revision: int = 1
    parent_revision: int | None = None
    window_start: str | None = None
    window_end: str | None = None
    selection_mode: SelectionMode = "user_specified"
    exposed_sample_refs: tuple[str, ...] = ()
    hypotheses: tuple[HypothesisDraft, ...] = ()
    open_questions: tuple[str, ...] = ()
    stop_reason: str = "in_progress"

    def __post_init__(self) -> None:
        for name in ("case_id", "question", "stop_reason"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "entity_ids",
            "source_refs",
            "exposed_sample_refs",
            "open_questions",
        ):
            object.__setattr__(self, name, _strings(getattr(self, name), name))
        _lineage(self.revision, self.parent_revision)
        if self.purpose not in _PURPOSES or self.selection_mode not in _SELECTION_MODES:
            raise ValueError("invalid research purpose or selection mode")
        for value in (self.window_start, self.window_end):
            if value is not None:
                if (
                    not isinstance(value, str)
                    or date.fromisoformat(value).isoformat() != value
                ):
                    raise ValueError("research window must use ISO dates")
        if (self.window_start is None) != (self.window_end is None):
            raise ValueError("research window must be fully resolved or remain unknown")
        if (
            self.window_start
            and self.window_end
            and self.window_start > self.window_end
        ):
            raise ValueError("reversed research window")
        if not isinstance(self.hypotheses, (tuple, list)) or any(
            not isinstance(item, HypothesisDraft) for item in self.hypotheses
        ):
            raise ValueError("hypotheses must contain HypothesisDraft values")
        object.__setattr__(self, "hypotheses", tuple(self.hypotheses))
        ids = [item.hypothesis_id for item in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate hypothesis_id")

    @classmethod
    def from_dict(cls, value: object) -> ResearchCase:
        payload = _object(value, cls)
        raw_hypotheses = payload.get("hypotheses", ())
        if not isinstance(raw_hypotheses, (list, tuple)):
            raise ValueError("hypotheses must be a list")
        payload["hypotheses"] = tuple(
            HypothesisDraft.from_dict(item) for item in raw_hypotheses
        )
        try:
            return cls(**payload)
        except TypeError as exc:
            raise ValueError(f"invalid ResearchCase: {exc}") from exc

    def to_dict(self) -> dict[str, object]:
        return {
            **json.loads(json.dumps(asdict(self))),
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            **_QUALIFICATIONS,
        }


def _retain(before: Iterable[str], after: Iterable[str], name: str) -> None:
    if not set(before).issubset(after):
        raise ValueError(f"revision must retain {name}")


def prepare_research_draft(
    payload: object,
    *,
    available_result_refs: Iterable[str],
    available_definition_refs: Iterable[str] = (),
    previous: ResearchCase | None = None,
) -> ResearchCase:
    """Validate a draft against authorized results and an exact prior artifact.

    Sample exposure references identify result artifacts/query scopes, including
    their complete sample membership. Source-case references name this case or a
    case artifact the caller has separately authorized. No text becomes evidence.
    """
    case = ResearchCase.from_dict(payload)
    allowed_refs = set(available_result_refs)
    allowed_definitions = set(available_definition_refs)
    evidence_refs = set(case.source_refs) | set(case.exposed_sample_refs)
    for item in case.hypotheses:
        unsupported = set(item.feature_definitions) - allowed_definitions
        if unsupported:
            raise ValueError(
                "unsupported_definition: put unavailable definitions in "
                "unresolved_definitions: " + ", ".join(sorted(unsupported))
            )
        evidence_refs.update(item.support_refs)
        evidence_refs.update(item.counterevidence_refs)
        evidence_refs.update(item.failed_sample_refs)
        evidence_refs.update(item.exposed_sample_refs)
        unknown_cases = set(item.source_case_refs) - allowed_refs - {case.case_id}
        if unknown_cases:
            raise ValueError(
                "hypothesis contains an unauthorized source case reference"
            )
    if evidence_refs - allowed_refs:
        raise ValueError("research draft contains an unauthorized result reference")
    if previous is None:
        if case.revision != 1 or any(item.version != 1 for item in case.hypotheses):
            raise ValueError("revised draft requires the exact previous artifact")
        return case
    if case.case_id != previous.case_id:
        raise ValueError("case_id cannot change within a revision")
    if (
        case.revision != previous.revision + 1
        or case.parent_revision != previous.revision
    ):
        raise ValueError("revision must extend the supplied previous artifact")
    _retain(previous.source_refs, case.source_refs, "source_refs")
    _retain(
        previous.exposed_sample_refs, case.exposed_sample_refs, "exposed_sample_refs"
    )
    old = {item.hypothesis_id: item for item in previous.hypotheses}
    new = {item.hypothesis_id: item for item in case.hypotheses}
    _retain(old, new, "hypotheses; mark a rejected explanation unsupported")
    for key, hypothesis in new.items():
        prior = old.get(key)
        if prior is None:
            if hypothesis.version != 1:
                raise ValueError("new hypothesis must begin at version 1")
            continue
        if hypothesis == prior:
            continue
        if (
            hypothesis.version != prior.version + 1
            or hypothesis.parent_version != prior.version
        ):
            raise ValueError(
                "changed hypothesis must increment version and retain parent"
            )
        for name in (
            "source_case_refs",
            "exposed_sample_refs",
            "failed_sample_refs",
            "counterevidence_refs",
        ):
            _retain(getattr(prior, name), getattr(hypothesis, name), name)
    return case


def research_draft_schema() -> dict[str, object]:
    """Tool argument schema. Ownership and parent-artifact loading stay outside."""
    strings = {"type": "array", "items": {"type": "string", "minLength": 1}}
    text = {"type": "string", "minLength": 1}
    parent = {"type": ["integer", "null"], "minimum": 1}
    hypothesis = {
        "type": "object",
        "additionalProperties": False,
        "required": ["hypothesis_id", "statement", "source_case_refs"],
        "properties": {
            **{key: text for key in ("hypothesis_id", "statement", "origin")},
            **{
                key: strings
                for key in (
                    "source_case_refs",
                    "feature_definitions",
                    "alternatives",
                    "support_refs",
                    "counterevidence_refs",
                    "failed_sample_refs",
                    "exposed_sample_refs",
                    "unresolved_definitions",
                )
            },
            "version": {"type": "integer", "minimum": 1},
            "parent_version": parent,
            "status": {"type": "string", "enum": list(_DRAFT_STATUSES)},
            **{
                key: {"type": "boolean", "const": value}
                for key, value in _QUALIFICATIONS.items()
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["case_id", "question", "purpose", "entity_ids", "source_refs"],
        "properties": {
            **{key: text for key in ("case_id", "question", "stop_reason")},
            **{
                key: strings
                for key in (
                    "entity_ids",
                    "source_refs",
                    "exposed_sample_refs",
                    "open_questions",
                )
            },
            "revision": {"type": "integer", "minimum": 1},
            "parent_revision": parent,
            "purpose": {"type": "string", "enum": list(_PURPOSES)},
            "selection_mode": {"type": "string", "enum": list(_SELECTION_MODES)},
            "window_start": {"type": ["string", "null"], "format": "date"},
            "window_end": {"type": ["string", "null"], "format": "date"},
            "hypotheses": {"type": "array", "items": hypothesis},
            **{
                key: {"type": "boolean", "const": value}
                for key, value in _QUALIFICATIONS.items()
            },
        },
    }


_HISTORY_POLICY = """历史研究领域策略（仅本研究用途生效）：
- 允许事后选强势股/板块，读取完整走势、后验峰值发现特征，提出候选假设；不要求发现前锁对象、预注册、申请 R 号或等待未来样本。
- 从当前证据主动提出相互竞争的解释，选择最能区分解释的可取得观察；新反证出现时改变下一查询、修订或削弱假设。研究轴不是固定模板，不强排同日事件先后，不把量能和行情先后写成资金因果。
- 用户要追到历史时，沿原假设比较多份历史样本，主动查失败、无特征却走强及不可判案例。相似 Top-K 只帮助发现，条件全集才是描述性比较分母；25 行预览不是完整样本。来源案例和已暴露样本不冒充独立验证。
- 对每个解释保留支持/反对/未知、来源与定义版本、失败样本和待查问题。未支持的计算定义记录 unresolved_definitions / unsupported_definition，不简化成另一条规则，不宣称已执行。
- L2、晚间卖方、晨汇在未同步的目标范围保持 pending_sync；缺失不等于零或无催化，成交额不能替代主买净额。可用盘面继续研究，依赖缺轨的假设保持未知。
- 当前没有正式认证：所有研究产物 research_only=true、promotion_eligible=false、decision_eligible=false。可以交付单案例解释和历史描述性关联，不能声称规律已通过认证、已可决策使用或已完成独立多样本确认。
- 证据足以回答、现有数据无法区分、缺关键数据或运行时预算/取消要求停止时，交付已完成事实与未决问题。领域只选择研究行动，不增加预算或另起执行循环。
- FINAL_JSON 可以附 history_research：{purpose,result_refs,claim_level,research_only:true,promotion_eligible:false,decision_eligible:false}。claim_level 只取 single_case / historical_comparison / insufficient_evidence，result_refs 必须引用实际返回的 query_id 或 result_ref；完整条件比较必须有 compare_cases 原件。正文仍按既有 bindings 绑定 E 序号。
"""


def history_research_prompt(
    context: ResearchRunContext, *, available_tools: Iterable[str]
) -> tuple[str, str]:
    """Return static policy and prompt-only metadata without copying result rows."""
    intent = context.history_intent
    if not isinstance(intent, HistoryIntent):
        return "", ""
    tools = set(available_tools)
    policy = _HISTORY_POLICY
    if "history_query" not in tools:
        policy += "\n本轮没有授权的 history_query；仅交付已有证据和计算缺口，不声称已经回测或完成历史条件比较。"
    if "save_history_research" in tools:
        policy += "\n保存候选与修订时使用 save_history_research 的 draft 与 previous_result_ref；case_id 由服务生成或继承，hypothesis.source_case_refs 可以引用已有 query_id/result_ref，无需预知 case_id。旧失败/反证及暴露记录必须保留，身份与原件持久化由工具核准。"
    if "read_history_result" in tools:
        policy += "\n追问时先用 read_history_result 读取相关已存 case/query，再续查或修订，避免遗忘原假设和失败样本。case 中的候选解释是研究草稿，不能当成新增事实证据。"
    summaries = [
        {
            key: result[key]
            for key in (
                "query_id",
                "operation",
                "result_ref",
                "status",
                "execution_status",
                "purpose",
                "total_matched",
                "returned_count",
            )
            if key in result
        }
        for result in context.history_results[-8:]
    ]
    dynamic = json.dumps(
        {
            "kind": "HISTORICAL_RESEARCH_CONTEXT",
            "intent": intent.to_dict(),
            "executed_results": summaries,
            "artifact_index": getattr(context, "history_artifact_index", [])[-20:],
            **_QUALIFICATIONS,
        },
        ensure_ascii=False,
    )
    return policy, dynamic


class HistoryFinishRejection(ValueError):
    def __init__(self, code: str, message: str, kind: RejectionKind) -> None:
        super().__init__(message)
        self.code = code
        self.kind = kind


@dataclass(frozen=True)
class HistoryFinishAssessment:
    claim_level: ClaimLevel
    result_refs: tuple[str, ...] = ()
    gap: str = ""
    force_partial: bool = False


def assess_history_finish(
    content: object, *, context: ResearchRunContext
) -> HistoryFinishAssessment | None:
    """Check declared claims against execution metadata, never prose keywords.

    Missing extensions remain compatible with existing model/repair envelopes;
    without an executed historical query, completion is downgraded to partial.
    """
    intent = context.history_intent
    if not isinstance(intent, HistoryIntent):
        return None
    decoded = parse_finish_json(content) if isinstance(content, str) else content
    if not isinstance(decoded, Mapping):
        return None  # The existing finish validator diagnoses malformed JSON.
    successful = [
        result
        for result in context.history_results
        if result.get("execution_status", result.get("status"))
        in {"ok", "completed", "success"}
        and result.get("operation")
        in {"inspect_history", "compute_history", "find_analogues", "compare_cases"}
        and result.get("purpose") in _PURPOSES
    ]
    refs = {
        ref: result
        for result in successful
        for key in ("query_id", "result_ref")
        if isinstance(ref := result.get(key), str) and ref
    }
    raw = decoded.get("history_research")
    if raw is None:
        if successful:
            return HistoryFinishAssessment("single_case")
        return HistoryFinishAssessment(
            "insufficient_evidence",
            gap="尚无可核验的历史计算原件，未完成历史样本检验。",
            force_partial=True,
        )
    if not isinstance(raw, Mapping) or set(raw) - {
        "purpose",
        "result_refs",
        "claim_level",
        *_QUALIFICATIONS,
    }:
        raise HistoryFinishRejection(
            "history_bad_envelope",
            "history_research must use the documented fields",
            RejectionKind.FORMAT,
        )
    if raw.get("purpose") != intent.purpose:
        raise HistoryFinishRejection(
            "history_purpose_mismatch",
            "history purpose must match the authorized context",
            RejectionKind.FORMAT,
        )
    for key, expected in _QUALIFICATIONS.items():
        if raw.get(key) is not expected:
            raise HistoryFinishRejection(
                "history_uncertified_claim",
                f"uncertified history requires {key}={expected}",
                RejectionKind.SUBSTANCE,
            )
    level = raw.get("claim_level")
    if not isinstance(level, str) or level not in {
        "single_case",
        "historical_comparison",
        "insufficient_evidence",
    }:
        raise HistoryFinishRejection(
            "history_bad_claim_level",
            "unsupported historical claim_level",
            RejectionKind.FORMAT,
        )
    try:
        claimed_refs = _strings(raw.get("result_refs"), "result_refs")
    except ValueError as exc:
        raise HistoryFinishRejection(
            "history_bad_refs", str(exc), RejectionKind.FORMAT
        ) from exc
    if set(claimed_refs) - set(refs):
        raise HistoryFinishRejection(
            "history_unknown_result",
            "history result reference has not been executed in the authorized context",
            RejectionKind.INTEGRITY,
        )
    if level != "insufficient_evidence" and not claimed_refs:
        raise HistoryFinishRejection(
            "history_missing_result",
            "historical claims need an executed result reference",
            RejectionKind.SUBSTANCE,
        )
    if level == "historical_comparison" and not any(
        refs[ref].get("operation") == "compare_cases" for ref in claimed_refs
    ):
        raise HistoryFinishRejection(
            "history_missing_comparison",
            "historical_comparison requires a compare_cases result; analogue lists are discovery",
            RejectionKind.SUBSTANCE,
        )
    return HistoryFinishAssessment(
        level,
        claimed_refs,
        gap="历史证据不足，尚不能形成完整样本比较。"
        if level == "insufficient_evidence"
        else "",
        force_partial=level == "insufficient_evidence",
    )
