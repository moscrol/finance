"""Own deterministic D4 text; free prose never receives an entailment certificate.

The two authoring boundaries compile an approved observation and render whole
document blocks selected by opaque refs. No IO, model call or numeric pool.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from difflib import SequenceMatcher
from hashlib import sha256
import json
import math
from types import MappingProxyType
from typing import TYPE_CHECKING

from market_feature_store.signals import (
    DOUBLE_RED_DESCRIPTION, DOUBLE_RED_SQL, is_double_red,
)

if TYPE_CHECKING:
    from intelligence.services.research_contract import ResearchRunContext
    from intelligence.services.research_tool_registry import ToolObservation

_SCHEMA = "d4_mainline_snapshot_v1"
_INPUTS = ("sector_pct", "diff_ratio", "sector_amount")
_KEYS = ("trade_date", "theme_code", "sector_ts_code")
_BASIS_KEYS = frozenset({
    "schema", "scope", "status", "market_date", "snapshot_date", "requested_as_of",
    "target_theme", "theme_names", "total_rows", "total_groups", "preview_limit_per_theme",
    "ordering", "groups", "history_window", "history", "metric_semantics",
    "price_volume_signals", "scope_note",
})
_SIGNAL_KEYS = frozenset({
    *_KEYS, *_INPUTS, "theme_name", "strict_double_red", "state", "inputs_complete", "missing_inputs",
})
# One versioned source descriptor, read by both the D4 producer and decoder.
# Units describe inputs; prose is a presentation of this source contract.
D4_SOURCE_DESCRIPTOR = MappingProxyType({
    "schema": _SCHEMA, "definition_version": "d4_strict_double_red_v1",
    "predicate_owner": "market_feature_store.signals.is_double_red",
    "inputs": MappingProxyType({"sector_pct": "%", "diff_ratio": "%", "sector_amount": "亿元"}),
    "metric_semantics": MappingProxyType({
        "sector_pct": "coalesce(fact_sector_daily.pct_chg, fact_mainline_sector_daily.today_pct)；%",
        "sector_amount": "coalesce(fact_sector_daily.amount, fact_mainline_sector_daily.amount/10000)；亿元",
        "mainline_amount": "fact_mainline_sector_daily.amount；保留原表值与源口径",
        "diff_ratio": "(当日成交额/上一交易日成交额-1)*100；成交额环比%，不是净流入",
        "strict_double_red": DOUBLE_RED_DESCRIPTION,
        "strict_double_red_rule": "market_feature_store.signals.is_double_red；任一输入缺失则资格未知",
    }),
})


class OwnedResultError(ValueError):
    """A stable source/selection error, not a claim about arbitrary prose."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return sha256(_json(value).encode()).hexdigest()


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return value


def _date(value: object) -> str:
    if not isinstance(value, str):
        raise OwnedResultError("source_date_conflict")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise OwnedResultError("source_date_conflict") from exc
    if parsed.isoformat() != value:
        raise OwnedResultError("source_date_conflict")
    return value


def _count(value: object) -> int:
    if type(value) is not int or value < 0:
        raise OwnedResultError("source_scope_conflict")
    return value


