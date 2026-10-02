from copy import deepcopy
from dataclasses import replace
import json

import pytest

from intelligence.eval.catalog_request_view import (
    CatalogRequestClient,
    entries_for_context,
    full_catalog,
)
from intelligence.tests.test_catalog_request_view import case as _case_factory


@pytest.fixture
def case():
    return _case_factory.__wrapped__()


class Recorder:
    model = "test-unranked-model"

    def __init__(self, calls):
        self.calls = calls
        self.result = object()

    def complete(self, **request):
        self.calls.append(request)
        return self.result


def request(case):
    payload, entries, tools = case
    messages = [
        {"role": "system", "content": "Unchanged system"},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False)
            + "\n\nHISTORY must remain exact",
        },
    ]
    return entries, {"messages": messages, "tools": tools, "timeout": 8.25}


def test_enabled_requires_receipt_sink(case):
    with pytest.raises(ValueError):
        CatalogRequestClient(Recorder([]), case[1], enabled=True)


def test_disabled_delegates_exactly_once_and_preserves_identity(case):
    entries, kwargs = request(case)
    calls = []
    base = Recorder(calls)
    client = CatalogRequestClient(base, entries)
    assert client.model == base.model
    assert client.complete(**kwargs) is base.result
    assert len(calls) == 1
    assert calls[0]["messages"] is kwargs["messages"]
    assert calls[0]["tools"] is kwargs["tools"]
    assert calls[0]["timeout"] == 8.25


def test_actual_delegate_input_equals_saved_receipt(case):
    entries, kwargs = request(case)
    original = deepcopy(kwargs)
    calls = []
    receipts = []
    base = Recorder(calls)
    client = CatalogRequestClient(base, entries, enabled=True, record=receipts.append)
    assert client.complete(**kwargs) is base.result
    assert len(calls) == len(receipts) == 1
    assert receipts[0]["applied"]
    assert receipts[0]["sent_request"] == calls[0]
    assert receipts[0]["original_request"] == kwargs == original
    assert receipts[0]["sent_sha256"] != receipts[0]["original_sha256"]
    assert calls[0]["messages"][1]["content"].endswith("\n\nHISTORY must remain exact")
    assert calls[0]["tools"] is kwargs["tools"]


def test_failed_receipt_prevents_model_call(case):
    entries, kwargs = request(case)
    calls = []

    def broken(_):
        raise OSError("receipt disk full")

    client = CatalogRequestClient(Recorder(calls), entries, enabled=True, record=broken)
    with pytest.raises(OSError):
        client.complete(**kwargs)
    assert calls == []


def test_sink_cannot_mutate_request(case):
    entries, kwargs = request(case)
    calls = []

    def corrupt(receipt):
        receipt["sent_request"]["tools"].clear()

    CatalogRequestClient(
        Recorder(calls), entries, enabled=True, record=corrupt
    ).complete(**kwargs)
    assert calls[0]["tools"] == kwargs["tools"] and calls[0]["tools"]


def test_following_user_or_tool_messages_are_never_rewritten(case):
    entries, kwargs = request(case)
    text = kwargs["messages"][1]["content"]
    kwargs["messages"] += [
        {"role": "tool", "content": text, "tool_call_id": "one"},
        {"role": "user", "content": text},
    ]
    calls = []
    receipts = []
    CatalogRequestClient(
        Recorder(calls), entries, enabled=True, record=receipts.append
    ).complete(**kwargs)
    assert calls[0]["messages"][2:] == kwargs["messages"][2:]
    assert receipts[0]["applied"]


@pytest.mark.parametrize(
    "text", ["not json", '{"available_tools":"one","available_tools":"two"}', "[]"]
)
def test_unrecognized_initial_payload_retains_original(case, text):
    entries, kwargs = request(case)
    kwargs["messages"][1]["content"] = text
    calls = []
    receipts = []
    CatalogRequestClient(
        Recorder(calls), entries, enabled=True, record=receipts.append
    ).complete(**kwargs)
    assert calls[0] == kwargs
    assert not receipts[0]["applied"]


