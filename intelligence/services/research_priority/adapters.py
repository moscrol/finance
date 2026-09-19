"""02 · 只读适配：把现役来源记录转成 ``research-task/v1`` 候选。

四种来源（spec §2 表），全部只读、不解析聊天正文、不发明绑定：

* ``maintenance_report`` / ``maintenance_item`` —— 01 的 ``judgment-maintenance/v1`` 输出。
  这是唯一能产出 abandon_or_downgrade 的来源，且只在 ``change_type=condition_evaluated``
  + ``condition_result=true`` + ``condition_role∈{abandon,downgrade}`` 时（P02 的反向证伪点）。
* ``research_project`` —— ``research_project.load_project`` 投影（``to_dict()`` 或同形 dict）：
  触发点 → verify_due_condition（绑定 checkpoint 对象）；下一问 / 未解问题 → explore / fill_gap，
  没有登记的判断对象，所以 ``legacy_unbound``。
* ``research_queue`` —— 现役 ``research-queue/v1`` 队列：全部 ``legacy_unbound``（P11）；
  「等盘面验证」是 waiting_release，「降级/观察」不生成研究任务。队列自己的「优先级」
  是热度分，本模块不读它（P01：热度不改变证据等级）。
* ``data_request`` —— ``data_requests.DataRequest``：fill_gap；``pending_sync`` 路线为
  missing_data；只有调用方显式给 ``request_bindings`` 才算绑定到判断。

调用方（06）负责：按 owner / 范围预过滤、解析真实路径与 hash、注入 ``effort_estimates``。
本模块收到不属于当前 owner 的 01 记录或研究项目时拒绝整份输入（P09）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from intelligence.services import checkpoints as checkpoints_svc
from intelligence.services import data_requests as data_requests_svc
from intelligence.services import research_queue as research_queue_svc

from . import contracts as c

SOURCE_MAINTENANCE_ITEM = "maintenance_item"
SOURCE_MAINTENANCE_REPORT = "maintenance_report"
SOURCE_RESEARCH_PROJECT = "research_project"
SOURCE_RESEARCH_QUEUE = "research_queue"
SOURCE_DATA_REQUEST = "data_request"

MAINTENANCE_SCHEMA = "judgment-maintenance/v1"
CHANGE_TYPES = (
    "content_changed",
    "source_corrected",
    "source_expired",
    "dependency_missing",
    "condition_evaluated",
    "unchanged",
)
ROLE_LABELS = {"upgrade": "升级", "downgrade": "降级", "abandon": "放弃", "review": "复核"}
REASON_LABELS = {
    "hash_changed": "内容哈希变化",
    "explicit_supersession": "显式更正/替代",
    "validity_ended": "有效期结束",
    "ref_unresolved": "引用无法解析",
    "time_metadata_missing": "时间元数据缺失",
    "dependency_unbound": "依赖未绑定",
    "condition_true": "条件为真",
    "condition_false": "条件为假",
    "condition_unknown": "条件未知",
    "no_change": "无变化",
}
PIT_DAILY = "trade_date_only"


@dataclass
class _Ctx:
    owner: str
    synthetic: bool
    conversation_id: str | None
    as_of: str | None
    knowledge_cutoff: str | None
    effort_estimates: dict[str, Any]
    request_bindings: dict[str, list[dict[str, Any]]]
    hindsight: bool = False
    tasks: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)

    def skip(self, source: dict[str, Any], reason: str, detail: str = "") -> None:
        self.skipped.append({"source": source, "reason": reason, "detail": detail})

    def effort_for(self, source: dict[str, Any]) -> dict[str, Any] | None:
        return self.effort_estimates.get(f"{source['kind']}:{source['id']}")


def adapt_candidates(source_records: Any, context: Any) -> dict[str, Any]:
    """把来源记录列表转成候选包 ``research-priority-candidates/v1``。

    每条记录形如 ``{"kind": <来源种类>, "payload": <原对象>, ...}``；未知种类、越权、
    未知 schema 拒绝整份输入。跳过的记录全部列在 ``skipped`` 里供对账。
    """
    if not isinstance(context, dict):
        raise c.ContractError("invalid_context", "context 必须是 dict")
    owner = context.get("owner_user_id")
    if not isinstance(owner, str) or not owner.strip():
        raise c.ContractError("owner_missing", "context.owner_user_id 必须是经验证的用户 id")
    ctx = _Ctx(
        owner=owner,
        synthetic=bool(context.get("synthetic", False)),
        conversation_id=context.get("conversation_id"),
        as_of=context.get("as_of"),
        knowledge_cutoff=context.get("knowledge_cutoff"),
        effort_estimates=dict(context.get("effort_estimates") or {}),
        request_bindings=dict(context.get("request_bindings") or {}),
        hindsight=bool(context.get("hindsight", False)),
    )
    if source_records is None:
        source_records = []
    if not isinstance(source_records, (list, tuple)):
        raise c.ContractError("invalid_source", "source_records 必须是列表")
    for index, record in enumerate(source_records):
        if not isinstance(record, dict):
            raise c.ContractError("invalid_source", f"source_records[{index}] 不是对象")
        kind = record.get("kind")
        handler = _HANDLERS.get(str(kind))
        if handler is None:
            raise c.ContractError("unknown_source_kind", f"source_records[{index}] kind={kind!r} 未知")
        handler(record, record.get("payload"), ctx)

    tasks: list[dict[str, Any]] = []
    for index, task in enumerate(ctx.tasks):
        validated = c.validate_task(task, owner_user_id=owner, index=index)
        validated["id"] = c.task_id_for(c.identity_key(validated))
        validated["source_task_ids"] = [validated["id"]]
        tasks.append(validated)
    tasks.sort(key=lambda t: (t["id"], c.canonical_json(t)))
    return {
        "schema_version": c.SCHEMA_CANDIDATES,
        "owner_user_id": owner,
        "tasks": tasks,
        "skipped": ctx.skipped,
        "synthetic": ctx.synthetic,
    }


# ---------------------------------------------------------------------------
# 共用构造
# ---------------------------------------------------------------------------


def _task(
    ctx: _Ctx,
    *,
    source: dict[str, Any],
    effect_kind: str,
    object_refs: list[dict[str, Any]],
    evidence_refs: list[dict[str, Any]],
    question: str,
    discriminating: str,
    completion: str,
    human_review_required: bool,
    condition_result: Any,
    availability: str,
    availability_reason: str | None,
    as_of: str | None,
    knowledge_cutoff: str | None,
    pit_grade: str,
    gaps: list[dict[str, Any]],
    conversation_id: str | None,
    entity_refs: list[str],
    maintenance_item_ids: list[str] | None = None,
    due_at: Any = None,
    available_at: Any = None,
    management_status: str | None = None,
    hindsight: bool = False,
) -> None:
    ctx.tasks.append(
        {
            "schema_version": c.SCHEMA_TASK,
            "id": "rt_pending",
            "owner_user_id": ctx.owner,
            "scope": {"conversation_id": conversation_id, "entity_refs": entity_refs},
            "source": source,
            "object_refs": object_refs,
            "maintenance_item_ids": maintenance_item_ids or [],
            "question": question,
            "discriminating_evidence": discriminating,
            "completion_condition": completion,
            "human_review_required": human_review_required,
            "effect_kind": effect_kind,
            "effect_evidence_refs": evidence_refs,
            "condition_result": condition_result,
            "availability": availability,
            "availability_reason": availability_reason,
            "available_at": available_at,
            "due_at": due_at,
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "pit_grade": pit_grade,
            "effort": ctx.effort_for(source),
            "gaps": gaps,
            "legacy_unbound": not object_refs,
            "management_status": management_status,
            "synthetic": ctx.synthetic,
            "hindsight": bool(hindsight or ctx.hindsight),
        }
    )


def _gap(reason: str, ref: str | None = None, *, retryable: bool | None = None) -> dict[str, Any]:
    return {"reason": reason, "ref": ref, "checked_at": None, "retryable": retryable}


def _gap_label(gap: dict[str, Any]) -> str:
    return f"{gap['reason']}（{gap['ref']}）" if gap.get("ref") else str(gap["reason"])


def _cutoff_or_gap(value: Any, gaps: list[dict[str, Any]], *, field_name: str) -> str | None:
    """旧产物的时间戳可能缺失或不带时区：不伪造、不拒绝整份输入，留 null + gap。"""
    if value is None or value == "":
        gaps.append(_gap(f"{field_name}_missing", retryable=True))
        return None
    try:
        c.parse_instant(value, field=field_name)
    except c.ContractError as exc:
        gaps.append(_gap(f"{field_name}_{exc.code}", str(value), retryable=True))
        return None
    return str(value)


def _evidence_refs(versions: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for version in versions or []:
        if not isinstance(version, dict) or not version.get("ref"):
            continue
        refs.append(
            {
                "kind": "evidence",
                "id": str(version["ref"]),
                "namespace": str(version.get("derivation") or "evidence"),
                "version_or_hash": None if version.get("source_hash") is None else str(version["source_hash"]),
                "scope": None,
            }
        )
    return refs


def _labels(refs: list[dict[str, Any]]) -> str:
    if not refs:
        return "（无引用）"
    return "、".join(
        c.object_label(r) + (f"@{r['version_or_hash'][:12]}" if r.get("version_or_hash") else "") for r in refs
    )


# ---------------------------------------------------------------------------
# 01 · judgment-maintenance/v1
# ---------------------------------------------------------------------------


def _adapt_maintenance_report(record: dict[str, Any], payload: Any, ctx: _Ctx) -> None:
    if not isinstance(payload, dict):
        raise c.ContractError("invalid_source", "maintenance_report payload 不是对象")
    if payload.get("schema_version") != MAINTENANCE_SCHEMA:
        raise c.ContractError("unknown_schema", f"maintenance_report schema_version={payload.get('schema_version')!r}")
    if payload.get("owner_user_id") != ctx.owner:
        raise c.ContractError("owner_mismatch", "maintenance_report 不属于当前用户")
    items = payload.get("items")
    if not isinstance(items, list):
        raise c.ContractError("invalid_source", "maintenance_report.items 必须是数组")
    defaults = {
        "report_id": payload.get("id"),
        "as_of": payload.get("as_of"),
        "knowledge_cutoff": payload.get("knowledge_cutoff"),
        "pit_grade": payload.get("pit_grade"),
        "hindsight": bool(payload.get("hindsight", False)),
    }
    for item in items:
        _adapt_maintenance_item_impl(item, ctx, defaults)


def _adapt_maintenance_item(record: dict[str, Any], payload: Any, ctx: _Ctx) -> None:
    _adapt_maintenance_item_impl(
        payload, ctx, {"report_id": record.get("id"), "hindsight": bool(record.get("hindsight", False))}
    )


def _adapt_maintenance_item_impl(item: Any, ctx: _Ctx, defaults: dict[str, Any]) -> None:
    if not isinstance(item, dict):
        raise c.ContractError("invalid_source", "maintenance_item 不是对象")
    if item.get("schema_version") != MAINTENANCE_SCHEMA:
        raise c.ContractError("unknown_schema", f"maintenance_item schema_version={item.get('schema_version')!r}")
    if item.get("owner_user_id") != ctx.owner:
        raise c.ContractError("owner_mismatch", "maintenance_item 不属于当前用户")
    item_id = str(item.get("id") or "")
    if not item_id:
        raise c.ContractError("invalid_source", "maintenance_item 缺 id")
    change_type = item.get("change_type")
    if change_type not in CHANGE_TYPES:
        raise c.ContractError("invalid_enum", f"maintenance_item {item_id} change_type 非法：{change_type!r}")

    object_ref_raw = item.get("object_ref") if isinstance(item.get("object_ref"), dict) else {}
    conversation_id = None
    if isinstance(object_ref_raw.get("scope"), dict):
        conversation_id = object_ref_raw["scope"].get("conversation_id")
    conversation_id = conversation_id or ctx.conversation_id
    source = {
        "kind": SOURCE_MAINTENANCE_ITEM,
        "id": item_id,
        "namespace": MAINTENANCE_SCHEMA,
        "version_or_hash": None if item.get("item_version") is None else str(item["item_version"]),
        "scope": {"report_id": defaults.get("report_id"), "conversation_id": conversation_id},
    }
    status = str(item.get("status") or "open")
    if status in ("closed", "superseded"):
        ctx.skip(source, f"management_status_{status}", "维护项已关闭/被替代，不再生成研究任务")
        return
    if status == "rejudgment_requested":
        ctx.skip(source, "rejudgment_in_flight", "已发起重新判断，由 06 跟踪该 run；失败会回到 open")
        return
    if status not in c.MANAGEMENT_STATUSES:
        raise c.ContractError("invalid_enum", f"maintenance_item {item_id} status 非法：{status!r}")
    if change_type == "unchanged":
        ctx.skip(source, "no_change", "证据无变化，只计覆盖")
        return

    reason_code = str(item.get("reason_code") or "")
    reason_label = REASON_LABELS.get(reason_code, reason_code or "未记录原因")
    condition_result = c.condition_result_of(item.get("condition_result"))
    role = item.get("condition_role")
    gaps = [_normalize_gap(g) for g in (item.get("gaps") or [])]

    object_refs: list[dict[str, Any]] = []
    has_identity = object_ref_raw.get("id") is not None or object_ref_raw.get("ref")
    if object_ref_raw.get("kind") and has_identity:
        ref = {
            "kind": str(object_ref_raw["kind"]),
            "id": None if object_ref_raw.get("id") is None else str(object_ref_raw["id"]),
            "namespace": str(object_ref_raw.get("namespace") or "judgments"),
            "version_or_hash": None
            if object_ref_raw.get("version_or_hash") is None
            else str(object_ref_raw["version_or_hash"]),
            "scope": object_ref_raw.get("scope") if isinstance(object_ref_raw.get("scope"), dict) else None,
        }
        if object_ref_raw.get("ref"):
            ref["ref"] = str(object_ref_raw["ref"])
        object_refs = [ref]
    else:
        gaps.append(_gap("dependency_unbound", None, retryable=False))

    before = _evidence_refs(item.get("before"))
    current = _evidence_refs(item.get("current"))
    evidence_refs = list(current or before)
    condition_ref = item.get("condition_ref")
    binding_id = item.get("binding_id")
    item_as_of = item.get("as_of") or defaults.get("as_of")
    item_cutoff = item.get("knowledge_cutoff") or defaults.get("knowledge_cutoff")
    if condition_ref:
        evidence_refs.append(
            {
                "kind": "condition",
                "id": str(condition_ref),
                "namespace": f"binding:{binding_id}" if binding_id else "binding",
                "version_or_hash": None if item.get("binding_version") is None else str(item["binding_version"]),
                # 观测窗口进 scope（不进 version_or_hash：那一格是 binding 版本，不能塞日期）。
                # 合并身份由任务级 as_of / knowledge_cutoff 承担，与 01 的 dedup_key「条件/观测窗口」同口径；
                # 这里保留窗口是为了让 06 / 04 能看出该条件取自哪一次观测。
                "scope": {"as_of": item_as_of, "knowledge_cutoff": item_cutoff},
            }
        )
    label = c.object_label(object_refs[0]) if object_refs else f"维护项 {item_id}"
    version_note = f"维护项 {item_id}（item_version {source['version_or_hash'] or '未记录'}）"
    common = dict(
        source=source,
        object_refs=object_refs,
        as_of=item_as_of,
        knowledge_cutoff=item_cutoff,
        pit_grade=item.get("pit_grade") or defaults.get("pit_grade") or "unverifiable",
        conversation_id=conversation_id,
        entity_refs=[],
        maintenance_item_ids=[item_id],
        management_status=status,
        hindsight=bool(defaults.get("hindsight", False)),
    )

    if change_type == "condition_evaluated":
        if condition_result is True and role in ("abandon", "downgrade"):
            role_label = ROLE_LABELS[role]
            _task(
                ctx,
                effect_kind=c.EFFECT_ABANDON,
                evidence_refs=evidence_refs,
                question=f"「{label}」的{role_label}条件 {condition_ref} 已被观测触发：复核该判断是否{role_label}",
                discriminating=f"条件 {condition_ref}（binding {binding_id} v{item.get('binding_version')}）的观测值；来源版本 {_labels(current or before)}",
                completion=f"读到条件 {condition_ref} 的观测来源 {_labels(current or before)}，并对{version_note}记录 reviewed_no_change 或 rejudge 动作",
                human_review_required=False,
                condition_result=True,
                availability=c.AVAIL_ACTIONABLE,
                availability_reason=None,
                gaps=gaps,
                **common,
            )
            return
        if condition_result is True:
            role_label = ROLE_LABELS.get(str(role), "复核")
            _task(
                ctx,
                effect_kind=c.EFFECT_VERIFY_DUE,
                evidence_refs=evidence_refs,
                question=f"「{label}」的{role_label}条件 {condition_ref} 已触发：核查是否成立并决定是否{role_label}",
                discriminating=f"条件 {condition_ref} 的观测值；来源版本 {_labels(current or before)}",
                completion=f"读到条件 {condition_ref} 的观测来源，并对{version_note}记录复核动作（reviewed_no_change / rejudge）",
                human_review_required=False,
                condition_result=True,
                availability=c.AVAIL_ACTIONABLE,
                availability_reason=None,
                gaps=gaps,
                **common,
            )
            return
        if condition_result is False:
            ctx.skip(source, "condition_false", f"条件 {condition_ref} 判定为假：未触发，无研究动作")
            return
        # unknown / null：不视为触发；缺观测值就是 missing_data。
        if condition_result is None:
            gaps.append(_gap("condition_result_null", str(condition_ref) if condition_ref else None, retryable=True))
        blocking = [g for g in gaps if g["reason"] not in ("condition_result_null",)]
        _task(
            ctx,
            effect_kind=c.EFFECT_VERIFY_DUE,
            evidence_refs=evidence_refs,
            question=f"「{label}」的条件 {condition_ref} 未能判定（{reason_label}）：补齐观测值后判定",
            discriminating=f"条件 {condition_ref} 所需观测值；当前缺口 {'；'.join(g['reason'] for g in gaps) or '未记录'}",
            completion=f"条件 {condition_ref} 在 01 下次 assess 中得到 true/false 判定，并对{version_note}记录复核动作",
            human_review_required=True,
            condition_result=c.CONDITION_UNKNOWN,
            availability=c.AVAIL_MISSING_DATA if blocking else c.AVAIL_ACTIONABLE,
            availability_reason=("补齐后可判定：" + "；".join(_gap_label(g) for g in blocking)) if blocking else None,
            gaps=gaps,
            **common,
        )
        return

    if change_type in ("content_changed", "source_corrected", "source_expired"):
        _task(
            ctx,
            effect_kind=c.EFFECT_REVIEW_CHANGED,
            evidence_refs=evidence_refs,
            question=f"「{label}」依赖的证据 {_labels(current or before)} 已变化（{reason_label}）：核对原判断是否仍成立",
            discriminating=f"前态 {_labels(before)} → 现态 {_labels(current)}；差异字段需核对",
            completion=f"读到 {_labels(current or before)} 并对{version_note}记录 reviewed_no_change 或 rejudge（收据绑定前后 hash）",
            human_review_required=False,
            condition_result=condition_result,
            availability=c.AVAIL_ACTIONABLE,
            availability_reason=None,
            gaps=gaps,
            **common,
        )
        return

    # dependency_missing
    gap_text = "；".join(_gap_label(g) for g in gaps) or reason_label
    _task(
        ctx,
        effect_kind=c.EFFECT_FILL_GAP,
        evidence_refs=evidence_refs,
        question=f"「{label}」依赖的证据 {_labels(before or current)} 无法解析（{reason_label}）：重新定位或确认失效",
        discriminating=f"缺口：{gap_text}",
        completion=f"依赖 {_labels(before or current)} 恢复为可解析版本（01 下次 assess 该项 change_type≠dependency_missing），或确认失效并解除绑定",
        human_review_required=False,
        condition_result=condition_result,
        availability=c.AVAIL_ACTIONABLE,
        availability_reason=None,
        gaps=gaps,
        **common,
    )


def _normalize_gap(gap: Any) -> dict[str, Any]:
    if isinstance(gap, str):
        return _gap(gap)
    if not isinstance(gap, dict) or not gap.get("reason"):
        raise c.ContractError("invalid_gap", "maintenance_item.gaps 项缺 reason")
    return {
        "reason": str(gap["reason"]),
        "ref": None if gap.get("ref") is None else str(gap["ref"]),
        "checked_at": None if gap.get("checked_at") is None else str(gap["checked_at"]),
        "retryable": gap.get("retryable") if isinstance(gap.get("retryable"), bool) else None,
    }


# ---------------------------------------------------------------------------
# research_project.load_project 投影
# ---------------------------------------------------------------------------


def _adapt_research_project(record: dict[str, Any], payload: Any, ctx: _Ctx) -> None:
    state = payload.to_dict() if hasattr(payload, "to_dict") else payload
    if not isinstance(state, dict):
        raise c.ContractError("invalid_source", "research_project payload 不是对象")
    if state.get("user_id") != ctx.owner:
        raise c.ContractError("owner_mismatch", "research_project 不属于当前用户")
    conversation_id = str(state.get("conversation_id") or record.get("id") or "")
    if not conversation_id:
        raise c.ContractError("invalid_source", "research_project 缺 conversation_id")
    version = None if state.get("updated_at") is None else str(state["updated_at"])
    as_of = state.get("as_of") or ctx.as_of
    subject = str(state.get("subject") or "")
    base_entities = [f"theme:{subject}"] if subject else []

    def _source(suffix: str) -> dict[str, Any]:
        return {
            "kind": SOURCE_RESEARCH_PROJECT,
            "id": f"{conversation_id}#{suffix}",
            "namespace": "research-project",
            "version_or_hash": version,
            "scope": {"conversation_id": conversation_id},
        }

    for trigger in state.get("triggers") or []:
        if not isinstance(trigger, dict):
            continue
        cid = str(trigger.get("id") or "")
        source = _source(f"checkpoint:{cid}")
        status = str(trigger.get("status") or "")
        if status in checkpoints_svc.TERMINAL_VERDICTS:
            ctx.skip(source, "verdict_recorded", f"可证伪点已裁决为 {status}")
            continue
        gaps = [_gap("object_version_unknown", f"checkpoint:{cid}", retryable=True)]
        cutoff = _cutoff_or_gap(ctx.knowledge_cutoff, gaps, field_name="knowledge_cutoff")
        due = trigger.get("due") or None
        if not due:
            gaps.append(_gap("due_missing", f"checkpoint:{cid}", retryable=False))
        themes = [str(t) for t in (trigger.get("themes") or ())]
        unverifiable = status == "unverifiable"
        claim = str(trigger.get("claim") or "")
        _task(
            ctx,
            source=source,
            effect_kind=c.EFFECT_VERIFY_DUE,
            object_refs=[
                {
                    "kind": "checkpoint",
                    "id": cid,
                    "namespace": "checkpoints",
                    "version_or_hash": None,
                    "scope": {"conversation_id": conversation_id},
                }
            ],
            evidence_refs=[],
            question=f"回检可证伪点「{claim}」" + (f"（到期 {due}）" if due else "（无到期日）"),
            discriminating=f"到期后的实际数据与 claim 比对；登记来源 {trigger.get('source') or '未记录'}"
            + (f"；题材 {'、'.join(themes)}" if themes else ""),
            completion=f"对 checkpoint {cid} 记录 verdict（hit/partial/miss/unverifiable）并附 checked_at"
            + ("；上次机器判不了，需人工核对" if unverifiable else ""),
            human_review_required=unverifiable,
            condition_result=c.CONDITION_UNKNOWN,
            availability=c.AVAIL_ACTIONABLE,
            availability_reason=None,
            as_of=as_of,
            knowledge_cutoff=cutoff,
            pit_grade=PIT_DAILY,
            gaps=gaps,
            conversation_id=conversation_id,
            entity_refs=[f"theme:{t}" for t in themes] or base_entities,
            due_at=due,
        )

    seen: set[str] = set()
    for followup in state.get("next_questions") or []:
        if not isinstance(followup, dict):
            continue
        text = str(followup.get("question") or followup.get("label") or followup.get("full_prompt") or "").strip()
        norm = c.normalize_text(text)
        digest = c.sha256_hex(norm)[:12]
        source = _source(f"followup:{digest}")
        if not text:
            ctx.skip(source, "empty_followup")
            continue
        if norm in seen:
            ctx.skip(source, "duplicate_followup", "同会话同文字的下一问只保留一条")
            continue
        seen.add(norm)
        gaps: list[dict[str, Any]] = []
        cutoff = _cutoff_or_gap(ctx.knowledge_cutoff, gaps, field_name="knowledge_cutoff")
        kind = str(followup.get("kind") or "")
        _task(
            ctx,
            source=source,
            effect_kind=c.EFFECT_FILL_GAP if kind == "gap_fill" else c.EFFECT_EXPLORE,
            object_refs=[],
            evidence_refs=[],
            question=text,
            discriminating=str(followup.get("rationale") or "下一问建议，未登记判别证据"),
            completion="人工确认该问题已得到有依据的回答并写入研究轮次",
            human_review_required=True,
            condition_result=None,
            availability=c.AVAIL_ACTIONABLE,
            availability_reason=None,
            as_of=as_of,
            knowledge_cutoff=cutoff,
            pit_grade=PIT_DAILY,
            gaps=gaps,
            conversation_id=conversation_id,
            entity_refs=base_entities,
        )
    for question in state.get("open_questions") or []:
        text = str(question or "").strip()
        norm = c.normalize_text(text)
        digest = c.sha256_hex(norm)[:12]
        source = _source(f"open_question:{digest}")
        if not text:
            continue
        if norm in seen:
            ctx.skip(source, "duplicate_open_question", "与下一问同文字，只保留一条")
            continue
        seen.add(norm)
        gaps = []
        cutoff = _cutoff_or_gap(ctx.knowledge_cutoff, gaps, field_name="knowledge_cutoff")
        _task(
            ctx,
            source=source,
            effect_kind=c.EFFECT_FILL_GAP,
            object_refs=[],
            evidence_refs=[],
            question=f"补齐未解问题：{text}",
            discriminating="上一轮研究登记的未解缺口，未绑定已登记判断",
            completion="人工确认该缺口已补齐并写入研究轮次",
            human_review_required=True,
            condition_result=None,
            availability=c.AVAIL_ACTIONABLE,
            availability_reason=None,
            as_of=as_of,
            knowledge_cutoff=cutoff,
            pit_grade=PIT_DAILY,
            gaps=gaps,
            conversation_id=conversation_id,
            entity_refs=base_entities,
        )


# ---------------------------------------------------------------------------
# research-queue/v1
# ---------------------------------------------------------------------------


def _adapt_research_queue(record: dict[str, Any], payload: Any, ctx: _Ctx) -> None:
    queue = research_queue_svc.extract_queue(payload)
    if queue is None:
        raise c.ContractError("invalid_source", "research_queue payload 不是队列产物")
    wrapped = isinstance(payload, dict) and isinstance(payload.get("research_queue"), dict)
    date = (payload.get("date") if wrapped else None) or record.get("as_of") or ctx.as_of
    generated_at = payload.get("generated_at") if wrapped else record.get("version_or_hash")
    for bucket, _label, _tone in research_queue_svc.QUEUE_SECTIONS:
        for item in queue.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            target = str(item.get("目标") or "-")
            source = {
                "kind": SOURCE_RESEARCH_QUEUE,
                "id": f"{date}:{bucket}:{target}",
                "namespace": research_queue_svc.SCHEMA_VERSION,
                "version_or_hash": "content_sha256:" + c.sha256_hex(c.canonical_json(item)),
                "scope": {"date": date},
            }
            if bucket == research_queue_svc.QUEUE_DOWNGRADE:
                ctx.skip(source, "downgrade_observe_only", "队列已判降级/观察：减少研究投入，不生成研究任务")
                continue
            gaps: list[dict[str, Any]] = []
            cutoff = _cutoff_or_gap(generated_at, gaps, field_name="knowledge_cutoff")
            if not date:
                gaps.append(_gap("as_of_missing", retryable=True))
            missing_layers = [str(x) for x in (item.get("缺失证据层") or [])]
            suggested = str(item.get("建议动作") or "人工复核")
            waiting = bucket == research_queue_svc.QUEUE_WAIT_MARKET
            _task(
                ctx,
                source=source,
                effect_kind=c.EFFECT_EXPLORE,
                object_refs=[],
                evidence_refs=[],
                question=f"{item.get('动作') or research_queue_svc.ACTION_LABELS.get(bucket, bucket)}：{target}",
                discriminating=("缺失证据层：" + "、".join(missing_layers)) if missing_layers else "未登记缺失证据层",
                completion=suggested,
                human_review_required=True,
                condition_result=None,
                availability=c.AVAIL_WAITING_RELEASE if waiting else c.AVAIL_ACTIONABLE,
                availability_reason=("等盘面验证：" + suggested) if waiting else None,
                as_of=date,
                knowledge_cutoff=cutoff,
                pit_grade=PIT_DAILY,
                gaps=gaps,
                conversation_id=ctx.conversation_id,
                entity_refs=[f"theme:{target}"],
            )
    skipped = queue.get("skipped") if isinstance(queue.get("skipped"), dict) else {}
    for key, items in skipped.items():
        for item in items or []:
            if not isinstance(item, dict):
                continue
            target = str(item.get("目标") or "-")
            ctx.skip(
                {
                    "kind": SOURCE_RESEARCH_QUEUE,
                    "id": f"{date}:skipped.{key}:{target}",
                    "namespace": research_queue_svc.SCHEMA_VERSION,
                    "version_or_hash": "content_sha256:" + c.sha256_hex(c.canonical_json(item)),
                    "scope": {"date": date},
                },
                f"queue_skipped:{key}",
                str(item.get("理由") or ""),
            )


# ---------------------------------------------------------------------------
# data_requests.DataRequest
# ---------------------------------------------------------------------------


def _adapt_data_request(record: dict[str, Any], payload: Any, ctx: _Ctx) -> None:
    request = payload.to_dict() if hasattr(payload, "to_dict") else payload
    if not isinstance(request, dict):
        raise c.ContractError("invalid_source", "data_request payload 不是对象")
    request_id = str(request.get("request_id") or "")
    if not request_id:
        raise c.ContractError("invalid_source", "data_request 缺 request_id")
    dataset = str(request.get("dataset") or "")
    window_start = str(request.get("window_start") or "")
    window_end = str(request.get("window_end") or "")
    fields = [str(f) for f in (request.get("fields") or [])]
    source = {
        "kind": SOURCE_DATA_REQUEST,
        "id": request_id,
        "namespace": "data-requests",
        "version_or_hash": "content_sha256:"
        + c.sha256_hex(c.canonical_json([dataset, window_start, window_end, sorted(fields)])),
        "scope": {"dataset": dataset, "window_start": window_start, "window_end": window_end},
    }
    status = record.get("status") or request.get("status")
    if status == data_requests_svc.STATUS_SATISFIED:
        ctx.skip(source, "already_satisfied", "补数请求已按 check_request 判 satisfied")
        return
    consumers = [
        consumer
        for consumer in (request.get("consumers") or [])
        if isinstance(consumer, dict) and consumer.get("user") == ctx.owner
    ]
    if not consumers:
        ctx.skip(source, "no_owner_consumer", "该请求没有当前用户的消费者")
        return
    route = request.get("fill_route") if isinstance(request.get("fill_route"), dict) else {}
    pending = route.get("mode") == data_requests_svc.ROUTE_PENDING_SYNC
    bindings = [dict(ref) for ref in (ctx.request_bindings.get(request_id) or [])]
    gaps: list[dict[str, Any]] = []
    cutoff = _cutoff_or_gap(request.get("last_asked_at"), gaps, field_name="knowledge_cutoff")
    if not bindings:
        gaps.append(_gap("dependency_unbound", request_id, retryable=True))
    table = str(request.get("table") or dataset)
    field_text = "、".join(fields) or "结构化数据"
    _task(
        ctx,
        source=source,
        effect_kind=c.EFFECT_FILL_GAP,
        object_refs=bindings,
        evidence_refs=[],
        question=f"补齐 {dataset} {window_start}..{window_end} 的 {field_text}",
        discriminating="；".join(str(s) for s in (request.get("sources_tried") or [])) or "库内该窗无行",
        completion=f"{table} 在 {window_start}..{window_end} 每个交易日有行且 {field_text} 非空（data_requests.check_request 判 satisfied）",
        human_review_required=False,
        condition_result=None,
        availability=c.AVAIL_MISSING_DATA if pending else c.AVAIL_ACTIONABLE,
        availability_reason=str(route.get("condition") or "等待数据源同步") if pending else None,
        as_of=window_end or None,
        knowledge_cutoff=cutoff,
        pit_grade=PIT_DAILY,
        gaps=gaps,
        conversation_id=str(consumers[0].get("conversation_id") or "") or ctx.conversation_id,
        entity_refs=[f"dataset:{dataset}"] if dataset else [],
    )


_HANDLERS: dict[str, Callable[[dict[str, Any], Any, _Ctx], None]] = {
    SOURCE_MAINTENANCE_ITEM: _adapt_maintenance_item,
    SOURCE_MAINTENANCE_REPORT: _adapt_maintenance_report,
    SOURCE_RESEARCH_PROJECT: _adapt_research_project,
    SOURCE_RESEARCH_QUEUE: _adapt_research_queue,
    SOURCE_DATA_REQUEST: _adapt_data_request,
}