@dataclass(frozen=True)
class OwnedBlock:
    result_ref: str
    key: tuple[str, ...]
    role: str
    value: bool | None
    text: str
    source_digest: str
    definition_digest: str
    start: int = 0
    end: int = 0

    def payload(self) -> dict[str, object]:
        return {"result_ref": self.result_ref, "key": list(self.key), "role": self.role,
                "value": self.value, "text": self.text, "source_digest": self.source_digest,
                "definition_digest": self.definition_digest, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class OwnedCatalogue:
    blocks: tuple[OwnedBlock, ...] = ()
    source_digest: str = ""
    source_identity: str = ""
    witness: Mapping[str, object] = MappingProxyType({})

    def ref_for(self, key: tuple[str, ...], role: str) -> str:
        for block in self.blocks:
            if block.key == key and block.role == role:
                return block.result_ref
        raise OwnedResultError("unknown_result_ref")

    def unavailable(self, role: str) -> bool:
        return not any(block.role == role for block in self.blocks)

    def model_view(self) -> list[dict[str, str]]:
        return [{"result_ref": block.result_ref, "text": block.text} for block in self.blocks]


@dataclass(frozen=True)
class RenderedOwnedParts:
    draft: str
    owned_blocks: tuple[OwnedBlock, ...]
    free_blocks: int
    receipt: dict[str, object] | None


@dataclass(frozen=True)
class _DeliveredSource:
    owner: str
    observation: ToolObservation


def _context_owner(context: ResearchRunContext) -> str:
    from intelligence.services.episode_entry_identity import capture_entry_identity

    return _digest([context.contract.task_id, context.contract.task_frame_hash,
                    context.trace_parent_id, capture_entry_identity(context)])


def _catalogue_from_context(context: ResearchRunContext) -> OwnedCatalogue:
    catalogues = []
    seen: dict[str, str] = {}
    fact_inputs: dict[tuple[tuple[str, ...], str], str] = {}
    for item in context._owned_result_sources:
        if not isinstance(item, _DeliveredSource) or item.owner != _context_owner(context):
            continue
        catalogue = compile_owned_results(item.observation, context)
        if not catalogue.blocks:
            continue
        old_digest = seen.get(catalogue.source_identity)
        if old_digest and old_digest != catalogue.source_digest:
            raise OwnedResultError("same_source_input_conflict")
        if old_digest:
            continue
        cards = {tuple(card["key"]): card["content_hash"] for card in catalogue.witness["cards"]}
        for row in catalogue.witness["query_basis"]["price_volume_signals"]:
            key = tuple(row[k] for k in _KEYS)
            if key not in cards:
                continue
            identity = (key, cards[key])
            inputs_digest = _digest({k: _thaw(row[k]) for k in (*_INPUTS, "inputs_complete", "missing_inputs", "strict_double_red")})
            if identity in fact_inputs and fact_inputs[identity] != inputs_digest:
                raise OwnedResultError("same_source_input_conflict")
            fact_inputs[identity] = inputs_digest
        seen[catalogue.source_identity] = catalogue.source_digest
        catalogues.append(catalogue)
    if not catalogues:
        return OwnedCatalogue()
    if len(catalogues) == 1:
        return catalogues[0]
    blocks = tuple(block for catalogue in catalogues for block in catalogue.blocks)
    witnesses = [_thaw(catalogue.witness) for catalogue in catalogues]
    cards = [card for witness in witnesses for card in witness["cards"]]
    return OwnedCatalogue(blocks, _digest(sorted(seen.values())), _digest(sorted(seen)),
                          _freeze({"cards": cards, "sources": witnesses}))


def _acknowledge_owned_results(
    observation: ToolObservation, model_content: str, *, context: ResearchRunContext,
) -> None:
    try:
        facing = json.loads(model_content)
    except (TypeError, ValueError):
        return
    if not isinstance(facing, dict) or not isinstance(facing.get("owned_results"), dict):
        return
    catalogue = compile_owned_results(observation, context)
    if (not catalogue.blocks or facing.get("query_basis") != observation.query_basis
            or facing["owned_results"].get("parts") != catalogue.model_view()):
        return
    source = replace(observation, query_basis=json.loads(_json(observation.query_basis)), telemetry={})
    delivery = _DeliveredSource(_context_owner(context), source)
    # Check source conflicts without leaving rejected data in the current cache.
    trial = replace(context, _owned_result_sources=[*context._owned_result_sources, delivery])
    _catalogue_from_context(trial)
    context._owned_result_sources.append(delivery)


def compile_owned_results(
    source_observation: ToolObservation, authorized_context: ResearchRunContext | None,
) -> OwnedCatalogue:
    """Compile only allowed source cards and their same-key D4 metadata.

    None is the existing, already-dispatched projection seam: it may display
    refs but grants no authority. ACK and each later use require a real context.
    Unknown/unapproved sources yield no catalogue; known conflicting sources
    fail closed. Telemetry and private locators are never read.
    """
    from intelligence.services.agent_research import evidence_content_hash

    basis = source_observation.query_basis
    if (not isinstance(basis, dict) or basis.get("schema") != _SCHEMA
            or source_observation.tool != "mainline_context"
            or source_observation.trace.status != "success" or basis.get("status") != "available"
            or not source_observation.evidence):
        return OwnedCatalogue()
    if source_observation.dataset != "mainline_sector_daily":
        raise OwnedResultError("source_dataset_conflict")
    if set(basis) != _BASIS_KEYS or basis["metric_semantics"] != D4_SOURCE_DESCRIPTOR["metric_semantics"]:
        raise OwnedResultError("source_definition_conflict")
    # JSON types and finite numbers only; a witness must be immutable and portable.
    try:
        _json(basis)
    except (TypeError, ValueError) as exc:
        raise OwnedResultError("source_schema_conflict") from exc
    snapshot = _date(basis["snapshot_date"])
    requested = _date(basis["requested_as_of"])
    market = _date(basis["market_date"])
    if snapshot > requested or snapshot > market:
        raise OwnedResultError("source_date_conflict")
    if authorized_context is not None:
        if "mainline_context" not in authorized_context.contract.allowed_capabilities:
            raise OwnedResultError("source_not_authorized")
        cutoff = authorized_context.information_cutoff.as_of_date.isoformat()
        if max(snapshot, requested, market) > cutoff:
            raise OwnedResultError("source_after_cutoff")
    groups, rows = basis["groups"], basis["price_volume_signals"]
    if not isinstance(groups, list) or not isinstance(rows, list):
        raise OwnedResultError("source_schema_conflict")
    total = _count(basis["total_rows"])
    limit = _count(basis["preview_limit_per_theme"])
    preview = omitted = 0
    names: list[str] = []
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"theme_name", "total_rows", "preview_rows", "omitted_rows", "non_null_counts"}:
            raise OwnedResultError("source_scope_conflict")
        name = group["theme_name"]
        if not isinstance(name, str) or not name or name in names:
            raise OwnedResultError("source_scope_conflict")
        names.append(name)
        shown, hidden, count = (_count(group[k]) for k in ("preview_rows", "omitted_rows", "total_rows"))
        if shown + hidden != count or shown > limit:
            raise OwnedResultError("source_scope_conflict")
        preview += shown
        omitted += hidden
        non_null = group["non_null_counts"]
        if not isinstance(non_null, dict) or any(_count(n) > count for n in non_null.values()):
            raise OwnedResultError("source_scope_conflict")
    scope = basis["scope"]
    target = basis["target_theme"]
    if (preview != len(rows) or preview + omitted != total
            or _count(basis["total_groups"]) != len(groups) or basis["theme_names"] != names
            or scope not in {"current_table_single_theme", "current_table_all_themes"}
            or (scope == "current_table_single_theme" and (not target or names != [target]))
            or (scope == "current_table_all_themes" and target is not None)):
        raise OwnedResultError("source_scope_conflict")
    cards: dict[tuple[str, ...], object] = {}
    for card in source_observation.evidence:
        if (card.tool != "mainline_context" or not card.content_hash
                or card.content_hash not in source_observation.evidence_hashes
                or card.evidence_tier != "L4_structured" or card.io_effect != "local_read"):
            continue
        try:
            key = json.loads(card.independent_key)
        except (TypeError, ValueError) as exc:
            raise OwnedResultError("source_key_conflict") from exc
        if (not isinstance(key, list) or len(key) != 3
                or any(not isinstance(k, str) or not k for k in key)
                or key[0] != snapshot or card.source_date != key[0]):
            raise OwnedResultError("source_key_conflict")
        fact_key = tuple(key)
        if fact_key in cards or evidence_content_hash(card) != card.content_hash:
            raise OwnedResultError("source_card_conflict")
        cards[fact_key] = card
    if not cards:
        return OwnedCatalogue()
    selected: list[tuple[dict, object, bool | None]] = []
    seen: set[tuple[str, ...]] = set()
    row_names: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != _SIGNAL_KEYS:
            raise OwnedResultError("source_schema_conflict")
        key = tuple(row[k] for k in _KEYS)
        if (any(not isinstance(k, str) or not k for k in key) or key[0] != snapshot
                or key in seen or row["theme_name"] not in names):
            raise OwnedResultError("source_key_conflict")
        seen.add(key)
        row_names[row["theme_name"]] = row_names.get(row["theme_name"], 0) + 1
        # A filtered-out card never gets a ref merely because raw metadata still has a row.
        if key not in cards:
            continue
        values = tuple(row[k] for k in _INPUTS)
        if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in values):
            raise OwnedResultError("source_numeric_conflict")
        missing = [k for k, v in zip(_INPUTS, values) if v is None]
        if (type(row["inputs_complete"]) is not bool or row["inputs_complete"] != (not missing)
                or row["missing_inputs"] != missing):
            raise OwnedResultError("source_completeness_conflict")
        truth = None if missing else is_double_red(*values)
        if row["strict_double_red"] is not truth:
            raise OwnedResultError("source_truth_conflict")
        selected.append((row, cards[key], truth))
    if set(cards) - seen or any(row_names.get(g["theme_name"], 0) != g["preview_rows"] for g in groups):
        raise OwnedResultError("source_key_scope_conflict")
    definition = {"descriptor": _thaw(D4_SOURCE_DESCRIPTOR), "predicate": DOUBLE_RED_SQL}
    identities = [{"key": list(key), "content_hash": card.content_hash, "source_date": card.source_date}
                  for key, card in sorted(cards.items())]
    identity = {"tool": source_observation.tool, "dataset": source_observation.dataset,
                "cards": identities, "schema": _SCHEMA}
    witness = {**identity, "query_basis": basis, "definition": definition}
    digest, definition_digest = _digest(witness), _digest(definition)
    blocks: list[OwnedBlock] = []
    for row, card, truth in selected:
        key = tuple(row[k] for k in _KEYS)
        display = card.title.rsplit(" / ", 1)[-1]
        qualifier = "资格未知" if truth is None else "满足严格双红" if truth else "不满足严格双红"
        text = f"{snapshot}，{row['theme_name']}主题中的{display}{qualifier}。"
        ref = "R" + _digest([digest, key, "strict_double_red"])[:20]
        blocks.append(OwnedBlock(ref, key, "strict_double_red", truth, text, digest, definition_digest))
    texts = {
        "rule_definition": "本地量价规则：" + DOUBLE_RED_DESCRIPTION + "这是规则定义，不是当日行情观测值。",
        "scope": f"{snapshot}，本表共{len(groups)}主题、{total}行，原表预览{preview}行、省略{omitted}行；"
                 f"本次来源可认证{len(selected)}条板块资格，不能据该预览认证全市场唯一主线。",
    }
    for role, text in texts.items():
        blocks.append(OwnedBlock("R" + _digest([digest, role])[:20], (), role, None,
                                 text, digest, definition_digest))
    return OwnedCatalogue(tuple(blocks), digest, _digest(identity), _freeze(witness))