def test_finalization_returns_original_catalog(case):
    entries, kwargs = request(case)
    receipts = []
    calls = []
    client = CatalogRequestClient(
        Recorder(calls), entries, enabled=True, record=receipts.append
    )
    client.complete(**kwargs)
    client.complete(**{**kwargs, "tools": []})
    assert receipts[0]["applied"] and not receipts[1]["applied"]
    assert calls[1]["messages"] is kwargs["messages"]
    assert (
        full_catalog(entries)
        in json.loads(kwargs["messages"][1]["content"].split("\n\nHISTORY")[0])[
            "available_tools"
        ]
    )


@pytest.mark.parametrize("kind", ["episode", "reference", "glm_runtime"])
def test_real_loop_client_seam_and_receipts(kind):
    from intelligence.tests.test_harness_reference_loop import (
        _frame,
        _context,
        _registry,
        _ScriptedModel,
        _tool_turn,
        _finish_turn,
    )
    from intelligence.services.research_tool_registry import ResearchToolRegistry
    from intelligence.runtime.agent_episode import ContinuousAgentEpisode
    from intelligence.runtime.harness_reference_loop import HarnessReferenceLoop

    frame = _frame()
    context = _context(frame)
    spec = _registry().resolve("market_data")
    registry = ResearchToolRegistry(
        (
            replace(
                spec,
                description=spec.description * 12,
                contract="只按本轮数据来源解释，不增加未授权读取，也不把空结果当作事实。",
            ),
        )
    )
    entries = entries_for_context(registry, context)
    base = _ScriptedModel([_tool_turn(), _finish_turn()])
    receipts = []
    client = CatalogRequestClient(base, entries, enabled=True, record=receipts.append)
    from intelligence.runtime.glm_agent_runtime import GLMAgentRuntime

    loop = (
        GLMAgentRuntime(client=client)
        if kind == "glm_runtime"
        else ContinuousAgentEpisode(client)
        if kind == "episode"
        else HarnessReferenceLoop(client)
    )
    result = loop.run(task_frame=frame, context=context, registry=registry)
    assert result.status == "completed"
    assert len(receipts) == len(base.calls) == 2
    assert receipts[0]["applied"]
    for receipt, wire in zip(receipts, base.calls):
        assert receipt["sent_request"] == wire
        assert receipt["original_request"]["tools"] == wire["tools"]
    assert (
        entries[0].description
        in receipts[0]["original_request"]["messages"][1]["content"]
    )
    assert (
        entries[0].description
        not in receipts[0]["sent_request"]["messages"][1]["content"]
    )


def test_native_glm_serialized_http_body_matches_projection_receipt(case):
    from contextlib import contextmanager
    from io import BytesIO
    from intelligence.runtime.glm_agent_runtime import GLMModelClient
    from intelligence.services import llm_refine

    entries, kwargs = request(case)
    provider = llm_refine.LLMProvider(
        name="unit",
        api_key="not-a-real-key",
        base_url="https://unit.example.invalid/v1",
        model="unit-model",
    )
    bodies = []
    receipts = []

    @contextmanager
    def intercept(req, timeout, **extras):
        del timeout, extras
        bodies.append(json.loads(req.data))
        yield BytesIO(
            json.dumps(
                {
                    "model": "unit-model",
                    "choices": [
                        {"message": {"role": "assistant", "content": "offline reply"}}
                    ],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                }
            ).encode()
        )

    client = CatalogRequestClient(
        GLMModelClient(providers=(provider,)),
        entries,
        enabled=True,
        record=receipts.append,
    )
    with llm_refine.http_transport_override(intercept):
        result = client.complete(**kwargs)
    assert result.content == "offline reply", result.error
    assert len(bodies) == len(receipts) == 1
    assert receipts[0]["applied"]
    assert bodies[0]["messages"] == receipts[0]["sent_request"]["messages"]
    assert bodies[0]["tools"] == receipts[0]["sent_request"]["tools"]


def test_entry_snapshot_respects_capability_and_read_scope():
    from intelligence.tests.test_harness_reference_loop import (
        _frame,
        _context,
        _registry,
    )

    context = _context(_frame())
    registry = _registry()
    assert entries_for_context(registry, context)
    denied = replace(
        context, contract=replace(context.contract, allowed_capabilities=())
    )
    assert entries_for_context(registry, denied) == ()
    assert entries_for_context(registry.with_read_scope("material_only"), context) == ()
