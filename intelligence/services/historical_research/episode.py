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


def _draft_page(payload: dict, result_ref: str, offset: int, limit: int) -> str:
    """Whole JSON under the real prose budget, never a market evidence card."""
    from intelligence.services.tool_result_budget import MAX_OBSERVATION_CHARS

    draft = payload["draft"]
    hypotheses = draft.get("hypotheses", [])
    question = draft["question"]
    page = {
        "kind": "research_draft", "research_only": True,
        "case_id": draft["case_id"], "revision": draft["revision"],
        "result_ref": result_ref,
        "question": question[:96], "question_truncated": len(question) > 96,
        "total_hypotheses": len(hypotheses), "offset": offset,
        "returned_count": 0, "next_offset": None, "hypotheses": [],
        "source_refs_count": len(draft.get("source_refs", [])),
        "exposed_sample_refs_count": len(draft.get("exposed_sample_refs", [])),
        "raw_artifact_preserved": True,
    }
    for index in range(offset, min(len(hypotheses), offset + limit)):
        hypothesis = hypotheses[index]
        statement = hypothesis["statement"]
        item = {
            "hypothesis_id": hypothesis["hypothesis_id"],
            "statement": statement[:120], "statement_truncated": len(statement) > 120,
            "status": hypothesis["status"], "version": hypothesis["version"],
        }

        def candidate(value):
            return dict(page, hypotheses=[*page["hypotheses"], value],
                returned_count=len(page["hypotheses"]) + 1,
                next_offset=index + 1 if index + 1 < len(hypotheses) else None)

        updated = candidate(item)
        if len(_compact(updated)) > MAX_OBSERVATION_CHARS:
            if page["hypotheses"]:
                break
            # Old immutable artifacts can contain arbitrarily long text/IDs.
            # Shorten only labelled statement prose, never a patch identifier.
            while item["statement"] and len(_compact(updated)) > MAX_OBSERVATION_CHARS:
                item["statement"] = item["statement"][:-1]
                item["statement_truncated"] = True
                updated = candidate(item)
            if len(_compact(updated)) > MAX_OBSERVATION_CHARS:
                updated = candidate({"hypothesis_index": index,
                    "projection_status": "oversized_hypothesis_id_requires_raw_artifact"})
        page = updated
    rendered = _compact(page)
    if len(rendered) > MAX_OBSERVATION_CHARS:
        raise ValueError("research case metadata exceeds model summary budget")
    return rendered


def _model_blocks(identity: dict, atoms: list[dict]) -> list[str]:
    """Pack whole semantic fields into the real model-facing detail budget.

    The artifact keeps every field. A single oversized value is explicitly
    omitted here instead of producing a clipped JSON string or numeric prefix.
    """
    from intelligence.services.tool_result_budget import MAX_EVIDENCE_DETAIL_CHARS

    def encode(value):
        return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))

    def merge(left, right):
        result = dict(left)
        for key, value in right.items():
            result[key] = (
                {**result[key], **value}
                if isinstance(result.get(key), dict) and isinstance(value, dict)
                else value
            )
        return result

    blocks, current = [], dict(identity)
    for atom in atoms:
        candidate = merge(current, atom)
        if len(encode(candidate)) <= MAX_EVIDENCE_DETAIL_CHARS:
            current = candidate
            continue
        if current != identity:
            blocks.append(encode(current))
        current = merge(identity, atom)
        if len(encode(current)) > MAX_EVIDENCE_DETAIL_CHARS:
            current = {
                "sample": identity.get("sample"),
                "projection_status": "oversized_field_omitted",
                "fields": list(atom),
            }
            blocks.append(encode(current))
            current = dict(identity)
    if current != identity or (not atoms and len(encode(identity)) <= MAX_EVIDENCE_DETAIL_CHARS):
        blocks.append(encode(current))
    return blocks