def render_owned_parts(
    parts: object, catalogue: OwnedCatalogue, *, legacy_draft: str = "",
) -> RenderedOwnedParts:
    """Render ref-only objects and free strings as separate document blocks."""
    if parts is None:
        return RenderedOwnedParts(legacy_draft, (), int(bool(legacy_draft)), None)
    if legacy_draft or not isinstance(parts, (list, tuple)):
        raise OwnedResultError("two_drafts_or_bad_answer_parts")
    by_ref = {block.result_ref: block for block in catalogue.blocks}
    text_parts: list[str] = []
    owned: list[OwnedBlock] = []
    free = 0
    free_spans: list[dict[str, int]] = []
    offset = 0
    saved: list[object] = []
    for part in parts:
        if type(part) is str:
            text = part
            free += 1
            saved.append(part)
        elif isinstance(part, dict) and set(part) == {"result_ref"} and isinstance(part["result_ref"], str):
            block = by_ref.get(part["result_ref"])
            if block is None:
                raise OwnedResultError("unknown_result_ref")
            text = block.text
            saved.append({"result_ref": block.result_ref})
        else:
            raise OwnedResultError("bad_answer_part")
        if text_parts:
            offset += 2
        if type(part) is str:
            free_spans.append({"start": offset, "end": offset + len(text)})
        else:
            owned.append(replace(block, start=offset, end=offset + len(text)))
        text_parts.append(text)
        offset += len(text)
    draft = "\n\n".join(text_parts)
    receipt = {"schema": "owned_answer_v1", "parts": saved,
               "draft_sha256": sha256(draft.encode()).hexdigest(),
               "source_digests": sorted({block.source_digest for block in owned}),
               "owned_blocks": [block.payload() for block in owned],
               "free_blocks": free, "free_spans": free_spans,
               "qualification": "partially_owned" if owned and free else "owned" if owned else "unassessed"}
    return RenderedOwnedParts(draft, tuple(owned), free, receipt)


