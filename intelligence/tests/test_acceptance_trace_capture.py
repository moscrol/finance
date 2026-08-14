from __future__ import annotations

import json

import pytest

from intelligence.api.app import _public_trace_step
from intelligence.eval import acceptance


def _diagnostic() -> dict[str, object]:
    return {
        "state": "rejected",
        "reason_code": "claim_binding_failed",
        "detail": "candidate answer had no evidence-bound claim",
        "prepared_message_count": 2,
        "candidate_claim_count": 1,
        "bound_claim_count": 0,
    }


def test_public_trace_exposes_only_whitelisted_synthesis_diagnostic() -> None:
    raw = {
        "step_id": "synthesize",
        "name": "answer_synthesis",
        "status": "completed",
        "output_summary": json.dumps(
            {
                "diagnostic": {
                    **_diagnostic(),
                    "prompt": "private prompt",
                    "evidence_body": "private evidence",
                }
            },
            ensure_ascii=False,
        ),
    }

    public = _public_trace_step(raw)

    assert public["diagnostic"] == _diagnostic()
    assert "private prompt" not in json.dumps(public, ensure_ascii=False)
    assert "private evidence" not in json.dumps(public, ensure_ascii=False)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("state", 1),
        ("reason_code", ["claim_binding_failed"]),
        ("detail", {"prompt": "PRIVATE_PROMPT", "evidence_body": "PRIVATE_EVIDENCE"}),
        ("prepared_message_count", "2"),
        ("candidate_claim_count", True),
        ("bound_claim_count", -1),
    ],
)
def test_public_trace_rejects_malformed_diagnostic_shape(
    field: str,
    value: object,
) -> None:
    diagnostic = _diagnostic()
    diagnostic[field] = value
    raw = {
        "step_id": "synthesize",
        "name": "answer_synthesis",
        "status": "completed",
        "output_summary": json.dumps({"diagnostic": diagnostic}, ensure_ascii=False),
    }

    public = _public_trace_step(raw)

    assert "diagnostic" not in public
    serialized = json.dumps(public, ensure_ascii=False)
    assert "PRIVATE_PROMPT" not in serialized
    assert "PRIVATE_EVIDENCE" not in serialized


@pytest.mark.parametrize(
    "detail",
    [
        "prompt=PRIVATE_PROMPT",
        "evidence_body=PRIVATE_EVIDENCE",
        "Authorization: Bearer PRIVATE_SECRET",
        "internal receipt at /tmp/private-trace.json",
        "internal receipt at /private/tmp/private-trace.json",
        "internal receipt at /Users/a77/private-trace.json",
    ],
)
def test_public_trace_rejects_unsafe_diagnostic_detail(detail: str) -> None:
    diagnostic = _diagnostic()
    diagnostic["detail"] = detail
    raw = {
        "step_id": "synthesize",
        "name": "answer_synthesis",
        "status": "completed",
        "output_summary": json.dumps({"diagnostic": diagnostic}, ensure_ascii=False),
    }

    public = _public_trace_step(raw)

    assert "diagnostic" not in public
    serialized = json.dumps(public, ensure_ascii=False)
    assert "PRIVATE_" not in serialized
    assert "/tmp/" not in serialized
    assert "/private/tmp/" not in serialized
    assert "/Users/" not in serialized


def _fulfillment_summary() -> dict[str, object]:
    return {
        "status": "partial",
        "reason": "仍缺少：反方或证据边界",
        "evaluated_output_ids": ["direct_assessment", "counterpoint"],
        "reason_code_counts": {"evidence_unbound": 1},
        "items": [
            {
                "output_id": "direct_assessment",
                "status": "fulfilled",
                "evidence_ids": ["E1"],
                "answer_spans": ["当前主线判断……"],
                "gap": "",
                "reason_code": "",
                "candidate_count": 2,
            },
            {
                "output_id": "counterpoint",
                "status": "missing",
                "evidence_ids": [],
                "answer_spans": [],
                "gap": "工具目录里没有该输出对应的 claim",
                "reason_code": "evidence_unbound",
                "candidate_count": 1,
            },
        ],
    }


def test_public_trace_exposes_structured_fulfillment_reason_codes() -> None:
    """判缺成因必须能出内网——否则「缺哪一格」永远查不出来。

    `FulfillmentVerdict.to_dict()` 早就带 `reason_code` 与 `candidate_count`，
    orchestrator 也已写进内部 trace，但公开 trace 此前只对 `answer_synthesis`
    投影 `diagnostic`，于是这份明细一次都没出去：实测 11 个 turn 的 gaps 写着
    「最终回答未完成任务契约」，没有一个能回答缺的是哪一格。
    """

    raw = {
        "step_id": "task_fulfillment",
        "name": "task_fulfillment",
        "status": "completed",
        "output_summary": json.dumps(_fulfillment_summary(), ensure_ascii=False),
    }

    public = _public_trace_step(raw)
    fulfillment = public["fulfillment"]

    assert fulfillment["status"] == "partial"
    assert fulfillment["reason_code_counts"] == {"evidence_unbound": 1}
    assert fulfillment["evaluated_output_ids"] == [
        "direct_assessment",
        "counterpoint",
    ]
    missing = [
        item for item in fulfillment["items"] if item["status"] != "fulfilled"
    ]
    assert [item["output_id"] for item in missing] == ["counterpoint"]
    assert missing[0]["reason_code"] == "evidence_unbound"
    assert missing[0]["candidate_count"] == 1


