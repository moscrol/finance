"""Compose history calculations with the existing Episode and artifact writer."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from intelligence.services.agent_research import (
    AgentEvidence,
    HistoricalEvidenceProvenance,
    StructuredObservation,
)
from intelligence.services.provider_observability import ProviderTrace
from intelligence.services.research_tool_registry import ToolDiagnostic, ToolRunResult, ToolSpec

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
        refreshed: dict[str, tuple[str, str]] = {}
        for item in related:
            for artifact in item.artifacts:
                filename = str(artifact.get("path", ""))
                if (
                    filename.startswith("history-")
                    and artifact.get("visibility") == "public"
                    and artifact.get("downloadable", True) is True
                ):
                    refreshed[f"{item.run_id}/{filename}"] = (item.run_id, filename)
        self.refs = refreshed

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
        # The display cache never grants authority, even for a previously read ref.
        if not isinstance(ref, str) or len(ref) > 300 or ref.count("/") != 1:
            raise ValueError("history result reference is outside this conversation")
        run_id, filename = ref.split("/", 1)
        payload = self.store.read_history_artifact(
            run_id, filename, conversation_id=self.conversation_id,
        )
        self.refs[ref] = (run_id, filename)
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
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))

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


def _model_projection(
    payload: dict, result_ref: str
) -> list[tuple[str, str, str | None, int | None, str, str, tuple[StructuredObservation, ...]]]:
    """Project data and definitions, keeping row count distinct from card count.

    The extra identity fields are control-plane metadata. They let every model
    card point back to one immutable query row without making page coordinates
    or free-form detail text carry provenance.
    """
    projected = []
    query_id = str(payload.get("query_id") or "")

    def add(
        title,
        identity,
        atoms,
        source_date=None,
        *,
        row_index: int | None = None,
        row_identity: str = "",
        row_hash: str = "",
        observations: tuple[StructuredObservation, ...] = (),
    ):
        # Row identity must be stable across pages, but is not a card identity:
        # a row may span several public citations with different fields.
        for block_index, detail in enumerate(_model_blocks(identity, atoms)):
            visible = json.loads(detail)
            visible_values = {**visible, **visible.get("features", {})}
            block_observations = tuple(
                observation for observation in observations
                if type(visible_values.get(observation.metric)) in (int, float)
                and visible_values[observation.metric] == observation.value
            )
            projected.append(
                (f"{title}·块{block_index + 1}" if row_identity else title,
                 detail, source_date, row_index, row_identity, row_hash, block_observations)
            )

    scope_observations = tuple(
        StructuredObservation(
            subject=query_id,
            as_of=str(payload.get("end") or payload.get("spec", {}).get("end") or ""),
            metric=key,
            value=float(payload[key]),
        )
        for key in ("total_matched", "returned_count")
        if isinstance(payload.get(key), (int, float)) and not isinstance(payload.get(key), bool)
    )
    add("历史研究范围与完整分母", {}, [
        {key: payload.get(key)}
        for key in ("operation", "status", "total_matched", "returned_count", "truncated", "offset", "next_offset")
    ] + [{"research_only": True, "decision_eligible": False, "promotion_eligible": False}], observations=scope_observations)
    add("历史研究原件引用", {}, [{"result_ref": result_ref}])
    add("历史研究使用边界", {}, [{
        "pit_grade": payload.get("pit_grade", "hindsight_reconstruction"),
        "null": "未知或不可计算，非0；具体原因见每项status；not_observed表示该窗口未观察到触发。",
    }])

    spec = payload.get("spec", {})
    add("历史计算声明观察窗", {}, [{"observation_window": {
        key: spec.get(key) for key in ("operation", "start", "end")
    }}])
    if isinstance(payload.get("window_binding"), dict):
        binding = payload["window_binding"]
        add("历史参照窗绑定", {}, [{key: binding[key] for key in (
            "relation", "source_start", "source_end", "start", "end",
        )}])
        add("历史排名区间", {}, [{key: binding[key] for key in ("ranking_start", "ranking_end")}])
        add("历史参照窗原件", {}, [
            {key: value} for key, value in binding.get("source_reference", {}).items()
        ] + [{key: binding.get(key)} for key in ("version", "source_query_id", "root_query_id", "root_sample_id")])
    comparison = payload.get("comparison")
    if isinstance(comparison, dict):
        add("历史条件比较定义", {}, [
            {"condition": spec.get("condition")},
            {"outcome_definition": payload.get("outcome_definition")},
        ])
        add("历史条件比较完整统计", {}, [{key: value} for key, value in sorted(comparison.items())])
    universe = payload.get("universe")
    if isinstance(universe, dict):
        add("历史比较宇宙与窗口", {}, [
            {key: value} for key, value in sorted(universe.items()) if key != "entity_codes"
        ] + [{"entity_count": len(universe.get("entity_codes", []))}])
    for key in ("analysis_definition",):
        if isinstance(payload.get(key), dict):
            add("行情过程的规则与边界", {}, [{name: value} for name, value in payload[key].items()])
    if payload.get("independence_policy"):
        add("样本独立性限制", {}, [{"independence_policy": payload["independence_policy"]}])
    if payload.get("matching_use"):
        add("历史相似召回用途", {}, [{"matching_use": payload["matching_use"]}])
    for name, definition in sorted(payload.get("feature_definitions", {}).items()):
        add("历史特征严格定义", {"feature": name}, [
            {key: definition[key]} for key in ("rule", "unit", "version", "input_mapping") if key in definition
        ])

    names: dict[str, set[str]] = {}
    for rows in payload.get("inputs", {}).values():
        for row in rows:
            for prefix in ("sector", "stock"):
                code, name = row.get(f"{prefix}_ts_code"), row.get(f"{prefix}_name")
                if code and name:
                    names.setdefault(code, set()).add(name)
    preview = payload.get("preview", [])
    # A sample is a row in the immutable result, not a position within this page.
    records = list(enumerate(
        preview[:25] if isinstance(preview, list) else [], start=payload.get("offset", 0)
    ))
    reference = payload.get("reference")
    if isinstance(reference, dict):
        records.insert(0, ("reference", reference))
    for index, row in records:
        if not isinstance(row, dict):
            continue
        row_index = index if isinstance(index, int) else None
        row_identity = f"{query_id}:row:{index}"
        row_hash = hashlib.sha256(_compact(row).encode("utf-8")).hexdigest()[:16]
        if row.get("record_kind") == "sector_succession":
            from .succession_projection import succession_atoms

            # Pair identity on EVERY card; status/reason/counts are one atom.
            # Do not pack status beside null confirmation/lag as unrelated keys.
            identity = {"sample": index, "record_kind": "sector_succession",
                        "source_sector": row.get("source_sector"), "entity_code": row.get("entity_code")}
            for atom in succession_atoms(row, payload):
                add(f"历史接力配对 {row.get('source_sector')}→{row.get('entity_code')}",
                    identity, [atom], row.get("succession_known_as_of"),
                    row_index=row_index, row_identity=row_identity, row_hash=row_hash)
            continue
        identity = {"sample": index, "entity_code": row.get("entity_code")}
        if isinstance(reference, dict):
            identity["role"] = "reference" if index == "reference" else "candidate"
        for key in ("trade_date", "start", "end", "record_kind"):
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
        # Stored artifacts use sorted keys. Order semantic atoms before packing,
        # not just the final JSON: block boundaries must also survive a reread.
        for name, value in sorted(row.get("features", {}).items()):
            atoms.append({
                "features": {name: value},
                "status": {name: row.get("feature_coverage", {}).get(name, {}).get("status", "unknown")},
            })
        atoms.extend(
            {"feature_differences": {name: value}}
            for name, value in sorted(row.get("feature_differences", {}).items())
        )
        for kind in ("sector", "stock"):
            values = row.get(kind)
            if isinstance(values, dict):
                atoms.extend({kind: {key: values[key]}} for key in (
                    "pct_chg", "amount", "diff_ratio", "price", "close", "turnover_rate"
                ) if key in values)
        for key in ("sample_id", "distance", "feature_cutoff", "first_date", "last_date", "observed_dates", "dates"):
            if key in row:
                atoms.append({key: row[key]})
        for key in (
            "overlap_cluster", "signal_date", "signal_known_as_of", "signal_status", "path_status",
            "peak_date", "peak_status", "peak_known_as_of", "peak_gain_pct", "days_to_peak",
            "confirmation_date", "confirmation_known_as_of", "end_drawdown_from_peak_pct", "path_anchor", "path_end",
            "parent_sector", "membership_date", "membership_snapshot_id", "membership_status", "sector_snapshot_id",
            "rank", "selection_mode", "population_count", "source_sector", "anchor_peak_date",
            "source_peak_status", "source_peak_confirmation_date", "target_signal_date", "lag_trading_days",
            "succession_status", "succession_known_as_of", "causal_status", "stage_semantics", "market_units",
        ):
            if key in row:
                atoms.append({key: row[key]})
        atoms.extend({"succession_evidence": {key: value}} for key, value in row.get("evidence", {}).items())
        path = row.get("path", [])
        if path:
            # Keep a bounded shape sketch plus exact anchor dates. Full daily path
            # remains in artifact; inspect_history exposes any omitted date.
            indexes = {round(i * (len(path) - 1) / 7) for i in range(8)}
            indexes.update(i for i, point in enumerate(path) if point["trade_date"] in
                           (row.get("peak_date"), row.get("confirmation_date")))
            atoms.append({"path_points_total": len(path), "path_points_shown": len(indexes),
                          "path_projection": "sampled_NAV_only; inspect_history for omitted daily price/amount"})
            atoms.extend({"path_sample": {str(path[i]["trade_date"]): path[i]["nav"]}}
                         for i in sorted(indexes))
        # Large members/events/coverage remain in the original. These counts
        # distinguish an empty collection from a hidden detailed collection.
        atoms.extend({f"{key}_count": len(row[key])} for key in (
            "members", "sector_memberships", "events", "heat"
        ) if isinstance(row.get(key), list))
        if "market" in row:
            atoms.append({"market_status": "missing_or_ambiguous" if row["market"] is None else "observed"})
            if isinstance(row["market"], dict):
                atoms.extend({"market": {key: row["market"][key]}} for key in (
                    "sh_index_pct_chg", "sh_index_close", "sh_deviation_pct", "total_amount",
                    "advancers", "limit_up", "limit_down", "market_stage", "market_stage_source", "market_stage_confidence", "cycle_stage", "stage_day", "sh_week_ma", "sh_week_ma_source", "amount_ma20", "volume_ratio",
                    "cycle_stage_source", "cycle_stage_updated_at", "volume_state", "concentration_state", "source",
                ) if key in row["market"])
        date_value = str(row.get("succession_known_as_of", row.get("trade_date", row.get("path_end", row.get("end", ""))))) or None
        sample_scope = " ".join(str(value) for key, value in identity.items() if key != "sample")
        row_observations: list[StructuredObservation] = []
        as_of = date_value or ""
        subject = str(row.get("entity_code") or row.get("entity_name") or query_id)
        for metric, value in sorted(row.get("features", {}).items()):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                row_observations.append(
                    StructuredObservation(subject, as_of, str(metric), float(value))
                )
        for metric, value in sorted(row.items()):
            if metric in {"features", "feature_coverage", "entity_code", "entity_name", "start", "end"}:
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                row_observations.append(
                    StructuredObservation(subject, as_of, str(metric), float(value))
                )
        add(
            f"历史观察样本 {sample_scope}",
            identity,
            atoms,
            date_value,
            row_index=row_index,
            row_identity=row_identity,
            row_hash=row_hash,
            observations=tuple(row_observations),
        )
    return projected


def _result(
    payload: dict, *, result_ref: str = "", tool: str = "history_query", offset: int = 0
):
    returned_count = payload.get("returned_count", 0)
    page_end = offset + returned_count
    payload = dict(
        payload,
        offset=offset,
        next_offset=(
            page_end if returned_count and page_end < payload.get("total_matched", 0) else None
        ),
    )
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
            "offset",
            "next_offset",
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
            "analysis_definition",
            "window_binding",
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
            title=f"{title}｜{query_id[:8]}·{(row_index + 1) if row_index is not None else card_index + 1}｜{scope}".rstrip("｜"),
            detail=detail,
            source="本地历史研究 · 可复算原件",
            internal_locator=result_ref,
            source_date=source_date,
            evidence_tier="L4_market_signal",
            freshness="historical",
            independent_key=query_id,
            observations=observations,
            history_provenance=HistoricalEvidenceProvenance(
                query_id=query_id,
                operation=str(payload.get("operation") or ""),
                purpose=str(payload.get("purpose") or ""),
                result_ref=result_ref,
                row_index=row_index,
                row_identity=row_identity,
                row_hash=row_hash,
                research_only=True,
                decision_eligible=False,
                promotion_eligible=False,
            ),
        )
        for card_index, (title, detail, source_date, row_index, row_identity, row_hash, observations) in enumerate(projection)
    ]
    return ToolRunResult(
        evidence=tuple(evidence),
        observation="探索结果，未认证规律；完整分母独立于投影条数。"
        + _compact({"result_ref": result_ref, "query_id": query_id,
                    "total_matched": payload.get("total_matched"), "returned_count": payload.get("returned_count"),
                    "truncated": payload.get("truncated"),
                    "offset": offset, "next_offset": payload["next_offset"],
                    "projected_evidence_count": len(projection)})
        + "样本以完整JSON语义块展示，同result_ref内sample是原件行号（从0起），跨页不重置；特征定义卡给出真实rule/unit/version。"
        "大成员、覆盖明细和超长字段仅在完整artifact；需更多行用read_history_result按next_offset分页，null表示已到末页。"
        "需未展示行请按next_offset分页；补查字段可明确实体/特征但保持所选窗口，仍不足就说明缺口或由用户查看原件，不把null当0。",
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


def record_history_delivery(observation, model_content: str, *, context) -> None:
    """Acknowledge a successful result only after its model message was appended.

    Worker completion and artifact reads are not delivery. In particular, a
    concurrent sibling cannot use an unread candidate from the same tool batch.
    No new store: this annotates the Episode's existing execution metadata.
    """
    if observation.tool not in {"history_query", "read_history_result"}:
        return
    metadata = observation.telemetry or {}
    ref, query_id = metadata.get("result_ref"), metadata.get("query_id")
    if not ref or not query_id or observation.trace.status != "success":
        return
    try:
        payload = json.loads(model_content)
        if payload.get("ok") is not True:
            return
        blocks = [json.loads(item["detail"]) for item in payload.get("evidence", ())]
    except (ValueError, TypeError, KeyError, AttributeError):
        return  # Unknown/custom projections cannot attest delivery.
    if not any(isinstance(b, dict) and b.get("result_ref") == ref for b in blocks):
        return
    source_spec = metadata.get("spec", {})
    if not any(isinstance(b, dict) and b.get("observation_window") == {
        key: source_spec.get(key) for key in ("operation", "start", "end")
    } for b in blocks):
        return
    samples = sorted({b["sample_id"] for b in blocks
                      if isinstance(b, dict) and isinstance(b.get("sample_id"), str)})
    binding = metadata.get("window_binding")
    binding_delivered = isinstance(binding, dict) and any(
        isinstance(b, dict) and all(b.get(key) == binding[key] for key in (
            "relation", "source_start", "source_end", "start", "end",
        )) for b in blocks
    )
    for item in context.history_results:
        if (item.get("result_ref") == ref and item.get("query_id") == query_id
                and item.get("execution_status") == "success"):
            item["delivery_status"] = "model_message"
            visible = set(item.get("visible_sample_ids", ()))
            item["visible_sample_ids"] = sorted(visible.union(samples))
            item["binding_delivered"] = bool(item.get("binding_delivered") or binding_delivered)


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
        HistoryQueryEntityError,
        HistoryQuerySpec,
        history_query_parameters,
    )
    from intelligence.services.research_tool_registry import _TOOL_CONTRACTS
    from intelligence.services.historical_research.intent import assert_history_window
    from intelligence.services.historical_research.window_binding import (
        ANALYSIS_OPERATIONS, WindowSelection, resolve_window_binding, validate_saved_window_binding,
    )

    selection = WindowSelection()

    def assert_dependency_scope(draft, aliases, *, visited=None, check=None):
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
            if check is not None:
                check()
            assert_read_scope(session.read(ref), visited=visited, check=check)

    def assert_read_scope(payload, *, visited=None, window_chain=(), check=None):
        if check is not None:
            check()
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
        dependency = spec.get("window_ref")
        if payload.get("window_binding") is not None and not isinstance(dependency, dict):
            raise ValueError("history_window_binding_invalid: saved binding has no source reference")
        if isinstance(dependency, dict):
            ref = dependency.get("result_ref")
            if ref in window_chain or len(window_chain) >= 64:
                raise ValueError("history_window_dependency_cycle_or_depth_limit")
            source = session.read(ref)
            assert_read_scope(source, visited=visited, window_chain=(*window_chain, ref), check=check)
            validate_saved_window_binding(payload, source)
        if "draft" in payload:
            aliases = dict(session.query_aliases)
            aliases.update(payload.get("query_aliases", {}))
            assert_dependency_scope(payload["draft"], aliases, visited=visited, check=check)
        if check is not None:
            check()

    def parse(arguments):
        spec = HistoryQuerySpec.from_arguments(arguments)
        if spec.preview_limit > 25:
            raise ValueError("history preview limit must be 1..25")
        return spec, _compact(asdict(spec))

    def execute_query(spec, tool_context, binding):
        tool_context.remaining()
        assert_history_window(frame.history_intent, spec.start, spec.end)
        if spec.search_start is not None:
            assert_history_window(frame.history_intent, spec.search_start, spec.search_end)
        try:
            payload = HistoryQuery(db_path).run(
                spec,
                information_cutoff=context.information_cutoff,
                deadline=tool_context.deadline,
                is_cancelled=tool_context.is_cancelled,
                **({"window_binding": binding} if binding is not None else {}),
            )
        except HistoryQueryEntityError as exc:
            entity_check = exc.entity_check
            return ToolRunResult(
                evidence=(), observation="",
                diagnostics=(ToolDiagnostic(code=entity_check.failure_code, message=entity_check.message),),
                trace=ProviderTrace(
                    provider="duckdb_history_query", capability="finance_query",
                    status="request_error", detail=entity_check.failure_code, result_count=0,
                ),
                gaps=entity_check.gaps, dataset="historical_research",
                caliber="retrospective_research_only",
                telemetry={"entity_check": entity_check.to_dict()},
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
        result = _result(payload, result_ref=ref)
        if binding is not None:
            metadata["window_binding"] = binding
        context.history_results.append(metadata)
        return result

    def run(spec, tool_context):
        tool_context.remaining()
        binding = None
        if (spec.operation in ANALYSIS_OPERATIONS
                and frame.history_intent.analysis_window_source != "none"
                and spec.window_ref is None):
            raise ValueError("history_window_reference_required: first read_history_result, then use window_ref; do not replace the requested historical reference with recent dates")
        if spec.window_ref is not None:
            if session is None:
                raise ValueError("history_window_session_required")
            source_ref = spec.window_ref["result_ref"]
            source = session.read(source_ref)
            assert_read_scope(source, check=tool_context.remaining)
            delivered = [item for item in context.history_results
                         if item.get("result_ref") == source_ref
                         and item.get("query_id") == source.get("query_id")
                         and item.get("execution_status") == "success"
                         and item.get("delivery_status") == "model_message"]
            binding = resolve_window_binding(spec, frame.history_intent, source, delivered)
        with selection.reserve(
            binding if frame.history_intent.analysis_window_source != "none" else None,
            observation=spec.operation == "trace_history",
        ):
            return execute_query(spec, tool_context, binding)

    query_parameters = history_query_parameters()
    query_parameters["properties"]["preview_limit"]["maximum"] = 25
    from intelligence.services.historical_research.features import FEATURES, FEATURE_VERSION

    query_parameters["properties"]["features"]["description"] = (
        f"版本{FEATURE_VERSION}；不得凭名称改定义。null为未知或不可计算，见status，非0。"
        + "；".join(
            f"{name}@{definition.get('version', FEATURE_VERSION)}[{definition['unit']}]={definition['rule']}"
            for name, definition in FEATURES.items()
        )
    )
    specs = [
        ToolSpec(
            name="history_query",
            capability="finance_query",
            description="重建历史行情、市场环境类比、启动到顶部日线路径与板块候选接力。市场阶段先inspect_history(entity_kind=market,000001.SH)，类比用find_analogues显式历史范围，当时谁强用rank_history声明窗排名（未指定代码=窗口内已观测全集；超限报缺口，不偷偷缩窗），行情解剖用trace_history；先inspect核对板块/股票精确代码，同名不同供应商不混接。共同启动特征比较launch_signal行；但只看已启动的是幸存者偏差，验证请用compare_cases配 condition={'rule':'launch_signal'}，它按同版本规则逐窗判定当时是否启动，未启动窗口即控制组，缺数与未成熟分开计数仍留在分母。trace仅日线描述代理，不冒充SPT/风远完整方法或当时可知顶部。续问按可信用途先read_history_result，再用window_ref绑定类比候选sample_id或已有分析观察窗，不按旧助手答案猜日期。不确定窗口先提出并注明，缺数不补零。",
            contract=_TOOL_CONTRACTS["history_query"],
            cost="local",
            freshness="historical",
            runner=run,
            # Read-only DuckDB; saving this run's observation is not a data read.
            # No vendor fetch, model, subprocess or knowledge-store fallback.
            io_effect="local_read",
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
        assert_read_scope(payload, check=tool_context.remaining)
        session.remember(ref, payload)
        if "/history-case-" in ref:
            # 经 scope 校验读到的 case 是本轮合法的研究产物引用：落一条独立的
            # read_history_case 元数据，finish 校验据此放行 result_refs 里的 case；
            # 它不是四种计算算子，不会被算成历史计算或比较。
            draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
            context.history_results.append(
                {
                    "operation": "read_history_case",
                    "execution_status": "success",
                    "status": "research_only",
                    "case_id": draft.get("case_id"),
                    "revision": draft.get("revision"),
                    "result_ref": ref,
                }
            )
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
            page = rows[offset : offset + limit]
            payload = dict(
                payload,
                preview=page,
                returned_count=len(page),
                truncated=len(page) < len(rows),
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
        result = _result(payload, result_ref=ref, tool="read_history_result", offset=offset)
        context.history_results.append(
            dict(metadata, result_ref=ref, execution_status="success",
                 **({"window_binding": payload["window_binding"]} if "window_binding" in payload else {}))
        )
        return result

    specs.append(
        ToolSpec(
            name="read_history_result",
            capability="finance_query",
            description="读取同会话上一轮query/case原件的指定页；case返回未认证草稿摘要和hypotheses分页，按next_offset续读。旧完整引用由patch服务端保留。",
            contract=_TOOL_CONTRACTS["read_history_result"],
            cost="local",
            freshness="historical",
            runner=read,
            # Same-user/conversation RunStore originals, scope checked above.
            io_effect="local_read",
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
            assert_read_scope(original, check=tool_context.remaining)
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
                "inspect_history", "compute_history", "find_analogues", "compare_cases", "trace_history", "rank_history"
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
        assert_dependency_scope(prepared.to_dict(), session.query_aliases, check=tool_context.remaining)
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