def _matching_owned_answer(events: object, draft: str) -> dict[str, object] | None:
    """Only the adopted latest finish can own this body; never search older prose."""
    for event in reversed(tuple(events)):
        if event.kind != "finish":
            continue
        receipt = event.payload.get("owned_answer")
        if isinstance(receipt, Mapping) and receipt.get("draft_sha256") == sha256(draft.encode()).hexdigest():
            return _thaw(receipt)
        return None
    return None


def _verify_owned_answer(receipt: object, draft: str, *, context: ResearchRunContext) -> RenderedOwnedParts | None:
    if receipt is None:
        return None
    raw = _thaw(receipt)
    if not isinstance(raw, dict) or raw.get("schema") != "owned_answer_v1":
        raise OwnedResultError("invalid_ownership_receipt")
    rendered = render_owned_parts(raw.get("parts"), _catalogue_from_context(context))
    expected = {**rendered.receipt, "owner": _context_owner(context)}
    if expected != raw or rendered.draft != draft:
        raise OwnedResultError("ownership_source_ref_body_conflict")
    return rendered


@dataclass(frozen=True)
class _OwnedAnswerProof:
    draft: str
    owned_blocks: tuple[OwnedBlock, ...]
    free_blocks: int
    owner: str
    task_id: str
    frame_hash: str


