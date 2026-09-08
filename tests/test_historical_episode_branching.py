"""A02 execution seam: observed counterevidence changes a real Episode branch.

The model is deliberately scripted. This proves observation -> next tool ->
saved hypothesis wiring, not autonomous research ability of a real LLM.
"""

import json
from threading import Event

import duckdb
import pytest

from intelligence.runtime.agent_episode import ContinuousAgentEpisode
from intelligence.services.agent_runtime import ModelToolCall, ModelTurn
from intelligence.services.query_understanding import understand_query
from scripts.audit_tool_reachability import _history_probe


class _ObservationBranchModel:
    """No fixture value or expected branch is passed to the model."""

    def __init__(self, outputs, purpose):
        self.outputs = outputs
        self.purpose = purpose
        self.calls = 0
        self.branch = None
        self.observed_return = None
        self.refs = []

    @staticmethod
    def _tool(call_id, name, arguments):
        return ModelTurn(
            "", (ModelToolCall(call_id, name, arguments),), "scripted-branch", ""
        )

    @staticmethod
    def _observation(message):
        payload = json.loads(message["content"])
        assert payload["ok"] is True, payload
        # The default model projection may truncate detail strings. The compact
        # leading observation object preserves the artifact reference separately.
        observation = payload["observation"].replace('\\"', '"')
        metadata, _ = json.JSONDecoder().raw_decode(
            observation[observation.index("{") :]
        )
        return metadata, payload["evidence"]

    @staticmethod
    def _visible_scalar(evidence, name):
        for item in evidence:
            if not item["title"].startswith("历史观察样本"):
                continue
            # Every sample must be complete model-visible JSON. Reject a clipped
            # numeric prefix rather than guessing its value or sign.
            detail = json.loads(item["detail"].replace('\\"', '"'))
            if name in detail.get("features", {}):
                assert detail["status"][name] == "complete"
                return detail["features"][name]
        raise AssertionError(f"actual model observation does not expose {name}")

    def complete(self, *, messages, tools, timeout):
        del timeout
        self.calls += 1
        assert self.calls <= 5, "unexpected repair/finalizer cycle"
        assert tools is not None
        observed = [message for message in messages if message.get("role") == "tool"]
        base = {
            "start": "2026-08-03",
            "end": "2026-08-04",
            "entity_codes": ["AUDIT.FP"],
        }
        if not observed:
            return self._tool(
                "observe",
                "history_query",
                {**base, "operation": "compute_history", "features": ["return_pct"]},
            )
        if len(observed) == 1:
            metadata, evidence = self._observation(observed[-1])
            self.refs.append(metadata["result_ref"])
            self.observed_return = self._visible_scalar(evidence, "return_pct")
            assert self.observed_return is not None
            self.branch = (
                "counterevidence" if self.observed_return < 0 else "volume_confirmation"
            )
            if self.branch == "counterevidence":
                return self._tool(
                    "check-loss-day",
                    "history_query",
                    {
                        **base,
                        "start": "2026-08-04",
                        "operation": "compute_history",
                        "features": ["return_pct"],
                    },
                )
            return self._tool(
                "check-volume",
                "history_query",
                {**base, "operation": "compute_history", "features": ["amount_ratio"]},
            )
        if len(observed) == 2:
            metadata, evidence = self._observation(observed[-1])
            self.refs.append(metadata["result_ref"])
            weakened = self.branch == "counterevidence"
            if weakened:
                assert self._visible_scalar(evidence, "return_pct") < 0
            else:
                assert self._visible_scalar(evidence, "amount_ratio") > 1
            hypothesis = {
                "hypothesis_id": "agriculture-continuation",
                "statement": "区间下跌削弱延续假设"
                if weakened
                else "上涨伴随成交额增加，保留延续候选",
                "source_case_refs": self.refs,
                "status": "weakened" if weakened else "candidate",
                "alternatives": ["整体市场环境可能解释表观相关"],
                "support_refs": [] if weakened else self.refs,
                "counterevidence_refs": self.refs if weakened else [],
                "failed_sample_refs": self.refs if weakened else [],
                "exposed_sample_refs": self.refs,
            }
            return self._tool(
                "save-revised-hypothesis",
                "save_history_research",
                {
                    "draft": {
                        "question": "复盘同一农业行情并检验延续候选",
                        "purpose": self.purpose,
                        "entity_ids": ["AUDIT.FP"],
                        "window_start": base["start"],
                        "window_end": base["end"],
                        "selection_mode": "posthoc_winner",
                        "source_refs": self.refs,
                        "hypotheses": [hypothesis],
                        "open_questions": ["需要更多未暴露样本"],
                        "stop_reason": "counterevidence_found"
                        if weakened
                        else "candidate_needs_validation",
                    }
                },
            )
        gap = "脚本机制测试仅检查单例分支；尚无独立多样本验证或可靠事件时间。"
        return ModelTurn(
            json.dumps(
                {
                    "status": "partial",
                    "draft": "已按实际盘面保存候选与反证边界。" + gap,
                    "gaps": [gap],
                    "bindings": [
                        {"output_id": output, "evidence_hashes": [], "gap": gap}
                        for output in self.outputs
                    ],
                    "history_research": {
                        "purpose": self.purpose,
                        "result_refs": self.refs,
                        "claim_level": "single_case",
                        "research_only": True,
                        "decision_eligible": False,
                        "promotion_eligible": False,
                    },
                },
                ensure_ascii=False,
            ),
            (),
            "scripted-branch",
            "",
        )