def test_public_fulfillment_projection_drops_free_text_and_spans() -> None:
    """只放结构化字段：`gap` 与 `answer_spans` 不外放。

    `gap` 是给人读的中文长句、可能带内部措辞，`answer_spans` 是正文片段。
    定位缺哪一格靠 `output_id` + `reason_code`，那才是结构化判据。
    """

    raw = {
        "step_id": "task_fulfillment",
        "name": "task_fulfillment",
        "status": "completed",
        "output_summary": json.dumps(_fulfillment_summary(), ensure_ascii=False),
    }

    serialized = json.dumps(_public_trace_step(raw), ensure_ascii=False)

    assert "工具目录里没有该输出对应的 claim" not in serialized
    assert "当前主线判断" not in serialized
    assert "evidence_ids" not in serialized


def test_public_trace_rejects_malformed_fulfillment_shape() -> None:
    """形状不对就整体不投影——半截结构比没有更难排查。"""

    for broken in (
        {"status": "partial"},
        {"status": 1, "items": []},
        {"items": [{"output_id": "x"}]},
    ):
        raw = {
            "step_id": "task_fulfillment",
            "name": "task_fulfillment",
            "status": "completed",
            "output_summary": json.dumps(broken, ensure_ascii=False),
        }
        assert "fulfillment" not in _public_trace_step(raw), broken


def test_acceptance_capture_takes_repair_round_as_final_fulfillment() -> None:
    """修复轮排在原始判缺之后，验收要看终态而不是修复前那份。"""

    steps = [
        {
            "name": "task_fulfillment",
            "status": "completed",
            "fulfillment": {"status": "partial", "items": [], "repaired": False},
        },
        {
            "name": "task_fulfillment_repair",
            "status": "completed",
            "fulfillment": {"status": "complete", "items": [], "repaired": True},
        },
    ]

    captured = acceptance._capture_fulfillment(steps)

    assert captured["status"] == "complete"
    assert captured["repaired"] is True
    assert acceptance._capture_fulfillment([{"name": "other"}]) == {}


def test_acceptance_capture_reads_answer_synthesis_diagnostic(monkeypatch) -> None:
    def fake_get(url: str, timeout: float = 30.0):
        del timeout
        if url.endswith("/context"):
            return {"evidence": [], "gaps": []}
        if url.endswith("/trace"):
            return [
                {
                    "name": "synthesize",
                    "status": "completed",
                    "diagnostic": {
                        **_diagnostic(),
                        "prompt": "must not be retained",
                    },
                }
            ]
        raise AssertionError(url)

    monkeypatch.setattr(acceptance, "_get", fake_get)
    trace = acceptance.TurnTrace(question="q", run_id="run-1")

    acceptance._fill_run_detail("http://base", trace)

    assert trace.synthesis_diagnostic == _diagnostic()
    assert trace.trace_steps == ["synthesize"]


def test_acceptance_capture_forwards_user_to_run_detail_endpoints(monkeypatch) -> None:
    requested: list[str] = []

    def fake_get(url: str, timeout: float = 30.0):
        del timeout
        requested.append(url)
        if "/context?" in url:
            return {"evidence": [{"status": "hit"}], "gaps": []}
        if "/trace?" in url:
            return [
                {
                    "name": "synthesize",
                    "status": "completed",
                    "diagnostic": _diagnostic(),
                }
            ]
        raise AssertionError(url)

    monkeypatch.setattr(acceptance, "_get", fake_get)
    trace = acceptance.TurnTrace(question="q", run_id="run-1")

    acceptance._fill_run_detail("http://base", trace, user="default user")

    assert requested == [
        "http://base/api/runs/run-1/context?user=default+user",
        "http://base/api/runs/run-1/trace?user=default+user",
    ]
    assert trace.evidence_bound == 1
    assert trace.synthesis_diagnostic == _diagnostic()


def test_acceptance_capture_keeps_old_trace_compatible(monkeypatch) -> None:
    def fake_get(url: str, timeout: float = 30.0):
        del timeout
        if url.endswith("/context"):
            return {"evidence": [], "gaps": []}
        return [{"name": "synthesize", "status": "completed"}]

    monkeypatch.setattr(acceptance, "_get", fake_get)
    trace = acceptance.TurnTrace(question="q", run_id="run-1")

    acceptance._fill_run_detail("http://base", trace)

    assert trace.synthesis_diagnostic == {}
