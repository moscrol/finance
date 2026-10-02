"""Observer callbacks are synthetic: no model/transport identity is inferred."""

from copy import deepcopy
import socket

import pytest

from scripts.review_probes.quantity_role_contract import ContractError
from scripts.review_probes.quantity_role_observer import QuantityRoleObserver


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    from intelligence.services import llm_http_transport, llm_refine
    from intelligence.services.episode_semantic_verifier import (
        NUMERIC_CONDITION_MARK_ENV,
    )

    def deny(*args, **kwargs):
        raise AssertionError("network forbidden")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(llm_http_transport, "urlopen", deny)
    monkeypatch.setattr(llm_refine, "judge_provider_chain", lambda: ())
    monkeypatch.setenv("ASK_SEMANTIC_JUDGE", "llm")
    monkeypatch.setenv(NUMERIC_CONDITION_MARK_ENV, "1")


def native(text="若未来连续三日满足条件。"):
    return {
        "question": "研究历史数据",
        "sentences": [{"index": 1, "text": text}],
        "evidence_registry": [],
        "runtime_context": {"today": "2026-10-01"},
    }


def select(request):
    spans = []
    for sentence in request["sentences"]:
        start = sentence["text"].find("三日")
        if start >= 0:
            spans.append(
                {"sentence_index": sentence["index"], "start": start, "end": start + 2}
            )
    return spans


def core(passed=True, index=1):
    return {
        "passed": passed,
        "rejected_sentence_indexes": [] if passed else [index],
        "issues": [] if passed else ["unsupported claim"],
    }


def combined(bundle, verdict=None):
    return {
        "schema": "quantity_role_response_v1",
        "review_id": bundle["review_id"],
        "grounding_report": core() if verdict is None else verdict,
        "quantity_roles": [
            {
                "target_id": t["target_id"],
                "role": "unknown",
                "evidence_ids": [],
                "historical_source_dates": [],
                "historical_cardinality": None,
                "reason": "synthetic diagnostic, no semantic quality claim",
            }
            for t in bundle["targets"]
        ],
    }


@pytest.mark.parametrize("passed", [True, False])
def test_native_core_and_timeout_pass_through_once(passed):
    calls = []

    def transport(payload, *, timeout):
        calls.append((deepcopy(payload), timeout))
        return combined(payload, core(passed))

    observer = QuantityRoleObserver(transport, select, max_dispatches=2)
    original = native()
    before = deepcopy(original)
    assert observer(original, timeout=4.25) == core(passed)
    assert original == before and len(calls) == 1 and calls[0][1] == 4.25
    record = observer.records[-1]
    assert record["sidecar_status"] == "bound" and record["transport_calls"] == 1
    assert record["diagnostic_only"] and not record["release_authorized"]
    assert not record["model_identity_verified"]
    view = observer.delivery_view(original, review_id=record["review_id"])
    assert view["status"] == "current_binding" and not view["release_authorized"]
    assert not view["model_identity_verified"]


@pytest.mark.parametrize("passed", [True, False])
def test_bad_role_data_cannot_hide_valid_current_core(passed):
    def transport(payload, *, timeout):
        answer = combined(payload, core(passed))
        answer["quantity_roles"][0]["role"] = "invalid"
        return answer

    observer = QuantityRoleObserver(transport, select, max_dispatches=1)
    assert observer(native(), timeout=5) == core(passed)
    record = observer.records[-1]
    assert record["sidecar_status"] == "invalid_roles"
    assert (
        observer.delivery_view(native(), review_id=record["review_id"])["status"]
        == "invalid_roles"
    )


@pytest.mark.parametrize("bad", ["nonce", "core", "schema", "extra"])
def test_invalid_envelope_or_native_core_is_not_unwrapped(bad):
    def transport(payload, *, timeout):
        answer = combined(payload)
        if bad == "nonce":
            answer["review_id"] = "another-call"
        elif bad == "core":
            answer["grounding_report"]["passed"] = "yes"
        elif bad == "schema":
            answer["schema"] = "quantity_role_shadow_v1"
        else:
            answer["release_authorized"] = True
        return answer

    observer = QuantityRoleObserver(transport, select, max_dispatches=1)
    with pytest.raises(ContractError):
        observer(native(), timeout=5)
    assert observer.records[-1]["sidecar_status"] == "failed"
    assert observer.records[-1]["transport_calls"] == 1


def test_no_target_sends_original_native_request_not_envelope():
    calls = []

    def transport(payload, *, timeout):
        calls.append(deepcopy(payload))
        return core()

    observer = QuantityRoleObserver(transport, select, max_dispatches=1)
    req = native("仅有定性描述。")
    assert observer(req, timeout=2) == core() and calls == [req]
    assert observer.records[-1]["sidecar_status"] == "not_requested"


