from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import asdict, dataclass
from pathlib import Path

from intelligence.api.structured_reports import (
    ask_result_modules,
    complete_report,
    new_structured_report,
    upsert_report_module,
)
from intelligence.services import run_store as rs
from intelligence.services.ask import (
    AskOptions,
    AskResult,
    answer_query,
    render_conversation_answer,
)
from intelligence.services.conversation_store import (
    Conversation,
    ConversationStore,
    Message,
)
from intelligence.services.llm_refine import LLMStreamCancelled
from intelligence.services.run_store import RunStore, redact
from intelligence.workbench_skills.contracts import (
    SkillExecutionContext,
    SkillOutput,
)
from intelligence.workbench_skills.registry import (
    SkillRegistry,
    builtin_skill_registry,
)
from intelligence.workbench_skills.router import (
    SkillMode,
    SkillRouteResult,
    route_skills,
)

RECENT_MESSAGE_LIMIT = 6
SUMMARY_CHAR_LIMIT = 2400
_INTERNAL_CITATION_PATTERN = re.compile(
    r"\[(?:D|P|L|G|R|S|W)\d+\]"
)
_INTERNAL_CODE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])[DPGRSW]\d+(?![A-Za-z0-9_])"
)
_EVIDENCE_LAYER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])L([1-4])(?:\s*级(?:别)?)?(?![A-Za-z0-9_])"
)
_INTERNAL_TIER_TOKEN_PATTERN = re.compile(
    r"(?:high/)?L[1-4](?:_L[1-4])+(?:_[A-Za-z0-9]+)*",
    re.IGNORECASE,
)
_EVIDENCE_LAYER_SUMMARY_PATTERN = re.compile(
    r"(?:整体)?证据层分布为\s*"
    r"L[1-4](?:\s*[×x*]\s*\d+)?"
    r"(?:\s*[、,，]\s*L[1-4](?:\s*[×x*]\s*\d+)?)*"
    r"\s*[，,]?\s*"
)
_INTERNAL_FIELD_PATTERN = re.compile(
    r'"?(?:candidate_tier|priority_score|cycle_status|warnings?)"?'
    r'\s*[:=]\s*(?:"[^"]*"|[^,，}\]\n]+)[,，]?',
    re.IGNORECASE,
)
_JSON_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*[\[{].*?[\]}]\s*```",
    re.IGNORECASE | re.DOTALL,
)
_HUMAN_READABLE_REPLACEMENTS = (
    ("Daily Review 确定性投影数据", "本地复盘数据"),
    ("Daily Review", "本地复盘"),
    ("本地复盘确定性投影数据", "本地复盘数据"),
    ("本地复盘确定性投影", "本地复盘数据"),
    ('并被系统标注为"沸点"', '，盘面状态达到"沸点"'),
    ("系统统一标注为", "盘面表现为"),
    ("盘面 L4 信号", "盘面信号"),
    ("盘面L4信号", "盘面信号"),
    ("L4 信号", "盘面信号"),
    ("L4信号", "盘面信号"),
    ("L3 硬证据", "公告等硬证据"),
    ("L3硬证据", "公告等硬证据"),
    ("RAG检索的wiki向量源降级未接入", "知识库资料没有提供可用补充"),
    ("RAG 检索的 wiki 向量源降级未接入", "知识库资料没有提供可用补充"),
    ("replay 发酵信号也未匹配到任何主题", "历史发酵信号也未提供可用信息"),
    ("replay 发酵信号", "历史发酵信号"),
    ("模块 replay", "历史信号回检"),
    ("replay", "历史信号回检"),
    ("wiki 向量检索无可用命中", "知识库没有提供可用补充"),
    ("wiki 向量检索", "知识库检索"),
    ("wiki向量源", "知识库资料"),
    ("wiki 向量源", "知识库资料"),
    ("wiki-rag", "知识库检索"),
    ("图谱命中的", "知识图谱关联到的"),
    ("图谱命中", "知识图谱关联"),
    ("graph_only低置信关联", "低置信关联"),
    ("graph_only/低置信暴露", "低置信关联"),
    ("graph_only", "低置信关联"),
    ("DuckDB 同题材强势替代队列为空", "本地盘面数据没有提供同题材强势替代方向"),
    ("命中主题=", "相关主题："),
    ("命中主要来自", "现有信息主要来自"),
    ("cycle_status", "阶段状态"),
    ("candidate_tier", "候选分层"),
    ("priority_score", "优先级"),
    ("diff_ratio", "成交边际变化"),
    ("模块路由", "分析路径"),
    ("rerank", "检索重排"),
    ("RAG 遥测", "检索诊断"),
    ("RAG", "知识库检索"),
    ("wiki", "知识库"),
    ("降权", "降低可信度"),
)
_EVIDENCE_LAYER_REPLACEMENTS = {
    "1": "行业资料",
    "2": "公司基础资料",
    "3": "公告等硬证据",
    "4": "盘面信号",
}


@dataclass(frozen=True)
class ConversationContext:
    summary: str
    recent_messages: tuple[Message, ...]

    def to_prompt_block(self) -> str:
        recent = "\n".join(
            f"{message.role}: {message.content}" for message in self.recent_messages
        )
        return (
            "## 较早消息摘要\n"
            f"{self.summary or '（无较早消息）'}\n\n"
            "## 最近消息原文\n"
            f"{recent or '（无历史消息）'}"
        )


@dataclass(frozen=True)
class TurnResult:
    status: str
    content: str
    selected_skill_ids: tuple[str, ...]
    invoked_skill_ids: tuple[str, ...]


def _summarize_messages(messages: Sequence[Message]) -> str:
    text = "\n".join(f"{message.role}: {message.content}" for message in messages)
    if len(text) <= SUMMARY_CHAR_LIMIT:
        return text
    return "…" + text[-(SUMMARY_CHAR_LIMIT - 1) :]


def _redact_object(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_redact_object(item) for item in value]
    if isinstance(value, dict):
        return {
            redact(str(key)): _redact_object(item)
            for key, item in value.items()
        }
    return value


def sanitize_conversation_answer(text: str) -> str:
    cleaned = _JSON_BLOCK_PATTERN.sub("", text)
    cleaned = _INTERNAL_FIELD_PATTERN.sub("", cleaned)
    cleaned = _EVIDENCE_LAYER_SUMMARY_PATTERN.sub("", cleaned)
    cleaned = _INTERNAL_CITATION_PATTERN.sub("", cleaned)
    for internal, readable in _HUMAN_READABLE_REPLACEMENTS:
        cleaned = cleaned.replace(internal, readable)
    cleaned = _INTERNAL_TIER_TOKEN_PATTERN.sub("较高置信候选", cleaned)
    cleaned = _EVIDENCE_LAYER_PATTERN.sub(
        lambda match: _EVIDENCE_LAYER_REPLACEMENTS[match.group(1)],
        cleaned,
    )
    cleaned = re.sub(
        r"公告等硬证据(?:\s*(?:硬)?证据)+", "公告等硬证据", cleaned
    )
    cleaned = re.sub(r"行业资料(?:\s*行业资料)+", "行业资料", cleaned)
    cleaned = re.sub(
        r"公司基础资料(?:\s*(?:公司)?基础资料)+", "公司基础资料", cleaned
    )
    cleaned = re.sub(r"盘面信号(?:\s*盘面信号)+", "盘面信号", cleaned)
    cleaned = re.sub(r"盘面\s*盘面信号", "盘面信号", cleaned)
    cleaned = re.sub(r"公告等硬证据\s*(?=(?:公告|订单|认证|量产|客户验证))", "", cleaned)
    cleaned = re.sub(
        r"(?<![A-Za-z])local(?![A-Za-z])", "本地", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"本地\s*本地", "本地", cleaned)
    cleaned = re.sub(r"本地复盘\s*确定性投影(?:数据)?", "本地复盘数据", cleaned)
    cleaned = cleaned.replace("知识知识图谱", "知识图谱")
    cleaned = _INTERNAL_CODE_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", cleaned)
    cleaned = re.sub(r" +([，。；：、])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_conversation_context(
    conversation: Conversation,
    messages: Sequence[Message],
    *,
    current_run_id: str,
) -> ConversationContext:
    history = [
        message
        for message in messages
        if message.run_id != current_run_id
        and message.status == "completed"
        and message.role in {"user", "assistant"}
        and message.content.strip()
    ]
    recent = tuple(history[-RECENT_MESSAGE_LIMIT:])
    older = history[:-RECENT_MESSAGE_LIMIT]
    summary = _summarize_messages(older) if older else conversation.summary
    return ConversationContext(summary=summary, recent_messages=recent)


class TurnOrchestrator:
    def __init__(
        self,
        *,
        repo_root: Path,
        conversation_store: ConversationStore,
        run_store: RunStore,
        answer_query_fn: Callable[[AskOptions], AskResult] | None = None,
        route_skills_fn: Callable[..., SkillRouteResult] | None = None,
        skill_registry: SkillRegistry | None = None,
        llm_model: str | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        cancellation_reason: Callable[[], str | None] | None = None,
        event_id_prefix: str = "",
    ) -> None:
        self.repo_root = repo_root
        self.conversation_store = conversation_store
        self.run_store = run_store
        self.answer_query = answer_query_fn or answer_query
        self.route_skills = route_skills_fn or route_skills
        self.skill_registry = skill_registry or builtin_skill_registry()
        self.llm_model = llm_model
        self.is_cancelled = is_cancelled or (lambda: False)
        self.cancellation_reason = cancellation_reason or (lambda: None)
        self.event_id_prefix = event_id_prefix

    def run_turn(
        self,
        *,
        conversation_id: str,
        run_id: str,
        assistant_message_id: str,
        query: str,
        skill_mode: SkillMode,
        selected_skill_ids: Sequence[str],
    ) -> TurnResult:
        report = new_structured_report(
            run_id=run_id,
            question=query,
            task_type="ask",
        )
        selected: list[str] = []
        manual_selected = list(dict.fromkeys(selected_skill_ids))
        invoked: list[str] = []
        warnings: list[str] = []
        citations: list[dict[str, object]] = []
        text_chunks: list[str] = []
        skill_outputs: list[SkillOutput] = []
        self._emit(
            run_id,
            assistant_message_id,
            "message:start",
            "message.start",
            {"status": "running"},
            conversation_id,
        )
        self._emit(
            run_id,
            assistant_message_id,
            "report:start",
            "report.start",
            {"report": report},
            conversation_id,
        )
        try:
            conversation = self.conversation_store.load_conversation(conversation_id)
            context = build_conversation_context(
                conversation,
                self.conversation_store.load_messages(conversation_id),
                current_run_id=run_id,
            )
            self.conversation_store.update_summary_text(
                conversation_id, context.summary
            )
            route = self.route_skills(
                query,
                "ask",
                skill_mode,
                selected_skill_ids,
                registry=self.skill_registry.definitions,
            )
            selected = [selection.skill_id for selection in route.selections]
            self._trace(
                run_id,
                assistant_message_id,
                conversation_id,
                "route",
                "route_skills",
                {
                    "selected": [
                        {
                            "skill_id": selection.skill_id,
                            "source": selection.selection_source,
                            "reason": selection.reason,
                        }
                        for selection in route.selections
                    ],
                    "fallback_to_ask": route.fallback_to_ask,
                },
            )
            self._check_cancelled()

            for selection in route.selections:
                self._check_cancelled()
                skill_id = selection.skill_id
                invoked.append(skill_id)
                self._emit(
                    run_id,
                    assistant_message_id,
                    f"skill:{skill_id}:start",
                    "skill.start",
                    {
                        "skill_id": skill_id,
                        "selection_source": selection.selection_source,
                        "reason": selection.reason,
                    },
                    conversation_id,
                )
                skill_pool = ThreadPoolExecutor(
                    max_workers=1,
                    thread_name_prefix=f"workbench-{skill_id}",
                )
                try:
                    future = skill_pool.submit(
                        self.skill_registry.executors[skill_id].execute,
                        SkillExecutionContext(
                            query=query,
                            task_type="ask",
                            user_id=self.run_store.user_id,
                            run_id=run_id,
                            conversation_id=conversation_id,
                            repo_root=self.repo_root,
                            run_store=self.run_store,
                        ),
                    )
                    output = future.result(
                        timeout=self.skill_registry.definitions[
                            skill_id
                        ].timeout_seconds
                    )
                except Exception as exc:  # noqa: BLE001
                    warning = (
                        f"Skill {skill_id} 执行超时"
                        if isinstance(exc, FuturesTimeoutError)
                        else f"Skill {skill_id} 执行失败（{type(exc).__name__}）"
                    )
                    warnings.append(warning)
                    self.run_store.add_degrade(run_id, warning)
                    module = self._skill_warning_module(skill_id, warning)
                    self._emit_module(
                        run_id,
                        assistant_message_id,
                        conversation_id,
                        report,
                        module,
                        f"skill:{skill_id}:warning",
                    )
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"skill:{skill_id}:result",
                        "skill.result",
                        {
                            "skill_id": skill_id,
                            "status": "degraded",
                            "warnings": [warning],
                        },
                        conversation_id,
                    )
                else:
                    skill_outputs.append(output)
                    warnings.extend(output.warnings)
                    citations.extend(output.citations)
                    for warning in output.warnings:
                        self.run_store.add_degrade(run_id, warning)
                    for index, module in enumerate(output.modules, start=1):
                        self._emit_module(
                            run_id,
                            assistant_message_id,
                            conversation_id,
                            report,
                            module,
                            f"skill:{skill_id}:module:{index}",
                        )
                    self._emit(
                        run_id,
                        assistant_message_id,
                        f"skill:{skill_id}:result",
                        "skill.result",
                        {
                            "skill_id": skill_id,
                            "status": "degraded" if output.warnings else "completed",
                            "output": asdict(output),
                        },
                        conversation_id,
                    )
                finally:
                    skill_pool.shutdown(wait=False, cancel_futures=True)
                self._check_cancelled()

            def emit_text_delta(delta: str) -> None:
                self._check_cancelled()
                text_chunks.append(delta)
                self._emit(
                    run_id,
                    assistant_message_id,
                    f"text:{len(text_chunks):06d}",
                    "text.delta",
                    {"delta": delta},
                    conversation_id,
                )

            result = self.answer_query(
                AskOptions(
                    query=query,
                    user=self.run_store.user_id,
                    compose=True,
                    compose_self_review=False,
                    compose_revise_on_warn=False,
                    market_db_path=self.repo_root
                    / "db"
                    / "market_feature_store.duckdb",
                    conversation_context=context.to_prompt_block(),
                    supplemental_evidence=self._skill_evidence(skill_outputs),
                    stream_text_delta=emit_text_delta,
                    stream_cancel_check=self.is_cancelled,
                )
            )
            self._check_cancelled()
            self._record_retrieval(
                run_id,
                assistant_message_id,
                conversation_id,
                result,
            )
            self.run_store.update_provenance(run_id, source_date=result.trade_date)
            warnings.extend(result.warnings)
            for warning in result.warnings:
                self.run_store.add_degrade(run_id, warning)
            citations.extend(
                {
                    "tag": citation.tag,
                    "source": citation.source,
                    "detail": citation.detail,
                }
                for citation in result.citations
            )
            for index, module in enumerate(ask_result_modules(result), start=1):
                self._emit_module(
                    run_id,
                    assistant_message_id,
                    conversation_id,
                    report,
                    module,
                    f"ask:module:{index}",
                )
            for index, citation in enumerate(citations, start=1):
                self._emit(
                    run_id,
                    assistant_message_id,
                    f"citation:{index:04d}",
                    "citation.ready",
                    {"citation": citation},
                    conversation_id,
                )

            answer_text = render_conversation_answer(result)
            if result.synthesis is not None:
                answer_text = sanitize_conversation_answer(answer_text)
            elif text_chunks:
                answer_text = "".join(text_chunks)
            else:
                emit_text_delta(answer_text)
            if result.synthesis is None:
                fallback = "llm_unavailable_template_answer"
                warnings.append(fallback)
                self.run_store.add_degrade(run_id, fallback)

            complete_report(
                report,
                as_of=result.trade_date,
                warnings=warnings,
                llm_provider=result.llm_provider,
                llm_model=self.llm_model if result.llm_provider else None,
            )
            self.run_store.add_artifact(
                run_id,
                "answer.md",
                redact(answer_text),
                renderer="markdown",
                title=redact(f"对话回答：{query[:24]}"),
            )
            self.run_store.add_artifact(
                run_id,
                "report.json",
                json.dumps(_redact_object(report), ensure_ascii=False, indent=2),
                renderer="structured_report",
                title="结构化对话报告",
            )
            self._check_cancelled()
            assistant = self.conversation_store.revise_message(
                conversation_id,
                assistant_message_id,
                content=answer_text,
                status="completed",
                selected_skill_ids=manual_selected,
                invoked_skill_ids=invoked,
                citations=citations,
                degrades=warnings,
            )
            self._emit(
                run_id,
                assistant_message_id,
                "report:complete",
                "report.complete",
                {"report": report},
                conversation_id,
            )
            self._emit(
                run_id,
                assistant_message_id,
                "message:complete",
                "message.complete",
                {"message": asdict(assistant)},
                conversation_id,
            )
            self.run_store.finish_run(run_id, rs.STATUS_COMPLETED)
            return TurnResult(
                status=rs.STATUS_COMPLETED,
                content=assistant.content,
                selected_skill_ids=tuple(selected),
                invoked_skill_ids=tuple(invoked),
            )
        except LLMStreamCancelled:
            if self.cancellation_reason() == "executor_timeout":
                return self._fail(
                    conversation_id,
                    run_id,
                    assistant_message_id,
                    report,
                    selected,
                    manual_selected,
                    invoked,
                    warnings,
                    citations,
                    text_chunks,
                    TimeoutError("executor_timeout"),
                )
            return self._cancel(
                conversation_id,
                run_id,
                assistant_message_id,
                report,
                selected,
                manual_selected,
                invoked,
                warnings,
                citations,
                text_chunks,
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(
                conversation_id,
                run_id,
                assistant_message_id,
                report,
                selected,
                manual_selected,
                invoked,
                warnings,
                citations,
                text_chunks,
                exc,
            )

    def _emit(
        self,
        run_id: str,
        message_id: str,
        event_id: str,
        event_type: str,
        payload: dict[str, object],
        conversation_id: str,
    ) -> None:
        self.run_store.append_stream_event(
            run_id,
            event_id=f"{self.event_id_prefix}{event_id}",
            event_type=event_type,
            payload=payload,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    def _check_cancelled(self) -> None:
        if self.is_cancelled():
            raise LLMStreamCancelled()

    def _emit_module(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        report: dict,
        module: dict,
        event_id: str,
    ) -> None:
        upsert_report_module(report, module)
        self._emit(
            run_id,
            message_id,
            event_id,
            "report.module",
            {"module": module},
            conversation_id,
        )

    def _trace(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        step_id: str,
        name: str,
        output: dict[str, object],
    ) -> None:
        step = self.run_store.append_step(
            run_id,
            step_id=step_id,
            name=name,
            status="completed",
            output_summary=json.dumps(output, ensure_ascii=False),
        )
        self._emit(
            run_id,
            message_id,
            f"trace:{step_id}",
            "trace.step",
            {"step": step},
            conversation_id,
        )

    def _record_retrieval(
        self,
        run_id: str,
        message_id: str,
        conversation_id: str,
        result: AskResult,
    ) -> None:
        self._trace(
            run_id,
            message_id,
            conversation_id,
            "retrieve",
            "ask_retrieve_compose",
            {
                "trade_date": result.trade_date,
                "matched_theme": result.matched_theme,
                "citation_count": len(result.citations),
            },
        )

    def _cancel(
        self,
        conversation_id: str,
        run_id: str,
        message_id: str,
        report: dict,
        selected: list[str],
        manual_selected: list[str],
        invoked: list[str],
        warnings: list[str],
        citations: list[dict[str, object]],
        text_chunks: list[str],
    ) -> TurnResult:
        warning = "用户已取消本轮执行"
        if warning not in warnings:
            warnings.append(warning)
        self.run_store.add_degrade(run_id, warning)
        report["status"] = rs.STATUS_CANCELLED
        report["warnings"] = list(dict.fromkeys(warnings))
        content = "".join(text_chunks)
        assistant = self.conversation_store.revise_message(
            conversation_id,
            message_id,
            content=content,
            status=rs.STATUS_CANCELLED,
            selected_skill_ids=manual_selected,
            invoked_skill_ids=invoked,
            citations=citations,
            degrades=warnings,
        )
        self.run_store.add_artifact(
            run_id,
            "report.json",
            json.dumps(_redact_object(report), ensure_ascii=False, indent=2),
            renderer="structured_report",
            title="已取消的结构化对话报告",
        )
        self._emit(
            run_id,
            message_id,
            "message:cancelled",
            "message.error",
            {"status": rs.STATUS_CANCELLED, "message": asdict(assistant)},
            conversation_id,
        )
        self.run_store.finish_run(run_id, rs.STATUS_CANCELLED)
        return TurnResult(
            status=rs.STATUS_CANCELLED,
            content=assistant.content,
            selected_skill_ids=tuple(selected),
            invoked_skill_ids=tuple(invoked),
        )

    def _fail(
        self,
        conversation_id: str,
        run_id: str,
        message_id: str,
        report: dict,
        selected: list[str],
        manual_selected: list[str],
        invoked: list[str],
        warnings: list[str],
        citations: list[dict[str, object]],
        text_chunks: list[str],
        error: Exception,
    ) -> TurnResult:
        warning = f"本轮执行失败（{type(error).__name__}）"
        warnings.append(warning)
        report["status"] = rs.STATUS_FAILED
        report["warnings"] = list(dict.fromkeys(warnings))
        content = "".join(text_chunks)
        assistant = self.conversation_store.revise_message(
            conversation_id,
            message_id,
            content=content,
            status=rs.STATUS_FAILED,
            selected_skill_ids=manual_selected,
            invoked_skill_ids=invoked,
            citations=citations,
            degrades=warnings,
        )
        self._emit(
            run_id,
            message_id,
            "report:error",
            "report.error",
            {"report": report},
            conversation_id,
        )
        self._emit(
            run_id,
            message_id,
            "message:error",
            "message.error",
            {"status": rs.STATUS_FAILED, "message": asdict(assistant)},
            conversation_id,
        )
        self.run_store.finish_run(
            run_id,
            rs.STATUS_FAILED,
            error=warning,
        )
        return TurnResult(
            status=rs.STATUS_FAILED,
            content=assistant.content,
            selected_skill_ids=tuple(selected),
            invoked_skill_ids=tuple(invoked),
        )

    @staticmethod
    def _skill_evidence(outputs: Sequence[SkillOutput]) -> str:
        if not outputs:
            return ""
        lines: list[str] = []
        for output in outputs:
            as_of = f"（截至 {output.as_of}）" if output.as_of else ""
            lines.append(f"### {output.skill_id}{as_of}")
            for module in output.modules:
                title = module.get("title")
                if isinstance(title, str) and title.strip():
                    lines.append(f"- {title.strip()}")
                summary = module.get("summary")
                if isinstance(summary, str) and summary.strip():
                    lines.append(f"  - 摘要：{summary.strip()}")
                content = module.get("content")
                if isinstance(content, str) and content.strip():
                    lines.append(f"  - 正文：{content.strip()}")
                metrics = module.get("metrics")
                if isinstance(metrics, list):
                    metric_bits: list[str] = []
                    for metric in metrics:
                        if not isinstance(metric, dict):
                            continue
                        label = metric.get("label")
                        value = metric.get("value")
                        if isinstance(label, str) and value is not None:
                            metric_bits.append(f"{label}={value}")
                    if metric_bits:
                        lines.append("  - 指标：" + "；".join(metric_bits))
            if output.warnings:
                lines.append(
                    "- 数据质量提示：" + "；".join(output.warnings[:3])
                )
        return "\n".join(lines)

    @staticmethod
    def _skill_warning_module(skill_id: str, warning: str) -> dict[str, object]:
        return {
            "module_id": f"skill_{skill_id}_warning",
            "title": f"{skill_id} 降级",
            "kind": "warning",
            "status": "degraded",
            "summary": warning,
            "content": None,
            "metrics": [],
            "items": [],
            "table": None,
            "warnings": [warning],
            "provenance": {
                "source": skill_id,
                "as_of": None,
                "generated_by": "turn_orchestrator",
            },
        }
