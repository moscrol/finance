"""研究进化（01–05）的 Workbench 接线：一个独立 router，由 ``create_app`` 注入既有 store 与资源。

spec ``docs/superpowers/specs/2026-09-13-research-evolution/06-workbench-integration.md`` §4.4。

四个端点（全部挂在既有会话下，不新建第二套「研究会话」）：

| 方法与路径 | 行为 |
|---|---|
| ``GET  …/research-evolution`` | 01/02/04 当前投影 + 可访问的 03/05 收据引用；读取无业务写副作用 |
| ``POST …/research-evolution/bindings`` | 用户明确建立「从现在开始跟踪」的证据依赖 |
| ``POST …/research-evolution/actions`` | 01 管理动作、02 任务选择、04 练习揭示/作答；校验版本与幂等 |
| ``POST …/research-evolution/events`` | 已同意记录的 05 前端测量事件；服务端补可信时间与 owner |

错误正文沿用本仓既有的 ``{"detail": ...}`` 外壳，内层放稳定业务码
``{"code", "message", "detail"}``——前端按 ``code`` 分支，不靠解析中文串。
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from intelligence.services.research_evolution.access import AccessPolicy, OwnerContext
from intelligence.services.research_evolution.contracts import ApiError, scrub_paths
from intelligence.services.research_evolution.facade import ResearchEvolutionService

PREFIX = "/api/conversations/{conversation_id}/research-evolution"


class BindingRequest(BaseModel):
    object_ref: dict[str, Any]
    entity: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    binding_origin: str | None = None
    user: str | None = None


class ActionRequest(BaseModel):
    action: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    item_id: str | None = None
    task_id: str | None = None
    exercise_id: str | None = None
    run_id: str | None = None
    new_judgment_ref: str | None = None
    expected_item_version: str | None = None
    expected_management_revision: int | None = None
    snooze_until: str | None = None
    selected_choices: list[str] = Field(default_factory=list)
    cited_refs: list[str] = Field(default_factory=list)
    rationale: str | None = None
    client_at: str | None = None
    as_of: str | None = None
    knowledge_cutoff: str | None = None
    # read_receipt：收据类型 + 定位（03 收据要 study_id；05 收据 / 总结要 receipt_id）
    receipt_kind: str | None = None
    receipt_id: str | None = None
    study_id: str | None = None
    # cancel_rejudge：取消原因（可选，默认「复核请求未被消息入口接受」）
    reason: str | None = None
    user: str | None = None


class EventsRequest(BaseModel):
    events: list[dict[str, Any]] = Field(min_length=1)
    user: str | None = None


def _http_error(exc: ApiError) -> HTTPException:
    """业务错误 → HTTP。绝对路径一律擦掉：错误正文不得泄漏用户目录。"""
    return HTTPException(exc.http_status, scrub_paths(exc.to_dict()))


def build_router(
    *,
    service_for: Callable[[], ResearchEvolutionService],
    access_policy: Callable[[], AccessPolicy],
) -> APIRouter:
    router = APIRouter()

    def _ctx(user: str | None) -> OwnerContext:
        owner = access_policy().resolve_owner(user)
        return OwnerContext.for_owner(owner)

    @router.get(PREFIX)
    def get_research_evolution(
        conversation_id: str,
        user: str | None = None,
        as_of: str | None = None,
        knowledge_cutoff: str | None = None,
        budget_minutes: float | None = None,
    ) -> dict[str, Any]:
        """01/02/04 的当前投影与 03/05 收据引用。只读：不改原判断、不登记完成、不调模型。"""
        try:
            ctx = _ctx(user)
            payload = service_for().view(
                ctx=ctx,
                conversation_id=conversation_id,
                as_of=as_of,
                knowledge_cutoff=knowledge_cutoff,
                budget_minutes=budget_minutes,
            )
        except ApiError as exc:
            raise _http_error(exc) from None
        return scrub_paths(payload)

    @router.get(PREFIX + "/evidence-catalog")
    def get_evidence_catalog(
        conversation_id: str,
        entity: str,
        as_of: str,
        user: str | None = None,
        knowledge_cutoff: str | None = None,
    ) -> dict[str, Any]:
        """建立绑定前，列出该实体当日**受控**的证据版本。用户只能从这里选引用。"""
        try:
            ctx = _ctx(user)
            service = service_for()
            service._conversation(ctx, conversation_id)  # 范围校验：会话必须属于本 owner
            payload = service.evidence_catalog(ctx=ctx, entity=entity, as_of=as_of, knowledge_cutoff=knowledge_cutoff)
        except ApiError as exc:
            raise _http_error(exc) from None
        return scrub_paths(payload)

    @router.post(PREFIX + "/bindings", status_code=201)
    def create_binding(conversation_id: str, req: BindingRequest) -> dict[str, Any]:
        """「从现在开始跟踪」：服务端解析真实 hash/版本；原判断日期不改，不追溯补成当时已知。"""
        try:
            ctx = _ctx(req.user)
            payload = service_for().create_binding(
                ctx=ctx,
                conversation_id=conversation_id,
                body=req.model_dump(exclude_none=False),
            )
        except ApiError as exc:
            raise _http_error(exc) from None
        return scrub_paths(payload)

    @router.post(PREFIX + "/actions")
    def post_action(conversation_id: str, req: ActionRequest) -> dict[str, Any]:
        """01 管理动作 / 02 任务选择 / 04 练习。版本过期 409；同键同载荷返回原结果。"""
        try:
            ctx = _ctx(req.user)
            payload = service_for().apply_action(
                ctx=ctx,
                conversation_id=conversation_id,
                body={k: v for k, v in req.model_dump().items() if v is not None},
            )
        except ApiError as exc:
            raise _http_error(exc) from None
        return scrub_paths(payload)

    @router.post(PREFIX + "/events", status_code=202)
    def post_events(conversation_id: str, req: EventsRequest) -> dict[str, Any]:
        """05 前端测量事件。只接受白名单里允许 frontend 的类型；拒收信息回给客户端，不静默丢。"""
        try:
            ctx = _ctx(req.user)
            payload = service_for().ingest_events(
                ctx=ctx,
                conversation_id=conversation_id,
                body={"events": req.events},
            )
        except ApiError as exc:
            raise _http_error(exc) from None
        return scrub_paths(payload)

    return router


__all__ = ["PREFIX", "ActionRequest", "BindingRequest", "EventsRequest", "build_router"]