def _make_owned_proof(outcome: object, *, context: ResearchRunContext) -> _OwnedAnswerProof | None:
    latest = next((e for e in reversed(outcome.events) if e.kind == "finish"), None)
    receipt = latest.payload.get("owned_answer") if latest is not None else None
    if receipt is None:
        return None
    configure = next((e.payload for e in outcome.events if e.kind == "configure"), {})
    if (configure.get("task_id") != context.contract.task_id
            or (receipt.get("owned_blocks") and "mainline_context" not in configure.get("authorized_tools", ()))
            or outcome.task_frame_hash != context.contract.task_frame_hash):
        raise OwnedResultError("ownership_task_or_authorization_conflict")
    _rebuild_owned_sources(outcome.events, context=context, evidence=outcome.evidence)
    rendered = _verify_owned_answer(receipt, outcome.draft, context=context)
    return _OwnedAnswerProof(rendered.draft, rendered.owned_blocks, rendered.free_blocks,
                             _context_owner(context), context.contract.task_id, context.contract.task_frame_hash)


def _owned_sentence_indexes(sentences: object, verified: object) -> frozenset[int]:
    proof = getattr(verified, "_owned_answer", None)
    if (not isinstance(proof, _OwnedAnswerProof) or verified.contract is None
            or proof.task_id != verified.contract.task_id or proof.frame_hash != verified.outcome.task_frame_hash
            or proof.draft != verified.outcome.draft):
        return frozenset()
    # Locate successive occurrences, preserving equal free text as a different span.
    cursor, indexes = 0, set()
    for sentence in sentences:
        text = str(sentence.get("text", ""))
        start = proof.draft.find(text, cursor)
        if start < 0:
            return frozenset()
        end = start + len(text)
        cursor = end
        if any(block.start <= start and end <= block.end for block in proof.owned_blocks):
            indexes.add(sentence["index"])
    return frozenset(indexes)


def _rewrite_free_sentence(verified: object, sentences: object, index: int, public: str, annotated: str) -> tuple[str, bool]:
    """An identical free sentence is a separate occurrence, never the first match."""
    proof = getattr(verified, "_owned_answer", None)
    if not isinstance(proof, _OwnedAnswerProof) or proof.draft != verified.outcome.draft:
        return public, False
    cursor = 0
    for sentence in sentences:
        text = str(sentence.get("text", ""))
        start = proof.draft.find(text, cursor)
        if start < 0:
            return public, False
        end, cursor = start + len(text), start + len(text)
        if sentence["index"] != index:
            continue
        if any(block.start <= start and end <= block.end for block in proof.owned_blocks):
            return public, False
        for block in SequenceMatcher(None, proof.draft, public, autojunk=False).get_matching_blocks():
            if block.a <= start and end <= block.a + block.size:
                left, right = block.b + start - block.a, block.b + end - block.a
                return public[:left] + annotated + public[right:], True
        return public, False
    return public, False


