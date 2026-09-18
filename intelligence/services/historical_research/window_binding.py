"""Bind an analysis to saved observations, never to an assistant's old answer.

No DB, new store, or research loop. The Episode supplies already scope-checked
originals and its actual delivery metadata. All dates remain explicit in args.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from threading import Lock

ANALYSIS_OPERATIONS = frozenset({"rank_history", "trace_history", "compute_history"})
BINDING_VERSION = "history-window-binding-v1"


def resolve_window_binding(spec, intent, source, delivered):
    reference = spec.window_ref
    source_spec = source.get("spec", {})
    operation = source_spec.get("operation")
    if source.get("status") != "research_only" or not source.get("query_id"):
        raise ValueError("history_window_source_invalid: expected a saved calculation, not a case or prose")
    if intent.analysis_window_source == "analogue" and operation != "find_analogues":
        raise ValueError("history_window_analogue_required: no successful analogue candidate selected; do not substitute the current window")
    if intent.analysis_window_source == "prior_analysis" and operation not in ANALYSIS_OPERATIONS:
        raise ValueError("history_window_prior_analysis_required: read the relevant rank/trace/compute original")
    if not delivered:
        raise ValueError("history_window_source_not_read: first read_history_result on the referenced original in this turn")
    if operation == "find_analogues":
        sample_id = reference.get("sample_id")
        rows = [r for r in source.get("rows", []) if sample_id and r.get("sample_id") == sample_id]
        if len(rows) != 1:
            raise ValueError("history_window_sample_not_found: select a saved analogue candidate sample_id, not its reference window or preview ordinal")
        if sample_id not in {s for item in delivered for s in item.get("visible_sample_ids", [])}:
            raise ValueError("history_window_sample_not_read: page the candidate with read_history_result before selecting it")
        start, end = rows[0]["start"], rows[0]["end"]
        root_query, root_sample = source["query_id"], sample_id
        ranking_start, ranking_end = start, end
    elif operation in ANALYSIS_OPERATIONS:
        if reference.get("sample_id"):
            raise ValueError("history_window_sample_not_applicable: use the analysis observation window, not a feature/member row window")
        start, end = source_spec.get("start"), source_spec.get("end")
        ancestor = source.get("window_binding", {})
        root_query = ancestor.get("root_query_id", source["query_id"])
        root_sample = ancestor.get("root_sample_id")
        ranking_start = ancestor.get("ranking_start", start)
        ranking_end = ancestor.get("ranking_end", end)
    else:
        raise ValueError("history_window_source_invalid: use find_analogues candidate or rank/trace/compute observation window")
    requested = (spec.start.isoformat(), spec.end.isoformat())
    if spec.operation == "rank_history" and requested != (ranking_start, ranking_end):
        raise ValueError("history_window_mismatch: extended observation is not a new ranking interval; read the original rank or analogue source")
    relation = "same_window"
    if requested != (start, end):
        if (intent.allow_window_extension and spec.operation == "trace_history"
                and operation in ANALYSIS_OPERATIONS and requested[0] == start
                and end is not None and requested[1] > end):
            relation = "extended_observation"
        else:
            raise ValueError("history_window_mismatch: start/end must equal the selected saved window; do not shorten or replace it after overflow. Only an explicitly authorized trace may extend end")
    return {
        "version": BINDING_VERSION,
        "source_reference": dict(reference),
        "source_query_id": source["query_id"],
        "source_start": start, "source_end": end,
        "ranking_start": ranking_start, "ranking_end": ranking_end,
        "root_query_id": root_query, "root_sample_id": root_sample,
        "start": requested[0], "end": requested[1], "relation": relation,
    }


def validate_saved_window_binding(payload, source):
    """Recheck a dependency edge without rewriting old originals or reading DB.

    This validates recorded lineage, not current-turn delivery or new permission.
    The caller separately checks every ancestor's authorization and cutoff.
    """
    from .intent import HistoryIntent
    from .query import HistoryQuerySpec

    spec = HistoryQuerySpec.from_arguments(payload["spec"])
    binding = payload.get("window_binding")
    if not isinstance(binding, dict) or binding.get("version") != BINDING_VERSION:
        raise ValueError("history_window_binding_invalid: missing or unsupported saved definition")
    intent = HistoryIntent("retrospective_discovery", analysis_window_source="prior_analysis"
                           if binding.get("relation") == "extended_observation" else "none",
                           allow_window_extension=binding.get("relation") == "extended_observation")
    expected = resolve_window_binding(spec, intent, source, [{
        "visible_sample_ids": [r.get("sample_id") for r in source.get("rows", [])],
    }])
    if expected != binding:
        raise ValueError("history_window_binding_invalid: saved lineage does not match the source original")


class WindowSelection:
    """Per-Episode reservation: incompatible parallel calls cannot both publish.

    No lock around IO. A failed first calculation releases its reservation;
    successful selection remains fixed for this turn, not for the conversation.
    """

    def __init__(self):
        self._lock = Lock()
        self._key = None
        self._active = 0
        self._committed = False
        self._observation_end = None
        self._observation_active = 0
        self._observation_committed = False

    @contextmanager
    def reserve(self, binding: Mapping | None, *, observation: bool = False):
        if binding is None:
            yield
            return
        # A user-authorized observation extension keeps the reference fixed;
        # its explicitly labelled later endpoint is not a new ranking window.
        key = tuple(binding.get(k) for k in ("root_query_id", "root_sample_id", "source_start", "source_end"))
        with self._lock:
            if self._key is not None and self._key != key:
                raise ValueError("history_window_selection_conflict: this turn already selected another reference/window; compare sector and stock on the same window")
            if observation and self._observation_end not in (None, binding["end"]):
                raise ValueError("history_window_observation_conflict: trace comparisons in this turn must use the same observation endpoint")
            self._key = key
            self._active += 1
            if observation:
                self._observation_end = binding["end"]
                self._observation_active += 1
        succeeded = False
        try:
            yield
            succeeded = True
        finally:
            with self._lock:
                self._committed |= succeeded
                self._active -= 1
                if not self._active and not self._committed:
                    self._key = None
                if observation:
                    self._observation_committed |= succeeded
                    self._observation_active -= 1
                    if not self._observation_active and not self._observation_committed:
                        self._observation_end = None
