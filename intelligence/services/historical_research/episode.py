"""Compose history calculations with the existing Episode and artifact writer."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from intelligence.services.agent_research import AgentEvidence
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import ToolRunResult, ToolSpec

if TYPE_CHECKING:
    from intelligence.services.run_store import RunStore


class HistorySession:
    """A same-user, same-conversation allowlist; model references are not paths."""

    def __init__(self, store: RunStore, run_id: str, conversation_id: str):
        self.store = store
        self.run_id = run_id
        self.conversation_id = conversation_id
        self.refs: dict[str, tuple[str, str]] = {}
        self.query_aliases: dict[str, str] = {}
        self.definition_refs: set[str] = set()
        run = store.load_run(run_id)
        if run.user != store.user_id or run.session_id != conversation_id:
            raise ValueError("history session identity mismatch")
        self.refresh()

    def refresh(self):
        # The prompt is bounded separately; authorization uses current metadata.
        related = [
            item
            for item in self.store.list_runs()
            if item.user == self.store.user_id and item.session_id == self.conversation_id
        ]
        for item in related:
            for artifact in item.artifacts:
                filename = str(artifact.get("path", ""))
                if (
                    filename.startswith("history-")
                    and artifact.get("visibility") == "public"
                ):
                    self.refs[f"{item.run_id}/{filename}"] = (item.run_id, filename)

    def save(self, kind: str, payload: dict) -> str:
        envelope = dict(
            payload,
            user_id=self.store.user_id,
            run_id=self.run_id,
            conversation_id=self.conversation_id,
            visibility="public",
        )
        artifact = self.store.add_history_artifact(self.run_id, kind, envelope)
        ref = f"{self.run_id}/{artifact.path}"
        self.refs[ref] = (self.run_id, artifact.path)
        if kind == "query":
            self.query_aliases[str(payload["query_id"])] = ref
            self.definition_refs.update(payload.get("definition_refs", ()))
        return ref

    def read(self, ref: str) -> dict:
        if ref not in self.refs:
            if not isinstance(ref, str) or len(ref) > 300 or ref.count("/") != 1:
                raise ValueError("history result reference is outside this conversation")
            run_id, filename = ref.split("/", 1)
            try:
                run = self.store.load_run(run_id)
            except (ValueError, FileNotFoundError) as exc:
                raise ValueError("history result reference is outside this conversation") from exc
            if run.user != self.store.user_id or run.session_id != self.conversation_id:
                raise ValueError("history result reference is outside this conversation")
            # The display index is bounded; same-conversation authorization isn't.
            self.store.read_history_artifact(run_id, filename)
            self.refs[ref] = (run_id, filename)
        run_id, filename = self.refs[ref]
        payload = self.store.read_history_artifact(run_id, filename)
        return payload

    def remember(self, ref: str, payload: dict):
        """Call only after the current task's scope check has passed."""
        filename = self.refs[ref][1]
        if filename.startswith("history-query-"):
            self.query_aliases[str(payload["query_id"])] = ref
            self.definition_refs.update(payload.get("definition_refs", ()))
        if filename.startswith("history-case-"):
            aliases = payload.get("query_aliases", {})
            self.query_aliases.update(
                {key: value for key, value in aliases.items() if value in self.refs}
            )
            self.definition_refs.update(payload.get("definition_refs", ()))

    def index(self) -> list[dict]:
        return [
            {"result_ref": ref, "kind": Path(filename).name.split("-")[1]}
            for ref, (_, filename) in self.refs.items()
        ]


def _compact(value) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")
    )