def _public_owned_coverage(proof: object, public: str, *, context: ResearchRunContext) -> dict[str, object] | None:
    if not isinstance(proof, _OwnedAnswerProof):
        return None
    if proof.owner != _context_owner(context):
        raise OwnedResultError("ownership_owner_conflict")
    opcodes = SequenceMatcher(None, proof.draft, public, autojunk=False).get_opcodes()
    fragments = []
    original_paragraphs = proof.draft.split("\n\n")
    public_paragraphs = public.strip().split("\n\n")
    for block in proof.owned_blocks:
        status, public_start, public_end = "removed", None, None
        for tag, a, b, x, y in opcodes:
            if tag == "equal" and a <= block.start and block.end <= b:
                left, right = x + block.start - a, x + block.end - a
                # A complete document node cannot be absorbed into free syntax.
                after = public[right:].lstrip("\n")
                node_before = left == 0 or public[:left].endswith("\n\n")
                node_after = not after or public[right:].startswith("\n\n")
                if node_before and node_after and public[left:right] == block.text:
                    status, public_start, public_end = "faithful", left, right
                else:
                    status = "changed"
                break
            if tag != "equal" and a < block.end and b > block.start:
                status = "removed" if tag == "delete" and a <= block.start and block.end <= b else "changed"
        # If free prose duplicates an owned node, deletion may be ambiguous.
        # Same node count/order can preserve it; a shorter document cannot certify the clone.
        if (proof.draft.count(block.text) > 1 and status == "faithful"
                and len(original_paragraphs) != len(public_paragraphs)):
            status, public_start, public_end = "removed", None, None
        fragments.append({"result_ref": block.result_ref, "status": status,
                          "public_start": public_start, "public_end": public_end})
    return {"owned_fragments": fragments,
            "owned_faithful": sum(f["status"] == "faithful" for f in fragments),
            "owned_changed": sum(f["status"] == "changed" for f in fragments),
            "owned_removed": sum(f["status"] == "removed" for f in fragments),
            "free_unassessed": proof.free_blocks, "whole_answer": "unassessed"}


def _rebuild_owned_sources(events: object, *, context: ResearchRunContext, evidence: object = None) -> None:
    """Rebuild from native, delivered tool results and existing approved atoms only."""
    from intelligence.services.provider_observability import ProviderTrace
    from intelligence.services.research_tool_registry import ToolObservation
    from intelligence.services.agent_research import AgentEvidence

    approved = None if evidence is None else {card.content_hash: card for card in evidence}
    trial = replace(context, _owned_result_sources=[])
    for event in events:
        if event.kind != "tool_result":
            continue
        payload = _thaw(event.payload)
        if payload.get("tool") != "mainline_context" or payload.get("ok") is not True:
            continue
        content = payload.get("model_content", "")
        if (not isinstance(content, str) or not content
                or payload.get("model_content_sha256") != sha256(content.encode()).hexdigest()
                or not isinstance(payload.get("owned_results"), dict)):
            continue
        if approved is None:
            # Source-only recovery, never reconstruction of the evidence ledger.
            fields = {"tool", "title", "detail", "source", "source_date", "evidence_tier", "supports",
                      "contradicts", "independent_key", "freshness", "content_hash", "io_effect"}
            cards = tuple(AgentEvidence(**{**{k: v for k, v in raw.items() if k in fields},
                                           "supports": tuple(raw.get("supports", ())),
                                           "contradicts": tuple(raw.get("contradicts", ()))})
                          for raw in payload.get("evidence", ()) if isinstance(raw, dict))
        else:
            cards = tuple(approved[digest] for digest in payload.get("evidence_hashes", ()) if digest in approved)
        observation = ToolObservation(
            tool=payload["tool"], query=payload.get("query", ""), evidence=cards,
            observation=payload.get("observation", ""),
            trace=ProviderTrace(provider="owned:restore", capability="mainline_context", status=payload.get("status", "unknown")),
            evidence_hashes=tuple(payload.get("evidence_hashes", ())),
            dataset=payload.get("dataset", "unknown"), query_basis=payload.get("query_basis", {}),
        )
        _acknowledge_owned_results(observation, content, context=trial)
    context._owned_result_sources[:] = trial._owned_result_sources