def test_repeated_dispatch_is_fresh_and_old_result_is_superseded():
    observer = QuantityRoleObserver(
        lambda payload, timeout: combined(payload), select, max_dispatches=2
    )
    observer(native(), timeout=5)
    old = observer.records[-1]["review_id"]
    observer(native(), timeout=5)
    new = observer.records[-1]["review_id"]
    assert old != new
    assert (
        observer.delivery_view(native(), review_id=old)["status"]
        == "foreign_or_superseded"
    )
    assert (
        observer.delivery_view(native(), review_id=new)["status"] == "current_binding"
    )


@pytest.mark.parametrize("failure", ["transport", "invalid_roles", "budget"])
def test_failed_latest_never_resurrects_previous_bound_annotation(failure):
    calls = []

    def transport(payload, *, timeout):
        calls.append(1)
        if len(calls) > 1:
            if failure == "transport":
                raise TypeError("private transport detail")
            answer = combined(payload)
            answer["quantity_roles"] = []
            return answer
        return combined(payload)

    observer = QuantityRoleObserver(
        transport, select, max_dispatches=1 if failure == "budget" else 2
    )
    observer(native(), timeout=5)
    prior = observer.records[-1]["review_id"]
    if failure == "invalid_roles":
        observer(native(), timeout=5)
    else:
        with pytest.raises((TypeError, RuntimeError)):
            observer(native(), timeout=5)
    assert (
        observer.delivery_view(native(), review_id=prior)["status"]
        == "foreign_or_superseded"
    )
    assert len(calls) == (1 if failure == "budget" else 2)
    assert "private transport detail" not in str(observer.records)


def test_delivery_text_or_context_change_invalidates_binding():
    observer = QuantityRoleObserver(
        lambda payload, timeout: combined(payload), select, max_dispatches=1
    )
    req = native()
    observer(req, timeout=5)
    identifier = observer.records[-1]["review_id"]
    for part in ["text", "context"]:
        current = deepcopy(req)
        if part == "text":
            current["sentences"][0]["text"] += "（待核）"
        else:
            current["runtime_context"]["today"] = "2026-10-02"
        view = observer.delivery_view(current, review_id=identifier)
        assert view["status"] == "stale" and not view["release_authorized"]


def test_mutable_selectors_transport_and_record_readers_do_not_edit_native_input():
    def selector(req):
        spans = select(req)
        req["question"] = "selector edit"
        return spans

    def transport(payload, *, timeout):
        return combined(payload)

    observer = QuantityRoleObserver(transport, selector, max_dispatches=1)
    req = native()
    before = deepcopy(req)
    observer(req, timeout=5)
    assert req == before
    records = observer.records
    records[-1]["response"]["review_id"] = "reader edit"
    assert observer.records[-1]["response"]["review_id"] != "reader edit"


def test_transport_mutating_wire_is_rejected_without_retry():
    calls = []

    def transport(payload, *, timeout):
        calls.append(1)
        payload["native_request"]["question"] = "changed wire"
        return combined(payload)

    observer = QuantityRoleObserver(transport, select, max_dispatches=1)
    with pytest.raises(ContractError):
        observer(native(), timeout=5)
    assert len(calls) == 1


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), True])
def test_invalid_timeout_does_not_dispatch(timeout):
    def transport(*args, **kwargs):
        raise AssertionError("must not dispatch")

    observer = QuantityRoleObserver(transport, select, max_dispatches=1)
    with pytest.raises(ValueError):
        observer(native(), timeout=timeout)
    assert observer.records[-1]["transport_calls"] == 0


@pytest.mark.parametrize("cap", [0, -1, True, 1.5])
def test_invalid_budget_is_not_an_implicit_unlimited_mode(cap):
    with pytest.raises(ValueError):
        QuantityRoleObserver(lambda *a: None, select, max_dispatches=cap)


def test_real_verifier_preserves_mark_with_observer_and_has_no_extra_dispatch():
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.research_contract import ResearchDeadline
    from intelligence.tests.test_episode_semantic_verifier import _structural, _judge

    frame, verified = _structural("若未来连续三日满足条件，则调整判断。")
    base = _judge(True)
    expected = SemanticEpisodeVerifier(judge_fn=base).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(30),
    )
    calls = []

    def transport(payload, *, timeout):
        calls.append(1)
        return combined(payload)

    observer = QuantityRoleObserver(transport, select, max_dispatches=3)
    actual = SemanticEpisodeVerifier(judge_fn=observer).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(30),
    )
    assert (
        actual.public_answer == expected.public_answer
        and "待核" in actual.public_answer
    )
    assert (actual.status, actual.judge_status, actual.issues) == (
        expected.status,
        expected.judge_status,
        expected.issues,
    )
    assert len(calls) == len(base.calls) == 1


