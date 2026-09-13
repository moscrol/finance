"""门面：把 01–05 的真模块组装成一个会话级投影与四类动作。

**只组装，不重写领域算法**（spec 06 §3）。每个判定都由对应 owner 的函数给出：

| 段 | 谁算的 |
|---|---|
| ``maintenance`` | ``judgment_maintenance.assess`` + ``reduce_actions`` |
| ``priority`` | ``research_priority.adapt_candidates`` → ``prioritize`` → ``render_view`` |
| ``diagnostics`` | ``research_diagnostics.diagnose`` |
| ``receipt_refs`` | 03 ``Repository`` / 05 收据的**引用**（读正文要先过曝光登记） |

三条纪律：

1. **知识截止两次取数**。绑定时按 ``baseline_cutoff`` 解析到的版本原样存进绑定记录；view 时按**今天**的
   cutoff 重新读**同一个 ref**（同一 ``as_of`` 的切片）。我们从不声称知道原判断当天的版本——
   那正是 01 的 baseline gap 要挡住的东西。
2. **UNKNOWN 不塌成 0**。模块缺输入 → ``unknown`` / ``pending`` + gap；模块异常 → ``error``；
   两者都不写成空数组（spec §4.4 末句）。
3. **动作不冒充事实**。``reviewed_no_change`` 只关闭维护项，不改原判断；``link_run`` 必须指到
   原写入者写下的新判断行，否则拒绝关闭。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from intelligence.services.research_evolution import adapters as re_adapters
from intelligence.services.research_evolution.access import OwnerContext
from intelligence.services.research_evolution.contracts import (
    ACTION_CANCEL_REJUDGE,
    ACTION_LINK_RUN,
    ACTION_READ_RECEIPT,
    ACTION_REJUDGE,
    ACTION_REVEAL_EXERCISE,
    ACTION_REVIEWED_NO_CHANGE,
    ACTION_SELECT_TASK,
    ACTION_SNOOZE,
    ACTION_SUBMIT_EXERCISE,
    ACTIONS,
    BINDING_RECORD_SCHEMA,
    CONTINUATION_SCHEMA,
    ERR_ACTION_REJECTED,
    ERR_BINDING_REJECTED,
    ERR_DEPENDENCY_MISSING,
    ERR_EXPOSURE_CONFLICT,
    ERR_IDEMPOTENCY_MISMATCH,
    ERR_INVALID_REQUEST,
    ERR_MODULE_UNAVAILABLE,
    ERR_NOT_FOUND,
    ERR_REF_UNRESOLVABLE,
    ERR_RUN_BINDING_MISMATCH,
    ERR_INVALID_TRANSITION,
    ERR_VERSION_CONFLICT,
    MAINTENANCE_ACTIONS,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_PENDING,
    STATUS_UNAVAILABLE,
    STATUS_UNKNOWN,
    SELF_USE_PROTOCOL_VERSION,
    ApiError,
    ModuleStatus,
    digest,
    ensure_aware,
    envelope,
    gap,
    stable_id,
    utc_iso,
)
from intelligence.services.research_evolution.store import (
    PROTOCOLS_DIR,
    RECEIPTS_DIR,
    REGISTRATIONS_DIR,
    SUMMARIES_DIR,
    EvolutionStore,
)

DIAGNOSTICS_WINDOW_DAYS = 90
POLICY_FILE = "diagnostics_policy.json"
EXERCISE_PACK_FILE = "exercise_pack.json"


def _shanghai() -> Any:
    from intelligence.services.research_validation.contracts import SHANGHAI

    return SHANGHAI


# --------------------------------------------------------------------------- #
# 注入资源
# --------------------------------------------------------------------------- #
@dataclass
class Resources:
    """由 ``create_app`` 注入。服务不从 cwd 推断任何生产根。"""

    evidence_source: re_adapters.EvidenceSource
    conversation_store_for: Callable[[str], Any]
    run_store_for: Callable[[str], Any]
    finance_root: Path | None = None
    code_sha: str = ""
    clock: Callable[[], datetime] = field(default_factory=lambda: (lambda: datetime.now(_shanghai())))


class ResearchEvolutionService:
    def __init__(self, resources: Resources) -> None:
        self.res = resources

    # ---- 基础 -------------------------------------------------------------- #
    def _now(self) -> datetime:
        return ensure_aware(self.res.clock(), where="clock")

    def _store(self, ctx: OwnerContext) -> EvolutionStore:
        return EvolutionStore(ctx.evolution_root, ctx.owner_user_id)

    def _conversation(self, ctx: OwnerContext, conversation_id: str) -> Any:
        from intelligence.services.research_evolution.access import conversation_scope

        store = self.res.conversation_store_for(ctx.owner_user_id)
        return conversation_scope(store.load_conversation, ctx, conversation_id)

    # ---- 维护段 ------------------------------------------------------------ #
    def _maintenance(
        self,
        ctx: OwnerContext,
        store: EvolutionStore,
        *,
        as_of: str,
        knowledge_cutoff: str,
        now: datetime,
        conversation_id: str | None,
    ) -> tuple[dict[str, Any] | None, ModuleStatus, list[dict[str, Any]]]:
        from intelligence.services.judgment_maintenance import (
            MaintenanceContractError,
            assess,
            reduce_actions,
        )

        gaps: list[dict[str, Any]] = []
        records = store.list_bindings()
        scoped = [
            r
            for r in records
            if conversation_id is None
            or str((r.get("binding") or {}).get("object_ref", {}).get("scope", {}).get("conversation_id") or "") == conversation_id
        ]
        if not scoped:
            return (
                None,
                ModuleStatus(STATUS_UNKNOWN, reason="no_bindings"),
                [gap("dependency_unbound", checked_at=knowledge_cutoff, retryable=True, module="maintenance", detail="本会话还没有建立证据依赖；旧记录没有完整依据，尚不能比较变化")],
            )

        bindings: list[dict[str, Any]] = []
        versions: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        seen_versions: set[str] = set()
        entities_for_conditions: set[str] = set()
        unreadable = 0

        for record in scoped:
            binding = dict(record["binding"])
            source = dict(record.get("source") or {})
            entity = str(source.get("entity") or "")
            slice_as_of = str(source.get("as_of") or "")
            if not entity or not slice_as_of:
                gaps.append(gap("binding_source_unknown", ref=str(binding.get("binding_id")), checked_at=knowledge_cutoff, retryable=False, module="maintenance", detail="绑定记录没有记下取数实体与交易日，无法按同一引用重读当前版本"))
                unreadable += 1
                continue
            # 今天的 cutoff 下，同一 as_of 切片里同一引用的当前版本。
            catalog = self.res.evidence_source.catalog(owner_user_id=ctx.owner_user_id, entity=entity, as_of=slice_as_of, knowledge_cutoff=knowledge_cutoff)
            if not catalog.available:
                gaps.append(gap(f"evidence_source_{catalog.reason or 'unavailable'}", ref=str(binding.get("binding_id")), checked_at=knowledge_cutoff, retryable=True, module="maintenance", detail=f"实体 {entity} 在 {slice_as_of} 的当前版本读不到，本条依赖只能保持未知"))
                unreadable += 1
                continue
            # 只有通过当前重读的绑定才喂给 01：基线版本与绑定一起进 assess。
            # 读不到当前版本的绑定**不喂**——只喂基线会让 01 判出「没有变化」，
            # 把「现在读不到」伪装成「现在没问题」（spec §4.4：错误不能被空数组掩盖）。
            bindings.append(binding)
            if binding.get("conditions"):
                entities_for_conditions.add(entity)
            # 1) 绑定时解析到的真实版本（baseline）。
            for version in source.get("evidence_versions") or []:
                key = digest(version)
                if key not in seen_versions:
                    seen_versions.add(key)
                    versions.append(dict(version))
            # 2) 当前版本。
            bound = set(binding.get("baseline_evidence_refs") or [])
            for version in catalog.versions:
                if version["ref"] not in bound:
                    continue
                clean = {k: v for k, v in version.items() if not k.startswith("_")}
                key = digest(clean)
                if key not in seen_versions:
                    seen_versions.add(key)
                    versions.append(clean)

        for entity in sorted(entities_for_conditions):
            if not entity:
                continue
            today_catalog = self.res.evidence_source.catalog(owner_user_id=ctx.owner_user_id, entity=entity, as_of=as_of, knowledge_cutoff=knowledge_cutoff)
            observations.extend(dict(o) for o in today_catalog.observations)
            if not today_catalog.available:
                gaps.append(gap(f"observation_source_{today_catalog.reason or 'unavailable'}", ref=entity, checked_at=knowledge_cutoff, retryable=True, module="maintenance", detail=f"{as_of} 读不到 {entity} 的盘面观测，显式条件只能保持未知"))

        try:
            report = assess(
                owner_user_id=ctx.owner_user_id,
                as_of=as_of,
                knowledge_cutoff=knowledge_cutoff,
                bindings=bindings,
                evidence_versions=versions,
                condition_observations=observations,
                policy={"schema_version": "judgment-maintenance-policy/v1"},
                generated_at=utc_iso(now),
            )
            folded = reduce_actions(report=report, events=store.list_events(), now=utc_iso(now))
        except MaintenanceContractError as exc:
            return (
                None,
                ModuleStatus(STATUS_ERROR, reason=exc.code, detail={"where": exc.where}),
                gaps + [gap("maintenance_contract_error", ref=exc.where, checked_at=knowledge_cutoff, retryable=False, module="maintenance", detail=str(exc))],
            )
        if unreadable:
            # 有绑定读不到当前版本：报告只覆盖可读的那部分，模块状态如实降级成 unknown。
            if not bindings:
                return (
                    None,
                    ModuleStatus(STATUS_UNKNOWN, reason="current_source_unreadable", detail={"excluded": unreadable}),
                    gaps,
                )
            return folded.to_dict(), ModuleStatus(STATUS_UNKNOWN, reason="current_source_unreadable", detail={"excluded": unreadable}), gaps
        return folded.to_dict(), ModuleStatus(STATUS_OK), gaps

    # ---- 排序段 ------------------------------------------------------------ #
    def _priority(
        self,
        ctx: OwnerContext,
        *,
        maintenance_report: Mapping[str, Any] | None,
        conversation_id: str,
        as_of: str,
        knowledge_cutoff: str,
        now: datetime,
        budget_minutes: float | None,
    ) -> tuple[dict[str, Any] | None, ModuleStatus, list[dict[str, Any]]]:
        from intelligence.services import research_project
        from intelligence.services.research_priority import (
            ContractError,
            adapt_candidates,
            prioritize,
            render_view,
        )

        gaps: list[dict[str, Any]] = []
        project_state: dict[str, Any] | None = None
        try:
            state = research_project.load_project(
                self.res.conversation_store_for(ctx.owner_user_id),
                self.res.run_store_for(ctx.owner_user_id),
                conversation_id,
            )
            project_state = state.to_dict()
        except (FileNotFoundError, ValueError, OSError) as exc:
            gaps.append(gap("research_project_unavailable", ref=conversation_id, checked_at=knowledge_cutoff, retryable=True, module="priority", detail=str(exc)))

        queue_path, queue_payload = re_adapters.load_research_queue_for(self.res.finance_root, as_of=as_of)
        if queue_path is None:
            gaps.append(gap("research_queue_absent", checked_at=knowledge_cutoff, retryable=True, module="priority", detail="没有找到 ≤ 当日的日更研究队列；缺队列是如实状态，不补造"))

        records = re_adapters.priority_source_records(
            maintenance_report=maintenance_report,
            project_state=project_state,
            research_queue=queue_payload or None,
        )
        if not records:
            return None, ModuleStatus(STATUS_UNKNOWN, reason="no_sources"), gaps

        try:
            candidates = adapt_candidates(
                records,
                {
                    "owner_user_id": ctx.owner_user_id,
                    "conversation_id": conversation_id,
                    "as_of": as_of,
                    "knowledge_cutoff": knowledge_cutoff,
                },
            )
            report = prioritize(candidates, None, {"minutes": budget_minutes}, utc_iso(now), owner_user_id=ctx.owner_user_id)
            view = render_view(report)
        except ContractError as exc:
            return None, ModuleStatus(STATUS_ERROR, reason=exc.code), gaps + [gap("priority_contract_error", checked_at=knowledge_cutoff, retryable=False, module="priority", detail=str(exc))]
        view["skipped"] = candidates.get("skipped", [])
        return view, ModuleStatus(STATUS_OK), gaps

    # ---- 诊断段 ------------------------------------------------------------ #
    def _diagnostics(
        self,
        ctx: OwnerContext,
        store: EvolutionStore,
        *,
        maintenance_report: Mapping[str, Any] | None,
        as_of: str,
        knowledge_cutoff: str,
        now: datetime,
    ) -> tuple[dict[str, Any] | None, ModuleStatus, list[dict[str, Any]]]:
        from intelligence.services.research_diagnostics import (
            DiagnosticsInputError,
            diagnose,
            parse_exercise_pack,
        )
        from intelligence.services.research_diagnostics import adapters as rd_adapters

        gaps: list[dict[str, Any]] = []
        policy_raw = store.read_immutable(REGISTRATIONS_DIR, "diagnostics_policy")
        if policy_raw is None:
            return (
                None,
                ModuleStatus(STATUS_UNKNOWN, reason="policy_not_registered"),
                [gap("diagnostics_policy_missing", checked_at=knowledge_cutoff, retryable=True, module="diagnostics", detail="尚未登记生产诊断策略（规则生效日由方法 owner 决定），暂无法诊断")],
            )
        policy = dict(policy_raw.get("policy") or {})
        synthetic = str(policy_raw.get("provenance") or policy.get("provenance") or "") == "synthetic"

        legacy = rd_adapters.load_legacy_inputs(
            owner_user_id=ctx.owner_user_id,
            checkpoints_path=ctx.user_root / "checkpoints.jsonl",
            verdicts_path=ctx.user_root / "verdicts.jsonl",
            judgments_path=ctx.user_root / "judgments.jsonl",
            scripts_path=ctx.user_root / "observation_scripts.jsonl",
            trees_path=ctx.user_root / "scenario_trees.jsonl",
        )
        receipts = [dict(r["receipt"]) for r in store.list_process_receipts() if isinstance(r.get("receipt"), dict)]
        pack_raw = store.read_immutable(REGISTRATIONS_DIR, "exercise_pack")
        cases: Any = None
        if pack_raw is not None:
            try:
                cases = parse_exercise_pack(dict(pack_raw.get("pack") or {}))
            except DiagnosticsInputError as exc:
                gaps.append(gap("exercise_pack_invalid", checked_at=knowledge_cutoff, retryable=False, module="diagnostics", detail=str(exc)))
        else:
            gaps.append(gap("exercise_pack_absent", checked_at=knowledge_cutoff, retryable=True, module="diagnostics", detail="尚未登记历史题包，报告不带练习"))

        start = (date_cls.fromisoformat(as_of) - timedelta(days=DIAGNOSTICS_WINDOW_DAYS)).isoformat()
        try:
            report = diagnose(
                owner_user_id=ctx.owner_user_id,
                start=start,
                end=as_of,
                knowledge_cutoff=knowledge_cutoff,
                records=legacy.records,
                verdicts=legacy.verdicts,
                maintenance_reports=[dict(maintenance_report)] if maintenance_report else (),
                process_receipts=receipts,
                exercise_cases=cases,
                policy=policy,
                generated_at=utc_iso(now),
            )
        except DiagnosticsInputError as exc:
            return None, ModuleStatus(STATUS_ERROR, reason="diagnostics_input_error"), gaps + [gap("diagnostics_input_error", checked_at=knowledge_cutoff, retryable=False, module="diagnostics", detail=str(exc))]

        # 04 的 Gap 没有 ``checked_at``（它的 gap 挂在报告的 knowledge_cutoff 上），01/02 的有。
        # 投影层按封套口径补上本次的截止，不改两边语义（两种形状的分歧记在 02 的 BLOCKED 里）。
        for g in legacy.gaps:
            gaps.append(gap(g.reason, ref=g.ref, checked_at=knowledge_cutoff, retryable=g.retryable, module="diagnostics", detail=g.detail))
        payload = report.to_dict() if hasattr(report, "to_dict") else report
        return payload, ModuleStatus(STATUS_OK, synthetic=synthetic), gaps

    # ---- 收据引用 ----------------------------------------------------------- #
    def _receipt_refs(
        self, ctx: OwnerContext, store: EvolutionStore, *, knowledge_cutoff: str
    ) -> tuple[dict[str, Any], dict[str, ModuleStatus], list[dict[str, Any]]]:
        gaps: list[dict[str, Any]] = []
        refs: dict[str, Any] = {"validation": [], "product_value": []}
        statuses: dict[str, ModuleStatus] = {}

        # 03：真实前向实验。未到期照样显示 pending，普通面板不出现概率承诺。
        try:
            from intelligence.services.research_validation import Repository

            repo = Repository(ctx.validation_root, owner_user_id=ctx.owner_user_id)
            study_ids = repo.list_studies()
            pending = 0
            for study_id in study_ids:
                for receipt in repo.list_receipts(study_id):
                    status = str(receipt.get("empirical_status") or "unknown")
                    pending += 1 if status == "pending" else 0
                    refs["validation"].append(
                        {
                            "kind": "method_validation_receipt",
                            "study_id": study_id,
                            "receipt_id": receipt.get("id"),
                            "empirical_status": status,
                            "synthetic": bool(receipt.get("synthetic")),
                            # 正文要经曝光登记才读；这里只给引用与状态。
                            "readable_via": "POST /api/conversations/{id}/research-evolution/actions?action=reveal_exercise|read_receipt",
                        }
                    )
            if not study_ids:
                statuses["validation_receipts"] = ModuleStatus(STATUS_UNKNOWN, reason="no_study_frozen")
                gaps.append(gap("no_forward_study", checked_at=knowledge_cutoff, retryable=True, module="validation_receipts", detail="尚未冻结任何真实前向协议，方法有效性保持未验"))
            elif pending:
                statuses["validation_receipts"] = ModuleStatus(STATUS_PENDING, reason="future_not_due", detail={"pending_receipts": pending})
            else:
                statuses["validation_receipts"] = ModuleStatus(STATUS_OK)
        except ImportError:
            statuses["validation_receipts"] = ModuleStatus(STATUS_UNAVAILABLE, reason="module_missing")
        except (OSError, ValueError) as exc:
            statuses["validation_receipts"] = ModuleStatus(STATUS_ERROR, reason="repository_error", detail={"detail": str(exc)})
            gaps.append(gap("validation_repository_error", checked_at=knowledge_cutoff, retryable=True, module="validation_receipts", detail=str(exc)))

        # 05：使用测量收据与总结。
        try:
            receipts = store.list_immutable(RECEIPTS_DIR)
            summaries = store.list_immutable(SUMMARIES_DIR)
            for receipt in receipts:
                refs["product_value"].append(
                    {
                        "kind": "measurement_receipt",
                        "receipt_id": receipt.get("receipt_id") or receipt.get("id"),
                        "status": receipt.get("status"),
                        "case_pair_id": receipt.get("case_pair_id"),
                        "provenance": (receipt.get("provenance") or {}).get("kind") if isinstance(receipt.get("provenance"), dict) else receipt.get("provenance"),
                    }
                )
            for summary in summaries:
                refs["product_value"].append(
                    {
                        "kind": "pilot_summary",
                        "summary_id": summary.get("summary_id") or summary.get("id"),
                        "engineering_status": summary.get("engineering_status"),
                        "field_status": summary.get("field_status"),
                        "commercial_status": summary.get("commercial_status"),
                    }
                )
            if not receipts and not summaries:
                statuses["product_value_receipts"] = ModuleStatus(STATUS_UNKNOWN, reason="no_measurement_yet")
                gaps.append(gap("no_product_value_receipt", checked_at=knowledge_cutoff, retryable=True, module="product_value_receipts", detail="尚无测量收据；真人效果与付费状态保持未开始"))
            else:
                statuses["product_value_receipts"] = ModuleStatus(STATUS_OK)
        except ApiError:
            raise
        except (OSError, ValueError) as exc:
            statuses["product_value_receipts"] = ModuleStatus(STATUS_ERROR, reason="store_error", detail={"detail": str(exc)})
            gaps.append(gap("product_value_store_error", checked_at=knowledge_cutoff, retryable=True, module="product_value_receipts", detail=str(exc)))

        return refs, statuses, gaps

    # ---- GET 投影 ----------------------------------------------------------- #
    def view(
        self,
        *,
        ctx: OwnerContext,
        conversation_id: str,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        budget_minutes: float | None = None,
        store: EvolutionStore | None = None,
    ) -> dict[str, Any]:
        """读取无业务写副作用：不改原判断、不登记完成、不触发模型调用。

        ``store`` 由已持有事务的调用方（动作路径）传入：锁内重读必须用同一把锁里的
        同一个 store 实例，新实例会去抢同一把进程锁 → 死锁。
        """
        self._conversation(ctx, conversation_id)
        now = self._now()
        day = now.astimezone(_shanghai()).date().isoformat()
        as_of = as_of or day
        knowledge_cutoff = knowledge_cutoff or as_of
        store = store or self._store(ctx)

        statuses: dict[str, ModuleStatus] = {}
        gaps: list[dict[str, Any]] = []

        maintenance, statuses["maintenance"], m_gaps = self._maintenance(
            ctx, store, as_of=as_of, knowledge_cutoff=knowledge_cutoff, now=now, conversation_id=conversation_id
        )
        gaps.extend(m_gaps)

        priority, statuses["priority"], p_gaps = self._priority(
            ctx,
            maintenance_report=maintenance,
            conversation_id=conversation_id,
            as_of=as_of,
            knowledge_cutoff=knowledge_cutoff,
            now=now,
            budget_minutes=budget_minutes,
        )
        gaps.extend(p_gaps)

        diagnostics, statuses["diagnostics"], d_gaps = self._diagnostics(
            ctx, store, maintenance_report=maintenance, as_of=as_of, knowledge_cutoff=knowledge_cutoff, now=now
        )
        gaps.extend(d_gaps)

        receipt_refs, receipt_statuses, r_gaps = self._receipt_refs(ctx, store, knowledge_cutoff=knowledge_cutoff)
        statuses.update(receipt_statuses)
        gaps.extend(r_gaps)

        bound_refs = {
            str((r.get("binding") or {}).get("object_ref", {}).get("ref")): str(r.get("binding_id"))
            for r in store.list_bindings()
        }
        ledgers = re_adapters.load_legacy_ledgers(ctx.user_root)
        trackable = re_adapters.trackable_objects(
            ledgers,
            owner_user_id=ctx.owner_user_id,
            baseline_cutoff=knowledge_cutoff,
            bound_refs=bound_refs,
            conversation_id=conversation_id,
        )
        for warning in ledgers.warnings:
            gaps.append(gap("legacy_ledger_warning", checked_at=knowledge_cutoff, retryable=True, module="maintenance", detail=warning))

        inputs = {
            "as_of": as_of,
            "knowledge_cutoff": knowledge_cutoff,
            "budget_minutes": budget_minutes,
            "bindings": len(bound_refs),
            "trackable_objects": [t.to_dict() for t in trackable],
        }
        return envelope(
            owner_user_id=ctx.owner_user_id,
            conversation_id=conversation_id,
            generated_at=utc_iso(now),
            maintenance=maintenance,
            priority=priority,
            diagnostics=diagnostics,
            receipt_refs=receipt_refs,
            module_status=statuses,
            gaps=gaps,
            inputs=inputs,
            view_version=self.res.code_sha or "unknown",
        )

    # ---- 证据目录（建立绑定前给用户选） --------------------------------------- #
    def evidence_catalog(self, *, ctx: OwnerContext, entity: str, as_of: str, knowledge_cutoff: str | None = None) -> dict[str, Any]:
        cutoff = knowledge_cutoff or as_of
        catalog = self.res.evidence_source.catalog(owner_user_id=ctx.owner_user_id, entity=entity, as_of=as_of, knowledge_cutoff=cutoff)
        return {
            "entity": catalog.entity,
            "as_of": catalog.as_of,
            "knowledge_cutoff": catalog.knowledge_cutoff,
            "available": catalog.available,
            "reason": catalog.reason,
            "pit_grade": catalog.pit_grade,
            "versions": [dict(v) for v in catalog.versions],
            "labels": list(re_adapters.SLICE_EVALUABLE_LABELS),
            "gaps": [dict(g) for g in catalog.gaps],
        }

    # ---- 建立绑定 ----------------------------------------------------------- #
    def create_binding(self, *, ctx: OwnerContext, conversation_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """用户明确「从现在开始跟踪」：服务端解析真实 hash/版本，保存真实 created_at 与 baseline_cutoff。

        原判断的日期一个字节都不改；``created_at`` 是**现在**，不追溯补成当时已知。
        """
        from intelligence.services.judgment_maintenance import MaintenanceContractError
        from intelligence.services.judgment_maintenance.contracts import parse_binding

        self._conversation(ctx, conversation_id)
        now = self._now()
        object_ref = body.get("object_ref")
        if not isinstance(object_ref, Mapping):
            raise ApiError(ERR_INVALID_REQUEST, "缺少 object_ref", detail={"where": "object_ref"})
        entity = str(body.get("entity") or "").strip()
        slice_as_of = str(body.get("as_of") or "").strip()
        refs = body.get("evidence_refs")
        if not entity or not slice_as_of:
            raise ApiError(ERR_INVALID_REQUEST, "必须指明取数实体与交易日", detail={"where": "entity/as_of"})
        if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)) or not refs:
            raise ApiError(ERR_INVALID_REQUEST, "必须至少选择一条证据引用", detail={"where": "evidence_refs"})

        store = self._store(ctx)
        ledgers = re_adapters.load_legacy_ledgers(ctx.user_root)
        bound_refs = {
            str((r.get("binding") or {}).get("object_ref", {}).get("ref")): str(r.get("binding_id"))
            for r in store.list_bindings()
        }
        trackable = re_adapters.trackable_objects(
            ledgers,
            owner_user_id=ctx.owner_user_id,
            baseline_cutoff=now.astimezone(_shanghai()).date().isoformat(),
            bound_refs=bound_refs,
            conversation_id=None,
        )
        target = re_adapters.find_trackable(trackable, object_ref)

        baseline_cutoff = now.astimezone(_shanghai()).date().isoformat()
        catalog = self.res.evidence_source.catalog(owner_user_id=ctx.owner_user_id, entity=entity, as_of=slice_as_of, knowledge_cutoff=baseline_cutoff)
        if not catalog.available:
            raise ApiError(ERR_REF_UNRESOLVABLE, "读不到该实体当日的证据目录，无法解析真实版本", detail={"entity": entity, "as_of": slice_as_of, "reason": catalog.reason})
        available = catalog.by_ref()
        chosen: list[dict[str, Any]] = []
        missing: list[str] = []
        for raw in refs:
            ref = str(raw).strip()
            version = available.get(ref)
            if version is None:
                missing.append(ref)
                continue
            chosen.append({k: v for k, v in version.items() if not k.startswith("_")})
        if missing:
            raise ApiError(ERR_REF_UNRESOLVABLE, "选中的引用不在受控目录中", detail={"refs": missing})

        conditions = body.get("conditions") or []
        binding_id = stable_id("bind", {"owner": ctx.owner_user_id, "object": target.object_ref.get("ref"), "refs": sorted(v["ref"] for v in chosen), "entity": entity, "as_of": slice_as_of})
        # 幂等重试（R8）：先按 binding_id 定位已提交记录。命中且**客户端业务载荷**一致 →
        # 直接返回原记录（服务端时间与解析到的基线都是首次提交时的，不随重试的时钟推进漂）；
        # 业务载荷不一致 → 冲突，不静默复用。
        business_payload = {
            "object_ref": {**dict(target.object_ref), "scope": {**dict(target.object_ref.get("scope") or {}), "conversation_id": conversation_id}},
            "entity": entity,
            "as_of": slice_as_of,
            "evidence_refs": sorted(str(v["ref"]) for v in chosen),
            "conditions": list(conditions),
            "binding_origin": str(body.get("binding_origin") or "user_confirmed"),
        }
        existing = store.find_binding(binding_id)
        if existing is not None:
            existing_binding = dict(existing.get("binding") or {})
            existing_source = dict(existing.get("source") or {})
            existing_business = {
                "object_ref": existing_binding.get("object_ref"),
                "entity": str(existing_source.get("entity") or ""),
                "as_of": str(existing_source.get("as_of") or ""),
                "evidence_refs": sorted(str(r) for r in (existing_binding.get("baseline_evidence_refs") or [])),
                "conditions": list(existing_binding.get("conditions") or []),
                "binding_origin": str(existing_binding.get("binding_origin") or "user_confirmed"),
            }
            if digest(existing_business) != digest(business_payload):
                raise ApiError(
                    ERR_IDEMPOTENCY_MISMATCH,
                    "同一绑定 id 已绑定不同业务载荷，不得复用",
                    detail={"binding_id": binding_id},
                )
            return {
                "schema_version": BINDING_RECORD_SCHEMA,
                "created": False,
                "binding_id": existing["binding_id"],
                "binding": existing_binding,
                "baseline_cutoff": existing_binding.get("baseline_cutoff"),
                "created_at": existing.get("created_at"),
                "pit_grade": existing_source.get("pit_grade"),
            }
        payload = {
            "schema_version": "judgment-maintenance-binding/v1",
            "binding_id": binding_id,
            "binding_version": 1,
            "owner_user_id": ctx.owner_user_id,
            "object_ref": {**dict(target.object_ref), "scope": {**dict(target.object_ref.get("scope") or {}), "conversation_id": conversation_id}},
            "baseline_evidence_refs": [v["ref"] for v in chosen],
            "baseline_source_hashes": {v["ref"]: v.get("source_hash") for v in chosen},
            "baseline_cutoff": baseline_cutoff,
            "created_at": utc_iso(now),
            "binding_origin": str(body.get("binding_origin") or "user_confirmed"),
            "conditions": list(conditions),
        }
        try:
            binding = parse_binding(payload, owner_user_id=ctx.owner_user_id, where="binding")
        except MaintenanceContractError as exc:
            raise ApiError(ERR_BINDING_REJECTED, "绑定不合法", detail={"code": exc.code, "where": exc.where, "detail": str(exc)}) from None

        with store.transaction() as txn:
            stored, created = txn.append_binding(
                binding.to_dict(),
                created_at=utc_iso(now),
                source={"entity": entity, "as_of": slice_as_of, "evidence_versions": chosen, "pit_grade": catalog.pit_grade, "conversation_id": conversation_id},
            )
        return {
            "schema_version": BINDING_RECORD_SCHEMA,
            "created": created,
            "binding_id": stored["binding_id"],
            "binding": stored["binding"],
            "baseline_cutoff": baseline_cutoff,
            "created_at": stored["created_at"],
            "pit_grade": catalog.pit_grade,
        }

    # ---- 动作 -------------------------------------------------------------- #
    def apply_action(self, *, ctx: OwnerContext, conversation_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        self._conversation(ctx, conversation_id)
        action = str(body.get("action") or "").strip()
        if action not in ACTIONS:
            raise ApiError(ERR_INVALID_REQUEST, "未知动作", detail={"action": action, "allowed": list(ACTIONS)})
        idempotency_key = str(body.get("idempotency_key") or "").strip()
        if not idempotency_key:
            raise ApiError(ERR_INVALID_REQUEST, "缺少 idempotency_key", detail={"where": "idempotency_key"})

        if action in MAINTENANCE_ACTIONS or action in (ACTION_LINK_RUN, ACTION_CANCEL_REJUDGE):
            return self._maintenance_action(ctx=ctx, conversation_id=conversation_id, action=action, idempotency_key=idempotency_key, body=body)
        if action == ACTION_SELECT_TASK:
            return self._select_task(ctx=ctx, conversation_id=conversation_id, idempotency_key=idempotency_key, body=body)
        if action == ACTION_REVEAL_EXERCISE:
            return self._reveal_exercise(ctx=ctx, conversation_id=conversation_id, idempotency_key=idempotency_key, body=body)
        if action == ACTION_SUBMIT_EXERCISE:
            return self._submit_exercise(ctx=ctx, conversation_id=conversation_id, idempotency_key=idempotency_key, body=body)
        if action == ACTION_READ_RECEIPT:
            return self._read_receipt(ctx=ctx, conversation_id=conversation_id, idempotency_key=idempotency_key, body=body)
        raise ApiError(ERR_INVALID_REQUEST, "未知动作", detail={"action": action})

    def _current_items(self, ctx: OwnerContext, conversation_id: str, *, as_of: str | None, knowledge_cutoff: str | None, store: EvolutionStore | None = None) -> dict[str, Any]:
        view = self.view(ctx=ctx, conversation_id=conversation_id, as_of=as_of, knowledge_cutoff=knowledge_cutoff, store=store)
        maintenance = view.get("maintenance")
        if not isinstance(maintenance, dict):
            raise ApiError(ERR_MODULE_UNAVAILABLE, "维护报告当前不可用，动作无法落到具体维护项", detail={"module_status": view.get("module_status", {}).get("maintenance")})
        return maintenance

    def _maintenance_action(
        self, *, ctx: OwnerContext, conversation_id: str, action: str, idempotency_key: str, body: Mapping[str, Any]
    ) -> dict[str, Any]:
        """维护动作：读 - 判 - 追加全部在同一把锁内完成（store.py 的事务纪律，QC S1）。

        锁外做版本校验、进锁只查幂等键，会让两个同版本请求都拿到 accepted、台账写两行、
        重建只应用一行。这里把当前项重读、版本校验、01 验证、追加全放进一个事务。
        """
        from intelligence.services.judgment_maintenance import validate_action
        from intelligence.services.judgment_maintenance.contracts import ManagementEvent

        now = self._now()
        store = self._store(ctx)
        item_id = str(body.get("item_id") or "").strip()
        if not item_id:
            raise ApiError(ERR_INVALID_REQUEST, "缺少 item_id", detail={"where": "item_id"})

        # 会话作用域绑进幂等摘要（R10）：同键同载荷换了个会话路径不是重放，是串单。
        payload_digest = digest({"conversation_id": conversation_id, **{k: v for k, v in body.items() if k != "idempotency_key"}})

        with store.transaction() as txn:
            existing = txn.find_action(idempotency_key)
            if existing is not None:
                if existing.get("payload_digest") != payload_digest or str(existing.get("conversation_id") or "") != conversation_id:
                    raise ApiError(ERR_IDEMPOTENCY_MISMATCH, "同一幂等键已绑定不同载荷或不同会话", detail={"idempotency_key": idempotency_key})
                return {"replayed": True, **dict(existing.get("result") or {})}

            # 锁内重读当前项：validate 时的版本必须是提交时的版本。
            maintenance = self._current_items(ctx, conversation_id, as_of=body.get("as_of"), knowledge_cutoff=body.get("knowledge_cutoff"), store=txn)
            item = next((i for i in maintenance.get("items", []) if str(i.get("id")) == item_id), None)
            if item is None:
                raise ApiError(ERR_DEPENDENCY_MISSING, "该维护项不在当前报告中，请刷新后重试", detail={"item_id": item_id})

            expected_item_version = str(body.get("expected_item_version") or "")
            expected_revision = body.get("expected_management_revision")
            # ``expected_revision or -1`` 会把合法的修订号 **0** 当成缺省——每条维护项的第一个动作
            # 都会被判成版本冲突，而错误信息里前后两个数还一模一样，看起来像并发。只能显式比 None。
            current_revision = int(item.get("management_revision") or 0)
            if expected_item_version != str(item.get("item_version")) or (
                expected_revision is None or int(expected_revision) != current_revision
            ):
                raise ApiError(
                    ERR_VERSION_CONFLICT,
                    "页面版本已过期，变化已更新",
                    detail={"item_id": item_id, "current_item_version": item.get("item_version"), "current_management_revision": item.get("management_revision")},
                )

            if action == ACTION_LINK_RUN:
                event, link_detail = self._link_run_event(ctx=ctx, conversation_id=conversation_id, item=item, body=body, now=now, store=txn)
                if event is None:
                    # run 未终态：只登记「本次维护请求发起了这个 run」的持久化关联（接受 ≠ 完成）。
                    return {"replayed": False, "status": "registered", "reason_code": "run_registered", "item_id": item_id, "link": link_detail}
                result_core = {"status": "accepted", "reason_code": event.kind, "item_id": item_id, "link": link_detail}
            elif action == ACTION_CANCEL_REJUDGE:
                event = self._cancel_rejudge_event(ctx=ctx, item=item, body=body, now=now)
                result_core = {
                    "status": "accepted",
                    "reason_code": event.kind,
                    "item_id": item_id,
                    "resulting_status": "open",
                    "resulting_management_revision": current_revision + 1,
                }
            else:
                command = {
                    "schema_version": "judgment-maintenance-command/v1",
                    "command_id": idempotency_key,
                    "item_id": item_id,
                    "owner_user_id": ctx.owner_user_id,
                    "expected_item_version": expected_item_version,
                    "expected_management_revision": int(expected_revision or 0),
                    "action": action,
                    "acted_at": utc_iso(now),
                }
                if action == ACTION_SNOOZE:
                    until = body.get("snooze_until")
                    if not until:
                        raise ApiError(ERR_INVALID_REQUEST, "snooze 必须给 snooze_until", detail={"where": "snooze_until"})
                    command["snooze_until"] = utc_iso(ensure_aware(until, where="snooze_until"))
                if action == ACTION_REVIEWED_NO_CHANGE:
                    command["reviewed_source_versions"] = _reviewed_versions(item)
                result = validate_action(item=item, command=command, owner_user_id=ctx.owner_user_id, now=utc_iso(now))
                if result.status == "rejected":
                    raise ApiError(ERR_ACTION_REJECTED, result.detail or "动作被拒绝", detail={"reason_code": result.reason_code, "item_id": item_id})
                if result.status == "conflict":
                    raise ApiError(ERR_VERSION_CONFLICT, result.detail or "版本冲突", detail={"reason_code": result.reason_code, "item_id": item_id})
                if result.event is None:
                    raise ApiError(ERR_ACTION_REJECTED, "动作没有产生可落盘事件", detail={"reason_code": result.reason_code})
                event = result.event
                result_core = {
                    "status": result.status,
                    "reason_code": result.reason_code,
                    "item_id": item_id,
                    "resulting_status": result.resulting_status,
                    "resulting_management_revision": result.resulting_management_revision,
                }

            if action == ACTION_REJUDGE:
                result_core["continuation"] = self._continuation_for(ctx, item, conversation_id)

            assert isinstance(event, ManagementEvent)
            txn.append_action(
                event.to_dict(),
                idempotency_key=idempotency_key,
                action=action,
                payload_digest=payload_digest,
                recorded_at=utc_iso(now),
                conversation_id=conversation_id,
                result=result_core,
            )
        return {"replayed": False, **result_core}

    def _link_run_event(self, *, ctx: OwnerContext, conversation_id: str, item: Mapping[str, Any], body: Mapping[str, Any], now: datetime, store: EvolutionStore) -> tuple[Any, dict[str, Any]]:
        """把「继续核查」产生的真实 run 终态折回维护项。失败 / 取消 → 退回 open，不伪装完成。

        R7 四道闸，一道都不能少：
        1. run 必须属于**本会话**——别会话的 run 不能冒充本次复核的成果；
        2. 持久化关联：run_links 登记 / 用户消息 continuation 携带 maintenance_item_id /
           同会话最低关联（关联强度如实写进事件 payload.association）；
        3. 新判断：存在于判断台账、**不是被维护的原判断本身**（新版本身份）、来自本会话、
           生成时刻不早于本次复核请求（生成时序）；缺省时服务端解析「本会话内请求之后最新一条」；
        4. 追加前用 01 ``apply_event`` 预检迁移——01 会拒绝的迁移不能落台账，
           否则 HTTP 说 accepted、折叠时却是 rejected。
        """
        from intelligence.services.judgment_maintenance.actions import apply_event
        from intelligence.services.judgment_maintenance.contracts import (
            EVENT_ID_PREFIX,
            ManagementEvent,
            parse_event,
            parse_item,
            short_hash,
        )

        run_id = str(body.get("run_id") or "").strip()
        if not run_id:
            # 用户点「挂接核查结果」不带 run_id：用本项最近登记的那个 run。
            link = store.latest_run_link(item_id=str(item["id"]))
            if link is None:
                raise ApiError(
                    ERR_DEPENDENCY_MISSING,
                    "还没有登记的核查 run：请先点「继续核查」发起一轮新研究",
                    detail={"item_id": item["id"]},
                )
            run_id = str(link["run_id"])
        run_store = self.res.run_store_for(ctx.owner_user_id)
        try:
            run = run_store.load_run(run_id)
        except (FileNotFoundError, ValueError):
            raise ApiError(ERR_NOT_FOUND, "run 不存在") from None
        if str(getattr(run, "user", "")) != ctx.owner_user_id:
            raise ApiError(ERR_NOT_FOUND, "run 不存在")
        if str(getattr(run, "session_id", "") or "") != conversation_id:
            raise ApiError(
                ERR_RUN_BINDING_MISMATCH,
                "该 run 不属于本会话，不能折回本维护项",
                detail={"run_id": run_id},
            )
        status = str(getattr(run, "status", ""))
        requested_at = str(((item.get("management") or {}).get("rejudgment") or {}).get("requested_at") or "")

        if status not in {"completed", "failed", "cancelled"}:
            # 未终态：登记「本次维护请求发起了这个 run」的关联（接受 ≠ 完成，不迁状态）。
            link_id = stable_id("rlink", {"item": item["id"], "run": run_id})
            _, created = store.append_run_link(
                {
                    "link_id": link_id,
                    "owner_user_id": ctx.owner_user_id,
                    "item_id": str(item["id"]),
                    "run_id": run_id,
                    "conversation_id": conversation_id,
                    "registered_at": utc_iso(now),
                }
            )
            return None, {"run_id": run_id, "run_status": status, "registered": True, "link_created": created}

        # 终态：查关联强度。同会话是最低关联（session），登记与 continuation 是加强证据。
        association = "session"
        if store.find_run_link(item_id=str(item["id"]), run_id=run_id) is not None:
            association = "registered"
        else:
            continuation = self._run_continuation(ctx, conversation_id, run_id)
            inherits = (continuation or {}).get("inherits") or {}
            if str(inherits.get("maintenance_item_id") or "") == str(item["id"]):
                association = "continuation"

        if status == "completed":
            judgment_ref = str(body.get("new_judgment_ref") or "").strip()
            ledgers = re_adapters.load_legacy_ledgers(ctx.user_root)
            judgments = [r for r in ledgers.judgments if r.get("id")]
            if not judgment_ref:
                candidates = [
                    r
                    for r in judgments
                    if str(r.get("session_id") or "") == conversation_id and (not requested_at or _ts_ge(r.get("ts"), requested_at))
                ]
                if not candidates:
                    raise ApiError(
                        ERR_DEPENDENCY_MISSING,
                        "关闭维护项需要原写入者在本会话写下的新判断；管理动作不能冒充它",
                        detail={"run_id": run_id, "hint": "先在本会话记录新判断，再关联"},
                    )
                judgment_ref = f"judgments.jsonl:{candidates[-1]['id']}"
            by_ref = {f"judgments.jsonl:{r['id']}": r for r in judgments}
            judgment = by_ref.get(judgment_ref)
            if judgment is None:
                raise ApiError(ERR_REF_UNRESOLVABLE, "新判断引用在判断台账里找不到", detail={"ref": judgment_ref})
            if judgment_ref == str((item.get("object_ref") or {}).get("ref") or ""):
                raise ApiError(
                    ERR_INVALID_TRANSITION,
                    "新判断不能是被维护的原判断本身——那只是把旧结论指回来，没有重判",
                    detail={"ref": judgment_ref},
                )
            if str(judgment.get("session_id") or "") != conversation_id:
                raise ApiError(
                    ERR_RUN_BINDING_MISMATCH,
                    "新判断不来自本会话，不能冒充本次复核的成果",
                    detail={"ref": judgment_ref},
                )
            if requested_at and not _ts_ge(judgment.get("ts"), requested_at):
                raise ApiError(
                    ERR_DEPENDENCY_MISSING,
                    "新判断早于本次复核请求，不是这次重判的成果",
                    detail={"ref": judgment_ref, "requested_at": requested_at},
                )
            kind = "rejudgment_linked"
            payload = {"new_judgment_ref": judgment_ref, "owner_user_id": ctx.owner_user_id, "run_id": run_id, "association": association}
            detail = {"run_status": status, "new_judgment_ref": judgment_ref, "association": association}
        else:
            kind = "rejudgment_failed"
            payload = {"run_id": run_id, "run_status": status, "error": getattr(run, "error", None), "association": association}
            detail = {"run_status": status, "association": association}

        event = ManagementEvent(
            event_id=EVENT_ID_PREFIX + short_hash({"item_id": item["id"], "kind": kind, "run_id": run_id, "owner": ctx.owner_user_id}),
            item_id=str(item["id"]),
            owner_user_id=ctx.owner_user_id,
            kind=kind,
            at=utc_iso(now),
            expected_management_revision=int(item.get("management_revision") or 0),
            command_id=None,
            payload_digest=None,
            payload=payload,
        )
        _, outcome = apply_event(parse_item(dict(item), owner_user_id=ctx.owner_user_id, where="item"), parse_event(event.to_dict(), owner_user_id=ctx.owner_user_id), utc_iso(now))
        if outcome.outcome == "rejected":
            raise ApiError(ERR_ACTION_REJECTED, outcome.detail or "迁移被拒绝", detail={"reason_code": outcome.reason_code, "item_id": item["id"]})
        if outcome.outcome == "conflict":
            raise ApiError(ERR_VERSION_CONFLICT, outcome.detail or "版本冲突", detail={"reason_code": outcome.reason_code, "item_id": item["id"]})
        return event, detail

    def _cancel_rejudge_event(self, *, ctx: OwnerContext, item: Mapping[str, Any], body: Mapping[str, Any], now: datetime) -> Any:
        """取消一次已发起的复核：01 系统事件 ``rejudgment_cancelled`` → open。

        「继续核查」的消息被消息入口拒绝后，前端用本动作把维护项退回 open——
        不留「已请求、永远没有 run」的假进行态（R1 要求的请求拒绝后可恢复状态）。
        """
        from intelligence.services.judgment_maintenance.actions import apply_event
        from intelligence.services.judgment_maintenance.contracts import (
            EVENT_ID_PREFIX,
            ManagementEvent,
            parse_event,
            parse_item,
            short_hash,
        )

        if str(item.get("status")) != "rejudgment_requested":
            raise ApiError(
                ERR_ACTION_REJECTED,
                "只有等待重判的维护项才能取消复核",
                detail={"item_id": item.get("id"), "status": item.get("status")},
            )
        event = ManagementEvent(
            event_id=EVENT_ID_PREFIX
            + short_hash({"item_id": item["id"], "kind": "rejudgment_cancelled", "owner": ctx.owner_user_id, "revision": item.get("management_revision")}),
            item_id=str(item["id"]),
            owner_user_id=ctx.owner_user_id,
            kind="rejudgment_cancelled",
            at=utc_iso(now),
            expected_management_revision=int(item.get("management_revision") or 0),
            command_id=None,
            payload_digest=None,
            payload={"reason": str(body.get("reason") or "复核请求未被消息入口接受，退回待处理"), "owner_user_id": ctx.owner_user_id},
        )
        _, outcome = apply_event(parse_item(dict(item), owner_user_id=ctx.owner_user_id, where="item"), parse_event(event.to_dict(), owner_user_id=ctx.owner_user_id), utc_iso(now))
        if outcome.outcome in {"rejected", "conflict"}:
            raise ApiError(ERR_ACTION_REJECTED, outcome.detail or "迁移被拒绝", detail={"reason_code": outcome.reason_code, "item_id": item["id"]})
        return event

    def _run_continuation(self, ctx: OwnerContext, conversation_id: str, run_id: str) -> dict[str, Any] | None:
        """该 run 的用户消息上落的 continuation（关联证据之一）。读不到就是 None，不猜。"""
        try:
            from intelligence.services import research_project

            store = self.res.conversation_store_for(ctx.owner_user_id)
            messages = store.load_messages(conversation_id)
            return research_project.continuation_for_run(messages, run_id)
        except (FileNotFoundError, ValueError, OSError):
            return None

    def _origin_run_id(self, ctx: OwnerContext, conversation_id: str) -> str | None:
        """既有消息合同要求 continuation 带**真实存在**的来源 run：取本会话最近一轮已完成的 run。

        会话还没有完成轮次时返回 None——前端这时不带 continuation 发普通消息，
        新 run 与维护请求的关联改由 link_run 的 run_links 登记持久化。
        不填一个任意 run_id 绕过 ``_validated_continuation`` 的校验（R1）。
        """
        try:
            from intelligence.services import research_project

            state = research_project.load_project(
                self.res.conversation_store_for(ctx.owner_user_id),
                self.res.run_store_for(ctx.owner_user_id),
                conversation_id,
            )
        except (FileNotFoundError, ValueError, OSError):
            return None
        rounds = state.completed_rounds
        return str(rounds[-1].run_id) if rounds else None

    def _continuation_for(self, ctx: OwnerContext, item: Mapping[str, Any], conversation_id: str) -> dict[str, Any]:
        return _continuation_payload(item, conversation_id, self._origin_run_id(ctx, conversation_id))

    def _select_task(self, *, ctx: OwnerContext, conversation_id: str, idempotency_key: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """02 任务选择：只记录选择与点击载荷，不改任何判定（02 明写「不因点击改判定」）。"""
        now = self._now()
        store = self._store(ctx)
        task_id = str(body.get("task_id") or "").strip()
        if not task_id:
            raise ApiError(ERR_INVALID_REQUEST, "缺少 task_id", detail={"where": "task_id"})
        view = self.view(ctx=ctx, conversation_id=conversation_id)
        priority = view.get("priority")
        if not isinstance(priority, dict):
            raise ApiError(ERR_MODULE_UNAVAILABLE, "研究排序当前不可用", detail={"module_status": view.get("module_status", {}).get("priority")})
        found = _find_task(priority, task_id)
        if found is None:
            raise ApiError(ERR_DEPENDENCY_MISSING, "该任务不在当前排序结果中，请刷新后重试", detail={"task_id": task_id})
        event = self._product_value_event(
            ctx,
            event_type="task_selected",
            conversation_id=conversation_id,
            now=now,
            payload={
                "task_id": task_id,
                "policy_version": priority.get("policy_version") or "research-priority-policy/v1",
                "view_id": view["view_digest"],
                "client_at": body.get("client_at"),
                "initiator": "user",
                "assistance_source": "workbench",
            },
            source_channel="server",
        )
        recorded = self._store_event(store, event, required=False)
        # R6：选择任务要「带 task_id、source_refs、conversation_id 和原 scope 进入既有对话」——
        # 把 click_payload 折成既有消息入口的 continuation（full_prompt 是 02 渲染的原任务问题，
        # 不是前端拿标题重猜的），有已完成轮次时带真实 origin run_id，没有则省略（前端发普通消息）。
        click = dict(found.get("click_payload") or {})
        question = str(found.get("标题") or "").strip() or f"研究任务 {task_id}"
        scope = dict(click.get("scope") or {})
        continuation: dict[str, Any] = {
            "schema_version": CONTINUATION_SCHEMA,
            "conversation_id": conversation_id,
            "kind": "continue",
            "source": "research-evolution",
            "label": "研究这项任务",
            "task_id": task_id,
            "click_payload": click,
            "full_prompt": question,
            "inherits": {
                "task_id": task_id,
                **{f"scope_{k}": str(v) for k, v in scope.items()},
            },
        }
        origin_run_id = self._origin_run_id(ctx, conversation_id)
        if origin_run_id:
            continuation["run_id"] = origin_run_id
        return {"replayed": not recorded, "task_id": task_id, "click_payload": click, "continuation": continuation, "event_recorded": recorded}

    # ---- 练习与曝光 --------------------------------------------------------- #
    def _exercise_and_case(self, ctx: OwnerContext, conversation_id: str, store: EvolutionStore, exercise_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """定位当前诊断报告里的练习与题包里的 case；不在报告中 / 题包缺题 → 400。"""
        view = self.view(ctx=ctx, conversation_id=conversation_id)
        diagnostics = view.get("diagnostics")
        if not isinstance(diagnostics, dict):
            raise ApiError(ERR_MODULE_UNAVAILABLE, "诊断当前不可用", detail={"module_status": view.get("module_status", {}).get("diagnostics")})
        exercise = diagnostics.get("exercise")
        if not isinstance(exercise, dict) or str(exercise.get("id")) != exercise_id:
            raise ApiError(ERR_DEPENDENCY_MISSING, "该练习不在当前诊断报告中", detail={"exercise_id": exercise_id})
        pack_raw = store.read_immutable(REGISTRATIONS_DIR, "exercise_pack")
        case = _case_for(pack_raw, str(exercise.get("case_ref") or ""))
        if case is None:
            raise ApiError(ERR_DEPENDENCY_MISSING, "题包里找不到该题的结果身份，无法登记曝光", detail={"exercise_id": exercise_id})
        return dict(exercise), case

    def _expose_exercise(
        self,
        ctx: OwnerContext,
        *,
        exercise_id: str,
        case: Mapping[str, Any],
        now: datetime,
        operation_id: str,
        actor: str,
        reason: str,
    ) -> tuple[dict[str, Any], Any]:
        """03 ``record_exposure`` 原子登记曝光；结果身份不可解析 → fail closed（不揭示、不评卷）。

        所有会返回答案的出口（揭示 / 提交作答后的评分反馈）都必须先过这一道（R2）。
        """
        from intelligence.services.research_validation import ConflictError, Repository, record_exposure

        identity = case.get("outcome_identity")
        structured = parse_outcome_identity(identity)
        if structured is None:
            raise ApiError(
                ERR_DEPENDENCY_MISSING,
                "这道题的结果身份不可解析，无法登记曝光，因此不揭示后续事实",
                detail={
                    "exercise_id": exercise_id,
                    "outcome_identity": str(identity),
                    "expected": "<entity_type>:<entity_id>:<as_of>:<outcome_due>:<horizon>",
                },
            )
        repo = Repository(ctx.validation_root, owner_user_id=ctx.owner_user_id)
        try:
            exposure = record_exposure(
                owner=ctx.owner_user_id,
                repository=repo,
                now=now,
                operation_id=operation_id,
                lineage_id=None,
                study_id=None,
                framework_hash=None,
                window=None,
                case_manifest_hash=None,
                outcome_identities=[structured],
                stage="practice_reveal",
                actor=actor,
                reason=reason,
            )
        except ConflictError as exc:
            raise ApiError(ERR_EXPOSURE_CONFLICT, str(exc), detail={"operation_id": operation_id}) from None
        return exposure, identity

    def _reveal_exercise(self, *, ctx: OwnerContext, conversation_id: str, idempotency_key: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """揭示后续事实前，先经 03 的 ``record_exposure`` 按底层结果身份原子登记曝光。

        改名 / 换 study 都绕不开：``record_exposure`` 记的是 ``outcome_identity``，不是题目名。
        """
        now = self._now()
        store = self._store(ctx)
        exercise_id = str(body.get("exercise_id") or "").strip()
        if not exercise_id:
            raise ApiError(ERR_INVALID_REQUEST, "缺少 exercise_id", detail={"where": "exercise_id"})
        exercise, case = self._exercise_and_case(ctx, conversation_id, store, exercise_id)
        exposure, identity = self._expose_exercise(
            ctx,
            exercise_id=exercise_id,
            case=case,
            now=now,
            operation_id=stable_id("expo", {"owner": ctx.owner_user_id, "exercise": exercise_id, "identity": case.get("outcome_identity")}),
            actor="research_evolution.reveal_exercise",
            reason=f"用户揭示练习 {exercise_id} 的后续事实",
        )

        receipt = {
            "receipt_id": stable_id("rcpt", {"kind": "exercise_seen", "exercise": exercise_id, "owner": ctx.owner_user_id}),
            "owner_user_id": ctx.owner_user_id,
            "kind": "exercise_seen",
            "occurred_at": utc_iso(now),
            "recorded_at": utc_iso(now),
            "payload": {"case_id": case.get("case_id"), "outcome_identity": identity, "exercise_id": exercise_id},
            "provenance": "observed",
        }
        with store.transaction() as txn:
            txn.append_process_receipt({"receipt_id": receipt["receipt_id"], "owner_user_id": ctx.owner_user_id, "receipt": receipt, "exposure_id": exposure.get("id")})
        return {
            "exercise_id": exercise_id,
            "exposure_id": exposure.get("id"),
            "exposure_recorded_at": exposure.get("accessed_at"),
            "answer_key_ref": exercise.get("answer_key_ref"),
            "answer_key": case.get("answer_key"),
            "limitation": exercise.get("limitation"),
        }

    def _submit_exercise(self, *, ctx: OwnerContext, conversation_id: str, idempotency_key: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """确定性评卷（04 ``evaluate_exercise_response``）。练习结果不进任何方法有效性统计。

        评分反馈里带正确选项与正确引用——所以提交作答与揭示走**同一条曝光边界**：
        先经 03 登记曝光再评卷（R2）。``operation_id`` 与揭示不同（不同门径、不同意图），
        避免同键异意图被 03 判成冲突。
        """
        from intelligence.services.research_diagnostics import (
            AnswerKey,
            DiagnosticsInputError,
            ExerciseResponse,
            evaluate_exercise_response,
        )
        from intelligence.services.research_diagnostics.contracts import HistoricalExercise

        now = self._now()
        store = self._store(ctx)
        exercise_id = str(body.get("exercise_id") or "").strip()
        if not exercise_id:
            raise ApiError(ERR_INVALID_REQUEST, "缺少 exercise_id", detail={"where": "exercise_id"})
        exercise_raw, case = self._exercise_and_case(ctx, conversation_id, store, exercise_id)
        exposure, _identity = self._expose_exercise(
            ctx,
            exercise_id=exercise_id,
            case=case,
            now=now,
            operation_id=stable_id("expo", {"owner": ctx.owner_user_id, "exercise": exercise_id, "identity": case.get("outcome_identity"), "gate": "submit"}),
            actor="research_evolution.submit_exercise",
            reason=f"用户提交练习 {exercise_id} 的作答并查看评分反馈",
        )
        try:
            feedback = evaluate_exercise_response(
                exercise=HistoricalExercise(**{k: v for k, v in exercise_raw.items() if k in HistoricalExercise.__dataclass_fields__}),
                response=ExerciseResponse(
                    exercise_id=exercise_id,
                    selected_choices=tuple(str(x) for x in (body.get("selected_choices") or ())),
                    cited_refs=tuple(str(x) for x in (body.get("cited_refs") or ())),
                    rationale=body.get("rationale"),
                ),
                answer_key=AnswerKey(**dict(case.get("answer_key") or {})),
            )
        except (DiagnosticsInputError, TypeError) as exc:
            raise ApiError(ERR_INVALID_REQUEST, f"练习作答不合法：{exc}", detail={"exercise_id": exercise_id}) from None

        event = self._product_value_event(
            ctx,
            event_type="exercise_submitted",
            conversation_id=conversation_id,
            now=now,
            payload={
                "exercise_id": exercise_id,
                "exercise_version": exercise_raw.get("answer_key_ref"),
                "submission_ref": stable_id("sub", {"exercise": exercise_id, "key": idempotency_key}),
                "submitted_at": utc_iso(now),
                "initiator": "user",
                "assistance_source": "workbench",
            },
            source_channel="server",
        )
        self._store_event(store, event, required=False)
        payload = feedback.to_dict() if hasattr(feedback, "to_dict") else {"status": feedback.status}
        payload["counts_toward_method_statistics"] = False
        payload["exposure_id"] = exposure.get("id")
        return payload

    # ---- 收据原件（R5） ------------------------------------------------------ #
    def _read_receipt(self, *, ctx: OwnerContext, conversation_id: str, idempotency_key: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """读收据原件。03 方法验证收据走 03 ``read_receipt``（内部先登记曝光，不另开旁路）；
        05 测量收据 / 试点总结走 06 store 的验权读取（owner 隔离在路径层）。
        """
        self._conversation(ctx, conversation_id)
        now = self._now()
        store = self._store(ctx)
        kind = str(body.get("receipt_kind") or "").strip()
        receipt_id = str(body.get("receipt_id") or "").strip()
        if kind == "method_validation_receipt":
            from intelligence.services.research_validation import ContractError, Repository, read_receipt

            study_id = str(body.get("study_id") or "").strip()
            if not study_id:
                raise ApiError(ERR_INVALID_REQUEST, "缺少 study_id", detail={"where": "study_id"})
            repo = Repository(ctx.validation_root, owner_user_id=ctx.owner_user_id)
            try:
                receipt = read_receipt(
                    owner=ctx.owner_user_id,
                    repository=repo,
                    now=now,
                    study_id=study_id,
                    receipt_id=receipt_id or None,
                    actor="research_evolution.read_receipt",
                )
            except ContractError as exc:
                raise ApiError(ERR_NOT_FOUND, str(exc)) from None
            if receipt is None:
                raise ApiError(ERR_DEPENDENCY_MISSING, "该实验还没有收据", detail={"study_id": study_id})
            return {"kind": kind, "study_id": study_id, "receipt": receipt}
        if kind == "measurement_receipt":
            if not receipt_id:
                raise ApiError(ERR_INVALID_REQUEST, "缺少 receipt_id", detail={"where": "receipt_id"})
            receipt = store.read_immutable(RECEIPTS_DIR, receipt_id)
            if receipt is None:
                raise ApiError(ERR_NOT_FOUND, "收据不存在", detail={"receipt_id": receipt_id})
            return {"kind": kind, "receipt": receipt}
        if kind == "pilot_summary":
            if not receipt_id:
                raise ApiError(ERR_INVALID_REQUEST, "缺少 receipt_id", detail={"where": "receipt_id"})
            summary = store.read_immutable(SUMMARIES_DIR, receipt_id)
            if summary is None:
                raise ApiError(ERR_NOT_FOUND, "总结不存在", detail={"receipt_id": receipt_id})
            return {"kind": kind, "receipt": summary}
        raise ApiError(
            ERR_INVALID_REQUEST,
            "未知收据类型",
            detail={"receipt_kind": kind, "allowed": ["method_validation_receipt", "measurement_receipt", "pilot_summary"]},
        )

    # ---- 05 事件 ------------------------------------------------------------ #
    def ingest_events(self, *, ctx: OwnerContext, conversation_id: str, body: Mapping[str, Any]) -> dict[str, Any]:
        """前端上报的已同意测量事件。服务端补可信时间与 owner，只放行白名单允许来自 frontend 的类型。"""
        from intelligence.services.product_value import validate_event
        from intelligence.services.product_value.contracts import EVENT_TYPES, SOURCE_FRONTEND

        self._conversation(ctx, conversation_id)
        now = self._now()
        store = self._store(ctx)
        raw_events = body.get("events")
        if not isinstance(raw_events, Sequence) or isinstance(raw_events, (str, bytes)) or not raw_events:
            raise ApiError(ERR_INVALID_REQUEST, "events 必须是非空列表", detail={"where": "events"})

        accepted: list[str] = []
        rejected: list[dict[str, Any]] = []
        duplicates: list[str] = []
        for index, raw in enumerate(raw_events):
            if not isinstance(raw, Mapping):
                rejected.append({"index": index, "code": "type_invalid", "message": "事件必须是对象"})
                continue
            event_type = str(raw.get("event_type") or "")
            spec = EVENT_TYPES.get(event_type)
            if spec is None:
                rejected.append({"index": index, "code": "unknown_event_type", "message": f"未知事件类型 {event_type}"})
                continue
            if SOURCE_FRONTEND not in spec.sources:
                rejected.append({"index": index, "code": "source_not_allowed", "message": f"{event_type} 不接受前端上报（服务端事实由服务端写）"})
                continue
            event = self._product_value_event(
                ctx,
                event_type=event_type,
                conversation_id=conversation_id,
                now=now,
                payload=dict(raw.get("payload") or {}),
                source_channel=SOURCE_FRONTEND,
                event_at=raw.get("event_at") or self._retry_event_at(store, raw.get("event_id")),
                event_id=raw.get("event_id"),
                pilot_id=raw.get("pilot_id"),
                participant_id=raw.get("participant_id"),
                task_id=raw.get("task_id"),
                run_ids=raw.get("run_ids"),
                gaps=raw.get("gaps"),
            )
            result = validate_event(event)
            if not result.ok:
                rejected.append({"index": index, "code": result.issues[0].code if result.issues else "invalid", "message": "; ".join(i.message for i in result.issues)[:400], "issues": [i.code for i in result.issues]})
                continue
            created = self._store_event(store, result.normalized or event, content_hash=result.content_hash, required=True)
            (accepted if created else duplicates).append(str(event["event_id"]))
        return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected, "recorded_at": utc_iso(now)}

    def _retry_event_at(self, store: EvolutionStore, event_id: Any) -> str | None:
        """R8：客户端没给 event_at 的重试，复用首个服务端时间再比业务载荷。

        05 的内容摘要只剔 ``recorded_at`` 不剔 ``event_at``——重试时服务端时钟已推进，
        新盖的时间会让同一条事件变成「同 id 异内容」的 409。先定位已提交的那条，
        把它的 event_at 拿过来重建事件：业务载荷一致 → 同摘要 → 如实返回 duplicates；
        不一致 → 冲突照旧。
        """
        eid = str(event_id or "").strip()
        if not eid:
            return None
        existing = store.find_product_value_event(eid)
        if existing is None:
            return None
        return str(existing.get("event_at") or "") or None

    def _product_value_event(
        self,
        ctx: OwnerContext,
        *,
        event_type: str,
        conversation_id: str,
        now: datetime,
        payload: Mapping[str, Any],
        source_channel: str,
        event_at: Any = None,
        event_id: Any = None,
        pilot_id: Any = None,
        participant_id: Any = None,
        task_id: Any = None,
        run_ids: Any = None,
        gaps: Any = None,
    ) -> dict[str, Any]:
        """服务端盖章：``source_channel`` / ``provenance`` / ``recorded_at`` / ``owner`` 一律覆盖客户端自报。"""
        from intelligence.services.product_value.contracts import EVENT_SCHEMA, PROVENANCE_OBSERVED

        stamp = utc_iso(ensure_aware(event_at, where="event_at")) if event_at else utc_iso(now)
        # Workbench 自用的测量事件不在任何冻结试点协议下。``source_version.protocol_version`` 是必填，
        # 这里给一个**明确表示「不是试点」**的版本号，并让 ``pilot_id`` 带上会话前缀——
        # 05 的 ``summarize`` 按 pilot_id 分区，自用事件因此永远混不进真人试点读数。
        protocol_version = SELF_USE_PROTOCOL_VERSION
        eid = str(event_id or "").strip() or stable_id("pve", {"type": event_type, "conv": conversation_id, "payload": dict(payload), "at": stamp, "nonce": time.monotonic_ns() if event_id is None and event_at is None else 0})
        body = {
            "schema_version": EVENT_SCHEMA,
            "event_id": eid,
            "event_type": event_type,
            "owner_user_id": ctx.owner_user_id,
            "pilot_id": str(pilot_id or f"workbench:{conversation_id}"),
            "participant_id": str(participant_id) if participant_id else None,
            "task_id": str(task_id) if task_id else (str(payload.get("task_id")) if payload.get("task_id") else None),
            "case_id": None,
            "case_version": None,
            "case_pair_id": None,
            "run_ids": [str(r) for r in (run_ids or [])],
            "object_refs": [],
            "assistance_condition": None,
            "event_at": stamp,
            "recorded_at": utc_iso(now),
            "source_version": {"code_sha": self.res.code_sha or "unknown", "protocol_version": protocol_version, "artifact_hash": None},
            "provenance": {"kind": PROVENANCE_OBSERVED, "source_ref": f"conversation:{conversation_id}", "source_hash": None},
            "source_channel": source_channel,
            "payload": dict(payload),
        }
        if gaps:
            body["gaps"] = list(gaps)
        else:
            body["gaps"] = [
                {"field": name, "reason": "not_applicable"}
                for name in ("participant_id", "case_id", "case_version", "case_pair_id", "assistance_condition")
                if body.get(name) is None
            ] + ([{"field": "task_id", "reason": "not_applicable"}] if body.get("task_id") is None else [])
        return body

    def _store_event(self, store: EvolutionStore, event: Mapping[str, Any], *, content_hash: str | None = None, required: bool) -> bool:
        try:
            with store.transaction() as txn:
                _, created = txn.append_product_value_event(event, content_hash=content_hash or digest(dict(event)))
            return created
        except ApiError:
            if required:
                raise
            return False

    # ---- 受控登记（测试与运维入口共用） ---------------------------------------- #
    def register_artifact(self, *, ctx: OwnerContext, kind: str, value: Mapping[str, Any]) -> dict[str, Any]:
        """登记诊断策略 / 题包等本批需要的领域配置（不可变、按内容 id 去重）。"""
        if kind not in {"diagnostics_policy", "exercise_pack", "pilot_protocol"}:
            raise ApiError(ERR_INVALID_REQUEST, "未知登记类型", detail={"kind": kind})
        store = self._store(ctx)
        with store.transaction() as txn:
            stored, created = txn.publish_immutable(REGISTRATIONS_DIR, kind, dict(value))
        return {"kind": kind, "created": created, "stored": stored}

    def record_process_receipt(self, *, ctx: OwnerContext, receipt: Mapping[str, Any]) -> dict[str, Any]:
        """登记 04 需要的流程收据（``coverage`` / ``evidence_use`` / ``stage_use`` / ``revision`` …）。

        这些收据决定 04 能不能把「未知」升级成「有证据的问题」——例如没有 ``coverage`` 声明
        回检台账完整到哪一天，就永远只能说 ``coverage_unknown``，不能说「漏检」。
        单 writer、按 ``receipt_id`` 幂等；同 id 异内容拒绝。
        """
        from intelligence.services.research_diagnostics.contracts import RECEIPT_KINDS

        kind = str(receipt.get("kind") or "")
        if kind not in RECEIPT_KINDS:
            raise ApiError(ERR_INVALID_REQUEST, "未知流程收据类型", detail={"kind": kind, "allowed": list(RECEIPT_KINDS)})
        receipt_id = str(receipt.get("receipt_id") or "").strip()
        if not receipt_id:
            raise ApiError(ERR_INVALID_REQUEST, "缺少 receipt_id", detail={"where": "receipt_id"})
        body = {**dict(receipt), "owner_user_id": ctx.owner_user_id}
        store = self._store(ctx)
        with store.transaction() as txn:
            stored, created = txn.append_process_receipt(
                {"receipt_id": receipt_id, "owner_user_id": ctx.owner_user_id, "receipt": body}
            )
        return {"receipt_id": receipt_id, "created": created, "kind": kind, "stored": stored}

    def store_protocol(self, *, ctx: OwnerContext, protocol: Mapping[str, Any]) -> dict[str, Any]:
        from intelligence.services.product_value import freeze_protocol, protocol_hash

        frozen = freeze_protocol(dict(protocol))
        phash = protocol_hash(frozen)
        store = self._store(ctx)
        with store.transaction() as txn:
            stored, created = txn.publish_immutable(PROTOCOLS_DIR, phash, dict(frozen))
        return {"protocol_hash": phash, "created": created, "protocol": stored}


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _ts_ge(value: Any, floor: str) -> bool:
    """比较两个带时区的 ISO 时刻：``value >= floor``。解析失败一律 False（不放行）。"""
    try:
        moment = ensure_aware(str(value or ""), where="ts")
        bound = ensure_aware(str(floor or ""), where="requested_at")
    except ApiError:
        return False
    return moment >= bound


def _reviewed_versions(item: Mapping[str, Any]) -> list[dict[str, str]]:
    """「核对后判断未变」必须针对**当前**版本集合。

    01 的 ``apply_event`` 拿它与 ``item.current`` 逐个比对，不一致就是 ``stale_source_versions``——
    所以这里**只能**取 ``current``，不能在它为空时回退到 ``before``：那样等于拿旧版本去关闭新变化。
    """
    out: list[dict[str, str]] = []
    for version in item.get("current") or ():
        ref = str(version.get("ref") or "")
        source_hash = version.get("source_hash")
        if ref and source_hash:
            out.append({"ref": ref, "source_hash": str(source_hash)})
    return out


def _continuation_payload(item: Mapping[str, Any], conversation_id: str, origin_run_id: str | None) -> dict[str, Any]:
    """「继续核查」的 continuation 载荷：带原对象、维护项与来源版本，由前端交给现有 POST 消息入口。

    ``run_id`` 只在有真实已完成轮次时出现（既有消息合同要求来源 run 真实存在）；
    ``inherits`` 是结构化关联字段的扁平版（消息合同是 dict[str, str]），
    服务端 link_run 靠它核验「这个 run 是这次维护请求发起的」。
    """
    object_ref = dict(item.get("object_ref") or {})
    versions = [f"{v.get('ref')}@{v.get('source_hash')}" for v in (item.get("current") or item.get("before") or ())]
    if not versions:
        # 条件项没有证据版本差异，它的「来源」是被观测的标签读数与绑定条件。
        evaluation = item.get("condition_evaluation") or {}
        for reading in evaluation.get("readings") or ():
            ref = reading.get("source_ref") if isinstance(reading, Mapping) else None
            if ref:
                versions.append(f"{ref}@{reading.get('observed')!r}")
        if not versions and item.get("condition_ref"):
            versions.append(str(item["condition_ref"]))
    payload: dict[str, Any] = {
        "schema_version": CONTINUATION_SCHEMA,
        "conversation_id": conversation_id,
        "kind": "condition_test",
        "source": "research-evolution",
        "label": "继续核查这条判断",
        "maintenance_item_id": item.get("id"),
        "item_version": item.get("item_version"),
        "object_ref": object_ref,
        "source_versions": versions,
        "full_prompt": _rejudge_prompt(item),
        "inherits": {
            "maintenance_item_id": str(item.get("id") or ""),
            "item_version": str(item.get("item_version") or ""),
            "object_ref": str(object_ref.get("ref") or ""),
            "source_versions": ";".join(versions),
        },
    }
    if origin_run_id:
        payload["run_id"] = origin_run_id
    return payload


def _rejudge_prompt(item: Mapping[str, Any]) -> str:
    change = str(item.get("change_type") or "")
    reason = str(item.get("reason_code") or "")
    refs = "、".join(str(v.get("ref")) for v in (item.get("current") or ()))
    return (
        f"这条旧判断的依据发生了变化（变化类型 {change}，原因 {reason}）。"
        f"涉及的依据引用：{refs or '（无）'}。请按当前证据重新核查该判断是否仍然成立，"
        "并说明是哪一条依据的变化改变了结论；无法判定的部分如实说未知。"
    )


def _find_task(priority_view: Mapping[str, Any], task_id: str) -> dict[str, Any] | None:
    for bucket in ("selected", "deferred", "blocked"):
        for task in priority_view.get(bucket) or ():
            if isinstance(task, Mapping) and str(task.get("task_id") or task.get("id")) == task_id:
                return dict(task)
    return None


# 04 的 ``ExerciseCase.outcome_identity`` 是一个**字符串**，03 的曝光台账要的是结构化结果身份
# （``entity_type / entity_id / as_of / outcome_due / horizon``）。两边都不该为对方改合同，
# 于是约定一种可解析的规范写法：``<entity_type>:<entity_id>:<as_of>:<outcome_due>:<horizon>``。
# 解析不出来的（例如 ``oc-overdue-001`` 这种不透明 id）**不揭示**——不能凭空编出实体与区间去登记曝光，
# 也不能跳过登记直接给答案。这一条是 fail closed，缺口记在 BLOCKED.md。
_IDENTITY_FIELDS = ("entity_type", "entity_id", "as_of", "outcome_due", "horizon")


def parse_outcome_identity(value: Any) -> dict[str, Any] | None:
    """把 04 的结果身份解析成 03 能登记的结构化身份；解析不出返回 ``None``。"""
    if isinstance(value, Mapping):
        return dict(value) if all(field_name in value for field_name in _IDENTITY_FIELDS) else None
    if not isinstance(value, str):
        return None
    parts = value.split(":")
    if len(parts) != 5:
        return None
    entity_type, entity_id, as_of, outcome_due, horizon = (p.strip() for p in parts)
    if not (entity_type and entity_id and horizon.isdigit()):
        return None
    try:
        date_cls.fromisoformat(as_of)
        date_cls.fromisoformat(outcome_due)
    except ValueError:
        return None
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "as_of": as_of,
        "outcome_due": outcome_due,
        "horizon": int(horizon),
    }


def _case_for(pack_raw: Mapping[str, Any] | None, case_ref: str) -> dict[str, Any] | None:
    if not pack_raw:
        return None
    for case in (pack_raw.get("pack") or {}).get("cases") or ():
        if isinstance(case, Mapping) and str(case.get("case_ref")) == case_ref:
            return dict(case)
    return None


__all__ = ["DIAGNOSTICS_WINDOW_DAYS", "EXERCISE_PACK_FILE", "POLICY_FILE", "Resources", "ResearchEvolutionService"]