def _model_projection(payload: dict, result_ref: str) -> list[tuple[str, str, str | None]]:
    """Project data and definitions, keeping row count distinct from card count."""
    projected = []

    def add(title, identity, atoms, source_date=None):
        projected.extend(
            (title, detail, source_date) for detail in _model_blocks(identity, atoms)
        )

    add("历史研究范围与完整分母", {}, [
        {key: payload.get(key)}
        for key in ("operation", "status", "total_matched", "returned_count", "truncated")
    ] + [{"research_only": True, "decision_eligible": False, "promotion_eligible": False}])
    add("历史研究原件引用", {}, [{"result_ref": result_ref}])
    add("历史研究使用边界", {}, [{
        "pit_grade": payload.get("pit_grade", "hindsight_reconstruction"),
        "null": "未知或不可计算，非0；具体原因见每项status；not_observed表示该窗口未观察到触发。",
    }])
    spec = payload.get("spec", {})
    comparison = payload.get("comparison")
    if isinstance(comparison, dict):
        add("历史条件比较定义", {}, [
            {"condition": spec.get("condition")},
            {"outcome_definition": payload.get("outcome_definition")},
        ])
        add("历史条件比较完整统计", {}, [{key: value} for key, value in comparison.items()])
    universe = payload.get("universe")
    if isinstance(universe, dict):
        add("历史比较宇宙与窗口", {}, [
            {key: value} for key, value in universe.items() if key != "entity_codes"
        ] + [{"entity_count": len(universe.get("entity_codes", []))}])
    if payload.get("matching_use"):
        add("历史相似召回用途", {}, [{"matching_use": payload["matching_use"]}])
    for name, definition in payload.get("feature_definitions", {}).items():
        add("历史特征严格定义", {"feature": name}, [
            {key: definition[key]} for key in ("rule", "unit", "version") if key in definition
        ])

    names: dict[str, set[str]] = {}
    for rows in payload.get("inputs", {}).values():
        for row in rows:
            for prefix in ("sector", "stock"):
                code, name = row.get(f"{prefix}_ts_code"), row.get(f"{prefix}_name")
                if code and name:
                    names.setdefault(code, set()).add(name)
    preview = payload.get("preview", [])
    records = list(enumerate(preview[:25] if isinstance(preview, list) else []))
    reference = payload.get("reference")
    if isinstance(reference, dict):
        records.insert(0, ("reference", reference))
    for index, row in records:
        if not isinstance(row, dict):
            continue
        identity = {"sample": index, "entity_code": row.get("entity_code")}
        if isinstance(reference, dict):
            identity["role"] = "reference" if index == "reference" else "candidate"
        for key in ("trade_date", "start", "end"):
            if key in row:
                identity[key] = row[key]
        atoms = []
        known = names.get(row.get("entity_code"), set())
        name = row.get("entity_name") or (next(iter(known)) if len(known) == 1 else None)
        if name:
            atoms.append({"entity_name": name})
        if "comparison_state" in row:
            atoms.extend({key: row[key]} for key in (
                "comparison_state", "x", "y", "forward_return_pct", "outcome_end"
            ) if key in row)
        for name, value in row.get("features", {}).items():
            atoms.append({
                "features": {name: value},
                "status": {name: row.get("feature_coverage", {}).get(name, {}).get("status", "unknown")},
            })
        atoms.extend(
            {"feature_differences": {name: value}}
            for name, value in row.get("feature_differences", {}).items()
        )
        for kind in ("sector", "stock"):
            values = row.get(kind)
            if isinstance(values, dict):
                atoms.extend({kind: {key: values[key]}} for key in (
                    "pct_chg", "amount", "diff_ratio", "price", "close", "turnover_rate"
                ) if key in values)
        for key in ("distance", "feature_cutoff", "first_date", "last_date", "observed_dates", "dates"):
            if key in row:
                atoms.append({key: row[key]})
        # Large members/events/coverage remain in the original. These counts
        # distinguish an empty collection from a hidden detailed collection.
        atoms.extend({f"{key}_count": len(row[key])} for key in (
            "members", "sector_memberships", "events", "heat"
        ) if isinstance(row.get(key), list))
        if "market" in row:
            atoms.append({"market_status": "missing_or_ambiguous" if row["market"] is None else "observed"})
        date_value = str(row.get("trade_date", row.get("end", ""))) or None
        sample_scope = " ".join(str(value) for key, value in identity.items() if key != "sample")
        add(f"历史观察样本 {sample_scope}", identity, atoms, date_value)
    return projected


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
            "spec",
            "feature_definitions",
        )
        if key in payload
    }
    metadata.update(
        result_ref=result_ref,
        research_only=True,
        decision_eligible=False,
        promotion_eligible=False,
    )
    query_id = str(payload.get("query_id", ""))
    projection = _model_projection(payload, result_ref)
    metadata["projected_evidence_count"] = len(projection)
    spec = payload.get("spec", {})
    scope = " ".join(str(value) for value in (
        ",".join(spec.get("entity_codes", [])[:2]), spec.get("start"), spec.get("end")
    ) if value)
    evidence = [
        AgentEvidence(
            tool=tool,
            # Citation UI deduplicates by title/source/date. A block is a public
            # observation, not an independent sample; independent_key stays qid.
            title=f"{title}｜{query_id[:8]}·{index + 1}｜{scope}".rstrip("｜"),
            detail=detail,
            source="本地历史研究 · 可复算原件",
            internal_locator=result_ref,
            source_date=source_date,
            evidence_tier="L4_market_signal",
            freshness="historical",
            independent_key=query_id,
        )
        for index, (title, detail, source_date) in enumerate(projection)
    ]
    return ToolRunResult(
        evidence=tuple(evidence),
        observation="探索结果，未认证规律；完整分母独立于投影条数。"
        + _compact({"result_ref": result_ref, "query_id": query_id,
                    "total_matched": payload.get("total_matched"), "returned_count": payload.get("returned_count"),
                    "truncated": payload.get("truncated"),
                    "projected_evidence_count": len(projection)})
        + "样本以完整JSON语义块展示，同sample属于同一原件行；特征定义卡给出真实rule/unit/version。"
        "大成员、覆盖明细和超长字段仅在完整artifact；需更多日期用read_history_result分页。"
        "需未展示字段请缩窄日期/实体/特征查询，仍不足就明确缺口或由用户查看原件，不把null当0。",
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
    from intelligence.services.historical_research.features import FEATURES, FEATURE_VERSION

    query_parameters["properties"]["features"]["description"] = (
        f"版本{FEATURE_VERSION}；不得凭名称改定义。null为未知或不可计算，见status，非0。"
        + "；".join(
            f"{name}[{definition['unit']}]={definition['rule']}"
            for name, definition in FEATURES.items()
        )
    )
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
                observation=_draft_page(payload, ref, offset, limit),
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
            description="读取同会话上一轮query/case原件的指定页；case返回未认证草稿摘要和hypotheses分页，按next_offset续读。旧完整引用由patch服务端保留。",
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
        ResearchCasePatch,
        prepare_research_draft,
        prepare_research_patch,
        research_draft_schema,
        research_patch_schema,
    )

    draft_schema = research_draft_schema()
    draft_schema["properties"].pop("case_id")
    draft_schema["required"].remove("case_id")

    def parse_save(arguments):
        if set(arguments) - {"draft", "patch", "previous_result_ref"} or ("draft" in arguments) == ("patch" in arguments):
            raise ValueError("save_history_research requires exactly one of draft or patch")
        mode = "patch" if "patch" in arguments else "draft"
        if not isinstance(arguments[mode], dict):
            raise ValueError(f"save_history_research requires a typed {mode}")
        if len(_compact(arguments)) > 32000:
            raise ValueError("research draft exceeds 32000 character limit")
        if "case_id" in arguments[mode]:
            raise ValueError("case identity is assigned by the server")
        previous_ref = arguments.get("previous_result_ref")
        if previous_ref is not None and not isinstance(previous_ref, str):
            raise ValueError("invalid previous case reference")
        if mode == "patch":
            if not previous_ref:
                raise ValueError("patch requires previous_result_ref of the exact saved case")
            ResearchCasePatch.from_dict(arguments[mode])
        return (arguments[mode], previous_ref, mode), _compact(arguments)

    def saved_result(prepared, ref, *, unchanged=False):
        metadata = {
            "operation": "save_history_research", "execution_status": "success",
            "status": "research_only", "case_id": prepared.case_id,
            "revision": prepared.revision, "result_ref": ref,
        }
        context.history_results.append(metadata)
        context.history_artifact_index[:] = session.index()
        return ToolRunResult(
            evidence=(),
            observation=_compact(dict(metadata, kind="research_draft", research_only=True,
                unchanged=unchanged, hypotheses_count=len(prepared.hypotheses),
                exposed_sample_refs_count=len(prepared.exposed_sample_refs))),
            trace=ProviderTrace(provider="history_artifact", capability="finance_query", status="success"),
            dataset="historical_research_draft", telemetry=metadata,
        )

    def save_case(value, tool_context):
        tool_context.remaining()
        draft, previous_ref, mode = value
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
            if item.get("result_ref") and item.get("operation") in {
                "inspect_history", "compute_history", "find_analogues", "compare_cases"
            }
        )
        payload = dict(draft, exposed_sample_refs=sorted(exposed))
        definitions = set(session.definition_refs)
        for item in context.history_results:
            definitions.update(item.get("definition_refs") or ())
        if mode == "patch":
            prepared = prepare_research_patch(payload, previous=previous,
                available_result_refs=allowed, available_definition_refs=definitions)
        else:
            prepared = prepare_research_draft(
                dict(payload, case_id=identity), available_result_refs=allowed,
                previous=previous, available_definition_refs=definitions,
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
                return saved_result(prepared, head_ref, unchanged=True)
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
        return saved_result(prepared, ref)

    def save(value, tool_context):
        _, previous_ref, _ = value
        if previous_ref:
            message = "previous_result_ref must reference a saved history case; omit for initial draft"
            if "/history-case-" not in previous_ref:
                raise ValueError(message)
            previous_payload = session.read(previous_ref)
            try:
                identity = ResearchCase.from_dict(previous_payload["draft"]).case_id
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(message) from exc
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
            description="初次保存用draft；修订优先用previous_result_ref+patch，按已有hypothesis_id只传变化及新增引用，不用复制旧记录或手填版本。旧假设/来源/反证/失败/暴露均保留；列表只追加。完整draft模式仍支持严格版本修订。",
            contract=_TOOL_CONTRACTS["save_history_research"],
            cost="local",
            freshness="historical",
            runner=save,
            parse_arguments=parse_save,
            parameters={
                "type": "object",
                "properties": {
                    "draft": draft_schema,
                    "patch": research_patch_schema(),
                    "previous_result_ref": {"type": "string", "description": "修订或patch必须引用确切已存history-case原件，不能填query原件"},
                },
                "oneOf": [
                    {"required": ["draft"], "not": {"required": ["patch"]}},
                    {"required": ["patch", "previous_result_ref"], "not": {"required": ["draft"]}},
                ],
                "additionalProperties": False,
            },
        )
    )
    return specs