def test_real_repair_deletion_keeps_native_rejection_and_does_not_reuse_old_roles():
    from intelligence.services.episode_semantic_verifier import (
        SemanticEpisodeVerifier,
        _numbered_sentences,
    )
    from intelligence.services.research_contract import ResearchDeadline
    from intelligence.tests.test_episode_semantic_verifier import _structural

    # Exercise the existing fact_beyond_evidence path under unchanged defaults.
    # Keep two substantive sentences (>80 chars) so deletion is not stub rollback.
    safe = "市场判断需要结合已有证据和后续变化，当前结论应保持谨慎，不能把短期观察当成稳定趋势，也不能把未取得的数据当成已经核实的事实，证据不足的部分仍需明确保留边界。现有判断以可复核的信息为基础，后续证据发生变化时需要重新审查结论。"
    frame, verified = _structural(safe + "政策变化推动了上述三日的市场上涨。")
    target = next(
        row["index"]
        for row in _numbered_sentences(verified.outcome.draft)
        if "三日" in row["text"]
    )

    def verdict(passed):
        value = core(passed, index=target)
        if not passed:
            value["reason_codes"] = [
                {"sentence_index": target, "code": "fact_beyond_evidence"}
            ]
        return value

    native_calls = []

    def baseline(request):
        native_calls.append(deepcopy(request))
        return verdict(len(native_calls) > 1)

    expected = SemanticEpisodeVerifier(judge_fn=baseline).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(30),
    )
    calls = []

    def transport(payload, *, timeout):
        calls.append(1)
        value = verdict(len(calls) > 1)
        return combined(payload, value) if "targets" in payload else value

    observer = QuantityRoleObserver(transport, select, max_dispatches=3)
    actual = SemanticEpisodeVerifier(judge_fn=observer).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(30),
    )
    assert (
        actual.public_answer == expected.public_answer
        and "三日" not in actual.public_answer
    )
    assert (actual.status, actual.judge_status, actual.issues) == (
        expected.status,
        expected.judge_status,
        expected.issues,
    )
    assert len(calls) == len(native_calls) == 2
    assert observer.records[0]["native_report"]["rejected_sentence_indexes"] == [target]
    assert observer.records[0]["native_report"]["reason_codes"] == [
        {"sentence_index": target, "code": "fact_beyond_evidence"}
    ]
    assert observer.records[-1]["sidecar_status"] == "not_requested"
    assert (
        observer.delivery_view(native(), review_id=observer.records[0]["review_id"])[
            "status"
        ]
        == "foreign_or_superseded"
    )


def test_default_no_code_semantic_rejection_policy_is_unchanged():
    from intelligence.services.episode_semantic_verifier import SemanticEpisodeVerifier
    from intelligence.services.research_contract import ResearchDeadline
    from intelligence.tests.test_episode_semantic_verifier import _structural, _judge

    frame, verified = _structural("市场仍需观察。若未来连续三日满足条件，则调整判断。")
    judge = _judge(False, rejected=(2,), issues=("unsupported claim",))
    expected = SemanticEpisodeVerifier(judge_fn=judge).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(30),
    )
    calls = []

    def transport(payload, *, timeout):
        calls.append(1)
        return combined(payload, core(False, index=2))

    observer = QuantityRoleObserver(transport, select, max_dispatches=2)
    actual = SemanticEpisodeVerifier(judge_fn=observer).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(30),
    )
    assert (
        actual.public_answer == expected.public_answer
        and "待核" in actual.public_answer
    )
    assert actual.issues == expected.issues
    assert len(calls) == len(judge.calls) == 1