def _run(root, *, final_return, cancel_after_first_result=False):
    registry, context, session = _history_probe(root, with_session=True)
    db = root / "finance/db/market_feature_store.duckdb"
    # The sole fact difference in the paired runs. The model only sees tool output.
    with duckdb.connect(str(db)) as con:
        con.execute(
            "UPDATE fact_sector_daily SET pct_chg=? WHERE trade_date='2026-08-04'",
            [final_return],
        )
    question = session.store.load_run(session.run_id).question
    frame = understand_query(question).task_frame
    model = _ObservationBranchModel(
        [item.output_id for item in context.contract.required_outputs],
        context.history_intent.purpose,
    )
    cancel = Event()

    def on_event(event):
        if cancel_after_first_result and event.kind == "tool_result":
            cancel.set()

    outcome = ContinuousAgentEpisode(
        model, is_cancelled=cancel.is_set, event_sink=on_event
    ).run(task_frame=frame, context=context, registry=registry)
    cases = [
        session.read(ref)["draft"] for ref in session.refs if "/history-case-" in ref
    ]
    queries = [session.read(ref) for ref in session.refs if "/history-query-" in ref]
    return outcome, model, cases, queries, question


def test_same_question_counterevidence_changes_real_tool_branch_and_saved_hypothesis(
    tmp_path,
):
    positive, positive_model, positive_cases, positive_queries, question = _run(
        tmp_path / "positive", final_return=2
    )
    negative, negative_model, negative_cases, negative_queries, same_question = _run(
        tmp_path / "negative", final_return=-10
    )
    assert question == same_question
    assert positive.stop_reason == negative.stop_reason == "model_finish"
    assert positive.status == negative.status == "partial"
    assert positive_model.observed_return == pytest.approx(3.02)
    assert negative_model.observed_return == pytest.approx(-9.1)
    assert positive_model.branch == "volume_confirmation"
    assert negative_model.branch == "counterevidence"
    assert [item["spec"]["operation"] for item in positive_queries] == [
        "compute_history",
        "compute_history",
    ]
    assert [item["spec"]["operation"] for item in negative_queries] == [
        "compute_history",
        "compute_history",
    ]
    assert positive_queries[1]["spec"]["features"] == ["amount_ratio"]
    assert negative_queries[1]["spec"]["features"] == ["return_pct"]
    assert (
        negative_queries[1]["spec"]["start"]
        == negative_queries[1]["spec"]["end"]
        == "2026-08-04"
    )
    assert positive_queries[0]["spec"] == negative_queries[0]["spec"]
    assert len(positive_cases) == len(negative_cases) == 1
    positive_hypothesis = positive_cases[0]["hypotheses"][0]
    negative_hypothesis = negative_cases[0]["hypotheses"][0]
    assert positive_hypothesis["status"] == "candidate"
    assert negative_hypothesis["status"] == "weakened"
    assert negative_hypothesis["failed_sample_refs"] == negative_model.refs
    assert negative_hypothesis["counterevidence_refs"] == negative_model.refs
    assert set(negative_model.refs) <= set(negative_cases[0]["exposed_sample_refs"])
    assert positive.usage.tool_calls == negative.usage.tool_calls == 3
    assert all(
        len([event for event in run.events if event.kind == "tool_result"]) == 3
        for run in (positive, negative)
    )


def test_existing_episode_cancellation_stops_branch_before_more_tools_or_save(tmp_path):
    outcome, model, cases, queries, _ = _run(
        tmp_path, final_return=-10, cancel_after_first_result=True
    )
    assert outcome.stop_reason == "cancelled"
    assert model.calls == 1
    assert len(queries) == 1
    assert cases == []
    assert outcome.usage.tool_calls == 1