def _result(payload: dict, *, result_ref: str = "", tool: str = "history_query"):
    metadata = {
        key: payload[key]
        for key in (
            "query_id",
            "operation",
            "purpose",
            "status",
            "total_matched",
            "returned_count",
            "truncated",
            "coverage",
            "definition_refs",
            "gaps",
            "summary",
            "comparison",
            "universe",
            "matching_use",
            "outcome_definition",
            "contingency",
            "selection_fingerprint",
            "independence_policy",
        )
        if key in payload
    }
    metadata.update(
        result_ref=result_ref,
        research_only=True,
        decision_eligible=False,
        promotion_eligible=False,
    )
    preview = payload.get("preview", [])
    if not isinstance(preview, list):
        preview = []
    query_id = str(payload.get("query_id", ""))
    evidence = [
        AgentEvidence(
            tool=tool,
            title="历史研究计算口径与完整样本统计",
            detail=_compact(metadata),
            source="本地历史研究 · 可复算原件",
            internal_locator=result_ref,
            evidence_tier="L4_market_signal",
            freshness="historical",
            independent_key=query_id,
        )
    ]
    evidence.extend(
        AgentEvidence(
            tool=tool,
            title="历史观察样本",
            detail=_compact(row),
            source="本地历史研究 · 样本明细",
            internal_locator=result_ref,
            source_date=str(row.get("trade_date", row.get("end", ""))) or None,
            evidence_tier="L4_market_signal",
            freshness="historical",
            independent_key=query_id,
        )
        for row in preview[:25]
        if isinstance(row, dict)
    )
    return ToolRunResult(
        evidence=tuple(evidence),
        observation="探索结果，未认证规律；完整分母独立于摘要截断。"
        + _compact({"result_ref": result_ref, "query_id": query_id,
                    "total_matched": payload.get("total_matched"), "returned_count": payload.get("returned_count"),
                    "truncated": payload.get("truncated")})
        + _compact(metadata),
        trace=ProviderTrace(
            provider="duckdb_history_query",
            capability="finance_query",
            status="success",
            result_count=len(evidence),
            detail=query_id,
        ),
        gaps=tuple(str(item) for item in payload.get("gaps", ())),
        dataset="historical_research",
        caliber="retrospective_research_only",
        payload_field_names=tuple(sorted(payload)),
        payload_sha256=query_id,
        telemetry=metadata,
    )


