"""Continuous model/tool loop for one bounded financial research turn."""

from __future__ import annotations

import json
import re
from typing import cast

from intelligence.services import query_ledger
from intelligence.services.agent_research import AgentEvidence
from intelligence.services.agent_runtime import (
    AgentModelClient,
    AgentOutcome,
    AgentUsage,
    EpisodeEvent,
    EpisodeStatus,
    ModelToolCall,
    ModelTurn,
    OutputEvidenceBinding,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_contract import ResearchRunContext
from intelligence.services.research_tool_registry import (
    ResearchToolRegistry,
)
from intelligence.services.task_frame import TaskFrame


DEFAULT_LLM_TIMEOUT = 20.0
_FINISH_STATUSES = frozenset({"completed", "partial"})
_FINAL_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S | re.I)


class _EpisodeLedger:
    def __init__(self, task_frame: TaskFrame) -> None:
        self._task_frame_hash = task_frame.task_frame_hash
        self.events: list[EpisodeEvent] = []
        self.add(
            "task",
            {
                "question": task_frame.raw_question,
                "task_frame": task_frame.to_dict(),
            },
        )

    def add(self, kind: str, payload: dict[str, object]) -> EpisodeEvent:
        event_payload = dict(payload)
        event_payload["task_frame_hash"] = self._task_frame_hash
        event = EpisodeEvent(len(self.events) + 1, kind, event_payload)
        self.events.append(event)
        return event