@pytest.mark.parametrize("second", ["reject", "invalid_roles", "timeout"])
def test_real_material_second_review_rebinds_and_cannot_inherit_success(second):
    from dataclasses import replace
    from intelligence.services.material_grounding import ClaimSourceBinding
    from intelligence.tests.material_judge_helpers import (
        material_judge_report as reviewed,
    )
    from intelligence.tests.test_e2_material_grounding import outcome, setup, verify
    from intelligence.tests.test_e2_material_answer_review import UNBOUND_REPEAT

    frame, context = setup()
    value = outcome(context)
    value = replace(
        value,
        draft=value.draft + "\n" + UNBOUND_REPEAT,
        bindings=(
            value.bindings[0],
            replace(
                value.bindings[1],
                claims=(ClaimSourceBinding(UNBOUND_REPEAT, "reasoning"),),
            ),
        ),
    )
    native_calls = []

    def verdict(request):
        if request.get("nonfactual_review"):
            if second == "timeout":
                raise TimeoutError("synthetic deadline")
            return reviewed(request, rejected=(request["sentences"][0]["index"],))
        return reviewed(request)

    def baseline(request):
        native_calls.append(deepcopy(request))
        return verdict(request)

    expected = verify(frame, context, value, baseline)

    def spans(request):
        return [
            {
                "sentence_index": s["index"],
                "start": s["text"].index("12.5%"),
                "end": s["text"].index("12.5%") + 5,
            }
            for s in request["sentences"]
            if "12.5%" in s["text"]
        ]

    def transport(payload, *, timeout):
        request = payload["native_request"]
        response = combined(payload, verdict(request))
        if request.get("nonfactual_review") and second == "invalid_roles":
            response["quantity_roles"] = []
        return response

    observer = QuantityRoleObserver(transport, spans, max_dispatches=2)
    actual = verify(frame, context, value, observer)
    assert (
        actual.public_answer,
        actual.status,
        actual.judge_status,
        actual.issues,
    ) == (
        expected.public_answer,
        expected.status,
        expected.judge_status,
        expected.issues,
    )
    assert actual.material_nonfactual_checks == expected.material_nonfactual_checks
    assert len(native_calls) == len(observer.records) == 2
    assert [r["native_request"] for r in observer.records] == native_calls
    first, last = observer.records
    assert first["sidecar_status"] == "bound"
    assert (
        first["bundle"]["targets"][0]["sentence_index"]
        > last["bundle"]["targets"][0]["sentence_index"]
        == 1
    )
    assert first["review_id"] != last["review_id"]
    assert "material_grounding" not in last["native_request"]
    assert "material_outputs" not in last["native_request"]
    assert (
        observer.delivery_view(last["native_request"], review_id=first["review_id"])[
            "status"
        ]
        == "foreign_or_superseded"
    )
    if second == "timeout":
        assert (
            actual.judge_status == "unavailable" and last["sidecar_status"] == "failed"
        )
    else:
        assert (
            actual.status != "completed" and UNBOUND_REPEAT not in actual.public_answer
        )
        assert last["native_report"]["rejected_sentence_indexes"] == [1]
        assert last["sidecar_status"] == (
            "invalid_roles" if second == "invalid_roles" else "bound"
        )


def test_real_repair_renumbering_and_public_numeric_mark_invalidate_binding():
    from intelligence.services.episode_semantic_verifier import (
        SemanticEpisodeVerifier,
        _numbered_sentences,
    )
    from intelligence.services.research_contract import ResearchDeadline
    from intelligence.tests.test_episode_semantic_verifier import _structural

    safe = "市场判断需要结合已有证据和后续变化，当前结论应保持谨慎，不能把短期观察当成稳定趋势，也不能把未取得的数据当成已经核实的事实，证据不足的部分仍需明确保留边界。现有判断以可复核的信息为基础，后续证据发生变化时需要重新审查结论。"
    frame, verified = _structural(
        "不可靠的政策消息推动了市场上涨。"
        + safe
        + "若未来连续三日满足条件，则调整判断。"
    )

    def verdict(request):
        rejected = request["sentences"][0]["text"] == "不可靠的政策消息推动了市场上涨。"
        value = core(not rejected, index=1)
        if rejected:
            value["reason_codes"] = [
                {"sentence_index": 1, "code": "fact_beyond_evidence"}
            ]
        return value

    native_calls = []

    def baseline(request):
        native_calls.append(deepcopy(request))
        return verdict(request)

    expected = SemanticEpisodeVerifier(judge_fn=baseline).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(30),
    )
    observer = QuantityRoleObserver(
        lambda payload, timeout: combined(payload, verdict(payload["native_request"])),
        select,
        max_dispatches=2,
    )
    actual = SemanticEpisodeVerifier(judge_fn=observer).verify(
        frame=frame,
        structurally_verified=verified,
        deadline=ResearchDeadline.from_timeout(30),
    )
    assert (
        actual.public_answer,
        actual.status,
        actual.judge_status,
        actual.issues,
    ) == (
        expected.public_answer,
        expected.status,
        expected.judge_status,
        expected.issues,
    )
    assert len(observer.records) == len(native_calls) == 2
    assert [r["native_request"] for r in observer.records] == native_calls
    first, last = observer.records
    assert (
        first["bundle"]["targets"][0]["sentence_index"] - 1
        == last["bundle"]["targets"][0]["sentence_index"]
    )
    assert (
        observer.delivery_view(last["native_request"], review_id=first["review_id"])[
            "status"
        ]
        == "foreign_or_superseded"
    )
    assert (
        observer.delivery_view(last["native_request"], review_id=last["review_id"])[
            "status"
        ]
        == "current_binding"
    )
    assert "待核" in actual.public_answer and "三日" in actual.public_answer
    delivered = deepcopy(last["native_request"])
    delivered["sentences"] = _numbered_sentences(actual.public_answer)
    assert (
        observer.delivery_view(delivered, review_id=last["review_id"])["status"]
        == "stale"
    )