def history_tool_specs(
    frame, context, db_path: Path, session: HistorySession | None
) -> list[ToolSpec]:
    if (
        frame.history_intent is None
        or "finance_query" not in context.contract.allowed_capabilities
    ):
        return []
    if session is not None:
        context.history_artifact_index[:] = session.index()
    from intelligence.services.historical_research.query import (
        HistoryQuery,
        HistoryQuerySpec,
        history_query_parameters,
    )
    from intelligence.services.research_tool_registry import _TOOL_CONTRACTS
    from intelligence.services.historical_research.intent import assert_history_window

    def assert_dependency_scope(draft, aliases, *, visited=None):
        """A draft's declared window cannot narrow its actual source material."""
        visited = set() if visited is None else visited

        def references(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key.endswith("_refs") and isinstance(child, (list, tuple)):
                        yield from child
                    else:
                        yield from references(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    yield from references(child)

        # The alias table is also restored by remember(); check every entry that
        # would become available, even if this version's prose does not cite it.
        candidates = (*references(draft), *aliases.values())
        for candidate in candidates:
            if candidate == draft.get("case_id"):
                continue  # A hypothesis may cite its containing case identity.
            ref = aliases.get(candidate, candidate)
            if ref in visited:
                continue
            visited.add(ref)
            assert_read_scope(session.read(ref), visited=visited)

    def assert_read_scope(payload, *, visited=None):
        cutoff = context.information_cutoff.as_of_date.isoformat()
        learned_at = payload.get("knowledge_cutoff")
        if learned_at and learned_at > cutoff:
            raise ValueError("historical_artifact_after_information_cutoff")
        spec = payload.get("spec", {})
        windows = [(spec.get("start"), spec.get("end"))]
        if spec.get("search_start"):
            windows.append((spec["search_start"], spec.get("search_end")))
        if "draft" in payload:
            if not learned_at:
                raise ValueError("historical_artifact_cutoff_unknown")
            windows = [(payload["draft"].get("window_start"), payload["draft"].get("window_end"))]
        for start, end in windows:
            assert_history_window(frame.history_intent, start, end, cutoff=cutoff)
        for rows in payload.get("inputs", {}).values():
            if any((row.get("trade_date") or row.get("event_date") or "") > cutoff for row in rows):
                raise ValueError("historical_artifact_after_information_cutoff")
        if "draft" in payload:
            aliases = dict(session.query_aliases)
            aliases.update(payload.get("query_aliases", {}))
            assert_dependency_scope(payload["draft"], aliases, visited=visited)

    def parse(arguments):
        spec = HistoryQuerySpec.from_arguments(arguments)
        if spec.preview_limit > 25:
            raise ValueError("history preview limit must be 1..25")
        return spec, _compact(asdict(spec))

    def run(spec, tool_context):
        tool_context.remaining()
        assert_history_window(frame.history_intent, spec.start, spec.end)
        if spec.search_start is not None:
            assert_history_window(frame.history_intent, spec.search_start, spec.search_end)
        payload = HistoryQuery(db_path).run(
            spec,
            information_cutoff=context.information_cutoff,
            deadline=tool_context.deadline,
            is_cancelled=tool_context.is_cancelled,
        )
        payload["operation"] = spec.operation
        payload["purpose"] = frame.history_intent.purpose
        payload["knowledge_cutoff"] = context.information_cutoff.as_of_date.isoformat()
        payload["authorized_scope"] = frame.history_intent.to_dict()
        payload["pending_sources"] = [
            {
                "source": source,
                "status": "pending_sync",
                "scope": "user_declared_unsynced",
                "scheduled": False,
            }
            for source in ("l2", "evening_sellside", "morning_brief")
        ]
        ref = session.save("query", payload) if session else ""
        metadata = {
            key: payload.get(key)
            for key in (
                "query_id",
                "operation",
                "purpose",
                "status",
                "total_matched",
                "returned_count",
                "coverage",
                "definition_refs",
            )
        }
        metadata["result_ref"] = ref
        metadata["execution_status"] = "success"
        context.history_results.append(metadata)
        return _result(payload, result_ref=ref)

    query_parameters = history_query_parameters()
    query_parameters["properties"]["preview_limit"]["maximum"] = 25
    specs = [
        ToolSpec(
            name="history_query",
            capability="finance_query",
            description="重建历史行情、计算时间特征、召回相似案例及完整条件样本比较。先查询实体候选核对精确代码；不确定窗口可先提出候选窗口并注明。",
            contract=_TOOL_CONTRACTS["history_query"],
            cost="local",
            freshness="historical",
            runner=run,
            parameters=query_parameters,
            parse_arguments=parse,
        )
    ]
    if session is None:
        return specs

    def parse_read(arguments):
        if set(arguments) - {"result_ref", "offset", "limit"}:
            raise ValueError("unsupported history read arguments")
        ref = arguments.get("result_ref")
        offset, limit = arguments.get("offset", 0), arguments.get("limit", 25)
        if (
            not isinstance(ref, str)
            or type(offset) is not int
            or not 0 <= offset <= 100000
        ):
            raise ValueError("invalid history reference or offset")
        if type(limit) is not int or not 1 <= limit <= 25:
            raise ValueError("history preview limit must be 1..25")
        return (ref, offset, limit), _compact(arguments)

    def read(value, tool_context):
        tool_context.remaining()
        ref, offset, limit = value
        payload = session.read(ref)
        assert_read_scope(payload)
        session.remember(ref, payload)
        if "/history-case-" in ref:
            return ToolRunResult(
                evidence=(),
                observation="研究草稿，不是已验证事实：" + _compact(payload),
                trace=ProviderTrace(
                    provider="history_artifact",
                    capability="finance_query",
                    status="success",
                ),
                dataset="historical_research_draft",
                telemetry={"result_ref": ref},
            )
        rows = payload.get("rows", payload.get("cases", []))
        if isinstance(rows, list):
            payload = dict(
                payload,
                preview=rows[offset : offset + limit],
                returned_count=len(rows[offset : offset + limit]),
                truncated=len(rows) > limit,
            )
        metadata = {
            key: payload.get(key)
            for key in (
                "query_id",
                "operation",
                "purpose",
                "status",
                "total_matched",
                "returned_count",
                "definition_refs",
            )
        }
        context.history_results.append(
            dict(metadata, result_ref=ref, execution_status="success")
        )
        return _result(payload, result_ref=ref, tool="read_history_result")

    specs.append(
        ToolSpec(
            name="read_history_result",
            capability="finance_query",
            description="通过本会话研究原件引用读取完整结果的指定页；可以继续读取上一轮结果。",
            contract=_TOOL_CONTRACTS["read_history_result"],
            cost="local",
            freshness="historical",
            runner=read,
            parse_arguments=parse_read,
            parameters={
                "type": "object",
                "properties": {
                    "result_ref": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                },
                "required": ["result_ref"],
                "additionalProperties": False,
            },
        )
    )
    from intelligence.services.historical_research.research import (
        ResearchCase,
        prepare_research_draft,
        research_draft_schema,
    )

    draft_schema = research_draft_schema()
    draft_schema["properties"].pop("case_id")
    draft_schema["required"].remove("case_id")

    def parse_save(arguments):
        if set(arguments) - {"draft", "previous_result_ref"} or not isinstance(
            arguments.get("draft"), dict
        ):
            raise ValueError("save_history_research requires a typed draft")
        if len(_compact(arguments)) > 32000:
            raise ValueError("research draft exceeds 32000 character limit")
        if "case_id" in arguments["draft"]:
            raise ValueError("case identity is assigned by the server")
        previous_ref = arguments.get("previous_result_ref")
        if previous_ref is not None and not isinstance(previous_ref, str):
            raise ValueError("invalid previous case reference")
        return (arguments["draft"], previous_ref), _compact(arguments)

    def save_case(value, tool_context):
        tool_context.remaining()
        draft, previous_ref = value
        previous = None
        if previous_ref:
            if "/history-case-" not in previous_ref:
                raise ValueError("previous_result_ref must name a research case")
            original = session.read(previous_ref)
            assert_read_scope(original)
            session.remember(previous_ref, original)
            previous = ResearchCase.from_dict(original["draft"])
        identity = (
            previous.case_id
            if previous
            else "case-"
            + hashlib.sha256(
                f"{session.store.user_id}:{session.conversation_id}:{frame.raw_question}".encode()
            ).hexdigest()[:24]
        )
        allowed = set(session.refs)
        allowed.update(session.query_aliases)
        allowed.update(
            str(item["query_id"])
            for item in context.history_results
            if item.get("query_id")
        )
        exposed = set(draft.get("exposed_sample_refs", ()))
        exposed.update(
            str(item["result_ref"])
            for item in context.history_results
            if item.get("result_ref")
        )
        payload = dict(draft, case_id=identity, exposed_sample_refs=sorted(exposed))
        definitions = set(session.definition_refs)
        for item in context.history_results:
            definitions.update(item.get("definition_refs") or ())
        prepared = prepare_research_draft(
            payload,
            available_result_refs=allowed,
            previous=previous,
            available_definition_refs=definitions,
        )
        assert_dependency_scope(prepared.to_dict(), session.query_aliases)
        existing = []
        for known_ref in tuple(session.refs):
            if "/history-case-" not in known_ref:
                continue
            known = session.read(known_ref).get("draft", {})
            if known.get("case_id") == identity:
                existing.append((known_ref, known))
        if existing:
            head_ref, head = max(existing, key=lambda item: item[1]["revision"])
            if _compact(prepared.to_dict()) == _compact(head):
                return ToolRunResult(evidence=(), observation="同一研究草稿已保存：" + _compact({"case_id": identity, "result_ref": head_ref}),
                    trace=ProviderTrace(provider="history_artifact", capability="finance_query", status="success"),
                    dataset="historical_research_draft", telemetry={"result_ref": head_ref, "case_id": identity})
            if previous is None:
                raise ValueError("existing_case_requires_previous_result_ref: 修改已存案例必须保留原版本并声明parent")
            if previous_ref != head_ref:
                raise ValueError("stale_case_revision: 请先读取当前最新版本再修订")
        artifact = {
            "draft": prepared.to_dict(),
            "previous_result_ref": previous_ref,
            "query_aliases": dict(session.query_aliases),
            "definition_refs": sorted(definitions),
            "knowledge_cutoff": context.information_cutoff.as_of_date.isoformat(),
            "prior_exposure_completeness": "unknown",
            "research_only": True,
            "decision_eligible": False,
            "promotion_eligible": False,
        }
        ref = session.save("case", artifact)
        context.history_artifact_index[:] = session.index()
        return ToolRunResult(
            evidence=(),
            observation="已保存候选研究草稿；尚未认证。"
            + _compact(
                {
                    "case_id": identity,
                    "revision": prepared.revision,
                    "result_ref": ref,
                    "hypothesis_ids": [
                        item.hypothesis_id for item in prepared.hypotheses
                    ],
                    "exposed_sample_refs": sorted(exposed),
                }
            ),
            trace=ProviderTrace(
                provider="history_artifact",
                capability="finance_query",
                status="success",
            ),
            dataset="historical_research_draft",
            telemetry={"result_ref": ref, "case_id": identity},
        )

    def save(value, tool_context):
        _, previous_ref = value
        if previous_ref:
            identity = session.read(previous_ref)["draft"]["case_id"]
        else:
            identity = "case-" + hashlib.sha256(
                f"{session.store.user_id}:{session.conversation_id}:{frame.raw_question}".encode()
            ).hexdigest()[:24]
        with session.store.history_case_transaction(session.conversation_id, identity):
            session.refresh()
            return save_case(value, tool_context)

    specs.append(
        ToolSpec(
            name="save_history_research",
            capability="finance_query",
            description="保存当前研究案例、候选解释、反证与未决问题；case_id由服务端分配。修改既有研究需previous_result_ref并保留旧失败与暴露记录。",
            contract=_TOOL_CONTRACTS["save_history_research"],
            cost="local",
            freshness="historical",
            runner=save,
            parse_arguments=parse_save,
            parameters={
                "type": "object",
                "properties": {
                    "draft": draft_schema,
                    "previous_result_ref": {"type": "string"},
                },
                "required": ["draft"],
                "additionalProperties": False,
            },
        )
    )
    return specs