class ContinuousAgentEpisode:
    """Run a task without rebuilding the model's observable message history."""

    def __init__(
        self,
        model: AgentModelClient,
        *,
        llm_timeout: float = DEFAULT_LLM_TIMEOUT,
    ) -> None:
        self._model = model
        self._llm_timeout = max(0.1, float(llm_timeout))

    def run(
        self,
        *,
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> AgentOutcome:
        if (
            context.contract.task_frame_hash
            and context.contract.task_frame_hash != task_frame.task_frame_hash
        ):
            raise ValueError("research contract task frame hash mismatch")

        ledger = _EpisodeLedger(task_frame)
        evidence: list[AgentEvidence] = []
        evidence_hashes: set[str] = set()
        traces: list[ProviderTrace] = []
        gaps: list[str] = []
        seen_queries: set[tuple[str, str]] = set()
        llm_calls = 0
        tool_calls = 0
        invalid_actions = 0
        finish_failures = 0
        messages: list[dict[str, object]] = [
            {
                "role": "system",
                "content": self._system_prompt(task_frame, context, registry),
            },
            {
                "role": "user",
                "content": self._task_prompt(task_frame, context),
            },
        ]
        definitions = registry.tool_definitions(
            context.contract.allowed_capabilities
        )
        authorized_names = {
            str(item["function"]["name"])
            for item in definitions
        }

        for _round in range(1, context.policy.max_steps + 1):
            timeout = context.deadline.stage_timeout(self._llm_timeout)
            if timeout <= 0.001:
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if evidence else "failed",
                    stop_reason="deadline_exhausted",
                    gap="研究截止时间已到，仍有必需输出未覆盖",
                    ledger=ledger,
                    evidence=evidence,
                    traces=traces,
                    gaps=gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            llm_calls += 1
            try:
                turn = self._model.complete(
                    messages=list(messages),
                    tools=definitions,
                    timeout=timeout,
                )
            except Exception as exc:
                reason = f"model_exception:{type(exc).__name__}"
                ledger.add("model_error", {"reason": reason})
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if evidence else "failed",
                    stop_reason="model_unavailable",
                    gap=reason,
                    ledger=ledger,
                    evidence=evidence,
                    traces=traces,
                    gaps=gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            ledger.add("model_turn", turn.to_dict())
            if turn.error:
                ledger.add("model_error", {"reason": turn.error})
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial" if evidence else "failed",
                    stop_reason="model_unavailable",
                    gap=turn.error,
                    ledger=ledger,
                    evidence=evidence,
                    traces=traces,
                    gaps=gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            messages.append(self._assistant_message(turn))
            if turn.tool_calls:
                for call in turn.tool_calls:
                    ledger.add("tool_request", call.to_dict())
                    query = call.arguments.get("query")
                    if (
                        call.name not in authorized_names
                        or not isinstance(query, str)
                        or not query.strip()
                    ):
                        invalid_actions += 1
                        error = "unknown_or_unauthorized_tool"
                        trace = ProviderTrace(
                            provider="episode:tool_gate",
                            capability=call.name,
                            status="disabled",
                            detail=error,
                            parent_id=context.trace_parent_id,
                            step_id=f"{context.trace_parent_id}:episode:gate",
                        )
                        traces.append(trace)
                        self._append_tool_error(
                            messages,
                            ledger,
                            call,
                            error,
                        )
                        continue

                    normalized = query_ledger.normalize_query(query)
                    query_key = (call.name, normalized)
                    if query_key in seen_queries:
                        invalid_actions += 1
                        self._append_tool_error(
                            messages,
                            ledger,
                            call,
                            "duplicate_query",
                        )
                        continue
                    if tool_calls >= context.policy.max_steps:
                        invalid_actions += 1
                        self._append_tool_error(
                            messages,
                            ledger,
                            call,
                            "tool_budget_exhausted",
                        )
                        continue
                    seen_queries.add(query_key)

                    tool_calls += 1
                    step_id = f"{context.trace_parent_id}:episode:{tool_calls}"
                    try:
                        observation = registry.execute(
                            call.name,
                            query,
                            context=context,
                            step_id=step_id,
                        )
                    except Exception as exc:
                        trace = ProviderTrace(
                            provider=f"agent:{call.name}",
                            capability=call.name,
                            status="request_error",
                            detail=f"{type(exc).__name__}: {str(exc)[:160]}",
                            parent_id=context.trace_parent_id,
                            step_id=step_id,
                        )
                        traces.append(trace)
                        self._append_tool_error(
                            messages,
                            ledger,
                            call,
                            "tool_exception",
                            detail=trace.detail,
                        )
                        continue

                    traces.append(observation.trace)
                    self._extend_unique(gaps, observation.gaps)
                    for item in observation.evidence:
                        if item.content_hash in evidence_hashes:
                            continue
                        evidence_hashes.add(item.content_hash)
                        evidence.append(item)
                    public_observation = {
                        "ok": True,
                        "tool": observation.tool,
                        "query": observation.query,
                        "observation": observation.observation,
                        "evidence": [
                            self._public_evidence(item)
                            for item in observation.evidence
                        ],
                        "evidence_hashes": list(observation.evidence_hashes),
                        "gaps": list(observation.gaps),
                    }
                    ledger.add("tool_result", public_observation)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.call_id,
                            "content": json.dumps(
                                public_observation,
                                ensure_ascii=False,
                            ),
                        }
                    )
                continue

            try:
                status, draft, final_gaps, bindings = self._parse_finish(
                    turn.content,
                    context=context,
                    evidence_hashes=evidence_hashes,
                )
            except ValueError as exc:
                finish_failures += 1
                invalid_actions += 1
                reason = str(exc)
                ledger.add("invalid_action", {"reason": reason})
                if finish_failures == 1 and _round < context.policy.max_steps:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "上一条终止输出无效。请保留当前任务和全部观察，"
                                "不要重启研究；修复后只输出 FINAL_JSON。"
                                f"错误：{reason}"
                            ),
                        }
                    )
                    continue
                return self._stopped_outcome(
                    task_frame=task_frame,
                    status="partial",
                    stop_reason="invalid_model_finish",
                    gap="模型未能返回可验证的结构化终止结果",
                    ledger=ledger,
                    evidence=evidence,
                    traces=traces,
                    gaps=gaps,
                    llm_calls=llm_calls,
                    tool_calls=tool_calls,
                    invalid_actions=invalid_actions,
                )

            self._extend_unique(gaps, final_gaps)
            self._extend_unique(gaps, tuple(item.gap for item in bindings))
            ledger.add(
                "finish",
                {
                    "status": status,
                    "stop_reason": "model_finish",
                    "bindings": [item.to_dict() for item in bindings],
                    "gaps": list(final_gaps),
                },
            )
            return AgentOutcome(
                task_frame_hash=task_frame.task_frame_hash,
                status=status,
                draft=draft,
                evidence=tuple(evidence),
                traces=tuple(traces),
                gaps=tuple(gaps),
                stop_reason="model_finish",
                events=tuple(ledger.events),
                bindings=bindings,
                usage=AgentUsage(llm_calls, tool_calls, invalid_actions),
            )

        return self._stopped_outcome(
            task_frame=task_frame,
            status="partial",
            stop_reason="step_exhausted",
            gap="研究预算已耗尽，仍有必需输出未覆盖",
            ledger=ledger,
            evidence=evidence,
            traces=traces,
            gaps=gaps,
            llm_calls=llm_calls,
            tool_calls=tool_calls,
            invalid_actions=invalid_actions,
        )

    @staticmethod
    def _system_prompt(
        task_frame: TaskFrame,
        context: ResearchRunContext,
        registry: ResearchToolRegistry,
    ) -> str:
        return (
            "你是连续运行的金融研究 Agent。始终回答最初的不可变任务；每次看到"
            "工具原始观察后，自主决定继续查、改写查询或停止。只能调用本轮提供的"
            "只读工具，不能臆造工具结果。事实判断必须绑定工具返回的 evidence_hashes；"
            "缺数据要写 gap。不要套固定标题、行数或段落模板。终止时不要调用工具，"
            "只输出一个 JSON 对象："
            '{"status":"completed|partial","draft":"自然语言回答",'
            '"gaps":["..."],"bindings":[{"output_id":"...",'
            '"evidence_hashes":["..."],"gap":""}]}。'
            "completed 必须覆盖所有 required outputs；partial 必须明确缺口。\n"
            f"任务哈希：{task_frame.task_frame_hash}\n"
            f"可用工具：\n{registry.prompt_block(context.contract.allowed_capabilities)}"
        )

    @staticmethod
    def _task_prompt(
        task_frame: TaskFrame,
        context: ResearchRunContext,
    ) -> str:
        return json.dumps(
            {
                "task_frame": task_frame.to_dict(),
                "research_contract": context.contract.to_dict(),
                "today": context.today,
                "latest_data_date": context.latest_data_date,
                "date_rule": (
                    "today 不是行情日期；市场事实服从 latest_data_date 和证据日期"
                ),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _assistant_message(turn: ModelTurn) -> dict[str, object]:
        message: dict[str, object] = {
            "role": "assistant",
            "content": turn.content,
        }
        if turn.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(
                            call.to_dict()["arguments"],
                            ensure_ascii=False,
                        ),
                    },
                }
                for call in turn.tool_calls
            ]
        return message

    @staticmethod
    def _append_tool_error(
        messages: list[dict[str, object]],
        ledger: _EpisodeLedger,
        call: ModelToolCall,
        error: str,
        *,
        detail: str = "",
    ) -> None:
        payload = {
            "ok": False,
            "tool": call.name,
            "error": error,
            "detail": detail,
        }
        ledger.add("tool_error", payload)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.call_id,
                "content": json.dumps(payload, ensure_ascii=False),
            }
        )

    @staticmethod
    def _parse_finish(
        content: str,
        *,
        context: ResearchRunContext,
        evidence_hashes: set[str],
    ) -> tuple[
        EpisodeStatus,
        str,
        tuple[str, ...],
        tuple[OutputEvidenceBinding, ...],
    ]:
        value = _parse_json_object(content)
        if value is None:
            raise ValueError("finish must be one JSON object")
        status = value.get("status")
        if status not in _FINISH_STATUSES:
            raise ValueError("finish status must be completed or partial")
        draft = value.get("draft")
        if not isinstance(draft, str):
            raise ValueError("finish draft must be a string")
        if status == "completed" and not draft.strip():
            raise ValueError("completed finish draft must be non-empty")
        raw_gaps = value.get("gaps", [])
        if not isinstance(raw_gaps, list) or any(
            not isinstance(item, str) for item in raw_gaps
        ):
            raise ValueError("finish gaps must be a string list")
        gaps = tuple(
            dict.fromkeys(item.strip() for item in raw_gaps if item.strip())
        )
        raw_bindings = value.get("bindings")
        if not isinstance(raw_bindings, list):
            raise ValueError("finish bindings must be a list")
        bindings: list[OutputEvidenceBinding] = []
        allowed_outputs = {
            item.output_id for item in context.contract.required_outputs
        }
        for raw in raw_bindings:
            if not isinstance(raw, dict):
                raise ValueError("each finish binding must be an object")
            raw_hashes = raw.get("evidence_hashes", [])
            if not isinstance(raw_hashes, list):
                raise ValueError("binding evidence_hashes must be a list")
            binding = OutputEvidenceBinding(
                output_id=str(raw.get("output_id") or ""),
                evidence_hashes=tuple(raw_hashes),
                gap=str(raw.get("gap") or ""),
            )
            if binding.output_id not in allowed_outputs:
                raise ValueError(f"unknown required output: {binding.output_id}")
            unknown = set(binding.evidence_hashes) - evidence_hashes
            if unknown:
                raise ValueError(
                    "binding contains unknown evidence hash: "
                    + ",".join(sorted(unknown))
                )
            bindings.append(binding)

        if len({item.output_id for item in bindings}) != len(bindings):
            raise ValueError("duplicate output binding")
        if status == "completed":
            binding_map = {item.output_id: item for item in bindings}
            missing = [
                required.output_id
                for required in context.contract.required_outputs
                if required.required
                and (
                    required.output_id not in binding_map
                    or not binding_map[required.output_id].evidence_hashes
                )
            ]
            if missing:
                raise ValueError(
                    "required output lacks evidence: " + ",".join(missing)
                )
        return cast(EpisodeStatus, status), draft, gaps, tuple(bindings)

    @staticmethod
    def _public_evidence(item: AgentEvidence) -> dict[str, object]:
        return {
            "tool": item.tool,
            "title": item.title,
            "detail": item.detail,
            "source": item.source,
            "source_date": item.source_date,
            "evidence_tier": item.evidence_tier,
            "supports": list(item.supports),
            "contradicts": list(item.contradicts),
            "independent_key": item.independent_key,
            "freshness": item.freshness,
            "content_hash": item.content_hash,
        }

    @staticmethod
    def _extend_unique(target: list[str], values: tuple[str, ...]) -> None:
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in target:
                target.append(cleaned)

    @staticmethod
    def _stopped_outcome(
        *,
        task_frame: TaskFrame,
        status: EpisodeStatus,
        stop_reason: str,
        gap: str,
        ledger: _EpisodeLedger,
        evidence: list[AgentEvidence],
        traces: list[ProviderTrace],
        gaps: list[str],
        llm_calls: int,
        tool_calls: int,
        invalid_actions: int,
    ) -> AgentOutcome:
        final_gaps = list(gaps)
        ContinuousAgentEpisode._extend_unique(final_gaps, (gap,))
        ledger.add(
            "finish",
            {
                "status": status,
                "stop_reason": stop_reason,
                "gaps": final_gaps,
            },
        )
        return AgentOutcome(
            task_frame_hash=task_frame.task_frame_hash,
            status=status,
            draft="",
            evidence=tuple(evidence),
            traces=tuple(traces),
            gaps=tuple(final_gaps),
            stop_reason=stop_reason,
            events=tuple(ledger.events),
            bindings=(),
            usage=AgentUsage(llm_calls, tool_calls, invalid_actions),
        )


def _parse_json_object(content: str) -> dict[str, object] | None:
    text = str(content or "").strip()
    fenced = _FINAL_JSON_RE.fullmatch(text)
    if fenced is not None:
        text = fenced.group(1)
    if not text.startswith("{") or not text.endswith("}"):
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


__all__ = ["ContinuousAgentEpisode", "DEFAULT_LLM_TIMEOUT"]
